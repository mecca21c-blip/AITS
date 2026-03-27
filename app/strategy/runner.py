"""Minimal KMTS-compatible strategy runner state container (no live trading loop).

UI and tabs expect these symbols and module-level state; implementations are
best-effort and must not raise through public entrypoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Module state (KMTS interface surface)
# ---------------------------------------------------------------------------

_RUNNING: bool = False
_SESSION_SNAPSHOT_SYMBOLS: Optional[List[str]] = None
_SESSION_SNAPSHOT_WL_BOOSTED: int = 0
_SESSION_SNAPSHOT_BL_EXCLUDED: int = 0

_LAST_SELL_ATTEMPT_TS: float = 0.0
_LAST_SELL_BLOCK_REASON_COUNTER: Dict[str, int] = {}
_LAST_SELL_ELIG_DECISION: Dict[str, Any] = {}
_LAST_SELL_ELIG_TOP_REASON: str = ""
_LAST_EXIT_SOURCE: str = ""

_EXIT_DISPLAY_FOR_UI: Dict[str, Dict[str, Any]] = {}

_LAST_SETTINGS: Any = None
_SIMULATE: bool = False


# ---------------------------------------------------------------------------
# Core lifecycle
# ---------------------------------------------------------------------------


def start_strategy(settings: Any = None) -> None:
    global _RUNNING, _LAST_SETTINGS
    try:
        _LAST_SETTINGS = settings
        _RUNNING = True
    except Exception:
        _RUNNING = True


def stop_strategy() -> None:
    global _RUNNING
    try:
        _RUNNING = False
    except Exception:
        _RUNNING = False


def set_session_snapshot(symbols: Any, wl_boosted: int = 0, bl_excluded: int = 0) -> None:
    global _SESSION_SNAPSHOT_SYMBOLS, _SESSION_SNAPSHOT_WL_BOOSTED, _SESSION_SNAPSHOT_BL_EXCLUDED
    try:
        out: List[str] = []
        if isinstance(symbols, (list, tuple, set)):
            for x in symbols:
                s = str(x or "").strip().upper()
                if s:
                    out.append(s)
        elif symbols is not None:
            s = str(symbols or "").strip().upper()
            if s:
                out = [s]
        _SESSION_SNAPSHOT_SYMBOLS = out if out else None
        _SESSION_SNAPSHOT_WL_BOOSTED = int(wl_boosted or 0)
        _SESSION_SNAPSHOT_BL_EXCLUDED = int(bl_excluded or 0)
    except Exception:
        _SESSION_SNAPSHOT_SYMBOLS = None
        _SESSION_SNAPSHOT_WL_BOOSTED = 0
        _SESSION_SNAPSHOT_BL_EXCLUDED = 0


def get_session_snapshot_summary() -> Dict[str, Any]:
    try:
        syms = list(_SESSION_SNAPSHOT_SYMBOLS or [])
        return {
            "count": len(syms),
            "wl_boosted": int(_SESSION_SNAPSHOT_WL_BOOSTED),
            "bl_excluded": int(_SESSION_SNAPSHOT_BL_EXCLUDED),
            "symbols": syms,
        }
    except Exception:
        return {
            "count": 0,
            "wl_boosted": 0,
            "bl_excluded": 0,
            "symbols": [],
        }


# ---------------------------------------------------------------------------
# Sell diagnostics (read-only getters)
# ---------------------------------------------------------------------------


def get_last_sell_attempt_ts() -> float:
    try:
        return float(_LAST_SELL_ATTEMPT_TS)
    except Exception:
        return 0.0


def get_last_sell_block_reason_counter() -> Dict[str, int]:
    try:
        return dict(_LAST_SELL_BLOCK_REASON_COUNTER)
    except Exception:
        return {}


def get_last_sell_elig_decision() -> Dict[str, Any]:
    try:
        return dict(_LAST_SELL_ELIG_DECISION)
    except Exception:
        return {}


def get_last_sell_elig_top_reason() -> str:
    try:
        return str(_LAST_SELL_ELIG_TOP_REASON or "")
    except Exception:
        return ""


def get_last_exit_source() -> str:
    try:
        return str(_LAST_EXIT_SOURCE or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Exit display / AI thresholds
# ---------------------------------------------------------------------------


def get_exit_display_for_ui() -> Dict[str, Dict[str, Any]]:
    try:
        return {k: dict(v) for k, v in (_EXIT_DISPLAY_FOR_UI or {}).items()}
    except Exception:
        return {}


def _get_ai_exit_thresholds(by_m: Any) -> Tuple[float, float, str]:
    """Return (tp_pct, sl_pct, extra). Third value reserved for KMTS compatibility."""
    try:
        if isinstance(by_m, dict):
            tp_pct = float(by_m.get("tp_pct", 3.0) or 3.0)
            sl_pct = float(by_m.get("sl_pct", 2.0) or 2.0)
            return (tp_pct, sl_pct, "")
        return (3.0, 2.0, "")
    except Exception:
        return (3.0, 2.0, "")


# ---------------------------------------------------------------------------
# Low-strength imports (UI compatibility)
# ---------------------------------------------------------------------------


def set_symbols_from_settings(settings: Any = None) -> bool:
    try:
        global _LAST_SETTINGS
        _LAST_SETTINGS = settings
        return True
    except Exception:
        return True


def set_simulate(simulate: bool) -> None:
    global _SIMULATE
    try:
        _SIMULATE = bool(simulate)
    except Exception:
        _SIMULATE = False


def get_ui_holdings() -> List[Any]:
    try:
        return []
    except Exception:
        return []


def get_ui_totals() -> Dict[str, float]:
    try:
        return {"total_asset": 0.0, "available_krw": 0.0}
    except Exception:
        return {"total_asset": 0.0, "available_krw": 0.0}
