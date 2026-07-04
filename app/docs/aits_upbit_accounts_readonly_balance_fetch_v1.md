# AITS Upbit Accounts Read-only Balance Fetch v1

## Goal

`AITS-UPBIT-ACCOUNTS-READONLY-BALANCE-FETCH-FAILURE-ROOT-FIX-01` separates
`balance_fetch_failed` from an actual zero KRW balance. The only private Upbit
endpoint in scope is read-only `/v1/accounts`.

## Active Path

- ON preflight owner: `app/ui/app_gui.py::_preflight_check`
- Balance snapshot owner:
  `app/services/order_service.py::OrderService.compute_available_krw_snapshot`
- Account read owner: `app/services/order_service.py::OrderService.fetch_accounts`
- Auth header owner: `app/services/order_service.py::OrderService._make_auth_headers`
- Key resolver owner: `app/services/order_service.py::OrderService._extract_upbit_keys`

## Secret-safe Diagnostics

The accounts trace records only safe metadata:

- `access_key_present`
- `secret_key_present`
- `upbit_key_fp`
- `jwt_build_attempted`
- `jwt_build_success`
- `authorization_header_present`
- `endpoint=/v1/accounts`
- `http_status`
- `error_type`
- `error_code`
- `error_message_sanitized`
- `response_shape`
- `krw_row_found`
- `krw_balance_raw_present`
- `krw_locked_raw_present`
- `available_krw`
- `balance_status`
- `fallback_used`
- `fallback_reason`

`upbit_key_fp` is a short SHA-256 fingerprint of the key pair. It is used only
to compare code paths. The access key, secret key, JWT, and Authorization header
must never be logged.

## Failure Taxonomy

- `upbit_access_key_missing`
- `upbit_secret_key_missing`
- `upbit_jwt_generation_failed`
- `upbit_http_401_unauthorized`
- `upbit_http_403_forbidden`
- `upbit_http_429_rate_limited`
- `upbit_network_error`
- `upbit_timeout`
- `upbit_response_parse_error`
- `accounts_response_empty`
- `krw_balance_missing_from_accounts`
- `actual_krw_balance_zero`
- `unknown_accounts_read_failure`

## Parse Policy

The KRW parser expects an Upbit accounts list. It finds the row with
`currency == "KRW"` and computes:

`available_krw = max(0, float(balance) - float(locked or 0))`

Mock proof cases cover positive KRW, locked KRW, missing KRW row, invalid
numeric values, empty responses, HTTP 401, and HTTP 403.

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-krw-parse-proof --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-balance-fetch-diagnostic --observe-only
```

The diagnostic mode does not call `/v1/accounts` by default. An actual read-only
accounts call requires explicit operator intent:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-balance-fetch-diagnostic --allow-upbit-readonly-accounts-call --observe-only
```

Order endpoints, order submit, cancel, retry, paper mode, virtual orders, and
fake balances are out of scope and forbidden.
