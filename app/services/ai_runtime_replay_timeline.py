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
        "order": "oldest_first",
    }


@dataclass
class AIRuntimeReplayTimelineItem:
    time: str
    provider: str
    frame_type: str
    label: str
    state: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeReplayTimelineBuilder:
    """Formats replay frames into an oldest-first replay timeline."""

    def build_timeline(self, frames: list) -> list[AIRuntimeReplayTimelineItem]:
        sorted_frames = sorted(
            list(frames or []),
            key=lambda frame: str(self._get(frame, "timestamp", "")),
        )
        timeline: list[AIRuntimeReplayTimelineItem] = []
        for frame in sorted_frames:
            metadata = _metadata()
            frame_metadata = self._get(frame, "metadata", {})
            if isinstance(frame_metadata, dict):
                metadata.update(frame_metadata)
            timeline.append(
                AIRuntimeReplayTimelineItem(
                    time=str(self._get(frame, "timestamp", "") or ""),
                    provider=str(self._get(frame, "provider", "unknown") or "unknown"),
                    frame_type=str(self._get(frame, "frame_type", "runtime") or "runtime"),
                    label=str(self._get(frame, "title", "") or self._get(frame, "frame_type", "runtime")),
                    state=str(self._get(frame, "state", "-") or "-"),
                    metadata=metadata,
                )
            )
        return timeline

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_replay_timeline() -> list[AIRuntimeReplayTimelineItem]:
    from app.services.ai_runtime_replay_builder import build_sample_replay_frames

    return AIRuntimeReplayTimelineBuilder().build_timeline(build_sample_replay_frames())


__all__ = [
    "AIRuntimeReplayTimelineBuilder",
    "AIRuntimeReplayTimelineItem",
    "build_sample_replay_timeline",
]
