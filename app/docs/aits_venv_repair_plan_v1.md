# AITS venv Repair Plan v1

## 1. Current Problem

The current shell validation Python is:

`C:\Python314\python.exe`

The project `.venv` exists, but `.venv\pyvenv.cfg` may still point to an older Python 3.13 installation:

`C:\Users\mecca\AppData\Local\Programs\Python\Python313\python.exe`

This means the system Python and project virtual environment are not aligned.

## 2. Why This Matters

- `py_compile` and headless validation may run under different interpreters.
- Packaging output can become unstable or non-reproducible.
- Dependency installation location becomes unclear.
- A different PC may not have the same global Python path.
- A broken `.venv` can silently pass path existence checks while failing execution.

## 3. Official Development Principle

- AITS official development execution and validation should use the project `.venv`.
- System Python is only a bootstrap or repair tool.
- `py_compile`, headless checks, packaging, and smoke tests should use the same interpreter.
- `requirements.txt` remains the dependency source of truth.

## 4. Safe Manual Repair Procedure

This document does not execute any commands. Use this as a manual checklist in a dedicated repair task.

1. Back up the current state.
2. Confirm `requirements.txt` exists and is the intended dependency source.
3. Choose one Python version for AITS development and packaging.
4. Delete or archive the broken `.venv` only after approval.
5. Recreate `.venv` from the chosen Python.
6. Install dependencies from `requirements.txt`.
7. Run `py_compile` checks with `.venv\Scripts\python.exe`.
8. Run headless validation with the same interpreter.

## 5. Recommended Command Examples

These are examples only. They are not executed by SPRINT-01-A3.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m py_compile app\services\runtime_environment_probe.py
.venv\Scripts\python.exe run.py --headless
```

## 6. Rollback Criteria

Stop and keep the existing system Python path available if any of the following fail:

- `requirements.txt` install fails.
- `PySide6` import fails.
- `run.py --headless` fails.
- Core service `py_compile` fails.

## 7. Next Steps

- SPRINT-01-A4: Ollama runtime asset layout
- SPRINT-01-A5: Ollama process health check
- SPRINT-01-A6: local inference live gate
