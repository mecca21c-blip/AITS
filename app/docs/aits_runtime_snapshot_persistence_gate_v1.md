# AITS Runtime Snapshot Persistence Gate v1

## Scope

This layer evaluates whether a runtime snapshot export payload is safe to
persist. It is a pre-write gate only.

It does not write JSON or CSV files, create directories, persist to a database,
send webhooks/email/Slack, or connect to trading execution.

## Persistence Policy

`app/services/ai_runtime_persistence_policy.py` defines
`AIRuntimePersistencePolicy`.

Default policy:

- `enabled=False`
- `allowed_formats=["json", "csv_preview", "text_preview"]`
- `max_payload_bytes=1_000_000`
- `allow_relative_path=True`
- `allow_absolute_path=False`
- `allowed_base_dir="data/runtime_exports"`
- `require_redacted=True`
- `require_safe_to_persist=True`

Because `enabled=False`, default gate output blocks persistence.

## Path Guard

`app/services/ai_runtime_persistence_path_guard.py` validates candidate paths.

Rules:

- empty paths are blocked
- absolute paths are blocked by default
- `..` traversal is blocked
- only paths under `data/runtime_exports` are allowed
- executable extensions are blocked: `.exe`, `.bat`, `.cmd`, `.ps1`, `.dll`

The guard does not create directories or files.

## Size Guard

`app/services/ai_runtime_persistence_size_guard.py` measures payload size using
`json.dumps(...).encode("utf-8")`.

Payloads over `max_payload_bytes` are blocked. Serialization failure is blocked.

## Persistence Gate

`app/services/ai_runtime_persistence_gate.py` combines policy, format, path,
size, redaction, and safe-to-persist checks.

Blocking reasons include:

- `policy_disabled`
- `format_blocked`
- path guard reasons
- size guard reasons
- `redaction_required`
- `safe_to_persist_required`

The gate only returns a decision. It does not persist anything.

## Persistence Report

`app/services/ai_runtime_persistence_report.py` converts gate results into a
compact report.

Statuses:

- `저장 가능`
- `저장 차단`
- `정책 비활성`
- `경로 차단`
- `크기 초과`
- `민감정보 의심`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps the existing snapshot/export
payload flow and attaches:

- `runtime_persistence_ready`
- `runtime_persistence_allowed`
- `runtime_persistence_report`
- `runtime_persistence_gate`
- `runtime_persistence_reason`

The candidate path is `data/runtime_exports/one_shot_snapshot.json`. With the
default disabled policy, `runtime_persistence_allowed=False`.

## Safety Contract

The persistence gate must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It assumes snapshot/export sanitization has already removed keys, tokens, raw
prompts, and raw responses. It must not call `OrderAdapter`, `ExecutionBridge`,
or any Upbit order API. It must not alter `DecisionRouter`, create UI widgets,
import PySide6, write files, create directories, use a database, send outbound
alerts, start background loops, auto-run providers, or perform provider failover.
