"""Read JSON and known encrypted translation-plugin data without running scripts."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path


MAX_ENCRYPTED_BYTES = 64 * 1024 * 1024
# Exact loader and cipher fingerprints: this is a supported plugin variant,
# not a general RPG Maker encryption key. Unknown plugins are never executed.
PROFILES = (({
    'ActorCommand.js': 'e270d4edd42516b8571ea4c06c7800ad40b05bad1ee0ced1738ae8d378a1e7d3',
    'TYA_EnemyGauge.js': 'c6826494432163d74fd27e78ad011a13d55e4670441cd49fc9f1e52a4afd28d9',
}, bytes.fromhex('5f213d59787940462f53433f6e67542d')),)


def decrypt_aes_ecb(data: bytes, key_bytes: bytes) -> bytes:
    """AES-128 ECB / PKCS7 using Windows' system provider, no game code."""
    if sys.platform != 'win32':
        raise ValueError('读取这种加密文本需要 Windows 10 / 11。')
    if len(key_bytes) != 16 or not data or len(data) % 16:
        raise ValueError('加密文本的密钥或数据长度无效。')
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    handle = ctypes.c_size_t
    signatures = {
        'CryptAcquireContextW': [ctypes.POINTER(handle), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD],
        'CryptImportKey': [handle, ctypes.c_void_p, wintypes.DWORD, handle, wintypes.DWORD, ctypes.POINTER(handle)],
        'CryptSetKeyParam': [handle, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD],
        'CryptDecrypt': [handle, handle, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)],
        'CryptDestroyKey': [handle], 'CryptReleaseContext': [handle, wintypes.DWORD],
    }
    for name, args in signatures.items():
        fn = getattr(api, name)
        fn.argtypes = args
        fn.restype = wintypes.BOOL
    provider, key = handle(), handle()
    def check(ok):
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
    try:
        check(api.CryptAcquireContextW(ctypes.byref(provider), None, None, 24, 0xf0000000))
        blob = struct.pack('<BBHII', 8, 2, 0, 0x660e, len(key_bytes)) + key_bytes
        check(api.CryptImportKey(provider, blob, len(blob), 0, 0, ctypes.byref(key)))
        mode = wintypes.DWORD(2)  # KP_MODE / CRYPT_MODE_ECB
        check(api.CryptSetKeyParam(key, 4, ctypes.byref(mode), 0))
        buffer = ctypes.create_string_buffer(data)
        length = wintypes.DWORD(len(data))
        check(api.CryptDecrypt(key, 0, True, 0, buffer, ctypes.byref(length)))
        return buffer.raw[:length.value]
    except OSError as error:
        raise ValueError('加密文本校验失败，可能使用了不同的插件版本或密钥。') from error
    finally:
        if key:
            api.CryptDestroyKey(key)
        if provider:
            api.CryptReleaseContext(provider, 0)


class GameJsonReader:
    def __init__(self, root: Path):
        self.root = root
        self.decrypted_files = []
        self._checked = False
        self._key = None

    def _profile_key(self):
        if not self._checked:
            self._checked = True
            for fingerprints, key in PROFILES:
                try:
                    if all((self.root / 'js/plugins' / name).is_file()
                           and hashlib.sha256((self.root / 'js/plugins' / name).read_bytes()).hexdigest() == digest
                           for name, digest in fingerprints.items()):
                        self._key = key
                        break
                except OSError:
                    continue
        return self._key

    def __call__(self, path: Path):
        text = path.read_text(encoding='utf-8-sig')
        parsed_string = False
        try:
            value = json.loads(text)
        except ValueError:
            value = None
        else:
            if not isinstance(value, str):
                return value
            text = value
            parsed_string = True
        compact = ''.join(text.split())
        if len(compact) > MAX_ENCRYPTED_BYTES * 4 // 3 + 4:
            raise ValueError('加密文本超过 64 MB 读取上限。')
        try:
            cipher = base64.b64decode(compact, validate=True)
        except (ValueError, binascii.Error):
            if parsed_string:
                return value
            raise ValueError('不是可读取的 JSON 数据，文件可能损坏或使用了自定义封装。') from None
        if not cipher or len(cipher) % 16:
            if parsed_string:
                return value
            raise ValueError('不是可读取的 JSON 数据，文件可能损坏或使用了自定义封装。')
        key = self._profile_key()
        if key is None:
            if parsed_string:
                return value
            raise ValueError('检测到疑似加密文本，但未识别对应插件；此文件未提取。')
        plain = decrypt_aes_ecb(cipher, key)
        try:
            document = json.loads(plain.decode('utf-8-sig'))
        except (UnicodeError, ValueError):
            raise ValueError('解密后不是有效的 JSON，已停止读取此文件。') from None
        if not isinstance(document, (list, dict)):
            raise ValueError('解密后的数据结构无效，已停止读取此文件。')
        if path.name not in self.decrypted_files:
            self.decrypted_files.append(path.name)
        return document
