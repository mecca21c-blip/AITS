# AITS Shadow Decision Preview

## Purpose

Shadow Decision Preview explains the next possible decision-readiness state without calling an AI model or changing any trading path.

It helps an operator understand why the runtime is waiting, blocked by protection mode, or ready for manual review.

## Principles

- preview only
- shadow only
- no inference
- no buy/sell prediction
- no order
- no apply
- submitted=0

## States

- `waiting`: input data is not sufficient for a useful preview.
- `blocked`: some inputs are available, but protection mode blocks execution.
- `ready_for_review`: inputs are sufficient for manual review if execution blocking is not active.

These states are UI preview states only. They are independent from DecisionRouter final action, confidence, and approved action rules.

## Safety Wording Policy

- Do not predict buy or sell.
- Do not imply that an order can be submitted.
- Prefer wording around protection mode, manual review, and waiting.
- Keep all execution and apply paths blocked.

## Verification

Run the standard smoke verification after changes:

```powershell
cd C:\AITS
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
$env:QT_QPA_PLATFORM="offscreen"
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```
