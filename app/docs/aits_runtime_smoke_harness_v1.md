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
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimum-real-order-test --confirm-phrase <exact-confirm-phrase>
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-order-post-trade-reconciliation --order-uuid <order-uuid>
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-preflight-proof --duration-min 120 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-order-path-cap-proof --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window --confirm-phrase AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM --duration-min 1 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600 --dry-run-no-on
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
- `provider-smoke`: runs one explicit provider refresh only when
  `--allow-provider-calls` is supplied. For GPT/Gemini it reports
  `generation_response_confirmed`, `generation_response_confirmed_reason`,
  `generation_request_id`, `generation_status`, `generation_status_text`,
  `generation_attempt_count`, `generation_max_attempts`,
  `generation_retry_used`, `generation_fresh`, `generation_stale`,
  `stale_reason`, `provider_selected`, `provider_actual`, `fallback_used`,
  `http_status`, `response_id_present`, `token_usage_present`, and
  `ui_generation_status_text`. A configured key or auth-ready state is not a
  generation response proof; only a provider success log or equivalent
  generation record may confirm the response. If GPT/Gemini fails and LOCAL is
  used, the report keeps the selected provider and records the fallback reason.
  Stale previous responses must not set `generation_response_confirmed=true`.
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
- `live-minimum-real-order-test`: high-risk one-shot KRW-BTC buy test mode.
  It refuses to run without the exact confirm phrase, checks Upbit account/key
  readiness, KRW balance, ticker freshness, RiskGuard, One-Shot Unlock, and
  LiveOrderPreflight before reaching the single allowed order-service call.
  If any pre-order condition fails, it stops without submitting an order.
  The 2026-06-29 funded retry produced report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_045413_391177.json`
  with one `KRW-BTC` buy request, HTTP `201`, submitted count `1`, immediate
  unlock consumption, relock, duplicate lock, and repeat-order block proof.
- `live-order-post-trade-reconciliation`: read-only order-status and balance
  reconciliation for the single known live order uuid. It performs Upbit GET
  order lookup and account balance lookup only. It does not place, cancel, sell,
  or retry orders. The first reconciliation report was
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_050259_116145.json`.
  The final audit recheck used
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_051206_771216.json`
  and again confirmed zero place/cancel/sell/retry calls.
  Interpret raw exchange state using
  `app/docs/aits_live_order_state_policy_v1.md`; the first live order is
  classified as `partially_filled_cancelled_remainder`, not as a simple failed
  cancellation.
  Restart persistence proof later used dry-read report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052941_859748.json`
  and reconciliation report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052957_387433.json`;
  relock, duplicate lock, and repeat-order blocking remained true.
  The 60 minute post-order passive proof used final dry-read report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064924_106372.json`
  and final reconciliation report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064935_630819.json`;
  no place/cancel/sell/retry, provider external generation, or order-risk marker
  appeared during the passive window.
  The read-only reconciliation hardening report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_081228_882109.json`
  adds `raw_order_state`, `normalized_order_state`,
  `normalized_order_action`, `reconciliation_reason`, structured
  `balance_reconciliation`, explicit place/cancel/sell/retry call counts, and
  `no_retry_enforced`. For the first order uuid it reports raw state `cancel`,
  normalized state `partially_filled_cancelled_remainder`, reconciliation
  status `reconciled`, zero balance delta, relock true, duplicate lock true,
  repeat block true, and zero place/cancel/sell/retry calls.
- `live-2h-guarded-window-preflight-proof`: evaluates the future 2 hour live
  guarded window contract without clicking AITS ON and without placing,
  cancelling, selling, or retrying orders. It verifies the 120 minute duration,
  10000 KRW per-order amount, 12000 KRW per-order hard cap, 20000 KRW total
  cap, max order count 2, 600 second interval, sell/cancel/retry disabled
  policy, and incident-stop behavior. It also creates and opens a smoke
  incident markdown report.
- `live-2h-guarded-window-order-path-cap-proof`: verifies that the future
  guarded-window order path uses the same 10000 KRW order unit, 12000 KRW
  per-order hard cap, 20000 KRW total cap, max order count 2, and 600 second
  interval across GuardedWindow, RiskGuard, One-Shot Unlock,
  LiveOrderPreflight, OrderAdapter metadata, and OrderService request scope.
  It does not click AITS ON and does not call `OrderService.place_order`.
- `live-2h-guarded-window`: runtime harness mode for the later guarded-window
  execution Goal. In `--dry-run-no-on` smoke mode it validates the confirm
  phrase, guarded-window config, baseline dry-read state, read-only
  reconciliation, guarded-window preflight proof, order-path cap proof, AITS ON
  selector discovery, monitoring loop wiring, incident markdown creation and
  Notepad auto-open, and final live-window report creation. It must report
  `aits_on_clicked=false`, zero order/cancel/sell/retry calls, and zero
  provider external calls. Removing `--dry-run-no-on` is allowed only in the
  later explicit live-window Goal.

## Safety Rules

- Default modes block provider HTTP POST calls.
- The harness skips startup provider verification inside the harness process.
- `AI 분석 새로고침` is located but never clicked in dry modes.
- Order-related UI or service calls are not part of the harness.
- Any report containing `AITS ON`, `Live`, `submitted=1`,
  `order_allowed=True`, `real_order=True`, or order bridge keywords is NO-GO.
  The only exception is the explicit `live-minimum-real-order-test` report,
  where `real_order=True` and `submitted_count=1` may appear only for the one
  sanctioned KRW-BTC buy response.
- `live-2h-guarded-window-preflight-proof` must always report
  `aits_on_clicked=false`, `place_order_call_count=0`, `cancel_call_count=0`,
  `sell_call_count=0`, and `retry_call_count=0`.
- `live-2h-guarded-window-order-path-cap-proof` must always report
  `allowed_10000_policy_passed=true`, `aits_on_clicked=false`,
  `place_order_call_count=0`, `cancel_call_count=0`, `sell_call_count=0`, and
  `retry_call_count=0`. The 5000 KRW amount remains historical evidence for
  the first one-shot order only; it is not the guarded-window order unit.
  The first cap-alignment report was
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091912_905642.json`
  and passed all eight fixtures without an order call.
- `live-2h-guarded-window --dry-run-no-on` must always report
  `confirm_phrase_valid=true`, `aits_on_selector_found=true`,
  `aits_on_clicked=false`, `place_order_call_count=0`, `cancel_call_count=0`,
  `sell_call_count=0`, `retry_call_count=0`,
  `provider_external_call_count=0`, and a smoke incident markdown path. It
  writes the normal runtime smoke JSON plus
  `data/live_window_reports/aits_live_2h_guarded_window_report_smoke_*.json`
  and a matching markdown summary.

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
- AITS run selector discovery prefers the `btn_run_toggle` attribute and the
  `StopButton` objectName. Discovery is read-only unless a later live-window
  Goal explicitly removes `--dry-run-no-on`.

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
- `--max-provider-calls N`: defaults to `1`; values greater than three are
  blocked. LOCAL still requires one call or fewer. GPT/Gemini may use `2` for
  retry-lifecycle proof when the Goal explicitly allows it.
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
- GPT/Gemini provider-smoke maps `--max-provider-calls` to the generation retry
  budget. `1` means no retry; `2` permits one provider-generation retry. This is
  not an order retry and must not call order services.
- Reports include provider branch delta, external cost-provider request delta,
  selected symbol, latest decision group id, snapshot/Journal proof flags,
  latest trade-log row, detail excerpt, duplicate detection, and order-risk flags.
- GPT/Gemini provider-smoke uses a compact generation payload only for this
  explicit smoke mode. The normal runtime provider path is unchanged. For GPT,
  the compact smoke request records `compact_smoke=true`, `messages_count`,
  `message_chars`, `output_token_cap`, and `timeout_sec` in
  `[AITS][OpenAIProviderProof] event=request_attempt`. The timeout owner is the
  HTTP provider request; the Qt worker watchdog remains later than that request
  timeout. A successful GPT smoke requires HTTP success, response id presence,
  token usage presence, `provider_actual=gpt`, `fallback_used=false`, and
  `generation_response_confirmed=true`.
- GPT timeout handling must distinguish request timeout from stale generation
  state. Timeout failures should keep the selected provider, record fallback
  reason clearly, and show timeout status instead of reverting to a generic
  unconfirmed response label. The 2026-06-29 timeout root fix verified GPT
  provider-smoke with report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_134523_490619.json`:
  `http_status=200`, response id present, token usage present,
  `provider_selected=gpt`, `provider_actual=gpt`, `fallback_used=false`,
  `generation_response_confirmed=true`, and UI status `생성 응답 확인됨`.

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

## Engine Readiness Fields

Dry-read and provider-smoke reports include the AITS ON engine-readiness
contract used by the UI gate:

- `engine_ready_for_run`
- `engine_ready_reason`
- `engine_not_ready_reason`
- `generation_response_confirmed`
- `generation_fresh`
- `generation_stale`
- `response_id_present`
- `token_usage_present`
- `provider_selected`
- `provider_actual`
- `fallback_used`
- `active_engine`
- `on_gate_expected_engine`
- `connection_state_simple`
- `connection_detail_text`

For GPT/Gemini, readiness requires a fresh confirmed generation response for
the selected provider with response-id or token-usage proof and no LOCAL
fallback. Auth-only, timeout, fallback, and stale preview states must remain
not-ready. Engine readiness is not order permission. `connection_state_text`
uses the simplified user-facing state (`연결중`, `연결됨`, `연결오류`), while
`connection_detail_text` may retain diagnostic context.

## Trading Boundary

The harness does not modify Router, Execution, Order, RiskGuard, repository, or
trade DB behavior. Runtime safety remains observe-only with `submitted=0`,
`order_allowed=False`, and `real_order=False`.

## Provider Startup Readiness Proof

`provider-startup-readiness-proof` verifies the startup/provider-apply readiness
path without clicking AITS ON and without orders:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-startup-readiness-proof --provider gpt --allow-provider-calls --max-provider-calls 1 --target-symbol KRW-BTC --timeout-sec 90
```

The mode enables `AITS_STARTUP_READINESS_PREFLIGHT=1` for the harness session,
keeps ordinary dry-read provider calls blocked, waits for the `startup_generation`
preflight, and reports:

- `startup_readiness_preflight_attempted`
- `generation_source`
- `generation_request_id`
- `generation_status`
- `connection_state_simple`
- `engine_ready_for_run`
- `active_engine`
- `provider_actual`
- `fallback_used`
- `external_cost_call_count`
- `provider_call_count_with_worker_markers`

PASS requires `connection_state_simple=연결됨`, fresh confirmed generation proof,
matching active provider, no fallback, provider external calls within budget, and
no order-risk markers.
