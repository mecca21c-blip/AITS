from __future__ import annotations

from dataclasses import dataclass, field


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
class AIRuntimeCapabilityProfile:
    provider: str
    model: str
    supports_dry_run: bool
    supports_live_one_shot: bool
    supports_structured_json: bool
    supports_state_context: bool
    supports_observation: bool
    supports_replay: bool
    supports_snapshot_export: bool
    supports_local_runtime: bool
    supports_vision: bool
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeCapabilityRegistry:
    """Static provider/model capability registry for runtime compatibility checks."""

    def get_profile(self, provider: str, model: str = "-") -> AIRuntimeCapabilityProfile:
        normalized = str(provider or "unknown").strip().lower()
        if normalized == "gpt":
            normalized = "openai"
        elif normalized in {"basic", "local", "local_ai"}:
            normalized = "ollama"
        model_name = str(model or "-")
        if normalized == "openai":
            return AIRuntimeCapabilityProfile(
                provider=normalized,
                model=model_name,
                supports_dry_run=True,
                supports_live_one_shot=True,
                supports_structured_json=True,
                supports_state_context=True,
                supports_observation=True,
                supports_replay=True,
                supports_snapshot_export=True,
                supports_local_runtime=False,
                supports_vision=True,
                metadata=_metadata(),
            )
        if normalized == "gemini":
            return AIRuntimeCapabilityProfile(
                provider=normalized,
                model=model_name,
                supports_dry_run=True,
                supports_live_one_shot=True,
                supports_structured_json=True,
                supports_state_context=True,
                supports_observation=True,
                supports_replay=True,
                supports_snapshot_export=True,
                supports_local_runtime=False,
                supports_vision=True,
                metadata=_metadata(),
            )
        if normalized == "ollama":
            return AIRuntimeCapabilityProfile(
                provider=normalized,
                model=model_name,
                supports_dry_run=True,
                supports_live_one_shot=False,
                supports_structured_json=True,
                supports_state_context=True,
                supports_observation=True,
                supports_replay=True,
                supports_snapshot_export=True,
                supports_local_runtime=True,
                supports_vision=False,
                metadata=_metadata(),
            )
        return AIRuntimeCapabilityProfile(
            provider=normalized or "unknown",
            model=model_name,
            supports_dry_run=True,
            supports_live_one_shot=False,
            supports_structured_json=False,
            supports_state_context=False,
            supports_observation=False,
            supports_replay=False,
            supports_snapshot_export=False,
            supports_local_runtime=False,
            supports_vision=False,
            metadata=_metadata(),
        )


def build_sample_capability_profile() -> AIRuntimeCapabilityProfile:
    return AIRuntimeCapabilityRegistry().get_profile("mock", "mock")


__all__ = [
    "AIRuntimeCapabilityProfile",
    "AIRuntimeCapabilityRegistry",
    "build_sample_capability_profile",
]
