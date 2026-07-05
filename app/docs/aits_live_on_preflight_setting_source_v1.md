# AITS Live ON Preflight Setting Source v1

## Goal

ON preflight separates account readiness, configured order amount, configured
hard caps, and candidate-stage position policy. It must not apply a
candidate-specific position cap before a candidate symbol exists.

## Active Owner

- File: `app/ui/app_gui.py`
- Handler path: `btn_run_toggle.toggled -> _on_toggle_run_toggled -> _on_toggle_run -> _preflight_check`

## Value Sources

| Field | Source | Meaning |
| --- | --- | --- |
| `available_krw` | `svc_order.compute_available_krw_snapshot()` -> `svc_order.fetch_accounts()` | Current KRW available from the read-only account/balance source. |
| `order_amount_krw` | `settings.strategy.order_amount_krw` | User-configured one-shot order amount SSOT. |
| `position_policy_mode` | `ai_dynamic_pending_candidate` | ON-start has no candidate symbol yet. |
| `pos_limit_krw` | `not_applicable_until_candidate_symbol` | User asset position cap is not applied at ON start. |
| `hard_cap_krw` | `settings.strategy.per_order_hard_cap_krw` | Configured per-order hard cap. Default `12000`. |
| `effective_hard_cap_krw` | `min(available_krw, hard_cap_krw, total_guarded_window_cap_krw)` | Runtime effective cap after balance and configured caps. |
| `total_guarded_window_cap_krw` | `settings.strategy.total_guarded_window_cap_krw` | Configured guarded-window cap. Default `20000`. |

## Asset Policy Contract

- asset percent `> 0`: use the explicit asset override at candidate/order stage.
- asset percent `0`, missing, or `None`: use AI dynamic position policy.
- asset percent `< 0`: invalid policy value.

`settings.strategy.pos_size_pct` is legacy/backward-compatible state and is not
used as the ON-start live preflight blocker.

## Effective Cap Example

```text
available_krw=113201
order_amount_krw=10000
hard_cap_krw=12000
window_cap=20000
effective_hard_cap_krw=min(113201, 12000, 20000)=12000
```

The cap condition passes because `12000 >= 10000`.

## Zero Value Interpretation

- `hard_cap_krw=0` should not appear as the configured cap. The configured cap is
  `settings.strategy.per_order_hard_cap_krw`.
- `effective_hard_cap_krw=0` can still appear when `available_krw=0`.
- `pos_limit_krw` is not applicable until candidate/order stage.
- `available_krw=0` must not hide balance-read failures. The preflight separates
  `actual_krw_balance_zero`, `balance_not_loaded`, `balance_fetch_failed`,
  `private_api_not_connected`, and `unknown_balance_source`.

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
- `effective_hard_cap_below_min_order`
- `order_amount_exceeds_per_order_hard_cap`
- `order_amount_exceeds_total_guarded_window_cap`

## Safety

This preflight source fix does not force ON, does not set `order_allowed=True`,
does not set `real_order=True`, does not emit an order intent, and does not call
OrderAdapter or ExecutionBridge.
