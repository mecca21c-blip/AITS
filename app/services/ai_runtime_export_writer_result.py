from __future__ import annotations

from dataclasses import dataclass, field


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
class AIRuntimeExportWriterResult:
    attempted: bool
    written: bool
    path: str
    format: str
    reason: str
    bytes_planned: int
    bytes_written: int
    metadata: dict = field(default_factory=_metadata)


def build_sample_export_writer_result() -> AIRuntimeExportWriterResult:
    return AIRuntimeExportWriterResult(
        attempted=True,
        written=False,
        path="data/runtime_exports/one_shot_snapshot.json",
        format="json",
        reason="writer_stub_no_actual_write",
        bytes_planned=128,
        bytes_written=0,
        metadata=_metadata(),
    )


__all__ = [
    "AIRuntimeExportWriterResult",
    "build_sample_export_writer_result",
]
