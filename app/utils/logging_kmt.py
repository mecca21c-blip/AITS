"""KMTS-compat logging helpers — minimal throttle shim (no full framework)."""

from __future__ import annotations

import time
from typing import Any, Dict

_LAST_LOG_TS: Dict[str, float] = {}


def is_debug_mode() -> bool:
    try:
        return False
    except Exception:
        return False


def log_throttled(
    logger: Any,
    *args: Any,
    interval_sec: float = 5.0,
) -> bool:
    """(logger, key, message) or (logger, level, key, message). Never raises."""
    try:
        if len(args) == 2:
            level: Any = "info"
            key, message = args[0], args[1]
        elif len(args) == 3:
            level, key, message = args[0], args[1], args[2]
        else:
            return True

        key_s = str(key)
        now = time.time()
        gap = float(interval_sec)
        last = _LAST_LOG_TS.get(key_s, 0.0)
        if now - last < gap:
            return False
        _LAST_LOG_TS[key_s] = now

        if logger is None:
            return True

        msg = str(message)

        try:
            if isinstance(level, int) and callable(getattr(logger, "log", None)):
                logger.log(level, msg)
                return True
        except Exception:
            pass

        try:
            lv = str(level).lower() if not isinstance(level, int) else "info"
            name = {
                "debug": "debug",
                "info": "info",
                "warning": "warning",
                "warn": "warning",
                "error": "error",
                "critical": "critical",
            }.get(lv, "info")
            fn = getattr(logger, name, None)
            if callable(fn):
                fn(msg)
                return True
        except Exception:
            pass

        try:
            if callable(logger):
                logger(msg)
        except Exception:
            pass
        return True
    except Exception:
        return True
