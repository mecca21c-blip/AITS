# AITS Runtime UI Preparation v1

## Scope

This layer prepares runtime/session/observation/guard/quality output for a
future UI. It does not create widgets, import PySide6, modify `app_gui.py`, or
add any real UI tab.

## Runtime UI Bundle

`app/services/ai_runtime_ui_bundle.py` defines `AIRuntimeUIBundle` and
`AIRuntimeUIBundleBuilder`.

The bundle combines one-shot output, session report, observation report, guard
report, and quality score into a single UI-ready dataclass.

Fields:

- `provider`
- `session_id`
- `status`
- `diagnosis`
- `summary_line`
- `badges`
- `health_label`
- `observation_summary`
- `quality_score`
- `confidence_drift`
- `scenario_drift`
- `anomaly_detected`
- `degraded`
- `cooldown_blocked`
- `metadata`

## Formatter

`app/services/ai_runtime_ui_formatter.py` converts a bundle into a compact dict:

- `header`
- `status_line`
- `badges`
- `risk_level`
- `compact_rows`
- `metadata`

Risk levels:

- `정상` -> `low`
- `관찰 필요` -> `medium`
- `불안정` or `런타임 불안정` -> `high`
- `차단 필요` -> `critical`

## Dashboard Summary

`app/services/ai_runtime_dashboard_summary.py` aggregates multiple bundles into
`AIRuntimeDashboardSummary`.

Fields:

- `total_providers`
- `healthy`
- `degraded`
- `cooldown_blocked`
- `avg_quality_score`
- `avg_confidence`
- `dominant_status`
- `summary_line`
- `metadata`

## Badge Builder

`app/services/ai_runtime_badge_builder.py` creates compact badges such as:

- `정상`
- `관찰 필요`
- `불안정`
- `쿨다운`
- `Drift`
- `Scenario Drift`
- `Anomaly`
- `연구모드`

## Status Color

`app/services/ai_runtime_status_color.py` maps runtime status to string color
tokens:

- `bg`
- `fg`
- `accent`

It does not use `QColor` or any UI framework object.

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps the existing
one-shot/session/observation/report flow and attaches:

- `runtime_ui_ready`
- `runtime_ui_bundle`
- `runtime_ui_formatted`
- `runtime_dashboard_summary`
- `runtime_badges`
- `runtime_status_colors`

This is attach-only data preparation. It does not change action, confidence, or
execution state.

## Safety Contract

The runtime UI preparation layer must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order API. It
must not alter `DecisionRouter` action behavior, create UI widgets, import
PySide6, modify `app/ui/*`, start background trading loops, auto-run multiple
providers, or perform provider failover.
