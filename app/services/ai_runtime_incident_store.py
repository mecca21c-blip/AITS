from __future__ import annotations

from app.services.ai_runtime_incident import (
    AIRuntimeIncident,
    build_sample_runtime_incident,
)


class AIRuntimeIncidentStore:
    """Memory-only incident store for AI runtime diagnostics."""

    def __init__(self) -> None:
        self._incidents: list[AIRuntimeIncident] = []

    def append(self, incident: AIRuntimeIncident) -> AIRuntimeIncident:
        incident.metadata = self._safe_metadata(incident.metadata)
        incident.active = bool(incident.active)
        incident.acknowledged = bool(incident.acknowledged)
        self._incidents.append(incident)
        return incident

    def list_incidents(
        self,
        active_only: bool = False,
        provider: str | None = None,
    ) -> list[AIRuntimeIncident]:
        incidents = list(self._incidents)
        if active_only:
            incidents = [incident for incident in incidents if bool(incident.active)]
        if provider:
            provider_filter = str(provider).strip().lower()
            incidents = [
                incident
                for incident in incidents
                if str(incident.provider or "").strip().lower() == provider_filter
            ]
        return incidents

    def latest(self, provider: str | None = None) -> AIRuntimeIncident | None:
        incidents = self.list_incidents(provider=provider)
        return incidents[-1] if incidents else None

    def acknowledge(self, incident_id: str) -> AIRuntimeIncident | None:
        incident = self._find(incident_id)
        if incident is not None:
            incident.acknowledged = True
            incident.metadata = self._safe_metadata(incident.metadata)
        return incident

    def resolve(self, incident_id: str) -> AIRuntimeIncident | None:
        incident = self._find(incident_id)
        if incident is not None:
            incident.active = False
            incident.metadata = self._safe_metadata(incident.metadata)
        return incident

    def clear(self) -> None:
        self._incidents.clear()

    def build_summary(self) -> dict:
        providers: dict[str, int] = {}
        by_type: dict[str, int] = {}
        active = 0
        critical = 0
        for incident in self._incidents:
            providers[incident.provider] = providers.get(incident.provider, 0) + 1
            by_type[incident.incident_type] = by_type.get(incident.incident_type, 0) + 1
            if incident.active:
                active += 1
            if incident.severity == "critical":
                critical += 1
        return {
            "total": len(self._incidents),
            "active": active,
            "critical": critical,
            "providers": providers,
            "by_type": by_type,
            "shadow_only": True,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }

    def _find(self, incident_id: str) -> AIRuntimeIncident | None:
        target = str(incident_id or "")
        for incident in self._incidents:
            if incident.incident_id == target:
                return incident
        return None

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


def build_sample_incident_store_summary() -> dict:
    store = AIRuntimeIncidentStore()
    store.append(build_sample_runtime_incident())
    return store.build_summary()


__all__ = [
    "AIRuntimeIncidentStore",
    "build_sample_incident_store_summary",
]
