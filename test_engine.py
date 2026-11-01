import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import Translator, clean, extract, game_root, json_from_js, translation_candidates
from exporter import export_records


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        (self.root / 'js').mkdir()
        (self.root / 'js' / 'rmmz_core.js').write_text('// marker')
        self.write('System', {'gameTitle': '测试游戏', 'terms': {'messages': {'test': '=1+1'}}})
        self.write('MapInfos', [None, {'id': 1, 'name': '起点'}])
        cmds = [self.cmd(101, ['', 0, 0, 2, 'Alice']), self.cmd(401, ['Hello']), self.cmd(401, ['World']),
                self.cmd(102, [['Yes', 'No'], 0]), self.cmd(402, [0, 'Yes']),
                self.cmd(401, ['Partial'], 1), self.cmd(401, ['Missing'], 1), self.cmd(404, []),
                self.cmd(401, ['Hello']), self.cmd(355, ['const text = "safe";']), self.cmd(0, [])]
        pages = [{'conditions': {'switch1Valid': True, 'switch1Id': 2}, 'list': cmds},
                 {'conditions': {}, 'list': [self.cmd(401, ['Hello']), self.cmd(0, [])]}]
        self.write('Map001', {'displayName': 'Starting place', 'events': [None, {'id': 1, 'name': '对话', 'pages': pages}]})
        self.write('CommonEvents', [None, {'id': 1, 'name': '问候', 'list': [self.cmd(401, ['Hello'])]}])
        self.write('Troops', [None, {'id': 1, 'name': 'Slime', 'pages': [{'list': [self.cmd(401, ['Battle'])]}]}])
        self.translation = self.root / '翻译.json'
        self.translation.write_text(json.dumps({'Hello\nWorld': '你好\n世界', 'Hello': '你好', 'Partial': '部分',
            'Yes': '是', 'No': '否', 'Alice': '爱丽丝', 'Unused': '未关联', 'Blank': ''}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def cmd(code, parameters, indent=0):
        return {'code': code, 'parameters': parameters, 'indent': indent}

    def write(self, stem, data):
        (self.root / 'data' / (stem + '.json')).write_text(json.dumps(data), encoding='utf-8')

    def run_extract(self):
        return extract(str(self.root), str(self.translation))

    def test_paragraph_matching_and_scene_duplicates(self):
        result = self.run_extract()
        para = next(r for r in result.records if r.raw == 'Hello\nWorld')
        self.assertEqual(para.translation, '你好\n世界')
        self.assertEqual(para.speaker, '爱丽丝')
        self.assertIn('开关#2', para.context)
        partial = next(r for r in result.records if r.raw == 'Partial\nMissing')
        self.assertEqual(partial.status, '部分匹配')
        self.assertEqual(partial.translation, '部分\nMissing')
        self.assertIn('选择：是', partial.context)
        repeats = [r for r in result.records if r.raw == 'Hello' and r.category == '对白']
        self.assertEqual(len(repeats), 3)
        self.assertEqual(len({r.scene_id for r in repeats}), 3)
        self.assertTrue(any(r.raw == 'Unused' and r.group == '未关联场景' for r in result.records))
        self.assertTrue(any(r.category == '脚本／插件（待辨识）' for r in result.records))
        self.assertTrue(any(r.group == '战斗事件' for r in result.records))

    def test_no_translation_and_detection(self):
        result = extract(str(self.root))
        self.assertTrue(all(r.status == '游戏内文本' for r in result.records))
        self.assertEqual(game_root(self.root / 'data'), self.root.resolve())
        self.assertEqual(result.engine, 'RPG Maker MZ')

    def test_langscore_auto_chinese_matching_and_explicit_mtool_priority(self):
        from test_langscore import write_csv
        (self.root / 'js/plugins.js').write_text('var $plugins = [{"name":"Langscore","status":true,"parameters":{}}];', encoding='utf-8')
        write_csv(self.root, 'Map001', [('Hello\nWorld', 'Hello\nWorld', 'CSV中文对白')])
        write_csv(self.root, 'Actors', [('Alice', 'Alice', '爱丽丝')])
        result = extract(str(self.root))
        row = next(r for r in result.records if r.raw == 'Hello\nWorld')
        self.assertEqual((row.original, row.translation, row.speaker), ('Hello\nWorld', 'CSV中文对白', '爱丽丝'))
        self.assertEqual(result.stats['translation_language'], 'zh-cn')
        self.assertEqual(Path(result.translation_file).resolve(), (self.root / 'data/translate').resolve())
        explicit = self.run_extract()
        self.assertEqual(next(r.translation for r in explicit.records if r.raw == 'Hello\nWorld'), '你好\n世界')
        self.assertNotIn('translation_language', explicit.stats)
        (self.root / 'js/plugins.js').write_text('var $plugins = [{"name":"Langscore","status":false,"parameters":{}}];', encoding='utf-8')
        self.assertTrue(all(not r.translation for r in extract(str(self.root)).records))

    def test_map_cache_fallback_is_marked_as_fragments_and_native_data_wins(self):
        packed = self.root / 'packed'
        cache = packed / 'MTool_MapDataCache'
        cache.mkdir(parents=True)
        exe = packed / 'Game.exe'
        exe.write_bytes(b'never execute')
        document = json.loads((self.root / 'data/Map001.json').read_text(encoding='utf-8'))
        document['events'].append({'id': 99, 'x': 1, 'y': 1})  # Position-only cache entries carry no dialogue.
        (cache / '1.json').write_text(json.dumps(document), encoding='utf-8')
        before = (cache / '1.json').read_bytes()
        self.assertEqual(game_root(exe), packed.resolve())
        result = extract(str(exe))
        self.assertTrue(any(r.raw == 'Hello\nWorld' for r in result.records))
        self.assertEqual(result.stats['coverage']['cached_maps'], 1)
        self.assertTrue(result.stats['coverage']['partial_reason'])
        self.assertTrue(all(r.source.startswith('MTool_MapDataCache/1.json:') for r in result.records))
        folder = export_records(result, result.records, str(packed / 'out'))
        self.assertIn('仅读取已缓存地图', next(folder.glob('*.txt')).read_text(encoding='utf-8-sig'))
        self.assertEqual((cache / '1.json').read_bytes(), before)
        shutil.copytree(cache, self.root / 'MTool_MapDataCache')
        native = extract(str(self.root))
        self.assertEqual(native.engine, 'RPG Maker MZ')
        self.assertNotIn('partial_reason', native.stats['coverage'])

    def test_packed_ace_without_data_or_cache_reports_what_is_missing(self):
        folder = self.root / 'protected'
        folder.mkdir()
        exe = folder / 'Game.exe'
        exe.write_bytes(b'never execute')
        (folder / 'Game.ini').write_text('[Game]\nLibrary=System\\RGSS301.dll\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'VX Ace.*Data'):
            extract(str(exe))

    def test_encrypted_common_events_are_counted_and_searchable(self):
        import base64
        from unittest.mock import patch
        from test_encrypted_json import CIPHER, install_profile
        profiles = install_profile(self.root)
        encrypted = self.root / 'data/CommonEvents.json'
        encrypted.write_bytes(base64.b64encode(CIPHER))
        before = encrypted.read_bytes()
        with patch('encrypted_json.PROFILES', profiles):
            result = extract(str(self.root))
        self.assertTrue(any(r.original == '补回的中文对白\n下一行' for r in result.records))
        self.assertTrue(any(r.category == '选项' and r.original == '继续' for r in result.records))
        self.assertEqual(result.stats['coverage']['decrypted_files'], ['CommonEvents.json'])
        self.assertEqual(result.stats['coverage']['incomplete_files'], [])
        self.assertEqual(encrypted.read_bytes(), before)

    def test_unreadable_events_wrong_shapes_and_missing_maps_mark_partial_exports(self):
        target = self.root / 'data/CommonEvents.json'
        for content in ('not json', '{"wrong":"shape"}'):
            with self.subTest(content=content):
                target.write_text(content, encoding='utf-8')
                result = extract(str(self.root))
                self.assertEqual(result.stats['coverage']['incomplete_files'], ['CommonEvents.json'])
                self.assertTrue(result.records)
        folder = export_records(result, result.records, str(self.root / 'out'))
        text = next(folder.glob('*.txt')).read_text(encoding='utf-8-sig')
        self.assertIn('本次导出可能缺少内容', text)
        manifest = json.loads((folder / '导出清单.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['coverage']['incomplete_files'], ['CommonEvents.json'])
        xlsx = export_records(result, result.records, str(self.root / 'out'), fmt='xlsx')
        from openpyxl import load_workbook
        book = load_workbook(next(xlsx.glob('*.xlsx')), read_only=True)
        try:
            info = dict(book['说明'].iter_rows(values_only=True))
            self.assertEqual(info['未读取文件'], 'CommonEvents.json')
        finally:
            book.close()
        (self.root / 'data/Map001.json').unlink()
        result = extract(str(self.root))
        self.assertIn('Map001.json', result.stats['coverage']['incomplete_files'])
        self.assertEqual(result.stats['coverage']['read_indexed_maps'], 0)

    def test_unindexed_broken_maps_are_reported_separately(self):
        (self.root / 'data/Map999.json').write_bytes(b'\0' * 30)
        result = extract(str(self.root))
        coverage = result.stats['coverage']
        self.assertEqual(coverage['incomplete_files'], [])
        self.assertEqual(coverage['unused_unread_files'], ['Map999.json'])
        self.assertEqual((coverage['read_indexed_maps'], coverage['indexed_maps']), (1, 1))

    def test_json_runtime_takes_priority_over_leftover_ace_data(self):
        for name in ('System', 'MapInfos', 'CommonEvents'):
            (self.root / 'data' / (name + '.rvdata2')).write_bytes(b'old data must not be parsed')
        self.write('CommonEvents', [None, {'id': 1, 'name': '当前事件',
                   'list': [self.cmd(401, ['当前版本的中文对白'])]}])
        for marker, engine in (('rmmz_core.js', 'RPG Maker MZ'), ('rpg_core.js', 'RPG Maker MV')):
            with self.subTest(engine=engine):
                for existing in (self.root / 'js').glob('*_core.js'):
                    existing.unlink()
                (self.root / 'js' / marker).write_text('// runtime marker')
                result = extract(str(self.root))
                self.assertEqual(result.engine, engine)
                self.assertEqual(result.title, '测试游戏')
                self.assertTrue(any(r.original == '当前版本的中文对白' for r in result.records))
                self.assertFalse(any('.rvdata2' in r.source for r in result.records))

    def test_mixed_mv_port_opens_from_exe_folder_www_and_data(self):
        wrapper = self.root / 'portable'
        www = wrapper / 'www'
        (www / 'js').mkdir(parents=True)
        (www / 'js' / 'rpg_core.js').write_text('// runtime marker')
        shutil.copytree(self.root / 'data', www / 'data')
        for name in ('System', 'MapInfos'):
            (www / 'data' / (name + '.rvdata2')).write_bytes(b'old data must not be parsed')
        exe = wrapper / 'Game.exe'
        exe.write_bytes(b'never executed')
        for source in (exe, wrapper, www, www / 'data'):
            with self.subTest(source=source.name):
                self.assertEqual(game_root(source), www.resolve())
                result = extract(str(source))
                self.assertEqual(result.engine, 'RPG Maker MV')
                self.assertTrue(any(r.raw == 'Hello\nWorld' for r in result.records))

    def test_controls_preserve_unknown_and_variables(self):
        self.assertEqual(clean(r'\C[2]\N<小明>你好\V[3]\N[2]\!\Mystery[4]'), '你好〔变量#3〕〔角色#2〕\\Mystery[4]')

    def test_translation_discovery_validates_contents_and_skips_cache(self):
        for name, content in {
            'MTool_TilesetDefinedCache.json': '{"tile": "cache"}',
            'package.json': '{"name": "game"}',
            'empty.json': '{}', 'array.json': '["text"]',
            'nested.json': '{"settings": {"enabled": true}}',
            'number.json': '{"version": 1}', 'broken.json': '{',
        }.items():
            (self.root / name).write_text(content, encoding='utf-8')
        (self.root / 'binary.json').write_bytes(b'\xff\xfe\x00')
        folder = self.root / 'translations'
        folder.mkdir()
        other = folder / 'custom.json'
        other.write_text('{"Hello": ""}', encoding='utf-8-sig')
        self.assertEqual(set(translation_candidates(self.root)), {self.translation, other})
        with self.assertRaisesRegex(ValueError, '缓存或配置文件'):
            Translator(self.root / 'MTool_TilesetDefinedCache.json')

    def test_mv_translation_discovery_searches_www_and_game_directory(self):
        www = self.root / 'www'
        www.mkdir()
        nested = www / 'translation'
        nested.mkdir()
        other = nested / 'custom.json'
        other.write_text('{"Hello": "Hi"}', encoding='utf-8')
        self.assertEqual(set(translation_candidates(www)), {self.translation, other})

    def test_dictionary_only_empty_and_bad_formats(self):
        standalone = self.root / 'standalone'
        standalone.mkdir()
        target = standalone / 'dict.json'
        target.write_text(self.translation.read_text(), encoding='utf-8')
        result = extract(str(target))
        self.assertEqual(len(result.records), 8)
        self.assertTrue(all(r.group == '未关联场景' for r in result.records))
        self.assertTrue(any(r.status == '未匹配' for r in result.records))
        target.write_text('{"bad": {"nested": "value"}}')
        with self.assertRaisesRegex(ValueError, '字符串字典'):
            extract(str(target))

    def test_normalized_line_endings(self):
        translator = Translator(self.translation)
        self.assertEqual(translator.translate('Hello\r\nWorld'), ('你好\n世界', '已匹配'))
        self.assertEqual(translator.translate('\\N<Alice>\nHello')[1], '已匹配')

    def test_cancellation(self):
        with self.assertRaises(InterruptedError):
            extract(str(self.root), cancelled=lambda: True)

    def test_plugin_data_is_parsed_without_executing(self):
        literal = '[ /* comment */ {"name":"Demo","status":true,"parameters":{"text":"https://a/b/*x*/",},}, // end\n]; evil();'
        self.assertEqual(json_from_js(literal)[0]['parameters']['text'], 'https://a/b/*x*/')
        (self.root/'js'/'plugins.js').write_text('var $plugins = ' + literal, encoding='utf-8')
        self.assertTrue(any(r.group == '插件参数' for r in self.run_extract().records))

    def test_txt_excel_and_split(self):
        from openpyxl import load_workbook
        result = self.run_extract()
        before = {str(p): p.read_bytes() for p in (self.root / 'data').glob('*.json')}
        txt = export_records(result, result.records, str(self.root / 'out'), split=True, bilingual=True)
        self.assertEqual(len(list(txt.glob('*.txt'))), len({r.scene_id for r in result.records}))
        self.assertFalse((txt / '导出未完成.txt').exists())
        contents = '\n'.join(p.read_text(encoding='utf-8-sig') for p in txt.glob('*.txt'))
        self.assertIn('原文：Hello\nWorld', contents)
        self.assertIn('部分匹配', contents)
        excel = export_records(result, result.records, str(self.root / 'out'), fmt='xlsx')
        book = load_workbook(next(excel.glob('*.xlsx')), read_only=True)
        rows = list(book['文本'].iter_rows())
        self.assertEqual(len(rows)-1, len(result.records))
        formula_text = next(row[6] for row in rows[1:] if row[6].value == '=1+1')
        self.assertEqual(formula_text.data_type, 's')
        book.close()
        self.assertEqual(before, {str(p): p.read_bytes() for p in (self.root / 'data').glob('*.json')})

    def test_long_excel_text_is_not_lost(self):
        from openpyxl import load_workbook
        result = self.run_extract()
        record = result.records[0]
        record.original = '😀' * 17000 + '末尾'
        record.raw = record.original
        record.translation = ''
        output = export_records(result, [record], str(self.root / 'out'), fmt='xlsx')
        book = load_workbook(next(output.glob('*.xlsx')), read_only=True)
        data = list(book['文本'].iter_rows(min_row=2, values_only=True))
        self.assertEqual(''.join(r[6] for r in data), record.original)
        self.assertEqual(len(data), 2)
        book.close()


if __name__ == '__main__':
    unittest.main()
