# AITS Detail Chart Symbol Policy v1

## 1. Purpose

This document defines how the detail chart's per-symbol policy panel should be understood.

The panel is a per-symbol observation policy surface. It may store symbol-specific preferences, but it must not bypass the global policy center, Risk Guard, Router, Order, or Execution.

## 2. Global Policy vs Symbol Policy

Global policy center owns broad operating posture:

- Provider and AI-call policy.
- Global observation style.
- Global risk and execution boundaries.
- Runtime Preview and policy summaries.

Detail-chart symbol policy owns only symbol-specific display and future override candidates:

- Whether this symbol should follow global policy.
- Whether this symbol needs stronger or weaker observation.
- Whether this symbol should be observation-only, held, excluded, or reviewed more carefully.
- Whether a future per-symbol limit should be proposed before Risk Guard integration.

## 3. Current Panel Audit

| Item | Current UI Meaning | Source | Global Overlap | Current Runtime Effect |
| --- | --- | --- | --- | --- |
| Operation style | Per-symbol display preference | detail chart UI state | High | Display/storage only |
| Symbol tendency | Per-symbol observation tendency | detail chart UI state | Medium | Display/storage only |
| Analysis reference strength | How strongly this symbol should be reviewed | detail chart UI state | Medium | Display/storage only |
| Maximum symbol weight | Candidate per-symbol cap | detail chart UI state | High | Not connected to Risk Guard or Order |
| Reset defaults | Restore global-following defaults | detail chart UI state | Low | UI state only |
| Advanced symbol policy details | Future audit/design area | placeholder UI | Medium | No runtime effect |

## 4. Per-Symbol Override Candidates

Future candidates:

1. AI analysis cadence override
   - Follow global policy
   - Fast
   - Normal
   - Slow
   - Manual only
   - Not connected in this Goal.

2. Observation sensitivity override
   - Follow global policy
   - Low
   - Normal
   - High

3. Maximum position weight override
   - Follow global policy
   - Symbol-specific cap
   - Must not affect Order or Risk Guard until a separate RiskGuard integration Goal.

4. Symbol operation status
   - Follow global policy
   - Observation only
   - Manual hold
   - Enhanced AI review
   - Excluded

## 5. Safety Rules

- Per-symbol policy must not place orders.
- Per-symbol policy must not schedule GPT/Gemini calls by itself.
- Per-symbol AI cadence is a design candidate only until an explicit AI-call policy implementation Goal.
- Per-symbol weight is display/storage only until Risk Guard owns enforcement.
- `submitted=0` remains an internal safety flag; user UI should show it as `실제 주문 없음`.
- `Router/Execution` should be shown to users as `주문 실행 경로`.

## 6. Follow-Up Goals

- `DETAIL-CHART-SYMBOL-POLICY-02`: define the final per-symbol policy schema.
- `SYMBOL-AI-CADENCE-POLICY-01`: design per-symbol AI analysis cadence without adding API calls.
- `SYMBOL-RISKGUARD-WEIGHT-CONTRACT-01`: define how a symbol-specific weight cap would be enforced by Risk Guard.
- `DETAIL-CHART-SYMBOL-POLICY-UI-01`: split active controls from future/disabled candidates.

## 7. DETAIL-CHART-UI-POLICY-POLISH-01 Notes

The detail-chart symbol policy panel is currently a display and design-candidate surface.

Per-symbol candidate fields:

1. AI analysis cadence override
   - Follow global policy
   - Fast
   - Normal
   - Slow
   - Manual only
   - Must not be connected to timers or API calls without a separate AI-call policy Goal.

2. Observation sensitivity override
   - Follow global policy
   - Low
   - Normal
   - High

3. Maximum symbol weight override
   - Follow global policy
   - Symbol-specific cap
   - Must not affect Order or Risk Guard until a separate RiskGuard integration Goal.

4. Symbol operation status
   - Follow global policy
   - Observation only
   - Manual hold
   - Enhanced AI review
   - Excluded

5. Per-symbol memo or reason
   - User note explaining why the symbol is watched
   - Whether AI may use this note is a later policy decision.

Current UI labels should make clear that `AI analysis reference strength` and symbol weight fields are display-only and do not affect orders, Risk Guard, or AI-call cadence.

## 8. AI-POLICY-CENTER-UI-SSOT-01 Notes

The AI Policy Center is the upper-level global policy SSOT.

Relationship rules:

- Global AI policy defaults are previewed and saved in the AI Policy Center.
- The detail-chart symbol policy panel is a per-symbol exception candidate and display-only surface.
- Per-symbol settings may describe observation sensitivity, review strength, future cadence candidates, or symbol-specific notes.
- Per-symbol settings do not override global policy for live orders until a separate Router/Risk Guard/Order integration Goal defines that contract.
- Per-symbol AI cadence candidates must not create timers or GPT/Gemini calls in this Goal.
- Per-symbol maximum weight candidates must not affect Risk Guard or Order sizing in this Goal.
- The user-facing copy should say `전역 정책 따름`, `표시 전용`, or `후속 적용 예정` when a field is not connected to runtime enforcement.
