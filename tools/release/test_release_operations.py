from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.aits_backup_manager import AITSBackupManager
from app.services.aits_installation_migration import AITSInstallationMigration
from app.services.aits_release_operation_context import AITSReleaseOperationContext
from app.services.aits_support_bundle import AITSSupportBundle


EXCLUDED_NAMES = {"prefs.json", "secrets.json", "secret.bin", ".env", "credentials.json"}
EXCLUDED_PARTS = {"acceptance", "backups", "archive", "cache", "temp", "__pycache__"}
STATE_PREFIXES = (
    "local_engine", "local_models", "ai_policy", "ai_review", "learning_journal",
    "runtime", "runtime_smoke_reports", "release", "governance",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_digest(root: Path, *, exclude_acceptance: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "missing"
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if exclude_acceptance and "acceptance" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(_sha256(path).encode("ascii"))
    return digest.hexdigest()


def _copy_current_state(source_data: Path, destination_data: Path) -> int:
    count = 0
    for path in sorted(source_data.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_data)
        if path.name.lower() in EXCLUDED_NAMES or any(part.lower() in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] == "logs":
            continue
        if not relative.parts or relative.parts[0] not in STATE_PREFIXES:
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".txt", ".md"}:
            continue
        if path.stat().st_size > 8 * 1024 * 1024:
            continue
        target = destination_data / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    destination_data.mkdir(parents=True, exist_ok=True)
    catalog_marker = destination_data / "release" / "isolated_source_catalog.json"
    catalog_marker.parent.mkdir(parents=True, exist_ok=True)
    catalog_marker.write_text(json.dumps({
        "schema": "aits_isolated_source_catalog.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "copied_real_state_file_count": count,
        "source_was_read_only": True,
        "secrets_excluded_before_copy": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return count + 1


def _context(operation: str, source: Path, target: Path, staging: Path) -> AITSReleaseOperationContext:
    return AITSReleaseOperationContext.create(
        operation_type=operation,
        source_root=source,
        target_root=target,
        staging_root=staging,
        explicit_user_approval=True,
        runtime_off_confirmed=True,
        execution_authorized=True,
        isolated_acceptance_mode=True,
        destructive_operation=False,
        source_preservation_required=True,
        rollback_required=True,
        requested_by="acceptance_test",
        authorization_reason="isolated_release_operations_acceptance",
    )


def _record_acceptance_resume(result: dict[str, Any]) -> None:
    acceptance = ROOT / "data" / "acceptance"
    defects_path = acceptance / "master_acceptance_defects.jsonl"
    state_path = acceptance / "master_acceptance_state.json"
    target_ids = {"MA-20260718-001", "MA-20260718-002", "MA-20260718-003"}
    existing_lines = defects_path.read_text(encoding="utf-8").splitlines() if defects_path.is_file() else []
    existing_transition_ids = {
        str(row.get("transition_id"))
        for line in existing_lines if line.strip()
        for row in [json.loads(line)]
        if isinstance(row, dict)
    }
    with defects_path.open("a", encoding="utf-8") as handle:
        for defect_id in sorted(target_ids):
            transition_id = f"stabilization-v1-isolated-{defect_id}"
            if transition_id in existing_transition_ids:
                continue
            handle.write(json.dumps({
                "schema": "aits_acceptance_defect_transition.v1",
                "transition_id": transition_id,
                "defect_id": defect_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_status": "open",
                "status": "acceptance_retest_required",
                "fix_implemented": True,
                "isolated_verified": True,
                "closed": False,
                "evidence_report": "release_operations_stabilization_test.json",
                "artifact_version": "1.0.0-rc.2",
            }, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    state.update({
        "acceptance_campaign_id": "SPRINT-AITS-MASTER-INTEGRATED-RUNTIME-ACCEPTANCE-V1",
        "previous_rc_version": "1.0.0-rc.1",
        "current_rc_version": "1.0.0-rc.2",
        "resume_supported": True,
        "completed_phases": ["A_artifact_provenance", "B_packaged_first_run"],
        "invalidated_phases": ["A_artifact_provenance", "B_packaged_first_run", "C_existing_data_migration", "D_packaged_ui_ssot", "I_data_governance"],
        "blocked_phase": "rc2_acceptance_retest",
        "blocking_defect_ids": sorted(target_ids),
        "resolved_defect_ids": [],
        "stabilization_commit": "pending_commit",
        "isolated_release_operations_verified": bool(result.get("passed")),
        "status": "acceptance_retest_required",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(state_path)


def run() -> dict[str, Any]:
    source_data = ROOT / "data"
    local_app_data = Path(os.environ.get("LOCALAPPDATA", "")) / "AITS" if os.environ.get("LOCALAPPDATA") else Path("__missing__")
    source_user_before = _tree_digest(source_data, exclude_acceptance=True)
    local_before = _tree_digest(local_app_data)
    with tempfile.TemporaryDirectory(prefix="aits-release-operations-") as temp:
        temp_root = Path(temp)
        isolated_source = temp_root / "source"
        copied = _copy_current_state(source_data, isolated_source / "data")
        isolated_source_before = _tree_digest(isolated_source)

        backup_context = _context(
            "essential_backup", isolated_source, temp_root / "backups", temp_root / "backup-staging"
        )
        backup = AITSBackupManager(isolated_source / "data", app_root=ROOT).execute(
            "essential", context=backup_context
        )
        backup_readback = AITSBackupManager.validate_bundle(backup.get("artifact_path", "")) if backup.get("artifact_path") else {}

        support_context = _context(
            "support_bundle", isolated_source, temp_root / "support", temp_root / "support-staging"
        )
        support = AITSSupportBundle().execute(context=support_context)
        support_readback = AITSSupportBundle.validate_bundle(support.get("artifact_path", "")) if support.get("artifact_path") else {}

        migration_context = _context(
            "migration", isolated_source, temp_root / "activated", temp_root / "migration-staging"
        )
        migration_service = AITSInstallationMigration()
        migration = migration_service.execute(migration_context)
        rollback = migration_service.rollback(migration_context, migration) if migration.get("activation_completed") else {
            "rollback_completed": False, "blocker": "migration_activation_failed"
        }
        isolated_source_after = _tree_digest(isolated_source)

        result = {
            "schema": "aits_release_operations_isolated_test.v1",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "isolated_acceptance_mode": True,
            "copied_real_state_file_count": copied,
            "essential_backup": backup,
            "essential_backup_readback": backup_readback,
            "support_bundle": support,
            "support_bundle_readback": support_readback,
            "migration": migration,
            "migration_rollback": rollback,
            "isolated_source_hash_unchanged": isolated_source_before == isolated_source_after,
            "real_user_data_migration_executed": False,
            "packaged_app_runtime_executed": False,
        }
    source_user_after = _tree_digest(source_data, exclude_acceptance=True)
    local_after = _tree_digest(local_app_data)
    result.update(
        source_user_data_hash_unchanged=source_user_before == source_user_after,
        localappdata_user_data_hash_unchanged=local_before == local_after,
    )
    checks = [
        backup.get("operation_executed"), backup_readback.get("valid"),
        support.get("operation_executed"), support_readback.get("valid"),
        migration.get("activation_completed"), migration.get("checksum_valid"),
        migration.get("schema_valid"), migration.get("resolver_target_valid"),
        rollback.get("rollback_completed"), result["isolated_source_hash_unchanged"],
        result["source_user_data_hash_unchanged"], result["localappdata_user_data_hash_unchanged"],
        not backup_readback.get("secret_leak_detected"),
        not support_readback.get("secret_leak_detected"),
        not support_readback.get("raw_prompt_detected"),
    ]
    result["passed"] = all(bool(value) for value in checks)
    result["first_blocker"] = "" if result["passed"] else next(
        (str(item.get("blocker")) for item in (backup, support, migration, rollback) if item.get("blocker")),
        "isolated_release_operation_check_failed",
    )
    report = ROOT / "data" / "acceptance" / "release_operations_stabilization_test.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(report)
    if result["passed"]:
        _record_acceptance_resume(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-current-data-readonly-clone", action="store_true", required=True)
    parser.add_argument("--isolated-temp-root", action="store_true", required=True)
    parser.parse_args()
    result = run()
    print(json.dumps({
        "passed": result["passed"],
        "first_blocker": result["first_blocker"],
        "copied_real_state_file_count": result["copied_real_state_file_count"],
        "essential_backup": result["essential_backup"].get("valid"),
        "support_bundle": result["support_bundle"].get("valid"),
        "migration_activation": result["migration"].get("activation_completed"),
        "migration_rollback": result["migration_rollback"].get("rollback_completed"),
        "source_unchanged": result["source_user_data_hash_unchanged"],
        "localappdata_unchanged": result["localappdata_user_data_hash_unchanged"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
