# AITS Provider Generation Lifecycle v1

## Purpose

This policy separates provider key/auth readiness from a real generation
response. It applies to GPT/OpenAI and Gemini provider generation paths,
including manual AI refresh and runtime smoke provider proof.

This policy does not enable trading, AITS ON, order submission, order retry, or
live-window execution.

## Lifecycle States

- `auth_verified_no_generation`: key/auth is usable, but no current generation
  request has succeeded.
- `request_started`: a new provider generation request id was created.
- `waiting_response`: the provider HTTP request is waiting for a response.
- `retrying`: a provider generation retry is waiting to start. This is not an
  order retry.
- `confirmed`: the current request id produced a provider response proof.
- `failed_timeout`: the current request exhausted its provider timeout budget.
- `failed_error`: the current request failed for a non-timeout reason.
- `fallback_local`: external provider generation failed and LOCAL fallback was
  used for reference output.
- `stale_previous_response`: older preview or snapshot data is being shown only
  as reference.

## Freshness Contract

Every GPT generation request receives a `generation_request_id`. A response is
fresh only when it belongs to the current request id and has current provider
proof, such as HTTP success plus response id or token usage.

Saved preview or previous snapshot data may be displayed after restart, but it
must be marked as stale/reference data and must not set
`generation_response_confirmed=true`.

The default fresh TTL is 600 seconds. Older manual-generation status becomes
`기존 응답 참고 · stale`.

## Retry Contract

Provider generation retry is limited and separate from order retry.

- Manual GPT refresh may use up to two generation attempts.
- Provider-smoke uses the CLI `--max-provider-calls` budget.
- If `--max-provider-calls 1` is used, provider-smoke does not retry.
- If `--max-provider-calls 2` is used, provider-smoke may retry once.
- There is no automatic infinite retry.
- Retry logs must include request id, attempt count, max attempts, provider,
  and reason.

## UI Status Text

- `인증 확인됨 · 생성 요청 대기`: key/auth is ready, generation has not run.
- `생성 요청 중`: a new generation request was initialized.
- `생성 응답 대기 중`: the current provider request is in flight.
- `생성 재시도 중 n/N`: provider generation retry is being attempted.
- `생성 응답 확인됨`: the current request id produced response proof.
- `응답 시간 초과`: provider generation timed out.
- `GPT 실패 · LOCAL 대체`: GPT failed and LOCAL fallback was used.
- `기존 응답 참고 · stale`: previous data is visible but not fresh proof.

## Report Fields

Provider-smoke reports should include:

- `generation_request_id`
- `generation_status`
- `generation_status_text`
- `generation_attempt_count`
- `generation_max_attempts`
- `generation_retry_used`
- `generation_fresh`
- `generation_stale`
- `stale_reason`
- `generation_response_confirmed`
- `generation_response_confirmed_reason`
- `ui_generation_status_text`

## Safety Boundary

Provider generation retry must never call order services, toggle AITS ON,
enable live mode, or submit/cancel/sell/retry orders.

## Engine Ready For Run Contract

AITS ON may treat an external provider as engine-ready only when the same
generation lifecycle proof is fresh and current:

- `provider_selected` is `gpt` or `gemini`.
- `provider_actual` matches the selected provider.
- `generation_status` is `confirmed`.
- `generation_response_confirmed=true`.
- `generation_fresh=true` and `generation_stale=false`.
- `fallback_used=false`.
- `response_id_present=true` or `token_usage_present=true`.

Key/auth-only state, waiting state, timeout, LOCAL fallback while GPT/Gemini is
selected, and stale previous responses are not ready for AITS ON. This readiness
contract only removes the engine-preparation popup; it does not authorize an
order. RiskGuard, LiveOrderPreflight, Unlock, duplicate lock, and guarded-window
caps remain separate mandatory gates.

See also `app/docs/aits_ai_engine_state_ssot_v1.md` for the selected/applied/
actual/active engine SSOT and the simplified user-facing connection states.

## Startup Readiness Preflight

On app startup or provider-preview application, GPT/Gemini may start in `연결중`
after key/API ping succeeds but before a generation response exists. That state
is not run-ready.

If the selected provider is GPT/Gemini, AITS is OFF, no provider generation is
already in flight, and there is no fresh generation proof, the UI may schedule
one lightweight `startup_generation` preflight. The preflight uses the provider
generation lifecycle, assigns a request id, uses compact payload limits, and is
bounded by the provider-call budget. It must not toggle AITS ON, route a trading
decision, or call order services.

If a fresh generation proof already exists, startup preflight is skipped. If the
preflight succeeds, `connection_state_simple` becomes `연결됨`; if it fails, the
state remains a clear non-ready failure/waiting state. Startup preflight is
recorded with source `startup_generation` so it can be distinguished from user
`manual_generation` refreshes and so trade-log/journal growth can be monitored
for duplicate flooding.

## Real App Startup Path

The startup preflight must also run on the real `run.py -> MainWindow` path,
not only in harness helper calls. Provider-preview application with
`start_connection=True` schedules the bounded startup preflight after the saved
provider/model/key state has been applied. The `startup_readiness_checked` guard
is set only after the generation worker is actually dispatched, so an early
timer or dispatch failure does not permanently suppress startup readiness.

Structured logs distinguish each step:

- `[AITS][StartupReadinessPreflight] event=scheduled`
- `[AITS][StartupReadinessPreflight] event=skip reason=...`
- `[AITS][StartupReadinessPreflight] event=worker_start`
- `[AITS][StartupReadinessPreflight] event=worker_result`
- `[AITS][StartupReadinessPreflight] event=ui_applied`

If a fresh external-provider response has already made the engine run-ready,
group-id-less LOCAL side-channel updates must not overwrite the GPT/Gemini
connection state. Explicit fallback results with provider context are still
recorded as fallback and are not treated as ready.
