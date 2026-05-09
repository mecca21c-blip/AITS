from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderCapability:
    provider: str
    dry_run: bool
    live_one_shot: bool
    local_runtime: bool
    structured_json: bool
    long_context: bool
    vision: bool
    research_mode: bool
    metadata: dict = field(default_factory=dict)


class ProviderCapabilityMatrix:
    """Static provider capability matrix for attach-only diagnostics."""

    def __init__(self) -> None:
        self._capabilities = {
            "openai": ProviderCapability(
                provider="openai",
                dry_run=True,
                live_one_shot=True,
                local_runtime=False,
                structured_json=True,
                long_context=True,
                vision=True,
                research_mode=True,
                metadata={"real_order": False, "submitted": 0},
            ),
            "gemini": ProviderCapability(
                provider="gemini",
                dry_run=True,
                live_one_shot=True,
                local_runtime=False,
                structured_json=True,
                long_context=True,
                vision=True,
                research_mode=True,
                metadata={"real_order": False, "submitted": 0},
            ),
            "ollama": ProviderCapability(
                provider="ollama",
                dry_run=True,
                live_one_shot=True,
                local_runtime=True,
                structured_json=True,
                long_context=False,
                vision=False,
                research_mode=True,
                metadata={"real_order": False, "submitted": 0},
            ),
            "mock": ProviderCapability(
                provider="mock",
                dry_run=True,
                live_one_shot=False,
                local_runtime=False,
                structured_json=True,
                long_context=False,
                vision=False,
                research_mode=True,
                metadata={"real_order": False, "submitted": 0},
            ),
        }

    def get_capability(self, provider: str) -> ProviderCapability | None:
        normalized = str(provider or "").strip().lower()
        if normalized == "gpt":
            normalized = "openai"
        elif normalized in {"local", "local_ai"}:
            normalized = "ollama"
        return self._capabilities.get(normalized)

    def build_matrix(self) -> dict[str, ProviderCapability]:
        return dict(self._capabilities)


def build_sample_provider_capabilities() -> dict[str, ProviderCapability]:
    return ProviderCapabilityMatrix().build_matrix()


__all__ = [
    "ProviderCapability",
    "ProviderCapabilityMatrix",
    "build_sample_provider_capabilities",
]
