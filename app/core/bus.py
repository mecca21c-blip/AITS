"""Minimal in-memory pub/sub shim for UI boot compatibility."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

_SUBSCRIBERS: Dict[str, List[Callable[[Any], None]]] = {}


def subscribe(topic, callback):
    """Register callback for a topic. Never raises."""
    try:
        t = str(topic or "").strip()
        if not t or not callable(callback):
            return
        _SUBSCRIBERS.setdefault(t, []).append(callback)
    except Exception:
        return


def publish(topic, payload=None):
    """Publish payload to topic subscribers. Never raises."""
    try:
        t = str(topic or "").strip()
        callbacks = list(_SUBSCRIBERS.get(t, []))
        for cb in callbacks:
            try:
                cb(payload)
            except Exception:
                continue
    except Exception:
        return
