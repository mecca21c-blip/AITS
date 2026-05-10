from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_event import build_sample_runtime_event


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "order": "latest_first",
    }


@dataclass
class AIRuntimeTimelineItem:
    time: str
    provider: str
    event_type: str
    severity: str
    title: str
    message: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeTimelineBuilder:
    """Builds a latest-first timeline from runtime events."""

    def build_timeline(
        self,
        events: list,
        limit: int = 50,
    ) -> list[AIRuntimeTimelineItem]:
        sorted_events = sorted(
            list(events or []),
            key=lambda event: str(self._get(event, "timestamp", "")),
            reverse=True,
        )
        items: list[AIRuntimeTimelineItem] = []
        for event in sorted_events[: max(0, int(limit or 50))]:
            metadata = _metadata()
            event_metadata = self._get(event, "metadata", {})
            if isinstance(event_metadata, dict):
                metadata.update(event_metadata)
            metadata["order"] = "latest_first"
            items.append(
                AIRuntimeTimelineItem(
                    time=str(self._get(event, "timestamp", "") or ""),
                    provider=str(self._get(event, "provider", "unknown") or "unknown"),
                    event_type=str(self._get(event, "event_type", "runtime_event") or "runtime_event"),
                    severity=str(self._get(event, "severity", "info") or "info"),
                    title=str(self._get(event, "title", "") or ""),
                    message=str(self._get(event, "message", "") or ""),
                    metadata=metadata,
                )
            )
        return items

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_runtime_timeline() -> list[AIRuntimeTimelineItem]:
    return AIRuntimeTimelineBuilder().build_timeline([build_sample_runtime_event()])


__all__ = [
    "AIRuntimeTimelineItem",
    "AIRuntimeTimelineBuilder",
    "build_sample_runtime_timeline",
]
