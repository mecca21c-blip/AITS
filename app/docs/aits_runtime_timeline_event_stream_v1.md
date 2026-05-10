# AITS Runtime Timeline & Event Stream v1

## Scope

This layer records AI runtime activity as memory-only events and prepares a
timeline/feed structure for future UI and log surfaces. It does not connect to
trading execution and does not create UI widgets.

## Runtime Event Model

`app/services/ai_runtime_event.py` defines `AIRuntimeEvent`.

Fields:

- `event_id`
- `session_id`
- `provider`
- `symbol`
- `event_type`
- `severity`
- `title`
- `message`
- `timestamp`
- `source`
- `metadata`

Supported event examples include `one_shot_started`, `one_shot_completed`,
`observation_recorded`, `quality_scored`, `guard_checked`,
`session_reported`, `anomaly_detected`, `drift_detected`, and
`safety_blocked`.

Severity values are `info`, `warning`, `error`, and `critical`.

## Event Stream

`app/services/ai_runtime_event_stream.py` provides `AIRuntimeEventStream`.

The stream is memory-only. It can append events, filter by session/provider/type,
return the latest event, clear all or one session, and build a summary:

- `total`
- `by_type`
- `by_severity`
- `providers`
- `sessions`

It does not write files, use a database, or call external APIs.

## Timeline Builder

`app/services/ai_runtime_timeline.py` converts events into
`AIRuntimeTimelineItem` entries.

Timeline fields:

- `time`
- `provider`
- `event_type`
- `severity`
- `title`
- `message`
- `metadata`

Items are sorted by timestamp latest-first, and metadata records the ordering.

## Event Formatter

`app/services/ai_runtime_event_formatter.py` converts events or timeline items
to compact UI-ready dictionaries:

- `label`
- `message`
- `severity`
- `badge`
- `metadata`

Severity badges:

- `info` -> `정보`
- `warning` -> `주의`
- `error` -> `오류`
- `critical` -> `긴급`

## Event Summary

`app/services/ai_runtime_event_summary.py` builds
`AIRuntimeEventSummaryReport`.

Fields:

- `total_events`
- `warnings`
- `errors`
- `critical`
- `dominant_event_type`
- `summary_line`
- `metadata`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` attaches runtime event output:

- `runtime_events_ready`
- `runtime_events`
- `runtime_timeline`
- `runtime_event_summary`
- `runtime_event_feed`

The harness creates fallback events even when a provider or runtime path fails.
It does not store raw prompts, raw responses, keys, secrets, or tokens.

## Safety Contract

The event layer must preserve:

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
