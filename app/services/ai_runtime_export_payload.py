from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.services.ai_runtime_snapshot import build_sample_runtime_snapshot
from app.services.ai_runtime_snapshot_sanitizer import AIRuntimeSnapshotSanitizer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "export_ready": True,
    }


@dataclass
class AIRuntimeExportPayload:
    export_id: str
    created_at: str
    format: str
    payload: dict
    safe_to_persist: bool
    redacted: bool
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeExportPayloadBuilder:
    """Builds export-ready payloads without writing or transmitting them."""

    def __init__(self) -> None:
        self._sanitizer = AIRuntimeSnapshotSanitizer()

    def build_payload(
        self,
        snapshot,
        format: str = "json",
    ) -> AIRuntimeExportPayload:
        safe_format = str(format or "json").strip().lower()
        if safe_format not in {"json", "csv_preview", "text_preview"}:
            safe_format = "json"
        payload = self._sanitizer.sanitize(snapshot)
        return AIRuntimeExportPayload(
            export_id=f"export-{uuid4().hex}",
            created_at=_now(),
            format=safe_format,
            payload=payload,
            safe_to_persist=True,
            redacted=True,
            metadata=_metadata(),
        )


def build_sample_export_payload() -> AIRuntimeExportPayload:
    return AIRuntimeExportPayloadBuilder().build_payload(build_sample_runtime_snapshot())


__all__ = [
    "AIRuntimeExportPayload",
    "AIRuntimeExportPayloadBuilder",
    "build_sample_export_payload",
]
