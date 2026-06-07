# AITS PyInstaller Controlled Install / Verify v1

## 1. Goal

AI-ARCH-19-C installs PyInstaller into the current AITS development venv in a controlled way and verifies that the existing Local AI dependency probe still works.

This Goal does not modify requirements, create or edit PyInstaller spec files, run a PyInstaller build, run a packaged exe, or connect anything to Router, UI, Execution, Order, Risk Guard, or runtime loops.

## 2. Pre-Install State

- Starting commit: `10b5ea1`
- Git status summary: existing unrelated dirty state was present before this Goal, including unrelated pycache changes, `AITS_MASTER_STATUS.md` deletion state, and untracked docs/archive files. These were not touched.
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- Python version: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- pip version: `pip 26.1.1 from C:\AITS\.venv\Lib\site-packages\pip (python 3.14)`
- PyInstaller pre-install state: not installed (`Package(s) not found: pyinstaller`)
- requirements diff before install: none
- requirements dependency lines:
  - `lightgbm==4.6.0`
  - no `pyinstaller` pin
  - no direct `scipy` pin
- LightGBM/scipy pre-install import:
  - `lightgbm 4.6.0`
  - `scipy 1.17.1`
- Project `.spec` files outside `.venv`: none
- `dist/`: missing
- `build/`: missing

## 3. Install Command

The install was executed with the current AITS venv Python:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

No global Python install was used.

## 4. Install Result

Result: success.

Installed package:

- `pyinstaller 6.20.0`

Installed supporting packages in the venv:

- `altgraph 0.17.5`
- `pefile 2024.8.26`
- `pyinstaller-hooks-contrib 2026.5`
- `pywin32-ctypes 0.2.3`
- `setuptools 82.0.1`

pip emitted cache deserialization warnings and a pip update notice, but the PyInstaller installation completed successfully.

`pip show pyinstaller` summary:

- Name: `pyinstaller`
- Version: `6.20.0`
- Location: `C:\AITS\.venv\Lib\site-packages`
- Requires: `altgraph`, `packaging`, `pefile`, `pyinstaller-hooks-contrib`, `pywin32-ctypes`, `setuptools`

## 5. Post-Install Verification Result

PyInstaller version:

```text
6.20.0
```

PyInstaller import:

```text
6.20.0
```

LightGBM/scipy import after install:

```text
lightgbm 4.6.0
scipy 1.17.1
```

`packaged_lightgbm_probe.py` compile:

- passed

venv packaged probe execution:

- schema: `aits_packaged_lightgbm_probe.v1`
- frozen: `False`
- LightGBM import: OK, version `4.6.0`
- scipy import: OK, version `1.17.1`
- dependency gate: OK, importable `True`, version `4.6.0`
- tiny real trainer smoke: OK
- train status: `success`
- model file created: `True`
- prediction executed: `True`
- router connected: `False`
- execution connected: `False`
- UI connected: `False`
- model auto approved: `False`

## 6. requirements State

- `requirements.txt` was not modified.
- `pyinstaller` was not pinned in requirements.
- `lightgbm==4.6.0` remains present.
- `scipy` remains a transitive dependency and is not directly pinned.
- Final `git diff -- requirements.txt`: no diff.

## 7. spec/build State

- No PyInstaller spec file was created or modified.
- No PyInstaller build was executed.
- No packaged exe was executed.
- `dist/` remains missing.
- `build/` remains missing.

## 8. Decision

Decision: GO for AI-ARCH-19-D Packaged LightGBM Probe Build.

GO criteria met:

- PyInstaller installation succeeded.
- PyInstaller version/import confirmed: `6.20.0`.
- LightGBM/scipy imports remained healthy.
- venv packaged probe execution passed.
- requirements were not modified.
- no spec file was created or modified.
- no build was executed.
- Router/UI/Execution were not connected.

WAIT conditions not triggered:

- PyInstaller version was confirmed.
- probe did not fail.
- build strategy remains intentionally deferred to AI-ARCH-19-D.

FAIL conditions not triggered:

- no install failure
- no Python execution failure
- no LightGBM/scipy import breakage
- no requirements pollution
- no spec/build creation
- no Router/UI/Execution change

## 9. Next Recommended Goal

Next recommended Goal:

- AI-ARCH-19-D Packaged LightGBM Probe Build
  - create a separate probe runner/spec
  - use onedir first
  - run packaged probe
  - verify LightGBM/scipy packaged import
  - verify dependency gate
  - run tiny trainer smoke if feasible

Later Goals:

- AI-ARCH-19-E Main App PyInstaller Spec Planning
- AI-ARCH-19-F Main App Packaged Dependency Verification

## 10. Safety

- No Router connection.
- No UI connection.
- No Execution connection.
- No Order connection.
- No Risk Guard bypass.
- No live trading impact.
- No automatic training scheduler.
- No `active_model` auto-selection.
- No model status promotion.
- No `model_auto_approved`.
- `submitted=0` principle remains in force.
- This Goal verifies a packaging tool install only; it is not deployment approval.

