from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any


class AITSRestoreManager:
    """Staging-first restore contract; no direct overwrite entrypoint exists."""

    MODES = ("essential", "learning", "models", "full")

    @staticmethod
    def safe_member_path(name: str) -> bool:
        path = PurePosixPath(name.replace("\\", "/"))
        return not path.is_absolute() and ".." not in path.parts

    def plan(self, bundle: Path | str, *, mode: str = "essential") -> dict[str, Any]:
        if mode not in self.MODES:
            raise ValueError("unsupported_restore_mode")
        return {
            "schema": "aits_data_restore_plan.v1", "bundle": str(bundle), "mode": mode,
            "manifest_parse_required": True, "unsafe_path_scan_required": True,
            "schema_compatibility_required": True, "staging_required": True,
            "checksum_validation_required": True, "current_state_snapshot_required": True,
            "user_approval_required": True, "off_only": True, "atomic_apply": True,
            "post_restore_validation": True, "rollback_ready": True,
            "secret_restore_default": False, "operation_executed": False,
        }

    def execute(self, bundle: Path | str, *, mode: str, runtime_active: bool, explicit: bool, approved: bool) -> dict[str, Any]:
        plan = self.plan(bundle, mode=mode)
        blocker = "structure_sprint_restore_execution_disabled" if explicit and approved and not runtime_active else "off_explicit_user_approval_required"
        return {**plan, "blocker": blocker, "operation_executed": False}
