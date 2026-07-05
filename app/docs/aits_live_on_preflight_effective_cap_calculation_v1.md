# AITS Live ON Preflight Effective Cap Calculation v1

## Goal

`AITS-LIVE-ON-PREFLIGHT-EFFECTIVE-CAP-CALCULATION-VERIFY-01` verifies the
effective cap shown by the ON preflight popup. It does not change settings,
force caps upward, bypass preflight, or submit orders.

## Active Path

- Owner: `app/ui/app_gui.py::_preflight_check`
- Order amount: `settings.strategy.order_amount_krw`
- Available KRW: `svc_order.compute_available_krw_snapshot(source_path="on_preflight")`
- Position size percent: `settings.strategy.pos_size_pct`
- Per-order hard cap: `settings.strategy.per_order_hard_cap_krw`
- Guarded-window cap: `settings.strategy.total_guarded_window_cap_krw`

## Calculation

```text
pos_limit_krw = available_krw * settings.strategy.pos_size_pct / 100
effective_hard_cap_krw = min(
    available_krw,
    pos_limit_krw,
    per_order_hard_cap_krw,
    total_guarded_window_cap_krw
)
```

`effective_hard_cap_below_min_order` is correct when:

- `order_amount_krw >= 10000`
- `effective_hard_cap_krw < 10000`

## Current Example

The observed popup values are mathematically consistent:

```text
available_krw = 113201
order_amount_krw = 10000
pos_size_pct = 2.5
pos_limit_krw = 113201 * 2.5 / 100 = 2830
per_order_hard_cap_krw = 12000
total_guarded_window_cap_krw = 20000
effective_hard_cap_krw = min(113201, 2830, 12000, 20000) = 2830
```

Because `2830 < 10000`, the blocker
`effective_hard_cap_below_min_order` is expected.

## Required Setting For 10000 KRW Test

For the current KRW balance, the minimum position size percent is:

```text
10000 / 113201 * 100 = 8.84%
```

A practical test setting is `pos_size_pct=10`, which gives:

```text
113201 * 10 / 100 = 11320
effective_hard_cap_krw = min(113201, 11320, 12000, 20000) = 11320
```

That is above the 10000 KRW minimum order and below the configured 12000 KRW
per-order hard cap.

## Harness Mode

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-effective-cap-summary --observe-only
```

The mode emits `aits_live_on_preflight_effective_cap_summary_v1` with:

- `available_krw`
- `order_amount_krw`
- `pos_limit_krw`
- `pos_size_pct`
- `per_order_hard_cap_krw`
- `total_guarded_window_cap_krw`
- `effective_hard_cap_krw`
- `min_required_pos_size_pct_for_order`
- `recommended_pos_size_pct_for_test`
- `first_blocker`
- `blocker_explained`
- `can_pass_if_pos_size_pct_adjusted`

Safety fields stay `actual_order=false`, `submitted_count=0`, and
`provider_external_call_count=0`.
