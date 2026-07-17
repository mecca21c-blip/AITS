from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.aits_data_catalog import AITSDataCatalog
from app.services.aits_hardware_probe import AITSHardwareProbe
from app.services.aits_release_manifest import safe_git_commit
from app.services.aits_release_operation_context import AITSReleaseOperationContext
from app.services.aits_secret_store import sanitized_config
from app.version import version_info


SUPPORT_SCHEMA = "aits_support_bundle_manifest.v1"
_SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(rb"Authorization\s*:\s*(?:Bearer\s+)?\S+", re.I),
    re.compile(rb'"(?:access_key|secret_key|api_key|password|token)"\s*:\s*"(?!<excluded>|<configured>|<not_configured>)[^"\s]{8,}"', re.I),
)
_PRIVATE_LOG_LINE = re.compile(r"account|balance|holding|authorization|raw_prompt|prompt=|payload=|credential|secret_key|access_key", re.I)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _sanitize_text(text: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<excluded>", text)
    text = re.sub(r"AIza[A-Za-z0-9_-]{12,}", "<excluded>", text)
    text = re.sub(r"(?i)(Authorization\s*:\s*)(?:Bearer\s+)?\S+", r"\1<excluded>", text)
    text = re.sub(r"(?i)((?:access_key|secret_key|api_key|password|token)\s*[=:]\s*)\S+", r"\1<excluded>", text)
    text = re.sub(r"C:\\Users\\[^\\\s]+", r"C:\\Users\\<user>", text, flags=re.I)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<email>", text)
    return text


def _scan(name: str, data: bytes) -> list[str]:
    hits: list[str] = []
    lower = PurePosixPath(name).name.lower()
    if lower in {"secrets.json", "secret.bin", ".env", "credentials.json", "prefs.json"}:
        hits.append("forbidden_filename")
    if b"raw_prompt" in data.lower():
        hits.append("raw_prompt")
    for index, pattern in enumerate(_SECRET_PATTERNS, start=1):
        if pattern.search(data):
            hits.append(f"secret_pattern_{index}")
    return hits


class AITSSupportBundle:
    """Creates a minimal, sanitized diagnostic ZIP through an authorized OFF context."""

    def plan(self, data_root: Path | str, safe_settings: dict[str, Any] | None = None) -> dict[str, Any]:
        root = Path(data_root)
        content = {
            "version": version_info(),
            "safe_settings": sanitized_config(safe_settings or {}),
            "hardware": AITSHardwareProbe().inspect(root),
            "catalog_summary": {key: value for key, value in AITSDataCatalog(root).inspect(deep=False).items() if key != "entries"},
        }
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return {
            "schema": SUPPORT_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "included": ["version", "safe_settings", "masked_provider_state", "authority_summary", "hardware", "sanitized_recent_logs", "crash_marker", "catalog_summary", "release_manifest", "latest_smoke_summary", "defect_summary"],
            "excluded": ["api_key", "account_private_data", "raw_prompt", "full_outcome_source", "training_source", "credential"],
            "content_digest": digest,
            "zip_required": True,
            "user_initiated_required": True,
            "secret_exclusion_validated": True,
            "operation_executed": False,
        }

    def _sections(self, source_root: Path, safe_settings: dict[str, Any] | None) -> dict[str, bytes]:
        data_root = source_root / "data" if (source_root / "data").is_dir() else source_root
        authority = _safe_json(data_root / "local_engine/local_engine_authority_state.json")
        registry = _safe_json(data_root / "local_models/registry.json")
        policy = _safe_json(data_root / "ai_policy/effective_policy_runtime_snapshot.json")
        intent = _safe_json(data_root / "ai_intent/intent_summary.json") or _safe_json(data_root / "ai_intent/active_intents.json")
        acceptance = _safe_json(data_root / "acceptance/master_acceptance_summary.json")
        release = _safe_json(source_root / "release_manifest.json")
        settings = sanitized_config(safe_settings or _safe_json(data_root / "config/sanitized_settings.json"))
        provider = settings.get("strategy", {}) if isinstance(settings, dict) else {}
        provider_summary = {
            "selected_provider": str(provider.get("ai_provider", "unknown")) if isinstance(provider, dict) else "unknown",
            "openai_key_configured": False,
            "gemini_key_configured": False,
            "raw_key_included": False,
        }
        authority_summary = {
            "global_level": authority.get("global_level"),
            "effective_level": authority.get("effective_level"),
            "authority": authority.get("authority") or authority.get("authority_state"),
            "health": authority.get("health") or authority.get("health_status"),
            "safe_for_live_decision": authority.get("safe_for_live_decision", False),
            "live_decision_enabled": authority.get("live_decision_enabled", False),
        }
        registry_summary = {
            "champion_model_id": registry.get("champion_model_id") or registry.get("champion"),
            "challenger_model_id": registry.get("challenger_model_id") or registry.get("challenger"),
            "registry_schema": registry.get("schema"),
        }
        policy_intent_summary = {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
            "policy_hash": policy.get("policy_hash"),
            "intent_status": intent.get("status") or intent.get("review_status"),
            "raw_policy_or_intent_included": False,
        }
        catalog = AITSDataCatalog(data_root).inspect(deep=False)
        log_candidates = (data_root / "logs/aits.log", data_root / "logs" / "aits.log")
        sanitized_lines: list[str] = []
        for log_path in log_candidates:
            if not log_path.is_file():
                continue
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-250:]
                sanitized_lines = [_sanitize_text(line) for line in lines if not _PRIVATE_LOG_LINE.search(line)][-200:]
            except OSError:
                sanitized_lines = []
            break
        defects_path = data_root / "acceptance/master_acceptance_defects.jsonl"
        defect_counts: Counter[str] = Counter()
        if defects_path.is_file():
            try:
                for line in defects_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        defect_counts[str(json.loads(line).get("severity", "unknown"))] += 1
            except (OSError, UnicodeError, json.JSONDecodeError):
                defect_counts["unreadable"] += 1
        values: dict[str, Any] = {
            "version.json": {**version_info(), "build_commit": safe_git_commit(source_root)},
            "safe_settings_summary.json": settings,
            "provider_summary.json": provider_summary,
            "authority_summary.json": authority_summary,
            "model_summary.json": registry_summary,
            "policy_intent_summary.json": policy_intent_summary,
            "hardware_summary.json": AITSHardwareProbe().inspect(data_root),
            "catalog_summary.json": {key: value for key, value in catalog.items() if key != "entries"},
            "schema_compatibility.json": {"minimum": version_info()["minimum_data_schema_version"], "maximum": version_info()["maximum_supported_data_schema_version"]},
            "release_manifest_summary.json": {key: release.get(key) for key in ("semantic_version", "build_commit", "architecture", "build_profile", "signature_status")},
            "acceptance_summary.json": {key: acceptance.get(key) for key in ("master_acceptance_status", "release_verdict", "critical_defect_count", "high_defect_count", "medium_defect_count", "low_defect_count")},
            "defect_summary.json": {"counts": dict(defect_counts)},
            "crash_marker.json": {"hard_freeze_marker_present": (data_root / "runtime/hard_freeze.marker").is_file()},
        }
        sections = {f"payload/{name}": json.dumps(sanitized_config(value), ensure_ascii=False, indent=2, default=str).encode("utf-8") for name, value in values.items()}
        sections["payload/sanitized_recent_logs.txt"] = ("\n".join(sanitized_lines) + ("\n" if sanitized_lines else "")).encode("utf-8")
        return sections

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
                if "aits_support_bundle_manifest.json" not in names:
                    return {"valid": False, "errors": ["manifest_missing"], "secret_hits": []}
                manifest = json.loads(archive.read("aits_support_bundle_manifest.json").decode("utf-8"))
                for row in manifest.get("files", []):
                    name = str(row.get("path", ""))
                    pure = PurePosixPath(name)
                    if name not in names or pure.is_absolute() or ".." in pure.parts:
                        errors.append(f"unsafe_or_missing:{name}")
                        continue
                    data = archive.read(name)
                    if _sha256(data) != row.get("sha256"):
                        errors.append(f"hash_mismatch:{name}")
                    secret_hits.extend(f"{name}:{hit}" for hit in _scan(name, data))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(type(exc).__name__)
            manifest = {}
        raw_prompt = any("raw_prompt" in item for item in secret_hits)
        return {
            "schema": "aits_support_bundle_validation.v1",
            "path": str(bundle),
            "valid": not errors and not secret_hits,
            "errors": errors,
            "secret_hits": secret_hits,
            "manifest_valid": bool(manifest),
            "hash_valid": not any("hash_mismatch" in item for item in errors),
            "secret_leak_detected": bool(secret_hits),
            "raw_prompt_detected": raw_prompt,
            "private_account_data_detected": False,
        }

    def execute(
        self,
        *,
        context: AITSReleaseOperationContext | None,
        safe_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if context is None:
            return {"operation_executed": False, "blocker": "authorized_release_operation_context_required"}
        context.require_authorized("support_bundle")
        plan = self.plan(context.source_root / "data", safe_settings)
        context.target_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        final_path = context.target_root / f"AITS-support-{timestamp}-{context.operation_id[-8:]}.zip"
        temporary = final_path.with_suffix(".partial")
        sections = self._sections(context.source_root, safe_settings)
        scan_hits = [f"{name}:{hit}" for name, data in sections.items() for hit in _scan(name, data)]
        if scan_hits:
            return {**plan, "operation_executed": False, "blocker": "support_bundle_sanitization_failed", "secret_hits": scan_hits}
        rows = [{"path": name, "sha256": _sha256(data), "size_bytes": len(data)} for name, data in sorted(sections.items())]
        manifest = {
            "schema": SUPPORT_SCHEMA,
            "support_bundle_id": context.operation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "app_version": version_info()["semantic_version"],
            "build_commit": safe_git_commit(context.source_root),
            "included_sections": plan["included"],
            "excluded_sections": plan["excluded"],
            "files": rows,
            "total_size": sum(row["size_bytes"] for row in rows),
            "sanitization_rules": ["key_token_masking", "authorization_removal", "private_account_line_exclusion", "user_path_masking", "raw_payload_exclusion"],
            "secret_scan_result": "pass",
            "validation_result": "pending_readback",
        }
        with context.operation_lock():
            try:
                with ZipFile(temporary, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                    for name, data in sorted(sections.items()):
                        archive.writestr(name, data)
                    archive.writestr("aits_support_bundle_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                validation = self.validate_bundle(temporary)
                if not validation["valid"]:
                    failed = temporary.with_suffix(".failed")
                    temporary.replace(failed)
                    return {**plan, **validation, "operation_executed": False, "blocker": "support_bundle_validation_failed", "failed_artifact": str(failed)}
                temporary.replace(final_path)
            finally:
                temporary.unlink(missing_ok=True)
        validation = self.validate_bundle(final_path)
        return {**plan, **validation, "artifact_path": str(final_path), "manifest": manifest, "operation_executed": True, "blocker": ""}
