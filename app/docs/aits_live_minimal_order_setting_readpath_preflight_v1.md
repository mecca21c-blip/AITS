# AITS Live Minimal Order Setting Read Path Preflight v1

## Goal

`AITS-LIVE-MINIMAL-ORDER-SETTING-READPATH-PREFLIGHT-01` verifies the
read-only path for the configured one-shot order amount before any real order
test.

This proof does not submit an order and does not call Router, RiskGuard,
LivePreflight, ExecutionBridge, OrderService, OrderAdapter, unlock services, or
external AI providers.

## Read Path Summary

The current configured order amount path is:

- UI input: `StrategyTab.spn_order_amount`
- UI sync: `settings.strategy.order_amount_krw`
- runtime read: `MainWindow._settings.strategy.order_amount_krw`
- prefs key: `prefs.json.strategy.order_amount_krw`
- schema key: `StrategyConfig.order_amount_krw`

`StrategyConfig.order_amount_krw` is the preferred SSOT for the user-configured
one-shot order amount. The schema default is currently 10,000 KRW, but 10,000
is a current/default value, not a hardcoded live-order amount.

## Harness Mode

- `live-minimal-order-setting-readpath-preflight`

Example:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-setting-readpath-preflight --target-symbol KRW-PYTH --observe-only
```

## Report Schema

`aits_live_minimal_order_setting_readpath_preflight_v1`

Key fields:

- `configured_order_amount_krw`
- `configured_order_amount_source`
- `ui_setting_key`
- `runtime_setting_key`
- `prefs_key`
- `settings_schema_key`
- `amount_ssot_confirmed`
- `amount_is_hardcoded=false`
- `current_default_or_current_value_krw`
- `min_order_krw`
- `per_order_hard_cap_krw`
- `total_guarded_window_cap_krw`
- `hard_cap_validated`
- `window_cap_validated`
- `next_confirm_phrase_template`
- `sample_confirm_phrase_for_current_amount`
- `ready_for_setting_amount_one_shot_test`
- `blockers`
- `warnings`
- `safety_flags`

## Readiness Rules

`ready_for_setting_amount_one_shot_test=true` requires:

- configured amount is read from `prefs.load_settings().strategy.order_amount_krw`
- amount SSOT is confirmed
- amount is not hardcoded to 10,000
- amount is at least the minimal test minimum of 10,000 KRW
- amount is at most the per-order hard cap of 12,000 KRW
- amount fits the 20,000 KRW guarded-window cap
- confirm phrase is based on `configured_order_amount_krw`
- `actual_order=false`
- `submitted_count=0`
- `provider_external_call_count=0`

## Blockers

- `configured_order_amount_read_path_missing`
- `amount_ssot_not_confirmed`
- `amount_hardcoded_to_10000`
- `ui_setting_and_runtime_setting_mismatch`
- `configured_amount_below_min_order`
- `configured_amount_exceeds_per_order_hard_cap`
- `guarded_window_cap_not_verifiable`
- `confirm_phrase_not_setting_amount_based`
- `actual_order_flag_detected`
- `submitted_count_not_zero`
- `provider_external_call_detected`

## User Action Before Actual Test

Before `AITS-LIVE-MINIMAL-ORDER-SETTING-AMOUNT-ONE-SHOT-TEST-01`, the user
should confirm the desired order amount in the program UI before pressing ON.
The actual one-shot test confirm phrase must match that configured amount
exactly.
