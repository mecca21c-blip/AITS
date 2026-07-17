from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_data_catalog import AITSDataCatalog


class AITSInstallationMigration:
    def detect(self, legacy_root: Path | str = Path("C:/AITS")) -> dict[str, Any]:
        root = Path(legacy_root)
        return {"schema": "aits_existing_installation_detection.v1", "root": str(root), "exists": root.is_dir(), "data_exists": (root / "data").is_dir()}

    def plan(self, source_root: Path | str, target_root: Path | str) -> dict[str, Any]:
        source, target = Path(source_root), Path(target_root)
        catalog = AITSDataCatalog(source / "data").inspect(deep=False)
        return {
            "schema": "aits_installation_migration_plan.v1", "source_root": str(source), "target_root": str(target),
            "catalog_dataset_count": catalog["dataset_count"], "essential_backup_required": True,
            "staging_required": True, "checksum_record_schema_validation": True,
            "atomic_activation": True, "source_preserved": True, "rollback_ready": True,
            "authority_preserved": True, "champion_preserved": True, "intent_policy_preserved": True,
            "plaintext_secret_migration": False, "off_only": True, "user_approval_required": True,
            "operation_executed": False,
        }

    def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"operation_executed": False, "blocker": "structure_sprint_migration_execution_disabled"}
