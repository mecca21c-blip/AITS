# AITS Runtime Export Writer Stub v1

## Scope

This layer introduces an export writer interface and stub behavior before any
real persistence implementation.

The writer never writes files in this goal. Directory creation is also disabled.
No JSON/CSV file is created.

## Export Writer Result

`app/services/ai_runtime_export_writer_result.py` defines
`AIRuntimeExportWriterResult`.

Fields:

- `attempted`
- `written`
- `path`
- `format`
- `reason`
- `bytes_planned`
- `bytes_written`
- `metadata`

Metadata includes `write_disabled=True`, `shadow_only=True`, `real_order=False`,
`submitted=0`, and `research_mode=True`.

## Writer Guard

`app/services/ai_runtime_export_writer_guard.py` provides
`AIRuntimeExportWriterGuard.can_write(...)`.

Rules:

- `explicit_enable=False` blocks with `explicit_enable_required`
- gate not allowed blocks
- `safe_to_persist=False` blocks
- `redacted=False` blocks
- unsupported format blocks

No filesystem action is performed.

## Writer Preview

`app/services/ai_runtime_export_writer_preview.py` builds
`AIRuntimeExportWriterPreview`.

Preview fields:

- `path`
- `format`
- `payload_bytes`
- `can_write`
- `reason`
- `metadata`

Preview computes payload size only; it does not create files or directories.

## Writer Stub

`app/services/ai_runtime_export_writer.py` defines `AIRuntimeExportWriter`.

`write(...)` behavior:

1. Evaluate guard.
2. If `explicit_enable=False`, return blocked result.
3. If guard fails, return blocked result.
4. Even if guard passes, this goal still returns:
   `written=False`, `reason="writer_stub_no_actual_write"`.
5. `bytes_written` is always `0`.

No `open(..., "w")`, no `write_text`, and no directory creation.

## Writer Report

`app/services/ai_runtime_export_writer_report.py` maps result/preview to a
compact report.

Statuses:

- `저장 안 함`
- `저장 차단`
- `저장 준비됨`
- `Stub 모드`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps existing snapshot/export/
persistence flow and adds:

- `runtime_export_writer_ready`
- `runtime_export_writer_preview`
- `runtime_export_writer_result`
- `runtime_export_writer_report`
- `runtime_export_written`

Default path is `data/runtime_exports/one_shot_snapshot.json`.
`explicit_enable=False` is fixed, so `runtime_export_written=False`.

## Safety Contract

The writer stub layer must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order API. It
must not alter `DecisionRouter`, import PySide6, modify `app/ui/*`, write files,
create directories, persist to DB, send outbound alerts, or trigger provider
automation.
