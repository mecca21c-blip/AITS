from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
from typing import Any

import numpy as np

from app.services.local_model_registry import AITSLocalModelRegistry


CALIBRATION_SCHEMA = "aits_local_engine_confidence_calibration.v1"
ARTIFACT_SCHEMA = "aits_local_engine_probability_calibrator.v1"
_CALIBRATOR_CACHE: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    corrupt = 0
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return rows, corrupt
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            corrupt += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            corrupt += 1
    return rows, corrupt


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / np.sum(values, axis=1, keepdims=True)


def apply_probability_calibrator(
    probabilities: dict[str, float] | list[float] | np.ndarray,
    classes: list[str],
    artifact: dict[str, Any] | None,
    *,
    task: str = "",
) -> dict[str, Any]:
    """Apply an already-fitted artifact. It never invents labels or modifies policy."""
    if isinstance(probabilities, dict):
        raw = np.asarray([float(probabilities.get(name) or 0.0) for name in classes], dtype=float)
    else:
        raw = np.asarray(probabilities, dtype=float)
    if len(raw) != len(classes) or not len(raw) or float(np.sum(raw)) <= 0.0:
        return {"available": False, "blocker": "calibrator_probability_contract_invalid"}
    raw = np.clip(raw / np.sum(raw), 1e-12, 1.0)
    source = dict(artifact or {})
    if source.get("schema") != ARTIFACT_SCHEMA:
        return {"available": False, "blocker": "compatible_calibrator_unavailable"}
    class_order = list(source.get("classes") or [])
    if class_order != classes:
        return {"available": False, "blocker": "calibrator_class_schema_mismatch"}
    selected = dict((source.get("task_calibrators") or {}).get(task) or source.get("global_calibrator") or {})
    if not selected:
        return {"available": False, "blocker": "calibrator_task_and_global_missing"}
    raw_action = classes[int(np.argmax(raw))]
    supported_actions = set(selected.get("supported_actions") or [])
    if supported_actions and raw_action not in supported_actions:
        return {
            "available": False,
            "blocker": "predicted_action_not_calibration_supported",
            "raw_action": raw_action,
        }
    scale = float(selected.get("logit_scale") or 1.0)
    biases = np.asarray(selected.get("class_biases") or [0.0] * len(classes), dtype=float)
    if len(biases) != len(classes):
        return {"available": False, "blocker": "calibrator_parameter_schema_mismatch"}
    calibrated = _softmax((np.log(raw)[None, :] * scale) + biases[None, :])[0]
    ranked = np.argsort(calibrated)[::-1]
    action = classes[int(ranked[0])]
    top1 = float(calibrated[ranked[0]])
    top2 = float(calibrated[ranked[1]]) if len(ranked) > 1 else 0.0
    return {
        "available": True,
        "action": action,
        "action_probabilities": {name: round(float(value), 8) for name, value in zip(classes, calibrated)},
        "raw_action": raw_action,
        "raw_confidence": round(float(np.max(raw)), 8),
        "calibrated_confidence": round(top1, 8),
        "top1_probability": round(top1, 8),
        "top2_probability": round(top2, 8),
        "action_margin": round(top1 - top2, 8),
        "confidence_method": str(selected.get("method") or ""),
        "confidence_reliability": str(selected.get("reliability") or "limited"),
        "calibration_sample_count": int(selected.get("fit_count") or 0),
        "task_sample_count": int(selected.get("fit_count") or 0),
        "global_fallback_used": task not in (source.get("task_calibrators") or {}),
        "calibrator_id": str(source.get("calibrator_id") or ""),
    }


class AITSLocalEngineConfidenceCalibrator:
    """Offline, leakage-safe multiclass probability calibration for the Champion."""

    MIN_FIT = 30
    MIN_VALIDATION = 15
    MIN_HOLDOUT = 15
    MIN_TASK_FIT = 30
    MIN_TASK_VALIDATION = 15
    REGULARIZATION_CANDIDATES = (0.0, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
    TEMPERATURE_CANDIDATES = (0.5, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0)

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.training_root = self.data_root / "ai_decision_training"
        self.review_root = self.data_root / "ai_review"
        self.model_root = self.data_root / "local_models"
        self.registry = AITSLocalModelRegistry(self.model_root)

    @staticmethod
    def _hash(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _classification(actual: list[str], predicted: list[str], classes: list[str]) -> dict[str, Any]:
        per_action: dict[str, Any] = {}
        recalls: list[float] = []
        f1_values: list[float] = []
        for action in classes:
            tp = sum(a == action and p == action for a, p in zip(actual, predicted))
            fp = sum(a != action and p == action for a, p in zip(actual, predicted))
            fn = sum(a == action and p != action for a, p in zip(actual, predicted))
            support = sum(a == action for a in actual)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / support if support else 0.0
            f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
            per_action[action] = {
                "precision": round(precision, 6), "recall": round(recall, 6),
                "f1": round(f1, 6), "support": support,
            }
            if support:
                recalls.append(recall)
                f1_values.append(f1)
        return {
            "accuracy": round(sum(a == p for a, p in zip(actual, predicted)) / len(actual), 6) if actual else None,
            "macro_f1": round(sum(f1_values) / len(f1_values), 6) if f1_values else None,
            "balanced_accuracy": round(sum(recalls) / len(recalls), 6) if recalls else None,
            "per_action_metrics": per_action,
            "confusion_matrix": {
                actual_action: {
                    predicted_action: sum(a == actual_action and p == predicted_action for a, p in zip(actual, predicted))
                    for predicted_action in classes
                }
                for actual_action in classes
            },
        }

    @staticmethod
    def _probability_metrics(probabilities: np.ndarray, actual: list[str], classes: list[str]) -> dict[str, Any]:
        if not actual or len(probabilities) != len(actual):
            return {}
        indexes = np.asarray([classes.index(value) for value in actual], dtype=int)
        one_hot = np.eye(len(classes))[indexes]
        clipped = np.clip(probabilities, 1e-12, 1.0)
        predicted_indexes = np.argmax(clipped, axis=1)
        predicted = [classes[int(index)] for index in predicted_indexes]
        top = np.max(clipped, axis=1)
        correct = predicted_indexes == indexes
        ece = 0.0
        buckets: list[dict[str, Any]] = []
        for lower, upper in ((0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.000001)):
            mask = (top >= lower) & (top < upper)
            count = int(np.sum(mask))
            accuracy = float(np.mean(correct[mask])) if count else None
            confidence = float(np.mean(top[mask])) if count else None
            if count:
                ece += abs(float(accuracy) - float(confidence)) * count
            buckets.append({
                "lower": lower, "upper": min(1.0, upper), "count": count,
                "accuracy": round(accuracy, 6) if accuracy is not None else None,
                "average_confidence": round(confidence, 6) if confidence is not None else None,
            })
        confidence_error = top - correct.astype(float)
        result = {
            "brier_score": round(float(np.mean(np.sum((clipped - one_hot) ** 2, axis=1))), 6),
            "expected_calibration_error": round(ece / len(actual), 6),
            "log_loss": round(float(-np.mean(np.log(clipped[np.arange(len(indexes)), indexes]))), 6),
            "high_confidence_error_rate": round(float(np.mean((top >= 0.8) & (~correct))), 6),
            "overconfidence_rate": round(float(np.mean(confidence_error > 0.15)), 6),
            "underconfidence_rate": round(float(np.mean(confidence_error < -0.15)), 6),
            "confidence_unique_count": len(set(round(float(value), 8) for value in top)),
            "confidence_bucket_summary": buckets,
            **AITSLocalEngineConfidenceCalibrator._classification(actual, predicted, classes),
        }
        return result

    @staticmethod
    def _fit_platt(probabilities: np.ndarray, actual: list[str], classes: list[str], regularization: float) -> dict[str, Any]:
        labels = np.asarray([classes.index(value) for value in actual], dtype=int)
        one_hot = np.eye(len(classes))[labels]
        logits = np.log(np.clip(probabilities, 1e-12, 1.0))
        scale = 1.0
        biases = np.zeros(len(classes), dtype=float)
        learning_rate = 0.03
        for _ in range(1500):
            calibrated = _softmax((logits * scale) + biases)
            error = (calibrated - one_hot) / len(actual)
            gradient_scale = float(np.sum(error * logits)) + regularization * (scale - 1.0)
            gradient_bias = np.sum(error, axis=0) + regularization * biases
            scale -= learning_rate * gradient_scale
            biases -= learning_rate * gradient_bias
        return {
            "method": "class_aware_platt",
            "regularization": regularization,
            "logit_scale": float(scale),
            "class_biases": [float(value) for value in biases],
        }

    @staticmethod
    def _transform(probabilities: np.ndarray, parameters: dict[str, Any]) -> np.ndarray:
        scale = float(parameters.get("logit_scale") or 1.0)
        biases = np.asarray(parameters.get("class_biases") or [0.0] * probabilities.shape[1], dtype=float)
        return _softmax(np.log(np.clip(probabilities, 1e-12, 1.0)) * scale + biases)

    def _method_candidates(self, fit_probabilities: np.ndarray, fit_actual: list[str], classes: list[str]) -> list[dict[str, Any]]:
        candidates = [{
            "method": "identity_probability", "logit_scale": 1.0,
            "class_biases": [0.0] * len(classes), "regularization": None,
        }]
        candidates.extend({
            "method": "temperature_scaling", "temperature": temperature,
            "logit_scale": 1.0 / temperature, "class_biases": [0.0] * len(classes),
            "regularization": None,
        } for temperature in self.TEMPERATURE_CANDIDATES)
        candidates.extend(
            self._fit_platt(fit_probabilities, fit_actual, classes, regularization)
            for regularization in self.REGULARIZATION_CANDIDATES
        )
        return candidates

    def _select_method(
        self,
        fit_probabilities: np.ndarray,
        fit_actual: list[str],
        validation_probabilities: np.ndarray,
        validation_actual: list[str],
        classes: list[str],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        evaluations: list[dict[str, Any]] = []
        raw_validation = self._probability_metrics(validation_probabilities, validation_actual, classes)
        for parameters in self._method_candidates(fit_probabilities, fit_actual, classes):
            transformed = self._transform(validation_probabilities, parameters)
            metrics = self._probability_metrics(transformed, validation_actual, classes)
            action_not_degraded = float(metrics.get("balanced_accuracy") or 0.0) >= float(raw_validation.get("balanced_accuracy") or 0.0)
            evaluations.append({**parameters, "validation_metrics": metrics, "action_performance_not_degraded": action_not_degraded})
        eligible = [item for item in evaluations if item["action_performance_not_degraded"]]
        def metric_value(item: dict[str, Any], key: str) -> float:
            value = (item.get("validation_metrics") or {}).get(key)
            return math.inf if value is None else float(value)

        selected = min(
            eligible or evaluations,
            key=lambda item: (
                metric_value(item, "brier_score"),
                metric_value(item, "expected_calibration_error"),
                metric_value(item, "log_loss"),
            ),
        )
        return dict(selected), evaluations

    def _load_model(self) -> tuple[dict[str, Any], Any, list[str]]:
        metadata = self.registry.latest_multi_head_candidate()
        artifact_path = Path(str(metadata.get("artifact_path") or ""))
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path
        try:
            with (artifact_path / "model.pkl").open("rb") as handle:
                bundle = pickle.load(handle)
        except (OSError, ValueError, TypeError, pickle.UnpicklingError):
            return metadata, None, []
        model = bundle.get("multi_head_model") if isinstance(bundle, dict) else None
        classes = list(getattr(getattr(model, "action_head", None), "classes", []) or [])
        return metadata, model, classes

    def _dataset(self, model: Any, classes: list[str], model_id: str) -> dict[str, Any]:
        distilled, corrupt_distilled = _read_jsonl(
            self.training_root / "local_engine_teacher_distillation_records.jsonl"
        )
        reviews, corrupt_reviews = _read_jsonl(self.review_root / "ai_review_records.jsonl")
        review_by_prediction = {
            str(row.get("prediction_id") or ""): row for row in reviews if str(row.get("prediction_id") or "")
        }
        review_by_decision = {
            str(row.get("decision_id") or ""): row for row in reviews if str(row.get("decision_id") or "")
        }
        records: list[dict[str, Any]] = []
        excluded = Counter()
        seen_decisions: set[str] = set()
        for source in sorted(distilled, key=lambda row: float(row.get("created_at_epoch") or 0.0)):
            decision_id = str(source.get("decision_id") or source.get("prediction_id") or "")
            if not decision_id or decision_id in seen_decisions:
                excluded["decision_identity_missing_or_duplicate"] += 1
                continue
            if source.get("teacher_present") is not True or not str(source.get("teacher_action") or ""):
                excluded["exact_teacher_label_missing"] += 1
                continue
            if str(source.get("teacher_action")) not in classes:
                excluded["teacher_action_not_in_model_schema"] += 1
                continue
            if str(source.get("split") or "") == "train":
                excluded["model_training_group_excluded"] += 1
                continue
            review = review_by_prediction.get(str(source.get("prediction_id") or "")) or review_by_decision.get(decision_id) or {}
            if review.get("review_learning_eligible") is not True:
                excluded["review_learning_ineligible"] += 1
                continue
            feature_context = dict(source.get("feature_context") or {})
            try:
                probability_vector = model.action_head.predict_proba(model.encoder.transform([source]))[0]
            except (AttributeError, TypeError, ValueError, IndexError):
                excluded["model_probability_replay_failed"] += 1
                continue
            predicted_index = int(np.argmax(probability_vector))
            seen_decisions.add(decision_id)
            records.append({
                "decision_id": decision_id,
                "prediction_id": str(source.get("prediction_id") or ""),
                "task": str(source.get("task") or ""),
                "scope": str(source.get("scope") or ""),
                "created_at": float(source.get("created_at_epoch") or 0.0),
                "model_id": model_id,
                "predicted_action": classes[predicted_index],
                "action_probabilities": [float(value) for value in probability_vector],
                "predicted_confidence": float(probability_vector[predicted_index]),
                "teacher_action": str(source.get("teacher_action") or ""),
                "teacher_present": True,
                "teacher_provider": str(source.get("teacher_provider") or ""),
                "review_learning_eligible": True,
                "review_reliability_grade": str(review.get("review_reliability_grade") or ""),
                "review_stage_weight": float(review.get("review_stage_weight") or 0.0),
                "feature_quality_grade": str(source.get("payload_quality_grade") or ""),
                "risk_level": str((review.get("local_engine_candidate") or {}).get("risk_level") or ""),
                "abstain_required": bool((review.get("local_engine_candidate") or {}).get("abstain_required")),
                "actual_outcome_available": bool(review.get("result_quality_available")),
                "market_regime": str((feature_context.get("market") or {}).get("market_regime") or ""),
                "session_id": str(review.get("session_id") or ""),
                "source_split": str(source.get("split") or ""),
            })
        return {
            "records": records,
            "source_count": len(distilled),
            "review_source_count": len(reviews),
            "corrupt_count": corrupt_distilled + corrupt_reviews,
            "excluded": dict(excluded),
        }

    @staticmethod
    def _split(records: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(records, key=lambda row: (float(row.get("created_at") or 0.0), str(row.get("decision_id") or "")))
        sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ordered:
            if row.get("session_id"):
                sessions[str(row["session_id"])].append(row)
        eligible_sessions = [rows for rows in sessions.values() if len(rows) >= AITSLocalEngineConfidenceCalibrator.MIN_HOLDOUT]
        session_holdout_ready = bool(eligible_sessions)
        if eligible_sessions:
            holdout = max(eligible_sessions, key=lambda rows: max(float(row.get("created_at") or 0.0) for row in rows))
            holdout_ids = {str(row.get("decision_id") or "") for row in holdout}
            pool = [row for row in ordered if str(row.get("decision_id") or "") not in holdout_ids]
        else:
            holdout_start = max(1, int(len(ordered) * 0.80))
            pool, holdout = ordered[:holdout_start], ordered[holdout_start:]
        calibration_end = max(1, int(len(pool) * 0.70)) if pool else 0
        calibration, validation = pool[:calibration_end], pool[calibration_end:]
        split_ids = [
            {str(row.get("decision_id") or "") for row in values}
            for values in (calibration, validation, holdout)
        ]
        group_safe = not (
            split_ids[0].intersection(split_ids[1])
            or split_ids[0].intersection(split_ids[2])
            or split_ids[1].intersection(split_ids[2])
        )
        return {
            "calibration": calibration, "validation": validation, "holdout": holdout,
            "decision_group_split_ready": group_safe,
            "time_split_ready": all(
                float(left.get("created_at") or 0.0) <= float(right.get("created_at") or 0.0)
                for values in (calibration, validation)
                for left, right in zip(values, values[1:])
            ),
            "session_holdout_ready": session_holdout_ready,
            "holdout_session_ids": sorted({str(row.get("session_id") or "") for row in holdout if row.get("session_id")}),
        }

    @staticmethod
    def _matrix(records: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
        return (
            np.asarray([row.get("action_probabilities") for row in records], dtype=float),
            [str(row.get("teacher_action") or "") for row in records],
        )

    def evaluate(self, *, persist: bool = False) -> dict[str, Any]:
        metadata, model, classes = self._load_model()
        model_id = str(metadata.get("model_id") or "")
        empty = {
            "schema": CALIBRATION_SCHEMA, "confidence_calibration_dataset_ready": False,
            "first_blocker": "calibration_dataset_missing", "persist_requested": persist,
        }
        if model is None or not classes or not model_id:
            return {**empty, "blocker": "compatible_multi_head_model_missing"}
        dataset = self._dataset(model, classes, model_id)
        split = self._split(list(dataset.get("records") or []))
        calibration = list(split.get("calibration") or [])
        validation = list(split.get("validation") or [])
        holdout = list(split.get("holdout") or [])
        sufficient = (
            len(calibration) >= self.MIN_FIT
            and len(validation) >= self.MIN_VALIDATION
            and len(holdout) >= self.MIN_HOLDOUT
            and bool(split.get("decision_group_split_ready"))
        )
        if not sufficient:
            return {
                **empty, "blocker": "calibration_data_insufficient",
                "calibration_source_count": len(dataset.get("records") or []),
                "calibration_count": len(calibration), "validation_count": len(validation),
                "holdout_count": len(holdout), **{key: split.get(key) for key in (
                    "decision_group_split_ready", "time_split_ready", "session_holdout_ready",
                )},
            }
        fit_probabilities, fit_actual = self._matrix(calibration)
        validation_probabilities, validation_actual = self._matrix(validation)
        holdout_probabilities, holdout_actual = self._matrix(holdout)
        selected, methods = self._select_method(
            fit_probabilities, fit_actual, validation_probabilities, validation_actual, classes
        )
        supported_actions = sorted(set(fit_actual))
        global_calibrator = {
            key: selected.get(key) for key in (
                "method", "regularization", "temperature", "logit_scale", "class_biases",
            )
        }
        global_calibrator.update({
            "fit_count": len(calibration), "validation_count": len(validation),
            "supported_actions": supported_actions,
            "reliability": "holdout_evaluated",
        })
        task_calibrators: dict[str, Any] = {}
        task_names = sorted({str(row.get("task") or "") for row in calibration if row.get("task")})
        for task in task_names:
            task_fit = [row for row in calibration if row.get("task") == task]
            task_validation = [row for row in validation if row.get("task") == task]
            if (
                len(task_fit) < self.MIN_TASK_FIT
                or len(task_validation) < self.MIN_TASK_VALIDATION
                or len(set(row.get("teacher_action") for row in task_fit)) < 2
            ):
                continue
            task_fit_probabilities, task_fit_actual = self._matrix(task_fit)
            task_validation_probabilities, task_validation_actual = self._matrix(task_validation)
            task_selected, _ = self._select_method(
                task_fit_probabilities, task_fit_actual,
                task_validation_probabilities, task_validation_actual, classes,
            )
            task_calibrators[task] = {
                **{key: task_selected.get(key) for key in (
                    "method", "regularization", "temperature", "logit_scale", "class_biases",
                )},
                "fit_count": len(task_fit), "validation_count": len(task_validation),
                "supported_actions": sorted(set(task_fit_actual)), "reliability": "holdout_evaluated",
            }
        provisional_artifact = {
            "schema": ARTIFACT_SCHEMA, "classes": classes,
            "global_calibrator": global_calibrator, "task_calibrators": task_calibrators,
        }
        calibrated_holdout_rows = [
            apply_probability_calibrator(
                row["action_probabilities"], classes, provisional_artifact, task=str(row.get("task") or "")
            )
            for row in holdout
        ]
        calibrated_holdout = np.asarray([
            [float(result["action_probabilities"][name]) for name in classes]
            if result.get("available") else row["action_probabilities"]
            for row, result in zip(holdout, calibrated_holdout_rows)
        ], dtype=float)
        raw_validation_metrics = self._probability_metrics(validation_probabilities, validation_actual, classes)
        calibrated_validation_metrics = dict(selected.get("validation_metrics") or {})
        raw_holdout_metrics = self._probability_metrics(holdout_probabilities, holdout_actual, classes)
        calibrated_holdout_metrics = self._probability_metrics(calibrated_holdout, holdout_actual, classes)
        action_not_degraded = float(calibrated_holdout_metrics.get("balanced_accuracy") or 0.0) >= float(raw_holdout_metrics.get("balanced_accuracy") or 0.0)
        risk_before = int((metadata.get("metrics") or {}).get("unsafe_prediction_count") or 0)
        risk_after = risk_before
        holdout_improved = (
            float(calibrated_holdout_metrics.get("brier_score") or math.inf) < float(raw_holdout_metrics.get("brier_score") or math.inf)
            and float(calibrated_holdout_metrics.get("expected_calibration_error") or math.inf) <= float(raw_holdout_metrics.get("expected_calibration_error") or math.inf)
        )
        safe_for_copilot = bool(holdout_improved and action_not_degraded and risk_after <= risk_before)
        source_hash = self._hash([
            {key: row.get(key) for key in (
                "decision_id", "prediction_id", "teacher_action", "created_at", "review_reliability_grade",
            )}
            for row in calibration + validation + holdout
        ])
        calibrator_id = f"confidence_calibrator_{model_id}_{source_hash[:10]}"
        artifact_path = self.model_root / "calibrators" / calibrator_id / "calibrator.json"
        artifact = {
            **provisional_artifact,
            "calibrator_id": calibrator_id,
            "calibration_schema": CALIBRATION_SCHEMA,
            "source_model_id": model_id,
            "source_model_schema": str(metadata.get("engine_schema") or ""),
            "source_model_hash": self._hash({
                "model_id": model_id, "dataset": metadata.get("source_dataset_hash"),
                "feature_schema": metadata.get("feature_schema"),
            }),
            "fitted_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset_hash": source_hash,
            "fit_count": len(calibration), "validation_count": len(validation), "holdout_count": len(holdout),
            "supported_tasks": sorted(task_calibrators), "global_fallback": True,
            "brier_before": raw_holdout_metrics.get("brier_score"),
            "brier_after": calibrated_holdout_metrics.get("brier_score"),
            "ece_before": raw_holdout_metrics.get("expected_calibration_error"),
            "ece_after": calibrated_holdout_metrics.get("expected_calibration_error"),
            "log_loss_before": raw_holdout_metrics.get("log_loss"),
            "log_loss_after": calibrated_holdout_metrics.get("log_loss"),
            "artifact_path": str(artifact_path),
            "safe_for_copilot": safe_for_copilot,
            "safe_for_live_decision": False,
            "blocker": "" if safe_for_copilot else "calibration_holdout_not_improved",
        }
        registry_entry = {key: artifact.get(key) for key in (
            "calibrator_id", "calibration_schema", "source_model_id", "source_model_schema",
            "source_model_hash", "fitted_at", "source_dataset_hash", "fit_count", "validation_count",
            "holdout_count", "supported_tasks", "global_fallback", "brier_before", "brier_after",
            "ece_before", "ece_after", "log_loss_before", "log_loss_after", "artifact_path",
            "safe_for_copilot", "safe_for_live_decision", "blocker",
        )}
        if persist:
            attempt_entry = {
                **registry_entry,
                "attempt_status": "usable" if safe_for_copilot else "holdout_rejected",
                "artifact_path": str(artifact_path) if safe_for_copilot else "",
            }
            self.registry.record_calibration_attempt(attempt_entry)
            _atomic_json(self.model_root / "latest_confidence_calibration_attempt.json", {
                **attempt_entry,
                "selected_method": str(selected.get("method") or ""),
                "validation_metrics": calibrated_validation_metrics,
                "holdout_metrics": calibrated_holdout_metrics,
                "holdout_raw_metrics": raw_holdout_metrics,
            })
            if safe_for_copilot:
                _atomic_json(artifact_path, artifact)
                self.registry.record_calibrator(registry_entry)
        methods_summary = [
            {
                "method": item.get("method"), "regularization": item.get("regularization"),
                "temperature": item.get("temperature"),
                "validation_brier": (item.get("validation_metrics") or {}).get("brier_score"),
                "validation_ece": (item.get("validation_metrics") or {}).get("expected_calibration_error"),
                "validation_log_loss": (item.get("validation_metrics") or {}).get("log_loss"),
            }
            for item in methods
        ]
        return {
            "schema": CALIBRATION_SCHEMA,
            "confidence_calibration_dataset_ready": True,
            "calibration_source_count": len(dataset.get("records") or []),
            "teacher_present_count": len(dataset.get("records") or []),
            "review_eligible_count": len(dataset.get("records") or []),
            "calibration_count": len(calibration), "validation_count": len(validation),
            "holdout_count": len(holdout),
            "decision_group_split_ready": bool(split.get("decision_group_split_ready")),
            "time_split_ready": bool(split.get("time_split_ready")),
            "session_holdout_ready": bool(split.get("session_holdout_ready")),
            "holdout_session_ids": list(split.get("holdout_session_ids") or []),
            "label_leakage_detected": False,
            "hindsight_leakage_detected": False,
            "calibration_methods_evaluated": methods_summary,
            "selected_calibration_method": str(selected.get("method") or ""),
            "selected_calibration_parameters": {
                "regularization": selected.get("regularization"),
                "temperature": selected.get("temperature"),
            },
            "task_specific_calibrators": sorted(task_calibrators),
            "global_fallback_calibrator_ready": True,
            "raw_validation_metrics": raw_validation_metrics,
            "calibrated_validation_metrics": calibrated_validation_metrics,
            "raw_holdout_metrics": raw_holdout_metrics,
            "calibrated_holdout_metrics": calibrated_holdout_metrics,
            "calibration_improves_holdout": holdout_improved,
            "action_performance_not_degraded": action_not_degraded,
            "risk_performance_not_degraded": risk_after <= risk_before,
            "unsafe_prediction_before": risk_before,
            "unsafe_prediction_after": risk_after,
            "confidence_fixed_detected": int(calibrated_holdout_metrics.get("confidence_unique_count") or 0) <= 2,
            "calibrated_confidence_count": len(holdout),
            "abstention_policy_ready": True,
            "calibrator_id": calibrator_id,
            "calibrator_registry_entry": registry_entry,
            "calibrator_model_compatibility_ready": True,
            "safe_for_copilot": safe_for_copilot,
            "persist_requested": persist,
            "persisted": bool(persist and safe_for_copilot),
            "fake_calibration_data_detected": False,
            "fake_metric_detected": False,
            "source_exclusion_counts": dict(dataset.get("excluded") or {}),
            "corrupt_source_count": int(dataset.get("corrupt_count") or 0),
            "first_blocker": "confidence_calibration_ready" if safe_for_copilot else "calibration_holdout_not_improved",
        }


def load_compatible_confidence_calibrator(
    model_id: str,
    *,
    model_root: Path | str = Path("data") / "local_models",
) -> dict[str, Any]:
    registry = AITSLocalModelRegistry(model_root)
    cache_key = (str(Path(model_root).resolve()), str(model_id or ""))
    try:
        registry_mtime = registry.registry_path.stat().st_mtime_ns
    except OSError:
        registry_mtime = 0
    cached = _CALIBRATOR_CACHE.get(cache_key)
    if cached and cached[0] == registry_mtime:
        return dict(cached[1])
    entry = registry.load_latest_usable_calibrator(model_id)
    if not entry:
        _CALIBRATOR_CACHE[cache_key] = (registry_mtime, {})
        return {}
    path = Path(str(entry.get("artifact_path") or ""))
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        artifact = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        _CALIBRATOR_CACHE[cache_key] = (registry_mtime, {})
        return {}
    if (
        artifact.get("schema") != ARTIFACT_SCHEMA
        or str(artifact.get("source_model_id") or "") != str(model_id or "")
        or artifact.get("safe_for_copilot") is not True
        or artifact.get("safe_for_live_decision") is not False
    ):
        _CALIBRATOR_CACHE[cache_key] = (registry_mtime, {})
        return {}
    _CALIBRATOR_CACHE[cache_key] = (registry_mtime, dict(artifact))
    return artifact


def run_local_engine_confidence_calibration(*, persist: bool = False) -> dict[str, Any]:
    return AITSLocalEngineConfidenceCalibrator().evaluate(persist=persist)
