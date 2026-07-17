from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from app.services.aits_data_catalog import AITSDataCatalog


BACKUP_SCHEMA = "aits_data_backup_manifest.v1"
SECRET_NAMES = {"secret.bin", "secrets.json", ".env", "prefs.json"}
PROFILES = {
    "essential": {"critical_state"},
    "learning": {"critical_state", "immutable_source", "derived_learning", "model_artifact"},
    "full": {"critical_state", "immutable_source", "derived_learning", "model_artifact", "operational_log"},
}


class AITSBackupManager:
    """Plans verified ZIP backups. Building a bundle is deliberately gated."""

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)

    @staticmethod
    def _safe_relative(path: str) -> bool:
        pure = PurePosixPath(path.replace("\\", "/"))
        return not pure.is_absolute() and ".." not in pure.parts

    def plan(self, profile: str) -> dict[str, Any]:
        if profile not in PROFILES:
            raise ValueError("unsupported_backup_profile")
        catalog = AITSDataCatalog(self.data_root).inspect(deep=False)
        included, excluded = [], []
        for row in catalog["entries"]:
            name = Path(row["path"]).name.lower()
            unsafe = row["category"] == "secret_excluded" or name in SECRET_NAMES or "prompt" in name or "credential" in name
            if unsafe or row["category"] not in PROFILES[profile]:
                excluded.append(row["dataset_id"])
            elif row["exists"]:
                included.append(row["dataset_id"])
        if profile in {"essential", "learning", "full"}:
            included.append("sanitized_settings_export")
        digest = hashlib.sha256("\n".join(sorted(included)).encode("utf-8")).hexdigest()
        return {
            "schema": BACKUP_SCHEMA, "backup_id": f"plan-{profile}",
            "created_at": datetime.now(timezone.utc).isoformat(), "profile": profile,
            "included_datasets": included, "excluded_datasets": excluded,
            "compression": "zip_deflated", "manifest_checksum": digest,
            "secret_exclusion_validated": True, "api_key_included": False,
            "raw_prompt_included": False, "user_approval_required": True,
            "sanitized_settings_export_required": True,
            "off_only": True, "validation_result": "plan_ready", "operation_executed": False,
        }

    def execute(self, profile: str, *, runtime_active: bool, explicit: bool, approved: bool) -> dict[str, Any]:
        plan = self.plan(profile)
        blocker = "structure_sprint_backup_execution_disabled" if explicit and approved and not runtime_active else "off_explicit_user_approval_required"
        return {**plan, "blocker": blocker, "operation_executed": False}
