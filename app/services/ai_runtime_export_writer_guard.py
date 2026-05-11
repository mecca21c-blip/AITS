from __future__ import annotations

from typing import Any


class AIRuntimeExportWriterGuard:
    """Final write guard. It never writes and only returns write eligibility."""

    def can_write(
        self,
        export_payload,
        gate_result=None,
        explicit_enable: bool = False,
    ) -> tuple[bool, str]:
        if not bool(explicit_enable):
            return False, "explicit_enable_required"
        if not bool(self._get(gate_result, "allowed", False)):
            reason = str(self._get(gate_result, "reason", "") or "gate_blocked")
            return False, reason
        if not bool(self._get(export_payload, "safe_to_persist", False)):
            return False, "safe_to_persist_required"
        if not bool(self._get(export_payload, "redacted", False)):
            return False, "redaction_required"
        payload_format = str(self._get(export_payload, "format", "") or "").strip().lower()
        if payload_format not in {"json", "csv_preview", "text_preview"}:
            return False, "format_not_allowed"
        return True, "write_allowed"

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        if value is None:
            return fallback
        return getattr(value, name, fallback)


def build_sample_export_writer_guard_result() -> tuple[bool, str]:
    payload = {"format": "json", "safe_to_persist": True, "redacted": True}
    gate = {"allowed": True, "reason": "allowed"}
    return AIRuntimeExportWriterGuard().can_write(
        payload,
        gate_result=gate,
        explicit_enable=False,
    )


__all__ = [
    "AIRuntimeExportWriterGuard",
    "build_sample_export_writer_guard_result",
]
