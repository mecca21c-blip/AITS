# AITS Dependency Audit v1

## 1. Current Findings

The repaired `.venv` now includes `cryptography`, and its import check passed.

The next headless run failed on:

`ModuleNotFoundError: No module named 'pydantic'`

This confirms `pydantic` is required by the runtime path but is not currently installed in the repaired environment.

## 2. Why This Audit Exists

Finding one missing dependency per headless run wastes time and makes packaging unreliable. AITS needs a clear dependency baseline before UI/runtime packaging and Ollama local runtime work continue.

The audit step checks package availability only. It does not install packages, call providers, run Ollama, touch orders, or modify `requirements.txt`.

## 3. Dependency Candidates

The current audit list checks:

- `cryptography` / `cryptography`
- `pydantic` / `pydantic`
- `PySide6` / `PySide6`
- `pandas` / `pandas`
- `matplotlib` / `matplotlib`
- `mplfinance` / `mplfinance`
- `requests` / `requests`
- `pyupbit` / `pyupbit`
- `openai` / `openai`
- `google-generativeai` / `google.generativeai`
- `numpy` / `numpy`
- `python-dotenv` / `dotenv`

## 4. Requirements Sync Policy

`requirements.txt` is not updated in this step. Synchronization should happen in a separate dependency repair task after reviewing the audit output.

## 5. Safety Statement

This audit performs import discovery only. It does not call provider APIs, run Ollama inference, access Upbit order execution, or modify live trading state.
