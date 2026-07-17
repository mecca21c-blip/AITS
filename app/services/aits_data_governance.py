from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_data_catalog import AITSDataCatalog, default_governance_policy
from app.services.aits_data_governance_view_model import build_data_governance_view_model
from app.services.aits_disk_health import AITSDiskHealth


class AITSDataGovernanceService:
    """Lightweight cached-status facade used by UI workers."""

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)

    def snapshot(self, *, policy: dict[str, Any] | None = None, deep: bool = False) -> dict[str, Any]:
        effective_policy = {**default_governance_policy(), **dict(policy or {})}
        catalog = AITSDataCatalog(self.data_root).inspect(deep=deep)
        disk = AITSDiskHealth(self.data_root).inspect(effective_policy)
        result = {
            "schema": "aits_data_governance_snapshot.v1", "policy": effective_policy,
            "catalog": catalog, "disk": disk, "last_backup_at": "",
            "raw_jsonl_scanned_on_ui_thread": False, "source_modified": False,
            "operations_inflight": False,
        }
        result["user_view"] = build_data_governance_view_model(result)
        return result

    @staticmethod
    def operation_guard(*, runtime_active: bool, inflight: bool, explicit: bool) -> str:
        if runtime_active:
            return "live_runtime_active"
        if inflight:
            return "governance_operation_already_running"
        if not explicit:
            return "explicit_user_request_required"
        return ""
