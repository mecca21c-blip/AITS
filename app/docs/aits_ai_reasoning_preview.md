# AITS AI Reasoning Preview

## Purpose

AI Reasoning Preview explains what inputs the AI Runtime can currently see before any inference or decision application happens.

It helps an operator understand whether the AI is ready to reason from the current runtime context without exposing technical internals as an action recommendation.

## Principles

- read-only
- preview only
- no inference
- no order
- no apply
- no prediction

## Input Criteria

The preview is based on the five Runtime Input axes:

- Market
- Portfolio
- Strategy
- Risk
- Command

Each axis is read only from existing runtime attachment state. The preview must not fetch market data, request balances, build prompts, call a model, or execute actions.

## State Rules

- `READY`: four or more inputs are attached.
- `PARTIAL`: two or three inputs are attached.
- `WAITING`: fewer than two inputs are attached.

The preview can show that reasoning is ready, partial, or waiting. It must not predict buy, sell, reduce, apply, or submit actions.

## Safety Rules

- `submitted=0`
- `real_order=False`
- `preview_only=True`
- shadow preview only

Order execution remains blocked. The preview is informational and does not change DecisionRouter, OrderAdapter, ExecutionBridge, or any order/apply path.

## Verification

Run the standard smoke verification after changes:

```powershell
cd C:\AITS
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
$env:QT_QPA_PLATFORM="offscreen"
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```
