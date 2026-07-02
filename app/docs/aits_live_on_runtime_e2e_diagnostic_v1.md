# AITS Live ON Runtime E2E Diagnostic v1

`AITS-LIVE-ON-RUNTIME-E2E-DIAGNOSTIC-01` defines a read-only diagnostic path for
observing what actually happens after the user turns AITS ON.

This diagnostic does not force a symbol, does not create a buy candidate, does
not refresh AI freshness, does not bypass RiskGuard or LivePreflight, and does
not submit an order. It reads the current settings, recent runtime smoke
reports, and `data/logs/aits.log`.

## Checklist

- UI, settings, and ON state
- runtime loop start
- market feed
- Managed Pool rows
- Basic score and candidate update
- AI opinion, freshness, and provider state
- order intent candidate
- Router validation
- RiskGuard
- LivePreflight
- one-shot unlock, duplicate, repeat, and relock gates
- ExecutionBridge
- OrderService
- OrderAdapter
- Upbit response
- trade log, position, and UI reflection

## Diagnostic Modes

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-e2e-diagnostic-dryrun --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-e2e-diagnostic-log-summary --observe-only
```

Both modes emit `aits_live_on_runtime_e2e_diagnostic_v1`.

`live-on-runtime-e2e-diagnostic-dryrun` is safe before ON. It confirms the report
shape and current read paths.

`live-on-runtime-e2e-diagnostic-log-summary` is intended after the user manually
turns AITS ON and lets the runtime produce logs.

## Symbol Policy

Harness fixture symbols such as `KRW-PYTH` are not runtime order targets. The ON
runtime diagnostic never requires `--target-symbol` and never hardcodes a live
target. It reports `detected_candidate_symbol` only when the actual runtime logs
or recent reports reveal one.

If no candidate is visible, the report uses `candidate_missing` or the precise
earlier blocker instead of injecting a candidate.

## Stage Blockers

- `on_state_not_detected`
- `runtime_loop_not_started`
- `market_feed_missing`
- `managed_pool_empty`
- `score_update_missing`
- `no_buy_ready_candidate`
- `ai_opinion_not_fresh`
- `order_intent_candidate_missing`
- `router_not_reached`
- `riskguard_not_reached`
- `live_preflight_not_reached`
- `unlock_not_reached`
- `execution_bridge_not_reached`
- `order_service_not_reached`
- `order_adapter_not_reached`
- `submit_not_attempted`
- `exchange_response_missing`
- `trade_log_missing`
- `position_update_missing`

## Order Path Status

- `no_runtime`
- `observing_only`
- `candidate_missing`
- `blocked_before_router`
- `blocked_at_router`
- `blocked_at_riskguard`
- `blocked_at_live_preflight`
- `blocked_at_unlock`
- `blocked_before_execution`
- `blocked_at_execution`
- `blocked_at_order_service`
- `blocked_at_order_adapter`
- `submitted`
- `submitted_but_no_exchange_response`
- `submitted_and_recorded`

## Safety Checks

The diagnostic flags critical states when runtime evidence shows more than one
submission, retry activity, multiple submitted symbols, an amount mismatch
against settings, OrderAdapter reachability without RiskGuard evidence, or a
submit path without unlock evidence.

The diagnostic itself keeps:

- `provider_external_call_count=0`
- `managed_pool_mutation=false`
- `actual_order_forced=false`
- `forced_candidate_injected=false`
- `forced_symbol_configured=false`
- no paper mode
- no virtual order

## User ON Test Procedure

1. Run `live-on-runtime-e2e-diagnostic-dryrun`.
2. Confirm `live-minimal-order-setting-readpath-preflight` still reads the UI
   setting amount from `prefs.load_settings.strategy.order_amount_krw`.
3. User manually turns AITS ON in the app.
4. Let the runtime run long enough to produce candidate/score/gate logs.
5. Run `live-on-runtime-e2e-diagnostic-log-summary`.
6. Use `last_reached_stage`, `first_blocker`, `all_blockers`, and
   `next_fix_target` to choose the next Goal.

## Next Fix Goal Rule

Do not jump to forced target or forced order tests. If the report shows no
runtime candidate, fix the earliest missing stage. If the report shows a submit
attempt, verify the Upbit response, trade log, position update, and UI
reflection before any further live-order Goal.
