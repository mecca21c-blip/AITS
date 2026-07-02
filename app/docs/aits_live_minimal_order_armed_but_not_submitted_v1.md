# AITS Live Minimal Order Armed But Not Submitted v1

## Goal

`AITS-LIVE-MINIMAL-ORDER-ARMED-BUT-NOT-SUBMITTED-01` is the last
read-only readiness step before a separately approved 10,000 KRW one-shot live
order test.

This proof creates an armed report only. It does not submit an order, emit an
order intent, consume an unlock token, or call Router, RiskGuard,
LivePreflight, ExecutionBridge, OrderService, or OrderAdapter.

## Proof Modes

- `live-minimal-order-armed-fixture-proof`
- `live-minimal-order-armed-live-proof`

Both modes produce `aits_live_minimal_order_armed_contract_v1` reports with
`armed_mode=not_submitted`.

## Helper Owners

- `_build_live_minimal_order_armed_input_v1`
- `_evaluate_live_minimal_order_armed_contract_v1`
- `_validate_live_minimal_order_armed_contract_v1`

All helpers live in `tools/runtime_smoke/aits_qt_smoke_harness.py`.

## Input Schema

`aits_live_minimal_order_armed_input_v1`

Key fields:

- `target_symbol`
- `source`
- `intended_side`
- `intended_amount_krw`
- `required_amount_krw=10000`
- `min_order_krw=10000`
- `per_order_hard_cap_krw=12000`
- `total_guarded_window_cap_krw=20000`
- `submitted_count`
- `session_approved_symbols`
- `live_order_final_gate_ready`
- `final_confirmation_ready`
- `duplicate_repeat_relock_ready`
- `final_emit_gate_ready`
- `live_minimal_order_readiness_ready`
- `riskguard_actual_readonly_adapter_ready`
- `live_preflight_actual_readonly_adapter_ready`
- `one_shot_unlock_ready`
- `unlock_token_present_or_mocked`
- `unlock_scope_symbol`
- `unlock_scope_side`
- `unlock_scope_amount_krw`
- `unlock_expiry_status`
- `operator_confirm_required=true`
- `operator_confirm_phrase`
- `expected_confirm_phrase`

Safety fields must remain false or zero:

- `actual_order=false`
- `actual_order_intent_emitted=false`
- `would_emit_order_intent=false`
- `order_intent_emitted=false`
- `would_consume_unlock=false`
- `unlock_consumed=false`
- `provider_external_call_count=0`

## Output Schema

`aits_live_minimal_order_armed_contract_v1`

Key fields:

- `live_minimal_order_armed`
- `armed_mode=not_submitted`
- `next_allowed_goal=AITS-LIVE-MINIMAL-ORDER-10000KRW-ONE-SHOT-TEST-01`
- `operator_confirm_required=true`
- `expected_confirm_phrase`
- `operator_confirm_phrase_matched`
- `final_gate_passed`
- `amount_locked_to_10000`
- `caps_validated`
- `source_policy_validated`
- `riskguard_readonly_validated`
- `live_preflight_readonly_validated`
- `unlock_final_confirmation_validated`
- `duplicate_repeat_relock_validated`
- `final_emit_gate_validated`
- `blockers`
- `warnings`
- `safety_summary`

## Confirm Phrase Policy

The expected phrase is generated from the target symbol, side, and amount:

`AITS LIVE ORDER KRW-PYTH BUY 10000`

The armed proof requires an exact match. If the phrase is missing or mismatched,
`live_minimal_order_armed=false`.

This phrase does not authorize an order in this Goal. It only proves the next
Goal has a precise operator confirmation contract.

## Armed Meaning

`live_minimal_order_armed=true` means:

- the final gate integration proof is ready
- the amount is exactly 10,000 KRW
- all caps are still valid
- the target is session approved
- read-only RiskGuard and LivePreflight readiness are validated
- one-shot unlock final confirmation is valid in the report
- duplicate, repeat, and relock checks are ready
- the operator confirmation phrase matches

It does not mean:

- an order was submitted
- an order intent was emitted
- an unlock token was consumed
- Router, RiskGuard, LivePreflight, ExecutionBridge, OrderService, or
  OrderAdapter were called

## Blockers

The contract blocks armed readiness on:

- `target_symbol_missing`
- `intended_side_not_buy`
- `intended_amount_not_10000`
- `intended_amount_below_min_order`
- `intended_amount_exceeds_per_order_hard_cap`
- `total_guarded_window_cap_exceeded`
- `submitted_count_not_zero`
- `user_added_not_session_approved`
- `live_order_final_gate_not_ready`
- `final_confirmation_not_ready`
- `duplicate_repeat_relock_not_ready`
- `final_emit_gate_not_ready`
- `live_minimal_order_readiness_not_ready`
- `riskguard_actual_readonly_adapter_not_ready`
- `live_preflight_actual_readonly_adapter_not_ready`
- `one_shot_unlock_not_ready`
- `unlock_token_missing`
- `unlock_scope_symbol_mismatch`
- `unlock_scope_side_mismatch`
- `unlock_amount_scope_exceeded`
- `unlock_expired`
- `operator_confirm_phrase_missing`
- `operator_confirm_phrase_mismatch`
- `actual_order_flag_detected`
- `actual_emit_detected`
- `would_emit_order_intent_detected`
- `unlock_would_consume_detected`
- `unlock_already_consumed`
- `provider_external_call_detected`

## Safety Boundary

The proof must keep:

- `actual_order=false`
- `actual_order_intent_emitted=false`
- `would_emit_order_intent=false`
- `order_intent_emitted=false`
- `would_consume_unlock=false`
- `unlock_consumed=false`
- `unlock_service_called=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `execution_bridge_called=false`
- `order_service_called=false`
- `order_adapter_called=false`
- `provider_external_call_count=0`
- `submitted_count=0`

## Next Goal

Recommended next Goal:

`AITS-LIVE-MINIMAL-ORDER-10000KRW-ONE-SHOT-TEST-01`

Only that Goal may consider a single real 10,000 KRW order test, and only with
explicit user approval, exact confirm phrase match, fixed target symbol, fixed
amount, no retry, and no additional order.
