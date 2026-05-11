from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_persistence_path_guard import AIRuntimePersistencePathGuard
from app.services.ai_runtime_persistence_policy import (
    AIRuntimePersistencePolicyBuilder,
)
from app.services.ai_runtime_persistence_size_guard import AIRuntimePersistenceSizeGuard


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "gate_only": True,
    }


@dataclass
class AIRuntimePersistenceGateResult:
    allowed: bool
    enabled: bool
    format_allowed: bool
    path_allowed: bool
    size_allowed: bool
    safe_to_persist: bool
    redacted: bool
    reason: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimePersistenceGate:
    """Evaluates whether a runtime export payload may be persisted."""

    def __init__(self) -> None:
        self._path_guard = AIRuntimePersistencePathGuard()
        self._size_guard = AIRuntimePersistenceSizeGuard()

    def evaluate(
        self,
        export_payload,
        path: str,
        policy=None,
    ) -> AIRuntimePersistenceGateResult:
        active_policy = policy or AIRuntimePersistencePolicyBuilder().build_default_policy()
        payload_format = str(self._get(export_payload, "format", "") or "")
        format_allowed = payload_format in list(active_policy.allowed_formats or [])
        path_check = self._path_guard.check_path(path, active_policy)
        payload_value = self._get(export_payload, "payload", export_payload)
        size_check = self._size_guard.check_size(payload_value, active_policy)
        safe_to_persist = bool(self._get(export_payload, "safe_to_persist", False))
        redacted = bool(self._get(export_payload, "redacted", False))

        reason = "allowed"
        allowed = True
        if not bool(active_policy.enabled):
            allowed = False
            reason = "policy_disabled"
        elif not format_allowed:
            allowed = False
            reason = "format_blocked"
        elif not bool(path_check.allowed):
            allowed = False
            reason = path_check.reason
        elif not bool(size_check.allowed):
            allowed = False
            reason = size_check.reason
        elif bool(active_policy.require_redacted) and not redacted:
            allowed = False
            reason = "redaction_required"
        elif bool(active_policy.require_safe_to_persist) and not safe_to_persist:
            allowed = False
            reason = "safe_to_persist_required"

        return AIRuntimePersistenceGateResult(
            allowed=bool(allowed),
            enabled=bool(active_policy.enabled),
            format_allowed=bool(format_allowed),
            path_allowed=bool(path_check.allowed),
            size_allowed=bool(size_check.allowed),
            safe_to_persist=safe_to_persist,
            redacted=redacted,
            reason=reason,
            metadata={
                **_metadata(),
                "path": str(path or ""),
                "path_reason": path_check.reason,
                "size_reason": size_check.reason,
                "payload_bytes": size_check.payload_bytes,
            },
        )

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_persistence_gate_result() -> AIRuntimePersistenceGateResult:
    payload = {
        "format": "json",
        "payload": {"provider": "mock"},
        "safe_to_persist": True,
        "redacted": True,
    }
    return AIRuntimePersistenceGate().evaluate(
        payload,
        "data/runtime_exports/one_shot_snapshot.json",
    )


__all__ = [
    "AIRuntimePersistenceGate",
    "AIRuntimePersistenceGateResult",
    "build_sample_persistence_gate_result",
]
