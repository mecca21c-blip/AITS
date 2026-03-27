"""Minimal auth shim for UI boot compatibility."""

from __future__ import annotations

import os
from typing import Any


def init_db(base_dir: Any) -> None:
    """Initialize auth DB path safely without blocking boot."""
    try:
        target = str(base_dir or "").strip() or "."
        os.makedirs(target, exist_ok=True)
    except Exception:
        # Boot compatibility shim: never raise from init.
        return
