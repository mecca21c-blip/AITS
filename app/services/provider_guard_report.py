from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.provider_cooldown_manager import ProviderCooldownState
from app.services.provider_health_monitor import ProviderHealthStatus
from app.services.provider_retry_policy import ProviderRetryDecision
from app.services.provider_timeout_guard import ProviderTimeoutPolicy


@dataclass
class ProviderGuardReport:
    provider: str
    runtime_allowed: bool
    cooldown_blocked: bool
    retry_allowed: bool
    degraded: bool
    timeout_sec: int
    reason: str
    metadata: dict = field(default_factory=dict)


class ProviderGuardReportBuilder:
    """Compacts guard state for one-shot attach-only diagnostics."""

    def build_report(
        self,
        provider: str,
        timeout_policy: ProviderTimeoutPolicy | None = None,
        retry_decision: ProviderRetryDecision | None = None,
        cooldown_state: ProviderCooldownState | None = None,
        health_status: ProviderHealthStatus | None = None,
    ) -> ProviderGuardReport:
        name = str(provider or "unknown").strip().lower() or "unknown"
        cooldown_blocked = bool(getattr(cooldown_state, "active", False))
        degraded = bool(getattr(health_status, "degraded", False))
        retry_allowed = bool(getattr(retry_decision, "should_retry", False))
        timeout_sec = int(getattr(timeout_policy, "total_timeout_sec", 0) or 0)
        timeout_enabled = bool(getattr(timeout_policy, "enabled", True))
        runtime_allowed = bool(timeout_enabled and not cooldown_blocked and not degraded)
        reason = self._reason(
            timeout_policy,
            retry_decision,
            cooldown_state,
            health_status,
            runtime_allowed,
        )
        return ProviderGuardReport(
            provider=name,
            runtime_allowed=runtime_allowed,
            cooldown_blocked=cooldown_blocked,
            retry_allowed=retry_allowed,
            degraded=degraded,
            timeout_sec=timeout_sec,
            reason=reason,
            metadata={
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
                "retry_executed": False,
                "failover_executed": False,
            },
        )

    def _reason(
        self,
        timeout_policy: Any,
        retry_decision: Any,
        cooldown_state: Any,
        health_status: Any,
        runtime_allowed: bool,
    ) -> str:
        if getattr(cooldown_state, "active", False):
            return str(getattr(cooldown_state, "reason", "cooldown_active"))
        if getattr(health_status, "degraded", False):
            return str(getattr(health_status, "last_error_type", "provider_degraded"))
        if not getattr(timeout_policy, "enabled", True):
            return "timeout_policy_disabled"
        if getattr(retry_decision, "reason", ""):
            return str(getattr(retry_decision, "reason"))
        return "runtime_allowed" if runtime_allowed else "runtime_blocked"


def build_sample_guard_report() -> ProviderGuardReport:
    from app.services.provider_retry_policy import ProviderRetryPolicy
    from app.services.provider_timeout_guard import ProviderTimeoutGuard

    return ProviderGuardReportBuilder().build_report(
        "mock",
        timeout_policy=ProviderTimeoutGuard().get_policy("mock"),
        retry_decision=ProviderRetryPolicy().decide("mock", None, 0),
        cooldown_state=None,
        health_status=None,
    )


__all__ = [
    "ProviderGuardReport",
    "ProviderGuardReportBuilder",
    "build_sample_guard_report",
]
