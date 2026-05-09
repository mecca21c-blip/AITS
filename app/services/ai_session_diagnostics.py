from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class AISessionDiagnostics:
    session_id: str
    provider: str
    healthy: bool
    degraded: bool
    cooldown_blocked: bool
    error_rate: float
    observation_ready: bool
    quality_ready: bool
    guard_ready: bool
    diagnosis: str
    metadata: dict = field(default_factory=_metadata)


class AISessionDiagnosticsBuilder:
    """Builds compact diagnostics for a single runtime session."""

    def build(
        self,
        session,
        observation_report: dict | object | None = None,
        guard_report: dict | object | None = None,
        quality_score: dict | object | None = None,
    ) -> AISessionDiagnostics:
        total_one_shots = self._safe_int(self._get(session, "total_one_shots", 0))
        total_errors = self._safe_int(self._get(session, "total_errors", 0))
        error_rate = total_errors / total_one_shots if total_one_shots else 0.0
        observation_ready = bool(observation_report)
        quality_ready = bool(quality_score)
        guard_ready = bool(guard_report)
        cooldown_blocked = bool(
            self._get(session, "cooldown_blocked", False)
            or self._get(guard_report, "cooldown_blocked", False)
        )
        degraded = bool(self._get(session, "degraded", False) or error_rate >= 0.3)
        if self._get(guard_report, "degraded", False):
            degraded = True

        healthy = bool(not degraded and not cooldown_blocked)
        diagnosis = self._diagnosis(
            healthy=healthy,
            degraded=degraded,
            cooldown_blocked=cooldown_blocked,
            observation_ready=observation_ready,
        )
        return AISessionDiagnostics(
            session_id=str(self._get(session, "session_id", "") or ""),
            provider=str(self._get(session, "provider", "unknown") or "unknown"),
            healthy=healthy,
            degraded=degraded,
            cooldown_blocked=cooldown_blocked,
            error_rate=error_rate,
            observation_ready=observation_ready,
            quality_ready=quality_ready,
            guard_ready=guard_ready,
            diagnosis=diagnosis,
            metadata=_metadata(),
        )

    def _diagnosis(
        self,
        healthy: bool,
        degraded: bool,
        cooldown_blocked: bool,
        observation_ready: bool,
    ) -> str:
        if cooldown_blocked:
            return "차단 필요"
        if degraded:
            return "런타임 불안정"
        if not observation_ready:
            return "관찰 필요"
        if healthy:
            return "정상"
        return "관찰 필요"

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def build_sample_session_diagnostics() -> AISessionDiagnostics:
    from app.services.ai_runtime_session_store import AIRuntimeSessionStore

    store = AIRuntimeSessionStore()
    session = store.create_session("mock", "mock")
    store.record_one_shot(session.session_id)
    return AISessionDiagnosticsBuilder().build(
        session,
        observation_report={"health_label": "정상"},
        guard_report={"runtime_allowed": True},
        quality_score={"quality_score": 0.8},
    )


__all__ = [
    "AISessionDiagnostics",
    "AISessionDiagnosticsBuilder",
    "build_sample_session_diagnostics",
]
