from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderHealthStatus:
    provider: str
    healthy: bool
    success_count: int
    failure_count: int
    last_error_type: str | None
    degraded: bool
    cooldown_active: bool
    metadata: dict = field(default_factory=dict)


class ProviderHealthMonitor:
    """Memory-only provider health tracker. It never calls providers."""

    def __init__(self) -> None:
        self._status: dict[str, ProviderHealthStatus] = {}

    def record_success(self, provider: str) -> ProviderHealthStatus:
        name = self._normalize(provider)
        current = self.get_status(name)
        status = ProviderHealthStatus(
            provider=name,
            healthy=True,
            success_count=current.success_count + 1,
            failure_count=0,
            last_error_type=None,
            degraded=False,
            cooldown_active=False,
            metadata=self._metadata(),
        )
        self._status[name] = status
        return status

    def record_failure(
        self,
        provider: str,
        error_type: str | None,
    ) -> ProviderHealthStatus:
        name = self._normalize(provider)
        current = self.get_status(name)
        failure_count = current.failure_count + 1
        status = ProviderHealthStatus(
            provider=name,
            healthy=False,
            success_count=current.success_count,
            failure_count=failure_count,
            last_error_type=str(error_type or "unknown"),
            degraded=failure_count >= 3,
            cooldown_active=False,
            metadata=self._metadata(),
        )
        self._status[name] = status
        return status

    def get_status(self, provider: str) -> ProviderHealthStatus:
        name = self._normalize(provider)
        return self._status.get(
            name,
            ProviderHealthStatus(
                provider=name,
                healthy=True,
                success_count=0,
                failure_count=0,
                last_error_type=None,
                degraded=False,
                cooldown_active=False,
                metadata=self._metadata(),
            ),
        )

    def build_summary(self) -> dict:
        return {
            "total": len(self._status),
            "degraded": sum(1 for status in self._status.values() if status.degraded),
            "providers": {
                provider: {
                    "healthy": status.healthy,
                    "success_count": status.success_count,
                    "failure_count": status.failure_count,
                    "degraded": status.degraded,
                }
                for provider, status in self._status.items()
            },
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


def build_sample_health_status() -> ProviderHealthStatus:
    monitor = ProviderHealthMonitor()
    monitor.record_failure("mock", "TimeoutError")
    monitor.record_failure("mock", "TimeoutError")
    return monitor.record_failure("mock", "TimeoutError")


__all__ = [
    "ProviderHealthStatus",
    "ProviderHealthMonitor",
    "build_sample_health_status",
]
