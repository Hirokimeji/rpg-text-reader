"""Create a portable release with source and third-party notices, no game data."""
from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path
import hashlib
import shutil
import sys
import urllib.request
import zipfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

root = Path(__file__).resolve().parent
release = root / 'release' / '台词拾光_1.4.0_便携版'
release.mkdir(parents=True, exist_ok=True)
licenses = release / '第三方许可'
licenses.mkdir(exist_ok=True)
for name in ('PySide6_Essentials', 'shiboken6', 'openpyxl', 'et_xmlfile', 'PyInstaller', 'Pillow', 'lxml', 'packaging', 'setuptools',
             'UnityPy', 'TypeTreeGeneratorAPI', 'lz4', 'brotli', 'texture2ddecoder', 'etcpak', 'astc-encoder-py',
             'fmod_toolkit', 'fsspec', 'attrs', 'tpk_ar'):
    try:
        dist = distribution(name)
    except PackageNotFoundError:
        continue
    folder = licenses / name
    folder.mkdir(exist_ok=True)
    (folder / '包信息.txt').write_text(f'{name} {dist.version}\n' + (dist.read_text('METADATA') or ''), encoding='utf-8')
    for item in dist.files or []:
        if any(part in str(item).lower() for part in ('license', 'licence', 'copying')):
            source = Path(dist.locate_file(item))
            if source.is_file():
                shutil.copy2(source, folder / source.name)
shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt', licenses/'Python-LICENSE.txt')
for filename, url in [('LGPL-3.0.txt', 'https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/LGPL-3.0-only.txt'),
                      ('GPL-3.0.txt', 'https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/GPL-3.0-only.txt')]:
    target = licenses / filename
    if not target.exists():
        previous = root/'third_party'/filename
        if previous.exists():
            shutil.copy2(previous, target)
        else:
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
(licenses/'Qt与PySide6说明.txt').write_text(
    '此程序使用 Qt / PySide6 6.12.0 的 LGPL 组件。版权归 The Qt Company 及相应贡献者所有。\n'
    '许可证文本见 LGPL-3.0.txt 和 GPL-3.0.txt；商业许可证文件是上游包附带的另一种授权选项。\n'
    'Qt 源码：https://code.qt.io/cgit/qt/\n'
    'PySide6 / Shiboken 源码：https://code.qt.io/cgit/pyside/pyside-setup.git/\n'
    '源码下载：https://download.qt.io/official_releases/QtForPython/\n'
    '本程序源文件、依赖版本和重新打包脚本位于“源代码”。用户可以修改源码、替换组件并重新构建。\n'
    '对这些 LGPL 组件的替换、修改和为调试修改而进行的逆向工程不施加额外限制。\n', encoding='utf-8-sig')
source_folder = release / '源代码'
source_folder.mkdir(exist_ok=True)
for name in ('app.py', 'ui_theme.py', 'engine.py', 'exporter.py', 'rgss.py', 'srpg.py', 'unity_reader.py', 'app.ico', 'requirements.txt', 'build.ps1', 'textlight.spec', 'package_release.py', 'version_info.txt', 'test_engine.py', 'test_gui.py', 'test_rgss.py', 'test_srpg.py', 'test_unity.py'):
    shutil.copy2(root/name, source_folder/name)
shutil.copytree(root/'vendor'/'srpg', source_folder/'vendor'/'srpg', dirs_exist_ok=True)
shutil.copytree(root/'third_party', source_folder/'third_party', dirs_exist_ok=True)
shutil.copy2(root/'vendor'/'srpg'/'LICENSE', licenses/'SRPG-ToolBox-MIT.txt')
shutil.copy2(root/'vendor'/'srpg'/'README.md', licenses/'SRPG-ToolBox说明.md')
shutil.copy2(root/'README.md', source_folder/'README.md')
shutil.copy2(root/'quickstart.txt', source_folder/'quickstart.txt')
shutil.copytree(root/'docs'/'images', source_folder/'docs'/'images', dirs_exist_ok=True)
shutil.copytree(root/'assets'/'icons', source_folder/'assets'/'icons', dirs_exist_ok=True)
shutil.copytree(root/'assets'/'ui', source_folder/'assets'/'ui', dirs_exist_ok=True)
shutil.copy2(root/'README.md', release/'使用说明.md')
shutil.copy2(root/'quickstart.txt', release/'先看这里.txt')
if (root/'docs'/'images').is_dir():
    shutil.copytree(root/'docs'/'images', release/'docs'/'images', dirs_exist_ok=True)
shutil.copy2(root/'dist'/'台词拾光.exe', release/'台词拾光.exe')
exe = release/'台词拾光.exe'
(release/'SHA256.txt').write_text(hashlib.sha256(exe.read_bytes()).hexdigest()+'  台词拾光.exe\n', encoding='utf-8')
archive = root/'release'/'台词拾光_1.4.0_便携版.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in sorted(release.rglob('*')):
        if path.is_file():
            z.write(path, path.relative_to(release.parent))
print(str(archive))
print(f'EXE: {exe.stat().st_size/1024/1024:.1f} MB')
print(f'ZIP: {archive.stat().st_size/1024/1024:.1f} MB')
