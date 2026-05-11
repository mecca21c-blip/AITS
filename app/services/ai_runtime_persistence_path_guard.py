from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath, PureWindowsPath

from app.services.ai_runtime_persistence_policy import (
    AIRuntimePersistencePolicyBuilder,
)


BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".dll"}


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
class AIRuntimePersistencePathCheck:
    allowed: bool
    path: str
    reason: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimePersistencePathGuard:
    """Validates candidate persistence paths without creating directories."""

    def check_path(
        self,
        path: str,
        policy=None,
    ) -> AIRuntimePersistencePathCheck:
        active_policy = policy or AIRuntimePersistencePolicyBuilder().build_default_policy()
        candidate = str(path or "").strip().replace("\\", "/")
        if not candidate:
            return self._result(False, candidate, "empty_path")
        pure = PureWindowsPath(candidate)
        if pure.is_absolute() and not bool(active_policy.allow_absolute_path):
            return self._result(False, candidate, "absolute_path_blocked")
        if (not pure.is_absolute()) and not bool(active_policy.allow_relative_path):
            return self._result(False, candidate, "relative_path_blocked")
        parts = [part for part in PurePath(candidate).parts if part not in ("", ".")]
        if ".." in parts:
            return self._result(False, candidate, "path_traversal_blocked")
        suffix = PurePath(candidate).suffix.lower()
        if suffix in BLOCKED_EXTENSIONS:
            return self._result(False, candidate, "blocked_extension")
        base = str(active_policy.allowed_base_dir or "").strip().replace("\\", "/").rstrip("/")
        if not base:
            return self._result(False, candidate, "missing_allowed_base_dir")
        normalized = candidate.rstrip("/")
        if normalized != base and not normalized.startswith(base + "/"):
            return self._result(False, candidate, "outside_allowed_base_dir")
        return self._result(True, candidate, "path_allowed")

    def _result(
        self,
        allowed: bool,
        path: str,
        reason: str,
    ) -> AIRuntimePersistencePathCheck:
        return AIRuntimePersistencePathCheck(
            allowed=bool(allowed),
            path=str(path or ""),
            reason=reason,
            metadata=_metadata(),
        )


def build_sample_path_check() -> AIRuntimePersistencePathCheck:
    return AIRuntimePersistencePathGuard().check_path("data/runtime_exports/a.json")


__all__ = [
    "AIRuntimePersistencePathCheck",
    "AIRuntimePersistencePathGuard",
    "build_sample_path_check",
]
