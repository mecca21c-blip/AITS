# AITS ON Button Nonblocking Startup Stability v1

## Root Cause

The legacy ON slot performed provider readiness, optional provider network verification, account preflight, settings synchronization, and modal validation before returning to the Qt event loop. Account preflight can perform a private API request. A slow network or provider call therefore made the button appear unchanged and could make the entire desktop feel frozen.

## Fast-return Contract

The active ON path now performs only these operations in the click stack:

1. reject a duplicate startup request
2. render the STARTING state
3. start the startup watchdog
4. schedule the first stage with `QTimer.singleShot(0, ...)`
5. return to the Qt event loop

`[AITS][ONStartup] event=on_click_handler_returned` records the elapsed time. More than 300 ms is a warning. No holdings, market, candle, chart, provider network, AI, or account request is executed in the click stack.

## Staged Startup

The sequence has twelve stages:

1. startup prepare
2. runtime contract pending state
3. configuration snapshot
4. account and balance preflight
5. holdings refresh ownership handoff
6. Managed Pool synchronization ownership handoff
7. market refresh ownership handoff
8. provider readiness snapshot
9. runtime loop enable
10. initial AI scheduling
11. ETA scheduler scheduling
12. delayed UI rendering scheduling

The account stage runs in `AITSOnStartupStageWorker`. Provider readiness uses an existing verified connection snapshot and does not perform automatic provider HTTP verification during ON startup. Holdings, Managed Pool, and market work remain owned by the runtime loop and are not duplicated in the UI thread.

## Watchdog And Recovery

The default overall timeout is 30 seconds. Stage limits are 3 to 10 seconds. The watchdog logs a heartbeat every second while the Qt event loop remains responsive. On timeout or failure, AITS disables trading, restores the button, displays the Korean START_FAILED message, and ignores late results from the expired startup token.

## UI States

- `OFF`: runtime is not requested.
- `STARTING`: startup is scheduled and the button is temporarily disabled.
- `ON_ACTIVE`: the runner acknowledged startup and post-start scheduling completed.
- `START_FAILED`: startup failed or timed out and the button was restored.
- `STOPPING`: shutdown is in progress.

Only Korean user-facing messages are rendered. Internal state names remain diagnostic metadata.

## Safety Boundary

This change does not alter AI actions, order intent, RiskGuard, LivePreflight, ExecutionBridge, OrderService, OrderAdapter, reconciliation, or valuation checks. Deferred UI rendering never implies deferred trading safety.

## Validation

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode on-button-nonblocking-startup-stability-v1-summary --observe-only
```

The structural summary does not click ON. A subsequent user-operated runtime verification must confirm `on_click_handler_elapsed_ms <= 300` and observe the final startup state.
