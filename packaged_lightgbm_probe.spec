# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone AITS LightGBM packaged probe.

This is not the main AITS app spec. It intentionally uses the dedicated probe
runner and excludes app data, secrets, preferences, registry data, and UI assets.
"""

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules, copy_metadata


block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules("lightgbm")
hiddenimports += collect_submodules("scipy")
hiddenimports += collect_submodules("numpy")

datas = []
datas += copy_metadata("lightgbm")
datas += copy_metadata("scipy")

binaries = []
binaries += collect_dynamic_libs("lightgbm")

a = Analysis(
    ["tools/run_packaged_lightgbm_probe.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "app.ui",
        "app.services.order_adapter",
        "app.services.order_service",
        "app.services.execution_bridge",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AITSLightGBMProbe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AITSLightGBMProbe",
)
