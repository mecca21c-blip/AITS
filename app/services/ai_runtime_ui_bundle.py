from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, asdict
from typing import Any


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
class AIRuntimeUIBundle:
    provider: str
    session_id: str
    status: str
    diagnosis: str
    summary_line: str
    badges: list
    health_label: str
    observation_summary: str
    quality_score: float
    confidence_drift: bool
    scenario_drift: bool
    anomaly_detected: bool
    degraded: bool
    cooldown_blocked: bool
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeUIBundleBuilder:
    """Builds a UI-ready runtime bundle without creating UI widgets."""

    def build_bundle(
        self,
        one_shot_result: dict,
        session_report=None,
        observation_report=None,
        guard_report=None,
        quality_score=None,
    ) -> AIRuntimeUIBundle:
        result = dict(one_shot_result or {})
        session = self._to_dict(session_report)
        observation = self._to_dict(observation_report)
        guard = self._to_dict(guard_report)
        quality = self._to_dict(quality_score)
        provider = str(
            result.get("provider") or session.get("provider") or observation.get("provider") or "unknown"
        )
        diagnosis = str(session.get("diagnosis") or result.get("session_diagnosis") or "관찰 필요")
        health_label = str(observation.get("health_label") or diagnosis or "관찰 필요")
        metadata = _metadata()
        metadata.update(
            {
                "confidence": self._extract_confidence(result),
                "source": "runtime_ui_bundle",
            }
        )
        return AIRuntimeUIBundle(
            provider=provider,
            session_id=str(result.get("session_id") or session.get("session_id") or ""),
            status=str(session.get("status") or result.get("session_status") or result.get("state") or "-"),
            diagnosis=diagnosis,
            summary_line=str(
                session.get("summary_line")
                or result.get("observation_summary_line")
                or result.get("status_line")
                or ""
            ),
            badges=list(session.get("badges") or []),
            health_label=health_label,
            observation_summary=str(
                observation.get("summary_line") or result.get("observation_summary_line") or ""
            ),
            quality_score=self._quality_value(quality, result),
            confidence_drift=bool(observation.get("confidence_drift", False)),
            scenario_drift=bool(observation.get("scenario_drift", False)),
            anomaly_detected=bool(observation.get("anomaly_detected", False)),
            degraded=bool(result.get("degraded", False) or guard.get("degraded", False)),
            cooldown_blocked=bool(
                result.get("cooldown_blocked", False) or guard.get("cooldown_blocked", False)
            ),
            metadata=metadata,
        )

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        if value is None:
            return {}
        return {
            name: getattr(value, name)
            for name in dir(value)
            if not name.startswith("_") and not callable(getattr(value, name))
        }

    def _quality_value(self, quality: dict, result: dict) -> float:
        return self._safe_float(
            quality.get("quality_score", result.get("response_quality_score", 0.0))
        )

    def _extract_confidence(self, result: dict) -> float:
        shadow = result.get("shadow_record") if isinstance(result.get("shadow_record"), dict) else {}
        return self._safe_float(shadow.get("confidence", 0.0))

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_runtime_ui_bundle() -> AIRuntimeUIBundle:
    one_shot = {
        "provider": "mock",
        "session_id": "sample-runtime-session",
        "session_status": "active",
        "session_diagnosis": "정상",
        "response_quality_score": 0.85,
        "degraded": False,
        "cooldown_blocked": False,
        "shadow_record": {"confidence": 0.6},
    }
    session_report = {
        "session_id": "sample-runtime-session",
        "provider": "mock",
        "status": "active",
        "diagnosis": "정상",
        "summary_line": "mock | 정상",
        "badges": ["정상", "연구모드"],
    }
    observation_report = {
        "provider": "mock",
        "health_label": "정상",
        "summary_line": "mock | records=1 | 정상",
    }
    return AIRuntimeUIBundleBuilder().build_bundle(
        one_shot,
        session_report=session_report,
        observation_report=observation_report,
    )


__all__ = [
    "AIRuntimeUIBundle",
    "AIRuntimeUIBundleBuilder",
    "build_sample_runtime_ui_bundle",
]
