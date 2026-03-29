"""Minimal live holdings shim for PortfolioTab (no full portfolio engine)."""

from __future__ import annotations

from typing import Any, Dict, List


def fetch_live_holdings(force: bool = False) -> Dict[str, Any]:
    _ = force
    result: Dict[str, Any] = {
        "ok": True,
        "items": [],
        "krw": 0.0,
        "total_eval": 0.0,
        "err": "",
    }
    try:
        from app.services.order_service import svc_order
        from app.services.upbit import get_all_markets

        rows = svc_order.fetch_accounts() or []
        live_markets: set[str] = set()
        try:
            live_markets = set(get_all_markets() or [])
        except Exception:
            live_markets = set()
        krw = 0.0
        items: List[Dict[str, Any]] = []
        for a in rows:
            if not isinstance(a, dict):
                continue
            cur = str(a.get("currency") or "").strip()
            balance = float(a.get("balance") or 0.0)
            locked = float(a.get("locked") or 0.0)
            avg_buy_price = float(a.get("avg_buy_price") or 0.0)
            if cur == "KRW":
                krw = float(balance or 0.0)
                continue
            if not cur:
                continue
            qty = max(balance - locked, 0.0)
            symbol = f"KRW-{cur}"
            market_supported = symbol in live_markets if live_markets else False
            px = avg_buy_price
            eval_krw = qty * avg_buy_price
            items.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "balance": balance,
                    "locked": locked,
                    "avg_price": avg_buy_price,
                    "px": px,
                    "eval_krw": eval_krw,
                    "market_supported": market_supported,
                }
            )
        total_eval = krw + sum(float(it.get("eval_krw") or 0.0) for it in items)
        result["items"] = items
        result["krw"] = krw
        result["total_eval"] = total_eval
        result["ok"] = True
        result["err"] = ""
    except Exception as e:
        result = {
            "ok": False,
            "items": [],
            "krw": 0.0,
            "total_eval": 0.0,
            "err": str(e)[:200],
        }
    print(
        f"[AITS][HoldingsService] fetch_live_holdings called | ok={result.get('ok')} | items={len(result.get('items', []))} | krw={result.get('krw', 0.0)}"
    )
    print(
        f"[AITS][HoldingsService] supported_markets items={len(result.get('items', []))} unsupported={len([x for x in result.get('items', []) if not x.get('market_supported')])}"
    )
    return result
