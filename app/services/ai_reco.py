"""Minimal AI recommendation shim for UI boot (no real engine)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

_LAST_DECISION: Dict[str, Any] = {
    "actual_engine": "",
    "selected_engine": "",
}
_LAST_ADVICE: Dict[str, Any] = {
    "source": "local",
    "fallback": False,
    "items": [],
    "decision_summary": "",
    "reason_code": "",
}
_SCHEDULER_STARTED: bool = False

_publish_fn: Optional[Callable[..., Any]] = None
_settings_getter: Optional[Callable[..., Any]] = None


def _safe_publish(topic: str, payload: Any = None) -> None:
    fn = _publish_fn
    if fn is None:
        return
    try:
        fn(topic, payload)
    except Exception:
        try:
            fn(topic, payload=payload)
        except Exception:
            pass


def start_scheduler(settings_getter: Any = None, publish_fn: Any = None) -> bool:
    global _SCHEDULER_STARTED, _publish_fn, _settings_getter
    try:
        _settings_getter = settings_getter
        _publish_fn = publish_fn if callable(publish_fn) else None
        _SCHEDULER_STARTED = True
        return True
    except Exception:
        _SCHEDULER_STARTED = True
        return True


def update(payload: Any = None, from_boot: bool = False) -> Dict[str, Any]:
    global _LAST_ADVICE, _LAST_DECISION
    try:
        out: Dict[str, Any] = {
            "ok": True,
            "source": "local",
            "fallback": False,
            "items": [],
            "decision_summary": "",
            "reason_code": "",
        }
        if isinstance(payload, dict):
            for k in ("ok", "source", "fallback", "items", "decision_summary", "reason_code"):
                if k in payload:
                    out[k] = payload[k]
        _LAST_ADVICE = dict(out)
        _LAST_DECISION = {
            "actual_engine": "",
            "selected_engine": "",
        }
        if isinstance(payload, dict):
            if "actual_engine" in payload:
                _LAST_DECISION["actual_engine"] = str(payload.get("actual_engine") or "")
            if "selected_engine" in payload:
                _LAST_DECISION["selected_engine"] = str(payload.get("selected_engine") or "")
        _safe_publish("ai.reco.updated", out)
        _safe_publish("ai.reco.items", out.get("items"))
        _safe_publish("ai.reco.strategy_suggested", out)
        return out
    except Exception:
        fallback = {
            "ok": True,
            "source": "local",
            "fallback": False,
            "items": [],
            "decision_summary": "",
            "reason_code": "",
        }
        _LAST_ADVICE = dict(fallback)
        return fallback


def get_last_decision() -> Dict[str, Any]:
    try:
        return dict(_LAST_DECISION)
    except Exception:
        return {"actual_engine": "", "selected_engine": ""}


def poll_gpt_future() -> Dict[str, Any]:
    try:
        return dict(_LAST_DECISION) if _LAST_DECISION else {}
    except Exception:
        return {}
