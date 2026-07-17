from __future__ import annotations

from typing import Any


class AITSReleaseRollback:
    def plan(self, previous_manifest: str) -> dict[str, Any]:
        return {
            "schema": "aits_release_rollback_plan.v1", "previous_manifest": previous_manifest,
            "app_rollback_separate_from_data": True, "app_only_preferred": True,
            "data_rollback_user_approval_required": True, "latest_source_loss_allowed": False,
            "schema_compatibility_required": True, "staging_required": True,
            "pre_upgrade_backup_required": True, "operation_executed": False,
        }

    @staticmethod
    def uninstall_contract() -> dict[str, Any]:
        return {
            "schema": "aits_uninstall_contract.v1", "preserve_user_data_default": True,
            "remove_user_data_default": False, "typed_confirmation_required": True,
            "verified_backup_recommended": True, "silent_user_data_deletion": False,
        }
