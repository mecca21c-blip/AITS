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

## Trading Boundary

The harness does not modify Router, Execution, Order, RiskGuard, repository, or
trade DB behavior. Runtime safety remains observe-only with `submitted=0`,
`order_allowed=False`, and `real_order=False`.
