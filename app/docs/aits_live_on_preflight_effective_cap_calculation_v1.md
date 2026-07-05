# AITS Live ON Preflight Effective Cap Calculation v1

## Goal

ON-start preflight is a symbol-less readiness gate. It must not block on a
candidate-specific user position cap before a candidate symbol exists.

This document does not change RiskGuard, LivePreflight, OrderAdapter, or any
order submit path.

## Active Path

- Owner: `app/ui/app_gui.py::_preflight_check`
- Order amount: `settings.strategy.order_amount_krw`
- Available KRW: `svc_order.compute_available_krw_snapshot(source_path="on_preflight")`
- Per-order hard cap: `settings.strategy.per_order_hard_cap_krw`
- Guarded-window cap: `settings.strategy.total_guarded_window_cap_krw`
- Position policy at ON start: `ai_dynamic_pending_candidate`

`settings.strategy.pos_size_pct` is not used as the ON-start live preflight
position cap.

## Calculation

```text
effective_hard_cap_krw = min(
    available_krw,
    per_order_hard_cap_krw,
    total_guarded_window_cap_krw
)
```

`pos_limit_krw` is `not_applicable` at ON start because there is no
`candidate_symbol` yet.

## Current Example

```text
available_krw = 113201
order_amount_krw = 10000
per_order_hard_cap_krw = 12000
total_guarded_window_cap_krw = 20000
effective_hard_cap_krw = min(113201, 12000, 20000) = 12000
```

The cap condition passes because `12000 >= 10000`.

Candidate/order stage still validates explicit per-asset overrides when a
symbol is known. Asset `0%` or missing means AI dynamic mode, not global
inheritance.

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-effective-cap-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-ai-dynamic-cap-summary --observe-only
```

Safety fields stay `actual_order=false`, `submitted_count=0`, and
`provider_external_call_count=0`.
