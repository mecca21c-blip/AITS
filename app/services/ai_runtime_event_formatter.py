from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class AIRuntimeEventFormatter:
    """Formats runtime events and timeline items for UI-ready feeds."""

    def format_event(self, event) -> dict:
        payload = self._to_dict(event)
        severity = str(payload.get("severity") or "info")
        return {
            "label": str(payload.get("title") or payload.get("event_type") or "Runtime event"),
            "message": str(payload.get("message") or ""),
            "severity": severity,
            "badge": self._badge(severity),
            "metadata": dict(payload.get("metadata") or {}),
        }

    def format_timeline_item(self, item) -> dict:
        payload = self._to_dict(item)
        severity = str(payload.get("severity") or "info")
        return {
            "label": str(payload.get("title") or payload.get("event_type") or "Runtime event"),
            "message": str(payload.get("message") or ""),
            "severity": severity,
            "badge": self._badge(severity),
            "metadata": dict(payload.get("metadata") or {}),
        }

    def _badge(self, severity: str) -> str:
        if severity == "warning":
            return "주의"
        if severity == "error":
            return "오류"
        if severity == "critical":
            return "긴급"
        return "정보"

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_formatted_event() -> dict:
    from app.services.ai_runtime_event import build_sample_runtime_event

    return AIRuntimeEventFormatter().format_event(build_sample_runtime_event())


__all__ = [
    "AIRuntimeEventFormatter",
    "build_sample_formatted_event",
]
