from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import protected_reader as reader
from engine import extract


def packed_fixture(root):
    """Metadata fixture, deliberately not executable code."""
    data = bytearray(1024**2 + 1024)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<HH', data, 132, 0x14c, 1)
    struct.pack_into('<H', data, 148, 224)
    struct.pack_into('<H', data, 152, 0x10b)
    struct.pack_into('<I', data, 152+56, 0x908000)
    struct.pack_into('<4I', data, 152+224+8, 4096, 4096, len(data)-512, 512)
    (root/'Game.exe').write_bytes(data)
    (root/'Game.ini').write_bytes(b'[Game]\nLibrary=System\\RGSS301.dll\n')
    return data


class ProtectedReaderTests(unittest.TestCase):
    def test_detects_packed_ace_and_prefers_matching_original_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = packed_fixture(root)
            game = reader.packed_game(root/'Game.exe')
            self.assertEqual(game.executable, root/'Game.exe')
            (root/'Game.exe.org').write_bytes(data)
            self.assertEqual(reader.packed_game(root).executable, root/'Game.exe.org')
            (root/'Data').mkdir()
            for name in ('System.rvdata2', 'MapInfos.rvdata2'):
                (root/'Data'/name).write_bytes(b'data')
            self.assertIsNone(reader.packed_game(root))

    def test_invalid_pe_never_starts_compatibility_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packed_fixture(root)
            (root/'Game.exe').write_bytes(b'MZ invalid file')
            with patch.object(reader, 'ensure_components') as components:
                with reader.prepare_protected(root) as (prepared, metadata):
                    self.assertEqual(prepared, root)
                    self.assertIsNone(metadata)
                components.assert_not_called()

    def test_cached_component_is_verified_and_download_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            content = b'verified runtime test'
            spec = (('test.zip', len(content), hashlib.sha256(content).hexdigest(), 'https://example.invalid/test.zip'),)
            (folder/'test.zip').write_bytes(content)
            with patch.object(reader, 'component_cache', return_value=folder), patch.object(reader, 'COMPONENTS', spec), patch.object(reader, 'download') as download:
                self.assertEqual(reader.ensure_components(), folder)
                download.assert_not_called()

    def test_incomplete_offline_bundle_does_not_use_network(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'增强读取组件'
            folder.mkdir()
            with patch.object(reader, 'component_cache', return_value=folder), patch.object(reader, 'download') as download:
                with self.assertRaisesRegex(OSError, '重新解压'):
                    reader.ensure_components()
                download.assert_not_called()

    def test_bad_download_is_not_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            content = b'expected'
            spec = (('test.zip', len(content), hashlib.sha256(content).hexdigest(), 'https://example.invalid/test.zip'),)
            def bad_download(url, target, *args):
                target.write_bytes(b'wrong')
            with patch.object(reader, 'component_cache', return_value=folder), patch.object(reader, 'COMPONENTS', spec), patch.object(reader, 'download', side_effect=bad_download):
                with self.assertRaisesRegex(OSError, '校验失败'):
                    reader.ensure_components()
            self.assertFalse((folder/'test.zip').exists())
            self.assertFalse(list(folder.glob('*.part')))

    def test_offline_bundle_is_used_without_downloading(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            offline = root/'增强读取组件'
            offline.mkdir()
            value = b'offline component'
            (offline/'runtime.zip').write_bytes(value)
            spec = (('runtime.zip', len(value), hashlib.sha256(value).hexdigest(), 'https://example.invalid/runtime.zip'),)
            with patch.dict(os.environ, {}, clear=False), patch.object(reader.sys, 'frozen', True, create=True), patch.object(reader.sys, 'executable', str(root/'台词拾光.exe')), patch.object(reader, 'COMPONENTS', spec), patch.object(reader, 'download') as download:
                with patch.dict(os.environ, {'TEXTLIGHT_READER_COMPONENTS': ''}):
                    self.assertEqual(reader.ensure_components(), offline)
                download.assert_not_called()

    def test_cancel_is_propagated_without_falling_back_to_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packed_fixture(root)
            cache = root/'MTool_MapDataCache'
            cache.mkdir()
            (cache/'1.json').write_text('{}')
            @contextmanager
            def cancelled(*args):
                raise InterruptedError('已取消提取。')
                yield
            with patch('engine.prepare_protected', cancelled), patch('engine._extract') as fallback:
                with self.assertRaises(InterruptedError):
                    extract(str(root))
                fallback.assert_not_called()

    def test_failed_compatibility_attempt_keeps_cache_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packed_fixture(root)
            cache = root/'MTool_MapDataCache'
            cache.mkdir()
            (cache/'1.json').write_text('{}')
            @contextmanager
            def failed(*args):
                raise OSError('unsupported sample')
                yield
            with patch('engine.prepare_protected', failed):
                result = extract(str(root))
            self.assertIn('partial_reason', result.stats['coverage'])
            self.assertTrue(any('增强读取未完成' in w for w in result.warnings))


if __name__ == '__main__':
    unittest.main()
