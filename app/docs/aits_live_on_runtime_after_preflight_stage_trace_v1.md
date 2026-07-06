# AITS Live ON Runtime After Preflight Stage Trace v1

Goal: distinguish UI ON, ON preflight, runtime start request, runner start, live gate, and order path reachability after a user presses ON.

This proof is diagnostic only. It must not force candidates, unlock gates, RiskGuard, LivePreflight, ExecutionBridge, OrderService, OrderAdapter, or any exchange order call.

## Active Owners

- ON button handler: `app/ui/app_gui.py::MainWindow._on_toggle_run`
- ON state trace writer: `MainWindow._log_live_on_button_state_trace`
- Preflight owner: `MainWindow._preflight_check`
- Runtime stage trace prefix: `[AITS][RuntimeState]`
- Existing E2E parser: `tools/runtime_smoke/aits_qt_smoke_harness.py::live-on-runtime-e2e-diagnostic-log-summary`

## Stage Taxonomy

- `on_click_not_detected`: no ON button or handler trace found.
- `on_preflight_not_logged`: ON was seen, but preflight was not logged.
- `on_preflight_blocked`: preflight failed before a runtime start request.
- `on_preflight_passed_but_runtime_not_started`: preflight passed but no start request was logged.
- `runtime_start_requested_but_not_started`: start was requested but runner start was not confirmed.
- `runtime_started_but_order_allowed_false`: runner started, but live order gate still reports order not allowed.
- `runtime_started_order_allowed_true_but_real_order_false`: order gate opened but real order is still disabled.
- `order_intent_candidate_missing`: candidate/feed loop exists but no order intent candidate reached the router path.

## Harness Modes

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-trace --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-summary --observe-only
```

Both modes read recent logs only and keep:

- `actual_order=false`
- `provider_external_call_count=0`
- `submitted_count` as observed from logs
- `managed_pool_mutation=false`

## Interpretation

`CandidateFeedState` score updates can continue while ON/live order gates are closed. Treat that as a separate candidate/feed loop until runtime start and order-intent bridge logs prove otherwise.
