from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class AIObservationReportFormatter:
    """Formats observation reports for compact UI/log display."""

    def format_report(self, report) -> dict:
        payload = self._to_dict(report)
        health_label = str(payload.get("health_label") or "")
        badge = self._badge(health_label, payload)
        return {
            "title": "AI 관측 리포트",
            "status": badge,
            "summary": str(payload.get("summary_line") or ""),
            "badges": [badge],
            "metadata": dict(payload.get("metadata") or {}),
        }

    def _badge(self, health_label: str, payload: dict) -> str:
        if health_label == "정상":
            return "정상"
        if health_label == "관찰 필요":
            return "주의"
        if health_label == "불안정":
            return "불안정"
        if health_label == "차단 필요":
            return "차단"
        if bool(payload.get("anomaly_detected")):
            return "불안정"
        if bool(payload.get("confidence_drift")) or bool(payload.get("scenario_drift")):
            return "주의"
        return "정상"

    def _to_dict(self, report: Any) -> dict:
        if isinstance(report, dict):
            return dict(report)
        if is_dataclass(report):
            return asdict(report)
        return {
            "health_label": getattr(report, "health_label", ""),
            "summary_line": getattr(report, "summary_line", ""),
            "metadata": getattr(report, "metadata", {}),
            "anomaly_detected": getattr(report, "anomaly_detected", False),
            "confidence_drift": getattr(report, "confidence_drift", False),
            "scenario_drift": getattr(report, "scenario_drift", False),
        }


def build_sample_observation_report_format() -> dict:
    from app.services.ai_observation_report import build_sample_observation_report

    return AIObservationReportFormatter().format_report(build_sample_observation_report())


__all__ = [
    "AIObservationReportFormatter",
    "build_sample_observation_report_format",
]
