from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any


@dataclass
class ProviderReliabilityScore:
    provider: str
    reliability_score: float
    total_records: int
    win_count: int
    loss_count: int
    hold_stability: float
    confidence_consistency: float
    scenario_accuracy: float
    last_updated: str
    metadata: dict = field(default_factory=dict)


class AIProviderReliabilityAnalyzer:
    """Single-provider AI reliability skeleton. It never calls providers or orders."""

    def build_reliability_score(
        self,
        tracker_summary: dict,
        history_records: list[dict],
        provider: str,
    ) -> ProviderReliabilityScore:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        records = [
            record
            for record in (history_records if isinstance(history_records, list) else [])
            if self._record_provider(record) == provider_name
        ]
        total_records = len(records)
        win_count = self._safe_int((tracker_summary or {}).get("win_count"), 0)
        loss_count = self._safe_int((tracker_summary or {}).get("loss_count"), 0)

        if total_records < 3:
            hold_stability = 0.5
            confidence_consistency = 0.5
            scenario_accuracy = 0.5
            reliability_score = 0.5
        else:
            win_rate = win_count / max(1, win_count + loss_count)
            hold_stability = self._calculate_hold_stability(records)
            confidence_consistency = self._calculate_confidence_consistency(records)
            scenario_accuracy = self._calculate_scenario_accuracy(records)
            reliability_score = (
                (win_rate * 0.35)
                + (hold_stability * 0.25)
                + (confidence_consistency * 0.25)
                + (scenario_accuracy * 0.15)
            )

        score = ProviderReliabilityScore(
            provider=provider_name,
            reliability_score=self._clamp(reliability_score),
            total_records=total_records,
            win_count=win_count,
            loss_count=loss_count,
            hold_stability=self._clamp(hold_stability),
            confidence_consistency=self._clamp(confidence_consistency),
            scenario_accuracy=self._clamp(scenario_accuracy),
            last_updated=datetime.now(timezone.utc).isoformat(),
            metadata=self._safety_metadata(),
        )
        logging.getLogger("aits").info(
            "[AITS][AIReliability] reliability_score_built | provider=%s | score=%.3f",
            score.provider,
            score.reliability_score,
        )
        return score

    def _record_provider(self, record: dict) -> str:
        if not isinstance(record, dict):
            return "unknown"
        shadow = record.get("ai_shadow") if isinstance(record.get("ai_shadow"), dict) else {}
        return str(shadow.get("provider") or record.get("provider") or "unknown").strip().lower() or "unknown"

    def _calculate_hold_stability(self, records: list[dict]) -> float:
        actions = [self._next_action(record) for record in records]
        if not actions:
            return 0.5
        stable_actions = {"hold", "watch", "wait", "long_watch"}
        stable_count = sum(1 for action in actions if action in stable_actions)
        oscillation_penalty = self._count_action_changes(actions) / max(1, len(actions) - 1)
        return self._clamp((stable_count / len(actions)) * (1.0 - (oscillation_penalty * 0.5)))

    def _calculate_confidence_consistency(self, records: list[dict]) -> float:
        values = [self._confidence(record) for record in records]
        if len(values) < 2:
            return 0.5
        avg = sum(values) / len(values)
        variance = sum((value - avg) ** 2 for value in values) / len(values)
        return self._clamp(1.0 - min(1.0, variance * 4.0))

    def _calculate_scenario_accuracy(self, records: list[dict]) -> float:
        scenarios = [self._scenario_name(record) for record in records if self._scenario_name(record)]
        if not scenarios:
            return 0.5
        most_common = max(set(scenarios), key=scenarios.count)
        return self._clamp(scenarios.count(most_common) / len(scenarios))

    def _next_action(self, record: dict) -> str:
        shadow = record.get("ai_shadow") if isinstance(record, dict) and isinstance(record.get("ai_shadow"), dict) else {}
        return str(shadow.get("next_action") or record.get("next_action") or "wait").strip().lower() or "wait"

    def _confidence(self, record: dict) -> float:
        shadow = record.get("ai_shadow") if isinstance(record, dict) and isinstance(record.get("ai_shadow"), dict) else {}
        return self._clamp(self._safe_float(shadow.get("confidence"), 0.0))

    def _scenario_name(self, record: dict) -> str:
        shadow = record.get("ai_shadow") if isinstance(record, dict) and isinstance(record.get("ai_shadow"), dict) else {}
        scenario = shadow.get("scenario") if isinstance(shadow.get("scenario"), dict) else {}
        if isinstance(scenario, dict):
            return str(scenario.get("label_ko") or scenario.get("name") or "").strip()
        return ""

    def _count_action_changes(self, actions: list[str]) -> int:
        return sum(1 for left, right in zip(actions, actions[1:]) if left != right)

    def _safety_metadata(self) -> dict:
        return {
            "real_order": False,
            "virtual_only": True,
            "submitted": 0,
            "research_mode": True,
        }

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _clamp(self, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.5


def build_sample_provider_reliability_score() -> ProviderReliabilityScore:
    records = [
        {
            "ai_shadow": {
                "provider": "mock",
                "next_action": "watch",
                "confidence": 0.62,
                "scenario": {"label_ko": "횡보 관찰형", "name": "sideways_watch"},
            }
        },
        {
            "ai_shadow": {
                "provider": "mock",
                "next_action": "hold",
                "confidence": 0.66,
                "scenario": {"label_ko": "횡보 관찰형", "name": "sideways_watch"},
            }
        },
        {
            "ai_shadow": {
                "provider": "mock",
                "next_action": "watch",
                "confidence": 0.64,
                "scenario": {"label_ko": "횡보 관찰형", "name": "sideways_watch"},
            }
        },
    ]
    tracker_summary = {
        "win_count": 1,
        "loss_count": 0,
    }
    return AIProviderReliabilityAnalyzer().build_reliability_score(
        tracker_summary=tracker_summary,
        history_records=records,
        provider="mock",
    )


__all__ = [
    "ProviderReliabilityScore",
    "AIProviderReliabilityAnalyzer",
    "build_sample_provider_reliability_score",
]
