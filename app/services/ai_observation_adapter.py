from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.ai_observation_record import AIObservationRecord


class AIObservationAdapter:
    """Converts one-shot harness output into a shadow-only observation record."""

    def from_one_shot_result(
        self,
        result: dict,
        symbol: str = "KRW-BTC",
    ) -> AIObservationRecord:
        payload = dict(result or {})
        shadow_record = payload.get("shadow_record")
        if not isinstance(shadow_record, dict):
            shadow_record = {}

        return AIObservationRecord(
            provider=str(payload.get("provider") or "unknown"),
            model=str(payload.get("model") or "-"),
            symbol=str(symbol or "KRW-BTC"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            suggestion=str(payload.get("suggestion") or "skip"),
            next_action=str(payload.get("next_action") or "wait"),
            confidence=self._safe_float(shadow_record.get("confidence")),
            scenario=self._scenario_text(shadow_record),
            state=str(payload.get("state") or "-"),
            quality_score=self._safe_float(payload.get("response_quality_score")),
            schema_valid=bool(payload.get("schema_valid", False)),
            recovery_used=bool(payload.get("recovery_used", False)),
            guard_degraded=bool(payload.get("degraded", False)),
            cooldown_blocked=bool(payload.get("cooldown_blocked", False)),
            applied=False,
            submitted=0,
            metadata=self._metadata(),
        )

    def _scenario_text(self, shadow_record: dict[str, Any]) -> str:
        scenario = shadow_record.get("scenario")
        if isinstance(scenario, dict):
            return str(scenario.get("label_ko") or scenario.get("name") or "-")
        return str(scenario or "-")

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _metadata(self) -> dict:
        return {
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
            "source": "one_shot",
        }


def build_sample_observation_from_one_shot() -> AIObservationRecord:
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
            "confidence": 0.5,
            "scenario": {"label_ko": "sample observation", "name": "sample"},
        },
    }
    return AIObservationAdapter().from_one_shot_result(result)


__all__ = [
    "AIObservationAdapter",
    "build_sample_observation_from_one_shot",
]
