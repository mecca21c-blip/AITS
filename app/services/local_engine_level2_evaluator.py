from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ai_review_repository import AITSDerivedJsonRepository
from app.services.local_engine_capability_evaluator import (
    AITSLocalEngineCapabilityEvaluator,
    TASK_CAPABILITY_ACTIONS,
)
from app.services.local_model_registry import AITSLocalModelRegistry


class AITSLocalEngineLevel2Evaluator:
    SCHEMA = "aits_local_engine_level2_eligibility.v1"
    PROMOTION_SCHEMA = "aits_local_engine_level2_promotion_candidate.v1"

    def __init__(
        self,
        *,
        data_root: Path | str = Path("data"),
        policy: dict[str, Any] | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.policy = dict(policy or {})

    @staticmethod
    def _action_metric(per_action: dict[str, Any], actions: tuple[str, ...]) -> float | None:
        values = [
            float((per_action.get(action) or {}).get("f1") or 0.0)
            for action in actions
            if int((per_action.get(action) or {}).get("support") or 0) > 0
        ]
        return round(sum(values) / len(values), 6) if values else None

    def evaluate(
        self,
        authority_state: dict[str, Any] | None = None,
        review_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        authority = dict(authority_state or {})
        model = AITSLocalModelRegistry().latest_multi_head_candidate()
        metrics = dict(model.get("metrics") or {})
        calibrator = AITSLocalModelRegistry().load_latest_usable_calibrator(str(model.get("model_id") or ""))
        if calibrator:
            metrics.update({
                "brier_score": calibrator.get("brier_after"),
                "expected_calibration_error": calibrator.get("ece_after"),
                "log_loss": calibrator.get("log_loss_after"),
                "calibrator_id": calibrator.get("calibrator_id"),
                "calibration_holdout_count": calibrator.get("holdout_count"),
            })
        per_action = dict(model.get("per_action_metrics") or metrics.get("per_action_metrics") or {})
        classes = Counter(model.get("class_distribution") or {})
        capability = AITSLocalEngineCapabilityEvaluator().evaluate()
        current_tasks = dict(capability.get("task_capabilities") or {})
        review = dict(review_evidence or AITSDerivedJsonRepository.load_json(
            self.data_root / "local_engine" / "local_engine_review_learning_priority.json", {}
        ))
        review_summary = AITSDerivedJsonRepository.load_json(
            self.data_root / "ai_review" / "ai_review_summary.json", {}
        )
        calibration = AITSDerivedJsonRepository.load_json(
            self.data_root / "local_models" / "latest_calibration_summary.json", {}
        )
        thresholds = dict(self.policy.get("level2_task_thresholds") or {})
        global_thresholds = dict(self.policy.get("level2_global_thresholds") or {})
        min_samples = int(thresholds.get("minimum_samples") or 20)
        min_reviews = int(thresholds.get("minimum_review_eligible") or 20)
        min_action_f1 = float(thresholds.get("minimum_action_f1") or 0.5)
        max_task_brier = float(thresholds.get("maximum_brier_score") or 0.45)
        eligible_reviews = int(
            review.get("review_learning_eligible_count")
            or review_summary.get("review_learning_eligible_count") or 0
        )
        total_reviews = max(1, int(review.get("review_count") or review_summary.get("review_records_count") or 0))
        task_review_counts = {
            key: sum((value or {}).values())
            for key, value in (review.get("review_quality_by_task") or {}).items()
        }
        unsafe = int(metrics.get("unsafe_prediction_count") or 0)
        brier = metrics.get("brier_score")
        task_results: dict[str, dict[str, Any]] = {}

        for task_key, actions in TASK_CAPABILITY_ACTIONS.items():
            current = dict(current_tasks.get(task_key) or {})
            sample_count = sum(int(classes.get(action) or 0) for action in actions)
            if not actions:
                sample_count = int(model.get("source_record_count") or sum(classes.values()))
            review_kind = {
                "portfolio_management": "portfolio",
                "position_buy_add": "buy",
                "position_sell_reduce": "sell",
                "take_profit_stop_loss": "sell",
                "rotation": "rotation",
            }.get(task_key, "position")
            review_count = int(task_review_counts.get(review_kind) or eligible_reviews)
            action_f1 = self._action_metric(per_action, actions)
            blockers: list[str] = []
            if int(current.get("capability_level") or 0) < 1:
                blockers.append("level1_task_capability_missing")
            if sample_count < min_samples:
                blockers.append("task_sample_count_insufficient")
            if review_count < min_reviews:
                blockers.append("review_learning_evidence_insufficient")
            if actions and (action_f1 is None or action_f1 < min_action_f1):
                blockers.append("task_action_f1_insufficient")
            if brier is None or float(brier) > max_task_brier:
                blockers.append("confidence_reliability_insufficient")
            if unsafe:
                blockers.append("unsafe_prediction_detected")
            if task_key == "risk_pre_assessment" and metrics.get("risk_distribution") is None:
                blockers.append("risk_head_evidence_missing")
            if task_key == "eta_redecision" and not metrics.get("eta_distribution"):
                blockers.append("eta_head_evidence_missing")
            if task_key == "invalidation_monitoring" and int(metrics.get("invalidation_nonempty_count") or 0) < min_samples:
                blockers.append("invalidation_evidence_insufficient")
            if task_key == "reason_explanation" and int(metrics.get("reason_nonempty_count") or 0) < min_samples:
                blockers.append("reason_evidence_insufficient")
            eligible = not blockers
            score_parts = [
                min(1.0, sample_count / max(1, min_samples)),
                min(1.0, review_count / max(1, min_reviews)),
                min(1.0, (action_f1 or 0.0) / max(0.01, min_action_f1)) if actions else 1.0,
                1.0 if not unsafe else 0.0,
            ]
            task_results[task_key] = {
                "level2_eligible": eligible,
                "eligibility_score": round(sum(score_parts) / len(score_parts), 4),
                "sample_count": sample_count,
                "recent_sample_count": int(current.get("recent_sample_count") or 0),
                "non_wait_sample_count": int(current.get("non_wait_sample_count") or 0),
                "teacher_count": int(current.get("teacher_sample_count") or 0),
                "outcome_count": int(current.get("outcome_sample_count") or 0),
                "review_eligible_count": review_count,
                "macro_f1": metrics.get("macro_f1"),
                "balanced_accuracy": metrics.get("balanced_accuracy"),
                "per_action_metrics": {action: per_action.get(action, {}) for action in actions},
                "confidence_metrics": {
                    "brier_score": brier,
                    "expected_calibration_error": metrics.get("expected_calibration_error"),
                },
                "risk_metrics": {
                    "unsafe_prediction_count": unsafe,
                    "blocker_recall": metrics.get("blocker_recall"),
                },
                "review_quality_metrics": dict((review.get("review_quality_by_task") or {}).get(review_kind) or {}),
                "repeated_failure_patterns": int(review.get("repeated_failure_pattern_count") or 0),
                "blockers": blockers,
            }

        eligible_tasks = [key for key, value in task_results.items() if value["level2_eligible"]]
        ineligible_tasks = [key for key, value in task_results.items() if not value["level2_eligible"]]
        global_blockers: list[str] = []
        minimum_eligible_tasks = int(global_thresholds.get("minimum_eligible_tasks") or 4)
        if len(eligible_tasks) < minimum_eligible_tasks:
            global_blockers.append("minimum_level2_eligible_tasks_not_met")
        if eligible_reviews < int(global_thresholds.get("minimum_review_eligible") or 100):
            global_blockers.append("minimum_review_learning_evidence_not_met")
        if float(metrics.get("macro_f1") or 0.0) < float(global_thresholds.get("minimum_macro_f1") or 0.5):
            global_blockers.append("minimum_macro_f1_not_met")
        if float(metrics.get("balanced_accuracy") or 0.0) < float(global_thresholds.get("minimum_balanced_accuracy") or 0.6):
            global_blockers.append("minimum_balanced_accuracy_not_met")
        if brier is None or float(brier) > float(global_thresholds.get("maximum_brier_score") or 0.35):
            global_blockers.append("maximum_brier_score_exceeded")
        if unsafe:
            global_blockers.append("unsafe_prediction_detected")
        if bool(review.get("policy_suggestion_auto_apply_detected")):
            global_blockers.append("policy_suggestion_auto_apply_detected")
        if bool(review.get("journal_patterns_used_as_action_labels")):
            global_blockers.append("journal_pattern_label_leakage_detected")
        if not model:
            global_blockers.append("usable_model_missing")
        global_eligible = not global_blockers
        current_level = int(authority.get("global_level") or 1)
        promotion_candidate = None
        if global_eligible and current_level == 1:
            promotion_candidate = {
                "schema": self.PROMOTION_SCHEMA,
                "promotion_candidate_id": f"level2-{model.get('model_id')}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "current_level": 1,
                "proposed_level": 2,
                "current_authority": "candidate_only",
                "proposed_authority": "co_pilot",
                "model_id": model.get("model_id"),
                "eligible_tasks": eligible_tasks,
                "ineligible_tasks": ineligible_tasks,
                "evidence_metrics": {
                    "macro_f1": metrics.get("macro_f1"),
                    "balanced_accuracy": metrics.get("balanced_accuracy"),
                    "brier_score": brier,
                    "brier_before_calibration": calibrator.get("brier_before") if calibrator else None,
                    "ece_before_calibration": calibrator.get("ece_before") if calibrator else None,
                    "ece_after_calibration": calibrator.get("ece_after") if calibrator else None,
                    "calibrator_id": calibrator.get("calibrator_id") if calibrator else "",
                    "review_learning_eligible_count": eligible_reviews,
                },
                "review_evidence": {"eligible": eligible_reviews, "total": total_reviews},
                "safety_evidence": {"unsafe_prediction_count": unsafe, "guard_bypass_count": 0},
                "provider_routing_evidence": {
                    "external_final_required": True,
                    "copilot_final_action_count": 0,
                },
                "changes_if_approved": [
                    "LOCAL_ENGINE 보조 판단이 GPT/Gemini 확인 우선순위와 provider routing metadata에 참여합니다.",
                    "위험하거나 불확실한 판단의 외부 AI 확인을 우선 추천합니다.",
                ],
                "unchanged_if_approved": [
                    "LOCAL_ENGINE은 단독 final action이나 주문을 만들지 않습니다.",
                    "GPT/Gemini 또는 안전 보류가 final action을 결정합니다.",
                    "RiskGuard, LivePreflight, CostGuard와 주문 submit 경로는 그대로 유지됩니다.",
                ],
                "blockers": [],
                "requires_user_approval": True,
                "approval_status": "awaiting_user_approval",
                "approved_at": None,
                "rejected_at": None,
            }
        return {
            "schema": self.SCHEMA,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "model_id": model.get("model_id"),
            "task_level2_eligibility": task_results,
            "level2_eligible_tasks": eligible_tasks,
            "level2_ineligible_tasks": ineligible_tasks,
            "global_level2_eligibility": global_eligible,
            "global_level2_blockers": global_blockers,
            "promotion_candidate": promotion_candidate,
            "confidence_calibrator": calibrator,
            "review_learning_eligible_count": eligible_reviews,
            "candidate_coverage_count": int(calibration.get("candidate_observation_valid_count") or 0),
            "external_final_required": True,
            "automatic_promotion": False,
            "requires_user_approval": True,
        }
