# AITS Order Intent Emit Gate Design v1

## Goal

This document defines the read-only design contract for the bridge between
`would_promote_to_order_intent=true` and any future real order-intent emission.

This is not an implementation Goal. It does not emit an order intent, call
DecisionRouter, call RiskGuard, call LivePreflight, call ExecutionBridge, call
OrderService, or place an order.

## Current Contract State

Basic `Buy Ready` is a calculation/display state owned by the Basic candidate
and Managed Pool status flow. It is not an order signal.

`AITS-BUY-READY-ORDER-INTENT-GATE-CONTRACT-PROOF-01` separated Basic
`Buy Ready` from `order_intent_candidate`.

`AITS-BUY-READY-AI-OPINION-FRESHNESS-UNBLOCK-PROOF-01` verified that a Basic
Buy Ready row can reach `would_promote_to_order_intent=true` when fresh AI
opinion/freshness is present:

- target symbol: `KRW-PYTH`
- score: `64.0`
- source: `user_added`
- before blocks: `ai_opinion_missing`, `freshness_not_acceptable:missing`
- injected opinion: `buy_wait` / buy-wait status
- injected freshness: `fresh_manual_refresh`
- after result: `would_promote_to_order_intent=true`
- actual emit: `false`
- DecisionRouter/RiskGuard/LivePreflight/OrderService calls: `false`
- submitted count: `0`

`would_promote_to_order_intent=true` means the row is eligible to be shaped
into a future intent candidate. It must not directly create an order or call a
trading path.

## Candidate Schema Draft

Schema name: `aits_order_intent_candidate_v1`

Required fields:

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

The candidate is a structured bridge object. It is not an exchange order and
must remain inert until every downstream gate has explicitly accepted it.

## Emit Gate Conditions

An implementation Goal may only emit `aits_order_intent_candidate_v1` when all
of these conditions are true:

- `would_promote_to_order_intent=true`
- AI opinion is fresh
- AI opinion status is `buy_wait` or another explicitly allowed status
- symbol is present and belongs to a Managed Pool row
- managed source is allowed by policy
- market feed is healthy
- `submitted=0`
- no duplicate buy block is active
- no repeat buy block is active
- relock state allows a new intent
- holding/dust state does not conflict with a new buy
- intended amount is at least `10000` KRW
- intended amount is no more than `12000` KRW
- current guarded-window total would remain at or below `20000` KRW
- final action has not been changed by the candidate itself
- actual order remains false at emit time

If any condition is missing, the implementation must report a block reason and
must not emit.

## Validation Sequence

The future live sequence must be staged as separate gates:

1. Basic Buy Ready
2. AI opinion freshness check
3. `aits_order_intent_candidate_v1` creation
4. DecisionRouter validation
5. RiskGuard validation
6. LivePreflight validation
7. One-shot unlock confirmation
8. duplicate/repeat/relock validation
9. ExecutionBridge handoff
10. OrderService call
11. OrderAdapter exchange request
12. exchange response reconciliation

This design review does not connect any of these steps.

## Router Preconditions

Before DecisionRouter receives a candidate:

- the candidate schema must be complete
- `actual_order=false`
- `submitted=0`
- `final_action_unchanged=true`
- user visibility/audit fields must be present
- stale or missing AI opinion must block the candidate
- provider response text must not be treated as an executable action

DecisionRouter final action must not be changed by any proof-only Goal.

## RiskGuard Preconditions

Before RiskGuard receives a candidate:

- DecisionRouter validation must have accepted the candidate
- intended amount must satisfy `10000 <= amount <= 12000`
- total guarded-window cap must remain `<= 20000`
- duplicate, repeat, and relock checks must be satisfied
- managed source policy must be satisfied
- holding/dust policy must be satisfied
- one-shot unlock state must be present if live order execution is possible

RiskGuard changes require a separate high-risk implementation Goal.

## LivePreflight And Unlock Preconditions

Before LivePreflight or one-shot unlock can be used:

- the candidate must have passed Router and RiskGuard validation
- live trading mode must be explicitly allowed by the user
- AITS ON state must be explicit and current
- one-shot unlock must be explicit, fresh, and scoped to the candidate
- provider calls must not be triggered by unlock itself
- any failure must relock or block the path before OrderService

One-shot unlock is required for real order execution. Without it, the candidate
must remain a suggestion/report object only.

## Safety Caps

The first implementation should use conservative fixed caps:

- minimum order amount: `10000` KRW
- per-order hard cap: `12000` KRW
- total guarded-window cap: `20000` KRW

The caps are hard safety boundaries, not target amounts.

## Source, Holding, And Dust Policy

Initial source policy:

- `basic_added`: allowed if all gates pass
- `user_added`: allowed only if policy explicitly keeps it enabled for live
  intent candidates
- `system_seed`: blocked by default until a separate policy Goal allows it
- protected/manual-hold/trade-hold rows: blocked for new buy intent

Holding policy:

- existing holding rows must not be duplicated blindly
- dust holding rows remain displayable but must be checked before new buy
- holding/dust conflicts must block or require explicit reasoned approval

## Duplicate, Repeat, And Relock

Future implementation must define and record:

- duplicate symbol checks
- repeated intent checks
- repeated submitted order checks
- post-failure relock checks
- post-fill reconciliation checks
- cooldown or freshness windows

No candidate should reach OrderService while any repeat/relock condition is
unknown.

## Implementation Scope Candidate

A future implementation Goal may consider changes in:

- `tools/runtime_smoke/aits_qt_smoke_harness.py` for proof modes
- a new narrow service for inert intent candidate shaping
- Managed Pool or Basic candidate read-only context helpers
- documentation under `app/docs/`

Implementation should avoid modifying trading execution layers unless the Goal
explicitly scopes and reviews that risk.

## Forbidden Layers For The Next Goal

The next implementation Goal must still treat these as forbidden unless it
explicitly says otherwise:

- `app/services/order_service.py`
- `app/services/order_adapter.py`
- `app/services/live_order_preflight.py`
- `app/services/live_order_unlock.py`
- `app/services/risk_guard.py`
- `app/services/decision_router.py` final action behavior
- `app/services/execution_bridge.py`
- repository persistence mutation
- provider external calls
- Managed Pool row mutation

## Risk Points

Known risks before real emit:

- treating Basic Buy Ready as an order signal
- allowing stale AI opinion to create a candidate
- letting `user_added` rows auto-buy without explicit policy
- confusing dust/holding display with new-buy eligibility
- bypassing duplicate/repeat/relock checks
- treating provider text as a Router final action
- allowing OrderService before one-shot unlock
- failing to reconcile partial fills, cancel states, or unknown exchange states

## Next Recommended Goal

Completed inert bridge proof Goal:

`AITS-ORDER-INTENT-CANDIDATE-INERT-BRIDGE-PROOF-01`

Scope:

- build an inert `aits_order_intent_candidate_v1` object from
  `would_promote_to_order_intent=true`
- keep `actual_order_intent_emitted=false`
- keep DecisionRouter/RiskGuard/LivePreflight/OrderService uncalled
- prove amount caps and block reasons in fixture/live observe mode
- do not place orders

The candidate schema is documented in
`app/docs/aits_order_intent_candidate_v1.md`.

Completed read-only Router pre-handoff Goal:

`AITS-ORDER-INTENT-CANDIDATE-ROUTER-PREFLIGHT-READONLY-CONTRACT-01`

Scope:

- define how an inert candidate would be validated before Router handoff
- keep Router/RiskGuard/LivePreflight/OrderService uncalled
- keep `actual_order_intent_emitted=false`
- keep actual orders forbidden

This Goal records `aits_order_intent_router_handoff_readiness_v1` with
`router_handoff_ready=true/false`, blockers, warnings, and check-level detail.

Completed Router validation stub Goal:

`AITS-ORDER-INTENT-CANDIDATE-ROUTER-VALIDATION-STUB-PROOF-01`

Scope:

- define a no-call Router validation adapter contract
- prove candidate-to-Router payload shape without invoking DecisionRouter
- keep RiskGuard/LivePreflight/OrderService uncalled
- keep actual orders forbidden

This Goal records `aits_order_intent_router_validation_stub_v1` with
`router_validation_payload_ready=true/false`, validation errors, policy
warnings, and policy blockers. `user_added` remains
`user_added_requires_live_policy_confirmation` as a warning in this proof.

Completed source live policy review:

`AITS-ORDER-INTENT-CANDIDATE-ROUTER-VALIDATION-STUB-POLICY-REVIEW-01`

Scope:

- decide `user_added` source policy before any live-intent handoff
- keep code unchanged and document the source policy only
- keep actual Router/RiskGuard/Order calls forbidden

Decision:

- `user_added` is blocked by default for live order intent.
- Only exact `session_approved_symbols` can clear the `user_added` source
  blocker for the current session.
- `KRW-PYTH` is an example of a symbol that would require explicit
  session-scoped approval before the next source policy proof can report
  source readiness.
- One-shot unlock, amount caps, duplicate/repeat guards, relock, and all
  order-safety gates remain required.

Policy document:

`app/docs/aits_order_intent_source_live_policy_v1.md`

Completed source live policy stub proof:

`AITS-ORDER-INTENT-CANDIDATE-SOURCE-LIVE-POLICY-STUB-PROOF-01`

Scope:

- implement a read-only source policy evaluator
- prove `user_added_not_session_approved` without `session_approved_symbols`
- prove exact symbol approval clears only the source blocker
- keep actual emit, Router, RiskGuard, LivePreflight, OrderService, and
  OrderAdapter disabled

Result:

- `KRW-PYTH` without approval is blocked at source policy.
- `KRW-PYTH` with `session_approved_symbols=["KRW-PYTH"]` is source-policy
  ready and keeps `router_validation_payload_ready=true`.
- Approval does not emit an intent and does not call Router/Risk/Preflight/Order.

Completed one-shot unlock readiness stub proof:

`AITS-ORDER-INTENT-CANDIDATE-ONE-SHOT-UNLOCK-READINESS-STUB-PROOF-01`

Scope:

- prove the one-shot unlock readiness contract after source policy readiness
- keep actual unlock execution, actual emit, Router, RiskGuard,
  LivePreflight, OrderService, and OrderAdapter disabled

Result:

- without exact mock unlock approval, `one_shot_unlock_ready=false`,
  `policy_blockers` contains `one_shot_unlock_required`, and
  `live_order_readiness=false`;
- with exact mock unlock approval for the same symbol,
  `one_shot_unlock_ready=true`, `policy_blockers=[]`, and
  `live_order_readiness=true`;
- approval is mock proof input only. No live unlock token is created, consumed,
  or reused, and no Router/Risk/Preflight/Order path is called.

Completed LivePreflight readiness stub proof:

`AITS-ORDER-INTENT-CANDIDATE-LIVE-PREFLIGHT-READINESS-STUB-PROOF-01`

Scope:

- define `aits_order_intent_live_preflight_readiness_v1`
- prove 10,000 / 12,000 / 20,000 KRW caps before real LivePreflight
- prove duplicate/repeat/relock/submitted/final-action checks
- keep actual emit, real LivePreflight, Router, RiskGuard, OrderService, and
  OrderAdapter disabled

Completed actual read-only adapter design review:

`AITS-ORDER-INTENT-CANDIDATE-LIVE-PREFLIGHT-ACTUAL-READONLY-ADAPTER-DESIGN-REVIEW-01`

Scope:

- define the future `aits_live_preflight_readonly_adapter_contract_v1`
- keep the adapter as a validation-only shape check, not a service call
- separate one-shot unlock readiness from unlock consumption
- confirm the final live sequence should run Router validation, RiskGuard
  validation, LivePreflight validation, then final unlock confirmation before
  any ExecutionBridge/OrderService/OrderAdapter path
- keep actual LivePreflight, unlock consumption, actual emit, Router, RiskGuard,
  OrderService, and OrderAdapter disabled

Completed LivePreflight read-only adapter skeleton proof:

`AITS-LIVE-PREFLIGHT-READONLY-ADAPTER-SKELETON-PROOF-01`

Scope:

- implement the documented read-only adapter contract in the harness only
- build adapter input and output payloads without importing or calling the real
  LivePreflight service
- prove valid and invalid chains with fixture/live modes
- keep `would_call_live_preflight=false`, `live_preflight_called=false`,
  `unlock_consumed=false`, `actual_order_intent_emitted=false`, and
  `submitted=0`
