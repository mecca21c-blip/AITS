from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.ai_response_schema_validator import AIResponseSchemaValidator


@dataclass
class AIResponseQualityScore:
    provider: str
    quality_score: float
    schema_score: float
    completeness_score: float
    safety_score: float
    consistency_score: float
    warnings: list
    metadata: dict = field(default_factory=dict)


class AIResponseQualityScorer:
    """Scores response quality for diagnostics only."""

    def score(
        self,
        response: dict,
        validation_result: dict | object | None = None,
    ) -> AIResponseQualityScore:
        payload = dict(response or {}) if isinstance(response, dict) else {}
        validation = validation_result or AIResponseSchemaValidator().validate(payload)
        normalized = self._get_attr(validation, "normalized", {}) or {}
        missing_fields = self._get_attr(validation, "missing_fields", []) or []
        invalid_fields = self._get_attr(validation, "invalid_fields", []) or []
        warnings = list(self._get_attr(validation, "warnings", []) or [])

        schema_score = 1.0 if self._get_attr(validation, "valid", False) else 0.65
        schema_score -= min(0.4, 0.05 * len(invalid_fields))
        schema_score = self._clamp(schema_score)

        expected = 11
        completeness_score = self._clamp((expected - len(missing_fields)) / expected)
        safety_score = self._build_safety_score(normalized or payload)
        consistency_score = self._build_consistency_score(normalized or payload, warnings)
        quality_score = self._clamp(
            (schema_score * 0.35)
            + (completeness_score * 0.25)
            + (safety_score * 0.25)
            + (consistency_score * 0.15)
        )

        result = AIResponseQualityScore(
            provider=str(payload.get("provider") or normalized.get("provider") or "unknown"),
            quality_score=quality_score,
            schema_score=schema_score,
            completeness_score=completeness_score,
            safety_score=safety_score,
            consistency_score=consistency_score,
            warnings=warnings,
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
        try:
            logging.getLogger("aits").info(
                "[AITS][AIResponseQuality] quality_scored | provider=%s | score=%.3f",
                result.provider,
                result.quality_score,
            )
        except Exception:
            pass
        return result

    def _get_attr(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    def _build_safety_score(self, payload: dict) -> float:
        checks = [
            payload.get("applied") is False,
            payload.get("applied_to_action") is False,
            payload.get("real_order") is False,
            int(payload.get("submitted") or 0) == 0,
        ]
        return self._clamp(sum(1 for item in checks if item) / len(checks))

    def _build_consistency_score(self, payload: dict, warnings: list) -> float:
        score = 1.0
        suggestion = str(payload.get("suggestion") or "")
        next_action = str(payload.get("next_action") or "")
        if suggestion == "reject" and next_action == "buy":
            score -= 0.35
        if suggestion == "skip" and next_action in {"buy", "sell"}:
            score -= 0.35
        if warnings:
            score -= min(0.25, 0.03 * len(warnings))
        return self._clamp(score)

    def _clamp(self, value: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        if parsed < 0.0:
            return 0.0
        if parsed > 1.0:
            return 1.0
        return parsed


def build_sample_quality_score() -> AIResponseQualityScore:
    response = {
        "provider": "mock",
        "suggestion": "confirm",
        "confidence": 0.72,
        "briefing": "sample",
        "evidence": ["sample"],
        "next_action": "watch",
        "pool_action": {"action": "watch"},
        "scenario": {"name": "sideways_watch"},
        "eta": {"remaining_minutes": 30},
        "suggestion_only": True,
        "applied_to_action": False,
        "applied": False,
        "real_order": False,
        "submitted": 0,
    }
    validation = AIResponseSchemaValidator().validate(response)
    return AIResponseQualityScorer().score(response, validation)


__all__ = [
    "AIResponseQualityScore",
    "AIResponseQualityScorer",
    "build_sample_quality_score",
]
