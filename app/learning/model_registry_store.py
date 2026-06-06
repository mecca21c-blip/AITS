"""Local AI model artifact and registry persistence preview.

This module stores trainer skeleton outputs as JSON files under a local preview
registry directory. It does not create model binaries, run training, connect
Router/UI/Execution/Order/Risk Guard, or approve models for live trading.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REGISTRY_INDEX_SCHEMA = "aits_local_ai_registry_index.v1"
ACTIVE_MODEL_SCHEMA = "aits_active_local_ai_model.v1"
PERSISTENCE_RESULT_SCHEMA = "aits_model_artifact_persistence_result.v1"
REAL_ARTIFACT_PERSISTENCE_RESULT_SCHEMA = "aits_model_real_artifact_persistence_result.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_default_registry_root() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "local_ai_registry"


def ensure_registry_root(root_path: Optional[Path] = None) -> Path:
    root = Path(root_path) if root_path is not None else get_default_registry_root()
    (root / "models").mkdir(parents=True, exist_ok=True)
    if not (root / "registry_index.json").exists():
        save_registry_index(_empty_registry_index(), root)
    if not (root / "active_model.json").exists():
        write_json_file(root / "active_model.json", _empty_active_model())
    return root


def get_model_dir(model_id: str, root_path: Optional[Path] = None) -> Path:
    safe_model_id = validate_safe_model_id(model_id)
    root = ensure_registry_root(root_path)
    return root / "models" / safe_model_id


def validate_safe_model_id(model_id: str) -> str:
    """Validate a model id before using it as a registry path component."""

    return _validate_model_id(model_id)


def sha256_file(path: Path) -> str | None:
    """Return the SHA-256 checksum of a file, or None when unavailable."""

    source = Path(path)
    if not source.exists() or not source.is_file():
        return None
    digest = hashlib.sha256()
    with source.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_model_file_to_registry(
    *,
    source_model_path: Path,
    model_id: str,
    root_path: Optional[Path] = None,
    filename: str = "model.txt",
) -> dict:
    """Copy a prototype model text file into the registry model directory."""

    safe_model_id = validate_safe_model_id(model_id)
    source = Path(source_model_path)
    if not source.exists() or not source.is_file():
        raise ValueError(f"source model file not found: {source}")
    safe_filename = str(filename or "model.txt").strip()
    if not safe_filename or "/" in safe_filename or "\\" in safe_filename or ".." in safe_filename:
        raise ValueError("filename must be a simple file name")
    model_dir = get_model_dir(safe_model_id, root_path)
    target = model_dir / safe_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    checksum = sha256_file(target)
    size = target.stat().st_size if target.exists() else None
    return {
        "source_model_path": str(source),
        "registry_model_path": str(target),
        "model_file_created": bool(target.exists()),
        "model_file_size_bytes": size,
        "checksum": checksum,
        "filename": safe_filename,
    }


def enrich_artifact_manifest_with_registry_model(
    artifact_manifest: dict,
    model_file_info: dict,
) -> dict:
    """Return artifact manifest updated with registry model file metadata."""

    manifest = copy.deepcopy(artifact_manifest or {})
    registry_model_path = model_file_info.get("registry_model_path")
    checksum = model_file_info.get("checksum")
    size = model_file_info.get("model_file_size_bytes")
    manifest.setdefault("schema", "aits_model_artifact_manifest.v1")
    manifest["artifact_path"] = registry_model_path
    manifest["checksum"] = checksum
    manifest["model_file_created"] = bool(model_file_info.get("model_file_created"))
    manifest["text_model_created"] = True
    manifest["model_file_size_bytes"] = size
    manifest["source_model_path"] = model_file_info.get("source_model_path")
    manifest["registry_model_path"] = registry_model_path
    manifest["binary_created"] = False
    notes = list(manifest.get("notes") or [])
    for note in ("registry_model_file_copied", "prototype_artifact_not_live_approved"):
        if note not in notes:
            notes.append(note)
    manifest["notes"] = notes
    return manifest


def validate_artifact_metadata_consistency(
    *,
    artifact_manifest: dict,
    evaluation_report: dict,
    model_registry_entry: dict,
) -> dict:
    """Validate registry artifact metadata consistency."""

    report_artifact = evaluation_report.get("artifact") if isinstance(evaluation_report, dict) else {}
    report_artifact = report_artifact if isinstance(report_artifact, dict) else {}
    checks = {
        "artifact_checksum_matches_report": artifact_manifest.get("checksum")
        == report_artifact.get("checksum"),
        "artifact_path_matches_registry_entry": artifact_manifest.get("artifact_path")
        == model_registry_entry.get("artifact_path"),
        "evaluation_report_id_matches_registry_entry": evaluation_report.get("evaluation_report_id")
        == model_registry_entry.get("evaluation_report_id"),
        "registry_entry_not_approved": model_registry_entry.get("status") != "approved",
    }
    issues = [key for key, ok in checks.items() if not ok]
    return {
        "consistent": not issues,
        "checks": checks,
        "issues": issues,
    }


def write_json_file(path: Path, payload: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_sanitize_payload(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def read_json_file(path: Path) -> dict | None:
    source = Path(path)
    if not source.exists():
        return None
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON file: {source}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {source}")
    return data


def load_registry_index(root_path: Optional[Path] = None) -> dict:
    root = ensure_registry_root(root_path)
    data = read_json_file(root / "registry_index.json")
    return data if isinstance(data, dict) else _empty_registry_index()


def save_registry_index(index: dict, root_path: Optional[Path] = None) -> Path:
    root = Path(root_path) if root_path is not None else get_default_registry_root()
    root.mkdir(parents=True, exist_ok=True)
    payload = dict(index or {})
    payload.setdefault("schema", REGISTRY_INDEX_SCHEMA)
    payload.setdefault("created_at", utc_now_iso())
    payload["updated_at"] = utc_now_iso()
    payload.setdefault("active_model_id", None)
    payload.setdefault("models", [])
    payload.setdefault("meta", {})
    return write_json_file(root / "registry_index.json", payload)


def build_registry_index_entry(
    model_registry_entry: dict,
    artifact_manifest: dict | None = None,
) -> dict:
    model_id = _validate_model_id(str(model_registry_entry.get("model_id") or ""))
    artifact_manifest = artifact_manifest or {}
    return {
        "model_id": model_id,
        "model_name": model_registry_entry.get("model_name"),
        "model_type": model_registry_entry.get("model_type"),
        "provider": model_registry_entry.get("provider"),
        "runtime": model_registry_entry.get("runtime"),
        "status": model_registry_entry.get("status"),
        "version": model_registry_entry.get("version"),
        "feature_schema_id": model_registry_entry.get("feature_schema_id"),
        "dataset_id": model_registry_entry.get("dataset_id"),
        "evaluation_report_id": model_registry_entry.get("evaluation_report_id"),
        "artifact_path": model_registry_entry.get("artifact_path"),
        "binary_created": bool(artifact_manifest.get("binary_created")),
        "created_at": model_registry_entry.get("created_at") or utc_now_iso(),
        "updated_at": model_registry_entry.get("updated_at") or utc_now_iso(),
    }


def upsert_registry_index_entry(
    model_registry_entry: dict,
    artifact_manifest: dict | None = None,
    root_path: Optional[Path] = None,
) -> dict:
    index = load_registry_index(root_path)
    entry = build_registry_index_entry(model_registry_entry, artifact_manifest)
    models = [
        item
        for item in index.get("models", [])
        if item.get("model_id") != entry["model_id"]
    ]
    models.append(entry)
    index["models"] = sorted(models, key=lambda item: str(item.get("model_id")))
    index["updated_at"] = utc_now_iso()
    save_registry_index(index, root_path)
    return index


def save_model_artifacts_preview(
    *,
    model_registry_entry: dict,
    artifact_manifest: dict,
    evaluation_report: dict,
    trainer_run_summary: dict,
    root_path: Optional[Path] = None,
) -> dict:
    model_id = _validate_model_id(str(model_registry_entry.get("model_id") or ""))
    model_dir = get_model_dir(model_id, root_path)
    model_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "model_registry_entry": write_json_file(
            model_dir / "model_registry_entry.json",
            model_registry_entry,
        ),
        "artifact_manifest": write_json_file(
            model_dir / "artifact_manifest.json",
            artifact_manifest,
        ),
        "evaluation_report": write_json_file(
            model_dir / "evaluation_report.json",
            evaluation_report,
        ),
        "trainer_run_summary": write_json_file(
            model_dir / "trainer_run_summary.json",
            trainer_run_summary,
        ),
    }
    upsert_registry_index_entry(model_registry_entry, artifact_manifest, root_path)
    return {
        "schema": PERSISTENCE_RESULT_SCHEMA,
        "model_id": model_id,
        "model_dir": str(model_dir),
        "files": {key: str(path) for key, path in files.items()},
        "registry_index_updated": True,
        "active_model_updated": False,
        "created_at": utc_now_iso(),
    }


def save_model_artifacts_with_model_file_preview(
    *,
    model_registry_entry: dict,
    artifact_manifest: dict,
    evaluation_report: dict,
    trainer_run_summary: dict,
    source_model_path: Path,
    root_path: Optional[Path] = None,
) -> dict:
    """Save model metadata and copy the real prototype text model file."""

    model_id = validate_safe_model_id(str(model_registry_entry.get("model_id") or ""))
    model_file_info = copy_model_file_to_registry(
        source_model_path=source_model_path,
        model_id=model_id,
        root_path=root_path,
        filename="model.txt",
    )
    enriched_manifest = enrich_artifact_manifest_with_registry_model(
        artifact_manifest,
        model_file_info,
    )
    enriched_entry = copy.deepcopy(model_registry_entry or {})
    enriched_entry["artifact_path"] = enriched_manifest.get("artifact_path")
    enriched_entry["checksum"] = enriched_manifest.get("checksum")
    enriched_entry.setdefault("status", "draft")
    if enriched_entry.get("status") == "approved":
        enriched_entry["status"] = "draft"
    notes = list(enriched_entry.get("notes") or [])
    for note in ("not_approved_for_live", "real_prototype_artifact_registered"):
        if note not in notes:
            notes.append(note)
    enriched_entry["notes"] = notes

    enriched_report = copy.deepcopy(evaluation_report or {})
    report_artifact = enriched_report.get("artifact")
    if not isinstance(report_artifact, dict):
        report_artifact = {}
    report_artifact["artifact_path"] = enriched_manifest.get("artifact_path")
    report_artifact["checksum"] = enriched_manifest.get("checksum")
    report_artifact["model_file_size_bytes"] = model_file_info.get("model_file_size_bytes")
    enriched_report["artifact"] = report_artifact
    if enriched_report.get("approval_status") == "approved":
        enriched_report["approval_status"] = "shadow_only"

    enriched_summary = copy.deepcopy(trainer_run_summary or {})
    if isinstance(enriched_summary.get("artifact"), dict):
        enriched_summary["artifact"]["artifact_manifest"] = enriched_manifest
        enriched_summary["artifact"]["model_path"] = enriched_manifest.get("artifact_path")
    enriched_summary["evaluation_report"] = enriched_report
    enriched_summary["model_registry_entry"] = enriched_entry

    consistency = validate_artifact_metadata_consistency(
        artifact_manifest=enriched_manifest,
        evaluation_report=enriched_report,
        model_registry_entry=enriched_entry,
    )

    base_result = save_model_artifacts_preview(
        model_registry_entry=enriched_entry,
        artifact_manifest=enriched_manifest,
        evaluation_report=enriched_report,
        trainer_run_summary=enriched_summary,
        root_path=root_path,
    )
    files = dict(base_result.get("files") or {})
    files["model_file"] = model_file_info.get("registry_model_path")
    return {
        "schema": REAL_ARTIFACT_PERSISTENCE_RESULT_SCHEMA,
        "model_id": model_id,
        "model_dir": base_result.get("model_dir"),
        "model_file": {
            "registry_model_path": model_file_info.get("registry_model_path"),
            "checksum": model_file_info.get("checksum"),
            "model_file_size_bytes": model_file_info.get("model_file_size_bytes"),
        },
        "files": files,
        "registry_index_updated": True,
        "active_model_updated": False,
        "metadata_consistency": consistency,
        "created_at": utc_now_iso(),
    }


def load_model_artifacts_preview(
    model_id: str,
    root_path: Optional[Path] = None,
) -> dict:
    model_dir = get_model_dir(model_id, root_path)
    return {
        "model_registry_entry": read_json_file(model_dir / "model_registry_entry.json") or {},
        "artifact_manifest": read_json_file(model_dir / "artifact_manifest.json") or {},
        "evaluation_report": read_json_file(model_dir / "evaluation_report.json") or {},
        "trainer_run_summary": read_json_file(model_dir / "trainer_run_summary.json") or {},
    }


def set_active_model_preview(
    model_id: str,
    root_path: Optional[Path] = None,
    notes: Optional[list[str]] = None,
) -> dict:
    safe_model_id = _validate_model_id(model_id)
    index = load_registry_index(root_path)
    if safe_model_id not in {item.get("model_id") for item in index.get("models", [])}:
        raise ValueError(f"model_id not found in registry index: {safe_model_id}")
    note_list = list(notes or [])
    for required in ("preview_pointer_only", "not_live_approved"):
        if required not in note_list:
            note_list.append(required)
    active = {
        "schema": ACTIVE_MODEL_SCHEMA,
        "active_model_id": safe_model_id,
        "updated_at": utc_now_iso(),
        "mode": "preview",
        "notes": note_list,
    }
    root = ensure_registry_root(root_path)
    write_json_file(root / "active_model.json", active)
    index["active_model_id"] = safe_model_id
    index["updated_at"] = utc_now_iso()
    save_registry_index(index, root)
    return active


def get_active_model_preview(root_path: Optional[Path] = None) -> dict:
    root = ensure_registry_root(root_path)
    active = read_json_file(root / "active_model.json")
    return active if isinstance(active, dict) else _empty_active_model()


def list_registry_models(root_path: Optional[Path] = None) -> list[dict]:
    index = load_registry_index(root_path)
    models = index.get("models")
    return models if isinstance(models, list) else []


def export_registry_snapshot(
    output_path: Path,
    root_path: Optional[Path] = None,
) -> Path:
    snapshot = {
        "schema": "aits_local_ai_registry_snapshot.v1",
        "created_at": utc_now_iso(),
        "registry_index": load_registry_index(root_path),
        "active_model": get_active_model_preview(root_path),
        "safety": {
            "preview_only": True,
            "router_connected": False,
            "execution_connected": False,
            "model_binary_created": False,
        },
    }
    return write_json_file(output_path, snapshot)


def _empty_registry_index() -> dict:
    now = utc_now_iso()
    return {
        "schema": REGISTRY_INDEX_SCHEMA,
        "created_at": now,
        "updated_at": now,
        "active_model_id": None,
        "models": [],
        "meta": {
            "preview_only": True,
            "not_live_approved": True,
        },
    }


def _empty_active_model() -> dict:
    return {
        "schema": ACTIVE_MODEL_SCHEMA,
        "active_model_id": None,
        "updated_at": utc_now_iso(),
        "mode": "preview",
        "notes": [
            "preview_pointer_only",
            "not_live_approved",
        ],
    }


def _validate_model_id(model_id: str) -> str:
    value = str(model_id or "").strip()
    if not value:
        raise ValueError("model_id is required")
    if "/" in value or "\\" in value or ".." in value:
        raise ValueError("model_id must not contain path traversal characters")
    return value


def _sanitize_payload(value):
    if isinstance(value, dict):
        clean = {}
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if (
                "api_key" in key_text
                or "secret" in key_text
                or "token" in key_text
                or "authorization" in key_text
            ):
                continue
            clean[key] = _sanitize_payload(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


__all__ = [
    "ACTIVE_MODEL_SCHEMA",
    "PERSISTENCE_RESULT_SCHEMA",
    "REAL_ARTIFACT_PERSISTENCE_RESULT_SCHEMA",
    "REGISTRY_INDEX_SCHEMA",
    "build_registry_index_entry",
    "copy_model_file_to_registry",
    "enrich_artifact_manifest_with_registry_model",
    "ensure_registry_root",
    "export_registry_snapshot",
    "get_active_model_preview",
    "get_default_registry_root",
    "get_model_dir",
    "list_registry_models",
    "load_model_artifacts_preview",
    "load_registry_index",
    "read_json_file",
    "save_model_artifacts_preview",
    "save_model_artifacts_with_model_file_preview",
    "save_registry_index",
    "set_active_model_preview",
    "sha256_file",
    "upsert_registry_index_entry",
    "utc_now_iso",
    "validate_artifact_metadata_consistency",
    "validate_safe_model_id",
    "write_json_file",
]
