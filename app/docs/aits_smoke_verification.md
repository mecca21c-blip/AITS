# AITS Smoke Verification Standard

This document defines the standard smoke verification flow for AITS patches.
Use this flow after code changes unless a sprint instruction explicitly says otherwise.

## Standard Commands

Run each command separately in PowerShell.

```powershell
cd C:\AITS
```

```powershell
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
```

```powershell
$env:QT_QPA_PLATFORM="offscreen"
```

```powershell
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```

## Success Criteria

- `[AITS][SmokeExit] runtime_stubs_installed`
- `[AITS][SmokeExit] scheduled`
- `[AITS][SmokeExit] quit`
- DecisionRouter v2.8 initialized
- No `Traceback`
- No real API or order call

## Notes

- Do not combine the `--smoke-exit` command with other commands.
- Run the PowerShell commands one line at a time.
- The smoke exit harness is for boot/runtime safety verification only.
- The smoke exit harness must not be treated as an inference, provider API, or order execution test.
