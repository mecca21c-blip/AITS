from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class AIRuntimeBadgeBuilder:
    """Builds compact runtime status badges from a UI bundle."""

    def build_badges(self, bundle) -> list[str]:
        payload = self._to_dict(bundle)
        badges = list(payload.get("badges") or [])
        diagnosis = str(payload.get("diagnosis") or payload.get("health_label") or "")
        if diagnosis == "정상":
            badges.append("정상")
        elif diagnosis == "관찰 필요":
            badges.append("관찰 필요")
        elif diagnosis in ("불안정", "런타임 불안정"):
            badges.append("불안정")
        elif diagnosis == "차단 필요":
            badges.append("쿨다운")
        if bool(payload.get("cooldown_blocked", False)):
            badges.append("쿨다운")
        if bool(payload.get("confidence_drift", False)):
            badges.append("Drift")
        if bool(payload.get("scenario_drift", False)):
            badges.append("Scenario Drift")
        if bool(payload.get("anomaly_detected", False)):
            badges.append("Anomaly")
        badges.append("연구모드")
        return list(dict.fromkeys(badges))

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_runtime_badges() -> list[str]:
    from app.services.ai_runtime_ui_bundle import build_sample_runtime_ui_bundle

    return AIRuntimeBadgeBuilder().build_badges(build_sample_runtime_ui_bundle())


__all__ = [
    "AIRuntimeBadgeBuilder",
    "build_sample_runtime_badges",
]
