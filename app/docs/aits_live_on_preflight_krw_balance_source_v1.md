# AITS Live ON Preflight KRW Balance Source v1

## Goal

`AITS-LIVE-ON-PREFLIGHT-KRW-BALANCE-SOURCE-TRACE-01` traces the KRW balance
used by the ON button preflight popup. The preflight must not treat a missing or
failed balance lookup as the same thing as an actual zero KRW balance.

## Active Path

- Popup owner: `app/ui/app_gui.py::_preflight_check`
- Balance resolver: `svc_order.compute_available_krw_snapshot(source_path="on_preflight")`
- Account read owner: `app/services/order_service.py::OrderService.fetch_accounts`
- Read-only private API endpoint: Upbit `/v1/accounts`

## Balance Status Taxonomy

| Status | Meaning | User-facing blocker |
| --- | --- | --- |
| `ok` | Read-only account lookup succeeded and available KRW is above zero. | none |
| `actual_krw_balance_zero` | Account lookup succeeded and KRW available is zero. | `KRW 잔고 부족` |
| `balance_not_loaded` | No usable balance read has happened. | `KRW 잔고 미확인 - 잔고 조회 후 다시 ON` |
| `balance_fetch_failed` | Account lookup attempted but failed. | `KRW 잔고 조회 실패 - Upbit 연결 확인 필요` |
| `private_api_not_connected` | Upbit private API keys are missing or not ready. | `Upbit 계정 연결 필요` |
| `upbit_access_key_missing` | Upbit access key was not resolved. | `Upbit API 키 확인 필요` |
| `upbit_secret_key_missing` | Upbit secret key was not resolved. | `Upbit API 키 확인 필요` |
| `upbit_jwt_generation_failed` | Local JWT header generation failed before the request. | `Upbit 계정 조회 인증 실패` |
| `upbit_http_401_unauthorized` | `/v1/accounts` returned HTTP 401. | `Upbit 계정 조회 권한 실패` |
| `upbit_http_403_forbidden` | `/v1/accounts` returned HTTP 403. | `Upbit 계정 조회 권한 실패` |
| `upbit_http_429_rate_limited` | `/v1/accounts` returned HTTP 429. | retry after rate limit window |
| `upbit_network_error` | The read-only account request failed at the network layer. | `KRW 잔고 조회 실패 - 네트워크 확인 필요` |
| `upbit_timeout` | The read-only account request timed out. | `KRW 잔고 조회 실패 - 네트워크 확인 필요` |
| `upbit_response_parse_error` | The account response could not be parsed safely. | inspect Upbit account response parser |
| `accounts_response_empty` | `/v1/accounts` returned an empty account list. | `KRW 잔고 항목 없음` |
| `krw_balance_missing_from_accounts` | Account lookup succeeded but no KRW row was present. | `KRW 잔고 항목 없음` |
| `balance_cache_stale` | A previous read exists but is too old for ON preflight. | refresh balance before ON |
| `unknown_balance_source` | The preflight could not identify a trusted balance source. | inspect balance source |

## Trace Fields

`[AITS][KRWBalanceSource]` records only safe metadata:

- `available_krw`
- `balance_status`
- `balance_source`
- `balance_cache_present`
- `balance_cache_age_sec`
- `balance_fetch_attempted`
- `balance_fetch_success`
- `balance_fetch_error_type`
- `upbit_private_connected`
- `account_service_ready`
- `fallback_used`
- `fallback_reason`
- `blocker`
- `access_key_present`
- `secret_key_present`
- `upbit_key_fp`
- `jwt_build_success`
- `authorization_header_present`
- `http_status`
- `response_shape`
- `krw_row_found`

`upbit_key_fp` is a short hash fingerprint of the Upbit key pair. It is only
for comparing paths and never includes the access key, secret key, JWT, or
authorization header.

## Runtime Smoke Modes

- `live-on-preflight-krw-balance-source-summary`: classifies recent ON
  preflight balance logs.
- `upbit-accounts-readonly-krw-parse-proof`: verifies mock `/v1/accounts`
  parsing cases without any Upbit network call.
- `upbit-accounts-readonly-balance-fetch-diagnostic`: inspects key presence,
  key fingerprint, local JWT build readiness, and the last safe trace. By
  default it does not call `/v1/accounts`.

Actual read-only `/v1/accounts` calls are allowed only when the operator passes
`--allow-upbit-readonly-accounts-call`. Order endpoints remain forbidden.

No Upbit key body, account identifier, order payload, or provider prompt is
logged.

## Safety

The trace is read-only. It does not force ON, does not bypass preflight, does
not set `order_allowed=True`, does not set `real_order=True`, and does not call
OrderAdapter, ExecutionBridge, RiskGuard, or LivePreflight.
