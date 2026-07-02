# AITS RiskGuard Read-Only Adapter Contract v1

## Goal

`aits_riskguard_readonly_adapter_contract_v1` defines the design boundary for a
future RiskGuard read-only adapter. The adapter prepares and validates the shape
of the payload that RiskGuard would eventually evaluate, without calling
RiskGuard or any execution path.

This is a design contract only. It does not call RiskGuard, does not call
LivePreflight, does not execute or consume a one-shot unlock, does not emit an
order intent, and does not call DecisionRouter, ExecutionBridge, OrderService,
or OrderAdapter.

## Current Readiness Chain

The current no-call chain is:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. One-shot unlock readiness stub
7. LivePreflight readiness stub
8. LivePreflight read-only adapter skeleton

Current proof states remain inert:

- `actual_order=false`
- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `unlock_consumed=false`
- `submitted_count=0`
- `provider_external_call_count=0`

## Adapter Purpose

The RiskGuard read-only adapter may:

- normalize an order-intent candidate into a RiskGuard-preview input
- verify required fields and safety flags before any actual RiskGuard call
- report blockers and warnings that would prevent a future RiskGuard evaluation
- keep the candidate disconnected from Router, LivePreflight, unlock, and order
  services

The adapter must not:

- import or call `app/services/risk_guard.py`
- instantiate `RiskGuard`
- call `RiskGuard.evaluate_order_candidate`
- call LivePreflight
- call DecisionRouter
- call ExecutionBridge, OrderService, or OrderAdapter
- consume a one-shot unlock
- emit an actual order intent
- place, cancel, sell, retry, or submit an order

## Input Schema

The adapter input should be named
`aits_riskguard_readonly_adapter_input_v1`.

Required fields:

- `schema`
- `symbol`
- `side`
- `source`
- `managed_source`
- `session_approved_symbols`
- `intended_amount_krw`
- `min_order_krw`
- `per_order_hard_cap_krw`
- `total_window_cap_krw`
- `total_window_after_candidate_krw`
- `basic_score`
- `ai_opinion`
- `ai_freshness`
- `source_policy_ready`
- `router_validation_payload_ready`
- `one_shot_unlock_ready`
- `live_preflight_readiness`
- `live_preflight_adapter_ready`
- `duplicate_guard_required`
- `repeat_guard_required`
- `relock_required`
- `submitted_count`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `final_action_unchanged=true`
- `validation_only=true`

The input must not include API keys, raw provider payloads, raw exchange
responses, executable callbacks, order-service instances, or adapter instances
that can reach the exchange.

## Output Schema

The adapter output should be named
`aits_riskguard_readonly_adapter_contract_v1`.

Required fields:

- `schema`
- `riskguard_adapter_ready`
- `adapter_mode=readonly_contract`
- `would_call_riskguard=false`
- `risk_guard_called=false`
- `risk_decision=not_evaluated`
- `risk_blockers`
- `risk_warnings`
- `required_next_goal`
- `live_preflight_called=false`
- `would_call_live_preflight=false`
- `order_service_reachable=false`
- `order_adapter_reachable=false`
- `unlock_consumed=false`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `submitted=0`
- `submitted_count=0`
- `provider_external_call_count=0`
- `managed_pool_mutation=false`
- `order_risk_detected=false`

`riskguard_adapter_ready=true` means only that the read-only adapter contract has
enough data for a future RiskGuard preview. It is not a RiskGuard pass, not a
live-order permission, and not permission to call LivePreflight or order
services.

## Required Risk Checks

A future RiskGuard read-only adapter must block or warn unless these conditions
are true:

1. `intended_amount_krw >= 10000`
2. `intended_amount_krw <= 12000`
3. `total_window_after_candidate_krw <= 20000`
4. `submitted_count == 0`
5. `duplicate_guard_required=true`
6. `repeat_guard_required=true`
7. `relock_required=true`
8. `source_policy_ready=true`
9. `router_validation_payload_ready=true`
10. `source=user_added` requires exact `session_approved_symbols` match
11. AI opinion freshness is acceptable, not stale or missing
12. `actual_order=false`
13. `actual_order_intent_emitted=false`
14. `final_action_unchanged=true`
15. `order_service_reachable=false`
16. `order_adapter_reachable=false`
17. `unlock_consumed=false`
18. `provider_external_call_count=0`
19. `managed_pool_mutation=false`

The adapter may carry `one_shot_unlock_ready=true` as a readiness fact, but it
must still keep `unlock_consumed=false`.

## Final Sequence

The recommended live-order sequence remains:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. RiskGuard read-only validation
7. LivePreflight read-only validation
8. One-shot unlock final confirmation
9. Duplicate/repeat/relock final check
10. ExecutionBridge
11. OrderService
12. OrderAdapter
13. Exchange response reconciliation

The earlier stubs can check one-shot unlock readiness before LivePreflight
readiness because they are inert proof payloads. Actual unlock consumption must
remain final-boundary behavior after Router, RiskGuard, LivePreflight, and
duplicate/repeat/relock checks are fresh.

## Risk Register

- A read-only adapter accidentally imports and calls the real RiskGuard service.
- RiskGuard adapter readiness is misunderstood as a RiskGuard pass.
- A future RiskGuard pass is misunderstood as order permission.
- LivePreflight readiness is confused with an actual LivePreflight call.
- One-shot unlock readiness is confused with unlock consumption.
- Duplicate, repeat, or relock final checks are skipped.
- `submitted_count` is stale.
- `user_added` session approval is interpreted too broadly.
- Stale AI opinion remains eligible for a live candidate.
- 10,000 / 12,000 / 20,000 KRW caps are bypassed.
- OrderService or OrderAdapter becomes reachable from a validation-only path.

## Next Implementation Goal

The next implementation should be limited to:

`AITS-RISKGUARD-READONLY-ADAPTER-SKELETON-PROOF-01`

That Goal may add a harness-only skeleton adapter and proof payload, but it must
still keep `would_call_riskguard=false`, `risk_guard_called=false`,
`would_call_live_preflight=false`, `live_preflight_called=false`,
`unlock_consumed=false`, `actual_order_intent_emitted=false`,
`actual_order=false`, and `submitted=0`.
