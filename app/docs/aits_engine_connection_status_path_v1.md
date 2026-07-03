# AITS Engine Connection Status Path v1

## Goal

`AITS-AI-ENGINE-CONNECTION-STATUS-ROOT-CAUSE-FIX-01` fixes the repeated issue where
GPT/Gemini engine status could remain `연결중` until the user clicked
`AI 분석 새로고침`.

## Root Cause

The UI connection badge previously mixed two different concepts:

- provider connection state: whether the selected engine returned a real API
  connection response, or LOCAL/Basic is ready.
- AI generation freshness: whether the latest AI opinion/generation payload is
  fresh and response-confirmed.

`MainWindow._connection_state_simple` was reading
`_build_ai_engine_readiness_state()`. For GPT/Gemini this readiness state can
legitimately report `generation_not_fresh` before any manual analysis run. That
made the provider connection badge show `연결중` even after the connection
pipeline had enough information to show `정상연결`, `연결실패`, or
`연결 확인 필요`.

Manual AI refresh then created fresh generation state, so the badge appeared to
recover. That made manual refresh look like the only successful status path.

## Active Path

- Provider selection owner: `MainWindow._set_ai_provider_ui_active`
- Session provider owner: `MainWindow._select_ai_provider_for_session`
- Startup/provider-change connection owner:
  `MainWindow._run_ai_startup_connection_check_async`
- Connection result owner:
  `MainWindow._apply_ai_preview_connection_result`
- Connection result recorder:
  `MainWindow._record_ai_connection_result`
- Timeout owner:
  `MainWindow._on_ai_connection_check_timeout`
- UI renderer:
  `MainWindow._render_ai_engine_state`
- Simplified UI state:
  `MainWindow._connection_state_simple`
- Manual connection check owner:
  `MainWindow._run_manual_ai_connection_check`

Manual connection checks and automatic startup/provider-change checks now share
the same connection result pipeline. Manual AI analysis refresh remains a
separate opinion/generation path and is not the only way to update connection
status.

## State Machine

Internal states:

- `connecting`
- `connected`
- `failed`
- `unknown`
- `disabled`

UI mapping:

- `연결중`: connection check started and waiting for result.
- `정상연결`: real provider API response confirmed, or LOCAL/Basic ready.
- `연결실패`: provider check failed or timed out.
- `연결 확인 필요`: no current confirmed response for the selected provider.

For GPT/Gemini, key presence or preview selection is not a connected state. Only
`API 응답 확인됨` or an equivalent real response result maps to `정상연결`.

## Writer Policy

`_connection_state_simple` reads the last connection status only when
`_last_ai_connection_provider` matches the selected provider. This prevents stale
state from a previous provider from becoming the visible status.

Connection status does not read AI generation freshness. AI generation freshness
continues to affect run-readiness and AI opinion state, but not the provider
connection badge.

## Diagnostics

Engine status transitions are logged with prefix:

- `[AITS][EngineStatusPath]`

## Follow-up: Key Refresh Writer Conflict Fix

Goal: `AITS-AI-ENGINE-STATUS-KEY-REFRESH-WRITER-CONFLICT-FIX-01`.

Reproduced symptom:

- Startup/provider selection entered `connecting`, then `failed`, then
  `check_needed`.

## Follow-up: Provider Settings Runtime SSOT Root Fix

Goal: `AITS-AI-PROVIDER-SETTINGS-RUNTIME-SSOT-ROOT-FIX-01`.

Root cause:

- Saved settings, UI/session provider codes, and provider service codes were not
  using one explicit mapping. Saved settings must use `openai`, `gemini`,
  `local`; UI/session preview may use `gpt`, `gemini`, `basic`; provider service
  runtime uses `openai`, `gemini`, `local`.
- Local/basic secret fallback paths could accidentally fall through to external
  provider secret helpers.
- Connection status used one global last-result field, so previous provider
  failures could contaminate the newly selected provider.
- After key save, selected provider runtime was not explicitly re-synced and
  stale failure state could remain visible until another manual action.

Fix policy:

- Provider normalization is shared by settings save/load/runtime apply.
- OpenAI and Gemini key/model paths stay provider-specific.
- Local/basic paths do not read external secrets.
- Key save performs selected-provider runtime sync and clears stale selected
  provider failure without marking the provider connected.
- Connection snapshots are selected-provider scoped.
- Manual AI refresh continues to update generation/freshness only and must not
  downgrade provider connection status.

Regression modes:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-settings-runtime-ssot-diagnostic --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-settings-restart-restore-regression-proof --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-switching-cross-provider-regression-proof --observe-only
```

## Follow-up: Key Resolution Bootstrap Trace

Goal: `AITS-AI-PROVIDER-KEY-RESOLUTION-BOOTSTRAP-ACTUAL-TRACE-FIX-01`.

The startup connection check, manual connection check, AI generation refresh,
and runtime service provider construction must use the same provider
normalization and key-source ordering. Safe diagnostics compare key availability
and `sha256` fingerprints only; raw keys, prefixes, and suffixes are forbidden.

Regression modes:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-bootstrap-trace --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-restart-regression-proof --provider gpt --observe-only
```
- Common Settings API connection test with a refreshed OpenAI key could verify
  the provider and show connected.
- A later manual AI analysis refresh could overwrite the same connection slot
  with generation/freshness text such as request-started, stale, or key-needed,
  causing the provider connection badge to fall back to check-needed.

Root cause:

- Provider connection status and AI generation status still shared
  `_last_ai_connection_status` / `_ai_connection_status` in several generation
  paths.
- `MainWindow._mark_provider_generation_failure_status`,
  `MainWindow._on_aits_provider_refresh_worker_result`, and the GPT/Gemini
  generation request initialization path could write generation-only state into
  the provider connection snapshot.
- Preview application also had legacy branches that interpreted
  `manual_generation` / `startup_generation` as connection status.

Fix policy:

- `_last_ai_connection_status` is owned only by provider connection checks,
  provider selection invalidation, and LOCAL self-check.
- AI analysis refresh updates only generation/opinion freshness fields:
  `_last_ai_generation_status`, `_last_ai_generation_fresh`,
  `_last_ai_generation_stale`, and response-confirmation fields.
- Generation request start, generation success, generation failure, missing
  generation key, and stale generation state must not downgrade provider
  connection status.
- These blocked writer attempts are logged with
  `[AITS][EngineStatusWriter]` and `downgrade_blocked_reason`.

Downgrade rules:

- Allowed: `connecting -> connected`.
- Allowed: `connecting -> failed`.
- Allowed: `connecting -> timeout`.
- Allowed: `connected -> failed` only from the latest actual provider
  connection check result.
- Allowed: provider/key change may intentionally invalidate the old snapshot to
  check-needed/connecting before a new check.
- Forbidden: `connected -> check_needed` because of `generation_not_fresh`.
- Forbidden: `connected -> check_needed` because manual AI analysis has no fresh
  result.
- Forbidden: stale old connection failure overwriting a newer connected result.
- Forbidden: render-only/timer-only code changing connected back to connecting
  or unknown.

Regression proof:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode engine-connection-key-refresh-regression-proof --provider gpt --observe-only
```

The proof simulates:

1. startup connecting/failed/check-needed,
2. key refresh connection success,
3. manual AI refresh generation-not-fresh,
4. generation failure,
5. stale old failure result,
6. latest actual connection failure,
7. provider-change invalidation.

Expected result: provider external calls remain `0`, connected remains connected
through generation-only events, and only the latest actual connection failure can
downgrade to failed.

The log includes source path, selected/normalized provider, previous/next status,
writer, reason, check id, elapsed time, and whether UI update was emitted. It
does not log API keys, prompts, raw payloads, or provider response bodies.

## Regression Modes

Default regression modes do not call GPT/Gemini:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode engine-connection-status-path-diagnostic --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode engine-connection-status-regression-proof --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode engine-connection-status-regression-proof --provider local --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode engine-connection-status-regression-proof --provider gemini --observe-only
```

Expected safety fields:

- `provider_external_call_count=0`
- `manual_refresh_only_writer=false`
- `connection_freshness_separated=true`
- `connecting_timeout_supported=true`
- `actual_order=false`
- `order_risk_detected=false`

## Manual UI Check

1. Start the app.
2. Select GPT.
3. Do not click `AI 분석 새로고침`.
4. Confirm the engine status leaves `연결중` and becomes either `정상연결`,
   `연결실패`, or `연결 확인 필요`.
5. Click `AI 분석 새로고침` only after confirming the status path is already
   independent.
6. Confirm the manual path logs the same connection status path when it performs
   a connection check.

## Safety

This change does not modify order, RiskGuard, LivePreflight, ExecutionBridge,
OrderService, OrderAdapter, or DecisionRouter final action logic.
