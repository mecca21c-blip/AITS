from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_export_writer import build_sample_export_writer_result_from_stub
from app.services.ai_runtime_export_writer_preview import build_sample_export_writer_preview


def _metadata() -> dict:
    return {
        "write_disabled": True,
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
    }


@dataclass
class AIRuntimeExportWriterReport:
    status: str
    written: bool
    path: str
    reason: str
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeExportWriterReportBuilder:
    """Builds compact writer reports from writer result/preview."""

    def build_report(self, result=None, preview=None) -> AIRuntimeExportWriterReport:
        written = bool(self._get(result, "written", False))
        path = str(self._get(result, "path", "") or self._get(preview, "path", "") or "")
        reason = str(self._get(result, "reason", "") or self._get(preview, "reason", "") or "")
        can_write = bool(self._get(preview, "can_write", False))
        status = self._status(written, can_write, reason)
        summary_line = f"{status} | written={written} | path={path or '-'} | reason={reason or '-'}"
        return AIRuntimeExportWriterReport(
            status=status,
            written=written,
            path=path,
            reason=reason,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _status(self, written: bool, can_write: bool, reason: str) -> str:
        if written:
            return "저장 준비됨"
        if reason == "writer_stub_no_actual_write":
            return "Stub 모드"
        if can_write:
            return "저장 안 함"
        return "저장 차단"

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        if value is None:
            return fallback
        return getattr(value, name, fallback)


def build_sample_export_writer_report() -> AIRuntimeExportWriterReport:
    return AIRuntimeExportWriterReportBuilder().build_report(
        result=build_sample_export_writer_result_from_stub(),
        preview=build_sample_export_writer_preview(),
    )


__all__ = [
    "AIRuntimeExportWriterReport",
    "AIRuntimeExportWriterReportBuilder",
    "build_sample_export_writer_report",
]
