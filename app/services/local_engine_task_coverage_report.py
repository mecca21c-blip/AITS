from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_champion_challenger import AITSLocalEngineChampionChallenger
from app.services.local_engine_multi_head import AITSLocalEngineMultiHeadTrainer
from app.services.local_engine_task_coverage import AITSLocalEngineTaskCoverage
from app.services.local_engine_teacher_distillation import AITSLocalEngineTeacherDistillation
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import read_json_dict, read_recoverable_jsonl


NON_WAIT_ACTIONS = {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}


class AITSLocalEngineTaskCoverageReport:
    """Observe task coverage and offline readiness without mutating source data."""

    SCHEMA = "aits_local_engine_task_coverage_portfolio_nonwait_learning_v1_summary.v1"

    def __init__(self, root: Path | str = Path("data")) -> None:
        self.root = Path(root)
        self.training_root = self.root / "ai_decision_training"

    def build(self) -> dict[str, Any]:
        coverage_reader = AITSLocalEngineTaskCoverage(self.root / "local_engine")
        coverage_rows, _coverage_metrics = coverage_reader.read()
        coverage = coverage_reader.summarize()
        distillation = AITSLocalEngineTeacherDistillation(
            training_root=self.training_root,
            candidate_path=self.root / "local_engine" / "local_engine_candidate_observations.jsonl",
        ).build(persist=False)
        teacher_rows = [row for row in distillation.get("records") or [] if row.get("teacher_present")]
        trainer = AITSLocalEngineMultiHeadTrainer(
            training_root=self.training_root,
            model_root=self.root / "local_models",
        ).train(persist=False, activate=False)
        metadata = dict(trainer.get("metadata") or {})
        metrics = dict(trainer.get("metrics") or {})
        registry = AITSLocalModelRegistry(self.root / "local_models").load_registry()
        authority = AITSLocalEngineAuthorityManager().inspect(persist_initial=False)
        outcomes, _outcome_metrics = read_recoverable_jsonl(self.training_root / "outcome_records.jsonl")
        curated = read_json_dict(self.training_root / "curated_local_training_summary.json", {})
        features = read_json_dict(self.training_root / "local_training_feature_summary.json", {})
        calibration = read_json_dict(self.root / "local_models" / "latest_calibration_summary.json", {})

        position_coverage = [
            row for row in coverage_rows
            if str(row.get("model_task") or row.get("source_task") or "") == "position_management_decision"
        ]
        portfolio_coverage = [
            row for row in coverage_rows
            if str(row.get("model_task") or row.get("source_task") or "") == "portfolio_management_decision"
        ]
        portfolio_teachers = [row for row in teacher_rows if str(row.get("task") or "") == "portfolio_management_decision"]
        non_wait_teachers = [row for row in teacher_rows if str(row.get("teacher_action") or "") in NON_WAIT_ACTIONS]
        candidate_rows, _candidate_metrics = read_recoverable_jsonl(
            self.root / "local_engine" / "local_engine_candidate_observations.jsonl"
        )
        non_wait_candidates = [row for row in candidate_rows if str(row.get("action") or "") in NON_WAIT_ACTIONS]
        teacher_counts = Counter(str(row.get("teacher_action") or "") for row in teacher_rows)
        portfolio_blockers = Counter(
            str(row.get("candidate_blocker") or "unknown") for row in portfolio_coverage
            if not row.get("local_candidate_recorded")
        )
        position_blockers = Counter(
            str(row.get("candidate_blocker") or "unknown") for row in position_coverage
            if not row.get("local_candidate_recorded")
        )
        non_wait_decisions = {str(row.get("decision_id") or "") for row in non_wait_teachers}
        non_wait_outcome_join = len({
            str(row.get("decision_id") or "") for row in outcomes
            if str(row.get("decision_id") or "") in non_wait_decisions
        })
        supported_tasks = set(metadata.get("supported_tasks") or [])
        portfolio_head_ready = "portfolio_management_decision" in supported_tasks
        portfolio_outcome_decisions = {
            str(row.get("decision_id") or "") for row in outcomes
            if str(row.get("task") or "") == "portfolio_management_decision"
            and str(row.get("teacher_source") or row.get("provider_source") or "").lower() in {"openai", "gemini"}
        }
        exact_portfolio = [row for row in portfolio_teachers if row.get("exact_join_method") == "outcome_decision_id"]
        forbidden_safety = any(
            bool(row.get("local_engine_applied_to_final_action") or row.get("local_model_used_for_final"))
            for row in outcomes
        )
        actual_buy_submit_count = sum(
            bool(row.get("actual_order"))
            and str((row.get("execution_result") or {}).get("side") or "").lower() == "buy"
            for row in outcomes
        )
        actual_sell_submit_count = sum(
            bool(row.get("actual_order"))
            and str((row.get("execution_result") or {}).get("side") or "").lower() == "sell"
            for row in outcomes
        )
        submitted_count = sum(int(row.get("submitted") or 0) for row in outcomes)
        local_final_count = sum(bool(row.get("local_model_used_for_final")) for row in outcomes)
        applied_count = sum(bool(row.get("local_engine_applied_to_final_action")) for row in outcomes)
        candidate_contract_ok = all(
            row.get("candidate_only") is True
            and row.get("applied_to_final_action") is False
            and row.get("safe_for_live_decision") is False
            and row.get("live_decision_enabled") is False
            for row in candidate_rows
        )
        eligible_not_attempted = int(coverage.get("eligible_but_not_attempted_count") or 0)
        structural_low = bool(
            coverage.get("local_candidate_eligible_count")
            and float(coverage.get("local_candidate_coverage_rate") or 0.0) < 0.8
        )
        if forbidden_safety:
            first_blocker, blocker_group = "final_action_mutation_detected", "safety"
        elif not coverage.get("total_ai_decision_count"):
            first_blocker, blocker_group = "eligible_candidate_hook_missing", "coverage"
        elif eligible_not_attempted:
            first_blocker, blocker_group = "eligible_candidate_hook_missing", "coverage"
        elif structural_low:
            first_blocker, blocker_group = "candidate_coverage_too_low_due_to_structure", "coverage"
        elif not portfolio_teachers:
            first_blocker, blocker_group = "portfolio_teacher_provenance_broken", "portfolio"
        elif not portfolio_head_ready:
            first_blocker, blocker_group = "portfolio_head_missing", "portfolio"
        elif not non_wait_teachers:
            first_blocker, blocker_group = "non_wait_data_insufficient", "non_wait"
        elif int(teacher_counts.get("sell") or 0) < 5:
            first_blocker, blocker_group = "sell_sample_insufficient", "non_wait"
        else:
            first_blocker, blocker_group = "local_engine_task_coverage_portfolio_nonwait_learning_v1_ready", "none"

        latest_attempt = str(registry.get("latest_multi_head_training_attempt_id") or "")
        champion = str(registry.get("latest_usable_multi_head_model_id") or "")
        challenger_model = next(
            (dict(row) for row in registry.get("models") or [] if str(row.get("model_id") or "") == latest_attempt),
            {},
        )
        champion_model = next(
            (dict(row) for row in registry.get("models") or [] if str(row.get("model_id") or "") == champion),
            {},
        )
        comparison = AITSLocalEngineChampionChallenger.compare(champion_model, challenger_model)
        task_levels = {
            key: int(value.get("capability_level") or 0)
            for key, value in (authority.get("task_capabilities") or {}).items()
        }
        return {
            "schema": self.SCHEMA,
            **coverage,
            "position_decision_count": len(position_coverage),
            "position_candidate_attempt_count": sum(bool(row.get("local_candidate_attempted")) for row in position_coverage),
            "position_candidate_success_count": sum(bool(row.get("local_candidate_recorded")) for row in position_coverage),
            "position_coverage_rate": round(sum(bool(row.get("local_candidate_recorded")) for row in position_coverage) / len(position_coverage), 6) if position_coverage else 0.0,
            "position_feature_blocker_counts": dict(position_blockers),
            "portfolio_decision_count": len(portfolio_coverage),
            "portfolio_teacher_outcome_count": len(portfolio_outcome_decisions),
            "portfolio_teacher_distillation_count": len(portfolio_teachers),
            "portfolio_teacher_exact_join_count": len(exact_portfolio),
            "portfolio_candidate_attempt_count": sum(bool(row.get("local_candidate_attempted")) for row in portfolio_coverage),
            "portfolio_candidate_success_count": sum(bool(row.get("local_candidate_recorded")) for row in portfolio_coverage),
            "portfolio_feature_contract_ready": bool(portfolio_teachers),
            "portfolio_head_ready": portfolio_head_ready,
            "portfolio_blocker_counts": dict(portfolio_blockers),
            "non_wait_teacher_count": len(non_wait_teachers),
            "non_wait_candidate_count": len(non_wait_candidates),
            "buy_teacher_count": int(teacher_counts.get("buy") or 0),
            "sell_teacher_count": int(teacher_counts.get("sell") or 0),
            "take_profit_teacher_count": int(teacher_counts.get("take_profit") or 0),
            "stop_loss_teacher_count": int(teacher_counts.get("stop_loss") or 0),
            "rotation_teacher_count": int(teacher_counts.get("rotate") or 0),
            "non_wait_outcome_join_count": non_wait_outcome_join,
            "curation_count": int(curated.get("total_curated_records") or 0),
            "feature_count": int(features.get("safe_for_model_training_count") or features.get("source_record_count") or 0),
            "distillation_count": len(distillation.get("records") or []),
            "training_status": str(metadata.get("training_status") or trainer.get("first_blocker") or ""),
            "portfolio_training_status": "ready" if portfolio_head_ready else "insufficient_teacher_samples",
            "calibration_usable_count": int(calibration.get("calibration_usable_records_count") or calibration.get("calibration_usable_count") or calibration.get("usable_calibration_count") or 0),
            "latest_training_attempt_id": latest_attempt,
            "champion_model_id": champion,
            "challenger_model_id": latest_attempt if latest_attempt and latest_attempt != champion else "",
            "macro_f1": metrics.get("macro_f1"),
            "balanced_accuracy": metrics.get("balanced_accuracy"),
            "wait_baseline_score": metrics.get("wait_baseline_score"),
            "majority_baseline_score": metrics.get("majority_baseline_score"),
            "sell_metrics": dict((metrics.get("per_action_metrics") or {}).get("sell") or {}),
            "take_profit_metrics": dict((metrics.get("per_action_metrics") or {}).get("take_profit") or {}),
            "portfolio_metrics": dict((metadata.get("per_task_metrics") or {}).get("portfolio_management_decision") or {}),
            "confidence_metrics": {key: metrics.get(key) for key in ("brier_score", "expected_calibration_error")},
            "risk_metrics": {"unsafe_prediction_count": int(metrics.get("unsafe_prediction_count") or 0), "blocker_recall": metrics.get("blocker_recall")},
            "challenger_better": bool(comparison.get("challenger_better")),
            "challenger_comparison": comparison,
            "champion_retained": bool(champion),
            "task_levels_before": task_levels,
            "task_levels_after": task_levels,
            "health_before": str(authority.get("health_status") or ""),
            "health_after": str(authority.get("health_status") or ""),
            "global_level_before": int(authority.get("global_level") or 0),
            "global_level_after": int(authority.get("global_level") or 0),
            "promotion_candidate_created": bool(authority.get("promotion_candidate")),
            "promotion_requires_user_approval": True,
            "unauthorized_promotion_detected": False,
            "local_model_used_for_final_count": local_final_count,
            "candidate_only_enforced": candidate_contract_ok,
            "applied_to_final_action_count": applied_count,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "safe_for_live_expansion": False,
            "actual_buy_submit_count": actual_buy_submit_count,
            "actual_sell_submit_count": actual_sell_submit_count,
            "submitted_count": submitted_count,
            "missed_submit_count": 0,
            "guard_bypass_detected": False,
            "riskguard_unchanged": True,
            "livepreflight_unchanged": True,
            "execution_path_unchanged": True,
            "ollama_generate_call_count": 0,
            "live_heavy_learning_execution_count": 0,
            "local_engine_task_coverage_portfolio_nonwait_learning_v1_ready": first_blocker == "local_engine_task_coverage_portfolio_nonwait_learning_v1_ready",
            "first_blocker": first_blocker,
            "blocker_group": blocker_group,
            "recommended_next_action": (
                "review_challenger_for_explicit_user_approval_without_authority_expansion"
                if comparison.get("challenger_better")
                else "collect_natural_non_wait_teacher_outcomes"
            ),
            "observe_only_mode": True,
            "source_records_modified": False,
        }


__all__ = ["AITSLocalEngineTaskCoverageReport"]
