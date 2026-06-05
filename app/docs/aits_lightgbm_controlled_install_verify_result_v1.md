# AITS Controlled LightGBM Install / Verify Result v1

## 1. Goal

AI-ARCH-15 validates a controlled LightGBM installation in the current AITS development virtual environment.

This result records the install command, package version, dependency gate result, and existing learning pipeline smoke tests.

This Goal does not modify requirements, run real training, create model binaries, or connect LightGBM to Router, UI, Runtime, Order, Execution, or Risk Guard.

## 2. Pre-Install State

- Working directory: `C:\AITS`
- Current commit before install: `763cc21`
- Python: `Python 3.14.4`
- pip: `pip 26.1.1 from C:\AITS\.venv\Lib\site-packages\pip (python 3.14)`
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- LightGBM before install: not installed (`Package(s) not found: lightgbm`)
- `requirements.txt` diff before install: clean
- Git status before install contained unrelated dirty/untracked files and generated cache files. They were not part of this Goal and were not committed.

## 3. Install Command

Executed with the AITS project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install lightgbm
```

## 4. Install Result

Status: success

Installed packages:

- `lightgbm 4.6.0`
- `scipy 1.17.1`

Existing dependency:

- `numpy 2.4.4`

`pip show lightgbm` summary:

- Name: `lightgbm`
- Version: `4.6.0`
- Location: `C:\AITS\.venv\Lib\site-packages`
- Requires: `numpy`, `scipy`

Import/version check:

```text
4.6.0
```

## 5. Dependency Gate Re-Verification

Dependency gate smoke result after install:

- schema: `aits_lightgbm_dependency_gate.v1`
- package: `lightgbm`
- importable: `True`
- version: `4.6.0`
- real_trainer_prototype_allowed: `True`
- training_executed: `False`
- requirements_modified: `False`
- JSON report export: success

## 6. Smoke Test Results

Dependency gate:

- `app/learning/lightgbm_dependency_gate.py` py_compile: pass
- dependency gate report generation/export: pass

Trainer Skeleton:

- schema: `aits_lightgbm_trainer_run_summary.v1`
- mode: `dry_run`
- total_rows: `1`
- training_usable_rows: `1`
- artifact_created: `False`
- model_status: `draft`
- router_connected: `False`
- execution_connected: `False`
- JSON export: success

Dataset Builder:

- `app/learning/lightgbm_dataset_builder.py` py_compile: pass

Model Registry Persistence:

- saved_files: `4`
- loaded_entry: `True`
- models: `1`
- active_model_id: created preview model id
- snapshot_exists: `True`
- active pointer mode: `preview`

## 7. Requirements Status

`requirements.txt` was not modified in this Goal.

No dependency pin was committed. Version pinning remains a separate decision for a controlled follow-up Goal.

## 8. Packaging / PyInstaller Status

Packaged executable validation was not performed in this Goal.

Known remaining packaging risks:

- LightGBM uses native wheel/binary components.
- Windows wheel compatibility must be reviewed before release packaging.
- PyInstaller hidden import and DLL inclusion must be validated separately.
- Packaged import verification is deferred to AI-ARCH-19.

## 9. Decision

Decision: GO for AI-ARCH-16 LightGBM Real Trainer Prototype planning.

Reason:

- Controlled venv install succeeded.
- LightGBM import/version check passed.
- Dependency gate now reports `importable=True`.
- Existing trainer skeleton and registry persistence smokes passed.
- `requirements.txt` remained unchanged.
- Router/UI/Execution remained disconnected.

Distribution packaging remains WAIT until AI-ARCH-19 packaged build verification.

## 10. Safety

- Real LightGBM training executed: no
- Model binary created: no
- Router connected: no
- UI connected: no
- Runtime loop connected: no
- Order/Execution connected: no
- Risk Guard bypass: no
- Live trading impact: none
- `submitted=0` principle: maintained

## 11. Next Recommended Goal

Recommended next options:

- AI-ARCH-15-B requirements pin decision
- AI-ARCH-16 LightGBM Real Trainer Prototype
- AI-ARCH-19 Packaged Build Dependency Verification before user distribution
