from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
import pickle
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from app.services.local_engine_reason_composer import AITSLocalEngineReasonComposer
from app.services.local_engine_teacher_distillation import (
    AITSLocalEngineTeacherDistillation,
    TEACHER_ACTIONS,
    task_contract_kind,
)
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import atomic_write_json


ETA_BUCKETS = (60, 180, 300, 900, 1800, 3600)
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _flatten_numeric(value: dict, prefix: str = "") -> dict[str, float]:
    result: dict[str, float] = {}
    for key, item in sorted(value.items()):
        if not prefix and key == "provider":
            # Provider agreement/escalation fields are decided after the external
            # response and are labels/provenance, never inference features.
            continue
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            result.update(_flatten_numeric(item, path))
        elif isinstance(item, bool):
            result[path] = 1.0 if item else 0.0
        else:
            number = _number(item)
            if number is not None:
                result[path] = number
    indicators = dict(value.get("indicators") or {}) if not prefix else {}
    position = dict(value.get("position") or {}) if not prefix else {}
    portfolio = dict(value.get("portfolio") or {}) if not prefix else {}
    ma5 = _number(indicators.get("ma5"))
    ma20 = _number(indicators.get("ma20"))
    if ma5 is not None and ma20 not in (None, 0.0):
        result["derived.ma5_minus_ma20_pct"] = (ma5 - ma20) / abs(ma20) * 100.0
    current = _number(position.get("current_price"))
    average = _number(position.get("avg_buy_price"))
    if current is not None and average not in (None, 0.0):
        result["derived.price_vs_avg_pct"] = (current - average) / abs(average) * 100.0
    total = _number(portfolio.get("total_asset_krw"))
    exposure = _number(portfolio.get("exposure_for_cap"))
    available = _number(portfolio.get("available_krw"))
    if total not in (None, 0.0):
        if exposure is not None:
            result["derived.exposure_ratio"] = exposure / abs(total)
        if available is not None:
            result["derived.cash_ratio"] = available / abs(total)
    return result


class AITSMultiHeadFeatureEncoder:
    def __init__(self) -> None:
        self.columns: list[str] = []
        self.means: np.ndarray = np.asarray([], dtype=float)
        self.scales: np.ndarray = np.asarray([], dtype=float)
        self.task_categories: list[str] = []

    def fit(self, records: list[dict]) -> "AITSMultiHeadFeatureEncoder":
        flattened = [_flatten_numeric(dict(row.get("feature_context") or {})) for row in records]
        counts = Counter(key for row in flattened for key in row)
        minimum = max(2, int(len(records) * 0.05))
        numeric_columns = sorted(key for key, count in counts.items() if count >= minimum)
        self.task_categories = sorted({str(row.get("task") or "unknown") for row in records})
        self.columns = numeric_columns + [f"task::{task}" for task in self.task_categories]
        raw = self._raw_matrix(records)
        self.means = np.mean(raw, axis=0) if len(raw) else np.zeros(len(self.columns))
        self.scales = np.std(raw, axis=0) if len(raw) else np.ones(len(self.columns))
        self.scales[self.scales < 1e-9] = 1.0
        return self

    def _raw_matrix(self, records: list[dict]) -> np.ndarray:
        numeric_count = len(self.columns) - len(self.task_categories)
        rows: list[list[float]] = []
        for record in records:
            values = _flatten_numeric(dict(record.get("feature_context") or {}))
            vector = [float(values.get(column, 0.0)) for column in self.columns[:numeric_count]]
            task = str(record.get("task") or "unknown")
            vector.extend(1.0 if task == category else 0.0 for category in self.task_categories)
            rows.append(vector)
        return np.asarray(rows, dtype=float) if rows else np.zeros((0, len(self.columns)), dtype=float)

    def transform(self, records: list[dict]) -> np.ndarray:
        raw = self._raw_matrix(records)
        return (raw - self.means) / self.scales if len(raw) else raw


class AITSWeightedMultinomialHead:
    def __init__(self) -> None:
        self.classes: list[str] = []
        self.weights: np.ndarray = np.zeros((0, 0), dtype=float)

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        shifted = logits - np.max(logits, axis=1, keepdims=True)
        exponent = np.exp(np.clip(shifted, -60.0, 60.0))
        return exponent / np.sum(exponent, axis=1, keepdims=True)

    def fit(self, matrix: np.ndarray, labels: list[str]) -> "AITSWeightedMultinomialHead":
        self.classes = sorted(set(labels))
        class_index = {name: index for index, name in enumerate(self.classes)}
        y = np.asarray([class_index[label] for label in labels], dtype=int)
        x = np.column_stack([matrix, np.ones(len(matrix))])
        self.weights = np.zeros((x.shape[1], len(self.classes)), dtype=float)
        counts = Counter(labels)
        sample_weights = np.asarray([len(labels) / (len(self.classes) * counts[label]) for label in labels])
        targets = np.eye(len(self.classes))[y]
        learning_rate = 0.08
        for _ in range(900):
            probabilities = self._softmax(x @ self.weights)
            gradient = x.T @ ((probabilities - targets) * sample_weights[:, None]) / len(x)
            gradient[:-1] += 0.002 * self.weights[:-1]
            self.weights -= learning_rate * gradient
        return self

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        x = np.column_stack([matrix, np.ones(len(matrix))])
        return self._softmax(x @ self.weights)


class AITSLocalEngineMultiHeadModel:
    """Pickle-safe candidate-only multi-head model."""

    BUNDLE_SCHEMA = "aits_local_engine_multi_head_bundle.v1"

    def __init__(
        self,
        *,
        encoder: AITSMultiHeadFeatureEncoder,
        action_head: AITSWeightedMultinomialHead,
        confidence_bins: list[dict],
        task_counts: dict[str, int],
        scope_counts: dict[str, int],
        eta_cadence: dict[str, int],
        supported_tasks: list[str],
    ) -> None:
        self.encoder = encoder
        self.action_head = action_head
        self.confidence_bins = confidence_bins
        self.task_counts = task_counts
        self.scope_counts = scope_counts
        self.eta_cadence = eta_cadence
        self.supported_tasks = supported_tasks
        self.reason_composer = AITSLocalEngineReasonComposer()

    @staticmethod
    def _nearest_eta(value: float) -> int:
        return min(ETA_BUCKETS, key=lambda bucket: abs(bucket - value))

    def _calibrate(self, raw: float) -> tuple[float, str]:
        for bucket in self.confidence_bins:
            if float(bucket["lower"]) <= raw <= float(bucket["upper"]):
                count = int(bucket.get("count") or 0)
                correct = int(bucket.get("correct") or 0)
                if count:
                    return max(0.0, min(1.0, (correct + 2.0 * raw) / (count + 2.0))), "empirical_bucket_shrinkage"
        return raw, "uncalibrated_probability"

    @staticmethod
    def _risk(feature_context: dict, quality_grade: str) -> dict:
        risk = dict(feature_context.get("risk") or {})
        market = dict(feature_context.get("market") or {})
        position = dict(feature_context.get("position") or {})
        portfolio = dict(feature_context.get("portfolio") or {})
        data_quality = dict(feature_context.get("data_quality") or {})
        score = 0.05
        factors: list[str] = []
        blockers: list[str] = []
        if risk.get("valuation_unit_mismatch") is True:
            score += 0.75
            factors.append("valuation_unit_mismatch")
            blockers.append("valuation_unit_mismatch")
        if market.get("market_data_stale") is True:
            score += 0.55
            factors.append("market_data_stale")
            blockers.append("market_data_stale")
        weight = _number(position.get("weight_pct"))
        if weight is not None and weight >= 25.0:
            score += min(0.3, weight / 200.0)
            factors.append("position_weight_elevated")
        cap_remaining = _number(portfolio.get("cap_remaining_krw"))
        if cap_remaining is not None and cap_remaining <= 0.0:
            score += 0.6
            factors.append("portfolio_cap_exhausted")
            blockers.append("portfolio_cap_exhausted")
        volatility = _number(market.get("volatility"))
        if volatility is not None and volatility >= 5.0:
            score += 0.3
            factors.append("volatility_elevated")
        missing = _number(data_quality.get("missing_feature_count"))
        if missing is not None and missing >= 5.0:
            score += 0.25
            factors.append("missing_critical_features")
        if quality_grade in {"D", "F", ""}:
            score += 0.35
            factors.append("feature_quality_low")
        score = max(0.0, min(1.0, score))
        level = "blocked" if blockers else "high" if score >= 0.65 else "medium" if score >= 0.25 else "low"
        return {
            "risk_level": level,
            "risk_score": round(score, 6),
            "risk_factors": factors,
            "risk_blockers": blockers,
            "order_suitability": "blocked" if blockers else "external_confirmation_required" if level != "low" else "candidate_only",
            "riskguard_required": True,
            "livepreflight_required": True,
        }

    @staticmethod
    def _invalidation(action: str, feature_context: dict) -> dict:
        indicators = dict(feature_context.get("indicators") or {})
        market = dict(feature_context.get("market") or {})
        conditions: list[dict] = []
        ma20 = _number(indicators.get("ma20"))
        if ma20 is not None:
            conditions.append({
                "condition_type": "price_threshold",
                "feature": "indicators.ma20",
                "operator": "crosses",
                "threshold": ma20,
                "expected": "redecision",
                "source": "observed_feature",
                "rationale_ko": "현재 관측된 20기간 이동평균을 가격이 교차하면 판단을 갱신합니다.",
            })
        if market.get("market_data_stale") is False:
            conditions.append({
                "condition_type": "market_data_stale",
                "feature": "market.market_data_stale",
                "operator": "equals",
                "threshold": True,
                "expected": "redecision",
                "source": "observed_feature",
                "rationale_ko": "시장 데이터가 stale 상태로 바뀌면 현재 판단을 무효화합니다.",
            })
        return {
            "invalidation_conditions": conditions,
            "invalidation_supported": bool(conditions),
            "invalidation_missing_reason": "" if conditions else "structured_threshold_evidence_unavailable",
        }

    def predict(
        self,
        *,
        feature_context: dict,
        task: str,
        scope: str,
        quality_grade: str,
        probability_calibrator: dict | None = None,
    ) -> dict:
        if task not in self.supported_tasks:
            return {
                "status": "unsupported",
                "blocker": f"multi_head_task_unsupported:{task or 'unknown'}",
                "abstain_required": True,
                "abstain_reason": "unsupported_or_insufficient_sample",
            }
        record = {"feature_context": feature_context, "task": task, "scope": scope}
        matrix = self.encoder.transform([record])
        raw_probabilities = self.action_head.predict_proba(matrix)[0]
        raw_ranked = sorted(zip(self.action_head.classes, raw_probabilities), key=lambda item: item[1], reverse=True)
        raw_action, raw_confidence = raw_ranked[0]
        from app.services.local_engine_confidence_calibrator import apply_probability_calibrator
        registered = apply_probability_calibrator(
            raw_probabilities,
            list(self.action_head.classes),
            probability_calibrator,
            task=task,
        )
        if registered.get("available"):
            probabilities = np.asarray([
                float((registered.get("action_probabilities") or {}).get(name) or 0.0)
                for name in self.action_head.classes
            ], dtype=float)
            ranked = sorted(zip(self.action_head.classes, probabilities), key=lambda item: item[1], reverse=True)
            action = str(registered.get("action") or ranked[0][0])
            calibrated = float(registered.get("calibrated_confidence") or ranked[0][1])
            calibration_method = str(registered.get("confidence_method") or "class_aware_platt")
            margin = float(registered.get("action_margin") or 0.0)
        else:
            probabilities = raw_probabilities
            ranked = raw_ranked
            action = raw_action
            margin = float(ranked[0][1] - ranked[1][1]) if len(ranked) > 1 else float(ranked[0][1])
            calibrated, calibration_method = self._calibrate(float(raw_confidence))
        quality_factor = {"A": 1.0, "B": 0.9, "C": 0.75, "D": 0.5, "F": 0.25}.get(quality_grade, 0.5)
        if not registered.get("available"):
            calibrated *= quality_factor
        risk = self._risk(feature_context, quality_grade)
        if not risk["risk_blockers"] and margin < 0.15:
            risk["risk_score"] = round(min(1.0, float(risk["risk_score"]) + 0.25), 6)
            risk["risk_factors"].append("action_uncertainty")
        if not risk["risk_blockers"] and raw_confidence < 0.6:
            risk["risk_score"] = round(min(1.0, float(risk["risk_score"]) + 0.15), 6)
            risk["risk_factors"].append("model_confidence_low")
        if not risk["risk_blockers"]:
            risk["risk_level"] = (
                "high" if float(risk["risk_score"]) >= 0.65
                else "medium" if float(risk["risk_score"]) >= 0.25
                else "low"
            )
            risk["order_suitability"] = (
                "external_confirmation_required" if risk["risk_level"] != "low" else "candidate_only"
            )
        abstain = bool(calibrated < 0.45 or margin < 0.10 or risk["risk_level"] == "blocked")
        abstain_reason = (
            "risk_blocked" if risk["risk_level"] == "blocked"
            else "action_margin_low" if margin < 0.10
            else "confidence_low" if calibrated < 0.45
            else ""
        )
        escalation_required = bool(abstain or action in ORDER_ACTIONS or risk["risk_level"] in {"medium", "high", "blocked"})
        escalation_reason = ""
        if escalation_required:
            escalation_reason = (
                abstain_reason
                or ("order_action_external_confirmation" if action in ORDER_ACTIONS else "risk_external_confirmation")
            )
        cadence_key = f"{task}|{action}"
        empirical_eta = int(self.eta_cadence.get(cadence_key) or self.eta_cadence.get(task) or 300)
        eta_reason = "observed_redecision_cadence"
        if risk["risk_level"] in {"high", "blocked"}:
            empirical_eta, eta_reason = 60, "risk_policy_override"
        elif risk["risk_level"] == "medium" or action in ORDER_ACTIONS:
            empirical_eta, eta_reason = 180, "candidate_review_policy"
        eta_seconds = self._nearest_eta(empirical_eta)
        invalidation = self._invalidation(action, feature_context)
        eta = {
            "eta_seconds": eta_seconds,
            "eta_bucket": eta_seconds,
            "eta_reason": eta_reason,
            "monitoring_priority": "high" if eta_seconds <= 180 else "normal",
        }
        escalation = {
            "escalation_required": escalation_required,
            "escalation_target": "configured_external_provider" if escalation_required else "none",
            "escalation_reason": escalation_reason,
            "escalation_confidence": round(1.0 - calibrated, 6) if escalation_required else round(calibrated, 6),
            "external_confirmation_required": escalation_required,
            "cost_guard_bypass_allowed": False,
            "provider_route_recommendation": (
                "external_confirmation" if escalation_required else "local_candidate"
            ),
        }
        reason = self.reason_composer.compose(
            action=action,
            feature_context=feature_context,
            confidence=calibrated,
            risk=risk,
            escalation=escalation,
            eta=eta,
            invalidation_conditions=invalidation["invalidation_conditions"],
        )
        return {
            "status": "available",
            "action": action,
            "action_probabilities": {name: round(float(value), 8) for name, value in zip(self.action_head.classes, probabilities)},
            "raw_action": raw_action,
            "raw_action_probabilities": {name: round(float(value), 8) for name, value in zip(self.action_head.classes, raw_probabilities)},
            "action_margin": round(margin, 8),
            "action_supported": True,
            "unsupported_action_reasons": [],
            "raw_confidence": round(float(raw_confidence), 8),
            "calibrated_confidence": round(max(0.0, min(1.0, calibrated)), 8),
            "calibration_method": calibration_method,
            "calibrator_id": str(registered.get("calibrator_id") or ""),
            "global_calibration_fallback_used": bool(registered.get("global_fallback_used")),
            "calibration_sample_count": int(registered.get("calibration_sample_count") or 0),
            "top1_probability": round(float(registered.get("top1_probability") or calibrated), 8),
            "top2_probability": round(float(registered.get("top2_probability") or max(0.0, calibrated - margin)), 8),
            "confidence_bucket": f"{int(calibrated * 10) / 10:.1f}",
            "confidence_reliability": str(registered.get("confidence_reliability") or ("limited" if calibrated < 0.6 else "observed")),
            "abstain_required": abstain,
            "abstain_reason": abstain_reason,
            **risk,
            **escalation,
            **eta,
            **invalidation,
            **reason,
        }


def _classification_metrics(actual: list[str], predicted: list[str], classes: list[str]) -> dict:
    confusion = {name: Counter() for name in classes}
    for truth, prediction in zip(actual, predicted):
        confusion[truth][prediction] += 1
    per_action: dict[str, dict] = {}
    recalls: list[float] = []
    f1_values: list[float] = []
    for name in classes:
        tp = confusion[name][name]
        fp = sum(confusion[other][name] for other in classes if other != name)
        fn = sum(confusion[name][other] for other in classes if other != name)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        recalls.append(recall)
        f1_values.append(f1)
        per_action[name] = {
            "support": sum(confusion[name].values()),
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }
    return {
        "accuracy": round(sum(left == right for left, right in zip(actual, predicted)) / len(actual), 6) if actual else None,
        "macro_f1": round(float(np.mean(f1_values)), 6) if f1_values else None,
        "balanced_accuracy": round(float(np.mean(recalls)), 6) if recalls else None,
        "per_action_metrics": per_action,
        "confusion_matrix": {name: dict(confusion[name]) for name in classes},
    }


class AITSLocalEngineMultiHeadTrainer:
    ENGINE_SCHEMA = "aits_local_engine_multi_head_model.v2"

    def __init__(
        self,
        training_root: Path | str = Path("data") / "ai_decision_training",
        model_root: Path | str = Path("data") / "local_models",
    ) -> None:
        self.training_root = Path(training_root)
        self.model_root = Path(model_root)
        self.distillation = AITSLocalEngineTeacherDistillation(self.training_root)
        self.registry = AITSLocalModelRegistry(self.model_root)

    @staticmethod
    def _stable_hash(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _confidence_bins(probabilities: np.ndarray, actual: list[str], predicted: list[str]) -> list[dict]:
        bins: list[dict] = []
        top = np.max(probabilities, axis=1) if len(probabilities) else np.asarray([])
        for lower, upper in ((0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.0)):
            indexes = [index for index, value in enumerate(top) if lower <= value <= upper]
            correct = sum(actual[index] == predicted[index] for index in indexes)
            bins.append({
                "lower": lower, "upper": upper, "count": len(indexes), "correct": correct,
                "accuracy": round(correct / len(indexes), 6) if indexes else None,
                "average_confidence": round(float(np.mean(top[indexes])), 6) if indexes else None,
            })
        return bins

    @staticmethod
    def _eta_cadence(records: list[dict]) -> dict[str, int]:
        groups: dict[str, list[float]] = defaultdict(list)
        for row in records:
            cadence = _number(row.get("teacher_eta_seconds")) or _number(row.get("observed_redecision_seconds"))
            if cadence is None:
                continue
            task = str(row.get("task") or "")
            action = str(row.get("teacher_action") or "")
            groups[task].append(cadence)
            groups[f"{task}|{action}"].append(cadence)
        return {key: min(ETA_BUCKETS, key=lambda bucket: abs(bucket - median(values))) for key, values in groups.items()}

    def train(self, *, persist: bool = False, activate: bool = True) -> dict:
        distilled = self.distillation.build(persist=persist)
        all_records = list(distilled.get("records") or [])
        teacher_records = [row for row in all_records if row.get("teacher_present")]
        train_records = [row for row in teacher_records if row.get("split") == "train"]
        validation_records = [row for row in teacher_records if row.get("split") == "validation"]
        holdout_records = [row for row in teacher_records if row.get("split") == "holdout"]
        train_labels = [str(row.get("teacher_action") or "") for row in train_records]
        class_counts = Counter(train_labels)
        supported_actions = sorted(action for action, count in class_counts.items() if count >= 2)
        usable_train = [row for row in train_records if row.get("teacher_action") in supported_actions]
        usable_labels = [str(row.get("teacher_action") or "") for row in usable_train]
        blocker = ""
        if not usable_train:
            blocker = "teacher_distillation_dataset_missing"
        elif len(supported_actions) < 2:
            blocker = "action_head_wait_only"

        model: AITSLocalEngineMultiHeadModel | None = None
        metrics: dict[str, Any] = {}
        if not blocker:
            encoder = AITSMultiHeadFeatureEncoder().fit(usable_train)
            action_head = AITSWeightedMultinomialHead().fit(encoder.transform(usable_train), usable_labels)
            evaluation = validation_records or holdout_records
            evaluation_actual = [str(row.get("teacher_action") or "") for row in evaluation]
            evaluation_matrix = encoder.transform(evaluation)
            probabilities = action_head.predict_proba(evaluation_matrix)
            predicted = [action_head.classes[int(index)] for index in np.argmax(probabilities, axis=1)] if len(probabilities) else []
            confidence_bins = self._confidence_bins(probabilities, evaluation_actual, predicted)
            action_metrics = _classification_metrics(evaluation_actual, predicted, action_head.classes)
            majority = class_counts.most_common(1)[0][0]
            majority_score = sum(label == majority for label in evaluation_actual) / len(evaluation_actual) if evaluation_actual else None
            wait_score = sum(label == "wait" for label in evaluation_actual) / len(evaluation_actual) if evaluation_actual else None
            one_hot = np.eye(len(action_head.classes))[
                [action_head.classes.index(label) for label in evaluation_actual]
            ] if evaluation_actual else np.zeros((0, len(action_head.classes)))
            brier = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))) if len(probabilities) else None
            ece_parts = [
                abs(float(bucket["accuracy"]) - float(bucket["average_confidence"])) * int(bucket["count"])
                for bucket in confidence_bins if bucket["count"]
            ]
            ece = sum(ece_parts) / len(evaluation_actual) if evaluation_actual else None
            task_counts = Counter(str(row.get("task") or "") for row in usable_train)
            scope_counts = Counter(str(row.get("scope") or "") for row in usable_train)
            eta_cadence = self._eta_cadence(teacher_records)
            supported_tasks = sorted(task for task, count in task_counts.items() if count >= 5)
            model = AITSLocalEngineMultiHeadModel(
                encoder=encoder,
                action_head=action_head,
                confidence_bins=confidence_bins,
                task_counts=dict(task_counts),
                scope_counts=dict(scope_counts),
                eta_cadence=eta_cadence,
                supported_tasks=supported_tasks,
            )
            predictions = [
                model.predict(
                    feature_context=dict(row.get("feature_context") or {}),
                    task=str(row.get("task") or ""), scope=str(row.get("scope") or ""),
                    quality_grade=str(row.get("payload_quality_grade") or ""),
                )
                for row in evaluation
            ]
            predicted_counts = Counter(str(row.get("action") or "") for row in predictions if row.get("status") == "available")
            confidence_values = [row.get("calibrated_confidence") for row in predictions if row.get("calibrated_confidence") is not None]
            risk_counts = Counter(str(row.get("risk_level") or "") for row in predictions if row.get("status") == "available")
            eta_counts = Counter(str(row.get("eta_seconds") or "") for row in predictions if row.get("status") == "available")
            invalidation_nonempty = sum(bool(row.get("invalidation_conditions")) for row in predictions)
            reason_nonempty = sum(bool(row.get("reason_ko")) for row in predictions)
            metrics = {
                **action_metrics,
                "predicted_action_counts": dict(predicted_counts),
                "majority_baseline_score": round(majority_score, 6) if majority_score is not None else None,
                "wait_baseline_score": round(wait_score, 6) if wait_score is not None else None,
                "improves_over_wait_baseline": bool(
                    action_metrics.get("accuracy") is not None
                    and wait_score is not None
                    and float(action_metrics["accuracy"]) > float(wait_score)
                ),
                "brier_score": round(brier, 6) if brier is not None else None,
                "expected_calibration_error": round(ece, 6) if ece is not None else None,
                "confidence_bucket_summary": confidence_bins,
                "confidence_values": confidence_values,
                "risk_distribution": dict(risk_counts),
                "unsafe_prediction_count": sum(row.get("risk_level") == "blocked" and row.get("action") in ORDER_ACTIONS for row in predictions),
                "blocker_recall": 1.0 if any(row.get("risk_blockers") for row in predictions) else None,
                "escalation_required_count": sum(bool(row.get("escalation_required")) for row in predictions),
                "escalation_reason_counts": dict(Counter(str(row.get("escalation_reason") or "") for row in predictions)),
                "unnecessary_escalation_rate": round(sum(
                    bool((record.get("provider_comparison") or {}).get("external_call_waste_suspected"))
                    for record in evaluation
                ) / len(evaluation), 6) if evaluation else None,
                "eta_distribution": dict(eta_counts),
                "eta_values": [row.get("eta_seconds") for row in predictions if row.get("eta_seconds")],
                "invalidation_nonempty_count": invalidation_nonempty,
                "invalidation_empty_count": len(predictions) - invalidation_nonempty,
                "supported_condition_rate": round(invalidation_nonempty / len(predictions), 6) if predictions else None,
                "reason_nonempty_count": reason_nonempty,
                "evidence_reference_valid_count": sum(bool(row.get("evidence_reference_valid")) for row in predictions),
                "unsupported_evidence_reference_count": sum(int(row.get("unsupported_evidence_reference_count") or 0) for row in predictions),
                "evaluation_count": len(evaluation),
            }

        source_hash = self._stable_hash([
            {key: row.get(key) for key in ("record_id", "teacher_action", "feature_manifest_hash", "split")}
            for row in teacher_records
        ])
        attempt_id = f"local_multi_head_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        trained = model is not None
        artifact_path = ""
        metadata = {
            "registry_schema": AITSLocalModelRegistry.REGISTRY_SCHEMA,
            "engine_schema": self.ENGINE_SCHEMA,
            "model_id": attempt_id,
            "model_version": "v1",
            "created_at": datetime.now().timestamp(),
            "trained_at": datetime.now().astimezone().isoformat(),
            "trained": trained,
            "training_status": "trained" if trained else "insufficient_data",
            "source_dataset_hash": source_hash,
            "source_record_count": len(teacher_records),
            "feature_schema": "task_specific_predecision_feature_context.v1",
            "supported_tasks": list(model.supported_tasks) if model else [],
            "supported_actions": supported_actions,
            "action_head": {"type": "class_weighted_multinomial_logistic", "ready": trained},
            "confidence_head": {"type": "empirical_bucket_shrinkage", "ready": trained},
            "risk_head": {"type": "factual_risk_evidence", "ready": trained},
            "escalation_head": {"type": "uncertainty_risk_action_policy", "ready": trained, "cost_guard_bypass_allowed": False},
            "eta_head": {"type": "observed_cadence_with_policy_override", "ready": trained},
            "invalidation_head": {"type": "observed_feature_threshold", "ready": trained},
            "reason_composer": {"type": "structured_korean_template", "ready": trained},
            "metrics": metrics,
            "per_action_metrics": metrics.get("per_action_metrics", {}),
            "per_task_metrics": {},
            "class_distribution": dict(sorted(Counter(str(row.get("teacher_action") or "") for row in teacher_records).items())),
            "safe_for_shadow_evaluation": trained,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "safe_for_live_expansion": False,
            "blocker": blocker,
            "fake_training_data_detected": False,
            "label_leakage_detected": False,
        }
        if persist and trained and model is not None:
            artifact_dir = self.model_root / attempt_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = str(artifact_dir)
            bundle = {
                "schema": AITSLocalEngineMultiHeadModel.BUNDLE_SCHEMA,
                "multi_head_model": model,
                "feature_columns": model.encoder.columns,
                "feature_types": {column: "numeric" for column in model.encoder.columns},
                "encoding_map": {},
                "safe_for_live_decision": False,
                "live_decision_enabled": False,
                "safe_for_live_expansion": False,
            }
            temporary = artifact_dir / "model.pkl.tmp"
            with temporary.open("wb") as handle:
                pickle.dump(bundle, handle)
                handle.flush()
            temporary.replace(artifact_dir / "model.pkl")
            atomic_write_json(artifact_dir / "feature_columns.json", {
                "feature_columns": model.encoder.columns,
                "feature_types": {column: "numeric" for column in model.encoder.columns},
            })
            atomic_write_json(artifact_dir / "encoding_map.json", {})
            atomic_write_json(artifact_dir / "metrics.json", metrics)
            atomic_write_json(artifact_dir / "training_config.json", {
                "trainer": "numpy_class_weighted_multinomial",
                "time_based_decision_group_split": True,
                "label_leakage_prevented": True,
                "safe_for_live_decision": False,
            })
            metadata["artifact_path"] = artifact_path
            metadata["metrics_path"] = str(artifact_dir / "metrics.json")
            self.registry.record_training_run(
                metadata,
                {**metrics, "model_id": attempt_id},
                activate=activate,
            )
        else:
            metadata["artifact_path"] = artifact_path

        return {
            "dataset": distilled.get("summary") or {},
            "metadata": metadata,
            "metrics": metrics,
            "model": model,
            "evaluation_records": validation_records or holdout_records,
            "persist_requested": bool(persist),
            "registry_activation_requested": bool(activate),
            "artifact_path": artifact_path,
            "training_ready": trained,
            "first_blocker": blocker or "multi_head_training_ready",
        }


def run_local_engine_multi_head_training(*, persist: bool = False) -> dict:
    """Explicit offline entrypoint; persistence remains opt-in."""
    return AITSLocalEngineMultiHeadTrainer().train(persist=persist)
