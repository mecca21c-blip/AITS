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
class AISessionReport:
    session_id: str
    provider: str
    status: str
    diagnosis: str
    total_one_shots: int
    total_observations: int
    total_errors: int
    badges: list
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AISessionReportBuilder:
    """Builds compact session reports for UI/log diagnostics."""

    def build_report(
        self,
        session,
        diagnostics=None,
        memory_summary=None,
    ) -> AISessionReport:
        provider = str(self._get(session, "provider", "unknown") or "unknown")
        session_id = str(self._get(session, "session_id", "") or "")
        status = str(self._get(session, "status", "active") or "active")
        diagnosis = str(self._get(diagnostics, "diagnosis", "관찰 필요") or "관찰 필요")
        total_one_shots = self._safe_int(self._get(session, "total_one_shots", 0))
        total_observations = self._safe_int(self._get(session, "total_observations", 0))
        total_errors = self._safe_int(self._get(session, "total_errors", 0))
        badges = self._badges(session, diagnostics)
        memory_items = self._safe_int(self._get(memory_summary, "total_items", 0))
        summary_line = (
            f"{provider} | session={session_id} | one_shots={total_one_shots} | "
            f"observations={total_observations} | errors={total_errors} | "
            f"memory={memory_items} | {diagnosis}"
        )
        return AISessionReport(
            session_id=session_id,
            provider=provider,
            status=status,
            diagnosis=diagnosis,
            total_one_shots=total_one_shots,
            total_observations=total_observations,
            total_errors=total_errors,
            badges=badges,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _badges(self, session, diagnostics) -> list:
        diagnosis = str(self._get(diagnostics, "diagnosis", "") or "")
        badges: list[str] = []
        if diagnosis == "정상":
            badges.append("정상")
        elif diagnosis == "관찰 필요":
            badges.append("관찰 필요")
        elif diagnosis == "런타임 불안정":
            badges.append("불안정")
        elif diagnosis == "차단 필요":
            badges.append("쿨다운")
        if bool(self._get(session, "cooldown_blocked", False)):
            badges.append("쿨다운")
        if bool(self._get(session, "degraded", False)) and "불안정" not in badges:
            badges.append("불안정")
        badges.append("연구모드")
        return list(dict.fromkeys(badges))

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def build_sample_session_report() -> AISessionReport:
    from app.services.ai_runtime_memory import AIRuntimeMemory
    from app.services.ai_runtime_session_store import AIRuntimeSessionStore
    from app.services.ai_session_diagnostics import AISessionDiagnosticsBuilder

    store = AIRuntimeSessionStore()
    session = store.create_session("mock", "mock")
    store.record_one_shot(session.session_id)
    memory = AIRuntimeMemory()
    memory.set_item(session.session_id, "last_quality_score", {"quality_score": 0.8})
    diagnostics = AISessionDiagnosticsBuilder().build(
        session,
        observation_report={"health_label": "정상"},
        guard_report={"runtime_allowed": True},
        quality_score={"quality_score": 0.8},
    )
    return AISessionReportBuilder().build_report(
        session,
        diagnostics=diagnostics,
        memory_summary=memory.build_summary(),
    )


__all__ = [
    "AISessionReport",
    "AISessionReportBuilder",
    "build_sample_session_report",
]
