# AITS Live Order Final Gate Integration Proof v1

## Goal

`AITS-LIVE-ORDER-FINAL-GATE-INTEGRATION-PROOF-01` combines the final no-call
readiness gates into a single runtime smoke contract:

1. one-shot unlock final confirmation
2. duplicate/repeat/relock final check
3. final emit gate contract
4. live minimal order readiness summary
5. pre-order GO/NO-GO decision

This proof is still read-only. It does not consume unlock, does not emit an
order intent, does not call RiskGuard or LivePreflight, does not call
DecisionRouter, ExecutionBridge, OrderService, or OrderAdapter, and does not
submit an order.

## Runtime Modes

- `live-order-final-gate-integration-fixture-proof`
- `live-order-final-gate-integration-live-proof`

Helpers:

- `_build_live_order_final_gate_integration_input_v1`
- `_evaluate_live_order_final_gate_integration_contract_v1`
- `_validate_live_order_final_gate_integration_contract_v1`

## Input Schema

Schema:

`aits_live_order_final_gate_integration_input_v1`

Required fields include:

- `target_symbol`
- `source`
- `intended_side`
- `intended_amount_krw`
- `min_order_krw=10000`
- `per_order_hard_cap_krw=12000`
- `total_guarded_window_cap_krw=20000`
- `mock_total_window_used_krw`
- `submitted_count`
- `session_approved_symbols`
- `ai_opinion_freshness_status`
- `source_policy_ready`
- `router_validation_payload_ready`
- `riskguard_actual_readonly_adapter_ready`
- `live_preflight_actual_readonly_adapter_ready`
- `one_shot_unlock_ready`
- `unlock_token_present_or_mocked`
- `unlock_scope_symbol`
- `unlock_scope_side`
- `unlock_scope_amount_krw`
- `unlock_expiry_status`
- `duplicate_check_ready`
- `repeat_check_ready`
- `relock_check_ready`
- `duplicate_order_detected=false`
- `repeat_order_detected=false`
- `relock_required=false`
- `final_emit_gate_contract_ready`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `unlock_consumed=false`
- `provider_external_call_count=0`

## Output Schema

Schema:

`aits_live_order_final_gate_integration_contract_v1`

Required fields include:

- `live_order_final_gate_ready`
- `final_gate_mode=readonly_integration_proof`
- `final_confirmation_ready`
- `duplicate_repeat_relock_ready`
- `final_emit_gate_ready`
- `live_minimal_order_readiness_ready`
- `next_allowed_goal=AITS-LIVE-MINIMAL-ORDER-ARMED-BUT-NOT-SUBMITTED-01`
- `actual_order=false`
- `actual_order_intent_emitted=false`
- `would_emit_order_intent=false`
- `order_intent_emitted=false`
- `would_consume_unlock=false`
- `unlock_consumed=false`
- `unlock_service_called=false`
- `would_call_riskguard=false`
- `risk_guard_called=false`
- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `decision_router_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `execution_bridge_called=false`
- `provider_external_call_count=0`
- `submitted_count=0`
- `managed_pool_mutation=false`
- `order_risk_detected=false`
- `blockers`
- `warnings`
- `safety_flags`

## Ready Meaning

`live_order_final_gate_ready=true` means only that the read-only final gate
contract is complete for the mock-approved valid chain. It is not an order
submission, not an order-intent emission, not unlock consumption, and not
permission to call the execution stack.

## Blockers

The proof treats these as blockers:

- `intended_amount_below_min_order`
- `intended_amount_exceeds_per_order_hard_cap`
- `total_guarded_window_cap_exceeded`
- `submitted_count_not_zero`
- `user_added_not_session_approved`
- `stale_or_missing_ai_opinion`
- `source_policy_not_ready`
- `router_validation_payload_not_ready`
- `riskguard_actual_readonly_adapter_not_ready`
- `live_preflight_actual_readonly_adapter_not_ready`
- `one_shot_unlock_not_ready`
- `unlock_token_missing`
- `unlock_scope_symbol_mismatch`
- `unlock_scope_side_mismatch`
- `unlock_amount_scope_exceeded`
- `unlock_expired`
- `duplicate_check_not_ready`
- `repeat_check_not_ready`
- `relock_check_not_ready`
- `duplicate_order_detected`
- `repeat_order_detected`
- `relock_required`
- `final_emit_gate_contract_not_ready`
- `actual_order_flag_detected`
- `actual_emit_detected`
- `unlock_already_consumed`
- `provider_external_call_detected`

Fixture proof covers at least:

- empty `session_approved_symbols`
- `intended_amount_krw=13000`
- `submitted_count=1`
- `unlock_token_present_or_mocked=false`
- `duplicate_order_detected=true`
- `final_emit_gate_contract_ready=false`

## Safety Boundary

The proof must keep:

- `actual_order=false`
- `actual_order_intent_emitted=false`
- `would_emit_order_intent=false`
- `order_intent_emitted=false`
- `would_consume_unlock=false`
- `unlock_consumed=false`
- `unlock_service_called=false`
- `would_call_riskguard=false`
- `risk_guard_called=false`
- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `decision_router_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `execution_bridge_called=false`
- `provider_external_call_count=0`
- `submitted_count=0`

## Next Goal

Recommended next Goal:

`AITS-LIVE-MINIMAL-ORDER-ARMED-BUT-NOT-SUBMITTED-01`

Only that Goal may examine an armed-but-not-submitted path. Actual submit must
still remain forbidden until a later explicitly approved one-shot live-order
test Goal.

That armed-but-not-submitted step must keep the same final gate readiness as
input, add the exact operator confirm phrase contract, lock the intended amount
to 10,000 KRW, and still keep `actual_order=false`, `would_emit_order_intent=false`,
`would_consume_unlock=false`, `unlock_consumed=false`, and `submitted_count=0`.
