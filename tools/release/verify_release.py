from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.release_config import FORBIDDEN_MODEL_SUFFIXES, FORBIDDEN_PARTS, REQUIRED_QT_PLUGIN_DIRS, SENSITIVE_NAMES


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(release_dir: Path) -> dict:
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    files = {path.relative_to(release_dir).as_posix(): path for path in release_dir.rglob("*") if path.is_file()}
    sensitive = []
    runtime_data = []
    ollama = []
    user_models = []
    for relative, path in files.items():
        lower_parts = {part.lower() for part in Path(relative).parts}
        lower_name = path.name.lower()
        if lower_name in SENSITIVE_NAMES:
            sensitive.append(relative)
        if lower_parts & FORBIDDEN_PARTS:
            runtime_data.append(relative)
        if "ollama" in lower_name:
            ollama.append(relative)
        if path.suffix.lower() in FORBIDDEN_MODEL_SUFFIXES:
            user_models.append(relative)
    hash_mismatches = []
    for row in manifest.get("files") or []:
        path = files.get(row.get("path"))
        if not path or sha256(path) != row.get("sha256"):
            hash_mismatches.append(row.get("path"))
    required_plugins = {item: (release_dir / item).is_dir() for item in REQUIRED_QT_PLUGIN_DIRS}
    report = {
        "schema": "aits_release_artifact_verification.v1", "release_dir": str(release_dir),
        "executable_exists": (release_dir / "AITS.exe").is_file(), "manifest_ready": bool(manifest),
        "file_hashes_valid": not hash_mismatches, "hash_mismatches": hash_mismatches,
        "secret_pattern_count": len(sensitive), "sensitive_files": sensitive,
        "runtime_data_count": len(runtime_data), "runtime_data_files": runtime_data,
        "ollama_binary_or_model_count": len(ollama), "unapproved_user_model_count": len(user_models),
        "required_qt_plugins": required_plugins, "required_qt_plugins_ready": all(required_plugins.values()),
        "dependency_manifest_ready": (release_dir / "_internal/release/manifests/dependency_manifest.json").is_file(),
        "third_party_license_manifest_ready": (release_dir / "_internal/release/manifests/THIRD_PARTY_LICENSES.txt").is_file(),
        "schema_compatibility_manifest_ready": bool(manifest.get("schema_compatibility")),
        "packaged_app_runtime_executed": False,
    }
    report["pass_status"] = "pass" if all((report["executable_exists"], report["manifest_ready"], report["file_hashes_valid"], report["secret_pattern_count"] == 0, report["runtime_data_count"] == 0, report["ollama_binary_or_model_count"] == 0, report["unapproved_user_model_count"] == 0, report["required_qt_plugins_ready"], report["dependency_manifest_ready"], report["third_party_license_manifest_ready"])) else "fail"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", required=True)
    args = parser.parse_args()
    report = verify(Path(args.release_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
