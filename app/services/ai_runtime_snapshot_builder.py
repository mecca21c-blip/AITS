from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.services.ai_runtime_snapshot import AIRuntimeSnapshot
from app.services.ai_runtime_snapshot_sanitizer import AIRuntimeSnapshotSanitizer


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


class AIRuntimeSnapshotBuilder:
    """Builds sanitized export-ready runtime snapshots from one-shot output."""

    def __init__(self) -> None:
        self._sanitizer = AIRuntimeSnapshotSanitizer()

    def build_snapshot(
        self,
        one_shot_result: dict,
        symbol: str = "KRW-BTC",
    ) -> AIRuntimeSnapshot:
        result = dict(one_shot_result or {})
        shadow = result.get("shadow_record") if isinstance(result.get("shadow_record"), dict) else {}
        snapshot = AIRuntimeSnapshot(
            snapshot_id=f"snapshot-{uuid4().hex}",
            provider=str(result.get("provider") or "unknown"),
            model=str(result.get("model") or "-"),
            symbol=str(shadow.get("symbol") or shadow.get("market") or symbol or "KRW-BTC"),
            created_at=_now(),
            session=self._session(result),
            observation=self._observation(result),
            timeline=self._timeline(result),
            incidents=self._incidents(result),
            ui_bundle=self._ui_bundle(result),
            health=self._health(result),
            safety=self._safety(result),
            metadata=_metadata(),
        )
        clean = self._sanitizer.sanitize(snapshot)
        return AIRuntimeSnapshot(**clean)

    def _session(self, result: dict) -> dict:
        return {
            "session_id": result.get("session_id", ""),
            "session_status": result.get("session_status", ""),
            "session_diagnosis": result.get("session_diagnosis", ""),
            "session_report": result.get("session_report", {}),
            "runtime_memory_summary": result.get("runtime_memory_summary", {}),
        }

    def _observation(self, result: dict) -> dict:
        return {
            "observation_ready": bool(result.get("observation_ready", False)),
            "observation_health_label": result.get("observation_health_label", ""),
            "observation_summary_line": result.get("observation_summary_line", ""),
            "observation_report": result.get("observation_report", {}),
            "observation_formatted": result.get("observation_formatted", {}),
        }

    def _timeline(self, result: dict) -> list:
        timeline = result.get("runtime_timeline")
        if isinstance(timeline, list):
            return timeline
        feed = result.get("runtime_event_feed")
        return feed if isinstance(feed, list) else []

    def _incidents(self, result: dict) -> list:
        incidents = result.get("runtime_incidents")
        if isinstance(incidents, list):
            return incidents
        feed = result.get("runtime_alert_feed")
        return feed if isinstance(feed, list) else []

    def _ui_bundle(self, result: dict) -> dict:
        return {
            "runtime_ui_bundle": result.get("runtime_ui_bundle", {}),
            "runtime_ui_formatted": result.get("runtime_ui_formatted", {}),
            "runtime_dashboard_summary": result.get("runtime_dashboard_summary", {}),
            "runtime_badges": result.get("runtime_badges", []),
            "runtime_status_colors": result.get("runtime_status_colors", {}),
        }

    def _health(self, result: dict) -> dict:
        return {
            "runtime_ready": bool(result.get("runtime_ready", False)),
            "guard_ready": bool(result.get("guard_ready", False)),
            "guard_report": result.get("guard_report", {}),
            "response_quality_ready": bool(result.get("response_quality_ready", False)),
            "response_quality_score": float(result.get("response_quality_score") or 0.0),
            "session_ready": bool(result.get("session_ready", False)),
            "runtime_events_ready": bool(result.get("runtime_events_ready", False)),
            "runtime_incidents_ready": bool(result.get("runtime_incidents_ready", False)),
        }

    def _safety(self, result: dict) -> dict:
        return {
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
            "safety_blocked": bool(result.get("safety_blocked", False)),
            "live_allowed": bool(result.get("live_allowed", False)),
        }


def build_sample_runtime_snapshot_from_one_shot() -> AIRuntimeSnapshot:
    result = {
        "provider": "mock",
        "model": "mock",
        "session_id": "sample-runtime-session",
        "session_status": "active",
        "session_diagnosis": "정상",
        "session_report": {"provider": "mock", "diagnosis": "정상"},
        "observation_ready": True,
        "observation_report": {"health_label": "정상"},
        "runtime_ui_bundle": {"provider": "mock"},
        "guard_ready": True,
        "response_quality_score": 0.8,
        "submitted": 0,
        "real_order": False,
        "shadow_record": {"symbol": "KRW-BTC"},
    }
    return AIRuntimeSnapshotBuilder().build_snapshot(result)


__all__ = [
    "AIRuntimeSnapshotBuilder",
    "build_sample_runtime_snapshot_from_one_shot",
]
