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
| `available_krw` | `svc_order._compute_available_krw()` | Current KRW available from the account/balance source. |
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

## Blocker Reclassification

When ON click reaches the preflight popup but runtime does not start, the
diagnostic should report `on_preflight_blocked` instead of treating it as a
missing ON click. More specific blockers include:

- `available_krw_zero`
- `insufficient_available_krw`
- `pos_limit_zero`
- `effective_hard_cap_below_min_order`
- `order_amount_exceeds_per_order_hard_cap`
- `order_amount_exceeds_total_guarded_window_cap`

## Safety

This preflight source fix does not force ON, does not set `order_allowed=True`,
does not set `real_order=True`, does not emit an order intent, and does not call
OrderAdapter or ExecutionBridge.
