from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import logging
import math
from pathlib import Path
import pickle
import re
import time
from typing import Any, Optional

from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import (
    atomic_write_bytes,
    atomic_write_json,
    read_json_dict,
)


class AITSMeanBaselineRegressor:
    """Small deterministic baseline trained only from observed target values."""

    model_type = "mean_baseline_regressor"

    def __init__(self) -> None:
        self.mean_: Optional[float] = None
        self.training_count_: int = 0

    def fit(self, values: list[float]) -> "AITSMeanBaselineRegressor":
        clean = [float(value) for value in values if math.isfinite(float(value))]
        if not clean:
            raise ValueError("no_target_values")
        self.mean_ = sum(clean) / len(clean)
        self.training_count_ = len(clean)
        return self

    def predict(self, count: int = 1) -> list[float]:
        if self.mean_ is None:
            raise RuntimeError("model_not_trained")
        return [float(self.mean_)] * max(0, int(count))


class AITSModeBaselineClassifier:
    """Observed-label baseline used only when real action labels are available."""

    model_type = "mode_baseline_classifier"

    def __init__(self) -> None:
        self.label_: Optional[str] = None
        self.training_count_: int = 0
        self.label_counts_: dict[str, int] = {}

    def fit(self, values: list[str]) -> "AITSModeBaselineClassifier":
        clean = [str(value).strip().lower() for value in values if str(value).strip()]
        if not clean:
            raise ValueError("no_action_labels")
        counts = Counter(clean)
        self.label_ = sorted(counts, key=lambda label: (-counts[label], label))[0]
        self.training_count_ = len(clean)
        self.label_counts_ = dict(counts)
        return self

    def predict(self, count: int = 1) -> list[str]:
        if not self.label_:
            raise RuntimeError("model_not_trained")
        return [self.label_] * max(0, int(count))


class AITSLocalModelTrainingPipeline:
    """Offline baseline trainer for curated LOCAL feature records."""

    FEATURE_SCHEMA = "aits_local_training_feature_record.v1"
    TRAINING_SCHEMA = "aits_local_model_training_run.v1"
    VALID_SPLITS = {"train", "validation", "holdout"}
    VALID_ACTIONS = {"wait", "hold", "buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
    TARGETS = ("action_quality_score", "outcome_score", "provider_value_score", "risk_adjusted_score")
    MIN_TRAINING_RECORDS = 10

    def __init__(
        self,
        training_root: Path | str = Path("data") / "ai_decision_training",
        model_root: Path | str = Path("data") / "local_models",
    ) -> None:
        self.training_root = Path(training_root)
        self.feature_path = self.training_root / "local_training_features.jsonl"
        self.feature_summary_path = self.training_root / "local_training_feature_summary.json"
        self.model_root = Path(model_root)
        self.registry = AITSLocalModelRegistry(self.model_root)

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _stable_hash(value: Any) -> str:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _read_json(path: Path) -> dict:
        return read_json_dict(path)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        atomic_write_json(path, value)

    @staticmethod
    def _write_pickle_atomic(path: Path, value: Any) -> None:
        from io import BytesIO

        payload = BytesIO()
        pickle.dump(value, payload, protocol=pickle.HIGHEST_PROTOCOL)
        atomic_write_bytes(path, payload.getvalue())

    @classmethod
    def _record_exclusions(cls, row: dict) -> list[str]:
        reasons: list[str] = []
        if str(row.get("schema") or "") != cls.FEATURE_SCHEMA:
            reasons.append("invalid_schema")
        if not row.get("safe_for_model_training"):
            reasons.append("unsafe_feature_record")
        if row.get("exclusion_reasons"):
            reasons.append("feature_record_has_exclusions")
        if str(row.get("split") or "") not in cls.VALID_SPLITS:
            reasons.append("invalid_or_unsplit_record")
        if str(row.get("feature_quality_grade") or "").upper() == "F":
            reasons.append("feature_quality_too_low")
        if not isinstance(row.get("feature_vector"), dict) or not row.get("feature_vector"):
            reasons.append("missing_feature_vector")
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        if str(labels.get("action_label") or row.get("action") or "").lower() not in cls.VALID_ACTIONS:
            reasons.append("missing_or_invalid_action_label")
        targets = row.get("outcome_targets") if isinstance(row.get("outcome_targets"), dict) else {}
        if not any(cls._number(targets.get(target)) is not None for target in cls.TARGETS):
            reasons.append("missing_valid_outcome_target")
        return sorted(set(reasons))

    def load_training_data(self) -> dict:
        summary = self._read_json(self.feature_summary_path)
        rows: list[dict] = []
        exclusions: Counter = Counter()
        source_count = 0
        corrupted = 0
        raw_text = ""
        seen: set[str] = set()
        if self.feature_path.exists():
            with self.feature_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    raw = line.strip()
                    if not raw:
                        continue
                    source_count += 1
                    raw_text += raw[-20_000:] + "\n"
                    try:
                        row = json.loads(raw)
                    except Exception:
                        corrupted += 1
                        exclusions["corrupted_line"] += 1
                        continue
                    if not isinstance(row, dict):
                        corrupted += 1
                        exclusions["corrupted_line"] += 1
                        continue
                    record_id = str(row.get("feature_record_id") or "")
                    if not record_id or record_id in seen:
                        exclusions["duplicate_or_missing_feature_record_id"] += 1
                        continue
                    seen.add(record_id)
                    reasons = self._record_exclusions(row)
                    if reasons:
                        exclusions.update(reasons)
                        continue
                    rows.append(row)
        secret_leak = bool(
            summary.get("raw_secret_leak_detected")
            or re.search(r"(?:api[_-]?key|authorization|secret)[\"' :=]+[A-Za-z0-9_\-]{12,}", raw_text, re.IGNORECASE)
        )
        prompt_leak = bool(
            summary.get("raw_prompt_leak_detected")
            or re.search(r'"(?:raw_prompt|prompt_body|request_body)"\s*:', raw_text, re.IGNORECASE)
        )
        fabricated_marker = bool(
            summary.get("fake_feature_detected")
            or re.search(r'"(?:fake|fabricated|synthetic)_?feature"\s*:\s*true', raw_text, re.IGNORECASE)
        )
        if secret_leak or prompt_leak or fabricated_marker:
            rows = []
            if secret_leak:
                exclusions["raw_secret_leak_detected"] += 1
            if prompt_leak:
                exclusions["raw_prompt_leak_detected"] += 1
            if fabricated_marker:
                exclusions["fabricated_feature_detected"] += 1
        data_empty = source_count == 0
        insufficient = source_count > 0 and len(rows) < self.MIN_TRAINING_RECORDS
        return {
            "records": rows,
            "feature_summary": summary,
            "training_source_records_count": source_count,
            "training_usable_records_count": len(rows),
            "training_excluded_records_count": max(0, source_count - len(rows)),
            "training_data_loaded": self.feature_path.exists() and self.feature_summary_path.exists(),
            "training_data_empty": data_empty,
            "training_data_insufficient": insufficient,
            "training_loader_blocker": (
                "raw_source_safety_violation" if secret_leak or prompt_leak or fabricated_marker
                else "no_usable_training_records" if not rows
                else "insufficient_training_records" if insufficient
                else ""
            ),
            "exclusion_reason_counts": dict(sorted(exclusions.items())),
            "corrupted_line_count": corrupted,
            "raw_secret_leak_detected": secret_leak,
            "raw_prompt_leak_detected": prompt_leak,
            "fake_training_data_created": False,
            "fake_feature_detected": fabricated_marker,
        }

    @staticmethod
    def _flatten(value: dict, prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, dict):
                result.update(AITSLocalModelTrainingPipeline._flatten(item, path))
            elif isinstance(item, (str, int, float, bool)) or item is None:
                result[path] = item
        return result

    def build_feature_matrix(self, records: list[dict]) -> dict:
        flattened = [self._flatten(dict(row.get("feature_vector") or {})) for row in records]
        columns = sorted({key for row in flattened for key in row})
        feature_types: dict[str, str] = {}
        encoding_map: dict[str, dict[str, int]] = {}
        numeric_count = categorical_count = boolean_count = missing_count = 0
        for column in columns:
            values = [row.get(column) for row in flattened if row.get(column) is not None]
            if values and all(isinstance(value, bool) for value in values):
                feature_types[column] = "boolean"
                boolean_count += 1
            elif values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                feature_types[column] = "numeric"
                numeric_count += 1
            else:
                feature_types[column] = "categorical"
                categories = sorted({str(value) for value in values})
                encoding_map[column] = {category: index + 1 for index, category in enumerate(categories)}
                categorical_count += 1
            missing_count += sum(row.get(column) is None for row in flattened)
        matrix: list[list[float]] = []
        for row in flattened:
            vector: list[float] = []
            for column in columns:
                value = row.get(column)
                kind = feature_types[column]
                if kind == "numeric":
                    vector.append(float(value) if self._number(value) is not None else 0.0)
                elif kind == "boolean":
                    vector.append(1.0 if value is True else 0.0)
                else:
                    vector.append(float(encoding_map[column].get(str(value), 0)) if value is not None else 0.0)
            matrix.append(vector)
        return {
            "matrix": matrix,
            "feature_columns": columns,
            "feature_types": feature_types,
            "feature_encoding_map": encoding_map,
            "missing_value_policy": {"numeric": 0.0, "boolean": 0.0, "categorical_unknown": 0},
            "feature_columns_count": len(columns),
            "numeric_features_count": numeric_count,
            "categorical_features_count": categorical_count,
            "boolean_features_count": boolean_count,
            "missing_features_count": missing_count,
            "feature_encoding_ready": True,
            "feature_matrix_builder_ready": True,
            "feature_matrix_blocker": "" if columns else "no_feature_columns",
        }

    def build_labels(self, records: list[dict]) -> dict:
        targets: dict[str, list[Optional[float]]] = {target: [] for target in self.TARGETS}
        missing = 0
        for row in records:
            values = dict(row.get("outcome_targets") or {})
            for target in self.TARGETS:
                number = self._number(values.get(target))
                targets[target].append(number)
                missing += int(number is None)
        ready = {target: any(value is not None for value in values) for target, values in targets.items()}
        action_labels = [
            str((row.get("labels") or {}).get("recommended_action_label") or row.get("final_action") or "").lower()
            for row in records
        ]
        action_labels = [value for value in action_labels if value in self.VALID_ACTIONS]
        return {
            "targets": targets,
            "recommended_action_labels": action_labels,
            "label_builder_ready": True,
            "action_quality_target_ready": ready["action_quality_score"],
            "outcome_score_target_ready": ready["outcome_score"],
            "provider_value_target_ready": ready["provider_value_score"],
            "label_missing_count": missing,
            "label_blocker": "" if any(ready.values()) else "no_trainable_targets",
        }

    @staticmethod
    def _regression_metrics(actual: list[float], predicted: list[float]) -> dict:
        if not actual or len(actual) != len(predicted):
            return {"mae": None, "rmse": None, "r2": None, "mean_target": None, "prediction_mean": None}
        errors = [prediction - target for target, prediction in zip(actual, predicted)]
        mae = sum(abs(error) for error in errors) / len(errors)
        rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
        mean_target = sum(actual) / len(actual)
        prediction_mean = sum(predicted) / len(predicted)
        denominator = sum((target - mean_target) ** 2 for target in actual)
        r2 = 1.0 - sum(error * error for error in errors) / denominator if denominator > 0.0 else None
        return {
            "mae": round(mae, 8),
            "rmse": round(rmse, 8),
            "r2": round(r2, 8) if r2 is not None else None,
            "mean_target": round(mean_target, 8),
            "prediction_mean": round(prediction_mean, 8),
        }

    def _evaluate(self, models: dict[str, AITSMeanBaselineRegressor], records: list[dict], matrix: dict) -> dict:
        validation = [row for row in records if row.get("split") == "validation"]
        holdout = [row for row in records if row.get("split") == "holdout"]
        metrics: dict[str, dict] = {}
        if validation:
            labels = self.build_labels(validation)["targets"]
            for target, model in models.items():
                if target not in labels:
                    continue
                actual = [value for value in labels[target] if value is not None]
                metrics[target] = self._regression_metrics(actual, model.predict(len(actual)))
        return {
            "schema": "aits_local_model_metrics.v1",
            "metrics_status": "evaluated" if validation and metrics else "insufficient_data",
            "targets": metrics,
            "train_count": sum(row.get("split") == "train" for row in records),
            "validation_count": len(validation),
            "holdout_count": len(holdout),
            "feature_count": int(matrix.get("feature_columns_count") or 0),
            "target_distribution": {
                target: {
                    "count": model.training_count_,
                    "mean": getattr(model, "mean_", None),
                    "label_counts": getattr(model, "label_counts_", None),
                }
                for target, model in models.items()
            },
            "data_quality_summary": dict(Counter(str(row.get("feature_quality_grade") or "") for row in records)),
            "warnings": [] if validation else ["validation_records_unavailable"],
        }

    def _model_card(self, metadata: dict, metrics: dict) -> str:
        return "\n".join(
            [
                "# AITS LOCAL Baseline Model Card",
                "",
                f"- Model ID: `{metadata.get('model_id')}`",
                f"- Model type: `{metadata.get('model_type')}`",
                f"- Targets: `{', '.join(metadata.get('targets') or [])}`",
                f"- Training records: `{metadata.get('train_count')}`",
                f"- Validation records: `{metadata.get('validation_count')}`",
                f"- Metrics status: `{metrics.get('metrics_status')}`",
                "- Intended use: LOCAL provider evaluation with registry-controlled activation.",
                "- Live decision use: disabled by default and requires both registry approval flags.",
                "- Order generation: not supported.",
            ]
        ) + "\n"

    def run_training(self, *, calibration_persist: bool = False) -> dict:
        started_at = time.time()
        model_id = f"local_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        loaded = self.load_training_data()
        records = list(loaded["records"])
        source_summary = dict(loaded.get("feature_summary") or {})
        source_hash = self._stable_hash({key: value for key, value in source_summary.items() if key != "last_feature_built_at"})
        train_records = [row for row in records if row.get("split") == "train"]
        validation_records = [row for row in records if row.get("split") == "validation"]
        matrix = self.build_feature_matrix(records)
        labels = self.build_labels(records)
        no_data = bool(loaded["training_data_empty"])
        insufficient = bool(not no_data and len(train_records) < self.MIN_TRAINING_RECORDS)
        training_attempted = False
        training_skipped = no_data or insufficient or not matrix["feature_columns"] or bool(labels["label_blocker"])
        skip_reason = (
            "no_usable_training_records" if no_data or not records
            else "insufficient_training_records" if insufficient
            else matrix["feature_matrix_blocker"] if not matrix["feature_columns"]
            else labels["label_blocker"]
        ) if training_skipped else ""
        models: dict[str, Any] = {}
        metrics: dict = {
            "schema": "aits_local_model_metrics.v1",
            "metrics_status": "no_data" if no_data else "insufficient_data",
            "targets": {},
            "train_count": len(train_records),
            "validation_count": len(validation_records),
            "holdout_count": sum(row.get("split") == "holdout" for row in records),
            "feature_count": int(matrix.get("feature_columns_count") or 0),
            "target_distribution": {},
            "data_quality_summary": dict(Counter(str(row.get("feature_quality_grade") or "") for row in records)),
            "warnings": [skip_reason] if skip_reason else [],
        }
        artifact_path = ""
        model_card_created = False
        if not training_skipped:
            training_attempted = True
            train_labels = self.build_labels(train_records)["targets"]
            for target in self.TARGETS:
                values = [value for value in train_labels[target] if value is not None]
                if values:
                    models[target] = AITSMeanBaselineRegressor().fit(values)
            action_labels = list(self.build_labels(train_records).get("recommended_action_labels") or [])
            if action_labels:
                models["recommended_action_label"] = AITSModeBaselineClassifier().fit(action_labels)
            if not models:
                training_skipped = True
                skip_reason = "no_trainable_targets"
            else:
                artifact_dir = self.model_root / model_id
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = str(artifact_dir)
                bundle = {
                    "schema": "aits_local_model_bundle.v1",
                    "models": models,
                    "feature_columns": matrix["feature_columns"],
                    "feature_types": matrix["feature_types"],
                    "encoding_map": matrix["feature_encoding_map"],
                    "missing_value_policy": matrix["missing_value_policy"],
                    "safe_for_live_decision": False,
                    "live_decision_enabled": False,
                }
                self._write_pickle_atomic(artifact_dir / "model.pkl", bundle)
                self._write_json_atomic(artifact_dir / "feature_columns.json", {"feature_columns": matrix["feature_columns"], "feature_types": matrix["feature_types"]})
                self._write_json_atomic(artifact_dir / "encoding_map.json", matrix["feature_encoding_map"])
                self._write_json_atomic(artifact_dir / "training_config.json", {"trainer": "mean_baseline_regressor", "minimum_training_records": self.MIN_TRAINING_RECORDS, "live_decision_enabled": False})
                metrics = self._evaluate(models, records, matrix)
                self._write_json_atomic(artifact_dir / "metrics.json", metrics)
                self._write_json_atomic(artifact_dir / "dataset_summary.json", source_summary)
                model_card = self._model_card(
                    {"model_id": model_id, "model_type": "mean_baseline_regressor", "targets": sorted(models), "train_count": len(train_records), "validation_count": len(validation_records)},
                    metrics,
                )
                (artifact_dir / "model_card.md").write_text(model_card, encoding="utf-8")
                model_card_created = True
        trained = bool(models and not training_skipped)
        training_status = "trained" if trained else ("no_data" if no_data else "insufficient_data")
        previous_latest = self.registry.load_latest_training_attempt()
        if (
            not trained
            and previous_latest.get("source_feature_summary_hash") == source_hash
            and previous_latest.get("training_status") == training_status
            and previous_latest.get("model_id")
        ):
            model_id = str(previous_latest["model_id"])
        metadata = {
            "registry_schema": AITSLocalModelRegistry.REGISTRY_SCHEMA,
            "model_id": model_id,
            "created_at": started_at,
            "trained": trained,
            "training_status": training_status,
            "source_dataset_version": str(source_summary.get("dataset_version") or "v1"),
            "source_feature_summary_hash": source_hash,
            "train_count": len(train_records),
            "validation_count": len(validation_records),
            "model_type": "mean_baseline_regressor" if trained else "none",
            "targets": sorted(models),
            "metrics_path": str(Path(artifact_path) / "metrics.json") if trained else str(self.registry.metrics_status_path),
            "artifact_path": artifact_path,
            "model_card_created": model_card_created,
            "safe_for_shadow_evaluation": trained,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "blocker": skip_reason,
            "training_source_records_count": int(loaded["training_source_records_count"]),
            "training_usable_records_count": int(loaded["training_usable_records_count"]),
            "training_excluded_records_count": int(loaded["training_excluded_records_count"]),
            "training_data_loaded": bool(loaded["training_data_loaded"]),
            "training_data_empty": bool(loaded["training_data_empty"]),
            "training_data_insufficient": bool(loaded["training_data_insufficient"]),
            "feature_columns_count": int(matrix["feature_columns_count"]),
            "action_quality_target_ready": bool(labels["action_quality_target_ready"]),
            "outcome_score_target_ready": bool(labels["outcome_score_target_ready"]),
            "provider_value_target_ready": bool(labels["provider_value_target_ready"]),
            "metrics_status": str(metrics["metrics_status"]),
            "model_training_attempted": training_attempted,
            "model_training_skipped": not trained,
            "model_training_skip_reason": skip_reason,
        }
        metrics_status = {**metrics, "model_id": model_id, "training_status": training_status, "trained": trained}
        self.registry.record_training_run(metadata, metrics_status)
        from app.services.local_model_calibration import AITSLocalModelCalibration
        calibration_summary = AITSLocalModelCalibration(
            training_root=self.training_root,
            model_root=self.model_root,
        ).run(persist=calibration_persist)
        result = {
            **loaded,
            **{key: value for key, value in matrix.items() if key != "matrix"},
            **{key: value for key, value in labels.items() if key != "targets"},
            "schema": self.TRAINING_SCHEMA,
            "model_id": model_id,
            "local_model_training_layer_ready": True,
            "baseline_trainer_ready": True,
            "model_training_attempted": training_attempted,
            "model_training_skipped": not trained,
            "model_training_skip_reason": skip_reason,
            "model_type": metadata["model_type"],
            "trained_targets": sorted(models),
            "trained_model_count": len(models),
            "training_record_count": len(train_records),
            "validation_record_count": len(validation_records),
            "metrics_evaluator_ready": True,
            "metrics_status": metrics["metrics_status"],
            "metrics_path": metadata["metrics_path"],
            "model_artifact_writer_ready": True,
            "model_registry_ready": True,
            "no_data_training_ready": no_data and not trained,
            "insufficient_data_training_ready": insufficient and not trained,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "safe_for_shadow_evaluation": trained,
            "artifact_path": artifact_path,
            "model_card_created": model_card_created,
            "training_status": training_status,
            "calibration_summary": calibration_summary,
        }
        logging.getLogger("aits").info(
            "[AITS][LocalModelTraining] event=training_completed model_id=%s training_status=%s source_count=%s usable_count=%s train_count=%s validation_count=%s model_training_attempted=%s model_training_skipped=%s skip_reason=%s trained_targets=%s safe_for_live_decision=false live_decision_enabled=false actual_order=False submitted=0",
            model_id, training_status, loaded["training_source_records_count"], loaded["training_usable_records_count"],
            len(train_records), len(validation_records), training_attempted, not trained, skip_reason or "-", ",".join(sorted(models)) or "-",
        )
        return result


def run_local_model_training() -> dict:
    return AITSLocalModelTrainingPipeline().run_training()
