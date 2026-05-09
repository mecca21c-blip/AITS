from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AIConfidenceDriftResult:
    provider: str
    drift_detected: bool
    direction: str
    avg_recent: float
    avg_baseline: float
    delta: float
    volatility: float
    reason: str
    metadata: dict = field(default_factory=dict)


class AIConfidenceDriftDetector:
    """Detects confidence drift from provided observation records only."""

    def detect(
        self,
        records: list,
        provider: str,
        recent_window: int = 10,
        baseline_window: int = 50,
    ) -> AIConfidenceDriftResult:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        filtered = [
            record
            for record in list(records or [])
            if str(self._get(record, "provider", "")).strip().lower() == provider_name
        ]
        if len(filtered) < 2:
            return self._result(provider_name, False, "stable", 0.0, 0.0, 0.0, 0.0, "not_enough_records")

        recent_values = [self._confidence(record) for record in filtered[-max(1, recent_window) :]]
        baseline_values = [self._confidence(record) for record in filtered[-max(1, baseline_window) :]]
        avg_recent = self._avg(recent_values)
        avg_baseline = self._avg(baseline_values)
        delta = avg_recent - avg_baseline
        volatility = self._volatility(recent_values)

        if volatility >= 0.25:
            return self._result(
                provider_name,
                True,
                "unstable",
                avg_recent,
                avg_baseline,
                delta,
                volatility,
                "confidence_volatility_high",
            )
        if abs(delta) >= 0.2:
            direction = "up" if delta > 0 else "down"
            return self._result(
                provider_name,
                True,
                direction,
                avg_recent,
                avg_baseline,
                delta,
                volatility,
                "confidence_delta_threshold",
            )
        return self._result(
            provider_name,
            False,
            "stable",
            avg_recent,
            avg_baseline,
            delta,
            volatility,
            "confidence_stable",
        )

    def _get(self, record, name: str, fallback):
        if isinstance(record, dict):
            return record.get(name, fallback)
        return getattr(record, name, fallback)

    def _confidence(self, record) -> float:
        try:
            value = float(self._get(record, "confidence", 0.0))
        except (TypeError, ValueError):
            return 0.0
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _avg(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _volatility(self, values: list[float]) -> float:
        if not values:
            return 0.0
        avg = self._avg(values)
        variance = sum((value - avg) ** 2 for value in values) / len(values)
        return variance ** 0.5

    def _result(
        self,
        provider: str,
        drift_detected: bool,
        direction: str,
        avg_recent: float,
        avg_baseline: float,
        delta: float,
        volatility: float,
        reason: str,
    ) -> AIConfidenceDriftResult:
        return AIConfidenceDriftResult(
            provider=provider,
            drift_detected=bool(drift_detected),
            direction=direction,
            avg_recent=avg_recent,
            avg_baseline=avg_baseline,
            delta=delta,
            volatility=volatility,
            reason=reason,
            metadata=self._metadata(),
        )

    def _metadata(self) -> dict:
        return {
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }


def build_sample_confidence_drift_result() -> AIConfidenceDriftResult:
    records = [
        {"provider": "mock", "confidence": 0.45},
        {"provider": "mock", "confidence": 0.50},
        {"provider": "mock", "confidence": 0.75},
        {"provider": "mock", "confidence": 0.80},
    ]
    return AIConfidenceDriftDetector().detect(records, "mock", recent_window=2, baseline_window=4)


__all__ = [
    "AIConfidenceDriftResult",
    "AIConfidenceDriftDetector",
    "build_sample_confidence_drift_result",
]
