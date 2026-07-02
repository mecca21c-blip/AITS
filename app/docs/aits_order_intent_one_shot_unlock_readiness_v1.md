# AITS Order Intent One-Shot Unlock Readiness v1

`aits_order_intent_one_shot_unlock_readiness_v1` is a read-only contract after
Router validation payload readiness and source live policy readiness.

It does not execute the one-shot unlock service, does not consume an unlock,
does not emit an order intent, and does not call DecisionRouter, RiskGuard,
LivePreflight, OrderService, OrderAdapter, or ExecutionBridge.

## Required Inputs

- Router validation stub payload
- Source live policy result
- Optional mock unlock context for proof only:
  - `mock_unlock_approved_symbols`
  - `mock_unlock_expired`
  - `mock_unlock_consumed`
  - `mock_unlock_reusable`

## Schema

Required report fields:

- `schema=aits_order_intent_one_shot_unlock_readiness_v1`
- `symbol`
- `source`
- `router_validation_payload_ready`
- `source_policy_ready`
- `one_shot_unlock_required`
- `one_shot_unlock_ready`
- `unlock_approval_mode`
- `unlock_approved_symbols`
- `unlock_consumed`
- `unlock_reusable`
- `unlock_expired`
- `live_order_readiness`
- `policy_warnings`
- `policy_blockers`
- `safety_flags`

Safety flags must remain inert:

- `actual_order=false`
- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `final_action_unchanged=true`
- `submitted=0`

## Readiness Rules

Without exact mock unlock approval, readiness is blocked:

- `one_shot_unlock_ready=false`
- `policy_blockers` contains `one_shot_unlock_required`
- `live_order_readiness=false`

With exact mock unlock approval for the same symbol:

- `one_shot_unlock_ready=true`
- `policy_blockers=[]`
- `live_order_readiness=true`

This is still only the next readiness state. Actual order intent emission and
actual unlock execution remain forbidden in this proof.

Expired, consumed, or reusable unlock contexts are blocked with explicit
reasons:

- `one_shot_unlock_expired`
- `one_shot_unlock_consumed`
- `one_shot_unlock_reuse_not_allowed`

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --observe-only
```

The mock approval flag is proof input only. It does not create, consume, or
reuse a live unlock token.

## Next Readiness Layer

`AITS-ORDER-INTENT-CANDIDATE-LIVE-PREFLIGHT-READINESS-STUB-PROOF-01` adds
`aits_order_intent_live_preflight_readiness_v1` after one-shot unlock readiness.

That layer rechecks the 10,000 KRW minimum, 12,000 KRW per-order hard cap,
20,000 KRW guarded-window cap, duplicate/repeat/relock requirements,
`submitted_count=0`, `actual_order=false`, and
`final_action_unchanged=true`. It still does not call the real LivePreflight
service and does not emit an order intent.
