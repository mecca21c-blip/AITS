from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from app.services.ai_runtime_export_writer_guard import AIRuntimeExportWriterGuard
from app.services.ai_runtime_export_writer_result import AIRuntimeExportWriterResult


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


class AIRuntimeExportWriter:
    """Writer stub: evaluates write eligibility and never writes files in this goal."""

    def __init__(self) -> None:
        self._guard = AIRuntimeExportWriterGuard()

    def write(
        self,
        export_payload,
        path: str,
        gate_result=None,
        explicit_enable: bool = False,
    ) -> AIRuntimeExportWriterResult:
        can_write, reason = self._guard.can_write(
            export_payload,
            gate_result=gate_result,
            explicit_enable=explicit_enable,
        )
        payload_value = self._get(export_payload, "payload", {})
        bytes_planned = self._payload_bytes(payload_value)
        payload_format = str(self._get(export_payload, "format", "json") or "json")

        if not bool(explicit_enable):
            return AIRuntimeExportWriterResult(
                attempted=True,
                written=False,
                path=str(path or ""),
                format=payload_format,
                reason="explicit_enable_required",
                bytes_planned=bytes_planned,
                bytes_written=0,
                metadata=_metadata(),
            )
        if not bool(can_write):
            return AIRuntimeExportWriterResult(
                attempted=True,
                written=False,
                path=str(path or ""),
                format=payload_format,
                reason=str(reason or "write_blocked"),
                bytes_planned=bytes_planned,
                bytes_written=0,
                metadata=_metadata(),
            )
        return AIRuntimeExportWriterResult(
            attempted=True,
            written=False,
            path=str(path or ""),
            format=payload_format,
            reason="writer_stub_no_actual_write",
            bytes_planned=bytes_planned,
            bytes_written=0,
            metadata=_metadata(),
        )

    def _payload_bytes(self, payload: Any) -> int:
        try:
            value = asdict(payload) if is_dataclass(payload) else payload
            return len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        except Exception:
            return 0

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        if value is None:
            return fallback
        return getattr(value, name, fallback)


def build_sample_export_writer_result_from_stub() -> AIRuntimeExportWriterResult:
    payload = {"format": "json", "payload": {"a": 1}, "safe_to_persist": True, "redacted": True}
    gate = {"allowed": True, "reason": "allowed"}
    return AIRuntimeExportWriter().write(
        payload,
        "data/runtime_exports/one_shot_snapshot.json",
        gate_result=gate,
        explicit_enable=False,
    )


__all__ = [
    "AIRuntimeExportWriter",
    "build_sample_export_writer_result_from_stub",
]
