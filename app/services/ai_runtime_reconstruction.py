from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata() -> dict:
    return {
        "replay_only": True,
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
    }


@dataclass
class AIRuntimeReconstructionState:
    provider: str
    session_state: str
    observation_state: str
    incident_count: int
    degraded: bool
    cooldown_blocked: bool
    last_quality_score: float
    last_event: str
    reconstructed_at: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeReconstructionEngine:
    """Reconstructs runtime state from replay frames only."""

    def reconstruct(self, frames: list) -> AIRuntimeReconstructionState:
        items = list(frames or [])
        provider = "unknown"
        session_state = "-"
        observation_state = "-"
        incident_count = 0
        degraded = False
        cooldown_blocked = False
        last_quality_score = 0.0
        last_event = "-"

        for frame in items:
            provider = str(self._get(frame, "provider", provider) or provider)
            frame_type = str(self._get(frame, "frame_type", "") or "")
            state = str(self._get(frame, "state", "") or "")
            last_event = frame_type or last_event
            metadata = self._get(frame, "metadata", {})
            if frame_type == "session":
                session_state = state or session_state
            elif frame_type == "observation":
                observation_state = state or observation_state
            elif frame_type == "quality":
                last_quality_score = self._safe_float(state)
                if isinstance(metadata, dict):
                    last_quality_score = self._safe_float(
                        metadata.get("quality_score", last_quality_score)
                    )
            elif frame_type == "incident":
                incident_count += 1
                if state in {"error", "critical"}:
                    degraded = True
                if isinstance(metadata, dict):
                    incident = metadata.get("incident")
                    if isinstance(incident, dict):
                        incident_type = str(incident.get("incident_type") or "")
                        if incident_type in {"cooldown_active", "runtime_blocked"}:
                            cooldown_blocked = True
                        if str(incident.get("severity") or "") in {"error", "critical"}:
                            degraded = True
            elif frame_type == "timeline_event" and state in {"warning", "error", "critical"}:
                degraded = True
            elif frame_type == "persistence_gate" and state not in {"allowed", "저장 가능"}:
                pass

        return AIRuntimeReconstructionState(
            provider=provider,
            session_state=session_state,
            observation_state=observation_state,
            incident_count=incident_count,
            degraded=bool(degraded),
            cooldown_blocked=bool(cooldown_blocked),
            last_quality_score=last_quality_score,
            last_event=last_event,
            reconstructed_at=_now(),
            metadata=_metadata(),
        )

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_reconstruction_state() -> AIRuntimeReconstructionState:
    from app.services.ai_runtime_replay_builder import build_sample_replay_frames

    return AIRuntimeReconstructionEngine().reconstruct(build_sample_replay_frames())


__all__ = [
    "AIRuntimeReconstructionEngine",
    "AIRuntimeReconstructionState",
    "build_sample_reconstruction_state",
]
