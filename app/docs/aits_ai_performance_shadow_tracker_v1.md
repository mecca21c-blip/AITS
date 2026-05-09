# AITS AI Performance Shadow Tracker v1

## 1. Purpose

AI Performance Shadow Tracker is a record-and-analysis device for AI judgment quality.

Its purpose is to:

- Verify AI judgment performance.
- Compare provider-level strategy behavior.
- Analyze AI reliability.
- Track AI behavior before any real order path is considered.

This layer exists to answer one question: how well did the AI judgment behave over time?

## 2. Core Principles

This system is not "virtual trading".

It is not a user practice account. It is not a simulated exchange account. It is not an execution rehearsal layer.

Hard safety rules:

- Real orders are strictly forbidden.
- Do not connect to `OrderAdapter`.
- Do not connect to `ExecutionBridge`.
- Do not call Upbit order APIs.
- Do not submit orders.
- Do not mutate real trading state.

The tracker records AI behavior for performance analysis only.

## 3. Current Structure

Current conceptual flow:

```text
AI Shadow
→ Shadow History
→ Provider Stats
→ State Machine
→ AI Performance Shadow Tracker
→ Virtual Performance Metrics
```

The tracker consumes AI shadow interpretation and records performance-oriented state. It does not route orders.

## 4. Internal Models

Current model skeletons:

- `PaperShadowPosition`
- `PaperShadowResult`

Required safety fields:

- `virtual_only=True`
- `real_order=False`
- `submitted=0`
- `applied=False`

These fields define the object as a shadow performance artifact, not a real position or execution record.

## 5. Shadow Tracker Rules

Initial tracker behavior:

- `buy` → virtual tracking entry
- `hold/watch/wait` → monitoring
- `sell/remove` → virtual close
- `reduce` → partial reduce placeholder
- `long_watch` → monitoring only

These rules do not create orders. They only record what the AI judgment implied for later performance analysis.

## 6. Tracker Summary

Tracker summary fields:

- `total_positions`
- `open_positions`
- `closed_positions`
- `providers`
- `win_count`
- `loss_count`

The summary is for diagnostics and reliability analysis only.

## 7. Real Trading vs Shadow Tracker

| Category | Real Trading | Shadow Tracker |
| --- | --- | --- |
| OrderAdapter | Used | Not used |
| ExecutionBridge | May be used | Not used |
| submitted | `submitted > 0` possible | `submitted=0` fixed |
| real_order | `real_order=True` possible | `real_order=False` fixed |
| virtual_only | False or not applicable | `virtual_only=True` fixed |
| Purpose | Execute orders | Analyze AI judgment performance |

The Shadow Tracker must never be treated as a trading engine.

## 8. Future Expansion

Future analysis directions:

- Provider reliability
- Scenario-level winrate
- AI survival analysis
- Provider ensemble
- Confidence calibration

These expansions remain analysis-only unless a separate, explicit live trading approval process is defined later.

## 9. Next Roadmap

201차:
Provider reliability score skeleton

202차:
Shadow performance metrics

203차:
Scenario performance tracker

204차:
Live provider one-shot test harness
