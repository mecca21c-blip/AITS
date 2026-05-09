from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.services.ai_runtime_session import AIRuntimeSession


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
    }


class AIRuntimeSessionStore:
    """Memory-only runtime session store for AI diagnostics."""

    def __init__(self) -> None:
        self._sessions: dict[str, AIRuntimeSession] = {}

    def create_session(self, provider: str, model: str = "-") -> AIRuntimeSession:
        timestamp = _now()
        session = AIRuntimeSession(
            session_id=f"ai-session-{uuid4().hex}",
            provider=str(provider or "unknown").strip().lower() or "unknown",
            model=str(model or "-"),
            started_at=timestamp,
            last_seen_at=timestamp,
            status="active",
            total_one_shots=0,
            total_observations=0,
            total_errors=0,
            degraded=False,
            cooldown_blocked=False,
            metadata=_metadata(),
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> AIRuntimeSession | None:
        return self._sessions.get(str(session_id or ""))

    def latest(self, provider: str | None = None) -> AIRuntimeSession | None:
        sessions = self.list_sessions(provider=provider)
        return sessions[-1] if sessions else None

    def touch(self, session_id: str):
        session = self.get_session(session_id)
        if session is not None:
            session.last_seen_at = _now()
        return session

    def record_one_shot(
        self,
        session_id: str,
        success: bool = True,
        error: bool = False,
    ):
        session = self.touch(session_id)
        if session is not None:
            session.total_one_shots += 1
            if error or not success:
                session.total_errors += 1
                session.status = "error"
            else:
                session.status = "active"
            session.metadata.update(_metadata())
        return session

    def record_observation(self, session_id: str):
        session = self.touch(session_id)
        if session is not None:
            session.total_observations += 1
            session.metadata.update(_metadata())
        return session

    def mark_degraded(self, session_id: str, degraded: bool = True):
        session = self.touch(session_id)
        if session is not None:
            session.degraded = bool(degraded)
            if degraded:
                session.status = "degraded"
            session.metadata.update(_metadata())
        return session

    def mark_cooldown(self, session_id: str, blocked: bool = True):
        session = self.touch(session_id)
        if session is not None:
            session.cooldown_blocked = bool(blocked)
            if blocked:
                session.status = "cooldown"
            session.metadata.update(_metadata())
        return session

    def list_sessions(self, provider: str | None = None) -> list[AIRuntimeSession]:
        provider_filter = str(provider or "").strip().lower()
        sessions = list(self._sessions.values())
        if provider_filter:
            sessions = [
                session
                for session in sessions
                if str(session.provider or "").strip().lower() == provider_filter
            ]
        return sessions

    def build_summary(self) -> dict:
        sessions = self.list_sessions()
        providers: dict[str, int] = {}
        active = 0
        degraded = 0
        cooldown_blocked = 0
        for session in sessions:
            provider = str(session.provider or "unknown")
            providers[provider] = providers.get(provider, 0) + 1
            if session.status == "active":
                active += 1
            if session.degraded:
                degraded += 1
            if session.cooldown_blocked:
                cooldown_blocked += 1
        return {
            "total_sessions": len(sessions),
            "providers": providers,
            "active": active,
            "degraded": degraded,
            "cooldown_blocked": cooldown_blocked,
            "shadow_only": True,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }


def build_sample_runtime_session_summary() -> dict:
    store = AIRuntimeSessionStore()
    session = store.create_session("mock", "mock")
    store.record_one_shot(session.session_id)
    return store.build_summary()


__all__ = [
    "AIRuntimeSessionStore",
    "build_sample_runtime_session_summary",
]
