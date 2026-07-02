# AITS Order Intent Source Live Policy v1

This document is a read-only policy decision for the step after
`aits_order_intent_router_validation_stub_v1`. It does not implement live
emission, call DecisionRouter, call RiskGuard, call LivePreflight, call
OrderService, or place orders.

## Policy Schema

Schema name: `aits_order_intent_source_live_policy_v1`

Fields for the next proof:

- `symbol`
- `source`
- `source_policy_ready`
- `source_policy_mode`
- `session_approved_symbols`
- `source_allowed_for_live_intent`
- `policy_warnings`
- `policy_blockers`
- `requires_session_symbol_approval`
- `requires_one_shot_unlock`
- `actual_order=false`
- `actual_order_intent_emitted=false`

## Source Policy Table

| Source | Default live intent candidate policy | Required approval | Blocker or warning |
| --- | --- | --- | --- |
| `user_added` | Block by default | `session_approved_symbols` must contain the exact symbol | Missing approval becomes `user_added_not_session_approved`; approved symbols may clear `user_added_requires_live_policy_confirmation` |
| `basic_added` | Allow only after all candidate/readiness/stub checks pass | No source-specific session approval in v1 | No source warning by default |
| `system_seed` | Separate policy required before live intent | Future explicit seed policy | `system_seed_live_policy_unconfirmed` |
| `holding` / `holding_display` | Do not create buy intent by source alone | Future holding-specific policy | `holding_source_buy_intent_unconfirmed` |
| `holding_eligible` | Rotation/sell-side policy is separate | Future rotation policy | `holding_eligible_live_policy_unconfirmed` |
| `trade_hold` / `manual_hold` | Block | Manual release required | `trade_hold_blocks_live_intent` |
| `dust` | Block buy/rotation by default | Future dust policy only | `dust_holding_blocks_live_intent` |
| `unknown` | Block | Source normalization required | `unknown_source_blocks_live_intent` |

## user_added Decision

`user_added` must not be globally allowed for the first live Step1 order-intent
path. User-added rows can contain watchlist intent, experiments, or manual
interest that should not automatically become live order candidates.

The approved policy is symbol-scoped:

- If `source=user_added` and the symbol is not in `session_approved_symbols`,
  the next policy-aware proof must set
  `policy_blocker=user_added_not_session_approved`.
- If `source=user_added` and the symbol is in `session_approved_symbols`, the
  source policy can become ready for that symbol only. Other gates still apply.
- Approval does not bypass Basic Buy Ready, fresh AI opinion, freshness,
  Router validation stub readiness, amount caps, one-shot unlock,
  duplicate/repeat guards, relock, or final preflight checks.

Example:

```json
{
  "schema": "aits_order_intent_source_live_policy_v1",
  "symbol": "KRW-PYTH",
  "source": "user_added",
  "source_policy_mode": "session_symbol_approval",
  "session_approved_symbols": ["KRW-PYTH"],
  "source_allowed_for_live_intent": true,
  "requires_session_symbol_approval": true,
  "requires_one_shot_unlock": true,
  "actual_order": false,
  "actual_order_intent_emitted": false
}
```

Without that explicit symbol approval, `KRW-PYTH` remains blocked by
`user_added_not_session_approved` even if
`router_validation_payload_ready=true`.

## Required Live Gates Remain

For an approved symbol, all of these must still be true before any future live
handoff Goal can be considered:

- Basic Buy Ready
- Fresh AI opinion
- Freshness OK
- `router_validation_payload_ready=true`
- `intended_amount_krw >= 10000`
- `intended_amount_krw <= 12000`
- guarded-window total cap `<= 20000`
- one-shot unlock required and separately satisfied
- duplicate guard required
- repeat guard required
- relock required
- `actual_order=false` through the next proof boundary

## Explicit Non-Goals

This policy review does not permit:

- actual order-intent emission
- DecisionRouter call
- RiskGuard call
- LivePreflight call
- OrderService or OrderAdapter call
- ExecutionBridge change
- provider external call
- real order

## Stub Proof Result

Completed implementation proof:

`AITS-ORDER-INTENT-CANDIDATE-SOURCE-LIVE-POLICY-STUB-PROOF-01`

That Goal adds a read-only evaluator for
`aits_order_intent_source_live_policy_v1`.

Proof expectations:

- `source=user_added`, `session_approved_symbols=[]`:
  `source_policy_ready=false`, `policy_blockers` contains
  `user_added_not_session_approved`, and the Router validation payload is not
  ready for live handoff.
- `source=user_added`, `session_approved_symbols=["KRW-PYTH"]`:
  `source_policy_ready=true`, `policy_blockers=[]`, the
  `user_added_requires_live_policy_confirmation` warning is removed for that
  symbol, and the Router validation payload can remain ready.
- In both cases, `actual_order_intent_emitted=false`, all Router/Risk/Preflight
  and Order call flags remain false, and `submitted_count=0`.

## One-Shot Unlock Readiness

`AITS-ORDER-INTENT-CANDIDATE-ONE-SHOT-UNLOCK-READINESS-STUB-PROOF-01`
adds the next read-only contract:
`aits_order_intent_one_shot_unlock_readiness_v1`.

Source policy readiness alone is not live order readiness. A future live path
also needs exact one-shot unlock readiness for the same symbol. The proof uses
mock unlock context only and keeps actual unlock execution, order intent
emission, Router, RiskGuard, LivePreflight, OrderService, OrderAdapter, and real
orders disabled.

## LivePreflight Readiness Stub

`AITS-ORDER-INTENT-CANDIDATE-LIVE-PREFLIGHT-READINESS-STUB-PROOF-01` adds
`aits_order_intent_live_preflight_readiness_v1` after one-shot unlock readiness.

That proof rechecks minimum order amount, per-order cap, guarded-window cap,
duplicate/repeat/relock requirements, `submitted_count=0`,
`actual_order=false`, and `final_action_unchanged=true` without calling the
real LivePreflight service.
