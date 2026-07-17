from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_schema_registry import AITSSchemaRegistry


class AITSDataMigrationManager:
    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.registry = AITSSchemaRegistry()

    def plan(self, dataset_id: str, target_schema: str) -> dict[str, Any]:
        return {
            "schema": "aits_data_migration_plan.v1", "dataset_id": dataset_id,
            "target_schema": target_schema, "staging_required": True, "backup_required": True,
            "count_hash_validation_required": True, "user_approval_required": True,
            "atomic_apply": True, "rollback_ready": True, "operation_executed": False,
        }

    def execute(self, *, runtime_active: bool, explicit: bool, approved: bool) -> dict[str, Any]:
        return {"operation_executed": False, "blocker": "structure_sprint_migration_execution_disabled" if explicit and approved and not runtime_active else "off_explicit_user_approval_required"}
