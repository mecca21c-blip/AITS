from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AIObservationRecord:
    provider: str
    model: str
    symbol: str
    timestamp: str
    suggestion: str
    next_action: str
    confidence: float
    scenario: str
    state: str
    quality_score: float
    schema_valid: bool
    recovery_used: bool
    guard_degraded: bool
    cooldown_blocked: bool
    applied: bool
    submitted: int
    metadata: dict = field(default_factory=dict)


def build_sample_observation_record() -> AIObservationRecord:
    return AIObservationRecord(
        provider="mock",
        model="mock",
        symbol="KRW-BTC",
        timestamp=datetime.now(timezone.utc).isoformat(),
        suggestion="confirm",
        next_action="watch",
        confidence=0.55,
        scenario="횡보 관찰형",
        state="watching",
        quality_score=0.82,
        schema_valid=True,
        recovery_used=False,
        guard_degraded=False,
        cooldown_blocked=False,
        applied=False,
        submitted=0,
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


__all__ = ["AIObservationRecord", "build_sample_observation_record"]
