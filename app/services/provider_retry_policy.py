from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderRetryDecision:
    provider: str
    should_retry: bool
    max_retries: int
    retry_delay_sec: int
    reason: str
    metadata: dict = field(default_factory=dict)


class ProviderRetryPolicy:
    """Decides whether retry would be allowed; it never performs retry."""

    AUTH_ERRORS = ("auth", "permission", "invalidkey", "invalid_key", "unauthorized")
    TEMP_ERRORS = ("timeout", "ratelimit", "rate_limit", "temporary", "temporarily", "connection")
    RECOVERY_FIRST_ERRORS = ("json", "parse", "schema", "validation")

    def decide(
        self,
        provider: str,
        error_type: str | None,
        attempt: int = 0,
    ) -> ProviderRetryDecision:
        name = self._normalize(provider)
        error = str(error_type or "").strip().lower()
        max_retries = 1

        if not error:
            return self._decision(name, False, max_retries, 0, "no_error")
        if any(token in error for token in self.AUTH_ERRORS):
            return self._decision(name, False, max_retries, 0, "auth_error_no_retry")
        if any(token in error for token in self.RECOVERY_FIRST_ERRORS):
            return self._decision(name, False, max_retries, 0, "recovery_first_no_provider_retry")
        if int(attempt or 0) >= max_retries:
            return self._decision(name, False, max_retries, 0, "max_retries_reached")
        if any(token in error for token in self.TEMP_ERRORS):
            return self._decision(name, True, max_retries, 2, "temporary_error_retry_allowed")
        return self._decision(name, False, max_retries, 0, "non_retryable_error")

    def _normalize(self, provider: str) -> str:
        name = str(provider or "").strip().lower()
        if name == "gpt":
            return "openai"
        if name in {"local", "local_ai"}:
            return "ollama"
        return name or "unknown"

    def _decision(
        self,
        provider: str,
        should_retry: bool,
        max_retries: int,
        retry_delay_sec: int,
        reason: str,
    ) -> ProviderRetryDecision:
        return ProviderRetryDecision(
            provider=provider,
            should_retry=bool(should_retry),
            max_retries=int(max_retries),
            retry_delay_sec=int(retry_delay_sec),
            reason=reason,
            metadata={
                "retry_executed": False,
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
            },
        )


def build_sample_retry_decision() -> ProviderRetryDecision:
    return ProviderRetryPolicy().decide("mock", "TimeoutError", 0)


__all__ = [
    "ProviderRetryDecision",
    "ProviderRetryPolicy",
    "build_sample_retry_decision",
]
