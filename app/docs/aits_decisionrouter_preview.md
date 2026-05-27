# AITS DecisionRouter Preview

## Purpose

DecisionRouter Preview explains the router's latest preview state to the operator without changing routing, confidence, order, or apply behavior.

It is a read-only bridge between router metadata and the Runtime Preview UI.

## Principles

- preview only
- no inference
- no apply
- no order
- submitted=0
- real_order=False

## Display Fields

- router version
- candidate action
- confidence
- review required
- blocked reason

The UI should keep action wording neutral and avoid presenting the candidate action as a recommendation.

## Safety Policy

- No buy/sell recommendation.
- No action apply implication.
- Use WAIT-centered operator wording.
- Keep order and apply paths blocked.

## Verification

Run the standard smoke verification after changes:

```powershell
cd C:\AITS
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
$env:QT_QPA_PLATFORM="offscreen"
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```
