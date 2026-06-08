# AITS Packaged UI Screenshot Verification v1

## 1. Goal

AI-ARCH-19-H verifies packaged `AITSMain.exe` readiness for visual UI screenshot confirmation after the packaged writable data path fix.

This Goal records:

- packaged exe startup behavior
- process survival
- console/stdout/stderr status
- UI launch logs
- packaged runtime path status
- dependency/runtime warnings
- safety scan result

This Goal does not capture or request a screenshot from Codex. Visual screenshot judgment remains outside this Codex verification step.

## 2. Pre-State

- Commit hash before verification: `bc9cbea`
- Executable path: `C:\AITS\dist\AITSMain\AITSMain.exe`
- Executable exists: yes
- Executable size: `26,111,493` bytes
- Executable timestamp: `2026-06-08 22:34:04`

Dist runtime data scan before execution:

- no `secret.bin`
- no `secrets.json`
- no `prefs.json`
- no `aits_journal.sqlite3`
- no `local_ai_registry`
- no `.log` file

LocalAppData runtime data before execution:

| File | Location | Size | LastWriteTime |
| --- | --- | ---: | --- |
| `secret.bin` | `C:\Users\mecca\AppData\Local\AITS\data\secret.bin` | `44` bytes | `2026-06-08 22:35:06` |
| `aits.log` | `C:\Users\mecca\AppData\Local\AITS\data\logs\aits.log` | `1,432` bytes | `2026-06-08 22:35:13` |

## 3. Execution Info

Command:

```powershell
.\dist\AITSMain\AITSMain.exe
```

Observation:

- observation duration: 60 seconds
- process stayed alive for the full observation window
- process was stopped after observation
- no process remained after stop check

Process result:

- process id: `23344`
- running after 60 seconds: `True`
- exit code: not available because the process was stopped after observation

## 4. UI Display Log Result

UI launch signals were observed in stdout and LocalAppData log.

Important stdout/log lines:

```text
[AITS][RuntimePathDiagnostic] run_mode=ui | cwd=C:\AITS | root_dir=C:\AITS\dist\AITSMain | data_dir=C:\Users\mecca\AppData\Local\AITS\data | prefs_path=C:\Users\mecca\AppData\Local\AITS\data\prefs.json
[AITS][StartupPerf] app_gui.window_show.start
[AITS][StartupPerf] app_gui.window_show.end elapsed_ms=94
UI launched via legacy-compatible entry
[AITS][Chart] render_mode | used=mplfinance | reason=ok
```

Additional UI/runtime startup signals:

- `MainWindow.__init__.end`
- `app_gui.main_window_create.end`
- detail panel refresh logs
- managed table debug logs
- chart render logs with `legacy` and `mplfinance`

Visual limitation:

- Codex did not visually inspect or screenshot the window.
- Main window visual correctness still requires external screenshot/visual confirmation.
- This document confirms the packaged app reached UI launch and rendering log milestones.

## 5. Runtime Path Result

Runtime diagnostic confirmed the AI-ARCH-19-G-FIX1 policy remains active:

```text
root_dir=C:\AITS\dist\AITSMain
data_dir=C:\Users\mecca\AppData\Local\AITS\data
prefs_path=C:\Users\mecca\AppData\Local\AITS\data\prefs.json
```

Dist runtime data after execution:

- no `secret.bin`
- no `secrets.json`
- no `prefs.json`
- no `aits_journal.sqlite3`
- no `local_ai_registry`
- no `.log` file

LocalAppData runtime data after execution:

| File | Location | Size | LastWriteTime |
| --- | --- | ---: | --- |
| `prefs.json` | `C:\Users\mecca\AppData\Local\AITS\data\prefs.json` | `3,786` bytes | `2026-06-08 23:13:29` |
| `secret.bin` | `C:\Users\mecca\AppData\Local\AITS\data\secret.bin` | `44` bytes | `2026-06-08 22:35:06` |
| `secrets.json` | `C:\Users\mecca\AppData\Local\AITS\data\secrets.json` | `70` bytes | `2026-06-08 23:13:29` |
| `aits.log` | `C:\Users\mecca\AppData\Local\AITS\data\logs\aits.log` | `5,364` bytes | `2026-06-08 23:13:31` |

Interpretation:

- Packaged runtime data no longer writes into `dist/AITSMain/data`.
- Writable runtime data is under `%LOCALAPPDATA%\AITS\data`.
- `prefs.json` and `secrets.json` were created in LocalAppData during packaged startup. No API key entry or connection test was performed.

## 6. Dependency Result

No critical dependency failure was observed.

- PySide6 platform plugin error: not observed
- matplotlib fatal error: not observed
- mplfinance fatal error: not observed
- LightGBM fatal error: not observed
- scipy fatal error: not observed
- numpy fatal error: not observed
- missing import error: not observed
- DLL/native dependency error: not observed

Non-critical stderr/runtime warnings observed:

- Qt signal disconnect `RuntimeWarning` messages
- `[SSOT] illegal settings access path`
- Qt stylesheet parse warnings for several `QFrame` objects
- account status warnings with zero values:
  - `[ACCT] warn total=0.0 avail=0.0 - check key/permissions`

These warnings did not stop startup or produce a traceback in this smoke run.

## 7. Safety Result

LocalAppData `aits.log` safety scan found no critical matches for:

- `submitted`
- `order`
- `execution`
- `live`
- `buy`
- `sell`
- `OrderAdapter`
- `ExecutionBridge`
- `trainer`
- `model_auto`
- `active_model`
- `api call`
- `real_order`
- `traceback`
- `exception`
- `error`

Console output did include normal startup service refresh messages such as:

- `fetch_accounts called`
- `fetch_live_holdings called`
- market ticker refresh logs
- `set_settings called | live_trade=False`

Safety interpretation:

- No submitted order was observed.
- No live order execution was observed.
- No buy/sell action was observed.
- `live_trade=False` was logged.
- Local AI trainer automatic execution was not observed.
- active model automatic setting was not observed.
- API key input/save/test was not performed.

## 8. Decision

Decision: `GO_FOR_SCREENSHOT_READINESS`

Why:

- packaged exe starts
- process stays alive for 60 seconds
- no traceback
- `UI launched via legacy-compatible entry` observed
- `app_gui.window_show` logs observed
- chart render logs observed
- dist runtime data remains empty
- LocalAppData data path remains active
- no critical dependency failure
- no live/order/submitted safety violation observed

Remaining non-blocking visual step:

- actual screenshot/visual judgment is still pending outside Codex.

Known non-critical warnings:

- Qt disconnect warnings
- stylesheet parse warnings
- `[SSOT] illegal settings access path`
- zero-account permission warnings

## 9. Next Step

Recommended follow-up after external visual confirmation:

- If the UI looks normal: record `AI-ARCH-19-H-GO` or proceed to the next packaging/runtime verification Goal.
- If the UI is visually broken: open a separate UI packaging fix Goal.
- If logs remain normal but the window does not appear or is off-screen: open a PySide6/window/display fix Goal.

No screenshot request is embedded in this Codex instruction or committed artifact.

## 10. Safety

This Goal did not modify:

- app code
- `run.py`
- `aits_app.spec`
- `packaged_lightgbm_probe.spec`
- `requirements.txt`
- `app/ui/app_gui.py`
- `app/utils/prefs.py`
- `app/utils/keys.py`
- `app/storage/journal_store.py`
- Local AI learning code
- Router code
- Execution code
- Order code
- RiskGuard code

This Goal did not:

- run PyInstaller build
- install or uninstall dependencies
- enter or save API keys
- run API connection tests
- click trading/order buttons
- execute live trading
- create Local AI automatic training scheduler
- auto-approve a model
- set active_model automatically

This is UI screenshot readiness documentation, not deployment approval.
