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
