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
- OrderService real order submission is not enabled by this review.
- RiskGuard exists and has synthetic plus active-path fixture proof.
- LiveOrderPreflight exists and is connected before the order service boundary.
- One-Shot Unlock exists as a contract input to preflight.
- Runtime safety fields must remain `submitted=0`, `order_allowed=false`, and
  `real_order=false` until the later real-order Goal explicitly opens them.

The current system is not live-order ready by default. The next Goal must open
only the minimum required live path and must close it immediately after one
attempt.

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
