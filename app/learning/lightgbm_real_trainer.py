"""LightGBM real trainer prototype for AITS Local AI ML Engine.

This module performs small, explicit prototype LightGBM train/predict/save/load
runs from AI-ARCH-10 dataset rows. It is not an operational trainer, does not
read live data automatically, does not connect Router/UI/Execution/Order/Risk
Guard paths, and does not approve models for live trading.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import lightgbm as lgb
import numpy as np

from app.learning.lightgbm_dataset_builder import is_future_or_outcome_key
from app.learning.model_registry_store import save_model_artifacts_preview

REAL_TRAINER_RESULT_SCHEMA = "aits_lightgbm_real_trainer_result.v1"
ARTIFACT_MANIFEST_SCHEMA = "aits_model_artifact_manifest.v1"
EVALUATION_REPORT_SCHEMA = "aits_model_evaluation_report.v1"
DATASET_ROW_SCHEMA = "aits_lightgbm_dataset_row.v1"
FEATURE_SCHEMA_ID = "aits_lightgbm_feature_schema.v1"
TRAINER_NAME = "lightgbm_real_trainer_prototype"
TRAINER_VERSION = "1.0.0"
MODEL_TYPE = "lightgbm_classifier"

SENSITIVE_KEY_PARTS = (
    "api_key",
    "secret",
    "token",
    "authorization",
    "access_key",
    "secret_key",
    "raw_private",
)


def utc_now_iso() -> str:
    """Return a UTC ISO timestamp."""

    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    """Return a compact uuid-based identifier."""

    return f"{prefix}-{uuid4().hex}"


def get_lightgbm_version() -> str | None:
    """Return the imported LightGBM package version."""

    version = getattr(lgb, "__version__", None)
    return str(version) if version is not None else None


def flatten_feature_groups(row: dict) -> dict:
    """Flatten one dataset row's feature groups into primitive columns."""

    flat: dict[str, Any] = {}
    features = row.get("features") if isinstance(row, dict) else None
    if not isinstance(features, dict):
        return flat
    for group_name, group in features.items():
        if not isinstance(group, dict):
            continue
        group_text = str(group_name or "").strip()
        if not group_text:
            continue
        for key, value in group.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            column = f"{group_text}__{key_text}"
            if _is_prohibited_feature_key(column):
                continue
            if isinstance(value, (dict, list, tuple, set)):
                continue
            encoded = encode_feature_value(value)
            if encoded is not None:
                flat[column] = encoded
    return flat


def encode_feature_value(value) -> int | float | str | None:
    """Normalize primitive feature values before numeric matrix conversion."""

    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return None


def fit_category_maps(flat_rows: list[dict]) -> dict:
    """Build per-column string category maps with 0 reserved for unknown."""

    maps: dict[str, dict[str, int]] = {}
    for flat in flat_rows or []:
        if not isinstance(flat, dict):
            continue
        for column, value in flat.items():
            if isinstance(value, str):
                maps.setdefault(column, {"unknown": 0})
                if value not in maps[column]:
                    maps[column][value] = len(maps[column])
    return maps


def transform_features_with_category_maps(
    flat_rows: list[dict],
    category_maps: dict,
) -> tuple[list[list[float]], list[str]]:
    """Convert flat feature dicts to a numeric matrix and stable columns."""

    feature_columns = sorted(
        {
            str(column)
            for flat in flat_rows or []
            if isinstance(flat, dict)
            for column in flat.keys()
            if not _is_prohibited_feature_key(str(column))
        }
    )
    return (
        _matrix_from_flat_rows(flat_rows or [], category_maps or {}, feature_columns),
        feature_columns,
    )


def transform_features_for_inference(
    rows: list[dict],
    category_maps: dict,
    feature_columns: list[str],
) -> list[list[float]]:
    """Build an inference matrix with training-time category maps and columns."""

    flat_rows = [flatten_feature_groups(row) for row in rows or []]
    return _matrix_from_flat_rows(flat_rows, category_maps or {}, feature_columns or [])


def extract_target_values(
    rows: list[dict],
    target_name: str = "classifier_target",
) -> list:
    """Extract target values from dataset rows."""

    labels = []
    for row in rows or []:
        targets = row.get("targets") if isinstance(row, dict) else None
        if not isinstance(targets, dict):
            continue
        value = targets.get(target_name)
        if value is not None:
            labels.append(value)
    return labels


def filter_training_rows(
    rows: list[dict],
    target_name: str = "classifier_target",
) -> list[dict]:
    """Return rows eligible for prototype classifier training."""

    filtered: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("schema") != DATASET_ROW_SCHEMA:
            continue
        quality = row.get("quality")
        targets = row.get("targets")
        if not isinstance(quality, dict) or quality.get("usable_for_training") is not True:
            continue
        if not isinstance(targets, dict) or targets.get(target_name) is None:
            continue
        if not flatten_feature_groups(row):
            continue
        filtered.append(row)
    return filtered


def encode_labels(labels: list) -> tuple[list[int], dict]:
    """Encode classifier labels into integers and return class metadata."""

    classes = sorted({str(label) for label in labels if label is not None})
    if len(classes) < 2:
        raise ValueError("LightGBM classifier prototype requires at least two classes")
    label_to_int = {label: idx for idx, label in enumerate(classes)}
    encoded = [label_to_int[str(label)] for label in labels]
    return encoded, {
        "label_to_int": label_to_int,
        "int_to_label": {idx: label for label, idx in label_to_int.items()},
        "classes": classes,
    }


def train_lightgbm_classifier_prototype(
    rows: list[dict],
    *,
    output_dir: Path,
    target_name: str = "classifier_target",
    num_boost_round: int = 10,
    params: dict | None = None,
) -> dict:
    """Train a small LightGBM classifier prototype and return a result dict."""

    run_id = make_id("lgbm-real-train")
    model_id = make_id("local-ai-lgbm")
    dataset_id = make_id("dataset")
    created_at = utc_now_iso()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model_path = output_path / f"{model_id}.txt"

    training_rows = filter_training_rows(rows or [], target_name=target_name)
    result = _base_result(
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        created_at=created_at,
        rows=rows or [],
        training_rows=training_rows,
        target_name=target_name,
        num_boost_round=num_boost_round,
    )

    try:
        if not training_rows:
            raise ValueError("no usable training rows")

        flat_rows = [flatten_feature_groups(row) for row in training_rows]
        category_maps = fit_category_maps(flat_rows)
        x_matrix, feature_columns = transform_features_with_category_maps(
            flat_rows,
            category_maps,
        )
        raw_labels = extract_target_values(training_rows, target_name)
        y_vector, label_map = encode_labels(raw_labels)
        sample_weight = [
            float(row.get("sample_weight", 1.0) or 1.0) for row in training_rows
        ]
        sample_weight_used = any(weight != 1.0 for weight in sample_weight)

        train_params = {
            "objective": "multiclass",
            "metric": "multi_logloss",
            "verbosity": -1,
            "seed": 42,
            "num_class": len(label_map["classes"]),
            "min_data_in_leaf": 1,
            "min_data_in_bin": 1,
            "force_col_wise": True,
        }
        if params:
            train_params.update(params)
        train_params["num_class"] = len(label_map["classes"])

        dataset = lgb.Dataset(
            np.asarray(x_matrix, dtype=float),
            label=np.asarray(y_vector, dtype=int),
            weight=np.asarray(sample_weight, dtype=float),
            feature_name=feature_columns,
            free_raw_data=False,
        )
        booster = lgb.train(
            train_params,
            dataset,
            num_boost_round=int(num_boost_round or 10),
        )
        probabilities = booster.predict(np.asarray(x_matrix, dtype=float))
        probability_preview = _preview_probabilities(probabilities)
        predicted_indices = _predicted_indices(probabilities)
        predictions = [
            label_map["int_to_label"].get(index, str(index))
            for index in predicted_indices
        ]
        training_accuracy = _accuracy(predictions, [str(label) for label in raw_labels])

        booster.save_model(str(model_path))
        checksum = _sha256_file(model_path)
        dataset_summary = {
            "total_rows": len(rows or []),
            "training_rows": len(training_rows),
            "feature_columns": feature_columns,
            "target_name": target_name,
            "label_classes": label_map["classes"],
            "sample_weight_used": sample_weight_used,
        }
        artifact_manifest = build_real_trainer_artifact_manifest(
            model_id=model_id,
            model_type=MODEL_TYPE,
            feature_schema_id=FEATURE_SCHEMA_ID,
            dataset_summary=dataset_summary,
            model_path=model_path,
            checksum=checksum,
            category_maps=category_maps,
            feature_columns=feature_columns,
            label_map=label_map,
        )
        evaluation_report = build_real_trainer_evaluation_report(
            model_id=model_id,
            dataset_id=dataset_id,
            training_accuracy=training_accuracy,
            sample_count=len(training_rows),
            class_count=len(label_map["classes"]),
            prediction_generated=True,
        )
        registry_entry = build_real_trainer_model_registry_entry(
            model_id=model_id,
            model_name="lightgbm_classifier_prototype",
            model_type=MODEL_TYPE,
            feature_schema_id=FEATURE_SCHEMA_ID,
            dataset_id=dataset_id,
            evaluation_report_id=evaluation_report["evaluation_report_id"],
            artifact_manifest=artifact_manifest,
        )

        result["dataset"] = dataset_summary
        result["training"] = {
            "executed": True,
            "status": "success",
            "error": None,
            "params": train_params,
            "num_boost_round": int(num_boost_round or 10),
        }
        result["prediction"] = {
            "executed": True,
            "sample_count": len(training_rows),
            "prediction_preview": predictions[:10],
            "probability_preview": probability_preview[:10],
        }
        result["artifact"] = {
            "model_file_created": model_path.exists(),
            "model_path": str(model_path),
            "artifact_manifest": artifact_manifest,
        }
        result["evaluation_report"] = evaluation_report
        result["model_registry_entry"] = registry_entry
        result["meta"] = {
            "category_maps": category_maps,
            "label_map": label_map,
            "feature_schema_id": FEATURE_SCHEMA_ID,
            "actual_training_executed": True,
            "model_text_file_created": True,
            "prototype_only": True,
        }
        return result
    except Exception as exc:
        result["training"] = {
            "executed": False,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "params": params or {},
            "num_boost_round": int(num_boost_round or 10),
        }
        result["meta"]["prototype_only"] = True
        return result


def load_lightgbm_model(model_path: Path):
    """Load a LightGBM Booster from a saved text model."""

    return lgb.Booster(model_file=str(Path(model_path)))


def predict_with_loaded_model(
    model_path: Path,
    rows: list[dict],
    category_maps: dict,
    feature_columns: list[str],
) -> list:
    """Load a model and run prediction for smoke verification."""

    booster = load_lightgbm_model(model_path)
    matrix = transform_features_for_inference(rows or [], category_maps, feature_columns)
    predictions = booster.predict(np.asarray(matrix, dtype=float))
    return _to_plain_list(predictions)


def build_real_trainer_artifact_manifest(
    *,
    model_id: str,
    model_type: str,
    feature_schema_id: str,
    dataset_summary: dict,
    model_path: Path,
    checksum: str,
    category_maps: dict,
    feature_columns: list[str],
    label_map: dict,
) -> dict:
    """Build an artifact manifest for the prototype text model."""

    return {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "artifact_id": make_id("artifact"),
        "model_id": model_id,
        "created_at": utc_now_iso(),
        "artifact_type": "prototype_text_model",
        "model_type": model_type,
        "feature_schema_id": feature_schema_id,
        "dataset_summary": dataset_summary,
        "artifact_path": str(model_path),
        "checksum": checksum,
        "binary_created": False,
        "model_file_created": True,
        "text_model_created": True,
        "category_maps": category_maps,
        "feature_columns": feature_columns,
        "label_map": label_map,
        "notes": [
            "prototype_train_only",
            "lightgbm_text_model",
            "not_approved_for_live",
        ],
    }


def build_real_trainer_evaluation_report(
    *,
    model_id: str,
    dataset_id: str,
    training_accuracy: float,
    sample_count: int,
    class_count: int,
    prediction_generated: bool,
) -> dict:
    """Build a small prototype evaluation report."""

    return {
        "schema": EVALUATION_REPORT_SCHEMA,
        "evaluation_report_id": make_id("eval-report"),
        "model_id": model_id,
        "dataset_id": dataset_id,
        "created_at": utc_now_iso(),
        "metrics": {
            "training_accuracy": training_accuracy,
            "sample_count": sample_count,
            "class_count": class_count,
            "prediction_generated": prediction_generated,
            "accuracy": training_accuracy,
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
        "decision_summary": "prototype_train_only_not_live",
        "approval_status": "shadow_only",
        "reviewer": "system",
        "notes": [
            "prototype_smoke_metric_only",
            "not_approved_for_live",
        ],
    }


def build_real_trainer_model_registry_entry(
    *,
    model_id: str,
    model_name: str,
    model_type: str,
    feature_schema_id: str,
    dataset_id: str,
    evaluation_report_id: str,
    artifact_manifest: dict,
) -> dict:
    """Build a Model Registry entry for the prototype model."""

    now = utc_now_iso()
    return {
        "model_id": model_id,
        "model_name": model_name,
        "model_type": model_type,
        "provider": "local_ai",
        "runtime": "lightgbm",
        "base_model": None,
        "version": "0.1.0-prototype",
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "artifact_path": artifact_manifest.get("artifact_path"),
        "checksum": artifact_manifest.get("checksum"),
        "feature_schema_id": feature_schema_id,
        "dataset_id": dataset_id,
        "evaluation_report_id": evaluation_report_id,
        "notes": [
            "prototype_train_only",
            "not_approved_for_live",
            "router_not_connected",
        ],
    }


def export_real_trainer_result_json(result: dict, output_path: Path) -> Path:
    """Export a real trainer prototype result as sanitized JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_export(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def train_and_persist_lightgbm_classifier_prototype(
    rows: list[dict],
    *,
    output_dir: Path,
    registry_root: Path | None = None,
    target_name: str = "classifier_target",
    num_boost_round: int = 10,
) -> dict:
    """Train prototype model and save metadata to registry preview storage."""

    result = train_lightgbm_classifier_prototype(
        rows,
        output_dir=output_dir,
        target_name=target_name,
        num_boost_round=num_boost_round,
    )
    if result.get("training", {}).get("status") != "success":
        return {"result": result, "registry_persistence": None}

    persistence = save_model_artifacts_preview(
        model_registry_entry=result["model_registry_entry"],
        artifact_manifest=result["artifact"]["artifact_manifest"],
        evaluation_report=result["evaluation_report"],
        trainer_run_summary=result,
        root_path=registry_root,
    )
    return {"result": result, "registry_persistence": persistence}


def _base_result(
    *,
    run_id: str,
    model_id: str,
    dataset_id: str,
    created_at: str,
    rows: list[dict],
    training_rows: list[dict],
    target_name: str,
    num_boost_round: int,
) -> dict:
    return {
        "schema": REAL_TRAINER_RESULT_SCHEMA,
        "run_id": run_id,
        "created_at": created_at,
        "mode": "prototype_train",
        "trainer": {
            "trainer_name": TRAINER_NAME,
            "trainer_version": TRAINER_VERSION,
            "lightgbm_version": get_lightgbm_version(),
            "model_type": MODEL_TYPE,
        },
        "dataset": {
            "total_rows": len(rows),
            "training_rows": len(training_rows),
            "feature_columns": [],
            "target_name": target_name,
            "label_classes": [],
            "sample_weight_used": False,
        },
        "training": {
            "executed": False,
            "status": "pending",
            "error": None,
            "params": {},
            "num_boost_round": int(num_boost_round or 10),
        },
        "prediction": {
            "executed": False,
            "sample_count": 0,
            "prediction_preview": [],
            "probability_preview": [],
        },
        "artifact": {
            "model_file_created": False,
            "model_path": None,
            "artifact_manifest": {},
        },
        "evaluation_report": {},
        "model_registry_entry": {
            "model_id": model_id,
            "dataset_id": dataset_id,
        },
        "safety": {
            "live_trading_enabled": False,
            "router_connected": False,
            "execution_connected": False,
            "ui_connected": False,
            "model_auto_approved": False,
        },
        "meta": {
            "category_maps": {},
            "label_map": {},
            "feature_schema_id": FEATURE_SCHEMA_ID,
            "actual_training_executed": False,
            "model_text_file_created": False,
            "prototype_only": True,
        },
    }


def _matrix_from_flat_rows(
    flat_rows: list[dict],
    category_maps: dict,
    feature_columns: list[str],
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for flat in flat_rows or []:
        row_values: list[float] = []
        for column in feature_columns:
            value = flat.get(column) if isinstance(flat, dict) else None
            if isinstance(value, str):
                row_values.append(float(category_maps.get(column, {}).get(value, 0)))
            elif isinstance(value, bool):
                row_values.append(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                row_values.append(float(value))
            else:
                row_values.append(0.0)
        matrix.append(row_values)
    return matrix


def _is_prohibited_feature_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return is_future_or_outcome_key(normalized) or any(
        part in normalized for part in SENSITIVE_KEY_PARTS
    )


def _preview_probabilities(probabilities) -> list:
    plain = _to_plain_list(probabilities)
    if not isinstance(plain, list):
        return []
    if plain and not isinstance(plain[0], list):
        return [[round(float(value), 6) for value in plain]]
    return [
        [round(float(value), 6) for value in row]
        for row in plain
        if isinstance(row, list)
    ]


def _predicted_indices(probabilities) -> list[int]:
    plain = _to_plain_list(probabilities)
    if not isinstance(plain, list):
        return []
    if plain and not isinstance(plain[0], list):
        return [1 if float(value) >= 0.5 else 0 for value in plain]
    indices = []
    for row in plain:
        if not isinstance(row, list) or not row:
            indices.append(0)
            continue
        indices.append(max(range(len(row)), key=lambda idx: row[idx]))
    return indices


def _accuracy(predictions: list[str], labels: list[str]) -> float:
    if not labels:
        return 0.0
    correct = sum(1 for predicted, label in zip(predictions, labels) if predicted == label)
    return round(correct / len(labels), 6)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_plain_list(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, tuple):
        return [_to_plain_list(item) for item in value]
    if isinstance(value, list):
        return [_to_plain_list(item) for item in value]
    return value


def _sanitize_export(value):
    if isinstance(value, dict):
        clean = {}
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                continue
            clean[key] = _sanitize_export(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_export(item) for item in value]
    return value


__all__ = [
    "ARTIFACT_MANIFEST_SCHEMA",
    "DATASET_ROW_SCHEMA",
    "EVALUATION_REPORT_SCHEMA",
    "REAL_TRAINER_RESULT_SCHEMA",
    "build_real_trainer_artifact_manifest",
    "build_real_trainer_evaluation_report",
    "build_real_trainer_model_registry_entry",
    "encode_feature_value",
    "encode_labels",
    "export_real_trainer_result_json",
    "filter_training_rows",
    "fit_category_maps",
    "flatten_feature_groups",
    "get_lightgbm_version",
    "load_lightgbm_model",
    "make_id",
    "predict_with_loaded_model",
    "train_and_persist_lightgbm_classifier_prototype",
    "train_lightgbm_classifier_prototype",
    "transform_features_for_inference",
    "transform_features_with_category_maps",
    "utc_now_iso",
]
