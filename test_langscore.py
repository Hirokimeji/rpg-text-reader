import csv
import tempfile
import unittest
from pathlib import Path

from langscore import load_langscore


def write_csv(root, name, rows, columns=('original', 'ja', 'zh-cn'), folder='translate'):
    file = root / 'data' / folder / (name + '.csv')
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    return file


class LangscoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_multiline_quotes_commas_bom_and_language_alias(self):
        original = 'First, line\n"second"'
        translated = '第一行，\n"第二行"'
        write_csv(self.root, 'Map001', [(original, original, translated)],
                  columns=('original', 'ja', 'ZH_CN'))
        tables = load_langscore(self.root)
        self.assertEqual(tables.language, 'zh-cn')
        self.assertEqual(tables.find(original.replace('\n', '\r\n'), 'Map001.json:events[1]'), translated)
        self.assertEqual(list(tables.unused_entries()), [])

    def test_conflicting_map_translations_stay_in_their_own_tables(self):
        write_csv(self.root, 'Map001', [('Hello', 'Hello', '你好')])
        write_csv(self.root, 'Map002', [('Hello', 'Hello', '您好')])
        tables = load_langscore(self.root)
        self.assertIsNone(tables.find('Hello'))
        self.assertEqual(tables.find('Hello', 'Map001.json:events[1]'), '你好')
        self.assertEqual(tables.find('Hello', 'Map002.json:events[1]'), '您好')
        self.assertIsNone(tables.find('Hello', 'Map003.json:events[1]'))

    def test_common_event_fallback_and_unambiguous_trailing_newlines(self):
        write_csv(self.root, 'CommonEvents', [('Shared', 'Shared', '公共对白'), ('End\n', 'End', '结尾')])
        tables = load_langscore(self.root)
        self.assertEqual(tables.find('Shared', 'Map001.json'), '公共对白')
        self.assertEqual(tables.find('End', 'CommonEvents.json'), '结尾')

    def test_legacy_folder_and_language_patch_folder(self):
        write_csv(self.root, 'CommonEvents', [('Hi', '你好')], columns=('original', 'zh-tw'), folder='translates')
        self.assertEqual(load_langscore(self.root).language, 'zh-tw')
        write_csv(self.root, 'CommonEvents', [('Hi', '你好')], columns=('original', 'zh-cn'), folder='translate/zh-cn')
        tables = load_langscore(self.root)
        self.assertEqual(tables.language, 'zh-cn')
        self.assertEqual(tables.folder.name, 'zh-cn')

    def test_duplicate_rows_follow_plugin_last_row_and_bad_rows_are_reported(self):
        file = write_csv(self.root, 'System', [('Title', 'Title', '旧标题'),
                                              ('Title', 'Title', '新标题'), ('broken',)])
        tables = load_langscore(self.root)
        self.assertEqual(tables.find('Title', 'System.json'), '新标题')
        self.assertEqual(tables.incomplete_files, ['data/translate/System.csv'])
        self.assertEqual(len(tables.warnings), 1)

    def test_empty_translations_and_no_chinese_column_keep_original(self):
        write_csv(self.root, 'Map001', [('Hello', 'Hello', '')])
        self.assertIsNone(load_langscore(self.root).find('Hello', 'Map001.json'))
        write_csv(self.root, 'Map001', [('Hello', 'Hello', 'English')], columns=('original', 'ja', 'en'))
        self.assertIsNone(load_langscore(self.root))
