from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.ai_runtime_replay_frame import AIRuntimeReplayFrame, build_replay_frame


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AIRuntimeReplayBuilder:
    """Builds replay-only frames from runtime snapshots."""

    def build_frames(self, snapshot) -> list[AIRuntimeReplayFrame]:
        payload = self._to_dict(snapshot)
        snapshot_id = str(payload.get("snapshot_id") or "")
        provider = str(payload.get("provider") or "unknown")
        created_at = str(payload.get("created_at") or _now())
        frames: list[AIRuntimeReplayFrame] = []

        session = self._dict(payload.get("session"))
        if session:
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "session",
                    "Session",
                    str(session.get("session_status") or session.get("status") or "-"),
                    str(session.get("session_diagnosis") or "session reconstructed"),
                    {"session": session},
                )
            )

        observation = self._dict(payload.get("observation"))
        if observation:
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "observation",
                    "Observation",
                    str(observation.get("observation_health_label") or observation.get("health_label") or "-"),
                    str(observation.get("observation_summary_line") or "observation reconstructed"),
                    {"observation": observation},
                )
            )

        health = self._dict(payload.get("health"))
        if health:
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "quality",
                    "Quality",
                    f"{self._safe_float(health.get('response_quality_score')):.2f}",
                    "quality score reconstructed",
                    {"quality_score": self._safe_float(health.get("response_quality_score"))},
                )
            )
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "guard",
                    "Guard",
                    "ready" if health.get("guard_ready") else "unknown",
                    "guard state reconstructed",
                    {"health": health},
                )
            )

        for incident in self._list(payload.get("incidents")):
            incident_data = self._dict(incident)
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    str(incident_data.get("detected_at") or created_at),
                    "incident",
                    str(incident_data.get("title") or incident_data.get("incident_type") or "Incident"),
                    str(incident_data.get("severity") or "-"),
                    str(incident_data.get("description") or ""),
                    {"incident": incident_data},
                )
            )

        for item in self._list(payload.get("timeline")):
            item_data = self._dict(item)
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    str(item_data.get("time") or item_data.get("timestamp") or created_at),
                    "timeline_event",
                    str(item_data.get("title") or item_data.get("label") or item_data.get("event_type") or "Event"),
                    str(item_data.get("severity") or item_data.get("state") or "-"),
                    str(item_data.get("message") or ""),
                    {"timeline_item": item_data},
                )
            )

        ui_bundle = self._dict(payload.get("ui_bundle"))
        if ui_bundle:
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "ui_bundle",
                    "UI Bundle",
                    "ready",
                    "ui-ready bundle reconstructed",
                    {"ui_bundle": ui_bundle},
                )
            )

        persistence = self._dict(payload.get("persistence"))
        if persistence:
            frames.append(
                build_replay_frame(
                    snapshot_id,
                    provider,
                    created_at,
                    "persistence_gate",
                    "Persistence Gate",
                    str(persistence.get("reason") or persistence.get("status") or "-"),
                    "persistence gate reconstructed",
                    {"persistence": persistence},
                )
            )
        return frames

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}

    def _dict(self, value: Any) -> dict:
        return self._to_dict(value)

    def _list(self, value: Any) -> list:
        return value if isinstance(value, list) else []

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_replay_frames() -> list[AIRuntimeReplayFrame]:
    from app.services.ai_runtime_snapshot import build_sample_runtime_snapshot

    return AIRuntimeReplayBuilder().build_frames(build_sample_runtime_snapshot())


__all__ = [
    "AIRuntimeReplayBuilder",
    "build_sample_replay_frames",
]
