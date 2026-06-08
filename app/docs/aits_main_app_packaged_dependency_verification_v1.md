# AITS Main App Packaged Dependency Verification v1

## 1. Goal

AI-ARCH-19-F attempted to build the AITS main app with `aits_app.spec` and verify packaged dependency/safety smoke behavior.

This Goal was verification only. It did not modify `aits_app.spec`, `run.py`, `app/ui/app_gui.py`, Router, Execution, Order, Risk Guard, requirements, app learning code, or app storage code.

## 2. Precheck State

- Starting commit: `bc66328`
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- Python version: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- PyInstaller version: `6.20.0`
- LightGBM version: `4.6.0`
- scipy version: `1.17.1`
- Spec file: `aits_app.spec`
- Existing packaged probe dist: `dist/AITSLightGBMProbe`
- Existing packaged probe build: `build/packaged_lightgbm_probe`
- Existing main app dist before build: none
- Existing main app build before build: none
- Existing unrelated dirty/pycache state remained outside this Goal and was not touched.

## 3. Build Information

Build command:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm aits_app.spec
```

Build result: failed by timeout.

Attempts:

- Attempt 1: timed out after approximately 15 minutes.
- Attempt 2: timed out after approximately 30 minutes.

The second attempt reached dynamic library analysis after broad PySide6, matplotlib, pandas, scipy, numpy, LightGBM, and app hidden import collection, but did not complete before timeout.

No `dist/AITSMain/AITSMain.exe` was created.

Partial build output:

- `build/aits_app/base_library.zip`
- `build/aits_app/qt.conf`

No `build/aits_app/warn-aits_app.txt` was produced before timeout.

Build warning/log summary observed before timeout:

- optional scipy torch compatibility collection warning: missing `torch`
- optional numpy f2py tests warning: missing `pytest`
- PySide6 deploy helper warning: missing `project_lib`
- optional `pycparser.lextab` / `pycparser.yacctab` hidden import warnings
- optional `scipy.special._cdflib` hidden import warning
- LightGBM hook warning that sklearn dynamic library collection was skipped because sklearn is not installed
- Google generative AI deprecation warning from imported package metadata/runtime import
- extensive PySide6 module collection occurred, including QtWebEngine-related modules
- extensive scipy/numpy test and submodule collection occurred

The timeout appears driven by the draft spec's broad `collect_submodules("PySide6")`, `collect_submodules("scipy")`, `collect_submodules("numpy")`, and `collect_submodules("app")` strategy.

## 4. Dist Included File Check

Main app dist was not created:

- `dist/AITSMain`: missing
- `dist/AITSMain/AITSMain.exe`: missing

Therefore full dist inclusion checks could not be completed.

Known existing dist output:

- `dist/AITSLightGBMProbe` from AI-ARCH-19-D remains a probe artifact and was not committed in this Goal.

Secrets/runtime data check:

- No main app dist exists, so no main app packaged runtime data was included.
- `requirements.txt`, `aits_app.spec`, and app code were not changed.

## 5. Packaged Exe Smoke Result

Packaged exe smoke could not be run.

Reason:

- `dist/AITSMain/AITSMain.exe` was not created.

Not performed:

- packaged exe startup
- UI display check
- console traceback check
- packaged dependency runtime check
- packaged runtime path check
- packaged safety smoke

## 6. Dependency Result

Development venv dependency status before build:

- LightGBM import: OK, `4.6.0`
- scipy import: OK, `1.17.1`

Packaged main app dependency status:

- LightGBM packaged main app import: not verified
- scipy packaged main app import: not verified
- PySide6 packaged main app plugin behavior: not verified
- matplotlib/mplfinance packaged main app behavior: not verified
- missing import behavior: not verified

Reason:

- build did not complete and no main app exe was created.

## 7. Runtime Path Result

Runtime path smoke could not be performed.

Not verified:

- data path behavior
- prefs/secrets path behavior
- writable path behavior
- journal path behavior
- local AI registry path behavior

Reason:

- no packaged main app exe was available to run.

## 8. Safety Result

Code safety:

- `run.py`: unchanged
- `app/ui/app_gui.py`: unchanged
- `app/services/decision_router.py`: unchanged
- `app/services/aits_orchestrator.py`: unchanged
- `app/services/execution_bridge.py`: unchanged
- `app/services/order_adapter.py`: unchanged
- `app/services/order_service.py`: unchanged
- `requirements.txt`: unchanged
- `aits_app.spec`: unchanged during this Goal

Runtime safety:

- live trading was not executed
- packaged main app was not executed
- no submitted order occurred
- no `active_model` was set
- no `model_auto_approved` was enabled
- no Local AI trainer auto-run was observed

The runtime safety smoke itself remains unverified because the packaged exe was not created.

## 9. Decision

Decision: FAIL for AI-ARCH-19-F main app packaged verification.

Failure reason:

- PyInstaller main app build did not complete within the extended 30 minute verification window.
- `dist/AITSMain/AITSMain.exe` was not created.
- packaged exe smoke could not be run.

This is a packaging-build failure, not an app runtime safety failure.

GO criteria not met:

- build did not complete
- exe was not created
- UI smoke was not possible
- dependency smoke was not possible

WAIT criteria not selected:

- the build did not produce an exe for partial smoke validation

FAIL criteria met:

- build failed by timeout
- exe creation failed

Forbidden-change checks passed:

- no requirements change
- no spec change
- no app code change
- no Router/UI/Execution change

## 10. Packaging Risk / Next Fix Goal

Recommended next Goal:

- AI-ARCH-19-F-FIX0 Main App Spec Collection Slimming

Recommended fix direction:

- replace broad `collect_submodules("PySide6")` with a narrower set based on actual app imports
- avoid collecting PySide6 scripts/deploy helpers
- avoid broad scipy/numpy test module collection
- avoid broad `collect_submodules("app")` if the module graph from `run.py` is sufficient
- keep LightGBM/scipy dynamic library handling informed by the successful probe spec
- preserve data/secret exclusion policy
- keep onedir/console-first verification mode

Possible later fix Goals:

- AI-ARCH-19-F-FIX1 PySide6 Plugin Packaging Fix
- AI-ARCH-19-F-FIX2 Matplotlib Data Packaging Fix
- AI-ARCH-19-F-FIX3 LightGBM SciPy DLL Packaging Fix
- AI-ARCH-19-G Packaged Runtime Path Verification/Fix
- AI-ARCH-19-H Packaging Size Optimization

## 11. Safety

- Router/UI/Execution code was not changed.
- No live trading was connected.
- No order path was modified.
- No `active_model` auto-setting was introduced.
- No `model_auto_approved` was introduced.
- `submitted=0` principle remains in force.
- This Goal was packaging verification only and does not imply live approval.

## 12. Git Diff / Commit Policy

Committed file:

- `app/docs/aits_main_app_packaged_dependency_verification_v1.md`

Not committed:

- `build/`
- `dist/`
- partial build artifacts
- probe build artifacts

Diff checks:

- `git diff -- requirements.txt`: no diff
- `git diff -- aits_app.spec`: no diff
- forbidden app/service file diffs: no diff

