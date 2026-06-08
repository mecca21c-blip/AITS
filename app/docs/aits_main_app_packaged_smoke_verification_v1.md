# AITS Main App Packaged Smoke Verification v1

## 1. Goal

AI-ARCH-19-F2 verifies the packaged main app executable created after the main app PyInstaller spec slimming work.

Scope:

- Run `dist/AITSMain/AITSMain.exe` once.
- Observe startup, console output, traceback status, packaged runtime path behavior, and safety posture.
- Do not modify app code, specs, requirements, Router, UI, Execution, Order, RiskGuard, or learning runtime.
- Do not treat this smoke verification as release approval.

## 2. Pre-State

- Commit hash before smoke: `ef2839d`
- Executable path: `C:\AITS\dist\AITSMain\AITSMain.exe`
- Executable exists: yes
- Executable size: `26,111,196` bytes
- Executable timestamp: `2026-06-08 12:23:46`
- Dist top-level structure:
  - `_internal/`
  - `AITSMain.exe`

Pre-run runtime data scan:

- `secrets.json`: not found in packaged dist
- `secret.bin`: not found in packaged dist
- `aits_journal.sqlite3`: not found in packaged dist
- `local_ai_registry`: not found in packaged dist
- `prefs.json`: not found in packaged dist

Packaged dependency traces were present under `_internal`:

- `lightgbm`
- `lightgbm-4.6.0.dist-info`
- `lightgbm/bin/lib_lightgbm.dll`
- `scipy`
- `scipy-1.17.1.dist-info`
- `scipy.libs`
- `numpy`
- `numpy-2.4.4.dist-info`
- `numpy.libs`
- `PySide6`
- `matplotlib`

## 3. Execution Info

Command:

```powershell
.\dist\AITSMain\AITSMain.exe
```

Observation method:

- Started the packaged exe with stdout/stderr redirected to temporary files.
- Waited 60 seconds.
- The process was still running after 60 seconds.
- Stopped the process after observation.

Process result:

- Process id: `19836`
- Running after 60 seconds: `True`
- Exit code: not available because the process was stopped after the smoke window.

## 4. App Start Result

Result: partial pass.

Observed stdout:

```text
AITS bootstrap start
[AITS][run] settings_loaded_for_orchestrator | ok=1
[AITS][RuntimePathDiagnostic] run_mode=ui | cwd=C:\AITS | root_dir=C:\AITS\dist\AITSMain | data_dir=C:\AITS\dist\AITSMain\data | prefs_path=C:\AITS\dist\AITSMain\data\prefs.json | prefs_exists=False | provider=local | openai_key_present=False | openai_key_len=0
[AITS][DecisionRouter] initialized | version=v2.8 | mode=shadow_provider
AITS orchestrator initialized
Module pack runtime initialized
UI launched via legacy-compatible entry
```

Observed stderr:

```text
Matplotlib is building the font cache; this may take a moment.
```

Traceback status:

- No Python traceback was observed in stdout.
- No Python traceback was observed in stderr.
- No immediate process crash was observed.
- The app remained alive for the 60 second smoke window.

UI visibility:

- Tool-level visual screenshot capture was not available in this smoke run.
- The packaged process remained alive and logged `UI launched via legacy-compatible entry`.
- A follow-up visual/screenshot verification is recommended before marking this packaging path fully GO.

## 5. Dependency Result

No critical dependency errors were observed.

- PySide6 platform plugin error: not observed
- matplotlib error: not observed
- mplfinance error: not observed
- LightGBM error: not observed
- scipy error: not observed
- numpy error: not observed
- missing import error: not observed
- DLL/native dependency error: not observed

The only stderr line was matplotlib font cache initialization.

## 6. Runtime Path Result

Runtime path diagnostic:

- `root_dir=C:\AITS\dist\AITSMain`
- `data_dir=C:\AITS\dist\AITSMain\data`
- `prefs_path=C:\AITS\dist\AITSMain\data\prefs.json`
- `prefs_exists=False`
- `provider=local`
- `openai_key_present=False`

Runtime-created files after execution:

- `C:\AITS\dist\AITSMain\data\logs\aits.log`
- `C:\AITS\dist\AITSMain\data\secret.bin` (`44` bytes)

Interpretation:

- `secret.bin` was not packaged into dist before execution.
- The packaged app created `secret.bin` during first startup under the packaged `data` directory.
- This is not a build-time secret inclusion, but it is a packaged runtime writable-path behavior that should be reviewed in AI-ARCH-19-G.

Runtime path errors:

- prefs path critical error: not observed
- secrets path critical error: not observed
- log path critical error: not observed
- journal DB path critical error: not observed
- local_ai_registry path critical error: not observed
- writable path critical error: not observed

## 7. Safety Result

Safety keyword scan against packaged `aits.log` did not find matches for:

- `submitted`
- `order`
- `execution`
- `trainer`
- `model_auto`
- `active_model`
- `traceback`
- `exception`
- `RiskGuard`
- `OrderAdapter`
- `BUY`
- `SELL`

Observed safety state:

- Live order execution: not observed
- Submitted order event: not observed
- OrderAdapter automatic execution: not observed
- ExecutionBridge automatic execution: not observed
- RiskGuard bypass: not observed
- active_model automatic setting: not observed
- Local AI trainer automatic execution: not observed
- API key present: false for OpenAI and Gemini
- API call auto-run: not observed

## 8. UI Smoke Result

UI smoke status: limited.

Positive signals:

- Process started successfully.
- Process stayed alive for 60 seconds.
- Startup logs reached `UI launched via legacy-compatible entry`.
- No critical startup traceback was observed.

Limitations:

- No screenshot was captured in this verification.
- No manual UI tab inspection was performed.
- No UI control was clicked.
- No API key input, connection test, trade action, or order action was performed.

## 9. Decision

Decision: `WAIT`

Reason:

- The packaged exe starts and stays alive without a critical traceback.
- Dependency errors were not observed.
- Packaged dist did not include runtime secrets before execution.
- However, visual UI confirmation was not captured by tooling.
- The packaged runtime created `dist/AITSMain/data/secret.bin` on first startup, which should be reviewed as runtime path behavior before declaring full packaging GO.

GO conditions partially met:

- exe execution: pass
- no critical traceback: pass
- dependency critical error absent: pass
- live/order safety violation absent: pass

Remaining WAIT items:

- capture or manually confirm UI window rendering
- verify runtime writable path policy for packaged `data`
- decide whether packaged first-run `secret.bin` location is acceptable

## 10. Packaging Risk / Next Fix Goal

Recommended next goal:

- `AI-ARCH-19-G Packaged Runtime Path Verification/Fix`

Why:

- The app uses `C:\AITS\dist\AITSMain\data` as packaged runtime data path.
- `secret.bin` is generated there on startup.
- This should be reviewed separately from dependency packaging because it affects runtime data policy, not PyInstaller dependency inclusion.

Potential follow-ups:

- If UI screenshot confirmation is required: `AI-ARCH-19-F2-B Main App Packaged UI Visual Smoke`
- If runtime data path should move outside dist: `AI-ARCH-19-G Packaged Runtime Path Verification/Fix`
- If later UI launch reveals plugin issues: `AI-ARCH-19-F2-FIX1 PySide6 Plugin Runtime Fix`

## 11. Safety

This Goal did not modify:

- `requirements.txt`
- `aits_app.spec`
- `packaged_lightgbm_probe.spec`
- `run.py`
- `app/ui/app_gui.py`
- Router code
- Execution code
- Order code
- RiskGuard code
- Local AI learning code
- storage code

No PyInstaller build was executed in this Goal.
No packaged dependency probe was rebuilt.
No live trading path was connected.
No order action was performed.
No API key was entered, saved, or tested.
No Local AI trainer was auto-started.
`submitted=0` principle remains intact.

This smoke result is not deployment approval.
