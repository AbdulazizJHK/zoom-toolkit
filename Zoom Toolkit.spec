# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# Bundle tkinterdnd2's native tkdnd binaries/data so drag-and-drop works in the exe.
dnd_datas, dnd_binaries, dnd_hidden = collect_all('tkinterdnd2')

a = Analysis(
    ['zoom_extractor.py'],
    pathex=[],
    binaries=dnd_binaries,
    datas=[('app_icon.ico', '.'), ('settings_icon.ico', '.')] + dnd_datas,
    hiddenimports=dnd_hidden + ['hijridate'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Zoom Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
)
