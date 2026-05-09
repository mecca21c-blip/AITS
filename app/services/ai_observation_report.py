from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIObservationReport:
    provider: str
    total_records: int
    avg_confidence: float
    avg_quality: float
    confidence_drift: bool
    scenario_drift: bool
    anomaly_detected: bool
    health_label: str
    summary_line: str
    metadata: dict = field(default_factory=dict)


class AIObservationReportBuilder:
    """Builds compact AI observatory reports for research diagnostics."""

    def build_report(
        self,
        provider: str,
        store_summary: dict,
        confidence_drift: Any = None,
        scenario_drift: Any = None,
        anomaly: Any = None,
    ) -> AIObservationReport:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        summary = dict(store_summary or {})
        total_records = int(summary.get("total") or 0)
        avg_confidence = self._safe_float(summary.get("avg_confidence"))
        avg_quality = self._safe_float(summary.get("avg_quality"))
        confidence_drift_detected = bool(self._get(confidence_drift, "drift_detected", False))
        scenario_drift_detected = bool(self._get(scenario_drift, "drift_detected", False))
        anomaly_detected = bool(self._get(anomaly, "anomaly_detected", False))
        severity = str(self._get(anomaly, "severity", "info") or "info")
        health_label = self._health_label(
            confidence_drift_detected,
            scenario_drift_detected,
            anomaly_detected,
            severity,
        )
        summary_line = (
            f"{provider_name} | records={total_records} | "
            f"confidence={avg_confidence:.2f} | quality={avg_quality:.2f} | {health_label}"
        )
        return AIObservationReport(
            provider=provider_name,
            total_records=total_records,
            avg_confidence=avg_confidence,
            avg_quality=avg_quality,
            confidence_drift=confidence_drift_detected,
            scenario_drift=scenario_drift_detected,
            anomaly_detected=anomaly_detected,
            health_label=health_label,
            summary_line=summary_line,
            metadata={
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
                "research_mode": True,
            },
        )

    def _health_label(
        self,
        confidence_drift: bool,
        scenario_drift: bool,
        anomaly_detected: bool,
        severity: str,
    ) -> str:
        if anomaly_detected and severity == "critical":
            return "차단 필요"
        if anomaly_detected or (confidence_drift and scenario_drift):
            return "불안정"
        if confidence_drift or scenario_drift:
            return "관찰 필요"
        return "정상"

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    def _safe_float(self, value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_observation_report() -> AIObservationReport:
    from app.services.ai_confidence_drift_detector import AIConfidenceDriftDetector
    from app.services.ai_observation_record import build_sample_observation_record
    from app.services.ai_observation_store import AIObservationStore
    from app.services.ai_provider_behavior_anomaly import AIProviderBehaviorAnomalyDetector
    from app.services.ai_scenario_drift_detector import AIScenarioDriftDetector

    store = AIObservationStore()
    store.append(build_sample_observation_record())
    summary = store.build_summary()
    records = store.list_records()
    confidence = AIConfidenceDriftDetector().detect(records, "mock")
    scenario = AIScenarioDriftDetector().detect(records, "mock")
    anomaly = AIProviderBehaviorAnomalyDetector().detect(records, "mock")
    return AIObservationReportBuilder().build_report("mock", summary, confidence, scenario, anomaly)


__all__ = [
    "AIObservationReport",
    "AIObservationReportBuilder",
    "build_sample_observation_report",
]
