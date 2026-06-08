# AITS Packaged Writable Data Path Policy v1

## 1. Goal

AI-ARCH-19-G-FIX1 fixes packaged runtime writable data path behavior.

Before this patch, packaged `AITSMain.exe` used `dist/AITSMain/data` as the runtime writable data directory. This caused packaged startup to create or update runtime files inside the packaged application directory.

This patch changes packaged/frozen mode so writable runtime data uses:

```text
%LOCALAPPDATA%\AITS\data
```

Development mode keeps the existing project-root data path:

```text
C:\AITS\data
```

## 2. Existing Problem

AI-ARCH-19-G found these packaged runtime files under the dist directory:

```text
C:\AITS\dist\AITSMain\data\secret.bin
C:\AITS\dist\AITSMain\data\logs\aits.log
```

Root cause candidate:

- `run.py` resolved frozen `root_dir` to the executable directory.
- `data_dir` was derived as `root_dir/data`.
- `app.utils.prefs.init_prefs()` creates `secret.bin` under the injected `data_dir` when missing.
- `init_logging()` writes `aits.log` under `data_dir/logs`.

The packaged app directory should be treated as an application bundle, not as the user writable data store.

## 3. Changed Policy

`run.py` now separates app root from writable data root.

Development mode:

| Field | Value |
| --- | --- |
| `root_dir` | project root |
| `data_dir` | `project_root\data` |
| `log_dir` | `project_root\data\logs` |

Packaged/frozen mode:

| Field | Value |
| --- | --- |
| `root_dir` | executable directory |
| `data_dir` | `%LOCALAPPDATA%\AITS\data` |
| `log_dir` | `%LOCALAPPDATA%\AITS\data\logs` |

Fallback if `LOCALAPPDATA` is unavailable:

```text
%USERPROFILE%\AppData\Local\AITS\data
```

## 4. Modified Files

Code:

- `run.py`

Documentation:

- `app/docs/aits_packaged_writable_data_path_policy_v1.md`

No large storage/prefs refactor was performed.

Not modified:

- `app/utils/prefs.py`
- `app/utils/keys.py`
- `app/storage/journal_store.py`
- `app/learning/*`
- `app/ui/app_gui.py`
- Router/Execution/Order/RiskGuard layers
- `requirements.txt`
- `aits_app.spec`

## 5. Verification Results

### py_compile

Command:

```powershell
.\.venv\Scripts\python.exe -m py_compile run.py
```

Result:

- passed

### Path Resolution

Development mode check:

```text
{'root_dir': 'C:\\AITS', 'data_dir': 'C:\\AITS\\data', 'log_dir': 'C:\\AITS\\data\\logs'}
```

Frozen mode simulation:

```text
{'root_dir': 'C:\\AITS\\.venv\\Scripts', 'data_dir': 'C:\\Users\\mecca\\AppData\\Local\\AITS\\data', 'log_dir': 'C:\\Users\\mecca\\AppData\\Local\\AITS\\data\\logs'}
```

### Main App Rebuild

Command:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm aits_app.spec
```

Result:

- build succeeded
- elapsed wall time: about 7 minutes 17 seconds
- executable generated:

```text
C:\AITS\dist\AITSMain\AITSMain.exe
```

Generated executable size:

```text
26,111,493 bytes
```

Build warnings to track separately:

- `collect_dynamic_libs - skipping library collection for module 'sklearn' as it is not a package`
- hidden import `pycparser.lextab` not found
- hidden import `pycparser.yacctab` not found
- hidden import `scipy.special._cdflib` not found
- `google.generativeai` package deprecation warning

These warnings did not prevent this build or packaged smoke from passing.

### Packaged Smoke

Command:

```powershell
.\dist\AITSMain\AITSMain.exe
```

Observation:

- observed for 60 seconds
- process stayed alive
- process was stopped after observation
- no traceback observed
- no stderr output observed
- UI launch log observed

Runtime diagnostic:

```text
root_dir=C:\AITS\dist\AITSMain
data_dir=C:\Users\mecca\AppData\Local\AITS\data
prefs_path=C:\Users\mecca\AppData\Local\AITS\data\prefs.json
prefs_exists=False
openai_key_present=False
```

## 6. Runtime File Location Map

After packaged smoke:

| Runtime item | Expected location | Observed location | Result |
| --- | --- | --- | --- |
| `secret.bin` | `%LOCALAPPDATA%\AITS\data\secret.bin` | `C:\Users\mecca\AppData\Local\AITS\data\secret.bin` | pass |
| logs | `%LOCALAPPDATA%\AITS\data\logs\aits.log` | `C:\Users\mecca\AppData\Local\AITS\data\logs\aits.log` | pass |
| `prefs.json` | `%LOCALAPPDATA%\AITS\data\prefs.json` when saved | not created during smoke | acceptable |
| `secrets.json` | `%LOCALAPPDATA%\AITS\data\secrets.json` when saved | not created during smoke | acceptable |
| journal DB | `%LOCALAPPDATA%\AITS\data\...` when journal is used | not created during smoke | acceptable |
| `local_ai_registry` | `%LOCALAPPDATA%\AITS\data\...` when registry is used | not created during smoke | acceptable |

Dist internal runtime scan after packaged smoke:

- no `secret.bin`
- no `secrets.json`
- no `prefs.json`
- no `aits_journal.sqlite3`
- no `local_ai_registry`
- no `.log` file

## 7. Safety

Safety scan against the new LocalAppData log found no matches for:

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
- `traceback`
- `exception`
- `error`

Observed safety state:

- live trading: not observed
- submitted order: not observed
- API key input/save/test: not performed
- Router/Execution connection change: none
- Local AI trainer auto-start: not observed
- model auto approval: not observed

## 8. Decision

Decision: `GO`

Reasons:

- packaged exe starts and remains alive
- packaged runtime `data_dir` now points to `%LOCALAPPDATA%\AITS\data`
- dist internal runtime files are not created after rebuild and smoke
- LocalAppData runtime files are created as expected
- safety scan found no live/order/trainer/approval signals
- only `run.py` and this document were changed

Remaining note:

- UI was inferred from `UI launched via legacy-compatible entry` and process survival. A later UI screenshot verification can still be useful, but it is not blocking this data path policy fix.

## 9. Future Follow-Up

Recommended next Goal:

- `AI-ARCH-19-H Packaged UI Screenshot Verification`

Optional later checks:

- verify prefs save/load in packaged mode without API key entry
- verify journal DB path when journal feature is intentionally exercised
- verify `local_ai_registry` path when registry feature is intentionally exercised

## 10. Non-Goals

This Goal did not:

- redesign prefs/secrets storage
- migrate old project-root data
- modify app GUI
- modify Router, Execution, Order, or RiskGuard
- modify requirements
- add dependencies
- enable live trading
- run Local AI automatic training
- approve or activate a model

This is a packaged runtime data path fix, not deployment approval.
