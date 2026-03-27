"""Order execution interface skeleton (Phase 1). No real exchange calls."""


class OrderService:
    """Minimal order placement surface for Order Adapter injection (live hook)."""

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
