# AITS Runtime Smoke Harness v1

## Purpose

The Qt smoke harness provides a screenshot-free way to inspect the live AITS
widget tree when Windows screenshot capture or Computer Use click automation is
unavailable.

It is a test infrastructure tool only. It must not run during normal
production startup.

## Entry Point

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-read
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-navigation
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode save-probe
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
```

Reports are written to:

```text
data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json
```

Reports are UTF-8 JSON without a BOM. The harness normalizes report values to
JSON-safe primitives before writing: strings keep Korean and UI symbols, unsafe
control characters and invalid surrogate code points are replaced or removed,
paths are stored as strings, non-finite floats become `null`, and unknown
objects are reduced to safe `repr(...)` text. The same sanitized report is
printed to stdout.

## Modes

- `dry-read`: creates the real Qt main window in a guarded harness process,
  reads objectName/property selectors, label text, row counts, latest trade-log
  row text, and safety state. It does not click buttons.
- `dry-navigation`: performs the same read and switches tabs through the bottom
  navigation selectors. It does not click `AI 분석 새로고침`.
- `provider-smoke`: reserved for a later explicit runtime-smoke Goal. It is
  blocked unless `--allow-provider-calls` is supplied.
- `save-probe`: switches to the trade-log context, verifies the footer save
  selector, calls the trade-log persistence handler directly, and records
  save proof without clicking AI refresh or making provider calls.
- `riskguard-proof`: runs synthetic dry-run order-candidate fixtures against
  `app/services/risk_guard.py`. It does not create provider calls, click AI
  refresh, submit orders, or require a Qt window.
- `riskguard-active-path-proof`: creates the real Qt window, runs one guarded
  orchestrator cycle without clicking AI refresh, and verifies that
  `RiskGuardActivePath` metadata/log proof is produced before the disabled
  order adapter boundary.
- `riskguard-active-path-candidate-proof`: injects deterministic dry-run
  candidates into the app execution path and verifies RiskGuard metadata
  reaches `ActionItem` and `ExecutionBridge`.
- `live-preflight-locked-proof`: evaluates the final live-order preflight lock
  with deterministic fixtures. It does not create paper trading, virtual
  trading, mock processors, provider calls, or order submissions.
- `live-one-shot-unlock-contract-proof`: validates the one-shot unlock
  contract, consume/reuse blocking, duplicate lock blocking, and valid unlock
  preflight input without submitting orders.

## Safety Rules

- Default modes block provider HTTP POST calls.
- The harness skips startup provider verification inside the harness process.
- `AI 분석 새로고침` is located but never clicked in dry modes.
- Order-related UI or service calls are not part of the harness.
- Any report containing `AITS ON`, `Live`, `submitted=1`,
  `order_allowed=True`, `real_order=True`, or order bridge keywords is NO-GO.

## Stable Selectors

The harness prefers Qt `objectName` and falls back to `smokeObjectName`
properties where existing object names are already used by stylesheets.

Core selectors include:

- `main_window_aits`
- `lbl_aits_power_state`
- `lbl_aits_safety_state`
- `lbl_selected_ai_engine`
- `lbl_applied_ai_engine`
- `lbl_provider_connection_state`
- `cmb_ai_provider`
- `tab_aits_managed`
- `tab_trade_log`
- `tab_investment`
- `tab_ai_policy_center`
- `tab_common_settings`
- `tbl_ai_managed`
- `btn_ai_analysis_refresh`
- `btn_ai_status_refresh`
- `tbl_trade_log`
- `pnl_trade_log_detail`
- `btn_trade_log_save`
- `btn_manual_sell_all`

## Provider Calls

The harness does not add automatic GPT, Gemini, OpenAI, Gemini, Ollama, or
other external AI calls. Provider runtime smoke must be run only by a later Goal
that explicitly permits the exact provider and call count.

## Provider-Smoke CLI

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-smoke --allow-provider-calls --provider local --max-provider-calls 1
```

Arguments:

- `--provider local|gpt|gemini`: required for provider-smoke.
- `--max-provider-calls N`: defaults to `1`; values greater than one are blocked.
- `--target-symbol KRW-...`: optional managed-row target.
- `--timeout-sec N`: maximum wait for snapshot and Journal proof.
- `--wait-after-click-sec N`: initial event-pump delay after the single click.
- `--no-click`: select provider and target only; do not click AI refresh.

Safety behavior:

- Provider-smoke refuses to run without `--allow-provider-calls` and `--provider`.
- Provider-smoke performs at most one AI refresh click.
- LOCAL provider-smoke expects zero external OpenAI/Gemini request markers.
- GPT and Gemini provider-smoke must be run only by a Goal that explicitly allows
  the exact provider and call count.
- Reports include provider branch delta, external cost-provider request delta,
  selected symbol, latest decision group id, snapshot/Journal proof flags,
  latest trade-log row, detail excerpt, duplicate detection, and order-risk flags.

`--no-click` may be used without `--allow-provider-calls` to validate the
provider-smoke report schema while network guards remain installed:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-smoke --provider local --no-click
```

## Report JSON Validation

PowerShell:

```powershell
Get-Content -Raw -Encoding UTF8 data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json | ConvertFrom-Json
```

Python:

```powershell
python -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8')); print('OK')" data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json
```

Report validation must not require provider calls. Use `dry-read`,
`dry-navigation`, or provider-smoke `--no-click` for schema checks.

## RiskGuard-Proof

Use this mode before any dry-run or small-money execution work:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
```

The mode validates seven synthetic candidates:

- `allowed_small_buy`
- `blocked_max_order`
- `blocked_position_limit`
- `blocked_daily_loss`
- `blocked_emergency_stop`
- `blocked_invalid_symbol`
- `blocked_stale_price`

The report includes:

- `riskguard_fixture_count`
- `riskguard_pass_count`
- `riskguard_fail_count`
- `riskguard_results`
- `provider_call_markers`
- `external_cost_call_delta`
- `submitted_detected`
- `order_risk_detected`
- `real_order_detected`

RiskGuard uses `risk_allowed=True` for a dry-run policy pass. It keeps
`submitted=0`, `order_allowed=False`, and `real_order=False` for both allowed
and blocked fixtures. A passing RiskGuard fixture is not live-order permission.

## RiskGuard Active Path Proof

Use this mode after RiskGuard integration changes:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-proof
```

The mode keeps network/provider guards installed, builds the real UI, then runs
one orchestrator dry-run cycle. It expects one of two safe outcomes:

- `pass`: a runtime candidate was evaluated and RiskGuard metadata was attached.
- `partial`: no execution candidate existed, but a `no_candidate` active-path
  proof was emitted.

The report includes:

- `riskguard_active_path_checked`
- `riskguard_active_path_events`
- `latest_riskguard_event`
- `riskguard_candidate_seen`
- `risk_allowed`
- `risk_blocked_reason`
- `riskguard_active_path_log_markers`

The mode must keep provider call markers at zero and must keep `submitted=0`,
`order_allowed=False`, and `real_order=False`.

## RiskGuard Active Path Candidate Fixture Proof

Use this mode when the active path is wired but the live app state does not
produce an execution candidate:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
```

The mode injects deterministic dry-run `ActionItem` fixtures into the app
execution path, calls the same RiskGuard integration helper used by the
orchestrator, and verifies `ExecutionBridge` metadata passthrough. It does not
click AI refresh, call providers, call OrderAdapter, or submit orders.

Required fixtures:

- `allowed_small_buy_path`
- `blocked_max_order_path`

The report includes:

- `riskguard_active_path_candidate_fixture_count`
- `riskguard_active_path_candidate_pass_count`
- `riskguard_active_path_candidate_results`
- `actionitem_metadata_seen`
- `execution_bridge_metadata_seen`
- `order_adapter_called`
- `order_adapter_execution_mode`

PASS requires `risk_allowed` to match each fixture, `ActionItem` and
`ExecutionBridge` metadata to be present, provider call markers to remain zero,
and `submitted=0`, `order_allowed=False`, and `real_order=False`.

## Live Preflight Locked Proof

Use this mode before any live-order unlock work:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
```

This mode keeps the AITS principle of one real-order path. It does not add paper
mode, virtual trading, or mock trading processors. It evaluates the real-order
preflight lock with deterministic fixtures and keeps every result locked. It
does not click AI refresh, does not call GPT/Gemini, does not call OrderAdapter
live execution, and does not call OrderService.

The report includes:

- `live_preflight_fixture_count`
- `live_preflight_pass_count`
- `live_preflight_fail_count`
- `live_preflight_results`
- `order_service_place_order_called`
- `order_adapter_live_branch_entered`
- `order_adapter_execution_mode`
- `submitted_detected`
- `order_risk_detected`
- `paper_mode_created`
- `virtual_trading_created`
- `mock_trading_processor_created`

PASS requires every preflight fixture to keep `locked=true`, `allowed=false`,
`submitted=0`, `order_allowed=false`, and `real_order=false`. Provider and
external-cost call markers must remain zero.

## Live One-Shot Unlock Contract Proof

Use this mode before any minimum real-order test:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
```

This mode validates the one-shot unlock contract only. It does not create paper
mode, virtual trading, simulation processors, or mock trading processors. It
does not call providers, does not enter the OrderAdapter live branch, and does
not call OrderService.

Fixtures:

- `no_unlock`
- `invalid_confirm_token`
- `amount_exceeds_unlock_cap`
- `expired_unlock`
- `valid_unlock_preflight_pass_but_no_order_submit`
- `consumed_unlock_reuse`
- `duplicate_lock_reuse`

The valid fixture may report `allowed_for_preflight=true`; that is not order
permission. PASS still requires `submitted=0`, `order_allowed=false`,
`real_order=false`, and `order_service_place_order_called=false`.

Report fields include:

- `one_shot_unlock_fixture_count`
- `one_shot_unlock_pass_count`
- `one_shot_unlock_fail_count`
- `one_shot_unlock_results`
- `valid_unlock_seen`
- `consumed_reuse_blocked`
- `duplicate_reuse_blocked`
- `order_service_place_order_called`
- `order_adapter_live_branch_entered`

## Minimum Real Order Preflight Review

Before any future minimum real-order attempt, run and record:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-read
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-navigation
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
```

The review plan lives at
`app/docs/aits_live_minimum_real_order_test_plan_v1.md`. It does not run an
order; it defines the single allowed future candidate, the hard cap, the
one-shot confirmation phrase, duplicate lock, failure handling, and immediate
relock policy.

Any provider call marker, order-risk marker, `submitted=1`,
`order_allowed=true`, or `real_order=true` before the future real-order Goal is
NO-GO.

## Save-Probe

Use this mode before persistence/restart smoke:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode save-probe
```

The probe verifies `btn_trade_log_save`, navigates to the trade-log context, and
then calls the same trade-log save handler used by the footer save dispatcher.
It intentionally avoids the modal success message that can block automation when
the button is clicked directly.

Save-probe report fields include:

- `save_button_found`
- `save_handler_entered`
- `save_completed`
- `save_elapsed_ms`
- `save_log_start_delta`
- `save_log_finish_delta`
- `trade_log_row_count_before`
- `trade_log_row_count_after`
- `latest_row_before`
- `latest_row_after`
- `journal_before`
- `journal_after`
- `provider_call_delta`
- `external_cost_call_delta`

PASS requires the save handler to return within 10 seconds, a finish log to be
observed, no provider-call delta, unchanged latest trade-log row semantics, and
no order-risk markers. A direct button-click path may show a success
`QMessageBox`; that is a UI feedback path, not a persistence requirement.

## Manual Order UI Safety

The harness reports manual high-risk order controls without clicking them.
`manual_order_buttons` includes found/visible/enabled state for selectors such
as `btn_manual_sell_all`. Any visible and enabled manual order button is treated
as an order-risk condition in dry-read and dry-navigation reports.

Manual sell, panic sell, liquidation, and emergency order controls must remain
disabled in Shadow/AITS OFF mode. Unlocking manual order UI requires a separate
high-risk Goal with RiskGuard, ExecutionBridge, OrderAdapter, and user
confirmation proof. The smoke harness must not click these controls.

## Trading Boundary

The harness does not modify Router, Execution, Order, RiskGuard, repository, or
trade DB behavior. Runtime safety remains observe-only with `submitted=0`,
`order_allowed=False`, and `real_order=False`.
