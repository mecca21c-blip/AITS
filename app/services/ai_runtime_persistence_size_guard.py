from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass

from app.services.ai_runtime_persistence_policy import (
    AIRuntimePersistencePolicyBuilder,
)


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
class AIRuntimePersistenceSizeCheck:
    allowed: bool
    payload_bytes: int
    max_payload_bytes: int
    reason: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimePersistenceSizeGuard:
    """Checks JSON-serialized payload size without writing it."""

    def check_size(
        self,
        payload,
        policy=None,
    ) -> AIRuntimePersistenceSizeCheck:
        active_policy = policy or AIRuntimePersistencePolicyBuilder().build_default_policy()
        try:
            value = asdict(payload) if is_dataclass(payload) else payload
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        except Exception:
            return self._result(False, 0, int(active_policy.max_payload_bytes), "serialization_failed")
        payload_bytes = len(encoded)
        max_bytes = int(active_policy.max_payload_bytes)
        if payload_bytes > max_bytes:
            return self._result(False, payload_bytes, max_bytes, "payload_too_large")
        return self._result(True, payload_bytes, max_bytes, "size_allowed")

    def _result(
        self,
        allowed: bool,
        payload_bytes: int,
        max_payload_bytes: int,
        reason: str,
    ) -> AIRuntimePersistenceSizeCheck:
        return AIRuntimePersistenceSizeCheck(
            allowed=bool(allowed),
            payload_bytes=int(payload_bytes),
            max_payload_bytes=int(max_payload_bytes),
            reason=reason,
            metadata=_metadata(),
        )


def build_sample_size_check() -> AIRuntimePersistenceSizeCheck:
    return AIRuntimePersistenceSizeGuard().check_size({"a": 1})


__all__ = [
    "AIRuntimePersistenceSizeCheck",
    "AIRuntimePersistenceSizeGuard",
    "build_sample_size_check",
]
