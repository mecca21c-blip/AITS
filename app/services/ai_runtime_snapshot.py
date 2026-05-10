from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


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
        "export_ready": True,
    }


@dataclass
class AIRuntimeSnapshot:
    snapshot_id: str
    provider: str
    model: str
    symbol: str
    created_at: str
    session: dict
    observation: dict
    timeline: list
    incidents: list
    ui_bundle: dict
    health: dict
    safety: dict
    metadata: dict = field(default_factory=_metadata)


def build_sample_runtime_snapshot() -> AIRuntimeSnapshot:
    return AIRuntimeSnapshot(
        snapshot_id=f"snapshot-{uuid4().hex}",
        provider="mock",
        model="mock",
        symbol="KRW-BTC",
        created_at=_now(),
        session={"session_id": "sample-runtime-session", "status": "active"},
        observation={"health_label": "정상", "summary_line": "mock | 정상"},
        timeline=[],
        incidents=[],
        ui_bundle={"provider": "mock", "diagnosis": "정상"},
        health={"guard_ready": True, "quality_score": 0.8},
        safety={
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        },
        metadata=_metadata(),
    )


__all__ = [
    "AIRuntimeSnapshot",
    "build_sample_runtime_snapshot",
]
