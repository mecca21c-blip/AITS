from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AIProviderBehaviorAnomalyResult:
    provider: str
    anomaly_detected: bool
    anomaly_type: str
    severity: str
    reason: str
    metadata: dict = field(default_factory=dict)


class AIProviderBehaviorAnomalyDetector:
    """Detects provider behavior anomalies from observation records only."""

    def detect(self, records: list, provider: str) -> AIProviderBehaviorAnomalyResult:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        filtered = [
            record
            for record in list(records or [])
            if str(self._get(record, "provider", "")).strip().lower() == provider_name
        ]
        if not filtered:
            return self._result(provider_name, False, "none", "info", "not_enough_records")

        if any(self._safe_int(self._get(record, "submitted", 0)) > 0 for record in filtered):
            return self._result(
                provider_name,
                True,
                "safety_violation",
                "critical",
                "submitted_greater_than_zero_detected",
            )
        if any(bool(self._get(record, "cooldown_blocked", False)) for record in filtered):
            return self._result(provider_name, True, "runtime_blocked", "warning", "cooldown_blocked_detected")

        total = len(filtered)
        avg_quality = sum(self._safe_float(self._get(record, "quality_score", 0.0)) for record in filtered) / total
        schema_invalid_ratio = sum(
            1 for record in filtered if not bool(self._get(record, "schema_valid", False))
        ) / total
        recovery_ratio = sum(
            1 for record in filtered if bool(self._get(record, "recovery_used", False))
        ) / total

        if avg_quality < 0.4:
            return self._result(provider_name, True, "low_quality", "warning", "avg_quality_below_threshold")
        if schema_invalid_ratio >= 0.3:
            return self._result(
                provider_name,
                True,
                "schema_instability",
                "warning",
                "schema_invalid_ratio_high",
            )
        if recovery_ratio >= 0.4:
            return self._result(
                provider_name,
                True,
                "format_instability",
                "warning",
                "recovery_used_ratio_high",
            )
        return self._result(provider_name, False, "none", "info", "provider_behavior_normal")

    def _get(self, record, name: str, fallback):
        if isinstance(record, dict):
            return record.get(name, fallback)
        return getattr(record, name, fallback)

    def _safe_float(self, value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _result(
        self,
        provider: str,
        anomaly_detected: bool,
        anomaly_type: str,
        severity: str,
        reason: str,
    ) -> AIProviderBehaviorAnomalyResult:
        return AIProviderBehaviorAnomalyResult(
            provider=provider,
            anomaly_detected=bool(anomaly_detected),
            anomaly_type=anomaly_type,
            severity=severity,
            reason=reason,
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


def build_sample_behavior_anomaly_result() -> AIProviderBehaviorAnomalyResult:
    records = [
        {"provider": "mock", "quality_score": 0.35, "schema_valid": True, "recovery_used": False, "submitted": 0},
        {"provider": "mock", "quality_score": 0.38, "schema_valid": True, "recovery_used": False, "submitted": 0},
    ]
    return AIProviderBehaviorAnomalyDetector().detect(records, "mock")


__all__ = [
    "AIProviderBehaviorAnomalyResult",
    "AIProviderBehaviorAnomalyDetector",
    "build_sample_behavior_anomaly_result",
]
