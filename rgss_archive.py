"""Read RGSSAD v3 data without running its scripts or game executable.

The container layout is documented by Archive::Rgss3a:
https://github.com/watashi/perl-archive-rgssad
Only Data/*.rvdata2 entries are decoded into a temporary directory.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import struct
import tempfile


MAX_FILE = 64 * 1024 * 1024
MAX_DATA = 256 * 1024 * 1024
MAX_TABLE = 16 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    size: int
    key: int


class RgssArchive:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries = []
        length = self.path.stat().st_size
        with self.path.open('rb') as file:
            if file.read(8) != b'RGSSAD\0\3':
                raise ValueError('不是标准的 VX Ace RGSSAD v3 数据包。')

            def read(count):
                value = file.read(count)
                if len(value) != count:
                    raise ValueError('RGSS 数据包不完整。')
                return value

            key = (struct.unpack('<I', read(4))[0] * 9 + 3) & 0xffffffff
            names = set()
            while True:
                offset = struct.unpack('<I', read(4))[0] ^ key
                if offset == 0:
                    break
                size, file_key, name_size = (n ^ key for n in struct.unpack('<3I', read(12)))
                if not 0 < name_size <= 2048 or len(self.entries) >= 100000:
                    raise ValueError('RGSS 文件索引无效或超出读取限制。')
                raw = read(name_size)
                raw = bytes(c ^ ((key >> (8 * (i % 4))) & 255) for i, c in enumerate(raw))
                try:
                    name = raw.decode('utf-8').replace('\\', '/')
                except UnicodeDecodeError as exc:
                    raise ValueError('RGSS 文件名编码无效。') from exc
                parts = PurePosixPath(name).parts
                if (not parts or name.startswith('/') or '\0' in name
                        or any(p in ('.', '..') or ':' in p for p in name.split('/'))):
                    raise ValueError('RGSS 索引包含无效路径。')
                folded = name.casefold()
                if folded in names or offset + size > length:
                    raise ValueError('RGSS 索引包含重复文件或越界位置。')
                names.add(folded)
                self.entries.append(Entry(name, offset, size, file_key))
                if file.tell() > MAX_TABLE:
                    raise ValueError('RGSS 文件索引过大。')
            if any(e.offset < file.tell() for e in self.entries):
                raise ValueError('RGSS 文件数据与索引重叠。')

    def data_entries(self):
        return [e for e in self.entries if len(PurePosixPath(e.name).parts) == 2
                and e.name.casefold().startswith('data/')
                and e.name.casefold().endswith('.rvdata2')]

    def read(self, entry: Entry, check=lambda: None) -> bytes:
        if entry.size > MAX_FILE:
            raise ValueError(f'{entry.name} 超出单文件读取限制。')
        result = bytearray(entry.size)
        key = entry.key
        with self.path.open('rb') as file:
            file.seek(entry.offset)
            for start in range(0, entry.size, 65536):
                check()
                block = file.read(min(65536, entry.size - start))
                if len(block) != min(65536, entry.size - start):
                    raise ValueError('RGSS 文件内容不完整。')
                for i in range(0, len(block), 4):
                    chunk = block[i:i+4]
                    word = int.from_bytes(chunk, 'little') ^ key
                    result[start+i:start+i+len(chunk)] = word.to_bytes(4, 'little')[:len(chunk)]
                    key = (key * 7 + 3) & 0xffffffff
        return bytes(result)


def find_archive(path: str | Path) -> Path | None:
    source = Path(path)
    if source.is_file() and source.suffix.casefold() == '.rgss3a':
        return source
    root = source.parent if source.is_file() else source
    if not root.is_dir():
        return None
    # Current MV/MZ data and expanded Ace data take precedence over old archives.
    if ((root / 'data/System.json').is_file()
            and any((root / 'js' / n).is_file() for n in ('rpg_core.js', 'rmmz_core.js'))):
        return None
    if all((root / 'Data' / n).is_file() for n in ('System.rvdata2', 'MapInfos.rvdata2')):
        return None
    candidates = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.casefold() == '.rgss3a')
    standard = next((p for p in candidates if p.name.casefold() == 'game.rgss3a'), None)
    if standard:
        return standard
    if len(candidates) > 1:
        raise ValueError('目录中有多个 RGSS 数据包，请直接选择要读取的 .rgss3a 文件。')
    return candidates[0] if candidates else None


@contextmanager
def prepare_archive(path, progress=None, cancelled=None):
    archive_path = find_archive(path)
    if archive_path is None:
        yield Path(path), None
        return
    archive = RgssArchive(archive_path)
    entries = archive.data_entries()
    names = {PurePosixPath(e.name).name.casefold() for e in entries}
    if not {'system.rvdata2', 'mapinfos.rvdata2'} <= names:
        raise ValueError('RGSS 数据包缺少 System 或 MapInfos，无法确认 VX Ace 游戏数据。')
    if sum(e.size for e in entries) > MAX_DATA:
        raise ValueError('RGSS 数据文件总量超出读取限制。')

    def check():
        if cancelled and cancelled():
            raise InterruptedError('已取消提取。')

    with tempfile.TemporaryDirectory(prefix='textlight-rgss-') as temp:
        root = Path(temp)
        (root / 'Data').mkdir()
        for n, entry in enumerate(entries):
            check()
            name = PurePosixPath(entry.name).name
            stem = name.split('.', 1)[0].upper()
            if (stem in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)),
                         *(f'LPT{i}' for i in range(10))}
                    or any(ord(c) < 32 or c in '<>"|?*' for c in name)):
                raise ValueError('RGSS 索引包含不能作为数据文件读取的名称。')
            if name.casefold() == 'scripts.rvdata2':
                continue
            if progress:
                progress(f'正在读取 RGSS 数据包 · {n+1}/{len(entries)} · {name}')
            data = archive.read(entry, check)
            (root / 'Data' / name).write_bytes(data)
        yield root, archive_path
