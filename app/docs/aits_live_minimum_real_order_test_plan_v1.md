# AITS Live Minimum Real Order Test Plan v1

## Purpose

This document is the final preflight review before a later
`AITS-LIVE-MINIMUM-REAL-ORDER-TEST-01` Goal. It does not execute orders, does
not enable live mode, and does not add paper mode, virtual trading, simulation
trading processors, or mock trading processors.

AITS keeps one real-order path. That path may be opened only by a later Goal
with an explicit one-shot unlock, RiskGuard pass, LiveOrderPreflight pass,
hard cap, duplicate lock, and immediate relock.

## Current Readiness Summary

- OrderAdapter default execution mode remains `disabled`.
- ExecutionBridge remains dry-run by default.
- OrderService real order submission is limited to the explicit one-shot
  minimum real-order test path.
- RiskGuard exists and has synthetic plus active-path fixture proof.
- LiveOrderPreflight exists and is connected before the order service boundary.
- One-Shot Unlock exists as a contract input to preflight.
- Runtime safety fields must remain `submitted=0`, `order_allowed=false`, and
  `real_order=false` until the later real-order Goal explicitly opens them.

The current system is not live-order ready by default. The next Goal must open
only the minimum required live path and must close it immediately after one
attempt.

## 2026-06-28 Minimum Real Order Attempt Result

Goal `AITS-LIVE-MINIMUM-REAL-ORDER-TEST-01` reached account/key readiness and
stopped before order submission because available KRW was below the confirmed
5000 KRW order amount.

- report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260628_224116_517539.json`
- result: `partial`
- failure reason: `insufficient_krw_balance`
- target: `KRW-BTC` buy `5000` KRW
- hard cap: `6000` KRW
- Upbit key/account readiness: true
- available KRW at check time: `225.99230448`
- `OrderService.place_order` called: false
- submitted count: `0`
- real order: false
- retry/reorder: not performed

Next real-order attempt must not reuse this result as approval. It requires a
fresh confirm phrase, sufficient KRW, and the same one-shot proof chain.

## 2026-06-29 Funded Retry Result

Goal `AITS-LIVE-MINIMUM-REAL-ORDER-TEST-RETRY-WITH-FUNDED-KRW-01` completed
the one-shot minimum real-order path after KRW funding.

- report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_045413_391177.json`
- result: `pass`
- target: `KRW-BTC` buy `5000` KRW
- hard cap: `6000` KRW
- Upbit key/account readiness: true
- available KRW before order: `118190.37846555`
- ticker price at preflight: `90186000`
- RiskGuard: passed
- One-Shot Unlock: valid before order, consumed after order
- LiveOrderPreflight: passed
- `OrderService.place_order` call count: `1`
- order HTTP status: `201`
- order uuid: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- order response state: `wait`
- submitted count: `1`
- real order: true
- relocked: true
- duplicate lock set: true
- repeat order blocked: true
- KRW after check: `113188.38509874`
- BTC after check: `0.00005542`
- retry/reorder: not performed

The runtime returned to a locked contract state after the one-shot attempt.
Any additional real order requires a new Goal and a fresh confirm phrase.

## 2026-06-29 Post-Trade Reconciliation Result

Goal `AITS-LIVE-ORDER-POST-TRADE-RECONCILIATION-01` queried the original order
without placing, cancelling, selling, or retrying any order.

- report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_050259_116145.json`
- order uuid: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- query HTTP status: `200`
- latest state: `cancel`
- market: `KRW-BTC`
- side: `bid`
- ord_type: `price`
- price: `5000`
- executed_volume: `0.00005542`
- trades_count: `1`
- paid_fee: `2.49974681`
- locked: `0.50663319`
- KRW balance: `113188.38509874`
- BTC balance: `0.00005542`
- KRW delta vs first post-order report: `0`
- BTC delta vs first post-order report: `0`
- `OrderService.place_order` called during reconciliation: false
- cancel called: false
- sell called: false
- repeat order attempted: false
- unlock consumed: true
- relocked: true
- duplicate lock set: true
- repeat order blocked: true

The first live order is reconciled as a single real order with one trade and no
additional order-side action from the reconciliation Goal.

## 2026-06-29 Final Live Order Audit Result

Goal `AITS-LIVE-ORDER-POST-TRADE-FINAL-AUDIT-01` rechecked the live-order
lifecycle and reconciliation reports, then performed a fresh dry-read and
read-only order reconciliation query for the same order uuid.

- final audit status: GO
- dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_051153_165897.json`
- reconciliation recheck report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_051206_771216.json`
- order uuid: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- latest state: `cancel`
- executed_volume: `0.00005542`
- paid_fee: `2.49974681`
- locked: `0.50663319`
- KRW balance: `113188.38509874`
- BTC balance: `0.00005542`
- delta vs first post-order report: `0`
- `OrderService.place_order` called during final audit: false
- cancel called: false
- sell called: false
- repeat order attempted: false
- unlock consumed: true
- relocked: true
- duplicate lock set: true
- repeat order blocked: true

The final audit does not authorize another live order. Before any later live
order, add explicit state-handling policy for partially filled orders that end
with exchange state `cancel`, strengthen read-only reconciliation automation,
and prove relock plus duplicate-lock persistence after restart.

## Live Order State Handling Policy

The state policy is defined in
`app/docs/aits_live_order_state_policy_v1.md`.

The first live order is classified with separate raw and normalized states:

- raw initial state: `wait`
- raw latest state: `cancel`
- normalized order state: `partially_filled_cancelled_remainder`
- reason: `executed_volume=0.00005542`, `paid_fee=2.49974681`, and BTC balance
  reconciliation prove that a fill occurred before the exchange returned the
  latest `cancel` state.

This classification means the filled quantity is treated as a real execution,
while any unfilled remainder is treated as cancelled or released by the
exchange. It is not a failed-order retry signal.

## 2026-06-29 Lock Persistence Restart Proof

Goal `AITS-LIVE-LOCK-PERSISTENCE-RESTART-PROOF-01` checked whether the
post-live safety state survived a fresh app initialization after the first live
order and reconciliation.

- baseline dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052854_981633.json`
- baseline reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052914_809635.json`
- restart dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052941_859748.json`
- restart reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052957_387433.json`
- post-restart AITS state: `AITS OFF`
- post-restart safety state: `Shadow · 주문 없음`
- order uuid retained: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- normalized order state retained by policy: `partially_filled_cancelled_remainder`
- reconciliation status: `reconciled`
- unlock consumed: true
- relocked: true
- duplicate lock set: true
- repeat order blocked: true
- `OrderService.place_order` called during proof: false
- cancel called: false
- sell called: false
- repeat order attempted: false

The proof used dry-read and read-only order reconciliation only. It did not
create another unlock and did not place, cancel, sell, or retry an order.

## 2026-06-29 Post-Order 60 Minute Passive Proof

Goal `AITS-LIVE-POST-ORDER-60MIN-PASSIVE-PROOF-01` kept the production app in a
passive state for 60 minutes after the first live order, reconciliation, state
policy, and restart-lock proof.

- passive app parent PID: `19196`
- passive app child PID: `11384`
- passive start: `2026-06-29 05:47:49 KST`
- passive 15 minute check: `2026-06-29 06:03:22 KST`
- passive 30 minute check: `2026-06-29 06:18:35 KST`
- passive 45 minute check: `2026-06-29 06:33:49 KST`
- passive 60 minute check: `2026-06-29 06:49:03 KST`
- baseline dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_054655_438514.json`
- baseline reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_054738_679398.json`
- final dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064924_106372.json`
- final reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064935_630819.json`
- crash/freeze: false
- extra `place_order` calls: `0`
- cancel calls: `0`
- sell calls: `0`
- retry calls: `0`
- new `real_order=True`: `0`
- `order_allowed=True`: `0`
- `live_order_unlock=True`: `0`
- provider external generation calls: `0`
- Traceback/ERROR/CRITICAL: `0`
- `AISnapshotStore`: `2`
- `TradeLogDecisionStage`: `0`
- `ManagedPoolAIReviewQueue`: `65`
- relocked: true
- duplicate lock set: true
- repeat order blocked: true

The 60 minute passive proof did not create another unlock and did not place,
cancel, sell, or retry an order. Review queue logging remained periodic, and no
Journal or Snapshot order-stage burst was observed.

## 2026-06-29 Read-Only Reconciliation Hardening

Goal `AITS-LIVE-READONLY-ORDER-RECONCILIATION-HARDENING-01` strengthened the
post-trade reconciliation harness without placing, cancelling, selling, or
retrying an order.

- hardened reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_081228_882109.json`
- dry-read regression report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_081249_122037.json`
- order uuid: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- raw order state: `cancel`
- normalized order state: `partially_filled_cancelled_remainder`
- normalized action: `treat_filled_quantity_as_executed_no_retry`
- reconciliation status: `reconciled`
- reconciliation reason: `read_only_query_balance_and_lock_proof_ok`
- executed_volume: `0.00005542`
- paid_fee: `2.49974681`
- locked: `0.50663319`
- KRW balance: `113188.38509874`
- BTC balance: `0.00005542`
- balance delta KRW: `0`
- balance delta BTC: `0`
- relocked: true
- duplicate lock set: true
- repeat order blocked: true
- place/cancel/sell/retry calls: `0`

The strengthened schema separates exchange raw state from AITS normalized
state and keeps reconciliation strictly read-only. It is evidence for audit and
operator review only; it does not authorize another live order.

## Minimum Real Order Scope

The later real-order Goal is limited to one candidate:

- symbol: `KRW-BTC`
- side: `buy`
- amount_krw candidate: `5000` KRW
- hard cap: `6000` KRW maximum for the whole test
- max order count per cycle: `1`
- max total orders per test: `1`
- duplicate order lock: required
- sell: prohibited
- market sell: prohibited
- full liquidation: prohibited
- retry order: prohibited
- automatic AI/provider-triggered repeat order: prohibited

The actual amount must be confirmed by the user at the start of the later
real-order Goal. If the exchange minimum order amount or available KRW balance
does not support the candidate amount, the later Goal must stop before unlock.

## Account And Exchange Readiness

The later Goal must verify readiness without exposing secrets:

- Upbit account readiness is true.
- API key readiness is true, without logging key bodies.
- available KRW is greater than or equal to the confirmed order amount plus
  expected fees.
- target symbol is tradable.
- target price is fresh.
- exchange minimum order amount is satisfied.

This review does not browse or call an order endpoint to confirm exchange
minimums. Treat the minimum amount as "must verify immediately before order" in
the later Goal.

## Confirm Phrase Policy

Candidate phrase for the later Goal:

```text
AITS_REAL_ORDER_ONCE_KRW_BTC_BUY_5000_CONFIRM
```

Rules:

- The phrase must include symbol, side, and amount.
- A mismatched phrase keeps the unlock locked.
- The raw phrase/token must not be written to logs or reports.
- Only a hash or masked proof may be logged.
- The unlock TTL must be short, recommended `120` seconds or less.
- The unlock must be consumed after one preflight use.
- A consumed unlock must not be reusable.

If the final amount changes from `5000`, the phrase must change to match the
final amount.

## RiskGuard Required Conditions

RiskGuard must pass the exact candidate before preflight:

- symbol is `KRW-BTC`
- side is `buy`
- requested amount is positive and within the hard cap
- cash is sufficient for the candidate
- max order amount is configured
- max position value is configured
- daily realized loss is within max daily loss
- emergency stop is off
- price is present and fresh

`risk_allowed=true` is only policy proof. It is not order permission by itself.

## LiveOrderPreflight Required Conditions

LiveOrderPreflight must receive and pass:

- execution mode is explicitly live for the one-shot attempt
- AITS enable state is explicitly allowed for the one-shot attempt
- one-shot unlock is valid and not consumed
- user confirmation token is present
- RiskGuard checked the candidate
- RiskGuard allowed the candidate
- emergency stop is off
- max order amount is configured
- max daily loss is configured
- max order count per cycle is configured
- duplicate order lock is present and unused
- minimum real order amount is configured
- account readiness is true
- API key readiness is true
- symbol, side, amount, and price are valid
- price is fresh

Preflight passing is still not permission to repeat. It is permission for one
attempt only in the later explicitly approved Goal.

## Duplicate Lock Policy

The duplicate lock key must include:

- Goal id
- symbol
- side
- amount
- UTC date/time bucket or request id

Candidate format:

```text
AITS-LIVE-MINIMUM-REAL-ORDER-TEST-01:KRW-BTC:buy:5000:<request_id>
```

Once consumed, the duplicate lock must block reuse. If duplicate state is
ambiguous, the later Goal must stop and must not retry the order.

## Emergency Stop Policy

Before unlock:

- emergency stop must be off
- manual sell/PANIC controls must remain disabled or guarded
- AITS must start from OFF/locked state
- live mode must not be enabled as a default setting

If emergency stop state cannot be read or is ambiguous, stop before unlock.

## Pre-Order Checklist

The later real-order Goal must complete this checklist before any order call:

- git HEAD and branch are fixed and reported
- runtime reports are backed up
- AITS starts OFF and locked
- manual sell/PANIC disabled proof is current
- `riskguard-proof` PASS
- `riskguard-active-path-candidate-proof` PASS
- `live-preflight-locked-proof` PASS
- `live-one-shot-unlock-contract-proof` PASS
- Upbit account readiness is true
- available KRW is sufficient
- target symbol price is fresh
- exchange minimum order amount is satisfied
- emergency stop is off
- duplicate lock is empty
- max order cap is configured
- daily loss cap is configured
- one-shot unlock is created for exactly one candidate
- OrderService actual order boundary is reviewed immediately before use
- one order attempt is made at most
- unlock is consumed and relocked immediately after the attempt

## During-Order Prohibitions

- no sell orders
- no liquidation orders
- no second order
- no retry after timeout or unknown state
- no provider refresh
- no AI-triggered order loop
- no change to hard cap after unlock
- no logging of API keys, secrets, or raw confirm token

## Post-Order Verification

After the later one-shot attempt, collect:

- exchange order response
- order id or uuid when present
- market
- side
- amount
- price
- state
- created_at
- executed volume
- remaining volume
- paid fee
- locked funds if reported
- available KRW and asset balance after the attempt
- AITS trade log row
- RiskGuard result
- LiveOrderPreflight result
- One-Shot Unlock consumed proof
- duplicate lock proof
- submitted count
- real_order flag
- relock status
- emergency stop status

## Failure Handling

Before order:

- unlock failure -> stop
- RiskGuard block -> stop
- Preflight lock -> stop
- account or key readiness failure -> stop
- stale price -> stop
- duplicate lock hit -> stop

During order:

- network timeout -> do not retry; query order/account state first
- HTTP error -> do not retry; persist response and stop
- unknown state -> do not retry; inspect exchange/account state manually
- partial response -> do not retry
- app crash -> restart only for inspection; verify exchange/app state before any
  further action

After order:

- missing trade log -> no further orders
- relock failure -> no further orders
- duplicate lock failure -> no further orders
- balance mismatch -> no further orders

## Relock Principle

The unlock must be consumed after one preflight use or one order attempt,
whichever happens first. A failed or unknown order attempt still consumes the
unlock. Re-ordering requires a separate future Goal and a new user confirmation.

## Next Goal Gate

`AITS-LIVE-MINIMUM-REAL-ORDER-TEST-01` may proceed only if this review, current
proof modes, and user approval all remain valid. If any checklist item is stale
or ambiguous, the next Goal must stop before unlock.
