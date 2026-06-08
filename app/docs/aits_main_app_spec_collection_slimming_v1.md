# AITS Main App Spec Collection Slimming v1

## 1. Goal

AI-ARCH-19-F-FIX0 reduces the broad PyInstaller collection strategy in `aits_app.spec` to resolve the main app build timeout observed in AI-ARCH-19-F.

This Goal modifies only the main app spec and records build verification results. It does not modify app runtime code, `run.py`, `app/ui/app_gui.py`, Router, Execution, Order, Risk Guard, requirements, app learning code, or app storage code.

## 2. AI-ARCH-19-F Failure Summary

AI-ARCH-19-F failed because the main app PyInstaller build timed out:

- attempt 1: timeout after approximately 15 minutes
- attempt 2: timeout after approximately 30 minutes
- `dist/AITSMain/AITSMain.exe`: not created
- packaged exe smoke: not possible

Primary broad collection candidates:

- `collect_submodules("app")`
- `collect_submodules("PySide6")`
- `collect_submodules("scipy")`
- `collect_submodules("numpy")`

The prior logs showed excessive PySide6 module collection, including QtWebEngine-related modules, and broad scipy/numpy test/submodule traversal.

## 3. Pre-Fix Problem Candidates

The previous spec attempted to collect entire package submodule trees:

- all `app` submodules
- all PySide6 submodules
- all scipy submodules
- all numpy submodules

This improved first-draft coverage but caused build analysis to take too long and pull in modules that are not needed for the first main app packaging check.

## 4. Spec Change Summary

Changed file:

- `aits_app.spec`

Removed broad collection:

- removed `collect_submodules("app")`
- removed `collect_submodules("PySide6")`
- removed `collect_submodules("scipy")`
- removed `collect_submodules("numpy")`
- removed the unused `_safe_collect_submodules()` helper and `collect_submodules` import

Explicit hidden imports kept or added:

- `app`
- `app.core.aits_state`
- `app.services.aits_orchestrator`
- `app.ui.app_gui`
- `app.ui.auth_dialogs`
- `app.ui.tabs.config_tabs`
- `app.ui.tabs.portfolio_tab`
- `app.ui.tabs.trades_tab`
- `app.ui.tabs.watchlist_tab`
- `app.utils.prefs`
- `lightgbm`
- `numpy`
- `scipy`
- `PySide6.QtCore`
- `PySide6.QtGui`
- `PySide6.QtWidgets`

Collection retained:

- `collect_data_files("matplotlib")`
- `collect_data_files("mplfinance")`
- LightGBM metadata
- scipy metadata
- `collect_dynamic_libs("lightgbm")`
- `collect_dynamic_libs("scipy")`
- `collect_dynamic_libs("numpy")`

Secrets/runtime data policy remained unchanged:

- no explicit inclusion of `data/secrets.json`
- no explicit inclusion of `data/secret.bin`
- no explicit inclusion of `data/aits_journal.sqlite3`
- no explicit inclusion of `data/local_ai_registry`
- no explicit inclusion of `prefs.json`
- no explicit inclusion of logs, archive, build, dist, `.git`, or `__pycache__`

## 5. Build Reverification Result

Build command:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm aits_app.spec
```

Result: success.

Approximate elapsed time:

- about 17 minutes 15 seconds
- previous result was timeout at 15 minutes and 30 minutes

Executable:

- `dist/AITSMain/AITSMain.exe`

Build warnings observed:

- `collect_dynamic_libs` skipped sklearn because sklearn is not installed
- optional `pycparser.lextab` / `pycparser.yacctab` hidden imports were not found
- optional `scipy.special._cdflib` hidden import was not found
- optional platform-specific modules appeared in `warn-aits_app.txt`
- Google `google.generativeai` deprecation warning appeared during PyInstaller dependency analysis

No build-stopping error occurred.

## 6. Dist Check Result

Main app dist:

- `dist/AITSMain`: created
- `dist/AITSMain/AITSMain.exe`: created
- `AITSMain.exe` size observed: about 26 MB
- `_internal/`: created

LightGBM/scipy/numpy traces:

- `_internal/lightgbm`
- `_internal/lightgbm-4.6.0.dist-info`
- `_internal/lightgbm/bin/lib_lightgbm.dll`
- `_internal/scipy`
- `_internal/scipy-1.17.1.dist-info`
- `_internal/scipy.libs`
- `_internal/numpy`
- `_internal/numpy-2.4.4.dist-info`
- `_internal/numpy.libs`

PySide6/matplotlib traces:

- `_internal/PySide6`
- `_internal/PySide6/Qt6Core.dll`
- `_internal/PySide6/Qt6Gui.dll`
- `_internal/PySide6/Qt6Widgets.dll`
- `_internal/matplotlib`
- `_internal/matplotlib/mpl-data`

Secrets/runtime data scan:

- no `secrets.json` found
- no `secret.bin` found
- no `aits_journal.sqlite3` found
- no `local_ai_registry` found
- no `prefs.json` found

## 7. Decision

Decision: GO for AI-ARCH-19-F2 Main App Packaged Smoke Verification.

GO criteria met:

- build timeout was resolved
- `AITSMain.exe` was created
- LightGBM/scipy/numpy files are present in dist
- PySide6/matplotlib files are present in dist
- secrets/runtime data were not found in dist scan
- requirements were not modified
- app runtime code was not modified
- Router/UI/Execution code was not modified

WAIT criteria:

- packaged exe smoke has not been run in this Goal
- runtime path behavior remains unverified
- UI startup remains unverified

FAIL criteria not triggered:

- no build timeout after slimming
- no build-stage missing import failure
- no secret/runtime data inclusion observed
- no forbidden code changes

## 8. Next Goal

Recommended next Goal:

- AI-ARCH-19-F2 Main App Packaged Smoke Verification

That Goal should run:

- `dist/AITSMain/AITSMain.exe`
- startup/traceback check
- UI visibility check
- PySide6 platform plugin runtime check
- matplotlib/mplfinance runtime check
- LightGBM/scipy runtime import smoke if available
- runtime path check
- safety check for no live submission

Possible later Goals:

- AI-ARCH-19-F-FIX1 PySide6 Plugin Packaging Fix
- AI-ARCH-19-F-FIX2 Matplotlib Data Packaging Fix
- AI-ARCH-19-F-FIX3 LightGBM SciPy Packaging Fix
- AI-ARCH-19-F-FIX0B Incremental Import Spec Split

## 9. Safety

- `run.py` was not modified.
- `app/ui/app_gui.py` was not modified.
- Router/UI/Execution were not connected.
- Order and Risk Guard paths were not modified.
- requirements were not modified.
- live trading was not connected.
- no submitted order occurred.
- no automatic Local AI training scheduler was created.
- no `active_model` was set.
- no model status was promoted.
- build outputs in `build/` and `dist/` are not committed.

