from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ProviderCooldownState:
    provider: str
    active: bool
    until_ts: float
    reason: str
    failure_count: int
    metadata: dict = field(default_factory=dict)


class ProviderCooldownManager:
    """Memory-only provider cooldown state."""

    def __init__(self) -> None:
        self._cooldowns: dict[str, ProviderCooldownState] = {}

    def mark_failure(
        self,
        provider: str,
        reason: str,
        cooldown_sec: int = 60,
    ) -> ProviderCooldownState:
        name = self._normalize(provider)
        previous = self._cooldowns.get(name)
        failure_count = int(getattr(previous, "failure_count", 0) or 0) + 1
        state = ProviderCooldownState(
            provider=name,
            active=True,
            until_ts=time.time() + max(0, int(cooldown_sec or 0)),
            reason=str(reason or "failure"),
            failure_count=failure_count,
            metadata=self._metadata(),
        )
        self._cooldowns[name] = state
        return state

    def clear(self, provider: str) -> None:
        self._cooldowns.pop(self._normalize(provider), None)

    def is_blocked(self, provider: str) -> bool:
        state = self.get_state(provider)
        return bool(state and state.active)

    def get_state(self, provider: str) -> ProviderCooldownState | None:
        name = self._normalize(provider)
        state = self._cooldowns.get(name)
        if state and state.active and state.until_ts <= time.time():
            self._cooldowns[name] = ProviderCooldownState(
                provider=name,
                active=False,
                until_ts=state.until_ts,
                reason=state.reason,
                failure_count=state.failure_count,
                metadata=self._metadata(),
            )
            return self._cooldowns[name]
        return state

    def build_summary(self) -> dict:
        active = 0
        total = 0
        providers: dict[str, dict] = {}
        for provider, state in list(self._cooldowns.items()):
            current = self.get_state(provider)
            if current is None:
                continue
            total += 1
            if current.active:
                active += 1
            providers[provider] = {
                "active": current.active,
                "failure_count": current.failure_count,
                "reason": current.reason,
            }
        return {
            "total": total,
            "active": active,
            "providers": providers,
            "submitted": 0,
            "real_order": False,
        }

    def _normalize(self, provider: str) -> str:
        name = str(provider or "").strip().lower()
        if name == "gpt":
            return "openai"
        if name in {"local", "local_ai"}:
            return "ollama"
        return name or "unknown"

    def _metadata(self) -> dict:
        return {
            "memory_only": True,
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
        }


def build_sample_cooldown_state() -> ProviderCooldownState:
    return ProviderCooldownManager().mark_failure("mock", "sample_failure", 60)


__all__ = [
    "ProviderCooldownState",
    "ProviderCooldownManager",
    "build_sample_cooldown_state",
]
