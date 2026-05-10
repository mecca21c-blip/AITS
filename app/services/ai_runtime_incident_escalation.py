from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_incident import build_runtime_incident


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
class AIRuntimeEscalationResult:
    escalation_required: bool
    escalation_level: str
    reason: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeIncidentEscalation:
    """Evaluates local incident severity without sending external alerts."""

    def evaluate(self, incidents: list) -> AIRuntimeEscalationResult:
        critical = 0
        errors = 0
        warnings = 0
        for incident in list(incidents or []):
            severity = str(self._get(incident, "severity", "info"))
            if severity == "critical":
                critical += 1
            elif severity == "error":
                errors += 1
            elif severity == "warning":
                warnings += 1
        if critical:
            return self._result(True, "긴급", "critical_incident_present")
        if errors >= 3:
            return self._result(True, "높음", "error_incident_threshold")
        if warnings >= 5:
            return self._result(True, "중간", "warning_incident_threshold")
        return self._result(False, "낮음", "no_escalation_threshold_met")

    def _result(
        self,
        required: bool,
        level: str,
        reason: str,
    ) -> AIRuntimeEscalationResult:
        return AIRuntimeEscalationResult(
            escalation_required=bool(required),
            escalation_level=level,
            reason=reason,
            metadata=_metadata(),
        )

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_escalation_result() -> AIRuntimeEscalationResult:
    incident = build_runtime_incident(
        provider="mock",
        session_id="sample-runtime-session",
        incident_type="safety_violation",
        severity="critical",
        title="Safety violation",
        description="sample critical incident",
    )
    return AIRuntimeIncidentEscalation().evaluate([incident])


__all__ = [
    "AIRuntimeEscalationResult",
    "AIRuntimeIncidentEscalation",
    "build_sample_escalation_result",
]
