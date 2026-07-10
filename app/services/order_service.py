"""Order execution interface.

Live order support is deliberately narrow:
- the completed minimum real-order test: KRW-BTC market buy for 5,000 KRW
  with a 6,000 KRW hard cap;
- the guarded one-shot/window path for KRW market buys;
- guarded market sells that already passed RiskGuard and LivePreflight.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from typing import Any
from urllib.parse import unquote, urlencode

import jwt
import requests


MINIMUM_REAL_ORDER_AMOUNT_KRW = 5000.0
MINIMUM_REAL_ORDER_HARD_CAP_KRW = 6000.0
GUARDED_WINDOW_ORDER_AMOUNT_KRW = 10000.0
GUARDED_WINDOW_ORDER_HARD_CAP_KRW = 12000.0
GUARDED_WINDOW_TOTAL_CAP_KRW = 20000.0
GUARDED_WINDOW_MAX_ORDER_COUNT = 2
GUARDED_ONE_SHOT_MAX_ORDER_COUNT = 1
GUARDED_WINDOW_MIN_INTERVAL_SEC = 600


class OrderService:
    """Minimal order placement surface for Order Adapter injection."""

    def __init__(self):
        self._settings = None
        self._simulate = True
        self._trading_enabled = True
        self._last_accounts_fetch_trace = {
            "status": "not_loaded",
            "source": "svc_order.fetch_accounts",
            "attempted": False,
            "success": False,
            "error_type": "",
            "access_key_present": False,
            "secret_key_present": False,
            "key_present": False,
            "upbit_key_fp": "",
            "jwt_build_attempted": False,
            "jwt_build_success": False,
            "authorization_header_present": False,
            "endpoint": "/v1/accounts",
            "http_status": None,
            "error_code": "",
            "error_message_sanitized": "",
            "response_shape": "not_loaded",
            "krw_row_found": False,
            "krw_balance_raw_present": False,
            "krw_locked_raw_present": False,
            "available_krw": 0.0,
            "balance_status": "not_loaded",
            "fallback_reason": "",
            "row_count": 0,
            "default_used": False,
            "fetched_at": 0.0,
        }
        self._aits_last_exec = {
            "action": None,
            "symbol": None,
            "ts": 0.0,
        }

    def set_settings(self, settings) -> bool:
        try:
            self._settings = settings
            if settings is not None:
                self._simulate = not bool(getattr(settings, "live_trade", False))
            print(
                "[AITS][OrderService] set_settings called | "
                f"live_trade={getattr(settings, 'live_trade', None) if settings is not None else None}"
            )
            return True
        except Exception:
            return False

    def fetch_accounts(self) -> list:
        default_rows = [
            {
                "currency": "KRW",
                "balance": "0",
                "locked": "0",
                "avg_buy_price": "0",
            }
        ]
        rows: list = list(default_rows)
        trace = {
            "status": "not_loaded",
            "source": "svc_order.fetch_accounts",
            "attempted": True,
            "success": False,
            "error_type": "",
            "access_key_present": False,
            "secret_key_present": False,
            "key_present": False,
            "upbit_key_fp": "",
            "jwt_build_attempted": False,
            "jwt_build_success": False,
            "authorization_header_present": False,
            "endpoint": "/v1/accounts",
            "http_status": None,
            "error_code": "",
            "error_message_sanitized": "",
            "response_shape": "empty",
            "krw_row_found": False,
            "krw_balance_raw_present": False,
            "krw_locked_raw_present": False,
            "available_krw": 0.0,
            "balance_status": "not_loaded",
            "fallback_reason": "",
            "row_count": 0,
            "default_used": True,
            "fetched_at": time.time(),
        }
        try:
            ak, sk = self._extract_upbit_keys()
            trace["access_key_present"] = bool(ak and len(ak) >= 10)
            trace["secret_key_present"] = bool(sk and len(sk) >= 10)
            trace["key_present"] = bool(trace["access_key_present"] and trace["secret_key_present"])
            trace["upbit_key_fp"] = _safe_upbit_key_fingerprint(ak, sk)
            _log_accounts_trace(
                "[AITS][UpbitAccounts] event=accounts_fetch_started "
                f"caller=fetch_accounts endpoint=/v1/accounts "
                f"access_key_present={trace['access_key_present']} "
                f"secret_key_present={trace['secret_key_present']} "
                f"upbit_key_fp={trace['upbit_key_fp'] or '-'}"
            )
            if not trace["access_key_present"]:
                trace["status"] = "upbit_access_key_missing"
                trace["error_type"] = "upbit_access_key_missing"
                trace["fallback_reason"] = "upbit_access_key_missing"
                rows = list(default_rows)
            elif not trace["secret_key_present"]:
                trace["status"] = "upbit_secret_key_missing"
                trace["error_type"] = "upbit_secret_key_missing"
                trace["fallback_reason"] = "upbit_secret_key_missing"
                rows = list(default_rows)
            else:
                trace["jwt_build_attempted"] = True
                try:
                    headers = self._make_auth_headers({})
                    trace["jwt_build_success"] = True
                    trace["authorization_header_present"] = bool(headers.get("Authorization"))
                    _log_accounts_trace(
                        "[AITS][UpbitAuth] event=jwt_build_result endpoint=/v1/accounts "
                        f"jwt_build_attempted={trace['jwt_build_attempted']} "
                        f"jwt_build_success={trace['jwt_build_success']} "
                        f"authorization_header_present={trace['authorization_header_present']} "
                        f"upbit_key_fp={trace['upbit_key_fp'] or '-'}"
                    )
                except Exception as exc:
                    trace["status"] = "upbit_jwt_generation_failed"
                    trace["error_type"] = "upbit_jwt_generation_failed"
                    trace["error_code"] = type(exc).__name__
                    trace["error_message_sanitized"] = _sanitize_error_message(str(exc))
                    trace["fallback_reason"] = "upbit_jwt_generation_failed"
                    rows = list(default_rows)
                    raise _AccountsTraceCompleted()
                r = requests.get(
                    "https://api.upbit.com/v1/accounts",
                    headers=headers,
                    timeout=5,
                )
                trace["http_status"] = getattr(r, "status_code", None)
                http_status = getattr(r, "status_code", None)
                http_ok = 200 <= int(http_status or 0) < 300
                if http_ok:
                    try:
                        data = r.json()
                    except Exception as exc:
                        trace["status"] = "upbit_response_parse_error"
                        trace["error_type"] = "upbit_response_parse_error"
                        trace["error_code"] = type(exc).__name__
                        trace["error_message_sanitized"] = _sanitize_error_message(str(exc))
                        trace["fallback_reason"] = "upbit_response_parse_error"
                        rows = list(default_rows)
                    else:
                        trace["response_shape"] = _response_shape(data)
                        if isinstance(data, list) and data:
                            rows = data
                            trace["status"] = "ok"
                            trace["success"] = True
                            trace["default_used"] = False
                            trace["error_type"] = ""
                        elif isinstance(data, list):
                            trace["status"] = "accounts_response_empty"
                            trace["error_type"] = "accounts_response_empty"
                            trace["fallback_reason"] = "accounts_response_empty"
                            rows = list(default_rows)
                        else:
                            trace["status"] = "upbit_response_parse_error"
                            trace["error_type"] = "upbit_response_parse_error"
                            trace["fallback_reason"] = "upbit_response_parse_error"
                            rows = list(default_rows)
                else:
                    failure_type = classify_upbit_accounts_http_failure(getattr(r, "status_code", None))
                    error_code, error_message = _safe_response_error(r)
                    trace["status"] = failure_type
                    trace["error_type"] = failure_type
                    trace["error_code"] = error_code
                    trace["error_message_sanitized"] = error_message
                    trace["fallback_reason"] = failure_type
                    rows = list(default_rows)
        except _AccountsTraceCompleted:
            rows = list(default_rows)
        except requests.Timeout as exc:
            trace["status"] = "upbit_timeout"
            trace["error_type"] = "upbit_timeout"
            trace["error_code"] = type(exc).__name__
            trace["error_message_sanitized"] = _sanitize_error_message(str(exc))
            trace["fallback_reason"] = "upbit_timeout"
            rows = list(default_rows)
        except requests.RequestException as exc:
            trace["status"] = "upbit_network_error"
            trace["error_type"] = "upbit_network_error"
            trace["error_code"] = type(exc).__name__
            trace["error_message_sanitized"] = _sanitize_error_message(str(exc))
            trace["fallback_reason"] = "upbit_network_error"
            rows = list(default_rows)
        except Exception as exc:
            trace["status"] = "unknown_accounts_read_failure"
            trace["error_type"] = type(exc).__name__
            trace["error_code"] = type(exc).__name__
            trace["error_message_sanitized"] = _sanitize_error_message(str(exc))
            trace["fallback_reason"] = "unknown_accounts_read_failure"
            rows = list(default_rows)
        trace["row_count"] = len(rows) if isinstance(rows, list) else 0
        parsed = parse_upbit_accounts_krw_snapshot(rows, trace)
        trace.update(
            {
                "krw_row_found": bool(parsed.get("krw_row_found")),
                "krw_balance_raw_present": bool(parsed.get("krw_balance_raw_present")),
                "krw_locked_raw_present": bool(parsed.get("krw_locked_raw_present")),
                "available_krw": _safe_float(parsed.get("available_krw")),
                "balance_status": str(parsed.get("balance_status") or trace.get("status") or ""),
                "fallback_reason": str(trace.get("fallback_reason") or parsed.get("fallback_reason") or ""),
            }
        )
        self._last_accounts_fetch_trace = trace
        _log_accounts_trace(
            "[AITS][UpbitAccounts] event=accounts_fetch_result "
            f"endpoint=/v1/accounts http_status={trace.get('http_status')} "
            f"status={trace.get('status')} error_type={trace.get('error_type') or '-'} "
            f"error_code={trace.get('error_code') or '-'} "
            f"error_message_sanitized={trace.get('error_message_sanitized') or '-'} "
            f"response_shape={trace.get('response_shape')} krw_row_found={trace.get('krw_row_found')} "
            f"available_krw={trace.get('available_krw')} fallback_used={trace.get('default_used')} "
            f"fallback_reason={trace.get('fallback_reason') or '-'}"
        )
        trace_line = (
            "[AITS][OrderService] fetch_accounts called | "
            f"rows={len(rows) if isinstance(rows, list) else 0} status={trace.get('status')} "
            f"success={trace.get('success')} default_used={trace.get('default_used')}"
        )
        print(trace_line)
        try:
            logging.getLogger("aits").info(trace_line)
        except Exception:
            pass
        return rows if isinstance(rows, list) else list(default_rows)

    def get_last_accounts_fetch_trace(self) -> dict:
        return dict(self._last_accounts_fetch_trace or {})

    def compute_available_krw_snapshot(self, source_path: str = "") -> dict:
        rows = self.fetch_accounts()
        trace = self.get_last_accounts_fetch_trace()
        parsed = parse_upbit_accounts_krw_snapshot(rows, trace)
        krw_balance = _safe_float(parsed.get("krw_balance"))
        krw_locked = _safe_float(parsed.get("krw_locked"))
        available = _safe_float(parsed.get("available_krw"))
        status = str(parsed.get("balance_status") or "unknown_balance_source")
        return {
            "available_krw": available,
            "krw_balance": krw_balance,
            "krw_locked": krw_locked,
            "balance_status": status,
            "balance_source": "svc_order.fetch_accounts",
            "balance_cache_present": bool(trace.get("success")),
            "balance_cache_age_sec": 0,
            "balance_fetch_attempted": bool(trace.get("attempted")),
            "balance_fetch_success": bool(trace.get("success")),
            "balance_fetch_error_type": str(trace.get("error_type") or ""),
            "upbit_private_connected": bool(trace.get("success")),
            "account_service_ready": True,
            "fallback_used": bool(trace.get("default_used")),
            "fallback_reason": str(trace.get("fallback_reason") or parsed.get("fallback_reason") or ""),
            "krw_row_found": bool(parsed.get("krw_row_found")),
            "krw_balance_raw_present": bool(parsed.get("krw_balance_raw_present")),
            "krw_locked_raw_present": bool(parsed.get("krw_locked_raw_present")),
            "upbit_key_fp": str(trace.get("upbit_key_fp") or ""),
            "jwt_build_success": bool(trace.get("jwt_build_success")),
            "authorization_header_present": bool(trace.get("authorization_header_present")),
            "http_status": trace.get("http_status"),
            "source_path": str(source_path or ""),
        }

    def _compute_available_krw(self) -> float:
        return _safe_float(self.compute_available_krw_snapshot().get("available_krw"))

    def fetch_order(self, order_uuid: str) -> dict:
        """Read-only Upbit order status lookup by UUID."""
        safe_uuid = str(order_uuid or "").strip()
        try:
            print(f"[AITS][OrderService] fetch_order called | uuid={safe_uuid}")
        except Exception:
            pass

        def _fail(error: str, **extra) -> dict:
            out = {
                "success": False,
                "uuid": safe_uuid,
                "error": error,
                "real_order": False,
                "submitted": False,
            }
            out.update(extra)
            return out

        try:
            if not safe_uuid:
                return _fail("missing_order_uuid")
            ak, sk = self._extract_upbit_keys()
            if not ak or not sk or len(ak) < 10 or len(sk) < 10:
                return _fail("upbit_key_not_ready")
            params = {"uuid": safe_uuid}
            response = requests.get(
                "https://api.upbit.com/v1/order",
                params=params,
                headers=self._make_auth_headers(params),
                timeout=5,
            )
            try:
                payload = response.json()
            except Exception:
                payload = {"text": str(response.text or "")[:500]}
            sanitized = self._sanitize_order_response(payload)
            http_status = int(getattr(response, "status_code", 0) or 0)
            if 200 <= http_status < 300:
                return {
                    "success": True,
                    "uuid": str(sanitized.get("uuid") or safe_uuid),
                    "http_status": http_status,
                    "state": str(sanitized.get("state") or ""),
                    "market": str(sanitized.get("market") or ""),
                    "side": str(sanitized.get("side") or ""),
                    "ord_type": str(sanitized.get("ord_type") or ""),
                    "response_sanitized": sanitized,
                    "real_order": False,
                    "submitted": False,
                }
            error = sanitized.get("error") if isinstance(sanitized.get("error"), dict) else {}
            return _fail(
                str(error.get("name") or sanitized.get("name") or f"http_{http_status}"),
                http_status=http_status,
                error_message=str(error.get("message") or sanitized.get("message") or "")[:300],
                response_sanitized=sanitized,
            )
        except Exception as exc:
            return _fail(f"order_query_exception:{type(exc).__name__}")

    def place_order(self, order_request: dict) -> dict:
        try:
            safe_symbol = str((order_request or {}).get("symbol") or "")
            safe_side = str((order_request or {}).get("side") or "")
            safe_amount = (order_request or {}).get("amount_krw") if isinstance(order_request, dict) else None
            print(
                "[AITS][OrderService] place_order called | "
                f"symbol={safe_symbol} side={safe_side} amount_krw={safe_amount}"
            )
        except Exception:
            pass

        def _fail(error: str, **extra) -> dict:
            out = {
                "success": False,
                "order_id": None,
                "error": error,
                "filled": None,
                "avg_price": None,
                "real_order": False,
                "submitted": False,
            }
            out.update(extra)
            return out

        try:
            if not isinstance(order_request, dict):
                return _fail("invalid_order_request")

            symbol = str(order_request.get("symbol") or "").strip().upper()
            side = str(order_request.get("side") or "").strip().lower()
            amount_krw = _safe_float(order_request.get("amount_krw"))
            volume = _safe_float(order_request.get("volume") or order_request.get("quantity"))
            order_type = str(order_request.get("order_type") or "market").strip().lower()
            request_id = str(order_request.get("request_id") or uuid.uuid4().hex)
            is_minimum_test = bool(order_request.get("live_minimum_real_order_test", False))
            is_guarded_window = bool(order_request.get("live_guarded_window_order", False))
            is_guarded_one_shot = bool(order_request.get("live_guarded_one_shot_order", False))

            if not is_minimum_test and not is_guarded_window and not is_guarded_one_shot:
                return _fail("live_order_scope_flag_missing")
            if is_minimum_test and symbol != "KRW-BTC":
                return _fail("unsupported_live_symbol")
            if (is_guarded_window or is_guarded_one_shot) and not (
                symbol.startswith("KRW-") and 5 <= len(symbol) <= 31
            ):
                return _fail("unsupported_live_symbol")
            if side not in {"buy", "sell"}:
                return _fail("unsupported_live_side")
            if order_type != "market":
                return _fail("unsupported_live_order_type")
            if side == "sell":
                if is_minimum_test:
                    return _fail("unsupported_live_side")
                if not (is_guarded_window or is_guarded_one_shot):
                    return _fail("live_sell_guard_missing")
                if volume <= 0:
                    return _fail("invalid_sell_volume")
                if amount_krw < MINIMUM_REAL_ORDER_AMOUNT_KRW:
                    return _fail("sell_value_below_min_order")
            if is_minimum_test:
                if abs(amount_krw - MINIMUM_REAL_ORDER_AMOUNT_KRW) > 0.0001:
                    return _fail("unsupported_live_amount")
                if amount_krw > MINIMUM_REAL_ORDER_HARD_CAP_KRW:
                    return _fail("hard_cap_exceeded")
            if is_guarded_window or is_guarded_one_shot:
                expected_amount = _safe_float(
                    order_request.get("guarded_window_per_order_krw"),
                    GUARDED_WINDOW_ORDER_AMOUNT_KRW,
                )
                hard_cap = _safe_float(
                    order_request.get("guarded_window_per_order_hard_cap_krw"),
                    GUARDED_WINDOW_ORDER_HARD_CAP_KRW,
                )
                total_cap = _safe_float(
                    order_request.get("guarded_window_total_cap_krw"),
                    GUARDED_WINDOW_TOTAL_CAP_KRW,
                )
                max_count = int(
                    _safe_float(
                        order_request.get("guarded_window_max_order_count"),
                        GUARDED_ONE_SHOT_MAX_ORDER_COUNT if is_guarded_one_shot else GUARDED_WINDOW_MAX_ORDER_COUNT,
                    )
                )
                min_interval = int(
                    _safe_float(
                        order_request.get("guarded_window_min_order_interval_sec"),
                        GUARDED_WINDOW_MIN_INTERVAL_SEC,
                    )
                )
                if side == "buy":
                    if abs(expected_amount - GUARDED_WINDOW_ORDER_AMOUNT_KRW) > 0.0001:
                        return _fail("guarded_window_per_order_policy_invalid")
                    if abs(amount_krw - expected_amount) > 0.0001:
                        return _fail("unsupported_guarded_window_amount")
                    if hard_cap > GUARDED_WINDOW_ORDER_HARD_CAP_KRW or amount_krw > hard_cap:
                        return _fail("guarded_window_hard_cap_exceeded")
                elif hard_cap > 0 and amount_krw > hard_cap:
                    return _fail("guarded_sell_hard_cap_exceeded")
                if total_cap > GUARDED_WINDOW_TOTAL_CAP_KRW:
                    return _fail("guarded_window_total_cap_policy_invalid")
                if is_guarded_one_shot and max_count != GUARDED_ONE_SHOT_MAX_ORDER_COUNT:
                    return _fail("guarded_one_shot_max_order_count_policy_invalid")
                if not is_guarded_one_shot and max_count > GUARDED_WINDOW_MAX_ORDER_COUNT:
                    return _fail("guarded_window_max_order_count_policy_invalid")
                if min_interval < GUARDED_WINDOW_MIN_INTERVAL_SEC:
                    return _fail("guarded_window_min_interval_policy_invalid")
                if is_guarded_one_shot and not bool(order_request.get("guarded_confirm_phrase_matched", False)):
                    return _fail("guarded_confirm_phrase_missing")
                if is_guarded_one_shot and not bool(order_request.get("guarded_one_shot_unlock_valid", False)):
                    return _fail("guarded_unlock_missing")
                if is_guarded_one_shot and bool(order_request.get("guarded_one_shot_unlock_consumed", False)):
                    return _fail("guarded_unlock_already_consumed")

            ak, sk = self._extract_upbit_keys()
            if not ak or not sk or len(ak) < 10 or len(sk) < 10:
                return _fail("upbit_key_not_ready")

            now_ts = time.time()
            current_action = side
            current_symbol = symbol

            last_action = str(self._aits_last_exec.get("action") or "").strip().lower()
            last_symbol = str(self._aits_last_exec.get("symbol") or "").strip().upper()
            last_ts = float(self._aits_last_exec.get("ts", 0.0) or 0.0)

            if (
                last_action == current_action
                and last_symbol == current_symbol
                and (now_ts - last_ts) < 10.0
            ):
                try:
                    print(
                        f"[AITS][ExecGuard] duplicate_block | action={current_action} | symbol={current_symbol}"
                    )
                except Exception:
                    pass
                return _fail("duplicate_blocked")

            identifier = f"aits-{uuid.uuid4().hex[:24]}"
            if side == "sell":
                params = {
                    "market": symbol,
                    "side": "ask",
                    "volume": f"{volume:.12f}".rstrip("0").rstrip("."),
                    "ord_type": "market",
                    "identifier": identifier,
                }
            else:
                params = {
                    "market": symbol,
                    "side": "bid",
                    "price": str(int(amount_krw)),
                    "ord_type": "price",
                    "identifier": identifier,
                }
            headers = self._make_auth_headers(params)

            self._aits_last_exec = {
                "action": current_action,
                "symbol": current_symbol,
                "ts": now_ts,
            }

            started = time.time()
            try:
                response = requests.post(
                    "https://api.upbit.com/v1/orders",
                    json=params,
                    headers=headers,
                    timeout=5,
                )
            except requests.Timeout:
                return _fail(
                    "order_timeout_unknown_state",
                    unknown_state=True,
                    request_id=request_id,
                    market=symbol,
                    side=side,
                    amount_krw=amount_krw,
                )
            except Exception as exc:
                return _fail(
                    f"order_request_exception:{type(exc).__name__}",
                    request_id=request_id,
                    market=symbol,
                    side=side,
                    amount_krw=amount_krw,
                )

            elapsed_ms = int((time.time() - started) * 1000)
            try:
                payload = response.json()
            except Exception:
                payload = {"text": str(response.text or "")[:500]}
            sanitized = self._sanitize_order_response(payload)
            http_status = int(getattr(response, "status_code", 0) or 0)
            if 200 <= http_status < 300:
                order_uuid = str(sanitized.get("uuid") or sanitized.get("identifier") or identifier)
                return {
                    "success": True,
                    "order_id": order_uuid,
                    "uuid": order_uuid,
                    "identifier": str(sanitized.get("identifier") or identifier),
                    "error": None,
                    "filled": sanitized.get("executed_volume"),
                    "avg_price": sanitized.get("price"),
                    "http_status": http_status,
                    "state": str(sanitized.get("state") or ""),
                    "market": str(sanitized.get("market") or symbol),
                    "side": side,
                    "amount_krw": amount_krw,
                    "volume": volume,
                    "response_sanitized": sanitized,
                    "elapsed_ms": elapsed_ms,
                    "request_id": request_id,
                    "real_order": True,
                    "submitted": True,
                }

            error = sanitized.get("error") if isinstance(sanitized.get("error"), dict) else {}
            return {
                "success": False,
                "order_id": None,
                "error": str(error.get("name") or sanitized.get("name") or f"http_{http_status}"),
                "error_message": str(error.get("message") or sanitized.get("message") or "")[:300],
                "filled": None,
                "avg_price": None,
                "http_status": http_status,
                "response_sanitized": sanitized,
                "elapsed_ms": elapsed_ms,
                "request_id": request_id,
                "real_order": False,
                "submitted": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "order_id": None,
                "error": f"internal_exception:{type(exc).__name__}",
                "filled": None,
                "avg_price": None,
                "real_order": False,
                "submitted": False,
            }

    def _extract_upbit_keys(self) -> tuple[str, str]:
        s = self._settings
        ak, sk = "", ""
        if s is not None:
            up = getattr(s, "upbit", None)
            if up is not None:
                if isinstance(up, dict):
                    ak = str(up.get("access_key") or "").strip()
                    sk = str(up.get("secret_key") or "").strip()
                else:
                    ak = str(getattr(up, "access_key", None) or "").strip()
                    sk = str(getattr(up, "secret_key", None) or "").strip()
        if not ak:
            ak = (os.getenv("UPBIT_ACCESS_KEY") or "").strip()
        if not sk:
            sk = (os.getenv("UPBIT_SECRET_KEY") or "").strip()
        return ak, sk

    def _make_auth_headers(self, params: dict | None = None) -> dict:
        ak, sk = self._extract_upbit_keys()
        payload = {"access_key": ak, "nonce": str(uuid.uuid4())}
        if params:
            query_string = unquote(urlencode(params, doseq=True))
            query_hash = hashlib.sha512(query_string.encode("utf-8")).hexdigest()
            payload["query_hash"] = query_hash
            payload["query_hash_alg"] = "SHA512"
        token = jwt.encode(payload, sk, algorithm="HS512")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return {"Authorization": f"Bearer {token}"}

    def _sanitize_order_response(self, payload: Any) -> dict:
        if not isinstance(payload, dict):
            return {"value": str(payload)[:500]}
        allowed = {
            "uuid",
            "identifier",
            "market",
            "side",
            "ord_type",
            "price",
            "state",
            "created_at",
            "volume",
            "remaining_volume",
            "reserved_fee",
            "remaining_fee",
            "paid_fee",
            "locked",
            "executed_volume",
            "trades_count",
            "error",
            "name",
            "message",
        }
        out = {}
        for key, value in payload.items():
            if key not in allowed:
                continue
            if isinstance(value, dict):
                out[key] = {
                    str(k): str(v)[:300]
                    for k, v in value.items()
                    if str(k) in {"name", "message"}
                }
            else:
                out[key] = str(value)[:300]
        return out


class _AccountsTraceCompleted(Exception):
    """Internal sentinel used after a local diagnostic branch completes."""


def classify_upbit_accounts_http_failure(status_code: Any) -> str:
    try:
        code = int(status_code)
    except Exception:
        return "unknown_accounts_read_failure"
    if code == 401:
        return "upbit_http_401_unauthorized"
    if code == 403:
        return "upbit_http_403_forbidden"
    if code == 429:
        return "upbit_http_429_rate_limited"
    return f"upbit_http_{code}"


def parse_upbit_accounts_krw_snapshot(rows: Any, trace: dict | None = None) -> dict:
    base_status = str((trace or {}).get("status") or "unknown_balance_source")
    response_shape = _response_shape(rows)
    result = {
        "available_krw": 0.0,
        "krw_balance": 0.0,
        "krw_locked": 0.0,
        "balance_status": base_status,
        "response_shape": response_shape,
        "krw_row_found": False,
        "krw_balance_raw_present": False,
        "krw_locked_raw_present": False,
        "fallback_reason": str((trace or {}).get("fallback_reason") or ""),
    }
    if not isinstance(rows, list):
        result["balance_status"] = "upbit_response_parse_error"
        result["fallback_reason"] = "upbit_response_parse_error"
        return result
    if (trace or {}).get("default_used") and not (trace or {}).get("success"):
        result["balance_status"] = base_status if base_status != "not_loaded" else "balance_not_loaded"
        result["fallback_reason"] = str((trace or {}).get("fallback_reason") or result["balance_status"])
        return result
    if not rows:
        result["balance_status"] = "accounts_response_empty"
        result["fallback_reason"] = "accounts_response_empty"
        return result
    krw_row: dict | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency") or "").strip().upper() == "KRW":
            krw_row = row
            break
    if krw_row is None:
        result["balance_status"] = "krw_balance_missing_from_accounts"
        result["fallback_reason"] = "krw_balance_missing_from_accounts"
        return result
    result["krw_row_found"] = True
    result["krw_balance_raw_present"] = krw_row.get("balance") is not None
    result["krw_locked_raw_present"] = krw_row.get("locked") is not None
    try:
        krw_balance = float(krw_row.get("balance"))
        krw_locked = float(krw_row.get("locked") or 0)
    except (TypeError, ValueError):
        result["balance_status"] = "upbit_response_parse_error"
        result["fallback_reason"] = "upbit_response_parse_error"
        return result
    available = max(0.0, krw_balance - krw_locked)
    result["krw_balance"] = krw_balance
    result["krw_locked"] = krw_locked
    result["available_krw"] = available
    if base_status == "ok":
        result["balance_status"] = "ok" if available > 0 else "actual_krw_balance_zero"
    elif base_status == "not_loaded":
        result["balance_status"] = "balance_not_loaded"
    return result


def _safe_upbit_key_fingerprint(access_key: str, secret_key: str) -> str:
    if not access_key or not secret_key:
        return ""
    digest = hashlib.sha256(f"{access_key}:{secret_key}".encode("utf-8")).hexdigest()
    return digest[:8]


def _response_shape(payload: Any) -> str:
    if isinstance(payload, list):
        return "empty" if not payload else "list"
    if isinstance(payload, dict):
        return "dict"
    if payload is None:
        return "empty"
    return "invalid"


def _sanitize_error_message(message: Any) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " ").strip()
    for marker in ("Bearer ", "access_key", "secret_key", "Authorization"):
        if marker in text:
            text = text.replace(marker, "[redacted]")
    return text[:240]


def _safe_response_error(response: Any) -> tuple[str, str]:
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        err = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        code = str(err.get("name") or err.get("code") or "")
        message = _sanitize_error_message(err.get("message") or "")
        return code[:80], message
    return "", ""


def _log_accounts_trace(line: str) -> None:
    try:
        print(line)
    except Exception:
        pass
    try:
        logging.getLogger("aits").info(line)
    except Exception:
        pass


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


svc_order = OrderService()
