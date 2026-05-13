from __future__ import annotations

from dataclasses import dataclass, field


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "real_order": False,
        "submitted": 0,
        "timing_only": True,
    }


@dataclass
class OllamaInferenceTimingResult:
    model: str
    prompt_profile: str
    timeout_sec: int
    elapsed_sec: float
    timed_out: bool
    completed: bool
    parsed_valid: bool
    metadata: dict = field(default_factory=_metadata)


def build_sample_ollama_inference_timing() -> OllamaInferenceTimingResult:
    return OllamaInferenceTimingResult(
        model="mock",
        prompt_profile="speed_test",
        timeout_sec=30,
        elapsed_sec=0.0,
        timed_out=False,
        completed=True,
        parsed_valid=True,
        metadata=_metadata(),
    )


__all__ = [
    "OllamaInferenceTimingResult",
    "build_sample_ollama_inference_timing",
]
