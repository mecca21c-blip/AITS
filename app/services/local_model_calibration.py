from __future__ import annotations

from collections import Counter
import hashlib
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Optional


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
    ) -> None:
        self.training_root = Path(training_root)
        self.model_root = Path(model_root)
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
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _stable_hash(value: Any, length: int = 32) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:length]

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read_jsonl(path: Path) -> tuple[list[dict], int]:
        rows: list[dict] = []
        corrupted = 0
        if not path.exists():
            return rows, corrupted
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except Exception:
                    corrupted += 1
                    continue
                if isinstance(value, dict):
                    rows.append(value)
                else:
                    corrupted += 1
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

    def load_sources(self) -> dict:
        rows_by_source: dict[str, list[dict]] = {}
        corrupted = 0
        source_count = 0
        for name, path in self.source_paths.items():
            rows, bad = self._read_jsonl(path)
            rows_by_source[name] = rows
            source_count += len(rows)
            corrupted += bad

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

    def run(self) -> dict:
        logging.getLogger("aits").info(
            "[AITS][LocalModelCalibration] event=calibration_started source=observed_outcomes actual_order=False submitted=0"
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
        }
        self._write_json_atomic(self.profile_path, profile)
        self._append_history_once(profile)
        self._write_json_atomic(self.summary_path, summary)
        logging.getLogger("aits").info(
            "[AITS][LocalModelCalibration] event=calibration_profile_written source_records=%s usable_records=%s data_sufficiency=%s safe_for_policy_use=true safe_for_live_expansion=%s policy_update_applied=false blocker=%s actual_order=False submitted=0",
            source["calibration_source_records_count"], source["calibration_usable_records_count"],
            analysis["data_sufficiency"], safe_for_expansion, blocker or "-",
        )
        return summary


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
