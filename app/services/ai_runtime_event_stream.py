from __future__ import annotations

from app.services.ai_runtime_event import AIRuntimeEvent, build_sample_runtime_event


class AIRuntimeEventStream:
    """Memory-only runtime event stream for AI diagnostics."""

    def __init__(self) -> None:
        self._events: list[AIRuntimeEvent] = []

    def append(self, event: AIRuntimeEvent) -> AIRuntimeEvent:
        event.metadata = self._safe_metadata(event.metadata)
        self._events.append(event)
        return event

    def list_events(
        self,
        session_id: str | None = None,
        provider: str | None = None,
        event_type: str | None = None,
    ) -> list[AIRuntimeEvent]:
        events = list(self._events)
        if session_id:
            events = [event for event in events if event.session_id == str(session_id)]
        if provider:
            provider_filter = str(provider).strip().lower()
            events = [
                event
                for event in events
                if str(event.provider or "").strip().lower() == provider_filter
            ]
        if event_type:
            events = [event for event in events if event.event_type == str(event_type)]
        return events

    def latest(self, session_id: str | None = None) -> AIRuntimeEvent | None:
        events = self.list_events(session_id=session_id)
        return events[-1] if events else None

    def clear(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._events.clear()
            return
        self._events = [
            event for event in self._events if event.session_id != str(session_id)
        ]

    def build_summary(self) -> dict:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        providers: dict[str, int] = {}
        sessions: set[str] = set()
        for event in self._events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
            providers[event.provider] = providers.get(event.provider, 0) + 1
            if event.session_id:
                sessions.add(event.session_id)
        return {
            "total": len(self._events),
            "by_type": by_type,
            "by_severity": by_severity,
            "providers": providers,
            "sessions": len(sessions),
            "shadow_only": True,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }

    def _safe_metadata(self, metadata: dict | None) -> dict:
        safe = dict(metadata or {})
        safe.update(
            {
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
                "research_mode": True,
            }
        )
        return safe


def build_sample_event_stream_summary() -> dict:
    stream = AIRuntimeEventStream()
    stream.append(build_sample_runtime_event())
    return stream.build_summary()


__all__ = [
    "AIRuntimeEventStream",
    "build_sample_event_stream_summary",
]
