"""LightGBM dependency gate for AITS Local AI.

This module checks whether LightGBM is importable and builds a dependency gate
report. It does not install packages, modify requirements, train models, create
model binaries, or connect to Router/UI/Execution/Order/Risk Guard paths.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DEPENDENCY_GATE_SCHEMA = "aits_lightgbm_dependency_gate.v1"
PACKAGE_NAME = "lightgbm"


def utc_now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""

    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    """Return a uuid-based gate identifier."""

    return f"{prefix}-{uuid4().hex}"


def check_lightgbm_import() -> dict:
    """Check LightGBM availability without installing or requiring it."""

    result = {
        "package_name": PACKAGE_NAME,
        "required_for_real_trainer": True,
        "installed": False,
        "importable": False,
        "version": None,
        "import_error": None,
    }
    try:
        spec = importlib.util.find_spec(PACKAGE_NAME)
        result["installed"] = spec is not None
        if spec is None:
            return result
        module = importlib.import_module(PACKAGE_NAME)
        result["importable"] = True
        result["version"] = str(getattr(module, "__version__", "unknown"))
    except Exception as exc:
        result["import_error"] = f"{type(exc).__name__}: {exc}"
    return result


def collect_environment_info() -> dict:
    """Collect compact environment information for dependency review."""

    system = platform.system()
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "executable": sys.executable,
        "is_windows": system.lower() == "windows",
        "is_packaged": bool(getattr(sys, "frozen", False)),
    }


def assess_packaging_risk(dependency: dict, environment: dict) -> dict:
    """Assess packaging risk conservatively for a future real trainer."""

    notes = [
        "LightGBM may require wheel/native binary compatibility checks",
        "PyInstaller packaging must be validated separately",
        "Do not enable real trainer until dependency gate is reviewed",
    ]
    pyinstaller_risk = "unknown"
    windows_wheel_risk = "unknown"

    if dependency.get("importable"):
        pyinstaller_risk = "medium" if environment.get("is_windows") else "low"
        windows_wheel_risk = "medium" if environment.get("is_windows") else "low"
    if environment.get("is_packaged"):
        pyinstaller_risk = "high"
        notes.append("Packaged runtime detected; bundled native libraries need validation")
    if not dependency.get("installed"):
        notes.append("LightGBM is not installed; continue with dry-run trainer skeleton")

    return {
        "pyinstaller_risk_level": pyinstaller_risk,
        "windows_wheel_risk": windows_wheel_risk,
        "notes": notes,
    }


def build_fallback_policy(dependency: dict) -> dict:
    """Build the safe fallback policy for missing or present dependency."""

    return {
        "fallback_available": True,
        "fallback_mode": "dry_run_trainer_skeleton",
        "real_training_enabled": False,
        "trainer_skeleton_available": True,
        "dependency_required_before_real_training": True,
    }


def evaluate_dependency_readiness(
    dependency: dict,
    packaging_risk: dict,
    fallback_policy: dict,
) -> dict:
    """Evaluate whether a future real trainer prototype can be attempted."""

    if dependency.get("importable"):
        return {
            "real_trainer_prototype_allowed": True,
            "dependency_action_required": False,
            "recommended_next_action": "review_packaging_risk_before_real_trainer",
        }
    return {
        "real_trainer_prototype_allowed": False,
        "dependency_action_required": True,
        "recommended_next_action": "install_or_add_lightgbm_in_controlled_goal",
    }


def build_lightgbm_dependency_gate_report() -> dict:
    """Build the full LightGBM dependency gate report."""

    dependency = check_lightgbm_import()
    environment = collect_environment_info()
    packaging_risk = assess_packaging_risk(dependency, environment)
    fallback_policy = build_fallback_policy(dependency)
    readiness = evaluate_dependency_readiness(
        dependency,
        packaging_risk,
        fallback_policy,
    )
    return {
        "schema": DEPENDENCY_GATE_SCHEMA,
        "gate_id": make_id("lightgbm-dependency-gate"),
        "created_at": utc_now_iso(),
        "dependency": dependency,
        "environment": environment,
        "packaging_risk": packaging_risk,
        "fallback_policy": fallback_policy,
        "readiness": readiness,
        "safety": {
            "requirements_modified": False,
            "pip_install_executed": False,
            "training_executed": False,
            "model_binary_created": False,
            "router_connected": False,
            "execution_connected": False,
            "ui_connected": False,
        },
        "meta": {
            "report_only": True,
            "dependency_installed_by_gate": False,
            "real_trainer_connected": False,
        },
    }


def export_dependency_gate_report_json(report: dict, output_path: Path) -> Path:
    """Export dependency gate report as JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_export(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_and_export_dependency_gate_report(output_path: Path) -> dict:
    """Build and export a dependency gate report."""

    report = build_lightgbm_dependency_gate_report()
    path = export_dependency_gate_report_json(report, output_path)
    return {"report": report, "json_path": str(path)}


def _sanitize_export(value):
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
            clean[key] = _sanitize_export(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_export(item) for item in value]
    return value


__all__ = [
    "DEPENDENCY_GATE_SCHEMA",
    "assess_packaging_risk",
    "build_and_export_dependency_gate_report",
    "build_fallback_policy",
    "build_lightgbm_dependency_gate_report",
    "check_lightgbm_import",
    "collect_environment_info",
    "evaluate_dependency_readiness",
    "export_dependency_gate_report_json",
    "make_id",
    "utc_now_iso",
]
