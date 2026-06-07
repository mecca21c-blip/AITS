# AITS Main App PyInstaller Spec Draft v1

## 1. Goal

AI-ARCH-19-E2 creates a draft PyInstaller spec for the AITS main application.

This Goal creates a spec draft and documents its inclusion/exclusion policy only. It does not run a PyInstaller build, execute a packaged exe, modify `run.py`, modify `app/ui/app_gui.py`, or connect Router/UI/Execution.

## 2. Created Spec

- Spec file: `aits_app.spec`
- Entry script: `run.py`
- App name: `AITSMain`
- Build mode: onedir via `COLLECT`
- Console: `True`
- Debug: `False`
- Main app build executed: no
- Packaged exe executed: no

The probe spec remains separate:

- `packaged_lightgbm_probe.spec` is the standalone LightGBM probe spec.
- `aits_app.spec` is the main app draft spec.
- The probe spec is a reference, not the main app spec.

## 3. Precheck Result

- Starting commit: `40ea95d`
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- Python version: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- PyInstaller version: `6.20.0`
- LightGBM version: `4.6.0`
- scipy version: `1.17.1`
- `run.py`: exists
- `app/ui/app_gui.py`: exists
- existing spec: `packaged_lightgbm_probe.spec`
- existing probe dist: `dist/AITSLightGBMProbe/AITSLightGBMProbe.exe`
- existing probe build directory: `build/packaged_lightgbm_probe`
- requirements direct dependency search:
  - `mplfinance`
  - `lightgbm==4.6.0`

PySide6, scipy, numpy, pandas, requests, and pyupbit were not direct requirement lines in the precheck search. Their actual packaged inclusion must be verified through the module graph and runtime smoke in the next packaging Goal.

## 4. Inclusion Strategy

### app package

The draft spec uses:

- `collect_submodules("app")`

This favors first-build stability over output size. Optimization can be split into a later packaging-size Goal.

### PySide6

The draft spec uses:

- `collect_submodules("PySide6")`

The first main app build must verify Qt platform plugins, UI startup, and any PySide6 plugin/data requirements. PySide6 plugin fixes should be handled in a dedicated follow-up Goal if needed.

### matplotlib / mplfinance

The draft spec uses:

- `collect_data_files("matplotlib")`
- `collect_data_files("mplfinance")`

The first main app packaged smoke must verify chart rendering and backend/data behavior. matplotlib backend failures should be handled separately.

### LightGBM / scipy / numpy

The draft spec follows the successful AI-ARCH-19-D probe direction:

- `collect_submodules("lightgbm")`
- `collect_submodules("scipy")`
- `collect_submodules("numpy")`
- `collect_dynamic_libs("lightgbm")`
- `collect_dynamic_libs("scipy")`
- `collect_dynamic_libs("numpy")`
- package metadata for LightGBM/scipy

This is intentionally conservative. The known tradeoff is build time and output size.

### pandas / requests / pyupbit

These packages are not explicitly collected in the draft because they were not direct requirement lines in the precheck search. If the main app module graph or runtime smoke requires them, hidden import or dependency policy should be added in a separate fix Goal.

## 5. Exclusion / Secret Policy

The draft spec does not add project runtime data to `datas`.

Explicit policy:

- exclude `data/secrets.json`
- exclude `data/secret.bin`
- exclude `prefs.json`
- exclude journal DB files such as `data/aits_journal.sqlite3`
- exclude `data/local_ai_registry`
- exclude logs
- exclude archive directories
- exclude `build/`
- exclude `dist/`
- exclude `.git`
- exclude `__pycache__`

Runtime data must live in an external writable path. It must not be bundled as default packaged data.

## 6. Build Mode

- Initial mode: onedir
- Console: `True`
- onefile: deferred
- windowed/noconsole: deferred

onedir and console output are preferred for the first main app verification because PySide6, matplotlib, LightGBM, scipy, and runtime path issues need visible diagnostics.

## 7. Why No Build In This Goal

This Goal is spec draft only.

Build/run verification is intentionally deferred to AI-ARCH-19-F so failures can be logged and classified without mixing spec creation with runtime fixes.

If the first build fails, each failure class should be split:

- PySide6 plugin issue
- matplotlib data/backend issue
- LightGBM/scipy DLL issue
- hidden import issue
- runtime writable path issue

## 8. Expected Next Verification

AI-ARCH-19-F should verify:

- PyInstaller build using `aits_app.spec`
- `dist/AITSMain` creation
- packaged exe startup
- UI start
- LightGBM/scipy import availability if diagnostic path exists
- dependency gate availability if diagnostic path exists
- `submitted=0`
- no live order submission
- no Router/Risk Guard/Execution bypass
- no bundled secrets or runtime user data

## 9. Known Risks

- PySide6 platform plugin failure
- missing Qt plugin/data files
- matplotlib data/backend failure
- mplfinance runtime charting issue
- LightGBM/scipy/native DLL issue
- broad scipy/numpy collection increasing build size
- runtime writable path mismatch
- missing hidden import from app runtime modules
- packaged startup accidentally touching live/order paths, which must trigger STOP and safety audit

## 10. Safety

- `run.py` was not modified.
- `app/ui/app_gui.py` was not modified.
- Router/UI/Execution were not connected.
- Order and Risk Guard paths were not modified.
- `active_model` was not set.
- `model_auto_approved` was not enabled.
- live trading was not connected.
- `submitted=0` principle remains in force.
- No build was executed.
- No packaged exe was executed.

## 11. Decision

GO:

- spec draft created
- entry is `run.py`
- app name is `AITSMain`
- onedir/console-first policy is reflected
- data/secret exclusion policy is reflected
- no build executed
- no forbidden files changed

WAIT:

- UI asset inclusion remains to be verified
- PySide6 plugin behavior remains to be verified
- runtime writable path behavior remains to be verified

FAIL conditions avoided:

- no secrets included
- no runtime data included
- no `run.py` or `app_gui.py` modification
- no build execution
- no Router/UI/Execution change

