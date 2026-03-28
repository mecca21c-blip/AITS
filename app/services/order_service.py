"""Order execution interface skeleton (Phase 1). No real exchange calls."""

import uuid

import jwt
import requests


class OrderService:
    """Minimal order placement surface for Order Adapter injection (live hook)."""

    def __init__(self):
        self._settings = None
        self._simulate = True
        self._trading_enabled = True

    def set_settings(self, settings) -> bool:
        try:
            self._settings = settings
            if settings is not None:
                self._simulate = not bool(getattr(settings, "live_trade", False))
            print(
                f"[AITS][OrderService] set_settings called | live_trade={getattr(settings, 'live_trade', None) if settings is not None else None}"
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
            if not ak or not sk or len(ak) < 10 or len(sk) < 10:
                rows = list(default_rows)
            else:
                payload = {"access_key": ak, "nonce": str(uuid.uuid4())}
                token = jwt.encode(payload, sk, algorithm="HS256")
                if isinstance(token, bytes):
                    token = token.decode("utf-8")
                headers = {"Authorization": f"Bearer {token}"}
                r = requests.get(
                    "https://api.upbit.com/v1/accounts",
                    headers=headers,
                    timeout=5,
                )
                if r.ok:
                    data = r.json()
                    if isinstance(data, list):
                        rows = data
                    else:
                        rows = list(default_rows)
                else:
                    rows = list(default_rows)
        except Exception:
            rows = list(default_rows)
        print(
            f"[AITS][OrderService] fetch_accounts called | rows={len(rows) if isinstance(rows, list) else 0}"
        )
        return rows if isinstance(rows, list) else list(default_rows)

    def place_order(self, order_request: dict) -> dict:
        try:
            print(f"[AITS][OrderService] place_order called | request={order_request}")
        except Exception:
            pass
        def _fail(error: str) -> dict:
            return {
                "success": False,
                "order_id": None,
                "error": error,
                "filled": None,
                "avg_price": None,
            }

        try:
            if not isinstance(order_request, dict):
                return _fail("invalid_order_request")

            symbol = order_request.get("symbol")
            side = order_request.get("side")
            amount_krw = order_request.get("amount_krw")
            volume = order_request.get("volume")
            order_type = order_request.get("order_type") or "market"
            _ = order_type  # accepted for forward compatibility; logic is market-oriented

            if not symbol:
                return _fail("invalid_symbol")

            if side not in ("buy", "sell"):
                return _fail("invalid_side")

            if side == "buy":
                if not isinstance(amount_krw, (int, float)) or amount_krw <= 0:
                    return _fail("invalid_amount_krw")

            if side == "sell":
                if not isinstance(volume, (int, float)) or volume <= 0:
                    return _fail("invalid_volume")

            return {
                "success": True,
                "order_id": "mock_order",
                "error": None,
                "filled": None,
                "avg_price": None,
            }
        except Exception as e:
            return {
                "success": False,
                "order_id": None,
                "error": f"internal_exception:{str(e)}",
                "filled": None,
                "avg_price": None,
            }


svc_order = OrderService()
