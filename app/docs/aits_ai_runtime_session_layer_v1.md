# AITS AI Runtime Session Layer v1

## Purpose

The AI Runtime Session Layer groups one-shot provider checks, observations,
quality diagnostics, guard state, and compact reports into a local session. It
is a research and diagnostics layer only.

It does not connect to trading execution.

## Runtime Session

`app/services/ai_runtime_session.py` defines `AIRuntimeSession`.

Session fields:

- `session_id`
- `provider`
- `model`
- `started_at`
- `last_seen_at`
- `status`
- `total_one_shots`
- `total_observations`
- `total_errors`
- `degraded`
- `cooldown_blocked`
- `metadata`

Metadata preserves `shadow_only=True`, `suggestion_only=True`,
`applied=False`, `applied_to_action=False`, `real_order=False`, `submitted=0`,
and `research_mode=True`.

## Session Store

`app/services/ai_runtime_session_store.py` provides `AIRuntimeSessionStore`.

The store is memory-only. It can create sessions, touch activity timestamps,
record one-shot attempts, record observations, mark degraded/cooldown state,
list sessions, and build a compact summary.

It does not write files, use a database, or call external APIs.

## Runtime Memory

`app/services/ai_runtime_memory.py` provides `AIRuntimeMemory`.

Runtime memory is scoped by session id and stores sanitized temporary context
such as:

- `last_shadow_record`
- `last_observation_report`
- `last_quality_score`
- `last_guard_report`
- `last_state_ui`

Forbidden storage:

- API keys
- secrets
- tokens
- raw full responses
- raw text responses

Runtime memory is memory-only and does not persist to files.

## Session Diagnostics

`app/services/ai_session_diagnostics.py` provides
`AISessionDiagnosticsBuilder`.

Diagnostics combine session counters, observation readiness, guard readiness,
quality readiness, degraded state, cooldown state, and error rate.

Rules:

- `error_rate >= 0.3` marks the session degraded.
- `cooldown_blocked=True` marks the session unhealthy.
- Missing observation report sets `observation_ready=False`.
- Diagnosis values are `정상`, `관찰 필요`, `런타임 불안정`, and `차단 필요`.

## Session Report

`app/services/ai_session_report.py` provides `AISessionReportBuilder`.

The report contains:

- `session_id`
- `provider`
- `status`
- `diagnosis`
- `total_one_shots`
- `total_observations`
- `total_errors`
- `badges`
- `summary_line`
- `metadata`

Badges include values such as `정상`, `관찰 필요`, `불안정`, `쿨다운`, and
`연구모드`.

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` creates a local session for the
single invocation, records counters, stores sanitized runtime memory, builds
diagnostics, and attaches session report fields to the returned dictionary.

Attached fields:

- `session_ready`
- `session_id`
- `session_status`
- `session_diagnosis`
- `session_report`
- `runtime_memory_summary`

The harness does not create a global session store and does not implement long
term persistence.

## Safety Contract

The session layer must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order API. It
must not alter `DecisionRouter` action behavior, start a background trading
loop, invoke automatic live provider retries, run multiple providers, or perform
provider failover.

The runtime session layer is attach-only and research-only.
