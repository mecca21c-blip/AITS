from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ai_runtime_capability_registry import AIRuntimeCapabilityRegistry


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
class AIRuntimeCompatibilityResult:
    provider: str
    model: str
    feature: str
    compatible: bool
    reason: str
    required_capabilities: list
    missing_capabilities: list
    metadata: dict = field(default_factory=_metadata)


FEATURE_REQUIREMENTS = {
    "one_shot_dry_run": ["supports_dry_run"],
    "one_shot_live": ["supports_live_one_shot", "supports_structured_json"],
    "state_aware_prompt": ["supports_state_context"],
    "observation_report": ["supports_observation"],
    "runtime_replay": ["supports_replay"],
    "snapshot_export": ["supports_snapshot_export"],
    "local_runtime": ["supports_local_runtime"],
}


class AIRuntimeCompatibilityChecker:
    """Checks feature compatibility from capability profiles only."""

    def __init__(self) -> None:
        self._registry = AIRuntimeCapabilityRegistry()

    def check(self, provider: str, model: str, feature: str) -> AIRuntimeCompatibilityResult:
        feature_name = str(feature or "").strip()
        required = FEATURE_REQUIREMENTS.get(feature_name)
        if required is None:
            return AIRuntimeCompatibilityResult(
                provider=str(provider or "unknown"),
                model=str(model or "-"),
                feature=feature_name,
                compatible=False,
                reason="unknown_feature",
                required_capabilities=[],
                missing_capabilities=[],
                metadata=_metadata(),
            )
        profile = self._registry.get_profile(provider, model)
        missing = [cap for cap in required if not bool(getattr(profile, cap, False))]
        compatible = len(missing) == 0
        return AIRuntimeCompatibilityResult(
            provider=profile.provider,
            model=profile.model,
            feature=feature_name,
            compatible=compatible,
            reason="compatible" if compatible else "missing_capabilities",
            required_capabilities=list(required),
            missing_capabilities=missing,
            metadata=_metadata(),
        )


def build_sample_compatibility_result() -> AIRuntimeCompatibilityResult:
    return AIRuntimeCompatibilityChecker().check("mock", "mock", "one_shot_dry_run")


__all__ = [
    "AIRuntimeCompatibilityResult",
    "AIRuntimeCompatibilityChecker",
    "build_sample_compatibility_result",
]
