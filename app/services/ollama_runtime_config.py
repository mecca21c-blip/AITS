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
        "local_runtime": True,
    }


@dataclass
class OllamaRuntimeConfig:
    provider: str
    engine: str
    model: str
    base_url: str
    timeout_sec: float
    allow_live_one_shot: bool
    dry_run_only: bool
    metadata: dict = field(default_factory=_metadata)


class OllamaRuntimeConfigBuilder:
    """Builds local BASIC/Ollama runtime config without touching the service."""

    def build_default_config(
        self,
        model: str = "qwen2.5:7b-instruct-q4",
        base_url: str = "http://127.0.0.1:11434",
        timeout_sec: float = 30.0,
    ) -> OllamaRuntimeConfig:
        return OllamaRuntimeConfig(
            provider="ollama",
            engine="basic",
            model=str(model or "qwen2.5:7b-instruct-q4"),
            base_url=str(base_url or "http://127.0.0.1:11434"),
            timeout_sec=float(timeout_sec or 30.0),
            allow_live_one_shot=False,
            dry_run_only=True,
            metadata=_metadata(),
        )


def build_sample_ollama_runtime_config() -> OllamaRuntimeConfig:
    return OllamaRuntimeConfigBuilder().build_default_config(model="mock")


__all__ = [
    "OllamaRuntimeConfig",
    "OllamaRuntimeConfigBuilder",
    "build_sample_ollama_runtime_config",
]
