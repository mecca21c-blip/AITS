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
```

Reports are written to:

```text
data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json
```

## Modes

- `dry-read`: creates the real Qt main window in a guarded harness process,
  reads objectName/property selectors, label text, row counts, latest trade-log
  row text, and safety state. It does not click buttons.
- `dry-navigation`: performs the same read and switches tabs through the bottom
  navigation selectors. It does not click `AI 분석 새로고침`.
- `provider-smoke`: reserved for a later explicit runtime-smoke Goal. It is
  blocked unless `--allow-provider-calls` is supplied.

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

## Trading Boundary

The harness does not modify Router, Execution, Order, RiskGuard, repository, or
trade DB behavior. Runtime safety remains observe-only with `submitted=0`,
`order_allowed=False`, and `real_order=False`.
