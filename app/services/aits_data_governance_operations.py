from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.aits_data_governance import AITSDataGovernanceService


class AITSDataGovernanceOperations:
    """OFF-only action coordinator with an append-only audit contract."""

    EVENTS = {
        "policy_updated", "catalog_rebuilt", "archive_planned", "archive_completed", "archive_failed",
        "backup_created", "backup_failed", "restore_planned", "restore_completed", "restore_failed",
        "derived_regenerated", "derived_quarantined", "integrity_issue_detected", "migration_planned",
        "migration_completed", "training_use_changed", "disk_warning", "data_reset_requested", "data_reset_completed",
    }

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.history_path = self.data_root / "governance" / "data_governance_history.jsonl"
        self._inflight = False

    def plan(self, action: str, *, runtime_active: bool, explicit: bool, dataset_ids: list[str] | None = None) -> dict[str, Any]:
        blocker = AITSDataGovernanceService.operation_guard(runtime_active=runtime_active, inflight=self._inflight, explicit=explicit)
        return {
            "schema": "aits_data_governance_operation_plan.v1", "action": action,
            "dataset_ids": list(dataset_ids or []), "off_only": True,
            "user_approval_required": True, "duplicate_operation_guard": True,
            "blocker": blocker, "operation_executed": False,
        }

    def append_history(self, event: str, *, dataset_ids: list[str], user_initiated: bool,
                       explicit: bool = False, approved: bool = False) -> dict[str, Any]:
        if event not in self.EVENTS:
            raise ValueError("unsupported_governance_event")
        if not explicit or not approved:
            return {"appended": False, "blocker": "explicit_user_approval_required"}
        row = {
            "schema": "aits_data_governance_history_event.v1", "event_id": str(uuid4()),
            "event": event, "created_at": datetime.now(timezone.utc).isoformat(),
            "user_initiated": user_initiated, "dataset_ids": dataset_ids,
            "source_count_before": None, "source_count_after": None,
            "size_before": None, "size_after": None, "backup_id": None,
            "archive_id": None, "blocker": "", "actual_order": False, "submitted": 0,
        }
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.history_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"appended": True, "event_id": row["event_id"]}

    @staticmethod
    def training_use_policy(policy: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "aits_training_use_policy.v1",
            "included_dataset_ids": list(policy.get("included_dataset_ids") or []),
            "excluded_dataset_ids": list(policy.get("excluded_dataset_ids") or []),
            "date_range": dict(policy.get("training_date_range") or {}),
            "archived_source_training_enabled": bool(policy.get("archived_source_training_enabled", True)),
            "historical_replay_enabled": bool(policy.get("historical_replay_enabled", True)),
            "minimum_review_reliability": str(policy.get("minimum_review_reliability") or "medium"),
            "source_mutation": False,
        }

    @staticmethod
    def derived_regeneration_plan(*, runtime_active: bool, explicit: bool, approved: bool) -> dict[str, Any]:
        return {
            "schema": "aits_derived_regeneration_plan.v1", "source_preserved": True,
            "derived_only": True, "champion_preserved": True,
            "full_reset_enabled": False, "operation_executed": False,
            "blocker": "" if explicit and approved and not runtime_active else "off_explicit_user_approval_required",
        }
