"""Minimal UI-boot compatibility shim for legacy upbit service imports.

This module intentionally provides only lightweight wrappers/fallbacks so
`app.ui.app_gui` can import expected symbols without full exchange integration.
"""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from app.services.market_feed import (
    get_markets as _mf_get_markets,
    get_tickers as _mf_get_tickers,
    get_top_markets_by_volume as _mf_get_top_markets_by_volume,
)


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
    """Pass-through wrapper to market_feed.get_tickers."""
    try:
        return _mf_get_tickers(markets)
    except Exception:
        return {}


def get_top_markets_by_volume(*args, **kwargs):
    """Pass-through wrapper to market_feed.get_top_markets_by_volume."""
    try:
        return _mf_get_top_markets_by_volume(*args, **kwargs)
    except Exception:
        return []


def get_all_markets(*args, **kwargs):
    """Pass-through wrapper to market_feed.get_markets."""
    try:
        return _mf_get_markets()
    except Exception:
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
