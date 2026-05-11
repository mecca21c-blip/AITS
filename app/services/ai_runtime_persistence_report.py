from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_persistence_gate import build_sample_persistence_gate_result


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
class AIRuntimePersistenceReport:
    allowed: bool
    status: str
    reason: str
    path_allowed: bool
    size_allowed: bool
    redacted: bool
    safe_to_persist: bool
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimePersistenceReportBuilder:
    """Builds compact UI/log reports from persistence gate results."""

    def build_report(self, gate_result) -> AIRuntimePersistenceReport:
        allowed = bool(self._get(gate_result, "allowed", False))
        reason = str(self._get(gate_result, "reason", "") or "")
        status = self._status(gate_result, reason)
        path_allowed = bool(self._get(gate_result, "path_allowed", False))
        size_allowed = bool(self._get(gate_result, "size_allowed", False))
        redacted = bool(self._get(gate_result, "redacted", False))
        safe_to_persist = bool(self._get(gate_result, "safe_to_persist", False))
        summary_line = (
            f"{status} | reason={reason} | path={path_allowed} | "
            f"size={size_allowed} | redacted={redacted}"
        )
        return AIRuntimePersistenceReport(
            allowed=allowed,
            status=status,
            reason=reason,
            path_allowed=path_allowed,
            size_allowed=size_allowed,
            redacted=redacted,
            safe_to_persist=safe_to_persist,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _status(self, gate_result, reason: str) -> str:
        if bool(self._get(gate_result, "allowed", False)):
            return "저장 가능"
        if not bool(self._get(gate_result, "enabled", False)):
            return "정책 비활성"
        if reason in {"empty_path", "absolute_path_blocked", "relative_path_blocked", "path_traversal_blocked", "blocked_extension", "outside_allowed_base_dir"}:
            return "경로 차단"
        if reason == "payload_too_large":
            return "크기 초과"
        if reason in {"redaction_required", "safe_to_persist_required"}:
            return "민감정보 의심"
        return "저장 차단"

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_persistence_report() -> AIRuntimePersistenceReport:
    return AIRuntimePersistenceReportBuilder().build_report(
        build_sample_persistence_gate_result()
    )


__all__ = [
    "AIRuntimePersistenceReport",
    "AIRuntimePersistenceReportBuilder",
    "build_sample_persistence_report",
]
