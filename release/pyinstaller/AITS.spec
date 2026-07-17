# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

project_root = Path(SPECPATH).resolve().parents[1]

def safe(call, name):
    try:
        return call(name)
    except Exception:
        return []

hiddenimports = [
    "app", "app.ui.app_gui", "app.ui.main_window", "app.services.aits_orchestrator",
    "app.services.aits_path_resolver", "app.services.aits_release_operations",
    "app.services.aits_data_governance", "app.utils.prefs",
    "numpy", "scipy", "pandas", "lightgbm", "matplotlib", "mplfinance",
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "cryptography", "pydantic",
]
datas = []
for package in ("matplotlib", "mplfinance", "certifi"):
    datas += safe(collect_data_files, package)
for package in ("lightgbm", "scipy"):
    datas += safe(copy_metadata, package)
datas += [
    (str(project_root / "assets/ui/header_toggle_on.png"), "assets/ui"),
    (str(project_root / "assets/ui/header_toggle_off.png"), "assets/ui"),
    (str(project_root / "release/assets/release_model_bundle.json"), "release/assets"),
    (str(project_root / "release/manifests/dependency_manifest.json"), "release/manifests"),
    (str(project_root / "release/manifests/THIRD_PARTY_LICENSES.txt"), "release/manifests"),
]
binaries = []
for package in ("lightgbm", "scipy", "numpy"):
    binaries += safe(collect_dynamic_libs, package)

a = Analysis(
    [str(project_root / "run.py")], pathex=[str(project_root)], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["IPython", "jupyter", "notebook", "pytest", "tkinter", "torch", "tensorflow", "ollama"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="AITS", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    disable_windowed_traceback=False, target_arch="x86_64",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AITS")
