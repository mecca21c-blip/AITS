from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
class AIRuntimeSession:
    session_id: str
    provider: str
    model: str
    started_at: str
    last_seen_at: str
    status: str
    total_one_shots: int
    total_observations: int
    total_errors: int
    degraded: bool
    cooldown_blocked: bool
    metadata: dict = field(default_factory=_metadata)


def build_sample_runtime_session() -> AIRuntimeSession:
    timestamp = _now()
    return AIRuntimeSession(
        session_id="sample-runtime-session",
        provider="mock",
        model="mock",
        started_at=timestamp,
        last_seen_at=timestamp,
        status="active",
        total_one_shots=0,
        total_observations=0,
        total_errors=0,
        degraded=False,
        cooldown_blocked=False,
        metadata=_metadata(),
    )


__all__ = [
    "AIRuntimeSession",
    "build_sample_runtime_session",
]
