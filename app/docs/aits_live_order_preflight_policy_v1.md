# AITS Live Order Preflight Policy v1

## Purpose

AITS keeps one real-order path. It does not add paper mode, virtual trading, or
mock trading processors. Before that real-order path can ever call an order
service, a live preflight lock must evaluate the candidate and fail closed when
any required condition is missing.

This version is a locked proof layer only. It does not submit orders and it
does not unlock live mode.

## Owner

- Policy owner: `app/services/live_order_preflight.py`
- Proof harness: `tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof`
- Order path lock point: `app/services/order_adapter.py`, immediately before
  any `OrderService.place_order` call in the live branch.

## Input Schema

`LiveOrderPreflightInput` contains:

- `request_id`
- `symbol`
- `side`
- `amount_krw`
- `quantity`
- `price`
- `execution_mode`
- `aits_enabled`
- `live_order_unlock`
- `user_confirm_token`
- `risk_guard_checked`
- `risk_allowed`
- `emergency_stop`
- `max_order_amount_krw`
- `max_daily_loss_krw`
- `max_order_count_per_cycle`
- `duplicate_order_lock`
- `min_real_order_amount_krw`
- `account_ready`
- `api_key_ready`
- `price_fresh`
- `selected_provider`
- `source`

## Result Schema

`LiveOrderPreflightResult` contains:

- `locked`
- `allowed`
- `blocked_reason`
- `severity`
- `required_conditions`
- `missing_conditions`
- `submitted`
- `order_allowed`
- `real_order`
- `execution_mode`
- `request_id`
- `timestamp`

For this proof version, every result keeps:

- `locked`: `true`
- `allowed`: `false`
- `submitted`: `0`
- `order_allowed`: `false`
- `real_order`: `false`

## Required Conditions

The preflight checks:

- execution mode is live
- AITS is enabled
- explicit live-order unlock exists
- user confirmation token exists
- RiskGuard checked the candidate
- RiskGuard policy passed the candidate
- emergency stop is off
- max order amount is configured
- max daily loss is configured
- max order count per cycle is configured
- duplicate order lock exists
- minimum real order amount is configured
- account readiness is true
- API key readiness is true
- symbol is valid
- side is valid
- amount is valid
- price is fresh
- price is valid

If all individual checks are supplied, this proof version still remains locked
until a later explicit live-unlock Goal changes the policy.

## Locked Fixtures

The harness proof evaluates:

- `locked_execution_mode_disabled`
- `locked_missing_user_confirm`
- `locked_missing_riskguard`
- `locked_emergency_stop`
- `locked_amount_exceeds_cap`

Each fixture must report a concrete `blocked_reason`, keep `submitted=0`, keep
`order_allowed=false`, keep `real_order=false`, and avoid provider calls.

## OrderService Non-Reachability

The proof report records:

- `order_service_place_order_called=false`
- `order_adapter_live_branch_entered=false`
- `order_adapter_execution_mode=disabled`

The OrderAdapter live branch also fails closed before any order service call if
preflight is locked or if preflight evaluation itself raises.

## Future Live Unlock

A later high-risk Goal must explicitly define a one-shot real-order test with:

- explicit live unlock
- user confirmation
- minimum order only
- hard order cap
- emergency stop off
- duplicate order lock
- one-shot limit
- RiskGuard active proof

Until then, live preflight is a locked proof gate only.
