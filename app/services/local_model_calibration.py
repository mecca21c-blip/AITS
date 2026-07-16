from __future__ import annotations

from collections import Counter
import hashlib
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Optional

from app.services.local_training_dataset_curation import (
    atomic_write_json,
    read_json_dict,
    read_recoverable_jsonl,
)


class AITSLocalModelCalibration:
    """Build conservative routing recommendations from observed LOCAL_MODEL outcomes."""

    PROFILE_SCHEMA = "aits_local_model_calibration_profile.v1"
    MIN_CALIBRATION_RECORDS = 30
    MIN_GROUP_RECORDS = 10
    MIN_LIVE_EXPANSION_RECORDS = 100
    BUCKETS = ((0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.000001))
    ORDER_GROUPS = {"buy_add", "sell_reduce", "take_profit_stop_loss", "rotate"}

    def __init__(
        self,
        training_root: Path | str = Path("data") / "ai_decision_training",
        model_root: Path | str = Path("data") / "local_models",
        candidate_path: Path | str | None = None,
    ) -> None:
        self.training_root = Path(training_root)
        self.model_root = Path(model_root)
        self.candidate_path = Path(candidate_path) if candidate_path is not None else (
            self.training_root.parent / "local_engine" / "local_engine_candidate_observations.jsonl"
        )
        self.source_paths = {
            "outcomes": self.training_root / "outcome_records.jsonl",
            "providers": self.training_root / "provider_comparison_outcomes.jsonl",
            "curated": self.training_root / "curated_local_training_records.jsonl",
            "features": self.training_root / "local_training_features.jsonl",
        }
        self.registry_path = self.model_root / "registry.json"
        self.latest_model_path = self.model_root / "latest_model.json"
        self.metrics_path = self.model_root / "latest_training_metrics.json"
        self.profile_path = self.model_root / "calibration_profile.json"
        self.history_path = self.model_root / "calibration_history.jsonl"
        self.summary_path = self.model_root / "latest_calibration_summary.json"

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_json(path: Path) -> dict:
        return read_json_dict(path)

    @staticmethod
    def _stable_hash(value: Any, length: int = 32) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:length]

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        atomic_write_json(path, value)

    @staticmethod
    def _read_jsonl(path: Path) -> tuple[list[dict], int]:
        rows, metrics = read_recoverable_jsonl(path)
        corrupted = metrics["corrupted_lines"] + metrics["nul_lines_recovered"]
        return rows, corrupted

    @staticmethod
    def _decision_id(row: dict) -> str:
        return str(row.get("decision_id") or row.get("source_decision_id") or "")

    @staticmethod
    def _action_group(action: Any, task: Any = "") -> str:
        value = str(action or "").lower()
        if str(task or "") == "portfolio_management_decision":
            return "portfolio"
        if value in {"wait", "hold"}:
            return "wait_hold"
        if value in {"buy", "add"}:
            return "buy_add"
        if value in {"sell", "reduce"}:
            return "sell_reduce"
        if value in {"take_profit", "stop_loss"}:
            return "take_profit_stop_loss"
        if value == "rotate":
            return "rotate"
        return "unknown"

    @classmethod
    def _model_action_correct(cls, action: str, label: str, score: float, final_action: str) -> bool:
        positive_labels = {
            "good_wait", "avoided_loss", "good_buy", "good_sell", "good_take_profit",
            "good_stop_loss", "useful_rotation", "good_rotation",
        }
        negative_labels = {
            "missed_opportunity", "bad_wait", "bad_buy", "early_sell", "bad_take_profit",
            "bad_stop_loss", "bad_rotation",
        }
        group = cls._action_group(action)
        if group == "wait_hold":
            return label in {"good_wait", "avoided_loss"} or (score >= 0.0 and label not in negative_labels)
        if group == "buy_add":
            return label == "good_buy" or (action == final_action and score > 0.0)
        if group == "sell_reduce":
            return label in {"good_sell", "avoided_loss"} or (action == final_action and score > 0.0)
        if group == "take_profit_stop_loss":
            return label in {"good_take_profit", "good_stop_loss", "avoided_loss"}
        if group == "rotate":
            return label in {"useful_rotation", "good_rotation"}
        return bool(action == final_action and (label in positive_labels or score > 0.0))

    @staticmethod
    def _contains_unsafe_source(row: dict) -> bool:
        flags = (
            row.get("fake_data"), row.get("synthetic_data"), row.get("manual_or_forced_action"),
            row.get("valuation_unit_mismatch"), row.get("reconciliation_missing"),
        )
        return any(value is True for value in flags)

    @staticmethod
    def _candidate_contract_errors(row: dict) -> list[str]:
        errors: list[str] = []
        if row.get("candidate_only") is not True:
            errors.append("candidate_only_not_true")
        if row.get("applied_to_final_action") is not False:
            errors.append("applied_to_final_action_not_false")
        if row.get("safe_for_live_decision") is not False:
            errors.append("safe_for_live_decision_not_false")
        if row.get("live_decision_enabled") is not False:
            errors.append("live_decision_enabled_not_false")
        if row.get("fake_prediction") is not False:
            errors.append("fake_prediction_not_false")
        if not str(row.get("action") or "").strip():
            errors.append("missing_action")
        if AITSLocalModelCalibration._number(row.get("confidence")) is None:
            errors.append("missing_confidence")
        if not str(row.get("prediction_id") or "") and not str(row.get("outcome_linkage_key") or ""):
            errors.append("missing_join_key")
        return errors

    def load_candidate_observations(self) -> dict:
        rows, read_metrics = read_recoverable_jsonl(self.candidate_path)
        raw_payload = self.candidate_path.read_bytes() if self.candidate_path.exists() else b""
        valid_rows: list[dict] = []
        invalid_rows: list[dict] = []
        prediction_index: dict[str, dict] = {}
        linkage_index: dict[str, dict] = {}
        invalid_prediction_ids: set[str] = set()
        invalid_linkage_keys: set[str] = set()
        duplicate_prediction_ids = 0
        duplicate_linkage_keys = 0

        for row in rows:
            candidate = dict(row)
            errors = self._candidate_contract_errors(candidate)
            if errors:
                candidate["candidate_contract_errors"] = errors
                invalid_rows.append(candidate)
                prediction_id = str(candidate.get("prediction_id") or "")
                linkage_key = str(candidate.get("outcome_linkage_key") or "")
                if prediction_id:
                    invalid_prediction_ids.add(prediction_id)
                if linkage_key:
                    invalid_linkage_keys.add(linkage_key)
                continue
            valid_rows.append(candidate)

        def newest(existing: dict | None, candidate: dict) -> dict:
            if not existing:
                return candidate
            existing_key = (str(existing.get("created_at") or ""), self._stable_hash(existing))
            candidate_key = (str(candidate.get("created_at") or ""), self._stable_hash(candidate))
            return candidate if candidate_key >= existing_key else existing

        for candidate in valid_rows:
            prediction_id = str(candidate.get("prediction_id") or "")
            linkage_key = str(candidate.get("outcome_linkage_key") or "")
            if prediction_id:
                if prediction_id in prediction_index:
                    duplicate_prediction_ids += 1
                prediction_index[prediction_id] = newest(prediction_index.get(prediction_id), candidate)
            if linkage_key:
                if linkage_key in linkage_index:
                    duplicate_linkage_keys += 1
                linkage_index[linkage_key] = newest(linkage_index.get(linkage_key), candidate)

        return {
            "candidate_observation_source_loaded": self.candidate_path.exists(),
            "candidate_observation_records_count": len(rows),
            "candidate_observation_valid_count": len(valid_rows),
            "candidate_observation_invalid_count": len(invalid_rows),
            "candidate_observation_corrupt_count": int(read_metrics.get("corrupted_lines") or 0)
            + int(read_metrics.get("nul_lines_recovered") or 0),
            "candidate_observation_nul_recovered_count": int(read_metrics.get("nul_lines_recovered") or 0),
            "candidate_observation_partial_line_count": int(bool(raw_payload) and not raw_payload.endswith(b"\n")),
            "candidate_prediction_id_index_count": len(prediction_index),
            "candidate_linkage_key_index_count": len(linkage_index),
            "candidate_duplicate_prediction_id_count": duplicate_prediction_ids,
            "candidate_duplicate_linkage_key_count": duplicate_linkage_keys,
            "fake_prediction_detected": any(row.get("fake_prediction") is not False for row in rows),
            "unsafe_candidate_contract_detected": bool(invalid_rows),
            "prediction_index": prediction_index,
            "linkage_index": linkage_index,
            "invalid_prediction_ids": invalid_prediction_ids,
            "invalid_linkage_keys": invalid_linkage_keys,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
        }

    @staticmethod
    def _join_candidate_to_outcome(outcome: dict, candidate_source: dict) -> tuple[dict, str, str]:
        row = dict(outcome)
        prediction_index = candidate_source["prediction_index"]
        linkage_index = candidate_source["linkage_index"]
        prediction_id = str(row.get("local_engine_prediction_id") or "")
        linkage_key = str(row.get("local_engine_outcome_linkage_key") or "")
        observation_ids = row.get("local_engine_candidate_observation_ids") or []
        if not isinstance(observation_ids, list):
            observation_ids = [observation_ids]

        candidate: dict | None = None
        method = ""
        if prediction_id and prediction_id in prediction_index:
            candidate = prediction_index[prediction_id]
            method = "prediction_id"
        elif linkage_key and linkage_key in linkage_index:
            candidate = linkage_index[linkage_key]
            method = "outcome_linkage_key"
        else:
            for observation_id in observation_ids:
                exact_id = str(observation_id or "")
                if exact_id and exact_id in prediction_index:
                    candidate = prediction_index[exact_id]
                    method = "observation_id"
                    break

        has_linkage = bool(prediction_id or linkage_key or any(str(value or "") for value in observation_ids))
        invalid_match = bool(
            (prediction_id and prediction_id in candidate_source["invalid_prediction_ids"])
            or (linkage_key and linkage_key in candidate_source["invalid_linkage_keys"])
        )
        if candidate is None:
            status = "invalid_candidate" if invalid_match else ("missing" if has_linkage else "not_applicable")
            row["local_engine_candidate_join_status"] = status
            row["local_engine_candidate_join_method"] = ""
            return row, status, ""

        action = str(candidate.get("action") or "").lower()
        row.update({
            "local_model_prediction": action,
            "local_model_action": action,
            "local_model_confidence": candidate.get("confidence"),
            "local_model_risk": str(candidate.get("risk_level") or ""),
            "local_model_risk_level": str(candidate.get("risk_level") or ""),
            "local_model_eta_seconds": candidate.get("eta_seconds"),
            "local_model_evidence": list(candidate.get("evidence") or []),
            "local_model_blockers": list(candidate.get("blockers") or []),
            "local_engine_prediction_id": str(candidate.get("prediction_id") or prediction_id),
            "local_engine_outcome_linkage_key": str(candidate.get("outcome_linkage_key") or linkage_key),
            "local_engine_candidate_join_status": "matched",
            "local_engine_candidate_join_method": method,
        })
        return row, "matched", method

    def load_sources(self) -> dict:
        rows_by_source: dict[str, list[dict]] = {}
        corrupted = 0
        source_count = 0
        for name, path in self.source_paths.items():
            rows, bad = self._read_jsonl(path)
            rows_by_source[name] = rows
            source_count += len(rows)
            corrupted += bad

        candidate_source = self.load_candidate_observations()
        original_outcomes = rows_by_source["outcomes"]
        prediction_before_join = sum(bool(row.get("local_model_prediction") or row.get("local_model_action")) for row in original_outcomes)
        outcome_matched_before_join = sum(bool(
            (row.get("local_model_prediction") or row.get("local_model_action"))
            and row.get("outcome_label")
            and self._number(row.get("outcome_score")) is not None
        ) for row in original_outcomes)
        join_methods: Counter[str] = Counter()
        join_statuses: Counter[str] = Counter()
        joined_outcomes: list[dict] = []
        for outcome in original_outcomes:
            joined, status, method = self._join_candidate_to_outcome(outcome, candidate_source)
            joined_outcomes.append(joined)
            if status != "not_applicable":
                join_statuses[status] += 1
            if method:
                join_methods[method] += 1
        rows_by_source["outcomes"] = joined_outcomes
        prediction_after_join = sum(bool(row.get("local_model_prediction") or row.get("local_model_action")) for row in joined_outcomes)
        outcome_matched_after_join = sum(bool(
            (row.get("local_model_prediction") or row.get("local_model_action"))
            and row.get("outcome_label")
            and self._number(row.get("outcome_score")) is not None
        ) for row in joined_outcomes)

        merged: dict[str, dict] = {}
        duplicate_ids: set[str] = set()
        seen_signatures: set[tuple[str, str, str]] = set()
        missing_decision_rows = 0
        for source_name in ("outcomes", "providers", "curated", "features"):
            for row in rows_by_source[source_name]:
                decision_id = self._decision_id(row)
                if not decision_id:
                    missing_decision_rows += 1
                    continue
                signature = (source_name, decision_id, self._stable_hash(row))
                if signature in seen_signatures:
                    duplicate_ids.add(decision_id)
                    continue
                seen_signatures.add(signature)
                target = merged.setdefault(decision_id, {"decision_id": decision_id, "source_names": []})
                target["source_names"].append(source_name)
                previous = dict(target.get(source_name) or {})
                previous_time = float(previous.get("evaluated_at") or previous.get("curated_at") or previous.get("feature_built_at") or 0.0)
                row_time = float(row.get("evaluated_at") or row.get("curated_at") or row.get("feature_built_at") or 0.0)
                if not previous or row_time >= previous_time:
                    target[source_name] = row

        prediction_records = 0
        outcome_matched_count = 0
        matched: list[dict] = []
        excluded: list[dict] = [
            {"decision_id": "", "exclusion_reasons": ["missing_decision_id"]}
            for _ in range(missing_decision_rows)
        ]
        for decision_id, source in sorted(merged.items()):
            outcome = dict(source.get("outcomes") or {})
            curated = dict(source.get("curated") or {})
            feature = dict(source.get("features") or {})
            model_prediction = str(
                outcome.get("local_model_prediction")
                or outcome.get("local_model_action")
                or curated.get("local_model_prediction")
                or curated.get("local_model_action")
                or ""
            ).lower()
            model_confidence = self._number(
                outcome.get("local_model_confidence", curated.get("local_model_confidence"))
            )
            model_risk_score = self._number(
                outcome.get("local_model_risk_score", curated.get("local_model_risk_score"))
            )
            model_provider_score = self._number(
                outcome.get("model_provider_value_score", curated.get("model_provider_value_score"))
            )
            if model_prediction:
                prediction_records += 1
            label = str(outcome.get("outcome_label") or curated.get("final_outcome_label") or "")
            score = self._number(outcome.get("outcome_score", curated.get("final_outcome_score")))
            if model_prediction and label and score is not None:
                outcome_matched_count += 1
            final_action = str(
                (outcome.get("final_decision") or {}).get("action")
                or curated.get("final_action") or ""
            ).lower()
            final_provider = str(
                (outcome.get("final_decision") or {}).get("provider")
                or curated.get("final_provider_source") or ""
            )
            task = str(outcome.get("task") or curated.get("task") or feature.get("task") or "")
            submitted = int(curated.get("order_submitted") or outcome.get("submitted") or 0)
            order_result = curated.get("order_result") or outcome.get("execution_result") or {}
            source_safe = bool(
                outcome.get("safe_for_local_training")
                or curated.get("safe_for_local_training")
                or feature.get("safe_for_model_training")
            )
            reasons: list[str] = []
            if not model_prediction:
                reasons.append("missing_local_model_prediction")
            if model_confidence is None:
                reasons.append("missing_local_model_confidence")
            if not label or score is None or label in {"data_unavailable", "inconclusive"}:
                reasons.append("missing_or_inconclusive_outcome")
            if not source_safe:
                reasons.append("source_not_safe_for_calibration")
            if submitted and not order_result:
                reasons.append("submitted_order_reconciliation_missing")
            if self._contains_unsafe_source({**outcome, **curated}):
                reasons.append("unsafe_or_unresolved_source")
            if decision_id in duplicate_ids:
                reasons.append("duplicate_decision_id")
            record = {
                "decision_id": decision_id,
                "model_id": str(outcome.get("local_model_id") or curated.get("local_model_id") or ""),
                "session_id": str(outcome.get("session_id") or curated.get("session_id") or ""),
                "task": task,
                "scope": str(outcome.get("scope") or curated.get("scope") or ""),
                "symbol": str(outcome.get("symbol") or curated.get("symbol") or ""),
                "model_recommended_action": model_prediction,
                "model_confidence": model_confidence,
                "model_action_quality_score": self._number(outcome.get("model_action_quality_score", curated.get("model_action_quality_score"))),
                "model_provider_value_score": model_provider_score,
                "model_risk_score": model_risk_score,
                "final_action": final_action,
                "final_provider_source": final_provider,
                "actual_order": bool(curated.get("actual_order") or outcome.get("actual_order")),
                "submitted": submitted,
                "outcome_label": label,
                "outcome_score": score,
                "price_change_pct": self._number((outcome.get("checkpoint") or {}).get("price_change_pct")),
                "pnl_change_pct": self._number((outcome.get("checkpoint") or {}).get("pnl_change_pct")),
                "opportunity_cost_label": str(curated.get("opportunity_cost_label") or ""),
                "provider_value_label": str(curated.get("provider_value_label") or ""),
                "exclusion_reasons": sorted(set(reasons)),
            }
            if reasons:
                excluded.append(record)
                continue
            correct = self._model_action_correct(model_prediction, label, float(score), final_action)
            risk_correct = bool(
                model_risk_score is not None
                and ((model_risk_score >= 0.5 and score >= 0.0) or (model_risk_score < 0.5 and score < 0.0))
            )
            provider_correct = bool(
                model_provider_score is not None
                and ((model_provider_score >= 0.0 and score >= 0.0) or (model_provider_score < 0.0 and score < 0.0))
            )
            record.update({
                "model_prediction_matched_to_outcome": True,
                "model_action_correct": correct,
                "model_risk_prediction_correct": risk_correct,
                "model_provider_value_prediction_correct": provider_correct,
                "model_overconfident": bool(model_confidence >= 0.85 and not correct),
                "model_underconfident": bool(model_confidence < 0.5 and correct),
                "model_safe_wait_correct": bool(self._action_group(model_prediction, task) == "wait_hold" and correct),
                "model_missed_opportunity": label == "missed_opportunity",
                "model_risky_action_detected": bool(self._action_group(model_prediction, task) in self.ORDER_GROUPS and score < 0.0),
                "model_prediction_outcome_score": float(score) if correct else -abs(float(score)),
                "action_group": self._action_group(model_prediction, task),
            })
            matched.append(record)
        missing_prediction_after_join = sum(
            "missing_local_model_prediction" in row.get("exclusion_reasons", []) for row in excluded
        )
        missing_confidence_after_join = sum(
            "missing_local_model_confidence" in row.get("exclusion_reasons", []) for row in excluded
        )
        if candidate_source["fake_prediction_detected"]:
            first_blocker = "fake_prediction_detected"
        elif candidate_source["unsafe_candidate_contract_detected"]:
            first_blocker = "unsafe_candidate_contract_detected"
        elif not candidate_source["candidate_observation_source_loaded"]:
            first_blocker = "candidate_observation_source_missing"
        elif candidate_source["candidate_observation_corrupt_count"]:
            first_blocker = "candidate_observation_parse_failed"
        elif not candidate_source["candidate_observation_valid_count"]:
            first_blocker = "candidate_observation_no_valid_records"
        elif not any(
            row.get("local_engine_prediction_id")
            or row.get("local_engine_outcome_linkage_key")
            or row.get("local_engine_candidate_observation_ids")
            for row in original_outcomes
        ):
            first_blocker = "outcome_linkage_fields_missing"
        elif not join_statuses["matched"]:
            first_blocker = "candidate_join_no_matches"
        elif not prediction_after_join:
            first_blocker = "local_model_prediction_still_zero_after_join"
        elif not matched:
            first_blocker = "calibration_usable_zero_after_join"
        else:
            first_blocker = "calibration_loader_candidate_join_ready"

        return {
            "rows_by_source": rows_by_source,
            "records": matched,
            "excluded": excluded,
            "calibration_source_records_count": source_count,
            "local_model_prediction_records_count": prediction_records,
            "outcome_matched_records_count": outcome_matched_count,
            "calibration_usable_records_count": len(matched),
            "calibration_excluded_records_count": len(excluded),
            "calibration_source_empty": source_count == 0,
            "calibration_data_insufficient": len(matched) < self.MIN_CALIBRATION_RECORDS,
            "corrupted_source_records_count": corrupted,
            "duplicate_decision_ids_count": len(duplicate_ids),
            **{
                key: value for key, value in candidate_source.items()
                if key not in {
                    "prediction_index", "linkage_index", "invalid_prediction_ids",
                    "invalid_linkage_keys", "valid_rows", "invalid_rows",
                }
            },
            "outcome_records_with_prediction_id": sum(bool(row.get("local_engine_prediction_id")) for row in original_outcomes),
            "outcome_records_with_linkage_key": sum(bool(row.get("local_engine_outcome_linkage_key")) for row in original_outcomes),
            "candidate_join_matched_count": int(join_statuses["matched"]),
            "candidate_join_missing_count": int(join_statuses["missing"]),
            "candidate_join_invalid_count": int(join_statuses["invalid_candidate"]),
            "candidate_join_method_counts": dict(join_methods),
            "local_model_prediction_records_before_join": prediction_before_join,
            "local_model_prediction_records_after_join": prediction_after_join,
            "outcome_matched_before_join": outcome_matched_before_join,
            "outcome_matched_after_join": outcome_matched_after_join,
            "calibration_usable_after_join": len(matched),
            "missing_local_model_prediction_after_join": missing_prediction_after_join,
            "missing_local_model_confidence_after_join": missing_confidence_after_join,
            "first_blocker": first_blocker,
        }

    def _confidence_calibration(self, records: list[dict]) -> dict:
        buckets: list[dict] = []
        threshold: Optional[float] = None
        for lower, upper in self.BUCKETS:
            rows = [row for row in records if lower <= float(row["model_confidence"]) < upper]
            correct = sum(bool(row.get("model_action_correct")) for row in rows)
            summary = {
                "range": f"{lower:.2f}-{min(upper, 1.0):.2f}",
                "count": len(rows),
                "correct_rate": round(correct / len(rows), 6) if rows else None,
                "average_outcome_score": round(sum(float(row["outcome_score"]) for row in rows) / len(rows), 6) if rows else None,
            }
            buckets.append(summary)
            if threshold is None and len(rows) >= self.MIN_GROUP_RECORDS and summary["correct_rate"] >= 0.7:
                threshold = lower
        sufficient = len(records) >= self.MIN_CALIBRATION_RECORDS
        return {
            "confidence_calibration_ready": True,
            "confidence_bucket_summary": buckets,
            "high_confidence_error_count": sum(bool(row.get("model_overconfident")) for row in records),
            "low_confidence_success_count": sum(bool(row.get("model_underconfident")) for row in records),
            "recommended_confidence_threshold": threshold if sufficient else None,
            "minimum_confidence_for_local_final": threshold if sufficient else None,
            "confidence_calibration_status": "evaluated" if sufficient else ("no_data" if not records else "insufficient_data"),
        }

    def _group_calibration(self, records: list[dict], key: str) -> dict:
        result: dict[str, dict] = {}
        for name in sorted(set(str(row.get(key) or "unknown") for row in records)):
            rows = [row for row in records if str(row.get(key) or "unknown") == name]
            correct = sum(bool(row.get("model_action_correct")) for row in rows)
            enough = len(rows) >= self.MIN_GROUP_RECORDS
            rate = correct / len(rows) if rows else 0.0
            result[name] = {
                "count": len(rows), "correct_rate": round(rate, 6) if rows else None,
                "status": "reliable" if enough and rate >= 0.7 else ("weak" if enough else "insufficient_sample"),
            }
        return result

    def analyze(self, source: dict) -> dict:
        records = list(source.get("records") or [])
        by_action = self._group_calibration(records, "action_group")
        by_task = self._group_calibration(records, "task")
        reliable_actions = sorted(name for name, value in by_action.items() if value["status"] == "reliable")
        weak_actions = sorted(name for name, value in by_action.items() if value["status"] == "weak")
        reliable_tasks = sorted(name for name, value in by_task.items() if value["status"] == "reliable")
        weak_tasks = sorted(name for name, value in by_task.items() if value["status"] == "weak")
        confidence = self._confidence_calibration(records)
        unsafe_count = sum(bool(row.get("model_risky_action_detected")) for row in records)
        risk_rows = [row for row in records if row.get("model_risk_score") is not None]
        risk_correct = sum(bool(row.get("model_risk_prediction_correct")) for row in risk_rows)
        data_sufficient = len(records) >= self.MIN_CALIBRATION_RECORDS
        final_allowed = [name for name in reliable_actions if name in {"wait_hold", "portfolio"}]
        external_required = sorted(self.ORDER_GROUPS | (set(weak_actions) - {"unknown"}))
        routing = {
            "local_model_final_allowed_action_groups": final_allowed,
            "local_model_external_confirmation_required_action_groups": external_required,
            "local_model_min_confidence_by_action": {
                name: confidence["recommended_confidence_threshold"] for name in final_allowed
            },
            "local_model_min_confidence_by_task": {
                name: confidence["recommended_confidence_threshold"] for name in reliable_tasks
            },
            "local_model_escalate_to_external_when": [
                "order_capable_action", "calibration_insufficient", "weak_action_group",
                "weak_task_group", "safety_blocker", "provider_disagreement",
            ],
            "local_model_never_final_when": [
                "critical_feature_missing", "risk_or_safety_blocker", "registry_live_disabled",
                "validator_rejected", "calibration_profile_unsafe",
            ],
            "local_model_safe_wait_hold_only_when": "calibrated_reliable_and_registry_approved",
            "local_model_policy_update_applied": False,
        }
        return {
            "prediction_outcome_matcher_ready": True,
            "model_prediction_matched_to_outcome_count": len(records),
            "model_action_correct_count": sum(bool(row.get("model_action_correct")) for row in records),
            "model_risk_prediction_correct_count": sum(bool(row.get("model_risk_prediction_correct")) for row in records),
            "model_provider_value_prediction_correct_count": sum(bool(row.get("model_provider_value_prediction_correct")) for row in records),
            "confidence_calibration": confidence,
            "action_calibration": by_action,
            "task_calibration": by_task,
            "reliable_action_groups": reliable_actions,
            "weak_action_groups": weak_actions,
            "reliable_task_groups": reliable_tasks,
            "weak_task_groups": weak_tasks,
            "action_group_min_record_requirement": self.MIN_GROUP_RECORDS,
            "task_group_min_record_requirement": self.MIN_GROUP_RECORDS,
            "provider_routing_recommendation": routing,
            "provider_routing_calibration_ready": True,
            "action_specific_calibration_ready": True,
            "task_specific_calibration_ready": True,
            "local_model_final_policy_recommended": True,
            "local_model_escalation_policy_recommended": True,
            "local_model_policy_update_candidate": routing,
            "local_model_policy_update_applied": False,
            "risk_calibration": {
                "risk_calibration_ready": True,
                "risk_prediction_correct_rate": round(risk_correct / len(risk_rows), 6) if risk_rows else None,
                "safety_blocker_prediction_summary": dict(Counter(
                    "unsafe" if row.get("model_risky_action_detected") else "no_observed_issue" for row in records
                )),
                "unsafe_model_prediction_count": unsafe_count,
                "local_model_risk_gate_recommendation": "retain_riskguard_and_livepreflight",
            },
            "data_sufficiency": "sufficient" if data_sufficient else ("no_data" if not records else "insufficient"),
        }

    def _append_history_once(self, profile: dict) -> None:
        signature = str(profile.get("calibration_signature") or "")
        last_signature = ""
        if self.history_path.exists():
            try:
                lines = [line for line in self.history_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
                if lines:
                    last_signature = str((json.loads(lines[-1]) or {}).get("calibration_signature") or "")
            except Exception:
                last_signature = ""
        if signature and signature == last_signature:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(profile, ensure_ascii=False, default=str) + "\n")

    def compute_calibration_profile(self) -> dict:
        logging.getLogger("aits").info(
            "[AITS][LocalModelCalibration] event=calibration_compute_started source=observed_outcomes persist_requested=false actual_order=False submitted=0"
        )
        source = self.load_sources()
        analysis = self.analyze(source)
        registry = self._read_json(self.registry_path)
        latest = self._read_json(self.latest_model_path)
        metrics = self._read_json(self.metrics_path)
        registry_hash = self._stable_hash(registry)
        source_hash = self._stable_hash({
            "counts": {key: source.get(key) for key in (
                "calibration_source_records_count", "local_model_prediction_records_count",
                "outcome_matched_records_count", "calibration_usable_records_count",
            )},
            "records": source.get("records"),
        })
        safe_for_expansion = bool(
            source["calibration_usable_records_count"] >= self.MIN_LIVE_EXPANSION_RECORDS
            and not analysis["risk_calibration"]["unsafe_model_prediction_count"]
            and analysis["confidence_calibration"]["recommended_confidence_threshold"] is not None
        )
        created_at = time.time()
        blocker = "" if analysis["data_sufficiency"] == "sufficient" else (
            "no_calibration_data" if analysis["data_sufficiency"] == "no_data" else "calibration_data_insufficient"
        )
        profile = {
            "schema": self.PROFILE_SCHEMA,
            "created_at": created_at,
            "source_model_id": str(latest.get("model_id") or registry.get("latest_model_id") or ""),
            "source_registry_hash": registry_hash,
            "source_records_hash": source_hash,
            "source_records_count": int(source["calibration_source_records_count"]),
            "usable_records_count": int(source["calibration_usable_records_count"]),
            "data_sufficiency": analysis["data_sufficiency"],
            "confidence_calibration": analysis["confidence_calibration"],
            "action_calibration": analysis["action_calibration"],
            "task_calibration": analysis["task_calibration"],
            "provider_routing_recommendation": analysis["provider_routing_recommendation"],
            "risk_calibration": analysis["risk_calibration"],
            "safety_policy": {
                "riskguard_required": True,
                "livepreflight_required": True,
                "external_confirmation_for_order_actions": True,
                "automatic_live_policy_expansion": False,
            },
            "recommended_min_records_before_live_expansion": self.MIN_LIVE_EXPANSION_RECORDS,
            "safe_for_policy_use": True,
            "safe_for_live_expansion": safe_for_expansion,
            "blocker": blocker,
            "latest_training_metrics_status": str(metrics.get("metrics_status") or ""),
            "calibration_signature": self._stable_hash({"registry": registry_hash, "source": source_hash}),
            "notes": "Recommendation-only calibration from observed outcomes; live policy is not changed.",
        }
        summary = {
            "schema": "aits_local_model_calibration_summary.v1",
            "created_at": created_at,
            **{key: value for key, value in source.items() if key not in {"rows_by_source", "records", "excluded"}},
            **{key: value for key, value in analysis.items() if key not in {"confidence_calibration", "action_calibration", "task_calibration", "provider_routing_recommendation", "risk_calibration"}},
            "confidence_calibration": analysis["confidence_calibration"],
            "action_calibration": analysis["action_calibration"],
            "task_calibration": analysis["task_calibration"],
            "provider_routing_recommendation": analysis["provider_routing_recommendation"],
            "risk_calibration": analysis["risk_calibration"],
            "safe_for_policy_use": True,
            "safe_for_live_expansion": safe_for_expansion,
            "no_data_calibration_ready": bool(source["calibration_source_records_count"] == 0 and not safe_for_expansion),
            "local_model_policy_update_applied": False,
            "blocker": blocker,
            "calibration_compute_write_separated": True,
            "calibration_persist_requested": False,
            "calibration_profile_write_attempted": False,
            "calibration_profile_write_performed": False,
            "calibration_summary_write_attempted": False,
            "calibration_summary_write_performed": False,
            "calibration_history_write_attempted": False,
            "calibration_history_write_performed": False,
        }
        logging.getLogger("aits").info(
            "[AITS][LocalModelCalibration] event=calibration_computed source_records=%s usable_records=%s data_sufficiency=%s persist_requested=false safe_for_policy_use=true safe_for_live_expansion=%s policy_update_applied=false blocker=%s actual_order=False submitted=0",
            source["calibration_source_records_count"], source["calibration_usable_records_count"],
            analysis["data_sufficiency"], safe_for_expansion, blocker or "-",
        )
        return {"profile": profile, "summary": summary}

    @staticmethod
    def _file_state(path: Path) -> tuple[int, int] | None:
        if not path.exists():
            return None
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

    def write_calibration_profile(self, computed: dict) -> dict:
        profile = dict(computed.get("profile") or {})
        summary = dict(computed.get("summary") or {})
        profile_before = self._file_state(self.profile_path)
        history_before = self._file_state(self.history_path)
        summary_before = self._file_state(self.summary_path)

        summary.update({
            "calibration_persist_requested": True,
            "calibration_profile_write_attempted": True,
            "calibration_summary_write_attempted": True,
            "calibration_history_write_attempted": True,
        })
        self._write_json_atomic(self.profile_path, profile)
        self._append_history_once(profile)
        summary.update({
            "calibration_profile_write_performed": self._file_state(self.profile_path) != profile_before,
            "calibration_history_write_performed": self._file_state(self.history_path) != history_before,
            "calibration_summary_write_performed": True,
        })
        self._write_json_atomic(self.summary_path, summary)
        summary["calibration_summary_write_performed"] = self._file_state(self.summary_path) != summary_before
        logging.getLogger("aits").info(
            "[AITS][LocalModelCalibration] event=calibration_profile_written source_records=%s usable_records=%s persist_requested=true profile_write=%s summary_write=%s history_write=%s safe_for_live_expansion=%s policy_update_applied=false actual_order=False submitted=0",
            int(summary.get("calibration_source_records_count") or 0),
            int(summary.get("calibration_usable_records_count") or 0),
            bool(summary.get("calibration_profile_write_performed")),
            bool(summary.get("calibration_summary_write_performed")),
            bool(summary.get("calibration_history_write_performed")),
            bool(summary.get("safe_for_live_expansion")),
        )
        return summary

    def run(self, *, persist: bool = False) -> dict:
        computed = self.compute_calibration_profile()
        if persist:
            return self.write_calibration_profile(computed)
        return dict(computed["summary"])


def load_local_model_calibration_profile(
    model_root: Path | str = Path("data") / "local_models",
) -> dict:
    path = Path(model_root) / "calibration_profile.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {"status": "unavailable", "reason": "calibration_profile_invalid"}
    if not isinstance(value, dict) or value.get("schema") != AITSLocalModelCalibration.PROFILE_SCHEMA:
        return {"status": "unavailable", "reason": "calibration_profile_unavailable"}
    return {
        "status": "available",
        "profile": value,
        "data_sufficient": value.get("data_sufficiency") == "sufficient",
        "safe_for_policy_use": bool(value.get("safe_for_policy_use")),
        "safe_for_live_expansion": bool(value.get("safe_for_live_expansion")),
    }
