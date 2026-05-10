from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_incident import build_sample_runtime_incident


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
class AIRuntimeIncidentReport:
    total_incidents: int
    active_incidents: int
    critical_incidents: int
    dominant_incident_type: str
    highest_severity: str
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeIncidentReportBuilder:
    """Builds compact reports from runtime incidents."""

    def build_report(self, incidents: list) -> AIRuntimeIncidentReport:
        items = list(incidents or [])
        by_type: dict[str, int] = {}
        active = 0
        critical = 0
        highest = "info"
        for incident in items:
            incident_type = str(self._get(incident, "incident_type", "runtime_incident"))
            severity = str(self._get(incident, "severity", "info"))
            by_type[incident_type] = by_type.get(incident_type, 0) + 1
            if bool(self._get(incident, "active", False)):
                active += 1
            if severity == "critical":
                critical += 1
            highest = self._max_severity(highest, severity)
        dominant = max(by_type.items(), key=lambda item: item[1])[0] if by_type else "-"
        summary_line = (
            f"incidents={len(items)} | active={active} | critical={critical} | "
            f"highest={highest} | dominant={dominant}"
        )
        return AIRuntimeIncidentReport(
            total_incidents=len(items),
            active_incidents=active,
            critical_incidents=critical,
            dominant_incident_type=dominant,
            highest_severity=highest,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _max_severity(self, left: str, right: str) -> str:
        order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        return right if order.get(right, 0) > order.get(left, 0) else left

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_incident_report() -> AIRuntimeIncidentReport:
    return AIRuntimeIncidentReportBuilder().build_report([build_sample_runtime_incident()])


__all__ = [
    "AIRuntimeIncidentReport",
    "AIRuntimeIncidentReportBuilder",
    "build_sample_incident_report",
]
