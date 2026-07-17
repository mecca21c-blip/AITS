from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.aits_data_catalog import AITSDataCatalog, default_governance_policy
from app.services.aits_release_manifest import safe_git_commit
from app.services.aits_release_operation_context import AITSReleaseOperationContext
from app.services.aits_schema_registry import AITSSchemaRegistry
from app.services.aits_secret_store import sanitized_config
from app.version import version_info


BACKUP_SCHEMA = "aits_backup_manifest.v1"
SECRET_NAMES = {"secret.bin", "secrets.json", ".env", "credentials.json"}
PROFILES = {
    "essential": {"critical_state"},
    "learning": {"critical_state", "immutable_source", "derived_learning", "model_artifact"},
    "full": {"critical_state", "immutable_source", "derived_learning", "model_artifact", "operational_log"},
}
ESSENTIAL_RELATIVE_PATHS = (
    "local_engine/local_engine_authority_state.json",
    "local_engine/local_engine_authority_history.jsonl",
    "local_engine/local_engine_authority_grants.jsonl",
    "local_engine/local_engine_authority_grant_state.json",
    "local_engine/local_engine_capability_matrix.json",
    "local_engine/local_engine_health_state.json",
    "local_engine/local_engine_continuous_learning_state.json",
    "local_engine/local_engine_teacher_sync_state.json",
    "local_models/registry.json",
    "local_models/latest_model_state.json",
    "local_models/latest_confidence_calibration_attempt.json",
    "local_models/latest_calibration_summary.json",
    "local_models/calibration_profile.json",
    "ai_intent/active_intents.json",
    "ai_intent/intent_history.jsonl",
    "ai_intent/intent_summary.json",
    "ai_policy/effective_policy_runtime_snapshot.json",
    "ai_policy/effective_policy_snapshots.jsonl",
    "learning_journal/policy_suggestions.jsonl",
    "learning_journal/policy_suggestion_summary.json",
)
_SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(rb"Authorization\s*:\s*Bearer\s+\S+", re.I),
    re.compile(rb'"(?:access_key|secret_key|api_key|password|token)"\s*:\s*"(?!<excluded>)[^"\s]{8,}"', re.I),
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_count(data: bytes, suffix: str) -> int | None:
    if suffix == ".jsonl":
        return sum(1 for line in data.splitlines() if line.strip())
    return 1 if suffix == ".json" else None


def _secret_hits(name: str, data: bytes) -> list[str]:
    hits: list[str] = []
    lower = PurePosixPath(name).name.lower()
    if lower in SECRET_NAMES or lower == "prefs.json":
        hits.append("forbidden_secret_filename")
    if b"raw_prompt" in data.lower():
        hits.append("raw_prompt_field")
    for index, pattern in enumerate(_SECRET_PATTERNS, start=1):
        if pattern.search(data):
            hits.append(f"secret_pattern_{index}")
    return hits


class AITSBackupManager:
    """Creates verified, immutable backup ZIPs through an authorized OFF context."""

    def __init__(self, data_root: Path | str = Path("data"), app_root: Path | str | None = None) -> None:
        self.data_root = Path(data_root).resolve()
        self.app_root = Path(app_root).resolve() if app_root else self.data_root.parent

    @staticmethod
    def _safe_relative(path: str) -> bool:
        pure = PurePosixPath(path.replace("\\", "/"))
        return not pure.is_absolute() and ".." not in pure.parts

    def _selected_files(self, profile: str) -> list[Path]:
        catalog = AITSDataCatalog(self.data_root).inspect(deep=False)
        selected: set[Path] = set()
        for row in catalog["entries"]:
            path = Path(row["path"])
            if row["category"] in PROFILES[profile] and row["category"] != "secret_excluded" and path.exists():
                if path.is_file():
                    selected.add(path)
                elif profile != "essential":
                    selected.update(item for item in path.rglob("*") if item.is_file())
        if profile == "essential":
            selected.update(self.data_root / relative for relative in ESSENTIAL_RELATIVE_PATHS if (self.data_root / relative).is_file())
        return sorted(selected)

    def plan(self, profile: str) -> dict[str, Any]:
        if profile not in PROFILES:
            raise ValueError("unsupported_backup_profile")
        files = self._selected_files(profile)
        excluded = sorted(SECRET_NAMES | {"prefs.json", "raw_prompt", "account_private_payload", "logs", "cache", "temp", "__pycache__"})
        return {
            "schema": BACKUP_SCHEMA,
            "backup_id": f"plan-{profile}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "included_datasets": [path.relative_to(self.data_root).as_posix() for path in files],
            "excluded_paths": excluded,
            "compression": "zip_deflated",
            "secret_exclusion_validated": True,
            "api_key_included": False,
            "raw_prompt_included": False,
            "user_approval_required": True,
            "sanitized_settings_export_required": True,
            "off_only": True,
            "validation_result": "plan_ready",
            "operation_executed": False,
        }

    def _payload(self, profile: str) -> dict[str, bytes]:
        payload: dict[str, bytes] = {}
        for path in self._selected_files(profile):
            relative = path.relative_to(self.data_root).as_posix()
            data = path.read_bytes()
            if _secret_hits(relative, data):
                raise ValueError(f"secret_scan_failed:{relative}")
            payload[f"payload/data/{relative}"] = data
        prefs_candidates = (self.data_root / "prefs.json", self.app_root / "prefs.json")
        for prefs in prefs_candidates:
            if not prefs.is_file():
                continue
            try:
                safe = sanitized_config(json.loads(prefs.read_text(encoding="utf-8")))
            except (OSError, UnicodeError, json.JSONDecodeError):
                safe = {"settings_status": "unavailable_or_invalid"}
            payload["payload/config/sanitized_settings.json"] = json.dumps(safe, ensure_ascii=False, indent=2).encode("utf-8")
            break
        payload["payload/meta/data_governance_policy.json"] = json.dumps(default_governance_policy(), ensure_ascii=False, indent=2).encode("utf-8")
        payload["payload/meta/schema_registry.json"] = json.dumps(AITSSchemaRegistry().inspect(), ensure_ascii=False, indent=2).encode("utf-8")
        provenance = {**version_info(), "build_commit": safe_git_commit(self.app_root)}
        payload["payload/meta/release_provenance.json"] = json.dumps(provenance, ensure_ascii=False, indent=2).encode("utf-8")
        return payload

    @staticmethod
    def validate_bundle(path: Path | str) -> dict[str, Any]:
        bundle = Path(path)
        errors: list[str] = []
        secret_hits: list[str] = []
        try:
            with ZipFile(bundle, "r") as archive:
                if archive.testzip():
                    errors.append("zip_crc_failed")
                names = archive.namelist()
                if "aits_backup_manifest.json" not in names:
                    return {"valid": False, "errors": ["manifest_missing"], "secret_hits": []}
                manifest = json.loads(archive.read("aits_backup_manifest.json").decode("utf-8"))
                for row in manifest.get("files", []):
                    name = str(row.get("path", ""))
                    if name not in names or not AITSBackupManager._safe_relative(name):
                        errors.append(f"unsafe_or_missing:{name}")
                        continue
                    data = archive.read(name)
                    if _sha256_bytes(data) != row.get("sha256"):
                        errors.append(f"hash_mismatch:{name}")
                    secret_hits.extend(f"{name}:{hit}" for hit in _secret_hits(name, data))
                    if name.endswith(".json"):
                        try:
                            json.loads(data.decode("utf-8"))
                        except (UnicodeError, json.JSONDecodeError):
                            errors.append(f"json_invalid:{name}")
                    elif name.endswith(".jsonl"):
                        for line in data.splitlines():
                            if line.strip():
                                try:
                                    json.loads(line.decode("utf-8"))
                                except (UnicodeError, json.JSONDecodeError):
                                    errors.append(f"jsonl_invalid:{name}")
                                    break
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(type(exc).__name__)
            manifest = {}
        return {
            "schema": "aits_backup_validation.v1",
            "path": str(bundle),
            "valid": not errors and not secret_hits,
            "errors": errors,
            "secret_hits": secret_hits,
            "manifest_valid": bool(manifest),
            "hash_valid": not any("hash_mismatch" in item for item in errors),
            "readback_valid": not errors,
            "secret_leak_detected": bool(secret_hits),
        }

    def execute(
        self,
        profile: str,
        *,
        context: AITSReleaseOperationContext | None = None,
        runtime_active: bool | None = None,
        explicit: bool | None = None,
        approved: bool | None = None,
    ) -> dict[str, Any]:
        plan = self.plan(profile)
        if context is None:
            return {**plan, "blocker": "authorized_release_operation_context_required", "operation_executed": False}
        context.require_authorized(f"{profile}_backup")
        context.target_root.mkdir(parents=True, exist_ok=True)
        expected_type = f"{profile}_backup"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        final_path = context.target_root / f"AITS-{profile}-{timestamp}-{context.operation_id[-8:]}.zip"
        temporary = final_path.with_suffix(".partial")
        payload = self._payload(profile)
        file_rows = [
            {
                "path": name,
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
                "record_count": _record_count(data, Path(name).suffix),
            }
            for name, data in sorted(payload.items())
        ]
        manifest = {
            "schema": BACKUP_SCHEMA,
            "backup_id": context.operation_id,
            "profile": profile,
            "app_version": version_info()["semantic_version"],
            "build_commit": safe_git_commit(self.app_root),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_root_digest": hashlib.sha256(str(self.data_root).encode("utf-8")).hexdigest(),
            "included_datasets": plan["included_datasets"],
            "excluded_paths": plan["excluded_paths"],
            "files": file_rows,
            "file_count": len(file_rows),
            "total_size": sum(row["size_bytes"] for row in file_rows),
            "secret_scan_result": "pass",
            "validation_result": "pending_readback",
        }
        with context.operation_lock():
            try:
                with ZipFile(temporary, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                    for name, data in sorted(payload.items()):
                        archive.writestr(name, data)
                    archive.writestr("aits_backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                validation = self.validate_bundle(temporary)
                if not validation["valid"]:
                    failed = temporary.with_suffix(".failed")
                    temporary.replace(failed)
                    return {**plan, **validation, "blocker": "backup_validation_failed", "failed_artifact": str(failed), "operation_executed": False}
                temporary.replace(final_path)
                history = context.target_root / "backup_history.jsonl"
                with history.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"backup_id": context.operation_id, "path": str(final_path), "created_at": manifest["created_at"], "validation_result": "pass"}, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                temporary.unlink(missing_ok=True)
        validation = self.validate_bundle(final_path)
        return {
            **plan,
            **validation,
            "operation_type": expected_type,
            "artifact_path": str(final_path),
            "manifest": manifest,
            "operation_executed": True,
            "blocker": "",
        }
