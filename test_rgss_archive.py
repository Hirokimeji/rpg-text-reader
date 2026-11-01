import struct
import tempfile
import unittest
from pathlib import Path

from engine import extract, game_root
from rgss_archive import RgssArchive, prepare_archive, find_archive
from test_rgss import encode


def archive_bytes(files):
    """Build test containers; encode the stream byte by byte."""
    seed = 21
    key = seed * 9 + 3
    position = 12 + sum(16 + len(name.encode()) for name, _ in files) + 16
    index, body = bytearray(), bytearray()
    for n, (name, data) in enumerate(files):
        file_key = 0x12345678 + n
        name = name.encode()
        index.extend(struct.pack('<4I', *(v ^ key for v in (position, len(data), file_key, len(name)))))
        index.extend(c ^ ((key >> (8 * (i % 4))) & 255) for i, c in enumerate(name))
        for i, c in enumerate(data):
            if i and i % 4 == 0:
                file_key = (file_key * 7 + 3) & 0xffffffff
            body.append(c ^ ((file_key >> (8 * (i % 4))) & 255))
        position += len(data)
    index.extend(struct.pack('<4I', key, key, key, key))
    return b'RGSSAD\0\3' + struct.pack('<I', seed) + index + body


def game_files():
    cmd = lambda code, parameters: ('RPG::EventCommand', {'code': code, 'indent': 0, 'parameters': parameters})
    values = {
        'System': ('RPG::System', {'game_title': '归档测试'}),
        'MapInfos': {1: ('RPG::MapInfo', {'name': '书房'})},
        'Map001': ('RPG::Map', {'events': {1: ('RPG::Event', {'id': 1, 'name': '见面', 'pages': [
            ('RPG::Event::Page', {'list': [cmd(101, ['', 0, 0, 2]), cmd(401, ['你好，旅行者。']), cmd(0, [])]})]})}}),
    }
    return [(f'Data/{name}.rvdata2', b'\x04\x08' + encode(value)) for name, value in values.items()]


class ArchiveTests(unittest.TestCase):
    def test_word_stream_and_partial_final_word(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'Game.rgss3a'
            for length in (1, 3, 4, 5, 65535, 65536, 65537):
                value = bytes(i % 251 for i in range(length))
                path.write_bytes(archive_bytes([('Data/Test.rvdata2', value)]))
                archive = RgssArchive(path)
                self.assertEqual(archive.read(archive.entries[0]), value)

    def test_exe_folder_and_direct_archive_use_full_game(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'Game.rgss3a'
            path.write_bytes(archive_bytes(game_files() + [('Data/Scripts.rvdata2', b'not executable here')]))
            exe = root / 'Game.exe'
            exe.write_bytes(b'not a program')
            cache = root / 'MTool_MapDataCache'
            cache.mkdir()
            (cache / '1.json').write_text('{}')
            original = path.read_bytes()
            for source in (path, root, exe):
                result = extract(str(source))
                self.assertEqual(result.title, '归档测试')
                self.assertEqual(result.root, str(root.resolve()))
                self.assertEqual(result.stats['coverage']['read_indexed_maps'], 1)
                self.assertEqual([r.display for r in result.records if r.category == '对白'], ['你好，旅行者。'])
                self.assertNotIn('partial_reason', result.stats['coverage'])
                self.assertEqual(game_root(source), root.resolve())
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse((root / 'Data').exists())

    def test_temporary_data_is_removed_and_cancelled(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'Game.rgss3a'
            path.write_bytes(archive_bytes(game_files()))
            with prepare_archive(path) as (prepared, _):
                self.assertTrue((prepared / 'Data/System.rvdata2').is_file())
            self.assertFalse(prepared.exists())
            with self.assertRaises(InterruptedError):
                extract(str(path), cancelled=lambda: True)

    def test_malformed_indexes_and_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'Game.rgss3a'
            cases = [b'bad', archive_bytes(game_files())[:30],
                     archive_bytes([('../outside.rvdata2', b'bad')]),
                     archive_bytes([('Data/../outside.rvdata2', b'bad')]),
                     archive_bytes([('C:/outside.rvdata2', b'bad')]),
                     archive_bytes([('Data/Test.rvdata2', b'a'), ('data/test.rvdata2', b'b')])]
            for value in cases:
                path.write_bytes(value)
                with self.assertRaises(ValueError):
                    RgssArchive(path)
            path.write_bytes(archive_bytes([('Graphics/a.png', b'picture')]))
            with self.assertRaisesRegex(ValueError, '缺少'):
                extract(str(path))

    def test_current_runtime_wins_over_archived_residue(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'Game.rgss3a').write_bytes(b'old archive')
            (root / 'data').mkdir()
            (root / 'js').mkdir()
            (root / 'data/System.json').write_text('{}')
            (root / 'js/rmmz_core.js').write_text('')
            self.assertIsNone(find_archive(root))
            (root / 'Data/MapInfos.rvdata2').write_bytes(b'data')
            (root / 'Data/System.rvdata2').write_bytes(b'data')
            self.assertIsNone(find_archive(root))


if __name__ == '__main__':
    unittest.main()
