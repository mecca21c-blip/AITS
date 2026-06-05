"""Local AI model artifact and registry persistence preview.

This module stores trainer skeleton outputs as JSON files under a local preview
registry directory. It does not create model binaries, run training, connect
Router/UI/Execution/Order/Risk Guard, or approve models for live trading.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REGISTRY_INDEX_SCHEMA = "aits_local_ai_registry_index.v1"
ACTIVE_MODEL_SCHEMA = "aits_active_local_ai_model.v1"
PERSISTENCE_RESULT_SCHEMA = "aits_model_artifact_persistence_result.v1"


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
    safe_model_id = _validate_model_id(model_id)
    root = ensure_registry_root(root_path)
    return root / "models" / safe_model_id


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
    "REGISTRY_INDEX_SCHEMA",
    "build_registry_index_entry",
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
    "save_registry_index",
    "set_active_model_preview",
    "upsert_registry_index_entry",
    "utc_now_iso",
    "write_json_file",
]
