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


def has_any_user() -> bool:
    """Compatibility stub for UI auth flow."""
    try:
        return False
    except Exception:
        return False


def create_user(email: str, password: str) -> tuple[bool, str]:
    """Compatibility stub for UI auth flow."""
    try:
        if not str(email or "").strip() or not str(password or "").strip():
            return (False, "invalid_input")
        return (True, "created")
    except Exception:
        return (False, "error")


def verify_login(email: str, password: str) -> tuple[bool, str]:
    """Compatibility stub for UI auth flow."""
    try:
        if not str(email or "").strip() or not str(password or "").strip():
            return (False, "invalid_input")
        return (True, "ok")
    except Exception:
        return (False, "error")
