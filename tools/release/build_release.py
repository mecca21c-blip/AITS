from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.collect_licenses import collect
from tools.release.generate_manifest import generate
from tools.release.release_config import BUILD_ROOT, CANONICAL_SPEC, MANIFEST_ROOT, OUTPUT_ROOT


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(profile: str, *, clean: bool, no_run: bool) -> dict:
    if profile not in {"release_candidate", "development", "stable"}:
        raise ValueError("unsupported_release_profile")
    profile_output = OUTPUT_ROOT / profile
    work_dir = BUILD_ROOT / profile
    if clean:
        for target in (profile_output, work_dir):
            if target.exists():
                shutil.rmtree(target)
    profile_output.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    collect(MANIFEST_ROOT)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(profile_output), "--workpath", str(work_dir), str(CANONICAL_SPEC)]
    subprocess.run(command, cwd=ROOT, check=True)
    app_dir = profile_output / "AITS"
    manifest = generate(app_dir, profile)
    portable = profile_output / f"AITS-{profile}-portable.zip"
    with zipfile.ZipFile(portable, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path("AITS") / path.relative_to(app_dir))
        archive.writestr("AITS/portable.flag", "AITS explicit portable profile\n")
    artifacts = {
        "schema": "aits_release_artifacts.v1", "profile": profile,
        "release_dir": str(app_dir), "portable_path": str(portable),
        "portable_sha256": sha256(portable), "installer_path": "",
        "packaged_app_runtime_executed": not no_run,
    }
    (profile_output / "release_artifacts.json").write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
    if not no_run:
        raise RuntimeError("packaged_runtime_execution_not_allowed_by_release_sprint")
    return {**artifacts, "file_count": len(manifest["files"]), "total_size": manifest["total_size"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="release_candidate")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()
    if not args.no_run:
        print("--no-run is required", file=sys.stderr)
        return 2
    result = build(args.profile, clean=args.clean, no_run=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
