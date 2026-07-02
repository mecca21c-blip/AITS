# AITS Order Intent LivePreflight Readiness v1

`aits_order_intent_live_preflight_readiness_v1` is a read-only contract after
source policy readiness, Router validation payload readiness, and one-shot
unlock readiness.

It does not call `LivePreflight`, does not call DecisionRouter, RiskGuard,
OrderService, OrderAdapter, or ExecutionBridge, and does not emit an order
intent.

## Required Checks

- `source_policy_ready=true`
- `router_validation_payload_ready=true`
- `one_shot_unlock_ready=true`
- `live_order_readiness=true`
- `intended_amount_krw >= 10000`
- `intended_amount_krw <= 12000`
- `total_window_after_candidate_krw <= 20000`
- `duplicate_guard_required=true`
- `repeat_guard_required=true`
- `relock_required=true`
- `submitted_count=0`
- `actual_order=false`
- `final_action_unchanged=true`

## Schema

Required report fields:

- `schema=aits_order_intent_live_preflight_readiness_v1`
- `symbol`
- `side`
- `source`
- `source_policy_ready`
- `router_validation_payload_ready`
- `one_shot_unlock_required`
- `one_shot_unlock_ready`
- `live_order_readiness`
- `live_preflight_readiness`
- `live_preflight_required`
- `min_order_krw`
- `per_order_hard_cap_krw`
- `total_window_cap_krw`
- `intended_amount_krw`
- `total_window_after_candidate_krw`
- `duplicate_guard_required`
- `repeat_guard_required`
- `relock_required`
- `submitted_count`
- `policy_warnings`
- `policy_blockers`
- `checks`
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

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --observe-only
```

The readiness result is not execution permission. Even when
`live_preflight_readiness=true`, actual order intent emission and the real
LivePreflight call remain forbidden until a separate Goal explicitly changes
that boundary.

## Actual Read-Only Adapter Design Boundary

The design review for the future actual read-only adapter is documented in
`app/docs/aits_live_preflight_readonly_adapter_contract_v1.md`.

The adapter contract is intentionally separate from this readiness stub:

- readiness proves the candidate has enough no-call preconditions for a future
  preflight preview;
- the read-only adapter may only normalize and inspect the future preflight
  request shape;
- it must keep `would_call_live_preflight=false`,
  `live_preflight_called=false`, `unlock_consumed=false`,
  `actual_order_intent_emitted=false`, `actual_order=false`, and `submitted=0`.

`live_preflight_readiness=true` remains a proof state only. It is not order
permission and must not make OrderService or OrderAdapter reachable.
