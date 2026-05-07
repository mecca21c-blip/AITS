# AITS DecisionRouter Shadow Integration Plan v1

## 1. Purpose

This document fixes the shadow-only safety contract before AI pipeline results are connected to `DecisionRouter`.

The goal is to prepare integration without allowing AI output to affect real trading actions. This is a verification phase before any trading reflection. AI outputs may be attached, observed, summarized, and compared, but they must not change final action or order flow.

## 2. Current AI Pipeline

Current pipeline:

```text
Context
→ State Context
→ Prompt
→ Provider Router
→ Shadow Record
→ State Machine
→ State Repository
→ State History
→ UI-ready dict
```

Meaning:

- Context builds compact market and operating inputs.
- State Context adds current state and recent history continuity.
- Prompt asks the provider for suggestion-only JSON.
- Provider Router creates normalized dry-run AI output.
- Shadow Record preserves provider analysis without action application.
- State Machine converts AI output into state snapshot.
- State Repository keeps latest state in memory.
- State History keeps state transitions in memory.
- UI-ready dict formats state for display.

## 3. Values That May Be Passed To Router

The following values may be attached as shadow data only:

- `shadow_record`
- `state_snapshot`
- `state_ui`
- `provider`
- `model`
- `parsed_valid`
- `suggestion`
- `next_action`
- `confidence`
- `scenario`
- `eta`
- `evidence`
- `pool_action`

These values are metadata for observation, diagnostics, and later comparison. They are not order instructions.

## 4. Values That Must Never Be Reflected Into Router Action

The shadow integration must not:

- Change `action`
- Directly create `buy` or `sell`
- Final-adjust router confidence
- Pass anything to `OrderAdapter`
- Pass anything to `ExecutionBridge`

AI shadow data must remain separate from the existing router decision result until a later approved phase.

## 5. Safety Contract

Required safety fields and invariants:

- `suggestion_only=True`
- `applied_to_action=False`
- `applied=False`
- `dry_run=True`
- `submitted=0`

The router must preserve the pre-existing final action. AI state can be displayed or logged, but it cannot become execution intent.

## 6. DecisionRouter Integration Method

### Phase 1

- Store only under `raw["meta"]["ai_shadow"]`.
- Show limited `ai_state` / `state_ui` fields in `RouterSummary`.
- Do not alter final action.
- Keep `ai_applied=False`.

### Phase 2

- Accumulate entries in `shadow_history`.
- Compare provider output by provider/model.
- Track stability, oscillation, and scenario consistency.

### Phase 3

- Add paper trading shadow apply.
- This is still not a real order.
- Paper result must remain separated from live execution fields.

### Phase 4

- Live application requires separate approval.
- Live application must not be enabled by this plan.
- Any future live mode must pass explicit safety gates.

## 7. Logging Plan

Planned log lines:

```text
[AITS][DecisionRouter] ai_shadow_received
[AITS][DecisionRouter] ai_shadow_stored
[AITS][DecisionRouter] ai_state_attached
[AITS][RouterSummary] ai_state=... ai_action=... ai_applied=False
```

Logs must not print API keys, secrets, raw provider responses, or full prompts.

## 8. Verification Conditions

Required verification conditions:

- `submitted=0`
- No `buy_order_request`
- No `sell_order_request`
- Final action keeps existing value
- `ai_applied=False`

Failure of any condition means the integration is not shadow-only and must be rejected.

## 9. Next Implementation Order

188차:
DecisionRouter shadow-only field attach

189차:
RouterSummary AI state display

190차:
`shadow_history` accumulation

191차:
Provider comparison stats

192차:
Paper trading shadow apply
