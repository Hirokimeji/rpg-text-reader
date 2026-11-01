import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from encrypted_json import GameJsonReader, decrypt_aes_ecb


KEY = bytes(range(16))
# Fixed AES/PKCS7 fixture generated independently with cryptography, not CryptoAPI.
CIPHER = base64.b64decode('U7lzI/rwYRHu1J4i6vjeAy5d60T3yCARX1ztOZXcSGuHZJOxXDxnx7NN7yPcN7SCyNKCSKioomVLxl2sFsAiff2tW+nY+DzVW/GslGjN7xbJEGpv0RuKffYPYMQutogTA16h6EWiFv7MbRFvbgruXotiCxjYm2+KlpW9E9sYK+tW/nZXrlR7bWOxxBwQFZPsnSLFVUsfZKaizlQbndgpZIVOF6hjsnsX7/0JvVLUrhyOhSNIo9vC8nx4FjdC9JTu/MOCxCdGF5iAONQDWMmuT0wB35hpbvyZJ+TcqjxVC58=')
PLAIN = b'[null, {"id": 1, "name": "\xe5\x8a\xa0\xe5\xaf\x86\xe5\x85\xac\xe5\x85\xb1\xe4\xba\x8b\xe4\xbb\xb6", "list": [{"code": 401, "parameters": ["\xe8\xa1\xa5\xe5\x9b\x9e\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\x87\xe5\xaf\xb9\xe7\x99\xbd"]}, {"code": 401, "parameters": ["\xe4\xb8\x8b\xe4\xb8\x80\xe8\xa1\x8c"]}, {"code": 102, "parameters": [["\xe7\xbb\xa7\xe7\xbb\xad", "\xe8\xbf\x94\xe5\x9b\x9e"], 0]}]}]'
PLUGIN = 'throw new Error("must never be executed");'


def install_profile(root):
    folder = root / 'js/plugins'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'Fixture.js').write_text(PLUGIN, encoding='utf-8')
    return (({'Fixture.js': hashlib.sha256(PLUGIN.encode()).hexdigest()}, KEY),)


class EncryptedJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / 'CommonEvents.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_aes_matches_independent_fixture_and_checks_padding(self):
        self.assertEqual(decrypt_aes_ecb(CIPHER, KEY), PLAIN)
        with self.assertRaisesRegex(ValueError, '校验失败'):
            decrypt_aes_ecb(CIPHER[:-1] + bytes([CIPHER[-1] ^ 1]), KEY)
        for data, key in ((b'x', KEY), (CIPHER, b'bad key')):
            with self.assertRaisesRegex(ValueError, '长度无效'):
                decrypt_aes_ecb(data, key)

    def test_fingerprinted_plugin_reads_raw_and_json_wrapped_cipher_without_writes(self):
        profiles = install_profile(self.root)
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped), patch('encrypted_json.PROFILES', profiles):
                text = base64.b64encode(CIPHER).decode()
                self.path.write_text(json.dumps(text) if wrapped else text, encoding='utf-8')
                before = self.path.read_bytes()
                reader = GameJsonReader(self.root)
                self.assertEqual(reader(self.path), json.loads(PLAIN))
                self.assertEqual(reader.decrypted_files, ['CommonEvents.json'])
                self.assertEqual(reader(self.path), json.loads(PLAIN))
                self.assertEqual(reader.decrypted_files, ['CommonEvents.json'])
                self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_or_modified_plugin_is_not_executed_or_decrypted(self):
        profiles = install_profile(self.root)
        (self.root / 'js/plugins/Fixture.js').write_text(PLUGIN + 'changed', encoding='utf-8')
        self.path.write_bytes(base64.b64encode(CIPHER))
        with patch('encrypted_json.PROFILES', profiles), patch('encrypted_json.decrypt_aes_ecb') as decrypt:
            with self.assertRaisesRegex(ValueError, '未识别'):
                GameJsonReader(self.root)(self.path)
            decrypt.assert_not_called()

    def test_plain_json_and_invalid_decrypted_structure(self):
        for value in ([None], {'text':'中文'}, '普通字符串'):
            self.path.write_text(json.dumps(value), encoding='utf-8')
            self.assertEqual(GameJsonReader(self.root)(self.path), value)
        profiles = install_profile(self.root)
        self.path.write_bytes(base64.b64encode(CIPHER))
        with patch('encrypted_json.PROFILES', profiles), patch('encrypted_json.decrypt_aes_ecb', return_value=b'"invalid shape"'):
            reader = GameJsonReader(self.root)
            with self.assertRaisesRegex(ValueError, '数据结构无效'):
                reader(self.path)
            self.assertEqual(reader.decrypted_files, [])

    def test_cipher_size_limit(self):
        self.path.write_bytes(base64.b64encode(CIPHER))
        with patch('encrypted_json.MAX_ENCRYPTED_BYTES', 16):
            with self.assertRaisesRegex(ValueError, '读取上限'):
                GameJsonReader(self.root)(self.path)
