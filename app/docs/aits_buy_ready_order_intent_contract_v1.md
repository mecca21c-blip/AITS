# AITS Buy Ready Order Intent Contract v1

## Scope

`Buy Ready` is a Basic calculation/display state. It is not an order signal and
does not call DecisionRouter, RiskGuard, LivePreflight, ExecutionBridge,
OrderAdapter, or OrderService by itself.

An `order_intent_candidate` is a separate observe-only contract result. It may
only be emitted as a report field in this proof. It must not be sent to
DecisionRouter or any order path in this Goal.

## Contract Schema

`aits_order_intent_candidate_contract_v1`

Required report fields:

- `symbol`
- `score`
- `source`
- `basic_buy_ready`
- `ai_opinion_status`
- `freshness`
- `market_feed_ok`
- `duplicate_block`
- `repeat_block`
- `holding_state`
- `dust_state`
- `would_promote_to_order_intent`
- `block_reasons`
- `actual_order_intent_emitted=false`
- `decision_router_called=false`
- `risk_guard_called=false`
- `live_preflight_called=false`
- `order_service_called=false`
- `actual_order=false`

## Minimum Observe-Only Conditions

A Basic `Buy Ready` row may be reported as
`would_promote_to_order_intent=true` only when all of these are true:

- symbol is present
- score is at or above the configured order-intent minimum score
- source is allowed by the contract policy
- market feed is healthy
- AI opinion/status is present and not data-insufficient
- freshness is not stale, missing, analysis-required, or manual-required
- duplicate/repeat blocks are absent
- holding/dust state does not block the row

Even when the contract reports `would_promote_to_order_intent=true`, this Goal
keeps `actual_order_intent_emitted=false`. Real order-intent emission and
DecisionRouter/RiskGuard/Execution wiring require a separate high-risk Goal.

## Fresh Opinion Unblock Proof

`AITS-BUY-READY-AI-OPINION-FRESHNESS-UNBLOCK-PROOF-01` verifies the missing
AI-opinion/freshness side of the contract with a mock/LOCAL-only payload. The
proof may inject an in-memory `managed_pool_ai_opinion_v1` context with:

- `provider=local`
- `source=manual_ai_refresh_mock`
- `status_label=매수대기`
- `freshness=fresh_manual_refresh`
- `order_execution=false`
- `final_action_unchanged=true`
- `actual_order=false`

If the Basic row already satisfies the other contract conditions, this mock
context may make `would_promote_to_order_intent=true`. This is still only a
report result. The proof must keep `actual_order_intent_emitted=false`,
`decision_router_called=false`, `risk_guard_called=false`,
`live_preflight_called=false`, and `order_service_called=false`.

## Current Policy Notes

For this proof, `basic`, `basic_added`, and `user_added` are allowed sources for
observe-only evaluation. `system_seed` rows are protected/default rows and are
not promoted by this contract unless a later policy Goal explicitly changes
that behavior.
