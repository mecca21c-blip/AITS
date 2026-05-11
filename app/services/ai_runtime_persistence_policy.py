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
        "gate_only": True,
    }


@dataclass
class AIRuntimePersistencePolicy:
    enabled: bool
    allowed_formats: list
    max_payload_bytes: int
    allow_relative_path: bool
    allow_absolute_path: bool
    allowed_base_dir: str
    require_redacted: bool
    require_safe_to_persist: bool
    metadata: dict = field(default_factory=_metadata)


class AIRuntimePersistencePolicyBuilder:
    """Builds persistence gate policies without enabling writes."""

    def build_default_policy(self) -> AIRuntimePersistencePolicy:
        return AIRuntimePersistencePolicy(
            enabled=False,
            allowed_formats=["json", "csv_preview", "text_preview"],
            max_payload_bytes=1_000_000,
            allow_relative_path=True,
            allow_absolute_path=False,
            allowed_base_dir="data/runtime_exports",
            require_redacted=True,
            require_safe_to_persist=True,
            metadata=_metadata(),
        )


def build_sample_persistence_policy() -> AIRuntimePersistencePolicy:
    return AIRuntimePersistencePolicyBuilder().build_default_policy()


__all__ = [
    "AIRuntimePersistencePolicy",
    "AIRuntimePersistencePolicyBuilder",
    "build_sample_persistence_policy",
]
