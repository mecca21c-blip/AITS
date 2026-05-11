from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from app.services.ai_runtime_export_writer_guard import AIRuntimeExportWriterGuard


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
class AIRuntimeExportWriterPreview:
    path: str
    format: str
    payload_bytes: int
    can_write: bool
    reason: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeExportWriterPreviewBuilder:
    """Builds write previews without filesystem side effects."""

    def __init__(self) -> None:
        self._guard = AIRuntimeExportWriterGuard()

    def build_preview(
        self,
        export_payload,
        path: str,
        gate_result=None,
        explicit_enable: bool = False,
    ) -> AIRuntimeExportWriterPreview:
        payload = self._get(export_payload, "payload", {})
        payload_bytes = self._payload_bytes(payload)
        can_write, reason = self._guard.can_write(
            export_payload,
            gate_result=gate_result,
            explicit_enable=explicit_enable,
        )
        return AIRuntimeExportWriterPreview(
            path=str(path or ""),
            format=str(self._get(export_payload, "format", "json") or "json"),
            payload_bytes=payload_bytes,
            can_write=bool(can_write),
            reason=reason,
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


def build_sample_export_writer_preview() -> AIRuntimeExportWriterPreview:
    payload = {"format": "json", "payload": {"a": 1}, "safe_to_persist": True, "redacted": True}
    gate = {"allowed": True, "reason": "allowed"}
    return AIRuntimeExportWriterPreviewBuilder().build_preview(
        payload,
        "data/runtime_exports/one_shot_snapshot.json",
        gate_result=gate,
        explicit_enable=False,
    )


__all__ = [
    "AIRuntimeExportWriterPreview",
    "AIRuntimeExportWriterPreviewBuilder",
    "build_sample_export_writer_preview",
]
