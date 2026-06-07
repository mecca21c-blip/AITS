# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec draft for the AITS main application.

This is a draft for future main app packaging verification. It uses run.py as
the entrypoint, keeps console output enabled, and intentionally excludes user
runtime data such as secrets, journals, logs, prefs, and model registry data.
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


block_cipher = None
project_root = Path(SPECPATH).resolve()


def _safe_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def _safe_collect_data_files(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []


def _safe_collect_dynamic_libs(package_name):
    try:
        return collect_dynamic_libs(package_name)
    except Exception:
        return []


def _safe_copy_metadata(package_name):
    try:
        return copy_metadata(package_name)
    except Exception:
        return []


hiddenimports = []
hiddenimports += _safe_collect_submodules("app")
hiddenimports += _safe_collect_submodules("lightgbm")
hiddenimports += _safe_collect_submodules("scipy")
hiddenimports += _safe_collect_submodules("numpy")

# PySide6 is expected by the UI runtime, but the first packaged verification
# should confirm the installed package/plugin shape before optimizing this list.
hiddenimports += _safe_collect_submodules("PySide6")

datas = []
datas += _safe_collect_data_files("matplotlib")
datas += _safe_collect_data_files("mplfinance")
datas += _safe_copy_metadata("lightgbm")
datas += _safe_copy_metadata("scipy")

binaries = []
binaries += _safe_collect_dynamic_libs("lightgbm")
binaries += _safe_collect_dynamic_libs("scipy")
binaries += _safe_collect_dynamic_libs("numpy")


a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "tkinter",
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
    name="AITSMain",
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
    name="AITSMain",
)
