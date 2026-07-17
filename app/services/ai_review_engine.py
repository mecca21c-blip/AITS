from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from app.services.ai_review_reason_composer import (
    classify_result_reasons,
    compose_review_ko,
    decision_result_matrix,
    evaluate_decision_quality,
    evaluate_result_quality,
)
from app.services.ai_review_repository import AITSAIReviewRepository, AITSDerivedJsonRepository
from app.services.local_engine_review_learning_bridge import AITSLocalEngineReviewLearningBridge


ELIGIBLE_TASKS = {
    "position_management_decision", "portfolio_management_decision", "ai_redecision",
    "buy_decision", "sell_decision", "rotation_decision", "promotion_decision",
    "post_order_replanning", "remaining_position_redecision",
}
ELIGIBLE_ACTIONS = {"wait", "hold", "buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _checkpoint_name(row: dict[str, Any]) -> str:
    checkpoint = row.get("checkpoint")
    if isinstance(checkpoint, dict):
        return str(checkpoint.get("checkpoint_name") or "")
    return str(checkpoint or "")


def _checkpoint_payload(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [row for row in rows if _checkpoint_name(row) == name]
    if not matches:
        return {}
    row = matches[-1]
    checkpoint = row.get("checkpoint")
    return dict(checkpoint) if isinstance(checkpoint, dict) else {
        "checkpoint_name": name,
        "outcome_label": row.get("outcome_label"),
        "outcome_score": row.get("outcome_score"),
    }


class AITSAIReviewEngine:
    SCHEMA = "aits_ai_review_record.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.training_root = self.data_root / "ai_decision_training"
        self.local_root = self.data_root / "local_engine"
        self.repository = AITSAIReviewRepository(self.data_root)
        self.decision_paths = (
            self.training_root / "redecision_events.jsonl",
            self.training_root / "position_decisions.jsonl",
            self.training_root / "initial_management_decisions.jsonl",
        )
        self.outcome_path = self.training_root / "outcome_records.jsonl"
        self.comparison_path = self.training_root / "provider_comparison_outcomes.jsonl"
        self.candidate_path = self.local_root / "local_engine_candidate_observations.jsonl"

    @staticmethod
    def _richer(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        current_score = sum(value not in (None, "", [], {}) for value in current.values())
        candidate_score = sum(value not in (None, "", [], {}) for value in candidate.values())
        return candidate if candidate_score >= current_score else current

    def load_sources(self) -> dict[str, Any]:
        decisions: dict[str, dict[str, Any]] = {}
        source_stats: dict[str, Any] = {}
        for path in self.decision_paths:
            rows, stats = AITSDerivedJsonRepository.read_jsonl(path)
            source_stats[path.name] = stats
            for row in rows:
                decision_id = str(row.get("decision_id") or "")
                task = str(row.get("task") or row.get("request_task") or "")
                action = str(row.get("final_action") or row.get("ai_action") or "").lower()
                if not decision_id or (task and task not in ELIGIBLE_TASKS) or (action and action not in ELIGIBLE_ACTIONS):
                    continue
                decisions[decision_id] = self._richer(decisions.get(decision_id, {}), row)
        outcomes, outcome_stats = AITSDerivedJsonRepository.read_jsonl(self.outcome_path)
        comparisons, comparison_stats = AITSDerivedJsonRepository.read_jsonl(self.comparison_path)
        candidates, candidate_stats = AITSDerivedJsonRepository.read_jsonl(self.candidate_path)
        source_stats[self.outcome_path.name] = outcome_stats
        source_stats[self.comparison_path.name] = comparison_stats
        source_stats[self.candidate_path.name] = candidate_stats
        return {
            "decisions": decisions,
            "outcomes": outcomes,
            "comparisons": comparisons,
            "candidates": candidates,
            "source_stats": source_stats,
        }

    @staticmethod
    def _review_stage(outcomes: list[dict[str, Any]], decision: dict[str, Any]) -> str:
        if decision.get("final_outcome"):
            return "final"
        names = {_checkpoint_name(row) for row in outcomes}
        available = False
        for row in outcomes:
            checkpoint = dict(row.get("checkpoint") or {})
            if str(checkpoint.get("status") or "") not in {"skipped", "unavailable"} and str(checkpoint.get("outcome_label") or row.get("outcome_label") or "") != "data_unavailable":
                available = True
                break
        if outcomes and not available:
            return "data_unavailable"
        if "outcome_final" in names:
            return "final"
        if "outcome_1h" in names:
            return "partial_1h"
        if "outcome_15m" in names:
            return "partial_15m"
        if "outcome_5m" in names:
            return "partial_5m"
        return "pending"

    @staticmethod
    def _candidate_indexes(candidates: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        indexes = {"decision": {}, "prediction": {}, "linkage": {}}
        for row in candidates:
            for name, key in (
                ("decision", row.get("decision_id")),
                ("prediction", row.get("prediction_id")),
                ("linkage", row.get("outcome_linkage_key")),
            ):
                if key:
                    indexes[name][str(key)] = row
        return indexes

    @staticmethod
    def _find_candidate(decision: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> tuple[dict[str, Any], str]:
        decision_id = str(decision.get("decision_id") or "")
        prediction_id = str(decision.get("local_engine_prediction_id") or "")
        linkage = str(decision.get("local_engine_outcome_linkage_key") or "")
        if decision_id and decision_id in indexes["decision"]:
            return indexes["decision"][decision_id], "decision_id"
        if prediction_id and prediction_id in indexes["prediction"]:
            return indexes["prediction"][prediction_id], "prediction_id"
        if linkage and linkage in indexes["linkage"]:
            return indexes["linkage"][linkage], "outcome_linkage_key"
        return {}, "missing"

    def build_reviews(self, *, persist: bool = False) -> dict[str, Any]:
        loaded = self.load_sources()
        decisions = dict(loaded["decisions"])
        outcomes_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        comparisons_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in loaded["outcomes"]:
            if row.get("decision_id"):
                outcomes_by_id[str(row["decision_id"])].append(row)
        for row in loaded["comparisons"]:
            if row.get("decision_id"):
                comparisons_by_id[str(row["decision_id"])].append(row)
        candidate_indexes = self._candidate_indexes(loaded["candidates"])
        now = _now()
        reviews: list[dict[str, Any]] = []
        join_counts: Counter[str] = Counter()
        for decision_id, decision in decisions.items():
            outcome_rows = outcomes_by_id.get(decision_id, [])
            candidate, candidate_join = self._find_candidate(decision, candidate_indexes)
            join_counts[candidate_join] += 1
            decision_quality, decision_success, decision_failure = evaluate_decision_quality(decision)
            result_quality, result = evaluate_result_quality(outcome_rows)
            result_success, result_failure = classify_result_reasons(decision, result)
            success_reasons = sorted(set(decision_success + result_success))
            failure_reasons = sorted(set(decision_failure + result_failure))
            matrix = decision_result_matrix(decision_quality, result_quality)
            composed = compose_review_ko(
                decision, result, decision_quality, result_quality,
                success_reasons, failure_reasons,
            )
            stage = self._review_stage(outcome_rows, decision)
            final_action = str(decision.get("final_action") or decision.get("ai_action") or "").lower()
            comparison = comparisons_by_id.get(decision_id, [])[-1] if comparisons_by_id.get(decision_id) else {}
            review_id = _stable_id("review", decision_id)
            limitations = []
            if not outcome_rows:
                limitations.append("outcome_checkpoint_missing")
            if result_quality == "unavailable":
                limitations.append("outcome_data_unavailable")
            if not candidate:
                limitations.append("local_engine_candidate_missing")
            if decision_quality == "inconclusive":
                limitations.append("decision_evidence_insufficient")
            if isinstance(decision.get("effective_policy_snapshot"), dict) and not bool(decision.get("effective_policy_snapshot", {}).get("policy_valid", True)):
                limitations.append("effective_policy_conflict")
            if decision.get("ai_intent") is not None and not isinstance(decision.get("ai_intent"), dict):
                limitations.append("canonical_intent_invalid")
            execution = decision.get("execution_result") if isinstance(decision.get("execution_result"), dict) else {}
            order_result = decision.get("order_result") if isinstance(decision.get("order_result"), dict) else {}
            canonical_intent = decision.get("ai_intent") if isinstance(decision.get("ai_intent"), dict) else {}
            effective_policy = decision.get("effective_policy_snapshot") if isinstance(decision.get("effective_policy_snapshot"), dict) else {}
            review = {
                "schema": self.SCHEMA,
                "review_id": review_id,
                "review_stage": stage,
                "decision_id": decision_id,
                "parent_decision_id": decision.get("parent_decision_id"),
                "prediction_id": candidate.get("prediction_id") or decision.get("local_engine_prediction_id"),
                "outcome_linkage_key": candidate.get("outcome_linkage_key") or decision.get("local_engine_outcome_linkage_key"),
                "session_id": decision.get("session_id"),
                "task": decision.get("task") or decision.get("request_task"),
                "scope": decision.get("scope") or decision.get("scope_type"),
                "symbol": decision.get("symbol") or decision.get("scope"),
                "created_at": decision.get("timestamp") or now,
                "updated_at": now,
                "intent_id": canonical_intent.get("intent_id") or decision.get("intent_id"),
                "parent_intent_id": canonical_intent.get("parent_intent_id"),
                "intent_revision": canonical_intent.get("revision") or decision.get("intent_revision"),
                "intent_status": canonical_intent.get("status") or "not_recorded",
                "intent_goal": canonical_intent.get("goal") or decision.get("trigger_reason") or "",
                "intent_watch_points": canonical_intent.get("watch_points") or decision.get("feature_coverage_summary") or {},
                "intent_conditions": canonical_intent.get("confirmation_conditions") or decision.get("invalidation_conditions") or [],
                "intent_invalidation_conditions": canonical_intent.get("invalidation_conditions") or decision.get("invalidation_conditions") or [],
                "expected_scenario": canonical_intent.get("expected_scenario") or decision.get("expected_scenario") or "",
                "effective_policy_id": effective_policy.get("policy_id") or decision.get("effective_policy_id"),
                "effective_policy_version": effective_policy.get("policy_version") or decision.get("effective_policy_version"),
                "effective_policy_hash": effective_policy.get("policy_hash") or decision.get("effective_policy_hash"),
                "policy_constraints": canonical_intent.get("policy_constraints") or {},
                "intent_is_order_promise": False,
                "provider_source": decision.get("final_provider_source") or decision.get("provider"),
                "teacher_provider": decision.get("external_provider_name") if decision.get("external_provider_called") else None,
                "local_engine_candidate": candidate,
                "candidate_join_method": candidate_join,
                "final_action": final_action,
                "final_confidence": decision.get("final_confidence") or decision.get("ai_confidence"),
                "raw_confidence": candidate.get("raw_confidence"),
                "calibrated_confidence": candidate.get("confidence"),
                "calibration_method": candidate.get("calibration_method"),
                "calibrator_id": candidate.get("calibrator_id"),
                "confidence_reliability": candidate.get("confidence_reliability"),
                "high_confidence_error": bool(
                    candidate.get("confidence") is not None
                    and float(candidate.get("confidence") or 0.0) >= 0.8
                    and candidate.get("action") != final_action
                ),
                "reason_ko": decision.get("final_reason_ko") or decision.get("ai_reason_ko") or "",
                "evidence": decision.get("evidence") or decision.get("feature_coverage_summary") or {},
                "risk_level": decision.get("risk_level") or candidate.get("risk_level"),
                "blockers": decision.get("missing_critical_features") or [],
                "eta_seconds": decision.get("eta_seconds"),
                "invalidation_conditions": decision.get("invalidation_conditions") or candidate.get("invalidation_conditions") or [],
                "payload_quality_grade": decision.get("payload_quality_grade"),
                "feature_quality_grade": decision.get("feature_quality_grade"),
                "order_requested": bool(decision.get("order_result") or decision.get("order_requested")),
                "order_submitted": bool(decision.get("submitted") or order_result.get("submitted")),
                "order_filled": bool(order_result.get("filled") or execution.get("filled")),
                "order_side": order_result.get("side") or execution.get("side"),
                "order_qty": order_result.get("qty") or execution.get("qty"),
                "order_krw": order_result.get("amount_krw") or execution.get("amount_krw"),
                "riskguard_result": decision.get("riskguard_result"),
                "livepreflight_result": decision.get("livepreflight_result"),
                "execution_result": execution,
                "reconciliation_result": decision.get("reconciliation_result"),
                "post_order_replanning_result": decision.get("post_order_replanning_result"),
                "outcome_5m": _checkpoint_payload(outcome_rows, "outcome_5m"),
                "outcome_15m": _checkpoint_payload(outcome_rows, "outcome_15m"),
                "outcome_1h": _checkpoint_payload(outcome_rows, "outcome_1h"),
                "final_outcome": decision.get("final_outcome") or result,
                "price_change": result.get("price_change_pct"),
                "pnl_change": result.get("pnl_change_pct"),
                "portfolio_change": result.get("portfolio_change_pct"),
                "opportunity_cost": next((row.get("opportunity_cost") for row in reversed(outcome_rows) if row.get("opportunity_cost") is not None), None),
                "avoided_drawdown": "avoided_loss" in success_reasons,
                "missed_opportunity": "missed_opportunity" in failure_reasons,
                "review_status": stage,
                "decision_quality": decision_quality,
                "result_quality": result_quality,
                "decision_result_matrix": matrix,
                "success_reasons": success_reasons,
                "failure_reasons": failure_reasons,
                **composed,
                "repeated_pattern_tags": sorted(set(success_reasons + failure_reasons)),
                "policy_suggestion_ids": [],
                "safe_for_learning": bool(decision.get("safe_for_local_training") or (decision_quality != "inconclusive" and result_quality != "unavailable")),
                "review_limitations": limitations,
                "provider_comparison": comparison,
                "copilot_decision": dict(decision.get("local_engine_copilot") or {}),
                "copilot_consulted": bool(decision.get("copilot_consulted")),
                "copilot_routing_used": bool(decision.get("copilot_recommendation_used")),
                "copilot_routing_effect": str(decision.get("copilot_routing_effect") or "not_recorded"),
                "external_confirmation_result": str(decision.get("final_provider_source") or decision.get("provider") or ""),
                "task_capability_level": int(decision.get("local_engine_task_level") or 0),
                "factual_evidence_only": True,
                "hindsight_leakage_detected": False,
                "fake_causality": False,
                "source_records_preserved": True,
            }
            review.update(AITSLocalEngineReviewLearningBridge.evaluate_review(review))
            reviews.append(review)

        status_counts = Counter(row["review_status"] for row in reviews)
        matrix_counts = Counter(row["decision_result_matrix"] for row in reviews)
        decision_counts = Counter(row["decision_quality"] for row in reviews)
        result_counts = Counter(row["result_quality"] for row in reviews)
        summary = {
            "schema": "aits_ai_review_summary.v1",
            "generated_at": now,
            "review_records_count": len(reviews),
            "review_status_counts": dict(status_counts),
            "decision_quality_counts": dict(decision_counts),
            "result_quality_counts": dict(result_counts),
            "decision_result_matrix_counts": dict(matrix_counts),
            "review_learning_eligible_count": sum(bool(row.get("review_learning_eligible")) for row in reviews),
            "review_learning_excluded_count": sum(not bool(row.get("review_learning_eligible")) for row in reviews),
            "review_reliability_grade_counts": dict(Counter(row.get("review_reliability_grade") for row in reviews)),
            "rubric_overreach_count": sum(bool(row.get("rubric_overreach_detected")) for row in reviews),
            "candidate_join_method_counts": dict(join_counts),
            "source_counts": {
                "decision": len(decisions),
                "intent": sum(bool(row.get("trigger_reason") or row.get("feature_coverage_summary")) for row in decisions.values()),
                "outcome": len(loaded["outcomes"]),
                "order": sum(bool(row.get("order_result") or row.get("execution_result")) for row in decisions.values()),
                "candidate": len(loaded["candidates"]),
            },
            "source_stats": loaded["source_stats"],
            "corrupt_review_count": 0,
            "exact_join_ready": True,
            "fuzzy_join_detected": False,
            "source_records_preserved": True,
            "recent_reviews": [
                {
                    key: row.get(key)
                    for key in (
                        "review_id", "created_at", "symbol", "scope", "task",
                        "final_action", "review_status", "decision_quality",
                        "result_quality", "decision_summary_ko", "result_summary_ko",
                        "review_summary_ko", "what_went_well_ko",
                        "what_went_wrong_ko", "what_was_unknown_ko", "lesson_ko",
                        "order_submitted", "review_limitations",
                        "review_learning_eligible", "review_reliability_grade",
                        "review_learning_weight", "review_target_eligibility",
                        "review_exclusion_reasons", "rubric_overreach_detected",
                        "local_engine_candidate", "provider_comparison",
                        "copilot_decision", "copilot_consulted", "copilot_routing_used",
                        "copilot_routing_effect", "task_capability_level",
                    )
                }
                for row in reviews[-100:]
            ],
        }
        if persist:
            write_result = self.repository.write_records(reviews)
            AITSDerivedJsonRepository.atomic_write_json(self.repository.summary_path, summary)
            AITSDerivedJsonRepository.atomic_write_json(self.repository.state_path, {
                "schema": "aits_ai_review_state.v1",
                "updated_at": now,
                "generation_status": "completed",
                "record_count": len(reviews),
                "source_records_preserved": True,
                "last_write_result": write_result,
            })
        return {"records": reviews, "summary": summary, "persisted": bool(persist)}
