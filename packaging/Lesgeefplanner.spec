# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-spec voor Lesgeefplanner. Zie docs/ONTWIKKELAAR.md voor hoe je dit bouwt.

Gegenereerd door en geverifieerd met:
    uv run pyinstaller --noconfirm --clean --name Lesgeefplanner --onefile --windowed \
        --collect-all nicegui --collect-all ortools \
        --distpath packaging/dist --workpath packaging/build --specpath packaging \
        packaging/bootstrap.py
Dat commando bouwt dit bestand opnieuw; als de dependencies wijzigen, regenereer het zo
in plaats van dit bestand met de hand aan te passen."""
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('nicegui')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ortools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['bootstrap.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='Lesgeefplanner',
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
)
