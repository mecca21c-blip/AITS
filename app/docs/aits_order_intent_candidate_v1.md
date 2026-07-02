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

## Router Handoff Readiness

Schema name: `aits_order_intent_router_handoff_readiness_v1`

The readiness object is read-only. It answers whether an inert candidate has the
minimum pre-handoff fields required before any future Router validation Goal.
It does not call Router.

Required checks:

- `candidate_valid`
- `actual_order_false`
- `submitted_zero`
- `order_execution_false`
- `final_action_unchanged`
- `ai_freshness_ok`
- `min_order_ok`
- `hard_cap_ok`
- `total_window_cap_ok`
- `one_shot_unlock_required`
- `one_shot_unlock_not_consumed`
- `duplicate_guard_required`
- `repeat_guard_required`
- `relock_required`
- `market_feed_ok`
- `managed_row_exists`
- `target_symbol_match`
- `no_dust_holding_conflict`
- `provider_call_not_required`
- `order_service_not_reachable`

If every check passes, the report may show `router_handoff_ready=true`. Even in
that case, these fields must remain false:

- `actual_order_intent_emitted`
- `decision_router_called`
- `risk_guard_called`
- `live_preflight_called`
- `order_service_called`
- `order_adapter_called`

Warnings are allowed for policy-sensitive states such as `user_added`, but they
must not trigger a live Router call in this proof.

## Router Validation Stub

Schema name: `aits_order_intent_router_validation_stub_v1`

The validation stub is the next read-only shape after Router handoff readiness.
It converts an inert `aits_order_intent_candidate_v1` and
`aits_order_intent_router_handoff_readiness_v1` into the payload a future Router
validation boundary could inspect. It is not a Router call.

Required payload fields:

- `candidate_schema`
- `symbol`
- `side`
- `source`
- `basic_score`
- `ai_opinion`
- `ai_freshness`
- `confidence`
- `reason`
- `intended_amount_krw`
- `min_order_krw`
- `per_order_hard_cap_krw`
- `total_window_cap_krw`
- `managed_source`
- `router_handoff_ready`
- `router_validation_payload_ready`
- `policy_warnings`
- `policy_blockers`
- `required_safety_flags`

`required_safety_flags` must keep the payload inert:

- `actual_order=false`
- `submitted=0`
- `final_action_unchanged=true`
- `order_execution=false`
- `suggestion_only=true`
- `validation_only=true`

For this proof, `user_added` remains a policy warning:
`user_added_requires_live_policy_confirmation`. Promoting that warning to a
blocker is reserved for a later live policy Goal.

## Source Live Policy Review

The source policy decision is documented in
`app/docs/aits_order_intent_source_live_policy_v1.md`.

Decision summary:

- `user_added` is not globally allowed for live order intent.
- `user_added` requires symbol-scoped session approval through
  `session_approved_symbols`.
- Without exact symbol approval, the next policy-aware proof must block with
  `user_added_not_session_approved`.
- With exact symbol approval, the source warning can be cleared for that symbol
  only; Basic Buy Ready, fresh AI opinion, freshness, validation stub readiness,
  amount caps, one-shot unlock, duplicate/repeat guards, and relock remain
  required.
- `system_seed`, `holding`, `holding_display`, `holding_eligible`,
  `trade_hold`, `dust`, and `unknown` remain separate source policies.
