"""LightGBM trainer skeleton for AITS Local AI ML Engine.

This module validates preview dataset rows and builds dry-run trainer artifacts.
It does not import LightGBM, add dependencies, train models, write model
binaries, or connect to Router/UI/Execution/Order/Risk Guard paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

TRAINER_RUN_SCHEMA = "aits_lightgbm_trainer_run_summary.v1"
ARTIFACT_MANIFEST_SCHEMA = "aits_model_artifact_manifest.v1"
EVALUATION_REPORT_SCHEMA = "aits_model_evaluation_report.v1"
DATASET_ROW_SCHEMA = "aits_lightgbm_dataset_row.v1"
TRAINER_NAME = "lightgbm_trainer_skeleton"
TRAINER_VERSION = "1.0.0"


def utc_now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""

    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    """Return a compact uuid-based identifier."""

    return f"{prefix}-{uuid4().hex}"


def collect_dataset_columns(rows: list[dict]) -> dict:
    """Collect flat feature/label/target column names from dataset rows."""

    feature_columns: set[str] = set()
    label_columns: set[str] = set()
    target_columns: set[str] = set()
    for row in rows or []:
        features = _dict_at(row, "features")
        for group_name, group in features.items():
            if not isinstance(group, dict):
                continue
            for key in group.keys():
                feature_columns.add(f"{group_name}__{key}")
        for key in _dict_at(row, "labels").keys():
            label_columns.add(f"label__{key}")
        for key in _dict_at(row, "targets").keys():
            target_columns.add(f"target__{key}")
    return {
        "feature_columns": sorted(feature_columns),
        "label_columns": sorted(label_columns),
        "target_columns": sorted(target_columns),
    }


def validate_training_rows(
    rows: list[dict],
    *,
    target_name: str = "classifier_target",
    min_rows: int = 10,
) -> dict:
    """Validate dry-run training readiness without running LightGBM."""

    total_rows = len(rows or [])
    usable_rows = [
        row
        for row in rows or []
        if row.get("schema") == DATASET_ROW_SCHEMA
        and _dict_at(row, "quality").get("usable_for_training") is True
    ]
    target_available_rows = [
        row
        for row in usable_rows
        if _dict_at(row, "targets").get(target_name) is not None
    ]
    columns = collect_dataset_columns(usable_rows)
    has_features = bool(columns["feature_columns"])

    status = "validated"
    reason = None
    valid = True
    if total_rows <= 0:
        status = "rejected"
        reason = "empty_dataset"
        valid = False
    elif not usable_rows:
        status = "rejected"
        reason = "no_training_usable_rows"
        valid = False
    elif not has_features:
        status = "rejected"
        reason = "missing_feature_columns"
        valid = False
    elif not target_available_rows:
        status = "rejected"
        reason = "missing_target"
        valid = False
    elif len(usable_rows) < int(min_rows or 1):
        status = "dry_run_only"
        reason = "below_min_rows"
        valid = False

    return {
        "valid": valid,
        "status": status,
        "reason": reason,
        "total_rows": total_rows,
        "training_usable_rows": len(usable_rows),
        "target_available_rows": len(target_available_rows),
    }


def build_artifact_manifest(
    *,
    model_id: str,
    model_type: str,
    feature_schema_id: str,
    dataset_summary: dict,
) -> dict:
    """Build a dry-run artifact manifest without creating model binaries."""

    return {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "artifact_id": make_id("artifact"),
        "model_id": model_id,
        "created_at": utc_now_iso(),
        "artifact_type": "dry_run_manifest",
        "model_type": model_type,
        "feature_schema_id": feature_schema_id,
        "dataset_summary": dataset_summary,
        "artifact_path": None,
        "checksum": None,
        "binary_created": False,
        "notes": [
            "dry_run_manifest_only",
            "no_model_binary_created",
            "lightgbm_dependency_not_required",
        ],
    }


def build_evaluation_report_skeleton(
    *,
    model_id: str,
    dataset_id: str,
) -> dict:
    """Build an evaluation report shell compatible with Model Registry docs."""

    return {
        "schema": EVALUATION_REPORT_SCHEMA,
        "evaluation_report_id": make_id("eval-report"),
        "model_id": model_id,
        "dataset_id": dataset_id,
        "created_at": utc_now_iso(),
        "metrics": {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "pnl_proxy": None,
            "drawdown_proxy": None,
            "false_buy_rate": None,
            "false_sell_rate": None,
            "missed_opportunity_rate": None,
        },
        "benchmark_model_id": None,
        "evaluation_period": None,
        "decision_summary": "dry_run_only_no_training_executed",
        "approval_status": "shadow_only",
        "reviewer": "system",
        "notes": [
            "trainer_skeleton_only",
            "metrics_not_computed",
            "not_approved_for_live",
        ],
    }


def build_model_registry_entry_skeleton(
    *,
    model_id: str,
    model_name: str,
    model_type: str,
    feature_schema_id: str,
    dataset_id: str,
    evaluation_report_id: str,
    artifact_manifest: dict,
) -> dict:
    """Build a draft Local AI Model Registry entry."""

    now = utc_now_iso()
    return {
        "model_id": model_id,
        "model_name": model_name,
        "model_type": model_type,
        "provider": "local_ai",
        "runtime": "lightgbm",
        "base_model": None,
        "version": "0.0.0-dry-run",
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "artifact_path": artifact_manifest.get("artifact_path"),
        "checksum": artifact_manifest.get("checksum"),
        "feature_schema_id": feature_schema_id,
        "dataset_id": dataset_id,
        "evaluation_report_id": evaluation_report_id,
        "notes": [
            "dry_run_trainer_skeleton_only",
            "no_model_binary_created",
            "not_approved_for_live",
        ],
    }


def dry_run_lightgbm_training_plan(
    rows: list[dict],
    *,
    model_type: str = "lightgbm_classifier",
    target_name: str = "classifier_target",
    feature_schema_id: str = "aits_lightgbm_feature_schema.v1",
    dataset_id: str | None = None,
    min_rows: int = 10,
) -> dict:
    """Build a dry-run trainer summary without training a model."""

    run_id = make_id("lgbm-train-dryrun")
    model_id = make_id("local-ai-lgbm")
    dataset_id = dataset_id or make_id("dataset")
    columns = collect_dataset_columns(rows or [])
    validation = validate_training_rows(
        rows or [],
        target_name=target_name,
        min_rows=min_rows,
    )
    dataset_summary = {
        "total_rows": validation["total_rows"],
        "training_usable_rows": validation["training_usable_rows"],
        "feature_columns": columns["feature_columns"],
        "label_columns": columns["label_columns"],
        "target_columns": columns["target_columns"],
        "sample_weight_available": any(
            row.get("sample_weight") is not None for row in rows or []
        ),
    }
    artifact_manifest = build_artifact_manifest(
        model_id=model_id,
        model_type=model_type,
        feature_schema_id=feature_schema_id,
        dataset_summary=dataset_summary,
    )
    evaluation_report = build_evaluation_report_skeleton(
        model_id=model_id,
        dataset_id=dataset_id,
    )
    registry_entry = build_model_registry_entry_skeleton(
        model_id=model_id,
        model_name=f"{model_type}_dry_run",
        model_type=model_type,
        feature_schema_id=feature_schema_id,
        dataset_id=dataset_id,
        evaluation_report_id=evaluation_report["evaluation_report_id"],
        artifact_manifest=artifact_manifest,
    )
    return {
        "schema": TRAINER_RUN_SCHEMA,
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "mode": "dry_run",
        "trainer": {
            "trainer_name": TRAINER_NAME,
            "trainer_version": TRAINER_VERSION,
            "dependency": {
                "lightgbm_required": False,
                "lightgbm_available": False,
                "dependency_added": False,
            },
        },
        "dataset": dataset_summary,
        "training_plan": {
            "model_type": model_type,
            "target_name": target_name,
            "feature_schema_id": feature_schema_id,
            "status": validation["status"],
            "rejected_reason": validation["reason"],
        },
        "artifact": {
            "artifact_created": False,
            "artifact_manifest": artifact_manifest,
        },
        "evaluation_report": evaluation_report,
        "model_registry_entry": registry_entry,
        "safety": {
            "live_trading_enabled": False,
            "router_connected": False,
            "execution_connected": False,
            "model_auto_approved": False,
        },
        "meta": {
            "validation": validation,
            "actual_training_executed": False,
            "model_binary_created": False,
        },
    }


def export_trainer_run_summary_json(summary: dict, output_path: Path) -> Path:
    """Export trainer dry-run summary as JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_export(summary), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_and_export_trainer_dry_run(
    rows: list[dict],
    output_path: Path,
    *,
    model_type: str = "lightgbm_classifier",
    target_name: str = "classifier_target",
    feature_schema_id: str = "aits_lightgbm_feature_schema.v1",
    dataset_id: str | None = None,
    min_rows: int = 10,
) -> dict:
    """Build and export a trainer dry-run summary."""

    summary = dry_run_lightgbm_training_plan(
        rows,
        model_type=model_type,
        target_name=target_name,
        feature_schema_id=feature_schema_id,
        dataset_id=dataset_id,
        min_rows=min_rows,
    )
    path = export_trainer_run_summary_json(summary, output_path)
    return {"summary": summary, "json_path": str(path)}


def _dict_at(row: dict, key: str) -> dict:
    value = row.get(key) if isinstance(row, dict) else None
    return value if isinstance(value, dict) else {}


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
    "ARTIFACT_MANIFEST_SCHEMA",
    "EVALUATION_REPORT_SCHEMA",
    "TRAINER_RUN_SCHEMA",
    "build_and_export_trainer_dry_run",
    "build_artifact_manifest",
    "build_evaluation_report_skeleton",
    "build_model_registry_entry_skeleton",
    "collect_dataset_columns",
    "dry_run_lightgbm_training_plan",
    "export_trainer_run_summary_json",
    "make_id",
    "utc_now_iso",
    "validate_training_rows",
]
