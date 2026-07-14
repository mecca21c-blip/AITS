# AITS Low Resource Runtime Stability v1

## Purpose

AITS uses a stability-first runtime profile so that ON startup does not launch provider work, chart rendering, table repaint, and ETA scheduling in one event-loop burst. The profile changes scheduling and presentation load only. It does not change market facts, AI payload data, order policy, or execution safety.

## Default Profile

`runtime_resource.low_resource_mode_enabled` defaults to `true` for development and packaged deployments. The default profile uses:

- 300 ms runtime-start yield
- 15 second initial AI warm-up
- 20 second ETA scheduler warm-up
- 60 second chart warm-up and background chart rendering disabled
- 5 second table refresh interval
- 2 second batched LIVE LOG flush
- 500 retained LIVE LOG lines
- 80 displayed candles
- 4 Managed Pool indicator/score rows per cycle
- optional 30 second process resource snapshots

Users with measured headroom may opt into a higher-performance profile through settings. The application must not infer or force that choice.

## Startup Staging

The ON sequence records `[AITS][StartupLoad]` events and yields to the Qt event loop before runtime engine start. Initial AI work, ETA scheduling, and chart rendering have separate warm-up gates. A delayed gate means the work remains pending; it does not create fallback market data or a synthetic decision.

The ON click itself follows the separate nonblocking startup contract. Account preflight runs in a worker, provider readiness reads a verified snapshot without an ON-time network call, and a 30 second watchdog restores the UI after a failed or stalled stage.

## Rendering And Logs

Chart data updates remain independent from rendering. Hidden charts are skipped, startup renders are delayed, displayed candles are capped, low-resource subplots are omitted, and Matplotlib uses `draw_idle()` for coalesced repaint. Low-resource defaults block background chart rendering entirely; a user chart option change is the explicit manual render path. Managed Pool and market tables use minimum repaint intervals while their backing data continues to refresh.

Runtime file logging remains immediate. The visible LIVE LOG is buffered, adjacent duplicate messages are counted, flushed in batches, and trimmed to the configured line limit. Raw prompts, keys, and request bodies are not eligible for the visible timeline.

Full dataset curation, feature regeneration, model training, and calibration are manual-only while live runtime is active. The factual outcome checkpoint writer remains enabled. This separates live evidence collection from CPU, memory, and disk intensive learning jobs.

## Runtime Backpressure

Initial AI and ETA scheduler calls are held behind their startup gates. Managed Pool score computation uses a rotating batch when the target set is larger than the configured indicator batch. Deferred rows retain their last observed state and are processed on following cycles. This is scheduling backpressure, not a trading signal or a data substitute.

## Resource Health And Degradation

When `psutil` is available, AITS records process CPU and memory. Otherwise those values remain unknown and UI timing counters still work. High resource pressure degrades presentation first:

1. chart redraw and subplots
2. non-visible chart work
3. table repaint frequency
4. visible LIVE LOG flush frequency

The following paths are never degraded: holdings snapshots, valuation consistency, AI decision state, outcome tracking, order reconciliation, SellUnitGuard, RiskGuard, LivePreflight, ExecutionBridge, OrderService, and OrderAdapter safety.

## Validation

Run the structural, observe-only check without starting the app:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode low-resource-runtime-stability-v1-summary --observe-only
```

The first user runtime check should keep the default low-resource profile, start ON once, and observe startup and resource logs before increasing any render frequency.
