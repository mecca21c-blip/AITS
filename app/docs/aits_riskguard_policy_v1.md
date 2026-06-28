# AITS RiskGuard Policy v1

## Purpose

RiskGuard is the dry-run order-candidate policy gate for AITS. It evaluates
whether a candidate would be acceptable under risk policy, but it never submits
orders, calls providers, calls brokers, writes to repositories, or changes UI.

This policy is a pre-live safety layer. Passing RiskGuard means only
`risk_allowed=True`; it does not mean real trading is enabled.

## Owner

- Implementation: `app/services/risk_guard.py`
- Proof harness: `tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof`
- Live integration: not enabled in this policy version

## Input Schema

`RiskGuardInput` contains:

- `symbol`
- `side`
- `requested_amount_krw`
- `price`
- `quantity`
- `source_provider`
- `confidence`
- `action`
- `holdings_value_krw`
- `cash_available_krw`
- `portfolio_value_krw`
- `daily_realized_pnl_krw`
- `daily_loss_limit_krw`
- `max_order_amount_krw`
- `max_position_value_krw`
- `emergency_stop`
- `stale_price`
- `execution_mode`
- `dry_run`
- `request_id`

## Output Schema

`RiskGuardResult` contains:

- `allowed`
- `risk_allowed`
- `blocked_reason`
- `severity`
- `max_allowed_amount_krw`
- `requires_confirm`
- `submitted`
- `order_allowed`
- `real_order`
- `dry_run`
- `checks`
- `request_id`

`allowed` and `risk_allowed` mean the candidate passed dry-run risk policy.
They are not live-order permission. In this version every result keeps
`submitted=0`, `order_allowed=False`, and `real_order=False`.

## Default Policy

- `emergency_stop=True` blocks.
- Invalid `symbol` blocks.
- `side` outside `buy` or `sell` blocks.
- `requested_amount_krw <= 0` blocks.
- Missing or non-positive `price` blocks.
- `stale_price=True` blocks.
- Amount above `max_order_amount_krw` blocks.
- Holdings plus requested amount above `max_position_value_krw` blocks.
- Realized daily loss at or below `-daily_loss_limit_krw` blocks.
- Buy amount above available cash blocks.

## Dry-Run Proof Fixtures

The proof harness validates seven synthetic candidates:

- `allowed_small_buy`
- `blocked_max_order`
- `blocked_position_limit`
- `blocked_daily_loss`
- `blocked_emergency_stop`
- `blocked_invalid_symbol`
- `blocked_stale_price`

Every fixture must preserve `submitted=0`, `order_allowed=False`,
`real_order=False`, and `dry_run=True`.

## Live Unlock Gates

Before small-money or live execution, AITS still needs:

- Active path integration before `OrderAdapter`.
- Runtime log proof that RiskGuard evaluated each candidate.
- User confirmation proof.
- Per-order amount cap proof.
- Daily loss limit proof.
- Emergency stop proof.
- Clear separation between `risk_allowed` and real `order_allowed`.
- A separate live unlock Goal.
