from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AIEngineDecision:
    action: str = "hold"
    confidence: float = 0.0
    risk: str = "medium"
    reason: str = ""
    engine: str = "local"
    raw: Dict[str, Any] = field(default_factory=dict)


class AIEngineProvider:
    name: str = "base"
    api_required: bool = False

    def is_ready(self) -> bool:
        return False

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="AIEngineProvider skeleton fallback",
            engine=self.name,
            raw={"mode": "skeleton", "context": dict(context or {})},
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "api_required": self.api_required,
            "ready": self.is_ready(),
        }


class LocalProvider(AIEngineProvider):
    name = "local"
    api_required = False

    def is_ready(self) -> bool:
        return True

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="LocalProvider skeleton ready",
            engine="local",
            raw={"mode": "skeleton"},
        )


class OpenAIProvider(AIEngineProvider):
    name = "openai"
    api_required = True

    def is_ready(self) -> bool:
        return False

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="OpenAIProvider skeleton only",
            engine="openai",
            raw={"mode": "skeleton"},
        )


class GeminiProvider(AIEngineProvider):
    name = "gemini"
    api_required = True

    def is_ready(self) -> bool:
        return False

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="GeminiProvider skeleton only",
            engine="gemini",
            raw={"mode": "skeleton"},
        )


def normalize_provider_name(provider_name: Any) -> str:
    provider_norm = str(provider_name or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    if provider_norm in ("local", "basic"):
        return "local"
    return "local"


def build_default_provider_registry() -> Dict[str, AIEngineProvider]:
    return {
        "local": LocalProvider(),
        "openai": OpenAIProvider(),
        "gemini": GeminiProvider(),
    }


def get_provider(
    registry: Optional[Dict[str, AIEngineProvider]], provider_name: Any
) -> AIEngineProvider:
    try:
        provider_key = normalize_provider_name(provider_name)
        providers = registry or {}
        provider = providers.get(provider_key) or providers.get("local")
        if provider is not None:
            return provider
    except Exception:
        pass
    return LocalProvider()
