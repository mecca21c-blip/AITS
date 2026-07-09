# AITS Live ON Runtime After Preflight Stage Trace v1

Goal: distinguish UI ON, ON preflight, runtime start request, runner start, live gate, and order path reachability after a user presses ON.

This proof is diagnostic only. It must not force candidates, unlock gates, RiskGuard, LivePreflight, ExecutionBridge, OrderService, OrderAdapter, or any exchange order call.

## Active Owners

- ON button handler: `app/ui/app_gui.py::MainWindow._on_toggle_run`
- ON button signal chain: `btn_run_toggle.toggled -> _on_toggle_run_toggled -> _on_toggle_run_toggled_impl -> _on_toggle_run`
- ON state trace writer: `MainWindow._log_live_on_button_state_trace`
- Preflight owner: `MainWindow._preflight_check`
- Runtime stage trace prefix: `[AITS][RuntimeState]`
- Existing E2E parser: `tools/runtime_smoke/aits_qt_smoke_harness.py::live-on-runtime-e2e-diagnostic-log-summary`

## Active Handler Instrumentation

`AITS-LIVE-ON-BUTTON-ACTIVE-HANDLER-INSTRUMENTATION-01` adds read-only trace
events to the active ON/OFF handler path:

- `[AITS][ON] event=handler_enter`
- `[AITS][ON] event=preflight_start`
- `[AITS][ON] event=preflight_result status=pass|fail`
- `[AITS][RuntimeState] event=start_requested`
- `[AITS][RuntimeState] event=start_result runtime_started=True|False`
- `[AITS][ON] event=off_requested`
- `[AITS][RuntimeState] event=stop_requested`
- `[AITS][RuntimeState] event=stop_result runtime_stopped=True|False`
- `[AITS][ON] event=handler_exception`

These events are instrumentation only. They do not change preflight,
RiskGuard, LivePreflight, unlock, order intent, or submit behavior.

## Runtime Provenance

`AITS-RUNTIME-ACTIVE-BUILD-AND-ON-WIDGET-PROVENANCE-TRACE-01` adds startup and
widget provenance markers:

- `[AITS][RuntimeProvenance] event=app_start`
- `[AITS][ONWidget] event=on_widget_bound`
- `[AITS][ONWidget] event=clicked_probe`
- `[AITS][ONWidget] event=toggled_probe`

Use `runtime-provenance-log-summary` before deeper order-path debugging when
ON clicks are not detected. If `RuntimeProvenance` is missing after restart,
suspect a stale build or different runtime entrypoint. If `on_widget_bound` is
present but click/toggle probes are missing, click ON in that same restarted
app and rerun the summary.

The summary treats the latest `RuntimeProvenance app_start` timestamp as the
fresh session boundary. Older ONWidget/ON probes are counted as
`old_probe_ignored_count` and are not used to decide whether the current
session click reached the handler.

ON signal wiring must keep one effective StopButton path: the `toggled(bool)`
and `clicked()` signals are connected to stored single-entry slots. Each slot
logs its probe event, applies a short duplicate-signal guard, records the
bridge/wrapper stage sequence, and forwards once into the active `_on_toggle_run`
runtime handler. Probe logging must live inside that entry path so it cannot
replace or bypass the handler chain.

The ON runtime contract is handler -> preflight -> runtime start. A failed
preflight must restore the toggle to OFF, emit `preflight_result status=fail`,
update the runtime status display, and return before any runtime start request.
A passed preflight emits `preflight_result status=pass` and may then request
runtime start while order submission remains behind the existing live gates.

## Stage Taxonomy

- `on_click_not_detected`: no ON button or handler trace found.
- `on_signal_not_connected_to_handler`: fresh click/toggle probes fired, but no
  handler or bridge stage was logged.
- `on_signal_bridge_not_connected`: fresh toggle probe fired, but no bridge
  stage was logged.
- `on_signal_bridge_not_invoked_after_probe`: bridge was recorded as connected,
  but a fresh toggle probe did not invoke the bridge.
- `on_handler_wrapper_not_forwarding`: `_on_toggle_run_toggled` was reached but
  did not forward to `_on_toggle_run_toggled_impl`.
- `on_handler_impl_not_forwarding`: `_on_toggle_run_toggled_impl` was reached
  but did not forward to `_on_toggle_run`.
- `on_checked_value_false`: `_on_toggle_run` was reached with the OFF branch.
- `on_run_early_return`: `_on_toggle_run` returned before preflight; inspect
  the logged blocker such as provider readiness or real guard cancellation.
- `on_handler_entered_but_preflight_not_started`: `_on_toggle_run` was reached
  on the ON branch but no preflight start was logged.
- `on_preflight_exception`: `_preflight_check()` raised before returning a
  pass/fail result.
- `on_handler_not_entered`: ON evidence exists, but the active handler entry trace is missing.
- `on_preflight_not_logged`: ON was seen, but preflight was not logged.
- `on_preflight_blocked`: preflight failed before a runtime start request.
  For provider blockers, inspect `ProviderReadinessSource`; a fresh confirmed
  generation can clear `provider_connection_check_needed` only when provider
  and key fingerprint match the current selected runtime provider.
- `on_preflight_passed_but_runtime_not_started`: preflight passed but no start request was logged.
- `runtime_start_requested_but_not_started`: start was requested but runner start was not confirmed.
- `runtime_started_but_order_allowed_false`: runner started, but live order gate still reports order not allowed.
- `runtime_started_order_allowed_true_but_real_order_false`: order gate opened but real order is still disabled.
- `order_intent_candidate_missing`: candidate/feed loop exists but no order intent candidate reached the router path.

## Harness Modes

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-trace --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-summary --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-harness-driven-click-run --observe-only
```

Both modes read recent logs only and keep:

- `actual_order=false`
- `provider_external_call_count=0`
- `submitted_count` as observed from logs
- `managed_pool_mutation=false`

## Interpretation

`CandidateFeedState` score updates can continue while ON/live order gates are closed. Treat that as a separate candidate/feed loop until runtime start and order-intent bridge logs prove otherwise.

## 2026-07-08 Provider Auto-Check Trace Fields

After-preflight summary recognizes `[AITS][ProviderReadinessAutoCheck]` lines and reports `provider_auto_check_attempted`, `provider_auto_check_success`, `provider_auto_check_reason`, `provider_auto_check_provider`, `provider_auto_check_key_fp`, `provider_ready_after_auto_check`, and `provider_external_call_count`. A pass through provider readiness can still fail later at balance/cap gates; that is no longer classified as provider readiness failure.
## 2026-07-08 - Feed And Balance Gate Fields

- After-preflight summary now mirrors E2E market-feed fields: `market_feed_ok`, `market_feed_source`, `market_feed_reason`, `latest_candidate_feed_total`, `latest_top_markets_count`, `latest_tickers_count`, and `latest_network_status`.
- It also mirrors balance/cap gate fields: `balance_gate_detected`, `available_krw`, `accounts_fetch_status`, `balance_fallback_reason`, `effective_cap_krw`, and `balance_gate_blocker`.
- A preflight failure after provider readiness can now be read as feed, balance, or cap state instead of a generic ON/preflight blocker.

## 2026-07-08 - Public Feed Recovery Fields

- After-preflight summary mirrors E2E public feed recovery fields: `latest_feed_recovery_seen`, `latest_feed_degraded_seen`, and `latest_public_feed_exception_type`.
- `market_feed_network_error` means public `/v1/market/all` or ticker HTTP/read path failed before usable rows were available.
- `market_feed_ticker_empty` and `market_feed_top_markets_empty` mean the read path returned no usable public rows without opening any order path.
- A later recovery render or non-stale score update should move classification past the earlier degraded feed blocker.

## 2026-07-08 - Network Profile Split Fields

- After-preflight summary now mirrors `runtime_network_profile_split_detected`, `market_feed_app_process_ok`, `market_feed_user_app_ok`, `user_app_process_detected`, `profile_split_result`, and `external_public_read_network_ok` from E2E diagnostics.
- These fields explain whether a public feed failure belongs to the harness environment, the observed app runtime profile, or a user-launched app profile.

## 2026-07-08 - Runtime Start And Observe-Only Candidate Contract

- Runtime start is now traced through `[AITS][RuntimeState]` with `start_pending_after_preflight`, `start_requested`, `start_result`, and `loop_status`.
- `CandidateFeedState` means the candidate/feed loop is alive; it is not by itself proof that the ON runtime start contract completed.
- Buy Ready rows can emit `[AITS][OrderIntentCandidate] event=candidate_detected observe_only=True` only as an observation contract. It must keep `router_called=False`, `riskguard_called=False`, `live_preflight_called=False`, `execution_called=False`, `order_allowed=False`, and `real_order=False`.
- After-preflight summaries expose `runtime_start_source`, `runtime_start_reason`, `runtime_start_result`, `candidate_loop_source`, `latest_buy_ready_count`, `order_intent_candidate_reason`, `order_intent_candidate_blocker`, and `order_intent_candidate_observe_only`.

## 2026-07-08 - Post-Preflight Start Path

- After `post_preflight_contract`, runtime start must emit exactly one of `start_requested`, `start_result`, or `start_skipped`.
- Paired `toggled`/`clicked` signals from one ON click are suppressed as `duplicate_suppressed reason=paired_toggled_clicked`.
- Summary fields include `post_preflight_contract_detected`, `start_requested_detected`, `start_request_count`, `start_result_status`, `start_skipped_reason`, and `duplicate_suppressed_count`.

## 2026-07-08 - RouterHandoff Observe-Only Boundary

- `[AITS][RouterHandoff] event=handoff_preview` is the only allowed bridge from an observe-only `OrderIntentCandidate` in this phase.
- The preview schema is `aits_router_handoff_preview.v1` and keeps `observe_only=True`, `router_apply=False`, `final_action_applied=False`, `submitted=0`, and `actual_order=False`.
- It is not a DecisionRouter final action and must not call RiskGuard, LivePreflight, ExecutionBridge, OrderService, or OrderAdapter.
- After-preflight summaries expose `router_handoff_preview_detected`, `router_handoff_schema`, `router_handoff_request_id`, `router_handoff_symbol`, `router_handoff_side`, `router_handoff_amount_krw`, `router_apply`, `final_action_applied`, and `router_validation_observe_only`.

## 2026-07-08 - RouterValidation Observe-Only Boundary

- `[AITS][RouterValidation] event=validation_preview` validates the RouterHandoff payload without calling `DecisionRouter.route()` or applying a final action.
- The preview schema is `aits_router_validation_preview.v1` and keeps `observe_only=True`, `router_apply=False`, `final_action_applied=False`, `submitted=0`, and `actual_order=False`.
- A passed preview stops at `first_blocker=router_validation_observe_only`; the next separated Goal may inspect RiskGuard/LivePreflight observe-only handoff.
- After-preflight summaries expose `router_validation_preview_detected`, `router_validation_schema`, `router_validation_request_id`, `router_validation_source_request_id`, `router_validation_status`, `router_validation_input_valid`, `router_validation_action_preview`, and `router_validation_confidence_preview`.

## 2026-07-08 - RiskGuard/LivePreflight Preview Boundary

- `[AITS][RiskGuardPreview] event=risk_preview` is the only allowed handoff after a passed RouterValidation preview in this phase.
- `[AITS][LivePreflightPreview] event=live_preflight_preview` is the only allowed handoff after a passed RiskGuard preview in this phase.
- Both previews are no-apply contracts: `riskguard_apply=False`, `live_preflight_apply=False`, `unlock_performed=False`, `submitted=0`, and `actual_order=False`.
- A blocked preview reports `riskguard_preview_blocked` or `live_preflight_preview_blocked`; a passed live preflight preview stops at `live_preflight_preview_observe_only`.

## 2026-07-08 - GuardedExecutionContract Preview

- `[AITS][GuardedExecutionContract] event=contract_preview` is emitted after LivePreflightPreview to explain the remaining user-controlled gates.
- The contract keeps `confirm_phrase_matched=False`, `unlock_performed=False`, `execution_allowed=False`, `execution_called=False`, `submitted=0`, and `actual_order=False`.
- When present after a blocked LivePreflightPreview, after-preflight summary reports `first_blocker=live_order_approval_required` and `last_reached_stage=guarded_execution_contract_preview`.
- This is UI/log visibility only. It does not call ExecutionBridge, OrderService, OrderAdapter, or unlock services.

## 2026-07-08 - Guarded One-Shot Approval Trace

- After ON preflight passes, the app must emit `LiveTradingUX` status lines so
  the user can see that live monitoring started and what the app is waiting for.
- After a preview, the app exposes guarded approval outside the header ON/OFF area.
- The approval surface is a confirmation dialog or scoped panel, not a permanent header button.
- The dialog must show symbol, side, amount, required phrase, phrase input, and current blocker/status.
- The action must log `LiveOrderUX`, `LiveOrderApproval`, `LivePreflightApply`, `ExecutionBridge`, `OrderSubmit`, and `LiveOrderResult` stages.
- Without exact confirm phrase and one-shot unlock, the trace must stop before ExecutionBridge.
- After one submit attempt, the trace must end in `locked_after_submit` or `locked_after_failed_submit`; repeat and retry are not allowed.
- Runtime started with no waiting status, no dialog, and no guarded contract is
  classified as `live_order_ux_silent_failure`.

## 2026-07-08 - Normal ON Auto-Trading Trace

- Normal live ON flow is traced with `[AITS][LiveOrderPipeline]`, not the guarded one-shot approval dialog.
- `candidate_selected`, `router_validation_result`, `riskguard_result`, `execution_requested`, `execution_result`, and `order_submit_result` mark the current stage.
- A normal guarded-window order does not require one-shot confirm phrase or one-shot unlock, but it still must pass RiskGuard, LivePreflight, ExecutionBridge, OrderService, and OrderAdapter.
- After-preflight summary exposes `normal_live_order_pipeline_detected`, `live_pipeline_router_result`, `live_pipeline_riskguard_result`, `live_pipeline_execution_requested`, `live_pipeline_execution_result`, `live_pipeline_order_submit_result`, and `live_pipeline_blocker`.
- This prevents a normal ON run from being classified as missing approval UI.
## 2026-07-08 - Buy Ready Criteria Visibility

- ON runtime이 시작됐지만 매수 후보가 없을 때는 `[AITS][BuyReadyCriteria] event=evaluate`로 관리종목별 점수, 상태, threshold, blocker를 남긴다.
- 후보가 없으면 `[AITS][LiveOrderPipeline] event=no_candidate`를 남기며 `best_symbol`, `best_score`, `best_status`, `best_blocker`, `threshold`를 포함한다.
- UI 상태 표시는 `ON - 매수 후보 탐색 중`과 후보 없음 사유를 보여준다.
- 이 단계는 합성된 매수 준비 상태나 합성 주문 의도를 만들지 않으며 `submitted=0`, `actual_order=false`를 유지한다.

## 2026-07-08 - LIVE LOG Placement Contract

- The central LIVE LOG bar belongs at the top of the MAIN ANALYSIS CENTER, directly below the center title/toolbar.
- ON button sub-status widgets remain in their existing control area; raw bottom status text is hidden from the user-facing surface.
- Runtime, managed-pool, detail, and normal live pipeline status updates are appended to one 50-entry in-memory LIVE LOG buffer.
- Clicking the LIVE LOG opens the latest five entries. This is visibility only and does not trigger ON, approval, Router, RiskGuard, LivePreflight, Execution, or submit.
### Runtime contract active SSOT update

`runtime_contract_active` is now written from one GUI-side contract snapshot instead
of being inferred from a status-label string. The active contract requires:
ON state, preflight passed, runtime start result `started` or `already_running`,
candidate loop/runner evidence, and live execution mode. It does not depend on
`order_allowed` or `real_order`; those remain final submit permission fields.

When a Buy Ready candidate is blocked because the runtime contract is inactive,
the app logs `[AITS][RuntimeContract] event=candidate_blocked_by_runtime_contract`
with the explicit blocker reason. The after-preflight summary reports
`runtime_contract_active`, `runtime_contract_reason`, and
`runtime_contract_last_writer`.
## Normal Live Pipeline Stage Trace

After ON preflight passes, the stage trace recognizes normal live pipeline events from `[AITS][LiveOrderPipeline]`.
The trace must distinguish preview-only fields from actual normal-flow events:

- `router_validation_started/result` means the selected candidate reached DecisionRouter validation.
- `riskguard_started/result` means Router passed and RiskGuard was evaluated.
- `live_preflight_started/result` means the final pre-execution safety gate was evaluated.
- `execution_requested` must not appear before `live_preflight_result status=passed`.
- `order_duplicate_blocked blocker=duplicate_candidate_locked` is a duplicate candidate guard, not a duplicate submit by itself.

## Post-Submit Reflection Stage

After `order_submit_result status=submitted`, the GUI must request reflection only:

- `[AITS][TradeLogReflection]` records the submitted order into the TradeLog journal.
- `[AITS][PostSubmitHoldingsRefresh]` requests a read-only holdings refresh.
- `[AITS][PositionReflection]` requests InvestmentCenter position refresh.
- `[AITS][CandidateHoldingsGuard]` logs whether a later candidate has an already-known live position.

These events are not submit permission and must not call order retry paths.

## Candidate Holdings Guard Add-Position Policy

- A held symbol is not automatically blocked from a buy candidate.
- CandidateHoldingsGuard classifies candidates as `no_position_new_entry_candidate`, `has_position_add_position_candidate`, `has_position_add_position_blocked`, or `has_position_hold_management`.
- `target_weight_pct=0` or missing means AI dynamic allocation; it is not interpreted as a buy ban.
- Explicit `max_weight_pct > 0` is used as a weight cap. If expected weight after the order exceeds it, the candidate is blocked with `add_position_blocked_by_weight_cap`.
- Submitted duplicate locks are cooldown-based, not permanent; repeated immediate submit remains blocked.
- The stage summary exposes `expected_weight_after_order`, `candidate_order_amount_krw`, and `candidate_total_asset_estimate` so the user can see why an add-position candidate continued or stopped.
- Post-submit observation distinguishes the latest reflected request from older retained orders that predate reflection hooks.
## Add-position safety hardening

- 보유 종목 매수 후보는 신규 진입이 아니라 add-position 후보로 분류한다.
- AI dynamic allocation은 유지하지만 안전 기본값을 항상 적용한다:
  - `symbol_add_position_cooldown_sec=3600`
  - `symbol_max_position_weight_pct=30.0`
  - `symbol_add_position_window_minutes=360`
  - `symbol_add_position_window_amount_krw=20000`
  - `global_add_position_window_amount_krw=40000`
- `expected_weight_after_order=(current_position_value_krw+order_amount_krw)/total_asset_krw*100`으로 계산한다.
- 차단 사유는 `[AITS][AddPositionPolicy]`와 LIVE LOG 한국어 메시지에 남긴다.
- BERA 감사에서 확인된 30분 반복 추가매수는 새 정책 기준으로 cooldown/window/weight cap 중 하나에 의해 차단 가능해야 한다.
## LIVE LOG User-Facing History

- LIVE LOG의 한 줄 상태는 최신 `message_ko`만 표시한다.
- 클릭하면 별도 팝업 대신 MAIN ANALYSIS CENTER 내부에서 최근 5개 로그가 최신순으로 펼쳐진다.
- `add_position_blocked_by_weight_cap`, `candidate_selected`, `order_blocked` 같은 raw event/blocker는 내부 분석용으로만 보존하고, 화면에는 한국어 운용 메시지와 한국어 차단 사유를 표시한다.
- 공통설정 운용 로그는 동일 formatter를 사용해 최근 50개 히스토리를 최신순으로 제공한다.
