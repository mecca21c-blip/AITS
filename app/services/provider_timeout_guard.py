from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderTimeoutPolicy:
    provider: str
    connect_timeout_sec: int
    read_timeout_sec: int
    total_timeout_sec: int
    max_one_shot_sec: int
    enabled: bool
    reason: str
    metadata: dict = field(default_factory=dict)


class ProviderTimeoutGuard:
    """Defines timeout policies only; it does not sleep or call providers."""

    def get_policy(self, provider: str) -> ProviderTimeoutPolicy:
        name = self._normalize(provider)
        if name == "openai":
            return self._policy(name, 5, 15, 20, 20, True, "openai_one_shot_limit")
        if name == "gemini":
            return self._policy(name, 5, 15, 20, 20, True, "gemini_one_shot_limit")
        if name == "ollama":
            return self._policy(name, 5, 40, 45, 45, True, "ollama_local_runtime_limit")
        if name == "mock":
            return self._policy(name, 1, 2, 3, 3, True, "mock_dry_run_limit")
        return self._policy(name, 3, 7, 10, 10, True, "unknown_provider_limit")

    def _normalize(self, provider: str) -> str:
        name = str(provider or "").strip().lower()
        if name == "gpt":
            return "openai"
        if name in {"local", "local_ai"}:
            return "ollama"
        return name or "unknown"

    def _policy(
        self,
        provider: str,
        connect_timeout_sec: int,
        read_timeout_sec: int,
        total_timeout_sec: int,
        max_one_shot_sec: int,
        enabled: bool,
        reason: str,
    ) -> ProviderTimeoutPolicy:
        return ProviderTimeoutPolicy(
            provider=provider,
            connect_timeout_sec=connect_timeout_sec,
            read_timeout_sec=read_timeout_sec,
            total_timeout_sec=total_timeout_sec,
            max_one_shot_sec=max_one_shot_sec,
            enabled=bool(enabled),
            reason=reason,
            metadata=self._safety_metadata(),
        )

    def _safety_metadata(self) -> dict:
        return {
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
        }


def build_sample_timeout_policy() -> ProviderTimeoutPolicy:
    return ProviderTimeoutGuard().get_policy("mock")


__all__ = [
    "ProviderTimeoutPolicy",
    "ProviderTimeoutGuard",
    "build_sample_timeout_policy",
]
