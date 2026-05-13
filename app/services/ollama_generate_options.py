from __future__ import annotations

from dataclasses import dataclass, field


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "shadow_only": True,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaGenerateOptions:
    profile: str
    num_predict: int
    temperature: float
    top_p: float
    repeat_penalty: float
    stop: list
    metadata: dict = field(default_factory=_metadata)


class OllamaGenerateOptionsBuilder:
    """Builds small Ollama /api/generate option profiles."""

    def build(self, profile: str = "speed") -> OllamaGenerateOptions:
        name = str(profile or "speed").lower()
        profiles = {
            "speed": {
                "num_predict": 64,
                "temperature": 0.0,
                "top_p": 0.8,
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "```"],
            },
            "json_short": {
                "num_predict": 128,
                "temperature": 0.0,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "stop": ["```"],
            },
            "json_safe": {
                "num_predict": 256,
                "temperature": 0.0,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "stop": [],
            },
            "debug_long": {
                "num_predict": 512,
                "temperature": 0.0,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "stop": [],
            },
        }
        selected = profiles.get(name, profiles["speed"])
        metadata = _metadata()
        metadata["profile"] = name if name in profiles else "speed"
        return OllamaGenerateOptions(
            profile=str(metadata["profile"]),
            num_predict=int(selected["num_predict"]),
            temperature=float(selected["temperature"]),
            top_p=float(selected["top_p"]),
            repeat_penalty=float(selected["repeat_penalty"]),
            stop=list(selected["stop"]),
            metadata=metadata,
        )


def build_sample_ollama_generate_options() -> OllamaGenerateOptions:
    return OllamaGenerateOptionsBuilder().build("speed")


__all__ = [
    "OllamaGenerateOptions",
    "OllamaGenerateOptionsBuilder",
    "build_sample_ollama_generate_options",
]
