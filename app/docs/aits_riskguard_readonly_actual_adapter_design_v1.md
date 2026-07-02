# AITS RiskGuard Read-Only Actual Adapter Design v1

## Goal

`AITS-RISKGUARD-READONLY-ACTUAL-ADAPTER-DESIGN-REVIEW-01` defines the design
boundary for a future actual-readonly RiskGuard adapter proof.

In this document, `actual` does not mean calling RiskGuard. It means the next
proof can align the harness contract with the callable shape already present in
`app/services/risk_guard.py`, while still keeping:

- `would_call_riskguard=false`
- `risk_guard_called=false`
- `risk_decision=not_evaluated`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `submitted_count=0`

This Goal is documentation-only. It does not import RiskGuard, does not call
RiskGuard, does not call LivePreflight, does not consume unlock, and does not
reach Router, ExecutionBridge, OrderService, or OrderAdapter.

## Current Chain

The current no-call readiness chain is:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. One-shot unlock readiness stub
7. LivePreflight readiness stub
8. RiskGuard read-only adapter skeleton
9. LivePreflight read-only adapter skeleton
10. `actual_order_intent_emitted=false`
11. `submitted_count=0`

## RiskGuard Callable Inventory

Read-only inspection found these callable candidates in
`app/services/risk_guard.py`:

- `RiskGuard.evaluate_order_candidate(candidate)`
  - input: `RiskGuardInput` or `dict[str, Any]`
  - output: `RiskGuardResult`
  - observed behavior from source inspection only: pure policy evaluation
    returning `submitted=0`, `order_allowed=False`, `real_order=False`, and
    `dry_run=True`
  - side-effect risk: low by code shape, but future proof must still treat
    callable invocation as prohibited until explicitly scoped
- `evaluate_order_candidate(candidate)`
  - module-level wrapper that instantiates `RiskGuard` and calls
    `RiskGuard.evaluate_order_candidate`
  - future proof should not use this wrapper before the call boundary is
    explicitly approved, because instantiation plus evaluation is still an
    actual RiskGuard call
- `build_risk_guard_input_from_action(action, context=None)`
  - input: action-like object plus optional context dict
  - output: `RiskGuardInput`
  - observed behavior from source inspection only: data shaping helper
  - future proof may reference its field contract, but must not call it unless a
    later Goal explicitly allows an actual-readonly callable-boundary test
- `RiskGuard.log_summary(result, candidate)`
  - input: `RiskGuardResult` plus candidate input
  - output: string summary
  - must not be used as proof of safety and must not be used to open any order
    path

No callable may be invoked in this design review.

## Callable Classification

`RiskGuard.evaluate_order_candidate` appears to be a pure validation function by
source shape: it works from dataclass/dict input, builds checks, and returns a
dataclass result. It does not visibly import order services, exchange clients,
repositories, UI objects, or providers.

The future proof must still classify every callable before use:

- pure validation function or not
- state mutation possible or not
- order or execution layer reachable or not
- external API reachable or not
- log-only helper or not
- exception path can open order flow or not
- result type: dict, dataclass, or object

## Future Input Contract

Future schema:

`aits_riskguard_readonly_actual_adapter_input_v1`

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
- `live_preflight_readiness`
- `riskguard_adapter_ready`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `order_context`
- `portfolio_context`
- `guarded_window_context`
- `duplicate_relock_context`

The input must not include executable callbacks, service instances, exchange
clients, API keys, raw provider payloads, or raw exchange responses.

## Future Output Contract

Future schema:

`aits_riskguard_readonly_actual_adapter_output_v1`

Required fields:

- `schema`
- `adapter_mode=actual_readonly_design`
- `would_call_riskguard=false`
- `risk_guard_called=false`
- `future_would_call_riskguard=design_only`
- `risk_decision=not_evaluated`
- `risk_result_present=false`
- `risk_guard_callable_identified`
- `risk_guard_input_contract_ready`
- `risk_guard_output_contract_ready`
- `risk_guard_call_boundary_defined`
- `risk_guard_side_effect_boundary_defined`
- `risk_guard_mutation_forbidden=true`
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
- `live_preflight_readiness_not_ready`
- `riskguard_adapter_not_ready`
- `actual_order_flag_detected`
- `actual_emit_detected`
- `risk_guard_side_effect_unknown`
- `risk_guard_callable_not_identified`

## Side-Effect Boundary

The future proof must keep these actions forbidden:

- order creation
- order emit
- submitted increment
- unlock consume
- actual LivePreflight call
- ExecutionBridge call
- OrderService call
- OrderAdapter call
- Upbit private API call
- provider external call
- Managed Pool mutation
- runtime state mutation
- execution mode mutation
- final action mutation

## Final Sequence

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

The RiskGuard actual-readonly proof must remain before LivePreflight
actual-readonly proof. Actual unlock consumption remains final-boundary
behavior and is not part of either read-only adapter proof.

## Next Goal

Recommended next Goal:

`AITS-RISKGUARD-READONLY-ACTUAL-ADAPTER-PROOF-01`

Only that Goal may consider adding a harness actual-readonly proof mode. Even
then, the safe default remains:

- `would_call_riskguard=false`
- `risk_guard_called=false`
- `risk_decision=not_evaluated`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `submitted_count=0`
- no Router, LivePreflight, unlock, ExecutionBridge, OrderService, OrderAdapter,
  exchange, or provider calls

After the RiskGuard actual-readonly proof is complete, the adjacent design step
is:

`AITS-LIVE-PREFLIGHT-READONLY-ACTUAL-ADAPTER-DESIGN-REVIEW-01`

That design step documents LivePreflight callable shape and side-effect
boundaries only. It still must not import or call LivePreflight, RiskGuard,
Router, unlock, ExecutionBridge, OrderService, or OrderAdapter.

## Proof Implementation

`AITS-RISKGUARD-READONLY-ACTUAL-ADAPTER-PROOF-01` implements this boundary in
the runtime smoke harness only. It adds:

- `riskguard-readonly-actual-adapter-fixture-proof`
- `riskguard-readonly-actual-adapter-live-proof`
- `_build_riskguard_readonly_actual_adapter_input_v1`
- `_evaluate_riskguard_readonly_actual_adapter_contract_v1`
- `_validate_riskguard_readonly_actual_adapter_contract_v1`

The proof uses static callable-contract names only. It does not import
`app.services.risk_guard`, does not instantiate `RiskGuard`, and does not call
`RiskGuard.evaluate_order_candidate`, the module-level
`evaluate_order_candidate`, or `build_risk_guard_input_from_action`.

The proof output schema is `aits_riskguard_readonly_actual_adapter_contract_v1`.
`actual_readonly_adapter_ready=true` means only that the candidate and static
callable contract are shaped for a future explicitly-scoped RiskGuard boundary
test. It is not a RiskGuard decision and it is not live-order permission.

Required invariant fields remain:

- `adapter_mode=actual_readonly_contract`
- `would_call_riskguard=false`
- `risk_guard_called=false`
- `risk_decision=not_evaluated`
- `risk_result_present=false`
- `risk_guard_reachable=false`
- `live_preflight_called=false`
- `order_service_reachable=false`
- `order_adapter_reachable=false`
- `execution_bridge_reachable=false`
- `unlock_consumed=false`
- `submitted_count=0`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `provider_external_call_count=0`
