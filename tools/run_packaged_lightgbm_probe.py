"""Standalone runner for the AITS packaged LightGBM probe.

This entrypoint is for PyInstaller dependency verification only. It does not
import the app GUI, Router, Execution, Order, Risk Guard, or runtime loop.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_report(exc: BaseException) -> dict:
    return {
        "schema": "aits_packaged_lightgbm_probe.v1",
        "created_at": _utc_now_iso(),
        "environment": {
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "python_version": sys.version,
            "platform": None,
        },
        "imports": {
            "lightgbm": {"ok": False, "version": None, "error": None},
            "scipy": {"ok": False, "version": None, "error": None},
        },
        "dependency_gate": {
            "ok": False,
            "importable": False,
            "version": None,
            "error": None,
        },
        "real_trainer_smoke": {
            "ok": False,
            "train_status": None,
            "model_file_created": False,
            "prediction_executed": False,
            "error": f"{type(exc).__name__}: {exc}",
        },
        "safety": {
            "router_connected": False,
            "execution_connected": False,
            "ui_connected": False,
            "training_scope": "tiny_probe_only",
            "model_auto_approved": False,
        },
        "runner_error": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        },
    }


def main() -> int:
    try:
        from app.learning.packaged_lightgbm_probe import run_packaged_lightgbm_probe

        report = run_packaged_lightgbm_probe()
        _fill_packaged_metadata_versions(report)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps(_error_report(exc), ensure_ascii=False, indent=2, sort_keys=True))
        return 1


def _fill_packaged_metadata_versions(report: dict) -> None:
    for package_name in ("lightgbm", "scipy"):
        detected_version = _package_metadata_version(package_name)
        package_report = report.get("imports", {}).get(package_name, {})
        if detected_version and not package_report.get("version"):
            package_report["version"] = detected_version
    lightgbm_version = report.get("imports", {}).get("lightgbm", {}).get("version")
    gate = report.get("dependency_gate", {})
    if lightgbm_version and gate.get("version") in (None, "", "unknown"):
        gate["version"] = lightgbm_version


def _package_metadata_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
