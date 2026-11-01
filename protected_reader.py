"""Optional, isolated compatibility reader for packed 32-bit VX Ace games.

Game binaries are only passed to BoxedWine inside a no-network AppContainer.
Downloads contain public runtime components, never game files or user data.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

from rgss_archive import find_archive


ASSETS = Path(__file__).resolve().parent / 'vendor/protected_reader/bin'
COMPONENTS = (
    ('boxedwine-download.zip', 5809236,
     '4e06e684b43c043a710a8c106011e61d6e23927b9e79048efd174fa28bc55748',
     'https://github.com/danoon2/Boxedwine/releases/download/25R1.0/Boxedwine25R1Windows-x86-x64-Arm64.zip'),
    ('wine.zip', 153742404,
     '1dbed7427341fdeee01bf6476d7795d136eeb4f11261ca769d35aa77f3eaba77',
     'https://boxedwine.org/v2/5/TinyCore15Wine9.0.zip'),
)
MAX_SOURCE = 1024**3


@dataclass(frozen=True)
class PackedGame:
    root: Path
    selected: Path
    executable: Path


def pe_layout(path: Path):
    """Small metadata-only check; never maps or executes the PE."""
    try:
        size = path.stat().st_size
        if not 512 <= size <= MAX_SOURCE:
            return None
        with path.open('rb') as file:
            header = file.read(64)
            if header[:2] != b'MZ':
                return None
            offset = struct.unpack_from('<I', header, 60)[0]
            if offset > min(size - 24, 1024**2):
                return None
            file.seek(offset)
            nt = file.read(24)
            if len(nt) != 24 or nt[:4] != b'PE\0\0':
                return None
            machine, count = struct.unpack_from('<HH', nt, 4)
            optional_size = struct.unpack_from('<H', nt, 20)[0]
            if machine != 0x14c or not 1 <= count <= 96 or not 96 <= optional_size <= 4096:
                return None
            optional = file.read(optional_size)
            if len(optional) != optional_size or optional[:2] != b'\x0b\x01':
                return None
            image_size = struct.unpack_from('<I', optional, 56)[0]
            large_payload = False
            for _ in range(count):
                section = file.read(40)
                if len(section) != 40:
                    return None
                virtual, _, raw, start = struct.unpack_from('<4I', section, 8)
                if start + raw > size:
                    return None
                large_payload |= raw > max(1024**2, virtual * 2)
            return image_size, large_payload
    except (OSError, ValueError, struct.error):
        return None


def packed_game(path: str | Path) -> PackedGame | None:
    source = Path(path).resolve()
    if source.is_file() and source.suffix.casefold() != '.exe':
        return None
    root = source.parent if source.is_file() else source
    if find_archive(path):
        return None
    if all((root / 'Data' / name).is_file() for name in ('System.rvdata2', 'MapInfos.rvdata2')):
        return None
    if ((root / 'data/System.json').is_file()
            and any((root / 'js' / name).is_file() for name in ('rpg_core.js', 'rmmz_core.js'))):
        return None
    ini = root / 'Game.ini'
    try:
        if ini.stat().st_size > 128 * 1024 or not re.search(
                rb'(?im)^\s*Library\s*=\s*.*RGSS3\d*\.dll', ini.read_bytes()):
            return None
    except OSError:
        return None
    selected = source if source.is_file() else root / 'Game.exe'
    layout = pe_layout(selected)
    if not layout or not layout[1]:
        return None
    backup = selected.with_name(selected.name + '.org')
    backup_layout = pe_layout(backup)
    executable = backup if backup_layout and backup_layout[0] == layout[0] else selected
    return PackedGame(root, selected, executable)


def digest(path: Path, cancelled=None):
    value = hashlib.sha256()
    with path.open('rb') as file:
        while block := file.read(1024**2):
            if cancelled and cancelled():
                raise InterruptedError('已取消提取。')
            value.update(block)
    return value.hexdigest()


def download(url, path, size, progress=None, cancelled=None):
    """Use Windows' bundled curl and certificate store; accept HTTPS only."""
    curl = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/curl.exe'
    if not curl.is_file():
        raise OSError('找不到系统下载组件，无法准备增强读取环境。')
    process = subprocess.Popen([
        str(curl), '-q', '--fail', '--silent', '--show-error', '--location',
        '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '30',
        '--max-time', '600', '--retry', '2', '--max-filesize', str(size),
        '--output', str(path), url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=0x08000000)
    try:
        while process.poll() is None:
            if cancelled and cancelled():
                raise InterruptedError('已取消提取。')
            received = path.stat().st_size if path.exists() else 0
            if received > size:
                raise OSError('组件下载大小异常，已停止。')
            if progress:
                progress(f'首次使用：正在下载增强读取组件 · {received / 1024**2:.1f}/{size / 1024**2:.1f} MB')
            time.sleep(0.2)
        if process.returncode:
            raise OSError('增强读取组件下载失败，请检查网络后重试。')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stderr:
            process.stderr.close()


def component_cache():
    override = os.environ.get('TEXTLIGHT_READER_COMPONENTS')
    if override:
        return Path(override)
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    bundled = base / '增强读取组件'
    if bundled.is_dir():
        return bundled
    return Path(os.environ['LOCALAPPDATA']) / 'Textlight/components/boxedwine25-wine9-v1'


def ensure_components(progress=None, cancelled=None):
    folder = component_cache()
    folder.mkdir(parents=True, exist_ok=True)
    for name, size, checksum, url in COMPONENTS:
        target = folder / name
        if target.is_file() and target.stat().st_size == size and digest(target, cancelled) == checksum:
            continue
        if folder.name == '增强读取组件':
            raise OSError('离线读取组件缺失或损坏，请重新解压完整的离线增强包。')
        # A unique staging name prevents concurrent windows from sharing partial downloads.
        descriptor, temp = tempfile.mkstemp(prefix=name+'.', suffix='.part', dir=folder)
        os.close(descriptor)
        partial = Path(temp)
        try:
            download(url, partial, size, progress, cancelled)
            if partial.stat().st_size != size or digest(partial, cancelled) != checksum:
                raise OSError('增强读取组件校验失败，请稍后重试。')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    return folder


def ascii_job():
    """Old emulators use narrow host paths; prefer an ASCII or short temp path."""
    candidates = [Path(tempfile.gettempdir()), Path(os.environ['SystemRoot']) / 'Temp']
    for base in candidates:
        try:
            root = Path(tempfile.mkdtemp(prefix='TextlightJob-', dir=base))
        except OSError:
            continue
        alias = root
        if not str(alias).isascii():
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            short_path = kernel.GetShortPathNameW
            short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            short_path.restype = ctypes.c_uint32
            buffer = ctypes.create_unicode_buffer(32768)
            if short_path(str(root), buffer, len(buffer)):
                alias = Path(buffer.value)
        if str(alias).isascii():
            return root, alias
        root.rmdir()
    raise OSError('无法创建兼容读取所需的临时目录。')


def copy_input(game: PackedGame, inp: Path, components: Path, cancelled=None):
    game_dir, host_dir, helpers = inp / 'game', inp / 'host', inp / 'helpers'
    for folder in (game_dir, host_dir, helpers):
        folder.mkdir()
    def copy(source, target):
        if cancelled and cancelled():
            raise InterruptedError('已取消提取。')
        if source.is_symlink() or not source.is_file():
            raise OSError('游戏所需文件不可用。')
        with source.open('rb') as reader, target.open('wb') as writer:
            while block := reader.read(4 * 1024**2):
                if cancelled and cancelled():
                    raise InterruptedError('已取消提取。')
                writer.write(block)
        shutil.copystat(source, target)
    required = game.executable.stat().st_size + 800 * 1024**2
    if shutil.disk_usage(inp).free < required:
        raise OSError('临时目录空间不足，增强读取需要约 1 GB 可用空间。')
    copy(game.executable, game_dir / 'Game.exe')
    copy(game.root / 'Game.ini', game_dir / 'Game.ini')
    total, count = 0, 0
    paths = list(game.root.glob('*.dll')) + list((game.root / 'System').glob('*.dll'))
    for source in paths:
        if source.name.casefold() == 'version.dll':
            continue
        total += source.stat().st_size
        count += 1
        if total > 128 * 1024**2 or count > 128:
            raise OSError('游戏启动库超出兼容读取限制。')
        target = game_dir / source.relative_to(game.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        copy(source, target)
    font_dir = game.root / 'Fonts'
    if font_dir.is_dir():
        fonts = game_dir / 'Fonts'
        fonts.mkdir()
        total, count = 0, 0
        for source in font_dir.rglob('*'):
            if not source.is_file() or source.suffix.lower() not in ('.ttf', '.otf'):
                continue
            total += source.stat().st_size
            count += 1
            if total > 64 * 1024**2 or count > 128:
                raise OSError('游戏字体超出兼容读取限制。')
            copy(source, fonts / (str(count) + source.suffix.lower()))
    copy(components / 'wine.zip', inp / 'wine.zip')
    with zipfile.ZipFile(components / 'boxedwine-download.zip') as archive:
        # Extract a single exact member, never arbitrary paths from the ZIP.
        binary = archive.read('Win64/BoxedWine.exe')
        if not binary.startswith(b'MZ') or len(binary) > 32 * 1024**2:
            raise OSError('兼容读取组件结构无效。')
        (host_dir / 'boxedwine.exe').write_bytes(binary)
    copy(ASSETS / 'version.dll', game_dir / 'version.dll')
    copy(ASSETS / 'launcher.exe', helpers / 'launcher.exe')
    copy(ASSETS / 'isolation_check.exe', host_dir / 'isolation_check.exe')


@contextmanager
def prepare_protected(path, progress=None, cancelled=None):
    game = packed_game(path) if os.name == 'nt' else None
    if game is None:
        yield Path(path), None
        return
    root = None
    try:
        components = ensure_components(progress, cancelled)
        root, alias = ascii_job()
        inp, out = root / 'input', root / 'output'
        inp.mkdir()
        out.mkdir()
        for name in ('root/home/username/.wine', 'tmp', 'profile'):
            (out / name).mkdir(parents=True)
        # The vendor prefix is already initialized. Avoid reconfiguring it for host time zones.
        (out / 'root/home/username/.wine/.update-timestamp').write_text('disable\n', encoding='ascii')
        if progress:
            progress('正在准备游戏读取副本…')
        copy_input(game, inp, components, cancelled)
        from win_sandbox import run_reader
        run_reader(root, alias, progress, cancelled)
        dump = out / 'dump'
        archive = dump / 'Game.rgss3a'
        metadata = {'root': str(game.root), 'source': game.selected.name,
                    'backup': game.executable.name if game.executable != game.selected else '',
                    'runtime': 'BoxedWine 25R1 / Wine 9.0'}
        if archive.is_file():
            yield archive, metadata
        elif all((dump / 'Data' / name).is_file() for name in ('System.rvdata2', 'MapInfos.rvdata2')):
            yield dump, metadata
        else:
            raise OSError('未找到可解析的游戏数据，该封装暂不能自动读取。')
    finally:
        if root:
            # root was created here; never remove a path derived from the selected game.
            allowed = {Path(tempfile.gettempdir()).resolve(), (Path(os.environ['SystemRoot']) / 'Temp').resolve()}
            if root.resolve().parent not in allowed or not root.name.startswith('TextlightJob-'):
                raise RuntimeError('拒绝清理非临时读取目录。')
            shutil.rmtree(root, ignore_errors=True)
