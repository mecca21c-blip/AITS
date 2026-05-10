# AITS Runtime Snapshot & Export Preparation v1

## Scope

This layer wraps one-shot runtime output into an export-ready snapshot structure.
It does not write JSON, CSV, databases, UI widgets, or outbound messages.

## Runtime Snapshot

`app/services/ai_runtime_snapshot.py` defines `AIRuntimeSnapshot`.

Fields:

- `snapshot_id`
- `provider`
- `model`
- `symbol`
- `created_at`
- `session`
- `observation`
- `timeline`
- `incidents`
- `ui_bundle`
- `health`
- `safety`
- `metadata`

Metadata includes `shadow_only=True`, `real_order=False`, `submitted=0`,
`research_mode=True`, and `export_ready=True`.

## Snapshot Sanitizer

`app/services/ai_runtime_snapshot_sanitizer.py` recursively sanitizes dicts,
lists, and dataclasses.

Removed key families include:

- `api_key`
- `key`
- `secret`
- `token`
- `access_key`
- `refresh_token`
- `raw_prompt`
- `prompt`
- `raw_response`
- `full_response`
- `response_text`
- `raw_text`
- `authorization`
- `bearer`

The sanitizer only transforms in-memory values. It does not save files.

## Snapshot Builder

`app/services/ai_runtime_snapshot_builder.py` builds `AIRuntimeSnapshot` from a
one-shot result dictionary.

It groups:

- session fields and `session_report`
- observation report and formatted observation
- runtime timeline and event feed
- runtime incidents and alert feed
- runtime UI bundle and formatted UI payload
- guard/session/quality health fields
- safety flags fixed to research-only values

Sanitization is applied before the snapshot is returned.

## Export Payload

`app/services/ai_runtime_export_payload.py` defines
`AIRuntimeExportPayloadBuilder`.

Allowed formats:

- `json`
- `csv_preview`
- `text_preview`

The builder returns a payload dataclass only. It does not write files, send
network requests, or persist to a database.

## Snapshot Formatter

`app/services/ai_runtime_snapshot_formatter.py` converts snapshots into compact
UI/log-ready dictionaries:

- `title`
- `summary`
- `sections`
- `badges`
- `metadata`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps the existing
session/observation/event/incident/UI flow and attaches:

- `runtime_snapshot_ready`
- `runtime_snapshot`
- `runtime_export_payload`
- `runtime_snapshot_formatted`
- `runtime_export_safe`
- `runtime_export_redacted`

## Safety Contract

The snapshot layer must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order API. It
must not alter `DecisionRouter`, create UI widgets, import PySide6, modify
`app/ui/*`, write files, export CSV/JSON, use a database, send webhooks/email/
Slack, start background loops, auto-run providers, or perform provider failover.
