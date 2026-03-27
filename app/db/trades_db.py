"""Minimal trades DB shim for UI boot (no real persistence)."""

from __future__ import annotations

import os
from typing import Any, Dict, List

positions: List[Any] = []


def init_trades_db(data_dir: Any = None) -> bool:
    try:
        d = str(data_dir or "").strip()
        if d:
            os.makedirs(d, exist_ok=True)
        return True
    except Exception:
        return True


def load_pnl_by_strategy(*args: Any, **kwargs: Any) -> List[Any]:
    try:
        return []
    except Exception:
        return []


def get_last_strategy_info(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        return {}
    except Exception:
        return {}
