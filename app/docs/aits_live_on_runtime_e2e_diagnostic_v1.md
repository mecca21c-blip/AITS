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

For ON button failures, pair this report with
`live-on-runtime-after-preflight-stage-summary`. The stage summary distinguishes
signal wiring, `_on_toggle_run` ON/OFF branch selection, preflight pass/fail,
preflight exceptions, and runtime start request/result before the broader E2E
stage list is evaluated.

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

## ON Button State Trace

`AITS-LIVE-ON-BUTTON-STATE-LOGGING-TRACE-01` adds an adjacent trace for the
header ON/OFF control. The active owner is `app/ui/app_gui.py`, widget
`btn_run_toggle`, signal `toggled`, handler chain
`_on_toggle_run_toggled -> _on_toggle_run_toggled_impl -> _on_toggle_run`.

The trace writes `[AITS][ON]` log lines for button entry, requested state, and
runner start confirmation. It does not click ON, force `order_allowed`, emit an
order intent, or call OrderAdapter/ExecutionBridge.

Use:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-button-state-trace-dryrun --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-button-state-log-summary --observe-only
```

If `live-on-runtime-e2e-diagnostic-log-summary` reports
`on_state_not_detected`, run the ON button log summary before investigating
Router/RiskGuard/LivePreflight. A missing ON trace means the blocker is still
button/runtime state wiring, not order-intent promotion.

## ON Preflight Setting Source

`AITS-LIVE-ON-PREFLIGHT-SETTING-SOURCE-FIX-01` separates configured live caps
from balance-derived effective caps in the ON preflight popup.

Use:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-preflight-setting-source-summary --observe-only
```

If the ON click reaches the `실행 전 점검` popup and runtime does not start, the
blocker is `on_preflight_blocked`, not a missing ON click. The configured
per-order hard cap source is `settings.strategy.per_order_hard_cap_krw`
(default `12000`), while `effective_hard_cap_krw` may still be zero when the
balance source returns `available_krw=0`.

## ON Preflight KRW Balance Source

`AITS-LIVE-ON-PREFLIGHT-KRW-BALANCE-SOURCE-TRACE-01` further classifies the
balance side of `on_preflight_blocked`. `[AITS][KRWBalanceSource]` lines count
as ON preflight evidence, and the first blocker can be refined to
`actual_krw_balance_zero`, `balance_not_loaded`, `balance_fetch_failed`,
`private_api_not_connected`, `balance_cache_stale`,
`order_amount_exceeds_available_krw`, or `order_amount_exceeds_effective_cap`
when the logs contain enough detail.

## ON Preflight Provider Readiness Source

`AITS-LIVE-ON-PREFLIGHT-PROVIDER-READINESS-SOURCE-FIX-01` reclassifies provider-readiness blockers separately from AI analysis freshness. If ON is blocked before runtime because the selected GPT/Gemini provider is not connected, the blocker should come from `MainWindow._build_on_preflight_provider_readiness_state` and the provider connection snapshot. Stale or missing AI generation freshness is not a provider connection failure.

## ON After Preflight Stage Trace

`AITS-LIVE-ON-RUNTIME-AFTER-PREFLIGHT-STAGE-TRACE-01` adds an adjacent log
summary for the stages after the ON button handler starts:

- ON button detected
- ON preflight logged and passed/failed
- runtime start requested
- runner start confirmed
- order/live gate state
- order-intent and submit reachability

Use:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-trace --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-summary --observe-only
```

`CandidateFeedState` score updates alone do not prove live runtime order path
entry. Treat them as candidate/feed-loop evidence until runtime start and order
gate logs are present.

`AITS-LIVE-ON-BUTTON-ACTIVE-HANDLER-INSTRUMENTATION-01` adds the active handler
entry and result markers used by that summary: `handler_enter`,
`preflight_start`, `preflight_result`, `start_requested`, `start_result`,
`off_requested`, `stop_requested`, `stop_result`, and `handler_exception`.
If these markers are missing after a user clicks ON, investigate signal wiring
before Router/RiskGuard/Order paths.

`AITS-LIVE-ON-BUTTON-RUNTIME-CONTRACT-IMPLEMENT-01` defines the active ON
runtime contract as handler -> preflight -> runtime start or blocked status.
`runtime_status_display` is the UI-visible state source for ON/blocked/error
reporting. It does not grant order permission and must not set `order_allowed`
or `real_order`; live submit remains behind the existing RiskGuard,
LivePreflight, and unlock gates.

## 2026-07-08 Provider Readiness Gate Update

`provider_connection_check_needed` is no longer a terminal ON blocker when the selected GPT/Gemini key is present and one provider readiness check is explicitly allowed. If the check succeeds, E2E diagnostics should continue to balance/cap/runtime-start blockers. If it fails, the blocker is `provider_connection_failed`. Submitted/order counts must remain zero in this diagnostic stage.
## 2026-07-08 - Market Feed / Balance Gate SSOT

- E2E diagnostic now treats `[AITS][RuntimeFeedReadiness]` as the runtime market-feed readiness snapshot.
- If `RuntimeFeedReadiness` is absent, the parser falls back to latest-session `CandidateFeedState event=score_update`, `top_markets_return`, `tickers_return`, and `NetworkState`.
- `market_feed_missing` is split into more specific blockers: `market_feed_ticker_empty`, `market_feed_top_markets_empty`, `market_feed_degraded`, `market_feed_snapshot_missing`, and `market_feed_not_ready`.
- Balance/cap blockers are surfaced from `[AITS][LiveOnPreflight]` and `[AITS][KRWBalanceSource]` with `available_krw`, `accounts_fetch_status`, `fallback_reason`, and `effective_cap_krw`.
- This is observability only: no fake market feed, no fake balance, no order enablement.

## 2026-07-08 - Public Market Feed Recovery Root Fix

- Public market-feed active path is `app.services.market_feed` through the `app.services.upbit` UI wrapper.
- `[AITS][PublicMarketFeed]` logs distinguish request, result, empty response, and HTTP/network exception states for top markets and tickers.
- `RuntimeFeedReadiness` remains the runtime SSOT; E2E uses it first, then latest-session public feed, score update, and NetworkState evidence.
- A recovery or non-stale score update after an empty feed result can clear the earlier degraded state.
- New blocker split: `market_feed_network_error`, `market_feed_ticker_empty`, `market_feed_top_markets_empty`, `market_feed_degraded`, and `market_feed_snapshot_missing`.
- Balance/cap gates remain observational only; no fake feed, fake balance, order enablement, or submit path is introduced.

## 2026-07-08 - Network Profile Split Handling

- E2E diagnostics now read the latest `public-market-feed-network-profile-proof` report.
- If only the harness/sandbox public feed profile fails while the app runtime public feed profile succeeds, E2E sets `runtime_network_profile_split_detected=true` and does not pin the first blocker to `market_feed_network_error`.
- A successful external/escalated public read is supporting evidence that the public endpoint is reachable outside the sandbox, but it does not clear an app runtime `market_feed_network_error` by itself.
- If the app runtime profile also fails, `market_feed_network_error` remains the first blocker.
- This rule prevents a Codex sandbox network restriction from being misclassified as an app runtime feed blocker.

## 2026-07-08 - Real User App Feed Profile

- E2E diagnostics now also read `real-user-app-public-feed-profile-summary` when present.
- `market_feed_user_app_ok=true` clears a harness-only `market_feed_network_error` for the user app profile and records `market_feed_source=real_user_app_profile`.
- If the real user app session is missing, E2E can report `first_blocker=user_app_session_missing` with `next_fix_target=ask user to launch app manually and wait for feed logs`.
- `profile_split_result` distinguishes `user_app_ok_harness_restricted`, `user_app_and_harness_both_restricted`, `external_ok_all_local_restricted`, `harness_launched_app_session_detected`, and `no_user_app_session_detected`.

## 2026-07-08 - Runtime Start SSOT And Candidate Contract

- E2E diagnostics now separate `runtime_start_requested` from `runtime_loop_started`; generic live/feed logs are not treated as runner start confirmation.
- `runtime_loop_started=true` requires explicit runner/start evidence such as `[RUNNER] start_strategy called`, `[START-ACK]`, `runtime_started=True`, or `runtime_loop_started=True`.
- `CandidateFeedState` contributes to `candidate_loop_running` and `candidate_loop_source`, while `[AITS][OrderIntentCandidate]` contributes to observe-only order intent candidate detection.
- Observe-only candidate logs are diagnostic only and must not call Router, RiskGuard, LivePreflight, ExecutionBridge, OrderService, or OrderAdapter.
- Boolean false text such as `live_preflight_called=False` is no longer treated as a LivePreflight call. E2E requires an actual LivePreflight prefix or an explicit true marker.

## 2026-07-08 - RouterHandoff Observe-Only Preview

- E2E diagnostics now recognize `[AITS][RouterHandoff] event=handoff_preview` as a preview-only payload boundary after `OrderIntentCandidate`.
- The preview keeps `router_apply=False`, `final_action_applied=False`, `submitted=0`, `actual_order=False`, and all downstream call flags false.
- If preview exists and DecisionRouter validation is not called, E2E reports `first_blocker=router_handoff_preview_only` instead of `router_not_reached`.
- Summary fields include `router_handoff_preview_detected`, `router_handoff_schema`, `router_handoff_request_id`, `router_handoff_symbol`, `router_handoff_side`, `router_handoff_amount_krw`, `router_handoff_observe_only`, `router_apply`, `final_action_applied`, and `router_validation_observe_only`.

## 2026-07-08 - RouterValidation Observe-Only Preview

- E2E diagnostics now recognize `[AITS][RouterValidation] event=validation_preview` as a no-apply validation boundary after RouterHandoff.
- The preview validates symbol, side, amount, runtime state, preflight status, provider readiness, market feed, balance gate, and cap gate inputs.
- It must keep `router_apply=False`, `final_action_applied=False`, `submitted=0`, `actual_order=False`, and all RiskGuard/LivePreflight/Execution/Order flags false.
- If validation passes, E2E reports `first_blocker=router_validation_observe_only` and `order_path_status=blocked_at_router`.
- If validation fails, E2E reports `first_blocker=router_validation_failed`.
- Read-only `[AITS][OrderService] fetch_accounts called` lines are reported as account reads, not submit/order path reach.

## 2026-07-08 - RiskGuard/LivePreflight Observe-Only Preview

- E2E diagnostics now recognize `[AITS][RiskGuardPreview] event=risk_preview` and `[AITS][LivePreflightPreview] event=live_preflight_preview`.
- Preview lines are not actual RiskGuard or LivePreflight calls and do not count as execution/order path reach.
- `riskguard_apply=True`, `live_preflight_apply=True`, `unlock_performed=True`, `submitted_count>0`, or any execution/order adapter reach is critical.
- New blockers are `riskguard_preview_missing`, `riskguard_preview_blocked`, `live_preflight_preview_missing`, `live_preflight_preview_blocked`, and `live_preflight_preview_observe_only`.
- The live preflight preview may require confirm phrase and unlock while keeping `confirm_phrase_matched=False` and `unlock_performed=False`.

## 2026-07-08 - Guarded Execution Approval Boundary

- E2E diagnostics now recognize `[AITS][GuardedExecutionContract] event=contract_preview` as `aits_guarded_execution_contract_preview.v1`.
- The contract separates `confirm_phrase_required`, `confirm_phrase_matched`, `unlock_required`, `unlock_performed`, and `execution_allowed`.
- A blocked LivePreflightPreview with this contract becomes `first_blocker=live_order_approval_required` and `order_path_status=blocked_before_execution`.
- Any `execution_allowed=True`, `execution_called=True`, `order_service_called=True`, `order_adapter_called=True`, `submitted_count>0`, or `actual_order=true` is critical.

## 2026-07-08 - Guarded One-Shot Execution Boundary

- The actual live path remains closed until the user enters the exact confirm phrase and grants a one-shot unlock in the app.
- The only opened amount is `10000 KRW`; `submit_attempt_count` and `submitted_count` must start at zero.
- After one attempt the app must log `locked_after_submit` or `locked_after_failed_submit` and must not retry.
- E2E keeps readiness and submit-result fields separate so a readiness proof does not imply that a live order was submitted.

## 2026-07-08 - Normal Live Trading UX Visibility

- After ON preflight passes, the app must emit `[AITS][LiveTradingUX] event=live_monitoring_started` and a visible waiting status while it waits for order information.
- If no `GuardedExecutionContract` is available yet, E2E reports `approval_waiting_status_detected` and `approval_waiting_reason` instead of leaving the user with a silent unchanged screen.
- When a guarded contract appears, the app opens the approval dialog and E2E reports `approval_dialog_auto_opened`, `approval_dialog_input_visible`, `approval_button_enabled`, and the dialog symbol/side/amount.
- A running ON session with no waiting status, no approval dialog, and no guarded contract is classified as `live_order_ux_silent_failure`.
- The ON button remains the normal run/stop control; the hidden one-shot compatibility button must not be added back to the header layout.

## 2026-07-08 - Normal Auto Trading Flow

- E2E diagnostics now recognize `[AITS][LiveOrderPipeline]` as the normal ON live path.
- Normal flow events include `candidate_selected`, `router_validation_started`, `router_validation_result`, `riskguard_started`, `riskguard_result`, `execution_requested`, `execution_result`, and `order_submit_result`.
- The normal path does not wait for `GuardedExecutionContract` approval and does not auto-open a confirm phrase dialog.
- One-shot unlock is not required for normal guarded-window orders, but RiskGuard, LivePreflight, ExecutionBridge, OrderService, and OrderAdapter remain required.
- Summary fields include `normal_live_order_pipeline_detected`, `live_pipeline_router_result`, `live_pipeline_riskguard_result`, `live_pipeline_execution_requested`, `live_pipeline_execution_result`, `live_pipeline_order_submit_result`, and `live_pipeline_blocker`.
- If the legacy UI entrypoint has no attached orchestrator object, the UI reads the existing `settings.live_trade` flag as a compatibility execution-mode fallback; it does not set `order_allowed` or `real_order` directly.
