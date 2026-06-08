# AITS Packaged Runtime Path Verification v1

## 1. Goal

AI-ARCH-19-G maps packaged `AITSMain.exe` runtime data paths after AI-ARCH-19-F2 found that `dist/AITSMain/data/secret.bin` was created during packaged startup.

This Goal is diagnostic only:

- track runtime file locations before and after packaged execution
- classify whether generated files are inside the packaged dist directory
- identify likely code-path causes
- verify safety posture
- do not modify path code, specs, requirements, runtime code, or app behavior

## 2. Pre-State

- Commit hash before diagnostics: `1a9aae3`
- Executable path: `C:\AITS\dist\AITSMain\AITSMain.exe`
- Executable exists: yes
- Executable size: `26,111,196` bytes
- Executable timestamp: `2026-06-08 12:23:46`

Existing packaged runtime files before this Goal's execution:

| File | Location | Size | LastWriteTime |
| --- | --- | ---: | --- |
| `secret.bin` | `C:\AITS\dist\AITSMain\data\secret.bin` | `44` bytes | `2026-06-08 12:46:29` |
| `aits.log` | `C:\AITS\dist\AITSMain\data\logs\aits.log` | `1,408` bytes | `2026-06-08 12:46:39` |

Project root data state:

| File | Location | Size | LastWriteTime |
| --- | --- | ---: | --- |
| `prefs.json` | `C:\AITS\data\prefs.json` | `7,157` bytes | `2026-06-07 08:38:13` |
| `secret.bin` | `C:\AITS\data\secret.bin` | `44` bytes | `2026-03-22 23:46:13` |
| `secrets.json` | `C:\AITS\data\secrets.json` | `930` bytes | `2026-06-07 08:38:13` |
| `aits.log` | `C:\AITS\data\logs\aits.log` | `26,645` bytes | `2026-06-07 08:38:11` |

LocalAppData candidates:

- `%LOCALAPPDATA% = C:\Users\mecca\AppData\Local`
- `C:\Users\mecca\AppData\Local\KMTS-v3` exists
- No active `AITS` or `AITSMain` LocalAppData runtime directory was observed in the targeted candidate scan.
- A recursive LocalAppData search found old AITS-like temp logs under `%LOCALAPPDATA%\Temp`, but no current packaged `AITSMain` prefs/secrets/journal/local registry path.

Path-related code search summary:

- `run.py:21-33` resolves `root_dir` to `os.path.dirname(sys.executable)` when frozen and sets `data_dir = os.path.join(root_dir, "data")`.
- `run.py:355-357` calls `resolve_paths()`, creates `data_dir` and `log_dir`, and initializes logging there.
- `app/utils/prefs.py:103-114` sets `_SECRET_FILE`, `_PREFS_FILE`, and `_SECRETS_FILE` under the provided `data_dir`, then creates `secret.bin` if missing.

## 3. Execution Info

Command:

```powershell
.\dist\AITSMain\AITSMain.exe
```

Observation:

- The executable was started with stdout/stderr captured.
- Observation duration: 60 seconds.
- The process was still running after 60 seconds.
- The process was stopped after observation.

Process result:

- Process id: `20608`
- Running after 60 seconds: `True`
- Exit code: not available because the process was stopped after the observation window.

Console summary:

```text
AITS bootstrap start
[AITS][run] settings_loaded_for_orchestrator | ok=1
[AITS][RuntimePathDiagnostic] run_mode=ui | cwd=C:\AITS | root_dir=C:\AITS\dist\AITSMain | data_dir=C:\AITS\dist\AITSMain\data | prefs_path=C:\AITS\dist\AITSMain\data\prefs.json | prefs_exists=False | provider=local | openai_key_present=False | openai_key_len=0
[AITS][DecisionRouter] initialized | version=v2.8 | mode=shadow_provider
AITS orchestrator initialized
Module pack runtime initialized: AI 기본 모드
UI launched via legacy-compatible entry
```

Traceback:

- No traceback observed.
- No stderr output observed in this run.

UI:

- The process stayed alive and logged `UI launched via legacy-compatible entry`.
- Tool-level screenshot capture was not performed in this Goal.

## 4. Before / After File Change Summary

Snapshot paths:

- `C:\AITS\dist\AITSMain`
- `C:\AITS\data`
- `%LOCALAPPDATA%\AITS`
- `%LOCALAPPDATA%\AITSMain`
- `%LOCALAPPDATA%\KMTS-v3`

Snapshot counts:

- Before count: `2,119`
- After count: `2,119`

New files after this Goal's packaged execution:

- none detected in the tracked snapshot paths

Modified files after this Goal's packaged execution:

| File | New size | New LastWriteTime |
| --- | ---: | --- |
| `C:\AITS\dist\AITSMain\data\logs\aits.log` | `2,816` bytes | `2026-06-08 19:21:20` |

Important interpretation:

- `secret.bin` already existed before this Goal because it was created during AI-ARCH-19-F2 first packaged startup.
- This Goal's repeat run did not recreate or update `secret.bin`.
- The repeat run appended to or rewrote packaged `data/logs/aits.log`.
- No project root data file changed in the tracked output.
- No LocalAppData AITS/AITSMain runtime file was created in the tracked output.

## 5. Runtime File Location Map

| Runtime item | Created / present | Location | Inside dist | External writable path | Policy judgment |
| --- | --- | --- | --- | --- | --- |
| `secret.bin` | present from prior packaged run | `C:\AITS\dist\AITSMain\data\secret.bin` | yes | no | `WAIT`: runtime secret key file lives inside packaged app directory |
| `secrets.json` | not observed | none in packaged dist | no | no | acceptable for this run |
| `prefs.json` | not observed | none in packaged dist | no | no | acceptable for this run, but path resolves to dist if saved later |
| logs | present and updated | `C:\AITS\dist\AITSMain\data\logs\aits.log` | yes | no | `WAIT`: logs are written inside packaged app directory |
| `aits_journal.sqlite3` | not observed | none in packaged dist | no | no | acceptable for this run |
| `local_ai_registry` | not observed | none in packaged dist | no | no | acceptable for this run |
| project root data | present before run | `C:\AITS\data` | no | project workspace | unchanged during packaged run |
| LocalAppData AITS/AITSMain | not observed | none | no | would be preferred | not used |

## 6. Dist Internal Generation Judgment

Finding: `WAIT`

The packaged runtime uses `C:\AITS\dist\AITSMain\data` as its data directory.

Evidence:

- Runtime diagnostic logs report:
  - `root_dir=C:\AITS\dist\AITSMain`
  - `data_dir=C:\AITS\dist\AITSMain\data`
  - `prefs_path=C:\AITS\dist\AITSMain\data\prefs.json`
- `C:\AITS\dist\AITSMain\data\secret.bin` exists.
- `C:\AITS\dist\AITSMain\data\logs\aits.log` exists and was updated during this run.

Build vs runtime distinction:

- `secret.bin` was not packaged into dist by PyInstaller.
- It was generated by packaged runtime startup during the prior packaged smoke.
- This repeat run confirmed the same dist-internal data path is still active.

Why this matters:

- Packaged app directories are not a reliable writable user-data location.
- Future installed builds may run from protected directories.
- Secrets, prefs, logs, journal DBs, and model registry artifacts should not be stored inside the app bundle directory.
- The current path behavior could later create `prefs.json`, `secrets.json`, journal DB, or model registry files inside dist if those flows are triggered.

## 7. Cause Candidates

Likely cause chain:

1. `run.py:21-33`
   - In frozen mode, `root_dir` is derived from `sys.executable`.
   - For this build, that resolves to `C:\AITS\dist\AITSMain`.
   - `data_dir` is then set to `root_dir/data`.

2. `run.py:355-357`
   - `ensure_runtime_dirs(paths["data_dir"], paths["log_dir"])` creates the packaged dist `data` and `data/logs` directories.
   - `init_logging(paths["log_dir"])` writes `aits.log` there.

3. `app/utils/prefs.py:103-114`
   - `init_prefs(root_dir, data_dir)` points `_SECRET_FILE` to `data_dir/secret.bin`.
   - If `secret.bin` does not exist, it creates a new Fernet key file.

Potential missing policy layer:

- No packaged writable app-data helper is used for prefs/secrets/logs.
- No `sys.frozen` branch redirects runtime data to `%LOCALAPPDATA%\AITS` or another external writable user path.
- `root_dir` is serving both app bundle location and runtime data base location.

No code was modified in this Goal.

## 8. Safety Result

Safety scan against packaged `aits.log` found no matches for:

- `submitted`
- `order`
- `execution`
- `live`
- `buy`
- `sell`
- `OrderAdapter`
- `ExecutionBridge`
- `model_auto`
- `active_model`
- `trainer`
- `api call`
- `real_order`
- `traceback`
- `exception`
- `error`

Observed safety state:

- Live order execution: not observed
- Submitted order event: not observed
- API call automatic execution: not observed
- active_model automatic setting: not observed
- Local AI trainer automatic execution: not observed
- Real trading safety violation: not observed
- OpenAI key present: false
- Gemini key present: false

## 9. Decision

Decision: `WAIT`

Reasons:

- The app starts without a critical traceback.
- No safety violation was observed.
- No new runtime files were created during the repeat run except log growth.
- However, packaged runtime data is rooted inside `dist/AITSMain/data`.
- `secret.bin` is already present inside dist from packaged runtime startup.
- Logs are written inside dist.
- Future prefs, secrets, journal, or local_ai_registry writes would likely also target dist unless the path policy is fixed.

This is not a crash or dependency failure. It is a runtime path policy issue.

## 10. Next Fix Goal

Recommended next Goal:

- `AI-ARCH-19-G-FIX1 Packaged Writable Data Path Policy`

Recommended fix direction for that future Goal:

- Add a single runtime path policy for packaged mode.
- Keep app bundle root separate from writable user data root.
- In frozen mode, route writable data to a user-specific path such as:
  - `%LOCALAPPDATA%\AITS`
  - or another explicit AITS app data directory approved by project policy
- Ensure these items use the external writable path:
  - `secret.bin`
  - `secrets.json`
  - `prefs.json`
  - logs
  - journal DB
  - `local_ai_registry`
- Preserve current source-tree behavior for development mode unless explicitly changed by the Fix Goal.

Additional follow-up if visual confirmation remains needed:

- `AI-ARCH-19-H Packaged UI Screenshot Verification`

## 11. Safety

This Goal did not modify:

- `requirements.txt`
- `aits_app.spec`
- `packaged_lightgbm_probe.spec`
- `run.py`
- `app/ui/app_gui.py`
- `app/utils/prefs.py`
- `app/utils/keys.py`
- `app/storage/journal_store.py`
- `app/learning/*`
- Router code
- Execution code
- Order code
- RiskGuard code

No PyInstaller build was executed.
No app/spec/path fix was applied.
No API key was entered, saved, or tested.
No trading button was pressed.
No order action was performed.
No Local AI trainer was auto-started.
`submitted=0` principle remains intact.

This document is a path diagnostic report, not a runtime path fix and not deployment approval.
