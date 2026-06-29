# AITS Live Guarded Window Policy v1

## Purpose

This policy defines the contract for a future 2 hour live guarded trading
window. It does not start AITS, submit orders, cancel orders, sell, retry, or
create paper or virtual trading.

The guarded window is a real-order-path contract. The later runtime Goal may
open AITS ON only after this contract, RiskGuard, LiveOrderPreflight,
One-Shot/Window Unlock, duplicate lock, reconciliation, and emergency stop
proofs pass.

## No Paper Or Virtual Trading

AITS keeps one real order path. The guarded window contract does not introduce:

- paper mode
- virtual trading
- mock trading processors
- simulation trading processors

## Window Limits

The guarded window policy is fixed for the first 2 hour window:

- duration: `120` minutes
- symbol: `KRW-BTC`
- side: buy only
- per-order amount: `10000` KRW
- per-order hard cap: `12000` KRW
- total window cap: `20000` KRW
- maximum order count: `2`
- minimum order interval: `600` seconds
- sell allowed: false
- cancel allowed: false
- retry allowed: false
- emergency stop required: true
- incident stop required: true

Any larger cap, additional order, sell, cancel, retry, duplicate-lock bypass,
unknown-state retry, or missing emergency-stop proof must stop the window.

## Contract Owner

The contract owner is `app/services/live_guarded_window.py`.

The owner provides:

- `LiveGuardedWindowConfig`
- `LiveGuardedWindowState`
- `LiveGuardedWindowCheckResult`
- `LiveGuardedWindow.evaluate_window_start(...)`
- `LiveGuardedWindow.evaluate_order_attempt(...)`
- `LiveGuardedWindow.record_incident(...)`

The owner is a pure evaluator. It does not call providers, external APIs,
OrderService, OrderAdapter, UI controls, or a database.

## Incident Stop

The window must stop immediately when any configured guard fails. Incident
reports use:

`data/live_incidents/aits_live_2h_guarded_window_incident_YYYYMMDD_HHMMSS.md`

Smoke incident reports include `smoke` in the filename.

Incident reports must include the goal, trigger condition, severity, stop
status, AITS state, order count, total order amount, last order uuid/state,
balances when available, relock, duplicate lock, repeat block, provider call
count, log excerpt, report path, suspected cause, and next Goal.

On Windows, the harness first tries to open the report with Notepad. If opening
fails, it must still print and report the path.

## Preflight Proof Mode

The runtime harness mode is:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-preflight-proof --duration-min 120 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
```

The mode must not click AITS ON and must not submit, cancel, sell, or retry an
order. It verifies the guarded-window contract and creates a smoke incident
report to prove report creation and auto-open behavior.

Required fixtures:

- `valid_window_contract_locked_no_on`
- `blocked_per_order_cap_exceeded`
- `blocked_total_cap_exceeded`
- `blocked_max_order_count_exceeded`
- `blocked_min_interval_violation`
- `blocked_sell_attempt`
- `blocked_unknown_state_retry`
- `incident_report_auto_open_smoke`

## Order Path Cap Proof

Before the 2 hour runtime window, the live order path must be aligned with the
same guarded-window limits. The 5000 KRW one-shot order remains historical
evidence from the first live test. The guarded-window path uses:

- order unit: `10000` KRW
- per-order hard cap: `12000` KRW
- total window cap: `20000` KRW
- maximum order count: `2`
- minimum order interval: `600` seconds

The proof mode is:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-order-path-cap-proof --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
```

Required fixtures:

- `allowed_10000_buy_within_window_policy`
- `blocked_per_order_hard_cap_12001`
- `blocked_total_window_cap_30000`
- `blocked_max_order_count_3`
- `blocked_min_interval_300sec`
- `blocked_sell_attempt`
- `blocked_cancel_attempt`
- `blocked_retry_attempt`

The allowed fixture is policy proof only. It must still report
`order_allowed=false`, `real_order=false`, `submitted=0`, and
`place_order_call_count=0`.

## Future Runtime Window

The later `AITS-LIVE-2H-GUARDED-TRADING-WINDOW-01` Goal must still perform
fresh baseline checks before clicking AITS ON. This policy does not authorize
the runtime window by itself.

## Runtime Harness Mode

The runtime harness mode is:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window --confirm-phrase AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM --duration-min 120 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
```

Before the actual runtime Goal, the same mode must be proven with:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window --confirm-phrase AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM --duration-min 1 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600 --dry-run-no-on
```

`--dry-run-no-on` is the safety gate for harness preparation. In that mode the
harness may discover the AITS ON selector, run baseline proofs, run a short
monitoring loop, create and open an incident smoke report, and write a final
window report. It must not click AITS ON and must not place, cancel, sell, or
retry an order.

The AITS ON selector discovery currently prefers the `btn_run_toggle` attribute
and `StopButton` objectName. Discovery is report-only until the later explicit
runtime Goal removes `--dry-run-no-on`.

Smoke reports are written under:

- `data/runtime_smoke_reports/runtime_smoke_report_*.json`
- `data/live_window_reports/aits_live_2h_guarded_window_report_smoke_*.json`
- `data/live_window_reports/aits_live_2h_guarded_window_summary_smoke_*.md`
- `data/live_incidents/aits_live_2h_guarded_window_incident_smoke_*.md`

Required runtime smoke fields include `confirm_phrase_valid`,
`aits_on_selector_found`, `aits_on_clicked=false`, `place_order_call_count=0`,
`cancel_call_count=0`, `sell_call_count=0`, `retry_call_count=0`,
`provider_external_call_count=0`, `baseline_status`, `monitoring_loop_status`,
and `report_status`.

## Preflight Proof Result

Goal `AITS-LIVE-2H-GUARDED-WINDOW-CONTRACT-PREFLIGHT-01` produced:

- dry-read report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_090436_656524.json`
- reconciliation report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_090448_240109.json`
- guarded-window preflight report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_090531_235638.json`
- smoke incident report: `C:\AITS\data\live_incidents\aits_live_2h_guarded_window_incident_smoke_20260629_090531.md`

The proof passed all eight fixtures, did not click AITS ON, did not call
`place_order`, and did not call cancel, sell, retry, provider, paper, virtual,
or mock trading paths.

## Order Path Cap Proof Result

Goal `AITS-LIVE-2H-GUARDED-WINDOW-ORDER-PATH-CAP-ENABLE-01` aligned the live
order request boundary with the guarded-window policy:

- order path cap report: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091912_905642.json`
- guarded-window preflight recheck: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091924_836839.json`
- dry-read recheck: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091942_915646.json`
- reconciliation recheck: `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091942_303291.json`

The cap proof passed all eight fixtures. The 10000 KRW buy candidate passed
GuardedWindow/RiskGuard/One-Shot Unlock/LiveOrderPreflight policy checks for a
future guarded window, but still reported `submitted=0`,
`order_allowed=false`, `real_order=false`, and `place_order_call_count=0`.
The 12001 KRW, total cap, order count, interval, sell, cancel, and retry
fixtures were blocked.

## Runtime Harness Smoke Result

Goal `AITS-LIVE-2H-GUARDED-WINDOW-RUNTIME-HARNESS-ENABLE-01` added the
`live-2h-guarded-window` CLI mode and verified it in `--dry-run-no-on` mode.
The smoke:

- accepted the guarded-window confirmation phrase
- validated the guarded-window config
- found the AITS ON selector without clicking it
- embedded read-only reconciliation, preflight, and order-path cap proofs
- ran a short monitoring loop
- generated and auto-opened a smoke incident markdown report
- wrote a final smoke JSON report and markdown summary
- reported zero AITS ON clicks and zero place/cancel/sell/retry calls

First smoke report:
`C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_103556_027624.json`

Live-window smoke report:
`C:\AITS\data\live_window_reports\aits_live_2h_guarded_window_report_smoke_20260629_103555_864057.json`
