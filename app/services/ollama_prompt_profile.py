from __future__ import annotations

from dataclasses import dataclass, field


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "inference_called": False,
        "real_order": False,
        "submitted": 0,
        "profile_only": True,
    }


@dataclass
class OllamaPromptProfile:
    name: str
    max_fields: int
    max_chars: int
    description: str
    metadata: dict = field(default_factory=_metadata)


class OllamaPromptProfileBuilder:
    """Defines prompt size profiles for local Ollama inference."""

    _PROFILES = {
        "full": OllamaPromptProfile("full", 20, 2400, "Full AITS JSON schema prompt.", _metadata()),
        "compact": OllamaPromptProfile("compact", 12, 1400, "Core decision and safety fields.", _metadata()),
        "ultra_compact": OllamaPromptProfile("ultra_compact", 9, 900, "Small schema for slower local models.", _metadata()),
        "speed_test": OllamaPromptProfile("speed_test", 7, 520, "Minimal JSON schema for timing tests.", _metadata()),
    }

    def get_profile(self, name: str = "compact") -> OllamaPromptProfile:
        key = str(name or "compact").strip().lower()
        return self._PROFILES.get(key, self._PROFILES["compact"])


def build_sample_ollama_prompt_profile() -> OllamaPromptProfile:
    return OllamaPromptProfileBuilder().get_profile("compact")


__all__ = [
    "OllamaPromptProfile",
    "OllamaPromptProfileBuilder",
    "build_sample_ollama_prompt_profile",
]
