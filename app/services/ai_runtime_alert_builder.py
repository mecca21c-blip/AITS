from __future__ import annotations

from typing import Any

from app.services.ai_runtime_incident import AIRuntimeIncident, build_runtime_incident


class AIRuntimeAlertBuilder:
    """Converts runtime diagnostics into local incidents without sending alerts."""

    def build_alerts(
        self,
        one_shot_result: dict,
        observation_report=None,
        anomaly=None,
        diagnostics=None,
        guard_report=None,
    ) -> list[AIRuntimeIncident]:
        result = dict(one_shot_result or {})
        observation = self._to_dict(observation_report)
        anomaly_payload = self._to_dict(anomaly)
        diag = self._to_dict(diagnostics)
        guard = self._to_dict(guard_report)
        provider = str(result.get("provider") or observation.get("provider") or "unknown")
        session_id = str(result.get("session_id") or diag.get("session_id") or "")
        incidents: list[AIRuntimeIncident] = []

        if bool(observation.get("anomaly_detected", False)) or bool(
            anomaly_payload.get("anomaly_detected", False)
        ):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "anomaly_detected",
                    "warning",
                    "Anomaly detected",
                    "Runtime observation anomaly detected.",
                )
            )
        if bool(observation.get("confidence_drift", False)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "confidence_drift",
                    "warning",
                    "Confidence drift",
                    "Observation confidence drift detected.",
                )
            )
        if bool(observation.get("scenario_drift", False)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "scenario_drift",
                    "warning",
                    "Scenario drift",
                    "Observation scenario drift detected.",
                )
            )
        if bool(result.get("safety_blocked", False)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "runtime_blocked",
                    "error",
                    "Runtime blocked",
                    "Runtime safety block is active.",
                )
            )
        if bool(result.get("degraded", False) or guard.get("degraded", False) or diag.get("degraded", False)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "degraded_runtime",
                    "warning",
                    "Runtime degraded",
                    "Provider runtime is degraded.",
                )
            )
        if bool(result.get("cooldown_blocked", False) or guard.get("cooldown_blocked", False)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "cooldown_active",
                    "error",
                    "Cooldown active",
                    "Provider cooldown is blocking runtime.",
                )
            )
        if not bool(result.get("schema_valid", True)):
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "schema_instability",
                    "warning",
                    "Schema instability",
                    "Provider response schema was invalid.",
                )
            )
        if self._safe_int(result.get("submitted", 0)) > 0:
            incidents.append(
                self._incident(
                    provider,
                    session_id,
                    "safety_violation",
                    "critical",
                    "Safety violation",
                    "submitted greater than zero detected in runtime diagnostics.",
                )
            )
        return incidents

    def _incident(
        self,
        provider: str,
        session_id: str,
        incident_type: str,
        severity: str,
        title: str,
        description: str,
    ) -> AIRuntimeIncident:
        return build_runtime_incident(
            provider=provider,
            session_id=session_id,
            incident_type=incident_type,
            severity=severity,
            title=title,
            description=description,
        )

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if value is None:
            return {}
        return {
            name: getattr(value, name)
            for name in dir(value)
            if not name.startswith("_") and not callable(getattr(value, name))
        }

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def build_sample_runtime_alerts() -> list[AIRuntimeIncident]:
    return AIRuntimeAlertBuilder().build_alerts(
        {
            "provider": "mock",
            "session_id": "sample-runtime-session",
            "schema_valid": True,
            "submitted": 0,
        },
        observation_report={"anomaly_detected": True},
    )


__all__ = [
    "AIRuntimeAlertBuilder",
    "build_sample_runtime_alerts",
]
