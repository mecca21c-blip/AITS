# AITS Preview System

## 1. Purpose

The Preview System helps operators understand the current AI Runtime state as one read-only flow: runtime input status, reasoning readiness, shadow preview, and DecisionRouter preview.

It is an operator-facing explanation layer. It does not execute inference, apply actions, or submit orders.

## 2. Preview Flow

The preview flow is organized in this order:

1. Runtime Input
2. Reasoning Preview
3. Shadow Decision Preview
4. DecisionRouter Preview

Runtime Input explains what data is attached. Reasoning Preview explains whether the AI has enough context to prepare a judgment. Shadow Decision Preview explains the next possible preview state without predicting buy or sell behavior. DecisionRouter Preview reflects the latest router-side preview metadata in read-only form.

## 3. Runtime Input 5 Axes

Runtime Input is summarized across five axes:

- Market
- Portfolio
- Strategy
- Risk
- Command

Each axis is read from existing in-memory state, UI tables, UI getters, ready flags, or cached count/source hints only. It must not trigger new API calls or data fetches.

## 4. Safety Principles

The Preview System must always preserve these rules:

- read-only
- preview-only
- shadow-only
- no inference
- no order
- no apply
- no buy/sell recommendation
- submitted=0
- real_order=False

Preview data may explain readiness, missing inputs, protection mode, or review status. It must not imply automatic execution.

## 5. UI Display Policy

Screen labels use operator-friendly wording. Technical details should be moved to tooltips.

Avoid wording that looks like a buy, sell, action, or execution recommendation. Order state should appear only as blocked, protected, or preview-only unless a later high-risk sprint explicitly changes execution behavior.

The compact UI should remain short enough to scan during operations. The detailed runtime panel can include more context, but it should still avoid repeating the same protection message across multiple labels.

## 6. Tooltip Policy

Preview tooltips use three sections:

- [1] Current AI State
- [2] Input Connections
- [3] Preview

Tooltips should minimize repeated explanations. Source hints and counts may be included only when they help explain the preview state without crowding the tooltip.

Recommended tooltip content:

```text
[1] Current AI State
- Status, mode, and blocked order state
- Engine/runtime/model in one line when useful

[2] Input Connections
- N/5 connected
- Connected and missing input names

[3] Preview
- Reasoning readiness
- Shadow preview state
- Router preview state
- preview only / submitted=0
```

## 7. DecisionRouter Preview Policy

DecisionRouter Preview uses the DecisionRouter v2.8 preview snapshot.

The router preview is read-only metadata. Candidate action and confidence are preview fields only and must not alter final routing behavior.

Required boundaries:

- Do not change final_action/action/confidence calculation.
- Do not connect preview fields to apply or order paths.
- Do not call OpenAI, Gemini, Ollama, Upbit, or order services.
- Keep operator wording WAIT-centered and review-centered.
- Do not show buy/sell recommendation language in the UI.

## 8. Verification Commands

Use the standard smoke verification:

```powershell
cd C:\AITS
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
$env:QT_QPA_PLATFORM="offscreen"
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```
