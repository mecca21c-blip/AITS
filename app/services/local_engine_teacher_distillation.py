from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.local_model_calibration import AITSLocalModelCalibration
from app.services.local_training_dataset_curation import atomic_write_json, atomic_write_jsonl


TEACHER_ACTIONS = {
    "wait", "hold", "buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"
}

TASK_FEATURE_CONTRACTS = {
    "position": (
        "position", "market", "indicators", "risk", "portfolio", "data_quality",
    ),
    "portfolio": (
        "portfolio", "risk", "data_quality",
    ),
    "candidate": (
        "opportunity", "market", "risk", "portfolio", "data_quality",
    ),
}


def task_contract_kind(task: str, scope: str) -> str:
    if task == "portfolio_management_decision" or scope == "PORTFOLIO":
        return "portfolio"
    if task in {
        "buy_decision", "rotation_decision", "promotion_decision",
        "managed_pool_promotion_decision", "candidate_selection_decision",
    }:
        return "candidate"
    return "position"


class AITSLocalEngineTeacherDistillation:
    """Create exact-joined teacher records without inventing absent labels."""

    SCHEMA = "aits_local_engine_teacher_distillation_record.v1"
    SUMMARY_SCHEMA = "aits_local_engine_teacher_distillation_summary.v1"

    def __init__(
        self,
        training_root: Path | str = Path("data") / "ai_decision_training",
        candidate_path: Path | str | None = None,
    ) -> None:
        self.training_root = Path(training_root)
        self.calibration = AITSLocalModelCalibration(
            training_root=self.training_root,
            candidate_path=candidate_path,
        )
        self.records_path = self.training_root / "local_engine_teacher_distillation_records.jsonl"
        self.excluded_path = self.training_root / "local_engine_teacher_distillation_excluded.jsonl"
        self.summary_path = self.training_root / "local_engine_teacher_distillation_summary.json"

    @staticmethod
    def _timestamp(value: Any) -> float:
        text = str(value or "")
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

    @staticmethod
    def _stable_hash(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _teacher_absent_reason(candidate: dict) -> str:
        guard = dict(candidate.get("provider_cost_guard_result") or {})
        blocker = str(guard.get("blocker") or "").lower()
        if blocker == "provider_request_cooldown":
            return "provider_request_cooldown"
        if "key" in blocker and ("missing" in blocker or "unavailable" in blocker):
            return "provider_key_missing"
        if "network" in blocker:
            return "network_unavailable"
        if "cost_guard" in blocker or guard.get("passed") is False:
            return "cost_guard_blocked"
        if "unavailable" in blocker:
            return "provider_unavailable"
        if str(candidate.get("final_provider_source") or "") == "local_safety_hold":
            return "external_not_required"
        return "historical_metadata_missing"

    @staticmethod
    def _feature_contract(task: str, scope: str, context: dict) -> dict:
        kind = task_contract_kind(task, scope)
        required = list(TASK_FEATURE_CONTRACTS[kind])
        available = [
            group for group in required
            if isinstance(context.get(group), dict) and bool(context.get(group))
        ]
        return {
            "kind": kind,
            "required_groups": required,
            "available_groups": available,
            "missing_groups": [group for group in required if group not in available],
            "task_specific_contract_applied": True,
        }

    @staticmethod
    def _external_decision(outcome: dict, provider_row: dict, candidate: dict) -> dict:
        external = dict(outcome.get("external_decision") or provider_row.get("external_decision") or {})
        if str(external.get("action") or "").lower() in TEACHER_ACTIONS:
            return external
        final = dict(outcome.get("final_decision") or provider_row.get("final_decision") or {})
        provider = str(final.get("provider") or candidate.get("final_provider_source") or "").lower()
        if provider in {"openai", "gemini"} and str(final.get("action") or "").lower() in TEACHER_ACTIONS:
            return final
        return {}

    @staticmethod
    def _choose_outcomes(rows: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
        by_prediction: dict[str, dict] = {}
        by_linkage: dict[str, dict] = {}
        for row in rows:
            prediction_id = str(row.get("local_engine_prediction_id") or "")
            linkage_key = str(row.get("local_engine_outcome_linkage_key") or "")
            # The feature snapshot is pre-decision and repeated at checkpoints. Prefer
            # the first exact record so future checkpoint values cannot become features.
            if prediction_id and prediction_id not in by_prediction:
                by_prediction[prediction_id] = row
            if linkage_key and linkage_key not in by_linkage:
                by_linkage[linkage_key] = row
        return by_prediction, by_linkage

    @staticmethod
    def _assign_splits(records: list[dict]) -> None:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in records:
            groups[str(row.get("decision_id") or row.get("prediction_id") or "")].append(row)
        ordered = sorted(
            groups.items(),
            key=lambda item: (
                min(float(row.get("created_at_epoch") or 0.0) for row in item[1]), item[0]
            ),
        )
        total = len(ordered)
        train_end = max(1, int(total * 0.70)) if total else 0
        validation_end = max(train_end, int(total * 0.85)) if total else 0
        for index, (_decision_id, rows) in enumerate(ordered):
            split = "train" if index < train_end else "validation" if index < validation_end else "holdout"
            for row in rows:
                row["split"] = split

    @staticmethod
    def _add_observed_cadence(records: list[dict]) -> None:
        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in records:
            groups[(str(row.get("task") or ""), str(row.get("scope") or ""))].append(row)
        for rows in groups.values():
            rows.sort(key=lambda row: float(row.get("created_at_epoch") or 0.0))
            for current, following in zip(rows, rows[1:]):
                delta = float(following.get("created_at_epoch") or 0.0) - float(current.get("created_at_epoch") or 0.0)
                if 30.0 <= delta <= 7200.0:
                    current["observed_redecision_seconds"] = round(delta, 3)

    def build(self, *, persist: bool = False) -> dict:
        candidate_source = self.calibration.load_candidate_observations()
        source = self.calibration.load_sources()
        outcomes = list(source.get("rows_by_source", {}).get("outcomes", []))
        providers = list(source.get("rows_by_source", {}).get("providers", []))
        outcomes_by_prediction, outcomes_by_linkage = self._choose_outcomes(outcomes)
        providers_by_decision = {
            str(row.get("decision_id") or row.get("source_decision_id") or ""): row
            for row in providers
            if str(row.get("decision_id") or row.get("source_decision_id") or "")
        }

        records: list[dict] = []
        excluded: list[dict] = []
        join_methods: Counter[str] = Counter()
        absent_reasons: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        for candidate in candidate_source.get("valid_rows") or []:
            prediction_id = str(candidate.get("prediction_id") or "")
            linkage_key = str(candidate.get("outcome_linkage_key") or "")
            outcome = outcomes_by_prediction.get(prediction_id)
            join_method = "prediction_id"
            if outcome is None:
                outcome = outcomes_by_linkage.get(linkage_key)
                join_method = "outcome_linkage_key"
            if outcome is None:
                excluded.append({
                    "prediction_id": prediction_id,
                    "outcome_linkage_key": linkage_key,
                    "exclusion_reason": "exact_outcome_not_found",
                })
                continue
            join_methods[join_method] += 1
            decision_id = str(outcome.get("decision_id") or candidate.get("decision_id") or "")
            provider_row = dict(providers_by_decision.get(decision_id) or {})
            external = self._external_decision(outcome, provider_row, candidate)
            teacher_provider = str(
                (outcome.get("final_decision") or {}).get("provider")
                or candidate.get("teacher_source")
                or ""
            ).lower()
            teacher_present = bool(
                teacher_provider in {"openai", "gemini"}
                and str(external.get("action") or "").lower() in TEACHER_ACTIONS
            )
            teacher_action = str(external.get("action") or "").lower() if teacher_present else ""
            absent_reason = "" if teacher_present else self._teacher_absent_reason(candidate)
            if absent_reason:
                absent_reasons[absent_reason] += 1
            if teacher_action:
                action_counts[teacher_action] += 1
            feature_context = dict(outcome.get("feature_context") or {})
            task = str(outcome.get("task") or candidate.get("task") or "")
            scope = str(outcome.get("scope") or candidate.get("scope") or "")
            feature_contract = self._feature_contract(task, scope, feature_context)
            quality = dict(outcome.get("payload_quality") or {})
            execution = dict(outcome.get("execution_result") or {})
            actual_order = bool(outcome.get("actual_order") or execution.get("actual_order"))
            submitted = int(outcome.get("submitted") or execution.get("submitted_count") or 0)
            record = {
                "schema": self.SCHEMA,
                "record_id": self._stable_hash({"prediction_id": prediction_id, "decision_id": decision_id})[:32],
                "decision_id": decision_id,
                "prediction_id": prediction_id,
                "outcome_linkage_key": linkage_key,
                "exact_join_method": join_method,
                "task": task,
                "scope": scope,
                "symbol": str(outcome.get("symbol") or scope),
                "created_at": str(candidate.get("created_at") or outcome.get("created_at") or ""),
                "created_at_epoch": self._timestamp(candidate.get("created_at") or outcome.get("created_at")),
                "teacher_provider": teacher_provider if teacher_present else None,
                "teacher_action": teacher_action if teacher_present else None,
                "teacher_confidence": external.get("confidence") if teacher_present else None,
                "teacher_reason_digest": str(candidate.get("final_reason_digest") or "") if teacher_present else "",
                "teacher_eta_seconds": external.get("eta_seconds") if teacher_present else None,
                "teacher_invalidation_conditions": list(external.get("invalidation_conditions") or []) if teacher_present else [],
                "teacher_present": teacher_present,
                "teacher_absent_reason": absent_reason,
                "final_provider_source": str(candidate.get("final_provider_source") or ""),
                "final_action": str(candidate.get("final_action") or "").lower(),
                "actual_order": actual_order,
                "submitted": submitted,
                "outcome_label": str(outcome.get("outcome_label") or ""),
                "outcome_score": outcome.get("outcome_score"),
                "payload_quality_grade": str(quality.get("payload_quality_grade") or ""),
                "feature_manifest_hash": str(outcome.get("feature_manifest_hash") or quality.get("feature_manifest_hash") or ""),
                "feature_context": feature_context,
                "feature_contract": feature_contract,
                "provider_comparison": dict(outcome.get("provider_comparison") or {}),
                "candidate_contract_valid": True,
                "label_leakage_prevented": True,
                "trainable_action_label": teacher_present,
                "fake_teacher": False,
            }
            records.append(record)

        # Outcome records already carry a stable decision_id, the pre-decision
        # feature_context, and an explicit external/final provider response. Use
        # that exact provenance for decisions which predate candidate coverage.
        # Only the first checkpoint row is considered, preventing future values
        # from becoming input features. No task/scope/time inference is used.
        represented_decisions = {str(row.get("decision_id") or "") for row in records}
        first_outcome_by_decision: dict[str, dict] = {}
        for outcome in outcomes:
            decision_id = str(outcome.get("decision_id") or "")
            if decision_id and decision_id not in first_outcome_by_decision:
                first_outcome_by_decision[decision_id] = outcome
        for decision_id, outcome in first_outcome_by_decision.items():
            if decision_id in represented_decisions:
                continue
            provider_row = dict(providers_by_decision.get(decision_id) or {})
            external = self._external_decision(outcome, provider_row, {})
            final = dict(outcome.get("final_decision") or provider_row.get("final_decision") or {})
            teacher_provider = str(
                final.get("provider")
                or outcome.get("teacher_source")
                or outcome.get("final_provider_source")
                or outcome.get("provider_source")
                or ""
            ).lower()
            teacher_action = str(external.get("action") or "").lower()
            if teacher_provider not in {"openai", "gemini"} or teacher_action not in TEACHER_ACTIONS:
                continue
            task = str(outcome.get("task") or outcome.get("decision_task") or "")
            scope = str(outcome.get("scope") or outcome.get("decision_scope") or "")
            feature_context = dict(outcome.get("feature_context") or {})
            feature_contract = self._feature_contract(task, scope, feature_context)
            if not task or not scope or not feature_context or feature_contract.get("missing_groups"):
                excluded.append({
                    "decision_id": decision_id,
                    "exclusion_reason": "outcome_native_feature_contract_incomplete",
                    "missing_groups": list(feature_contract.get("missing_groups") or []),
                })
                continue
            quality = dict(outcome.get("payload_quality") or {})
            execution = dict(outcome.get("execution_result") or {})
            reason = str(external.get("reason_ko") or external.get("reason") or "")
            record = {
                "schema": self.SCHEMA,
                "record_id": self._stable_hash({"decision_id": decision_id, "source": "outcome_native"})[:32],
                "decision_id": decision_id,
                "prediction_id": None,
                "outcome_linkage_key": str(outcome.get("local_engine_outcome_linkage_key") or ""),
                "exact_join_method": "outcome_decision_id",
                "task": task,
                "scope": scope,
                "symbol": str(outcome.get("symbol") or scope),
                "created_at": str(outcome.get("created_at") or ""),
                "created_at_epoch": self._timestamp(outcome.get("created_at")),
                "teacher_provider": teacher_provider,
                "teacher_action": teacher_action,
                "teacher_confidence": external.get("confidence"),
                "teacher_reason_digest": self._stable_hash(reason)[:24] if reason else "",
                "teacher_eta_seconds": external.get("eta_seconds"),
                "teacher_invalidation_conditions": list(external.get("invalidation_conditions") or []),
                "teacher_present": True,
                "teacher_absent_reason": "",
                "final_provider_source": teacher_provider,
                "final_action": str(final.get("action") or outcome.get("final_action") or "").lower(),
                "actual_order": bool(outcome.get("actual_order") or execution.get("actual_order")),
                "submitted": int(outcome.get("submitted") or execution.get("submitted_count") or 0),
                "outcome_label": str(outcome.get("outcome_label") or ""),
                "outcome_score": outcome.get("outcome_score"),
                "payload_quality_grade": str(quality.get("payload_quality_grade") or outcome.get("payload_quality_grade") or ""),
                "feature_manifest_hash": str(outcome.get("feature_manifest_hash") or quality.get("feature_manifest_hash") or ""),
                "feature_context": feature_context,
                "feature_contract": feature_contract,
                "provider_comparison": dict(outcome.get("provider_comparison") or {}),
                "candidate_contract_valid": None,
                "candidate_not_required_for_exact_outcome_teacher": True,
                "label_leakage_prevented": True,
                "trainable_action_label": True,
                "fake_teacher": False,
            }
            records.append(record)
            represented_decisions.add(decision_id)
            join_methods["outcome_decision_id"] += 1
            action_counts[teacher_action] += 1

        self._add_observed_cadence(records)
        self._assign_splits(records)
        teacher_records = [row for row in records if row.get("teacher_present")]
        split_counts = Counter(str(row.get("split") or "") for row in teacher_records)
        class_imbalance = bool(action_counts and max(action_counts.values()) > 2 * min(action_counts.values()))
        summary = {
            "schema": self.SUMMARY_SCHEMA,
            "teacher_distillation_dataset_ready": bool(teacher_records),
            "candidate_observation_records_count": int(candidate_source.get("candidate_observation_records_count") or 0),
            "distillation_records_count": len(records),
            "distillation_excluded_count": len(excluded),
            "teacher_present_count": len(teacher_records),
            "teacher_absent_count": len(records) - len(teacher_records),
            "teacher_absent_reason_counts": dict(sorted(absent_reasons.items())),
            "supported_action_label_counts": dict(sorted(action_counts.items())),
            "unsupported_action_label_counts": {
                action: 0 for action in sorted(TEACHER_ACTIONS - set(action_counts))
            },
            "train_count": int(split_counts["train"]),
            "validation_count": int(split_counts["validation"]),
            "holdout_count": int(split_counts["holdout"]),
            "class_imbalance_detected": class_imbalance,
            "exact_join_method_counts": dict(sorted(join_methods.items())),
            "fuzzy_join_used": False,
            "label_leakage_detected": False,
            "fake_training_data_detected": False,
            "task_contract_counts": dict(Counter(
                str((row.get("feature_contract") or {}).get("kind") or "") for row in records
            )),
            "portfolio_teacher_record_count": sum(
                (row.get("feature_contract") or {}).get("kind") == "portfolio" and row.get("teacher_present")
                for row in records
            ),
            "source_records_modified": False,
            "persist_requested": bool(persist),
        }
        if persist:
            atomic_write_jsonl(self.records_path, records)
            atomic_write_jsonl(self.excluded_path, excluded)
            atomic_write_json(self.summary_path, summary)
        return {"records": records, "excluded": excluded, "summary": summary}
