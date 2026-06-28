# AITS Live One-Shot Unlock Policy v1

## Purpose

AITS keeps one real-order path. It does not add paper mode, virtual trading,
simulation trading processors, or mock trading processors. A real order may be
considered only after an explicit one-shot unlock contract is valid and the
live preflight lock accepts that contract.

This policy is a contract proof only. It does not submit orders, does not
enable live mode, and does not call `OrderService.place_order`.

## Owner

- Contract owner: `app/services/live_order_unlock.py`
- Preflight owner: `app/services/live_order_preflight.py`
- Proof harness:
  `tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof`

## Request Schema

`LiveOneShotUnlockRequest` contains:

- `request_id`
- `symbol`
- `side`
- `amount_krw`
- `max_order_amount_krw`
- `min_order_amount_krw`
- `user_confirm_phrase`
- `confirm_token`
- `expires_at_utc`
- `ttl_sec`
- `duplicate_lock_key`
- `created_at_utc`
- `source`
- `operator_note`

## State Schema

`LiveOneShotUnlockState` contains:

- `unlock_id`
- `active`
- `consumed`
- `expired`
- `symbol`
- `side`
- `amount_krw`
- `max_order_amount_krw`
- `min_order_amount_krw`
- `confirm_token_hash`
- `expires_at_utc`
- `duplicate_lock_key`
- `created_at_utc`
- `consumed_at_utc`
- `consume_reason`

The raw confirmation token is never stored in state or written to reports.

## Result Schema

`LiveOneShotUnlockResult` contains:

- `unlock_valid`
- `locked`
- `allowed_for_preflight`
- `blocked_reason`
- `severity`
- `unlock_id`
- `consumed`
- `expired`
- `duplicate_locked`
- `max_order_amount_krw`
- `submitted`
- `order_allowed`
- `real_order`
- `request_id`

`allowed_for_preflight=true` means only that the one-shot contract can be used
as input to `LiveOrderPreflight`. It does not mean order submission is allowed.
The result always keeps `submitted=0`, `order_allowed=false`, and
`real_order=false`.

## Policy

- missing unlock -> locked
- invalid confirm token -> locked
- expired unlock -> locked
- consumed unlock -> locked
- duplicate lock reuse -> locked
- amount <= 0 -> locked
- amount below minimum -> locked
- amount above hard cap -> locked
- symbol mismatch -> locked
- side mismatch -> locked
- valid unlock -> `allowed_for_preflight=true`

A valid unlock must be consumed after use. Once consumed, the same unlock cannot
be reused. Its duplicate lock key also prevents another unlock from being used
for the same one-shot order key.

## Proof Fixtures

The harness validates:

- `no_unlock`
- `invalid_confirm_token`
- `amount_exceeds_unlock_cap`
- `expired_unlock`
- `valid_unlock_preflight_pass_but_no_order_submit`
- `consumed_unlock_reuse`
- `duplicate_lock_reuse`

The valid fixture proves only that the contract can satisfy preflight inputs.
It also proves:

- `OrderService.place_order` is not called.
- `submitted=0`
- `order_allowed=false`
- `real_order=false`
- provider call markers stay zero.

## Future Minimum Real Order Goal

A later `AITS-LIVE-MINIMUM-REAL-ORDER-TEST-01` Goal must separately approve a
single minimum-size real order with explicit unlock, user confirmation, hard
cap, duplicate lock, emergency stop off, RiskGuard active proof, and immediate
relock after one use.
