from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform
import struct
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

from app.version import version_info


RELEASE_MANIFEST_SCHEMA = "aits_release_manifest.v1"
RELEASE_MODEL_SCHEMA = "aits_release_model_bundle.v1"
EXCLUDED_NAMES = {"secrets.json", "secret.bin", ".env", "prefs.json"}
EXCLUDED_PARTS = {"data", "logs", "backups", "archive", "cache", "temp", "__pycache__", ".git", ".venv"}


def _runtime_architecture() -> str:
    machine = platform.machine().strip().lower()
    if machine in {"amd64", "x86_64"}:
        return "x86_64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine:
        return machine
    return "x86_64" if struct.calcsize("P") * 8 == 64 else "x86"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_release_manifest(release_dir: Path, *, repo_root: Path, profile: str,
                           dependency_versions: dict[str, str] | None = None,
                           qt_plugins: Iterable[str] = (), model_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    files = []
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file() or path.name == "release_manifest.json":
            continue
        relative = path.relative_to(release_dir).as_posix()
        files.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    info = version_info()
    return {
        "schema": RELEASE_MANIFEST_SCHEMA, **info, "build_commit": safe_git_commit(repo_root),
        "build_profile": profile, "architecture": _runtime_architecture(),
        "generated_at": datetime.now(timezone.utc).isoformat(), "executable": "AITS.exe",
        "files": files, "total_size": sum(row["size_bytes"] for row in files),
        "dependency_versions": dict(dependency_versions or {}), "qt_plugin_list": sorted(set(qt_plugins)),
        "bundled_model_manifest": dict(model_bundle or {}),
        "schema_compatibility": {"minimum": info["minimum_data_schema_version"], "maximum": info["maximum_supported_data_schema_version"]},
        "excluded_sensitive_patterns": sorted(EXCLUDED_NAMES | EXCLUDED_PARTS),
        "python_build_version": platform.python_version(), "pyinstaller_version": dependency_versions.get("PyInstaller", "") if dependency_versions else "",
        "signature_status": "unsigned_release_candidate", "installer_hash": "", "portable_hash": "",
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def default_release_model_bundle() -> dict[str, Any]:
    return {
        "schema": RELEASE_MODEL_SCHEMA, "bundle_id": "aits-no-bootstrap-model-v1",
        "model_id": None, "model_schema": None, "model_version": None, "calibrator_id": None,
        "supported_tasks": [], "supported_actions": [], "model_hash": "", "artifact_size_mb": 0,
        "cpu_only_supported": True, "gpu_required": False, "external_runtime_required": False,
        "minimum_memory_mb": 0, "package_compatible": True, "license_id": None,
        "approved_for_release": False, "safe_for_live_decision": False,
        "default_authority_level": 0, "blocker": "no_approved_bootstrap_model",
    }
