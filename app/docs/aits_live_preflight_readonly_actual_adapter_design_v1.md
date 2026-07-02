# AITS LivePreflight Read-Only Actual Adapter Design v1

## Goal

`AITS-LIVE-PREFLIGHT-READONLY-ACTUAL-ADAPTER-DESIGN-REVIEW-01` defines the
design boundary for a future actual-readonly LivePreflight adapter proof.

In this document, `actual` does not mean calling LivePreflight. It means a later
proof can align the harness contract with the callable shape already present in
`app/services/live_order_preflight.py`, while still keeping:

- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `live_preflight_decision=not_evaluated`
- `live_preflight_result_present=false`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `submitted_count=0`

This Goal is documentation-only. It does not import LivePreflight, does not call
LivePreflight, does not call RiskGuard, does not consume unlock, and does not
reach Router, ExecutionBridge, OrderService, or OrderAdapter.

## Current Chain

The current no-call readiness chain is:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. One-shot unlock readiness
7. LivePreflight readiness stub
8. RiskGuard read-only adapter skeleton
9. RiskGuard actual-readonly adapter proof
10. LivePreflight read-only adapter skeleton
11. `actual_order_intent_emitted=false`
12. `submitted_count=0`

## LivePreflight Callable Inventory

Read-only inspection found these callable candidates in
`app/services/live_order_preflight.py`:

- `LiveOrderPreflight.evaluate(data)`
  - input: `LiveOrderPreflightInput` or `dict[str, Any]`
  - output: `LiveOrderPreflightResult`
  - observed behavior from source inspection only: pure preflight-condition
    evaluation returning `submitted=0`, `order_allowed=False`,
    `real_order=False`, and `execution_mode` copied from input
  - side-effect risk: low by code shape, but future proof must still treat
    callable invocation as prohibited until explicitly scoped
- `evaluate_live_order_preflight(data)`
  - module-level wrapper that instantiates `LiveOrderPreflight` and calls
    `LiveOrderPreflight.evaluate`
  - future proof must not use this wrapper before the call boundary is
    explicitly approved, because instantiation plus evaluation is still an
    actual LivePreflight call
- `build_preflight_input_from_order_request(order_request, request_id,
  execution_mode, risk_guard)`
  - input: order-request dict plus risk/preflight context
  - output: `LiveOrderPreflightInput`
  - observed behavior from source inspection only: data shaping helper
  - future proof may reference its field contract, but must not call it unless a
    later Goal explicitly allows an actual-readonly callable-boundary test
- `LiveOrderPreflight.log_summary(result, data)`
  - input: `LiveOrderPreflightResult` plus candidate input
  - output: string summary
  - must not be used as proof of safety and must not be used to open any order
    path

No callable may be invoked in this design review.

## Callable Classification

`LiveOrderPreflight.evaluate` appears to be a pure validation function by source
shape: it coerces dataclass/dict input, computes missing conditions, and returns
a dataclass result. It does not visibly import order services, exchange clients,
repositories, UI objects, or providers.

The future proof must still classify every callable before use:

- pure validation function or not
- state mutation possible or not
- order or execution layer reachable or not
- Upbit private API or order API reachable or not
- provider/API reachable or not
- log-only helper or not
- exception path can open order flow or not
- result type: dict, dataclass, or object

## Future Input Contract

Future schema:

`aits_live_preflight_readonly_actual_adapter_input_v1`

Required fields:

- `schema`
- `target_symbol`
- `source`
- `intended_side`
- `intended_amount_krw`
- `min_order_krw=10000`
- `per_order_hard_cap_krw=12000`
- `total_guarded_window_cap_krw=20000`
- `submitted_count`
- `session_approved_symbols`
- `ai_opinion_freshness_status`
- `source_policy_ready`
- `router_validation_payload_ready`
- `one_shot_unlock_ready`
- `riskguard_adapter_ready`
- `riskguard_actual_readonly_adapter_ready`
- `live_preflight_readiness`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `order_context`
- `portfolio_context`
- `balance_context`
- `market_context`
- `guarded_window_context`
- `duplicate_relock_context`

The input must not include executable callbacks, service instances, exchange
clients, API keys, raw provider payloads, raw exchange responses, unlock tokens
that can be consumed, or mutable runtime objects.

## Future Output Contract

Future schema:

`aits_live_preflight_readonly_actual_adapter_output_v1`

Required fields:

- `schema`
- `adapter_mode=actual_readonly_design`
- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `future_would_call_live_preflight=design_only`
- `live_preflight_decision=not_evaluated`
- `live_preflight_result_present=false`
- `live_preflight_callable_identified`
- `live_preflight_input_contract_ready`
- `live_preflight_output_contract_ready`
- `live_preflight_call_boundary_defined`
- `live_preflight_side_effect_boundary_defined`
- `live_preflight_mutation_forbidden=true`
- `risk_guard_called=false`
- `order_service_reachable=false`
- `order_adapter_reachable=false`
- `execution_bridge_reachable=false`
- `unlock_consumed=false`
- `submitted_count=0`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `provider_external_call_count=0`
- `blockers`
- `warnings`

## Blockers

The future actual-readonly adapter proof must keep these blockers:

- `intended_amount_below_min_order`
- `intended_amount_exceeds_per_order_hard_cap`
- `total_guarded_window_cap_exceeded`
- `submitted_count_not_zero`
- `user_added_not_session_approved`
- `stale_or_missing_ai_opinion`
- `router_validation_payload_not_ready`
- `source_policy_not_ready`
- `one_shot_unlock_not_ready`
- `riskguard_adapter_not_ready`
- `riskguard_actual_readonly_adapter_not_ready`
- `live_preflight_readiness_not_ready`
- `actual_order_flag_detected`
- `actual_emit_detected`
- `live_preflight_side_effect_unknown`
- `live_preflight_callable_not_identified`
- `live_preflight_input_contract_not_ready`
- `live_preflight_output_contract_not_ready`
- `live_preflight_call_boundary_not_defined`

## Side-Effect Boundary

The future proof must keep these actions forbidden:

- order creation
- order emit
- submitted increment
- unlock consume
- actual RiskGuard call
- ExecutionBridge call
- OrderService call
- OrderAdapter call
- Upbit private API call
- provider external call
- Managed Pool mutation
- runtime state mutation
- balance mutation
- order state mutation
- execution mode mutation
- final action mutation

## RiskGuard and LivePreflight Order

RiskGuard actual-readonly proof comes first. LivePreflight actual-readonly proof
comes next. Neither result is order permission and neither result is an actual
service call. Unlock consumption remains final-boundary behavior and must not
occur during read-only adapter proof.

The recommended live-order sequence remains:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. RiskGuard read-only actual adapter proof
7. LivePreflight read-only actual adapter proof
8. One-shot unlock final confirmation
9. Duplicate/repeat/relock final check
10. ExecutionBridge
11. OrderService
12. OrderAdapter
13. Exchange response reconciliation

## Next Goal

Recommended next Goal:

`AITS-LIVE-PREFLIGHT-READONLY-ACTUAL-ADAPTER-PROOF-01`

Only that Goal may consider adding a harness actual-readonly proof mode. Even
then, the safe default remains:

- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `live_preflight_decision=not_evaluated`
- `live_preflight_result_present=false`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `submitted_count=0`
- no RiskGuard, unlock, ExecutionBridge, OrderService, OrderAdapter, exchange,
  or provider calls
