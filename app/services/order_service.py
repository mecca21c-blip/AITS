"""Order execution interface.

The only live path currently supported is the explicit AITS minimum real-order
test: KRW-BTC market buy for 5,000 KRW with a 6,000 KRW hard cap.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from typing import Any
from urllib.parse import unquote, urlencode

import jwt
import requests


class OrderService:
    """Minimal order placement surface for Order Adapter injection."""

    def __init__(self):
        self._settings = None
        self._simulate = True
        self._trading_enabled = True
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
        try:
            ak, sk = self._extract_upbit_keys()
            if not ak or not sk or len(ak) < 10 or len(sk) < 10:
                rows = list(default_rows)
            else:
                r = requests.get(
                    "https://api.upbit.com/v1/accounts",
                    headers=self._make_auth_headers({}),
                    timeout=5,
                )
                if r.ok:
                    data = r.json()
                    rows = data if isinstance(data, list) else list(default_rows)
                else:
                    rows = list(default_rows)
        except Exception:
            rows = list(default_rows)
        print(
            f"[AITS][OrderService] fetch_accounts called | rows={len(rows) if isinstance(rows, list) else 0}"
        )
        return rows if isinstance(rows, list) else list(default_rows)

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
            order_type = str(order_request.get("order_type") or "market").strip().lower()
            request_id = str(order_request.get("request_id") or uuid.uuid4().hex)

            if not bool(order_request.get("live_minimum_real_order_test", False)):
                return _fail("live_minimum_real_order_test_flag_missing")
            if symbol != "KRW-BTC":
                return _fail("unsupported_live_symbol")
            if side != "buy":
                return _fail("unsupported_live_side")
            if order_type != "market":
                return _fail("unsupported_live_order_type")
            if abs(amount_krw - 5000.0) > 0.0001:
                return _fail("unsupported_live_amount")
            if amount_krw > 6000.0:
                return _fail("hard_cap_exceeded")

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
            params = {
                "market": "KRW-BTC",
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
                    "side": "buy",
                    "amount_krw": amount_krw,
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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


svc_order = OrderService()
