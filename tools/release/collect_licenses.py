from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path


PACKAGES = ("PyInstaller", "PySide6", "numpy", "scipy", "pandas", "scikit-learn", "lightgbm", "matplotlib", "mplfinance", "requests", "certifi", "pydantic", "cryptography")


def collect(output_dir: Path) -> dict:
    components = []
    notices = ["AITS THIRD-PARTY COMPONENT NOTICES", ""]
    for name in PACKAGES:
        try:
            meta = importlib.metadata.metadata(name)
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        license_name = str(meta.get("License-Expression") or meta.get("License") or "See package metadata").strip()
        if "\n" in license_name or len(license_name) > 200:
            license_name = "See installed package license metadata"
        components.append({"name": name, "version": version, "license": license_name, "homepage": meta.get("Home-page") or ""})
        notices.append(f"{name} {version} — {license_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "aits_release_dependency_manifest.v1", "components": components, "external_llm_runtime_dependency": False, "ollama_dependency": False}
    (output_dir / "dependency_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "THIRD_PARTY_LICENSES.txt").write_text("\n".join(notices) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = collect(Path(args.output_dir))
    print(json.dumps({"components": len(result["components"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
