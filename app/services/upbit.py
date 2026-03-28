"""Minimal UI-boot compatibility shim for legacy upbit service imports.

This module intentionally provides only lightweight wrappers/fallbacks so
`app.ui.app_gui` can import expected symbols without full exchange integration.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import requests

from app.services.market_feed import (
    get_markets as _mf_get_markets,
    get_tickers as _mf_get_tickers,
    get_top_markets_by_volume as _mf_get_top_markets_by_volume,
)


class _TickerRow(dict):
    """Ticker as dict; str(row) is market code for legacy `str(s)` symbol extraction."""

    def __str__(self) -> str:  # noqa: D105
        try:
            return str(self.get("market") or "")
        except Exception:
            return ""


def _normalize_ticker_dict(market: str, d: Any) -> Dict[str, Any]:
    try:
        if not isinstance(d, dict):
            d = {}
        m = str(market or d.get("market") or "")
        return {
            "market": m,
            "trade_price": float(d.get("trade_price") or 0.0),
            "acc_trade_price_24h": float(d.get("acc_trade_price_24h") or 0.0),
            "signed_change_rate": float(d.get("signed_change_rate") or 0.0),
            "signed_change_price": float(d.get("signed_change_price") or 0.0),
            "high_price": float(d.get("high_price") or 0.0),
            "low_price": float(d.get("low_price") or 0.0),
            "prev_closing_price": float(d.get("prev_closing_price") or 0.0),
            "acc_trade_volume_24h": float(d.get("acc_trade_volume_24h") or 0.0),
            "timestamp": int(d.get("timestamp") or 0),
        }
    except Exception:
        return {
            "market": str(market or ""),
            "trade_price": 0.0,
            "acc_trade_price_24h": 0.0,
            "signed_change_rate": 0.0,
            "signed_change_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "prev_closing_price": 0.0,
            "acc_trade_volume_24h": 0.0,
            "timestamp": 0,
        }


_KRW_SYM_TAIL = re.compile(r"^[A-Za-z0-9]+$")


def _valid_krw_market(s: str) -> bool:
    if not s or not s.startswith("KRW-"):
        return False
    if any(ch in s for ch in " ,\t\n{}\"'"):
        return False
    tail = s[4:]
    if not tail or not _KRW_SYM_TAIL.match(tail):
        return False
    return True


def test_public_ping(*args, **kwargs):
    """Simple public API health check. Never raises."""
    timeout = kwargs.get("timeout", 3)
    try:
        r = requests.get("https://api.upbit.com/v1/market/all", timeout=timeout)
        ok = bool(r.ok)
        return {"ok": ok, "status_code": int(r.status_code)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_tickers(markets, *args, **kwargs):
    """Return list[dict] ticker rows (KMTS UI contract). Never raises."""
    out: List[Dict[str, Any]] = []
    raw_markets: List[Any] = []
    try:
        if markets is None:
            raw_markets = []
        elif isinstance(markets, str):
            raw_markets = [markets]
        else:
            raw_markets = list(markets)
    except Exception:
        raw_markets = []

    valid_markets: List[str] = []
    seen: set[str] = set()
    for x in raw_markets:
        s = str(x).strip()
        if not _valid_krw_market(s):
            continue
        if s in seen:
            continue
        seen.add(s)
        valid_markets.append(s)

    raw_n = len(raw_markets)
    print(
        f"[AITS][upbit] tickers_request raw={raw_n} valid={len(valid_markets)} sample={valid_markets[:3]}"
    )

    if not valid_markets:
        print(
            f"[AITS][upbit] tickers_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return out

    try:
        ttl = float(kwargs.get("ttl", 1.5))
        raw = _mf_get_tickers(valid_markets, ttl)
        if isinstance(raw, dict):
            for mk, row in raw.items():
                r = _TickerRow()
                r.update(_normalize_ticker_dict(str(mk), row))
                out.append(r)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    r = _TickerRow()
                    r.update(
                        _normalize_ticker_dict(str(item.get("market") or ""), item)
                    )
                    out.append(r)
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    r = _TickerRow()
                    r.update(_normalize_ticker_dict(str(item[0]), item[1]))
                    out.append(r)
        print(
            f"[AITS][upbit] tickers_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return out
    except Exception:
        print(
            f"[AITS][upbit] tickers_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return []


def get_top_markets_by_volume(*args, **kwargs):
    """Return list[dict] top markets (KMTS UI contract). Never raises."""
    out: List[Dict[str, Any]] = []
    try:
        raw = _mf_get_top_markets_by_volume(*args, **kwargs)
        if not isinstance(raw, list):
            raw = []
        for item in raw:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                m, d = item[0], item[1]
                r = _TickerRow()
                r.update(_normalize_ticker_dict(str(m), d))
                out.append(r)
            elif isinstance(item, dict):
                r = _TickerRow()
                r.update(_normalize_ticker_dict(str(item.get("market") or ""), item))
                out.append(r)
        print(
            f"[AITS][upbit] top_markets_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return out
    except Exception:
        print(
            f"[AITS][upbit] top_markets_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return []


def get_all_markets(*args, **kwargs):
    """Return list[str] market codes (KMTS UI contract). Never raises."""
    out: List[str] = []
    try:
        raw = _mf_get_markets(*args, **kwargs)
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str) and x.strip():
                    out.append(x.strip())
                elif isinstance(x, dict):
                    m = x.get("market")
                    if m is not None:
                        s = str(m).strip()
                        if s:
                            out.append(s)
        print(
            f"[AITS][upbit] all_markets_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return out
    except Exception:
        print(
            f"[AITS][upbit] all_markets_return count={len(out)} type={type(out[0]).__name__ if out else 'empty'}"
        )
        return []


def get_holdings_snapshot(*args, **kwargs):
    """Safe empty holdings fallback for UI compatibility."""
    try:
        return {"ok": True, "items": [], "krw": 0.0, "total_eval": 0.0}
    except Exception:
        return {"ok": False, "items": [], "krw": 0.0, "total_eval": 0.0}


def get_holdings_snapshot_auto(*args, **kwargs):
    """Safe empty holdings fallback for UI compatibility."""
    try:
        return {"ok": True, "items": [], "krw": 0.0, "total_eval": 0.0}
    except Exception:
        return {"ok": False, "items": [], "krw": 0.0, "total_eval": 0.0}
