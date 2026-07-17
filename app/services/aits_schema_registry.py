from __future__ import annotations

from typing import Any


class AITSSchemaRegistry:
    SCHEMAS = {
        "data_catalog": "aits_data_asset_catalog_entry.v1",
        "archive_manifest": "aits_data_archive_manifest.v1",
        "period_summary": "aits_data_period_summary.v1",
        "backup_manifest": "aits_backup_manifest.v1",
        "governance_policy": "aits_data_governance_policy.v1",
        "release_operation_context": "aits_release_operation_context.v1",
        "installation_migration": "aits_installation_migration.v1",
        "support_bundle_manifest": "aits_support_bundle_manifest.v1",
    }

    def inspect(self) -> dict[str, Any]:
        return {
            "schema": "aits_schema_registry.v1", "datasets": dict(self.SCHEMAS),
            "supported_old_schemas": {}, "migration_functions_registered": True,
            "reversible_migration_required": True, "backup_required": True,
        }
