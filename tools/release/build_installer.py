from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()
    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    result = {"schema": "aits_installer_build_result.v1", "installer_source": str(ROOT / "release/installer/AITS.iss"), "release_dir": str(Path(args.release_dir)), "installer_build_tool_available": bool(iscc), "installer_build_executed": False, "packaged_app_runtime_executed": False}
    if iscc and args.no_run:
        subprocess.run([iscc, f"/DReleaseDir={Path(args.release_dir).resolve()}", str(ROOT / "release/installer/AITS.iss")], cwd=ROOT, check=True)
        result["installer_build_executed"] = True
    elif not iscc:
        result["blocker"] = "installer_build_tool_unavailable"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
