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

- After-preflight summary now mirrors `runtime_network_profile_split_detected`, `market_feed_app_process_ok`, and `external_public_read_network_ok` from E2E diagnostics.
- These fields explain whether a public feed failure belongs to the harness environment or the app runtime profile.
