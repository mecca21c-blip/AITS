from __future__ import annotations

from dataclasses import dataclass, field


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "benchmark_only": True,
        "shadow_only": True,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaModelRuntimeProfile:
    model: str
    completed: bool
    timed_out: bool
    elapsed_sec: float
    response_chars: int
    first_response_available: bool
    usable_for_basic: bool
    error_type: str
    metadata: dict = field(default_factory=_metadata)


def build_sample_ollama_model_runtime_profile() -> OllamaModelRuntimeProfile:
    return OllamaModelRuntimeProfile(
        model="mock",
        completed=True,
        timed_out=False,
        elapsed_sec=0.1,
        response_chars=12,
        first_response_available=True,
        usable_for_basic=True,
        error_type="",
    )


__all__ = [
    "OllamaModelRuntimeProfile",
    "build_sample_ollama_model_runtime_profile",
]
