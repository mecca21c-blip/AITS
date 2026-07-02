# AITS Order Intent Candidate v1

## Scope

`aits_order_intent_candidate_v1` is an inert bridge object. It can be built from
an observe-only `would_promote_to_order_intent=true` contract result, but it is
not an emitted trading intent and is not an exchange order.

This object must not call DecisionRouter, RiskGuard, LivePreflight,
ExecutionBridge, OrderService, or OrderAdapter by itself.

## Required Fields

- `schema=aits_order_intent_candidate_v1`
- `symbol`
- `side=buy`
- `source=basic_buy_ready_ai_confirmed`
- `basic_score`
- `ai_opinion`
- `ai_freshness`
- `confidence`
- `reason`
- `intended_amount_krw`
- `min_order_krw=10000`
- `per_order_hard_cap_krw=12000`
- `total_window_cap_krw=20000`
- `managed_source`
- `holding_state`
- `dust_state`
- `duplicate_guard_required=true`
- `repeat_guard_required=true`
- `relock_required=true`
- `risk_guard_required=true`
- `preflight_required=true`
- `one_shot_unlock_required=true`
- `actual_order=false`
- `submitted=0`
- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `order_service_called=false`
- `order_adapter_called=false`

## Inert Builder Policy

The first proof owner is the runtime smoke harness helper:

`tools/runtime_smoke/aits_qt_smoke_harness.py::_build_inert_order_intent_candidate_v1`

The helper may create a candidate only when:

- `would_promote_to_order_intent=true`
- symbol is present
- intended amount is at least `10000` KRW
- intended amount is not above `12000` KRW

The helper returns build errors instead of creating a candidate when those
conditions are missing.

## Validation Policy

`_validate_inert_order_intent_candidate_v1` checks that all safety flags remain
inert and that the hard caps are present. A valid candidate still does not emit
anything.

Valid proof output must keep:

- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `provider_external_call_count=0`
- `submitted_count=0`

## Next Boundary

The next live-facing Goal may shape a candidate into a gated intent only after
separate review. Router, RiskGuard, Preflight, unlock, and OrderService wiring
remain out of scope for this schema proof.
