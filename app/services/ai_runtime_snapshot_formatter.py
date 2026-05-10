from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class AIRuntimeSnapshotFormatter:
    """Formats runtime snapshots into compact UI/log-ready summaries."""

    def format_snapshot(self, snapshot) -> dict:
        payload = self._to_dict(snapshot)
        provider = str(payload.get("provider") or "unknown")
        session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else {}
        safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
        incidents = payload.get("incidents") if isinstance(payload.get("incidents"), list) else []
        timeline = payload.get("timeline") if isinstance(payload.get("timeline"), list) else []
        summary = (
            f"{provider} | session={session.get('session_id', '-')} | "
            f"observation={bool(observation.get('observation_ready', False))} | "
            f"events={len(timeline)} | incidents={len(incidents)}"
        )
        badges = ["연구모드", "Export Ready"]
        if bool(safety.get("safety_blocked", False)):
            badges.append("Safety Blocked")
        if incidents:
            badges.append("Incident")
        return {
            "title": "AI Runtime Snapshot",
            "summary": summary,
            "sections": [
                {"name": "session", "data": session},
                {"name": "observation", "data": observation},
                {"name": "health", "data": payload.get("health", {})},
                {"name": "safety", "data": safety},
            ],
            "badges": badges,
            "metadata": dict(payload.get("metadata") or {}),
        }

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_snapshot_format() -> dict:
    from app.services.ai_runtime_snapshot import build_sample_runtime_snapshot

    return AIRuntimeSnapshotFormatter().format_snapshot(build_sample_runtime_snapshot())


__all__ = [
    "AIRuntimeSnapshotFormatter",
    "build_sample_snapshot_format",
]
