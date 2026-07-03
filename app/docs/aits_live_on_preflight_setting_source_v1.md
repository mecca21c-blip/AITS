# AITS Live ON Preflight Setting Source v1

## Goal

`AITS-LIVE-ON-PREFLIGHT-SETTING-SOURCE-FIX-01` separates the ON button
preflight popup values into configured settings and balance-derived effective
limits.

## Active Owner

- File: `app/ui/app_gui.py`
- Handler path: `btn_run_toggle.toggled -> _on_toggle_run_toggled -> _on_toggle_run -> _preflight_check`
- Popup title: `실행 전 점검`

## Value Sources

| Field | Source | Meaning |
| --- | --- | --- |
| `available_krw` | `svc_order.compute_available_krw_snapshot()` -> `svc_order.fetch_accounts()` | Current KRW available from the read-only account/balance source. |
| `order_amount_krw` | `settings.strategy.order_amount_krw` | User-configured one-shot order amount SSOT. |
| `pos_limit_krw` | `available_krw * settings.strategy.pos_size_pct / 100` | Balance-derived position-size limit. |
| `hard_cap_krw` | `settings.strategy.per_order_hard_cap_krw` | Configured per-order hard cap. Default `12000`. |
| `effective_hard_cap_krw` | `min(available_krw, settings.max_total_krw, pos_limit_krw, hard_cap_krw)` | Runtime effective cap after balance and position constraints. |
| `total_guarded_window_cap_krw` | `settings.strategy.total_guarded_window_cap_krw` | Configured guarded-window cap. Default `20000`. |

## Zero Value Interpretation

- `hard_cap_krw=0` should not appear as the configured cap. The configured cap is
  `settings.strategy.per_order_hard_cap_krw`.
- `effective_hard_cap_krw=0` can still appear when `available_krw=0` or
  `pos_limit_krw=0`.
- `pos_limit_krw=0` is expected when `available_krw=0` because it is derived from
  the balance source.
- `available_krw=0` must not hide balance-read failures. The preflight now
  separates `actual_krw_balance_zero`, `balance_not_loaded`,
  `balance_fetch_failed`, `private_api_not_connected`, and
  `unknown_balance_source`.

## Blocker Reclassification

When ON click reaches the preflight popup but runtime does not start, the
diagnostic should report `on_preflight_blocked` instead of treating it as a
missing ON click. More specific blockers include:

- `available_krw_zero`
- `actual_krw_balance_zero`
- `balance_not_loaded`
- `balance_fetch_failed`
- `private_api_not_connected`
- `balance_cache_stale`
- `insufficient_available_krw`
- `pos_limit_zero`
- `effective_hard_cap_below_min_order`
- `order_amount_exceeds_per_order_hard_cap`
- `order_amount_exceeds_total_guarded_window_cap`

## Safety

This preflight source fix does not force ON, does not set `order_allowed=True`,
does not set `real_order=True`, does not emit an order intent, and does not call
OrderAdapter or ExecutionBridge.

## KRW Balance Source Trace

`AITS-LIVE-ON-PREFLIGHT-KRW-BALANCE-SOURCE-TRACE-01` adds
`[AITS][KRWBalanceSource]` logs and the
`live-on-preflight-krw-balance-source-summary` harness mode. The goal is to
distinguish an actual zero KRW balance from a missing or failed read-only
account lookup. The popup copy uses the same taxonomy, for example:

- `KRW 잔고 부족` for an actual zero/insufficient KRW balance.
- `KRW 잔고 미확인 - 잔고 조회 후 다시 ON` when the balance has not been
  loaded.
- `KRW 잔고 조회 실패 - Upbit 연결 확인 필요` when the account lookup fails.
- `Upbit 계정 연결 필요` when the private account API is not configured.
