from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from app.services.aits_data_source_resolver import AITSDataSourceResolver


ARCHIVE_SCHEMA = "aits_data_archive_manifest.v1"


class AITSDataArchiveManager:
    """Archive planner. Source cleanup is a separate, disabled-by-default action."""

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.resolver = AITSDataSourceResolver(self.data_root)

    def plan(self, dataset_id: str, *, deep_checksum: bool = False) -> dict[str, Any]:
        segments = self.resolver.segments(dataset_id, include_active=True, include_archived=False)
        source = Path(segments[0]["path"]) if segments else None
        size = source.stat().st_size if source and source.is_file() else 0
        checksum = hashlib.sha256(source.read_bytes()).hexdigest() if deep_checksum and source and source.is_file() else ""
        return {
            "schema": "aits_data_archive_plan.v1",
            "manifest_schema": ARCHIVE_SCHEMA,
            "dataset_id": dataset_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source or ""),
            "uncompressed_size": size,
            "source_checksum": checksum,
            "source_checksum_pending": not deep_checksum,
            "compression": "gzip",
            "steps": ["readonly_snapshot", "temporary_archive", "record_count_validation", "checksum_validation", "atomic_rename"],
            "off_only": True,
            "user_confirmation_required": True,
            "original_source_preserved": True,
            "delete_source_allowed": False,
            "operation_executed": False,
        }

    def execute(self, dataset_id: str, *, runtime_active: bool, explicit: bool, approved: bool) -> dict[str, Any]:
        if runtime_active or not explicit or not approved:
            return {**self.plan(dataset_id), "blocker": "off_explicit_user_approval_required"}
        return {**self.plan(dataset_id), "blocker": "structure_sprint_archive_execution_disabled"}
