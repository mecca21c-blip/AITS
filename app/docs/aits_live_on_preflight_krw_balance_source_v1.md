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

No Upbit key body, account identifier, order payload, or provider prompt is
logged.

## Safety

The trace is read-only. It does not force ON, does not bypass preflight, does
not set `order_allowed=True`, does not set `real_order=True`, and does not call
OrderAdapter, ExecutionBridge, RiskGuard, or LivePreflight.

