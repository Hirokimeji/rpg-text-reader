# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project = Path(SPECPATH)
a = Analysis(
    [str(project / 'app.py')],
    pathex=[str(project)],
    binaries=[],
    datas=[(str(project / 'app.ico'), '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'numpy', 'pandas'],
    noarchive=False,
)
# Qt uses Windows' unversioned ICU API. A same-name ICU from Poppler on PATH
# has version-suffixed exports and must not shadow the Windows system library.
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in {'icuuc.dll', 'icuin.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='台词拾光', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    version=str(project / 'version_info.txt'), icon=str(project / 'app.ico'),
)
