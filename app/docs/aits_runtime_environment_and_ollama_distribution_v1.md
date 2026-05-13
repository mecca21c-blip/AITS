# AITS Runtime Environment & Ollama Distribution Policy v1

## 1. Current Issue

The project `.venv\Scripts\python.exe` currently reports a broken base interpreter reference:

`C:\Users\mecca\AppData\Local\Programs\Python\Python313\python.exe`

Recent validation succeeded with system Python `3.14.4` at `C:\Python314\python.exe`, which means the active validation interpreter and the project virtual environment are not aligned. This is a packaging and deployment risk because another PC may not have the same system Python or the broken Python 3.13 path.

## 2. Principles

- Do not split development validation Python and distribution Python.
- The official AITS development runtime should be the project-local `.venv`.
- If `.venv` is broken, repair or recreate it in a separate approved task.
- `py_compile`, headless checks, and runtime smoke tests should use the same interpreter.
- Environment probes must not run provider inference, install packages, create directories, or modify settings.

## 3. Recommended venv Policy

- `.venv` lives under the project root.
- The Python version is pinned to one supported version for development and packaging.
- Dependencies are restored from `requirements.txt`.
- `pip install` is never run automatically by diagnostic code.
- `.venv` repair should be documented and executed as a dedicated SPRINT-01-A3 task.

## 4. Ollama Distribution Policy

AITS should prefer a bundled Ollama runtime so users do not need a separate manual install.

Development/source layout:

- `runtime/ollama/ollama.exe`
- `runtime/ollama/models`

Packaged layout:

- `<exe_dir>/runtime/ollama/ollama.exe`
- `<exe_dir>/runtime/ollama/models`

User data fallback:

- `%LOCALAPPDATA%/AITS/runtime/ollama`
- `%LOCALAPPDATA%/AITS/runtime/ollama/models`

Preferred model family:

- `qwen2.5` 7B Instruct Q4 series

This step does not download, execute, or start Ollama.

## 5. Packaging Policy

- PyInstaller should use `onedir` packaging for runtime asset clarity.
- `runtime/ollama` should be included as a runtime asset folder when enabled.
- Model files are large and need a separate asset/version policy.
- Packaged execution should resolve paths from the executable directory.

## 6. Safety Policy

- Ollama path diagnosis is not inference.
- Model path detection is not model execution.
- Runtime status and inference execution stay separated.
- All diagnostic metadata keeps `submitted=0`, `real_order=False`, `shadow_only=True`, and `research_mode=True`.

## 7. Next Steps

- SPRINT-01-A3: venv repair plan
- SPRINT-01-A4: Ollama runtime asset layout
- SPRINT-01-A5: Ollama process health check
- SPRINT-01-A6: local inference dry-run to real local call gate
