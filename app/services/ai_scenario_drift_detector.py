from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AIScenarioDriftResult:
    provider: str
    drift_detected: bool
    dominant_scenario: str
    dominant_ratio: float
    scenario_counts: dict
    reason: str
    metadata: dict = field(default_factory=dict)


class AIScenarioDriftDetector:
    """Detects scenario concentration from supplied records only."""

    def detect(
        self,
        records: list,
        provider: str,
        window: int = 50,
    ) -> AIScenarioDriftResult:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        filtered = [
            record
            for record in list(records or [])
            if str(self._get(record, "provider", "")).strip().lower() == provider_name
        ][-max(1, int(window or 50)) :]
        if not filtered:
            return self._result(provider_name, False, "-", 0.0, {}, "not_enough_records")

        counts: dict[str, int] = {}
        for record in filtered:
            scenario = str(self._get(record, "scenario", "-") or "-")
            counts[scenario] = counts.get(scenario, 0) + 1
        dominant_scenario, dominant_count = max(counts.items(), key=lambda item: item[1])
        ratio = dominant_count / len(filtered) if filtered else 0.0
        drift_detected = ratio >= 0.7
        reason = "scenario_concentration_high" if drift_detected else "scenario_distribution_normal"
        return self._result(provider_name, drift_detected, dominant_scenario, ratio, counts, reason)

    def _get(self, record, name: str, fallback):
        if isinstance(record, dict):
            return record.get(name, fallback)
        return getattr(record, name, fallback)

    def _result(
        self,
        provider: str,
        drift_detected: bool,
        dominant_scenario: str,
        dominant_ratio: float,
        scenario_counts: dict,
        reason: str,
    ) -> AIScenarioDriftResult:
        return AIScenarioDriftResult(
            provider=provider,
            drift_detected=bool(drift_detected),
            dominant_scenario=dominant_scenario,
            dominant_ratio=dominant_ratio,
            scenario_counts=dict(scenario_counts or {}),
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


def build_sample_scenario_drift_result() -> AIScenarioDriftResult:
    records = [
        {"provider": "mock", "scenario": "횡보 관찰형"},
        {"provider": "mock", "scenario": "횡보 관찰형"},
        {"provider": "mock", "scenario": "횡보 관찰형"},
        {"provider": "mock", "scenario": "리스크 회피형"},
    ]
    return AIScenarioDriftDetector().detect(records, "mock", window=4)


__all__ = [
    "AIScenarioDriftResult",
    "AIScenarioDriftDetector",
    "build_sample_scenario_drift_result",
]
