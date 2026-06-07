# AITS Packaged LightGBM Probe Build v1

## 1. Goal

AI-ARCH-19-D verifies LightGBM packaged dependency behavior through a standalone PyInstaller probe executable.

This is not main app packaging. It does not modify `run.py`, `app_gui.py`, Router, Execution, Order, Risk Guard, requirements, or the main app runtime.

## 2. Precheck State

- Starting commit: `cb1822a`
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- Python version: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- PyInstaller version: `6.20.0`
- LightGBM version in venv: `4.6.0`
- scipy version in venv: `1.17.1`
- requirements state:
  - `lightgbm==4.6.0` present
  - no direct scipy pin
  - no PyInstaller pin
  - no requirements diff
- Existing project `.spec` files before this Goal: none outside `.venv`
- Existing `dist/` before this Goal: missing
- Existing `build/` before this Goal: missing
- Existing unrelated dirty/pycache state was present and not touched.

## 3. Created Files

- `tools/run_packaged_lightgbm_probe.py`
- `packaged_lightgbm_probe.spec`

This result document:

- `app/docs/aits_packaged_lightgbm_probe_build_v1.md`

## 4. Build Settings

- Spec file: `packaged_lightgbm_probe.spec`
- Entry script: `tools/run_packaged_lightgbm_probe.py`
- Output name: `AITSLightGBMProbe`
- Build mode: onedir
- Console mode: enabled
- Main app spec: not created
- Main app build: not executed
- UI assets: not included intentionally
- app data/secrets/prefs: not included intentionally
- local AI registry data: not included intentionally

Hidden imports and package collection:

- `lightgbm` submodules collected
- `scipy` submodules collected
- `numpy` submodules collected
- LightGBM dynamic libraries collected
- LightGBM/scipy package metadata copied so packaged report can show version values

## 5. Build Command

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm packaged_lightgbm_probe.spec
```

The first build succeeded but the packaged report showed LightGBM version as `null` and dependency gate version as `unknown`. The runner/spec were then adjusted to include package metadata and fill report versions from `importlib.metadata`; the probe was rebuilt.

## 6. Build Result

Final build result: success.

Executable path:

```text
C:\AITS\dist\AITSLightGBMProbe\AITSLightGBMProbe.exe
```

Build output:

- `dist/AITSLightGBMProbe/` created
- `build/packaged_lightgbm_probe/` created
- exe created successfully

Build warning summary:

- Optional `torch` collection warning from scipy array API compatibility.
- Optional `pytest` collection warning from numpy f2py tests.
- Optional `pycparser.lextab` / `pycparser.yacctab` hidden import warnings.
- Optional `scipy.special._cdflib` hidden import warning.
- `sklearn` dynamic library collection skipped because sklearn is not installed.

These warnings did not prevent packaged probe execution, LightGBM/scipy import, dependency gate, or tiny trainer smoke from passing.

## 7. Packaged Probe Execution Result

Execution command:

```powershell
.\dist\AITSLightGBMProbe\AITSLightGBMProbe.exe
```

Packaged stdout JSON summary:

- schema: `aits_packaged_lightgbm_probe.v1`
- executable: `C:\AITS\dist\AITSLightGBMProbe\AITSLightGBMProbe.exe`
- frozen: `True`
- platform: `Windows-10-10.0.19045-SP0`
- LightGBM import: OK
- LightGBM version: `4.6.0`
- scipy import: OK
- scipy version: `1.17.1`
- dependency gate: OK
- dependency gate importable: `True`
- dependency gate version: `4.6.0`
- real trainer smoke: OK
- train status: `success`
- model file created: `True`
- prediction executed: `True`
- router connected: `False`
- execution connected: `False`
- UI connected: `False`
- model auto approved: `False`
- training scope: `tiny_probe_only`

## 8. Packaging Risk Assessment

Current result:

- LightGBM packaged import works.
- scipy packaged import works.
- dependency gate works in packaged mode.
- tiny real trainer smoke works in packaged mode.
- No native DLL failure observed in the probe executable.
- No Router/UI/Execution dependency was required by the probe.

Remaining risks:

- The probe spec is intentionally separate from the main app spec.
- Main app packaging may still need a different hidden import/data/DLL strategy.
- The broad scipy/numpy submodule collection increased build time and likely output size.
- Future probe spec optimization may reduce unnecessary test-module collection.

Spec modification needed before main app packaging:

- Not for this probe PASS.
- Main app spec planning remains a separate Goal.

## 9. Decision

Decision: GO for AI-ARCH-19-E Main App PyInstaller Spec Planning.

GO criteria met:

- packaged probe exe build succeeded
- packaged exe was created
- packaged exe executed successfully
- JSON report printed to stdout
- `frozen=True`
- LightGBM import OK
- LightGBM version `4.6.0`
- scipy import OK
- dependency gate OK
- tiny trainer smoke OK
- safety flags remained false
- main app files were not modified

WAIT conditions not triggered:

- trainer smoke did not fail or skip
- stdout JSON was parseable
- dependency gate did not fail

FAIL conditions not triggered:

- no build failure
- no exe execution failure
- no LightGBM/scipy native DLL failure observed
- no app GUI/PySide6 requirement in probe runtime
- no Router/UI/Execution changes

## 10. Safety

- This was not main app packaging.
- Router/UI/Execution were not connected.
- No live trading path was touched.
- No automatic training scheduler was created.
- No `active_model` was set.
- No model status was promoted.
- `model_auto_approved=False`.
- `submitted=0` principle remains in force.
- Training scope was tiny probe only.

## 11. Next Recommended Goal

Recommended next Goal:

- AI-ARCH-19-E Main App PyInstaller Spec Planning

Possible later Goals:

- AI-ARCH-19-F Main App Packaged Dependency Verification
- AI-ARCH-19-D-OPT Probe Spec Size / Hidden Import Optimization
- AI-ARCH-20 Local AI Shadow Training Loop Preview

