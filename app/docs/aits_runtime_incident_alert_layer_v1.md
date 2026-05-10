# AITS Runtime Incident & Alert Layer v1

## Scope

This layer promotes anomaly, drift, runtime blocked, cooldown, degraded, schema,
and safety states into local runtime incidents. It is a diagnostics layer only.

It does not execute trades, create UI widgets, import PySide6, or send external
alerts through webhook, email, Slack, or any other channel.

## Runtime Incident

`app/services/ai_runtime_incident.py` defines `AIRuntimeIncident`.

Fields:

- `incident_id`
- `provider`
- `session_id`
- `incident_type`
- `severity`
- `title`
- `description`
- `detected_at`
- `active`
- `acknowledged`
- `metadata`

Incident types include `anomaly_detected`, `confidence_drift`,
`scenario_drift`, `runtime_blocked`, `cooldown_active`, `degraded_runtime`,
`schema_instability`, and `safety_violation`.

Severity values are `info`, `warning`, `error`, and `critical`.

## Incident Store

`app/services/ai_runtime_incident_store.py` provides
`AIRuntimeIncidentStore`.

The store is memory-only and supports append, list, latest, acknowledge,
resolve, clear, and summary generation.

Summary fields:

- `total`
- `active`
- `critical`
- `providers`
- `by_type`

It does not write files, use a database, or call external APIs.

## Alert Builder

`app/services/ai_runtime_alert_builder.py` converts runtime diagnostics into
local incidents.

Rules:

- `anomaly_detected=True` -> `anomaly_detected`
- `confidence_drift=True` -> `confidence_drift`
- `scenario_drift=True` -> `scenario_drift`
- `safety_blocked=True` -> `runtime_blocked`
- `degraded=True` -> `degraded_runtime`
- `cooldown_blocked=True` -> `cooldown_active`
- `schema_valid=False` -> `schema_instability`
- `submitted > 0` -> `safety_violation` with `critical`

No external alert is sent.

## Incident Report

`app/services/ai_runtime_incident_report.py` provides
`AIRuntimeIncidentReportBuilder`.

Report fields:

- `total_incidents`
- `active_incidents`
- `critical_incidents`
- `dominant_incident_type`
- `highest_severity`
- `summary_line`
- `metadata`

## Escalation

`app/services/ai_runtime_incident_escalation.py` maps incident severity counts
to local escalation labels.

Rules:

- any critical incident -> `긴급`
- error count >= 3 -> `높음`
- warning count >= 5 -> `중간`
- otherwise -> `낮음`

The escalation result is local metadata only and does not trigger outbound
notification.

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps the existing
observation/session/UI/event flow and attaches:

- `runtime_incidents_ready`
- `runtime_incidents`
- `runtime_incident_report`
- `runtime_escalation`
- `runtime_alert_feed`

Incident attach failures do not replace or block the original one-shot result.

## Safety Contract

The incident layer must preserve:

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
providers, perform provider failover, or send external alerts.

Keys, secrets, tokens, raw prompts, and raw responses must not be stored.
