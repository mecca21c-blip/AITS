from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.aits_release_manifest import build_release_manifest, default_release_model_bundle, write_manifest


def dependency_versions() -> dict[str, str]:
    names = ("PyInstaller", "PySide6", "numpy", "scipy", "pandas", "scikit-learn", "lightgbm", "matplotlib", "mplfinance", "requests", "certifi", "pydantic", "cryptography")
    result = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return result


def generate(release_dir: Path, profile: str) -> dict:
    model_path = ROOT / "release/assets/release_model_bundle.json"
    model = json.loads(model_path.read_text(encoding="utf-8")) if model_path.is_file() else default_release_model_bundle()
    qt_plugins = [path.relative_to(release_dir).as_posix() for path in release_dir.rglob("q*.dll") if "plugins" in path.parts]
    manifest = build_release_manifest(release_dir, repo_root=ROOT, profile=profile, dependency_versions=dependency_versions(), qt_plugins=qt_plugins, model_bundle=model)
    write_manifest(release_dir / "release_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--profile", default="release_candidate")
    args = parser.parse_args()
    manifest = generate(Path(args.release_dir), args.profile)
    print(json.dumps({"manifest": str(Path(args.release_dir) / "release_manifest.json"), "files": len(manifest["files"]), "total_size": manifest["total_size"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
