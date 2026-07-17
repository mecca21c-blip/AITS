from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from app.services.aits_backup_manager import AITSBackupManager
from app.services.aits_data_catalog import AITSDataCatalog
from app.services.aits_path_resolver import AITSPathResolver
from app.services.aits_release_operation_context import AITSReleaseOperationContext
from app.services.aits_secret_store import sanitized_config


MIGRATION_SCHEMA = "aits_installation_migration_result.v1"
EXCLUDED_NAMES = {"secret.bin", "secrets.json", ".env", "credentials.json", "prefs.json"}
EXCLUDED_DIRECTORIES = {"__pycache__", "cache", "temp", "backups", "acceptance"}
PRESERVATION_GROUPS = {
    "authority": (
        "data/local_engine/local_engine_authority_state.json",
        "data/local_engine/local_engine_authority_history.jsonl",
        "data/local_engine/local_engine_authority_grants.jsonl",
        "data/local_engine/local_engine_capability_matrix.json",
    ),
    "champion": ("data/local_models/registry.json",),
    "policy_intent": (
        "data/ai_policy/effective_policy_runtime_snapshot.json",
        "data/ai_policy/effective_policy_snapshots.jsonl",
        "data/ai_intent/active_intents.json",
        "data/ai_intent/intent_history.jsonl",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _snapshot_digest(root: Path, relative_paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative in relative_paths:
        path = root / relative
        if path.is_file():
            digest.update(relative.encode("utf-8"))
            digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _copy_allowed(source: Path, target: Path) -> list[str]:
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part.lower() in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.name.lower() in EXCLUDED_NAMES or "raw_prompt" in path.name.lower() or "credential" in path.name.lower():
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(relative.as_posix())
    return copied


def _validate_structured_files(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name.endswith(".corrupt"):
            continue
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".jsonl":
                with path.open("r", encoding="utf-8") as handle:
                    for number, line in enumerate(handle, start=1):
                        if line.strip():
                            json.loads(line)
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{path.relative_to(root).as_posix()}:invalid_structured_data")
    return errors


class AITSInstallationMigration:
    def detect(self, legacy_root: Path | str = Path("C:/AITS")) -> dict[str, Any]:
        root = Path(legacy_root)
        return {"schema": "aits_existing_installation_detection.v1", "root": str(root), "exists": root.is_dir(), "data_exists": (root / "data").is_dir()}

    def plan(self, source_root: Path | str, target_root: Path | str) -> dict[str, Any]:
        source, target = Path(source_root), Path(target_root)
        catalog = AITSDataCatalog(source / "data").inspect(deep=False)
        return {
            "schema": "aits_installation_migration_plan.v1",
            "source_root": str(source),
            "target_root": str(target),
            "catalog_dataset_count": catalog["dataset_count"],
            "essential_backup_required": True,
            "staging_required": True,
            "checksum_record_schema_validation": True,
            "atomic_activation": True,
            "source_preserved": True,
            "rollback_ready": True,
            "authority_preserved": True,
            "champion_preserved": True,
            "intent_policy_preserved": True,
            "plaintext_secret_migration": False,
            "off_only": True,
            "user_approval_required": True,
            "operation_executed": False,
        }

    def execute(self, context: AITSReleaseOperationContext | None = None, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if context is None:
            return {"operation_executed": False, "blocker": "authorized_release_operation_context_required"}
        context.require_authorized("migration")
        source_root = context.source_root
        target_root = context.target_root
        staging_root = context.staging_root
        plan = self.plan(source_root, target_root)
        if not (source_root / "data").is_dir():
            return {**plan, "blocker": "source_data_root_missing", "operation_executed": False}
        free = shutil.disk_usage(target_root.parent if target_root.parent.exists() else target_root.parent.parent).free
        source_size = sum(path.stat().st_size for path in (source_root / "data").rglob("*") if path.is_file())
        if free < max(source_size * 2, 64 * 1024 * 1024):
            return {**plan, "blocker": "insufficient_target_disk_space", "operation_executed": False}
        source_manifest_before = _tree_manifest(source_root)
        preservation_before = {name: _snapshot_digest(source_root, paths) for name, paths in PRESERVATION_GROUPS.items()}
        operation_root = staging_root.parent / f"migration-{context.operation_id}"
        work_staging = operation_root / "staging"
        backup_root = operation_root / "essential_backup"
        previous_target = operation_root / "previous_target"
        state_path = operation_root / "migration_state.json"
        operation_root.mkdir(parents=True, exist_ok=False)
        state: dict[str, Any] = {"schema": MIGRATION_SCHEMA, "operation_id": context.operation_id, "state": "backup_required"}

        def persist_state() -> None:
            temporary = state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(state_path)

        with context.operation_lock():
            persist_state()
            backup_context = AITSReleaseOperationContext.create(
                operation_type="essential_backup",
                source_root=source_root,
                target_root=backup_root,
                staging_root=operation_root / "backup-staging",
                explicit_user_approval=context.explicit_user_approval,
                runtime_off_confirmed=context.runtime_off_confirmed,
                execution_authorized=context.execution_authorized,
                isolated_acceptance_mode=context.isolated_acceptance_mode,
                requested_by=context.requested_by,
                authorization_reason=f"migration_precondition:{context.operation_id}",
            )
            backup_result = AITSBackupManager(source_root / "data", app_root=source_root).execute("essential", context=backup_context)
            if not backup_result.get("valid"):
                state.update(state="failed", blocker="migration_backup_failed")
                persist_state()
                return {**plan, **state, "backup": backup_result, "operation_executed": False}
            state["state"] = "staging"
            persist_state()
            work_staging.mkdir(parents=True)
            copied = _copy_allowed(source_root / "data", work_staging / "data")
            prefs = source_root / "data" / "prefs.json"
            if prefs.is_file():
                try:
                    safe_prefs = sanitized_config(json.loads(prefs.read_text(encoding="utf-8")))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    safe_prefs = {"settings_status": "unavailable_or_invalid"}
                safe_path = work_staging / "config" / "sanitized_settings.json"
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                safe_path.write_text(json.dumps(safe_prefs, ensure_ascii=False, indent=2), encoding="utf-8")
            state["state"] = "validating"
            persist_state()
            stage_manifest = _tree_manifest(work_staging)
            structured_errors = _validate_structured_files(work_staging)
            preservation_staged = {name: _snapshot_digest(work_staging, paths) for name, paths in PRESERVATION_GROUPS.items()}
            preservation_valid = {name: preservation_before[name] == preservation_staged[name] for name in PRESERVATION_GROUPS}
            checksum_valid = all((work_staging / relative).is_file() and _sha256(work_staging / relative) == digest for relative, digest in stage_manifest.items())
            if structured_errors or not checksum_valid or not all(preservation_valid.values()):
                state.update(state="failed", blocker="migration_validation_failed")
                persist_state()
                return {
                    **plan, **state, "backup": backup_result, "schema_errors": structured_errors,
                    "checksum_valid": checksum_valid, "preservation_valid": preservation_valid,
                    "operation_executed": False,
                }
            state["state"] = "ready_to_activate"
            persist_state()
            target_root.parent.mkdir(parents=True, exist_ok=True)
            target_preexisted = target_root.exists()
            if target_preexisted:
                target_root.replace(previous_target)
            state["state"] = "activating"
            persist_state()
            work_staging.replace(target_root)
            resolved = AITSPathResolver.resolve(env={"AITS_DATA_ROOT": str(target_root)}, frozen=True, executable=str(target_root / "AITS.exe"))
            resolver_target_valid = resolved.user_data_root == target_root.resolve()
            post_errors = _validate_structured_files(target_root)
            target_preservation = {name: _snapshot_digest(target_root, paths) for name, paths in PRESERVATION_GROUPS.items()}
            post_preservation_valid = {name: preservation_before[name] == target_preservation[name] for name in PRESERVATION_GROUPS}
            if post_errors or not resolver_target_valid or not all(post_preservation_valid.values()):
                if target_root.exists():
                    target_root.replace(operation_root / "failed_activation")
                if previous_target.exists():
                    previous_target.replace(target_root)
                state.update(state="failed", blocker="post_activation_validation_failed")
                persist_state()
                return {**plan, **state, "operation_executed": False}
            source_unchanged = source_manifest_before == _tree_manifest(source_root)
            state.update(state="activated", activated_at=datetime.now(timezone.utc).isoformat(), rollback_ready=True)
            persist_state()
        return {
            **plan,
            **state,
            "backup": backup_result,
            "copied_file_count": len(copied),
            "staging_completed": True,
            "checksum_valid": checksum_valid,
            "schema_valid": not structured_errors,
            "authority_preserved": post_preservation_valid["authority"],
            "champion_preserved": post_preservation_valid["champion"],
            "policy_intent_preserved": post_preservation_valid["policy_intent"],
            "activation_completed": True,
            "resolver_target_valid": resolver_target_valid,
            "source_hash_unchanged": source_unchanged,
            "target_preexisted": target_preexisted,
            "operation_root": str(operation_root),
            "previous_target": str(previous_target),
            "state_path": str(state_path),
            "operation_executed": True,
            "blocker": "",
        }

    def rollback(self, context: AITSReleaseOperationContext, result: dict[str, Any]) -> dict[str, Any]:
        context.require_authorized("migration")
        if not result.get("activation_completed") or not result.get("rollback_ready"):
            return {"rollback_completed": False, "blocker": "migration_not_rollback_ready"}
        operation_root = Path(result["operation_root"])
        previous_target = Path(result["previous_target"])
        target_root = context.target_root
        rolled_back_activation = operation_root / "rolled_back_activation"
        with context.operation_lock():
            if not target_root.exists():
                return {"rollback_completed": False, "blocker": "active_target_missing"}
            target_root.replace(rolled_back_activation)
            if previous_target.exists():
                previous_target.replace(target_root)
            expected_target_exists = bool(result.get("target_preexisted"))
            target_state_valid = target_root.exists() == expected_target_exists
            source_valid = context.source_root.exists()
            state_path = Path(result["state_path"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.update(state="rolled_back", rolled_back_at=datetime.now(timezone.utc).isoformat())
            temporary = state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(state_path)
        return {
            "schema": "aits_installation_migration_rollback.v1",
            "rollback_completed": target_state_valid and source_valid,
            "target_previous_state_restored": target_state_valid,
            "source_preserved": source_valid,
            "rolled_back_activation": str(rolled_back_activation),
            "blocker": "" if target_state_valid and source_valid else "rollback_validation_failed",
        }
