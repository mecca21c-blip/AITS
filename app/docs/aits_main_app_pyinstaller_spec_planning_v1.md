# AITS Main App PyInstaller Spec Planning v1

## 1. Document Purpose

This document defines the planning baseline for creating a future PyInstaller spec for the main AITS application.

It is the reference document for AI-ARCH-19-E2 or AI-ARCH-19-F main app packaged verification work. It reflects the successful AI-ARCH-19-D standalone LightGBM probe result and translates that result into a main app packaging strategy.

This Goal does not create a main app spec, run a main app PyInstaller build, execute a packaged main app, modify `run.py`, modify `app/ui/app_gui.py`, or connect Router/UI/Execution.

## 2. Current Packaging State Summary

Precheck state:

- Current commit before this Goal: `3856c14`
- Python executable: `C:\AITS\.venv\Scripts\python.exe`
- Python version: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- PyInstaller version: `6.20.0`
- LightGBM version: `4.6.0`
- scipy version: `1.17.1`
- `run.py`: exists
- `app/ui/app_gui.py`: exists
- existing probe spec: `packaged_lightgbm_probe.spec`
- probe build output: `dist/AITSLightGBMProbe/AITSLightGBMProbe.exe`
- probe build work directory: `build/packaged_lightgbm_probe`

requirements summary:

- `python-dotenv>=1.0.0`
- `mplfinance`
- `lightgbm==4.6.0`
- PySide6 is not directly listed in `requirements.txt`
- scipy is not directly pinned
- numpy/pandas/requests/pyupbit are not directly listed in `requirements.txt`

AI-ARCH-19-D packaged probe result:

- standalone probe onedir build succeeded
- packaged executable ran successfully
- `environment.frozen=True`
- packaged LightGBM import succeeded
- packaged LightGBM version: `4.6.0`
- packaged scipy import succeeded
- packaged scipy version: `1.17.1`
- packaged dependency gate passed
- packaged tiny real trainer smoke passed
- main app spec was not created
- main app build was not executed
- `run.py`, `app_gui.py`, Router, Execution, Order, and Risk Guard were not modified

Current remaining packaging gaps:

- no main app spec exists yet
- no main app build has been performed
- PySide6 + matplotlib/mplfinance + LightGBM/scipy packaging has not been verified together in the main app
- data/secrets/prefs/local_ai_registry inclusion and exclusion policy must be locked before main app build
- `dist/` and `build/` generated output git policy should be clarified in a separate cleanup/policy Goal if needed

## 3. Main App Entry Strategy

Expected main app entrypoint:

- `run.py`

Strategy:

- Use `run.py` as the entry script from the future main app spec.
- Do not modify `run.py` for the first main app spec draft.
- Do not use `app/ui/app_gui.py` directly as the PyInstaller entrypoint.
- Keep the standalone probe spec separate from the main app spec.
- Do not copy `packaged_lightgbm_probe.spec` directly into a main app spec; use it only as a reference for LightGBM/scipy handling.

Candidate main app spec names:

- `AITS.spec`
- `aits_app.spec`
- `AITSMain.spec`

Recommended:

- Use `aits_app.spec` or `AITS.spec`, choosing one naming style that fits the project convention.
- Keep the name clearly distinct from `packaged_lightgbm_probe.spec`.

## 4. Build Mode Strategy

Initial main app verification should use onedir.

Reasons:

- PySide6 DLLs and Qt platform plugins are easier to inspect.
- LightGBM/scipy/native DLLs are easier to inspect.
- matplotlib and mplfinance data files are easier to inspect.
- startup log and import failures are easier to diagnose.
- output contents can be compared across build attempts.

onefile should be considered later, after onedir is stable.

Console policy:

- First main app packaged verification should use `console=True` or an equivalent console-enabled mode.
- `windowed` / `noconsole` should be deferred until startup and dependency errors are understood.

## 5. Dependency Inclusion Strategy

### A. PySide6

PySide6 is part of the app runtime, but it is not directly listed in the current `requirements.txt` precheck. The future spec draft must verify how PySide6 is installed and collected in the current environment.

Potential needs:

- Qt platform plugins
- Qt image plugins
- Qt styles/plugins used by the UI
- possible PyInstaller hook or `collect_submodules` support

Risk:

- packaged execution can fail with Qt platform plugin errors if the plugin path is incomplete.

### B. matplotlib / mplfinance

`mplfinance` is directly listed in `requirements.txt`.

Potential needs:

- matplotlib data files
- backend configuration
- font/data collection
- mplfinance import verification in packaged mode

Risk:

- matplotlib backend/data issues may appear only in the packaged app.

### C. LightGBM / scipy / numpy

AI-ARCH-19-D proved that the standalone packaged probe can import and run:

- LightGBM `4.6.0`
- scipy `1.17.1`
- tiny LightGBM real trainer smoke

Main app implication:

- the main app spec may need the same or similar collection strategy
- package metadata should be included if version reporting is needed
- LightGBM dynamic library collection should be considered
- scipy/numpy broad collection can increase build time and output size

Any LightGBM/scipy DLL or hidden import failure in the main app should be split into a dedicated fix Goal.

### D. pandas / requests / pyupbit / exchange dependencies

These were not directly listed in the current `requirements.txt` precheck, but the application may import them through installed environment or source modules.

Future spec work must verify actual imports from the module graph and runtime smoke rather than assuming requirements coverage is complete.

Network/API keys are not packaging data and must not be embedded.

### E. app package

The main app package should include the Python modules required by runtime:

- `app/`
- UI modules required by `run.py`
- service modules required by startup
- `app/learning` only if imported or required by packaged diagnostics
- `app/storage` only if imported or required by runtime

`app/docs` should not be included unless a runtime feature explicitly requires it.

## 6. Data / Secret Inclusion Policy

Never include:

- `data/secrets.json`
- `data/secret.bin`
- API keys
- Upbit secrets
- OpenAI/Gemini keys
- account secrets
- raw private account details
- user journal database contents
- local model registry artifacts by default

Default exclusions:

- `data/local_ai_registry/`
- `data/aits_journal.sqlite3`
- runtime logs
- caches
- pycache
- archives

`prefs.json` policy:

- Decide carefully before inclusion.
- Prefer generating or loading user-specific prefs from an external writable path.
- Do not package secrets through prefs; prefs may contain only safe flags such as key-present indicators if already supported by the app.

Recommended packaged startup behavior:

- create/use a writable external data directory on first run
- keep secrets and user runtime data outside the executable bundle
- keep demo/sample data separate if needed

## 7. Runtime Path Policy

The main app spec must account for development vs packaged path differences.

Items to verify:

- `sys.frozen`
- `_MEIPASS`
- current working directory assumptions
- existing data path helpers
- log path behavior
- prefs path behavior
- secrets path behavior
- journal DB path behavior
- local AI registry path behavior

Runtime writable data should not live inside the packaged executable directory if that directory may be read-only or managed by an installer.

Recommended:

- use an explicit external writable application data path for prefs, secrets, logs, journals, and model registry artifacts
- document any path migration before changing code

## 8. Local AI / LightGBM Packaging Policy

Current status:

- LightGBM packaged probe: GO
- main app packaged LightGBM behavior: not yet verified

Policy:

- Local AI trainer must not run automatically at packaged startup.
- LightGBM import availability is not model approval.
- `active_model` must not be automatically set.
- `model_auto_approved` must remain false.
- `data/local_ai_registry` must not be bundled by default.
- model artifacts remain runtime/user data, not packaged default data.
- packaged dependency verification is diagnostic, not live trading approval.

## 9. Spec Creation Strategy For Next Goal

Future main app spec creation should:

- use `run.py` as the entry script
- use name `AITS` or `AITSMain`
- use onedir mode first
- use console enabled for first verification
- start with minimal hidden imports
- add hidden imports based on build/runtime failures
- reference the LightGBM probe spec strategy without copying it blindly
- consider PySide6 collection separately
- consider matplotlib data separately
- exclude secrets and runtime data
- output to `dist/AITS` or `dist/AITSMain`

Candidate spec policy:

- `.spec` is source and may be committed after review
- generated exe/dll/pyd/build outputs must not be committed
- main app spec creation must be its own Goal

## 10. Main App Packaged Smoke Test Plan

### A. Import Smoke

- run packaged exe
- inspect startup log
- verify main imports load
- verify LightGBM import availability if diagnostic path exists
- verify scipy import availability if diagnostic path exists

### B. UI Smoke

- main window loads
- major tabs load
- restore/default UI state does not crash
- AI settings panel can be reached if applicable

### C. Safety Smoke

- `submitted=0`
- no live submission
- no OrderAdapter bypass
- no Router/Risk Guard/Execution bypass
- no `active_model` auto-setting
- `model_auto_approved=False`

### D. Local AI Smoke

- dependency gate can run if exposed through a diagnostic path
- real trainer does not auto-run at startup
- tiny trainer smoke remains a separate diagnostic/probe operation

## 11. Build Output / Git Policy

- Do not commit `dist/`.
- Do not commit `build/`.
- Do not commit generated exe/dll/pyd/cache files.
- Commit reviewed `.spec` source files only.
- If `.gitignore` lacks `dist/` or `build/`, handle that in a separate Goal.
- This Goal does not modify `.gitignore`.

## 12. Packaging Risk / Fix Separation Criteria

Split issues into dedicated Goals:

- PySide6 plugin failure -> PySide6 plugin packaging fix
- matplotlib data/backend failure -> matplotlib data packaging fix
- LightGBM/scipy DLL failure -> LightGBM/scipy native dependency fix
- missing import failure -> hidden import fix
- runtime writable path failure -> packaged path policy fix
- live/order-related logs during packaged startup -> immediate STOP and safety audit

Do not bundle unrelated fixes into the first main app spec draft.

## 13. Decision Gate

GO:

- main app spec creation plan is clear
- entrypoint policy is clear
- inclusion/exclusion policy is clear
- data/secrets exclusion policy is clear
- onedir/console-first strategy is clear
- next Goal can create a main app spec without changing runtime code

WAIT:

- entrypoint becomes unclear
- data path policy is unclear
- PySide6 plugin strategy is not understood
- runtime writable path policy is unresolved

FAIL:

- a plan proposes bundling secrets/user data
- a plan requires `run.py` or `app_gui.py` changes without a specific Goal
- a plan changes Router/UI/Execution behavior
- a plan connects live trading
- a plan commits generated `dist/` or `build/` output

## 14. Future Goal Map

Recommended sequence:

- AI-ARCH-19-E2 Main App Spec Draft
- AI-ARCH-19-F Main App Packaged Dependency Verification
- AI-ARCH-19-G Packaged Runtime Path Verification
- AI-ARCH-19-H Packaged UI Smoke Verification
- AI-ARCH-20 Local AI Shadow Training Loop Preview

## 15. Safety

- No live trading connection.
- No Router change.
- No UI runtime change.
- No Execution change.
- No Order change.
- No Risk Guard bypass.
- No `active_model` auto-setting.
- No `model_auto_approved`.
- `submitted=0` principle remains in force.
- Packaging verification is not deployment approval and not live approval.

