from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from app.services.ai_runtime_capability_registry import (
    AIRuntimeCapabilityRegistry,
    AIRuntimeCapabilityProfile,
)


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "capability_only": True,
    }


@dataclass
class AIRuntimeFeatureMatrix:
    provider: str
    model: str
    features: dict
    enabled_count: int
    disabled_count: int
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeFeatureMatrixBuilder:
    """Converts capability profiles into normalized feature matrices."""

    def build_matrix(self, profile) -> AIRuntimeFeatureMatrix:
        p = self._to_dict(profile)
        features = {
            "dry_run": bool(p.get("supports_dry_run", False)),
            "live_one_shot": bool(p.get("supports_live_one_shot", False)),
            "structured_json": bool(p.get("supports_structured_json", False)),
            "state_context": bool(p.get("supports_state_context", False)),
            "observation": bool(p.get("supports_observation", False)),
            "replay": bool(p.get("supports_replay", False)),
            "snapshot_export": bool(p.get("supports_snapshot_export", False)),
            "local_runtime": bool(p.get("supports_local_runtime", False)),
            "vision": bool(p.get("supports_vision", False)),
        }
        enabled = sum(1 for value in features.values() if bool(value))
        disabled = len(features) - enabled
        return AIRuntimeFeatureMatrix(
            provider=str(p.get("provider") or "unknown"),
            model=str(p.get("model") or "-"),
            features=features,
            enabled_count=enabled,
            disabled_count=disabled,
            metadata=_metadata(),
        )

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_feature_matrix() -> AIRuntimeFeatureMatrix:
    profile: AIRuntimeCapabilityProfile = AIRuntimeCapabilityRegistry().get_profile("mock", "mock")
    return AIRuntimeFeatureMatrixBuilder().build_matrix(profile)


__all__ = [
    "AIRuntimeFeatureMatrix",
    "AIRuntimeFeatureMatrixBuilder",
    "build_sample_feature_matrix",
]
