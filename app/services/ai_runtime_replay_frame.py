from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


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
class AIRuntimeReplayFrame:
    frame_id: str
    snapshot_id: str
    provider: str
    timestamp: str
    frame_type: str
    title: str
    state: str
    message: str
    metadata: dict = field(default_factory=_metadata)


def build_replay_frame(
    snapshot_id: str,
    provider: str,
    timestamp: str,
    frame_type: str,
    title: str,
    state: str,
    message: str,
    metadata: dict | None = None,
) -> AIRuntimeReplayFrame:
    safe_metadata = _metadata()
    if isinstance(metadata, dict):
        safe_metadata.update(metadata)
    return AIRuntimeReplayFrame(
        frame_id=f"frame-{uuid4().hex}",
        snapshot_id=str(snapshot_id or ""),
        provider=str(provider or "unknown"),
        timestamp=str(timestamp or _now()),
        frame_type=str(frame_type or "runtime"),
        title=str(title or frame_type or "Runtime frame"),
        state=str(state or "-"),
        message=str(message or ""),
        metadata=safe_metadata,
    )


def build_sample_replay_frame() -> AIRuntimeReplayFrame:
    return build_replay_frame(
        snapshot_id="sample-snapshot",
        provider="mock",
        timestamp=_now(),
        frame_type="session",
        title="Session",
        state="active",
        message="sample runtime session frame",
    )


__all__ = [
    "AIRuntimeReplayFrame",
    "build_replay_frame",
    "build_sample_replay_frame",
]
