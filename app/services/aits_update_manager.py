from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any


class AITSUpdateManager:
    @staticmethod
    def safe_package_member(name: str) -> bool:
        path = PurePosixPath(name.replace("\\", "/"))
        return not path.is_absolute() and ".." not in path.parts

    def plan(self, package: Path | str) -> dict[str, Any]:
        return {
            "schema": "aits_verified_update_plan.v1", "package": str(package),
            "manifest_hash_signature_validation": True, "schema_compatibility_required": True,
            "app_off_required": True, "essential_backup_required": True,
            "app_staging_required": True, "data_migration_staging_required": True,
            "post_update_validation": True, "rollback_ready": True,
            "user_data_overwrite": False, "authority_reset": False, "champion_reset": False,
            "settings_reset": False, "automatic_network_update_enabled": False,
            "user_approval_required": True, "operation_executed": False,
        }
