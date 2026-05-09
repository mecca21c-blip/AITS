from __future__ import annotations

from dataclasses import asdict

from app.services.ai_confidence_drift_detector import AIConfidenceDriftDetector
from app.services.ai_observation_adapter import AIObservationAdapter
from app.services.ai_observation_report import AIObservationReportBuilder
from app.services.ai_observation_store import AIObservationStore
from app.services.ai_provider_behavior_anomaly import AIProviderBehaviorAnomalyDetector
from app.services.ai_scenario_drift_detector import AIScenarioDriftDetector


class AIObservationPipeline:
    """Runs the dry-run observation flow from one-shot output to report."""

    def __init__(self) -> None:
        self.store = AIObservationStore()
        self.adapter = AIObservationAdapter()
        self.confidence_drift_detector = AIConfidenceDriftDetector()
        self.scenario_drift_detector = AIScenarioDriftDetector()
        self.anomaly_detector = AIProviderBehaviorAnomalyDetector()
        self.report_builder = AIObservationReportBuilder()

    def run_once(self, one_shot_result: dict, symbol: str = "KRW-BTC") -> dict:
        record = self.adapter.from_one_shot_result(one_shot_result, symbol=symbol)
        safe_record = self.store.append(record)
        provider = str(safe_record.provider or "unknown").strip().lower() or "unknown"
        records = self.store.list_records(provider=provider)
        summary = self.store.build_summary()
        confidence_drift = self.confidence_drift_detector.detect(records, provider)
        scenario_drift = self.scenario_drift_detector.detect(records, provider)
        anomaly = self.anomaly_detector.detect(records, provider)
        report = self.report_builder.build_report(
            provider,
            summary,
            confidence_drift,
            scenario_drift,
            anomaly,
        )

        return {
            "record_ready": True,
            "store_total": int(summary.get("total") or 0),
            "confidence_drift": asdict(confidence_drift),
            "scenario_drift": asdict(scenario_drift),
            "anomaly_detected": bool(anomaly.anomaly_detected),
            "anomaly": asdict(anomaly),
            "report_ready": True,
            "report": asdict(report),
            "health_label": str(report.health_label or ""),
            "summary_line": str(report.summary_line or ""),
            "submitted": 0,
            "real_order": False,
        }


def build_sample_observation_pipeline_result() -> dict:
    result = {
        "provider": "mock",
        "model": "mock",
        "suggestion": "skip",
        "next_action": "wait",
        "state": "idle",
        "response_quality_score": 0.85,
        "schema_valid": True,
        "recovery_used": False,
        "degraded": False,
        "cooldown_blocked": False,
        "shadow_record": {
            "confidence": 0.55,
            "scenario": {"label_ko": "sample observation", "name": "sample"},
        },
    }
    return AIObservationPipeline().run_once(result)


__all__ = [
    "AIObservationPipeline",
    "build_sample_observation_pipeline_result",
]
