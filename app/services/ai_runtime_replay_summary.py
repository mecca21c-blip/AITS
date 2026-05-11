from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
class AIRuntimeReplaySummary:
    total_frames: int
    incidents: int
    degraded: bool
    cooldown_blocked: bool
    final_state: str
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeReplaySummaryBuilder:
    """Builds compact replay/reconstruction summaries."""

    def build_summary(self, frames, reconstruction=None) -> AIRuntimeReplaySummary:
        frame_list = list(frames or [])
        incidents = sum(1 for frame in frame_list if self._get(frame, "frame_type", "") == "incident")
        degraded = bool(self._get(reconstruction, "degraded", False))
        cooldown = bool(self._get(reconstruction, "cooldown_blocked", False))
        final_state = str(
            self._get(reconstruction, "last_event", "")
            or (self._get(frame_list[-1], "frame_type", "-") if frame_list else "-")
        )
        summary_line = (
            f"frames={len(frame_list)} | incidents={incidents} | "
            f"degraded={degraded} | cooldown={cooldown} | final={final_state}"
        )
        return AIRuntimeReplaySummary(
            total_frames=len(frame_list),
            incidents=incidents,
            degraded=degraded,
            cooldown_blocked=cooldown,
            final_state=final_state,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_replay_summary() -> AIRuntimeReplaySummary:
    from app.services.ai_runtime_reconstruction import AIRuntimeReconstructionEngine
    from app.services.ai_runtime_replay_builder import build_sample_replay_frames

    frames = build_sample_replay_frames()
    reconstruction = AIRuntimeReconstructionEngine().reconstruct(frames)
    return AIRuntimeReplaySummaryBuilder().build_summary(frames, reconstruction)


__all__ = [
    "AIRuntimeReplaySummary",
    "AIRuntimeReplaySummaryBuilder",
    "build_sample_replay_summary",
]
