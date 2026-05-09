from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
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
class AIRuntimeDashboardSummary:
    total_providers: int
    healthy: int
    degraded: int
    cooldown_blocked: int
    avg_quality_score: float
    avg_confidence: float
    dominant_status: str
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeDashboardSummaryBuilder:
    """Aggregates runtime UI bundles for a future dashboard surface."""

    def build_summary(self, bundles: list) -> AIRuntimeDashboardSummary:
        payloads = [self._to_dict(bundle) for bundle in list(bundles or [])]
        total = len(payloads)
        healthy = sum(1 for item in payloads if self._diagnosis(item) == "정상")
        degraded = sum(1 for item in payloads if bool(item.get("degraded", False)))
        cooldown_blocked = sum(1 for item in payloads if bool(item.get("cooldown_blocked", False)))
        quality_values = [self._safe_float(item.get("quality_score")) for item in payloads]
        confidence_values = [
            self._safe_float((item.get("metadata") or {}).get("confidence"))
            for item in payloads
        ]
        status_counts: dict[str, int] = {}
        for item in payloads:
            status = self._diagnosis(item)
            status_counts[status] = status_counts.get(status, 0) + 1
        dominant_status = (
            max(status_counts.items(), key=lambda pair: pair[1])[0] if status_counts else "-"
        )
        avg_quality = sum(quality_values) / total if total else 0.0
        avg_confidence = sum(confidence_values) / total if total else 0.0
        summary_line = (
            f"providers={total} | healthy={healthy} | degraded={degraded} | "
            f"cooldown={cooldown_blocked} | status={dominant_status}"
        )
        return AIRuntimeDashboardSummary(
            total_providers=total,
            healthy=healthy,
            degraded=degraded,
            cooldown_blocked=cooldown_blocked,
            avg_quality_score=avg_quality,
            avg_confidence=avg_confidence,
            dominant_status=dominant_status,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _diagnosis(self, item: dict) -> str:
        return str(item.get("diagnosis") or item.get("health_label") or "-")

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_dashboard_summary() -> AIRuntimeDashboardSummary:
    from app.services.ai_runtime_ui_bundle import build_sample_runtime_ui_bundle

    return AIRuntimeDashboardSummaryBuilder().build_summary(
        [build_sample_runtime_ui_bundle()]
    )


__all__ = [
    "AIRuntimeDashboardSummary",
    "AIRuntimeDashboardSummaryBuilder",
    "build_sample_dashboard_summary",
]
