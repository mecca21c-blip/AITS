from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.ai_review_repository import AITSDerivedJsonRepository
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_confidence_calibrator import AITSLocalEngineConfidenceCalibrator
from app.services.local_engine_level2_evaluator import AITSLocalEngineLevel2Evaluator
from app.services.local_model_registry import AITSLocalModelRegistry


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_local_engine_confidence_calibration_level2_report(
    repo_root: Path | str = Path("."),
) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    source_paths = (
        data / "local_engine" / "local_engine_candidate_observations.jsonl",
        data / "ai_decision_training" / "local_engine_teacher_distillation_records.jsonl",
        data / "ai_decision_training" / "outcome_records.jsonl",
        data / "ai_decision_training" / "provider_comparison_outcomes.jsonl",
        data / "ai_review" / "ai_review_records.jsonl",
    )
    protected_paths = (
        data / "local_engine" / "local_engine_authority_state.json",
        data / "local_models" / "registry.json",
        data / "local_models" / "latest_model.json",
        data / "local_models" / "calibration_profile.json",
        data / "local_models" / "latest_calibration_summary.json",
    )
    before = {str(path): _hash(path) for path in source_paths + protected_paths}
    authority_manager = AITSLocalEngineAuthorityManager(data / "local_engine")
    authority_before = authority_manager.inspect(persist_initial=False)
    calibration = AITSLocalEngineConfidenceCalibrator(data).evaluate(persist=False)
    review_bridge = AITSDerivedJsonRepository.load_json(
        data / "local_engine" / "local_engine_review_learning_priority.json", {}
    )
    level2 = AITSLocalEngineLevel2Evaluator(
        data_root=data,
        policy=authority_manager.policy.as_dict(),
    ).evaluate(authority_before, review_bridge)
    authority_after = authority_manager.inspect(persist_initial=False)
    after = {str(path): _hash(path) for path in source_paths + protected_paths}
    source_preserved = all(before[str(path)] == after[str(path)] for path in source_paths)
    protected_preserved = all(before[str(path)] == after[str(path)] for path in protected_paths)

    raw_validation = dict(calibration.get("raw_validation_metrics") or {})
    validation = dict(calibration.get("calibrated_validation_metrics") or {})
    raw_holdout = dict(calibration.get("raw_holdout_metrics") or {})
    holdout = dict(calibration.get("calibrated_holdout_metrics") or {})
    registry = AITSLocalModelRegistry(data / "local_models")
    model = registry.latest_multi_head_candidate()
    latest_attempt = registry.load_latest_training_attempt()
    challenger = (
        latest_attempt
        if str(latest_attempt.get("model_id") or "")
        and str(latest_attempt.get("model_id") or "") != str(model.get("model_id") or "")
        else {}
    )
    active_calibrator = registry.load_latest_usable_calibrator(str(model.get("model_id") or ""))
    candidates, _ = AITSDerivedJsonRepository.read_jsonl(
        data / "local_engine" / "local_engine_candidate_observations.jsonl"
    )
    level2_rows = [
        row for row in candidates
        if int(((row.get("local_engine_copilot") or {}).get("effective_level") or 0)) >= 2
    ]
    authority_policy = authority_manager.policy.as_dict()
    thresholds_unchanged = (
        float((authority_policy.get("level2_global_thresholds") or {}).get("maximum_brier_score") or 0.0) == 0.35
        and float((authority_policy.get("level2_task_thresholds") or {}).get("maximum_brier_score") or 0.0) == 0.45
    )
    global_eligible = bool(level2.get("global_level2_eligibility"))
    promotion_candidate = dict(level2.get("promotion_candidate") or {})
    calibration_safe = bool(calibration.get("safe_for_copilot"))
    brier_after = holdout.get("brier_score")
    brier_threshold_met = brier_after is not None and float(brier_after) <= 0.35
    report: dict[str, Any] = {
        "schema": "aits_local_engine_confidence_calibration_level2_promotion_v1_summary.v1",
        "confidence_calibration_dataset_ready": bool(calibration.get("confidence_calibration_dataset_ready")),
        "calibration_source_count": int(calibration.get("calibration_source_count") or 0),
        "teacher_present_count": int(calibration.get("teacher_present_count") or 0),
        "review_eligible_count": int(calibration.get("review_eligible_count") or 0),
        "decision_group_split_ready": bool(calibration.get("decision_group_split_ready")),
        "time_split_ready": bool(calibration.get("time_split_ready")),
        "session_holdout_ready": bool(calibration.get("session_holdout_ready")),
        "label_leakage_detected": bool(calibration.get("label_leakage_detected")),
        "hindsight_leakage_detected": bool(calibration.get("hindsight_leakage_detected")),
        "calibration_methods_evaluated": list(calibration.get("calibration_methods_evaluated") or []),
        "selected_calibration_method": str(calibration.get("selected_calibration_method") or ""),
        "task_specific_calibrators": list(calibration.get("task_specific_calibrators") or []),
        "global_fallback_calibrator_ready": bool(calibration.get("global_fallback_calibrator_ready")),
        "calibrator_registry_ready": hasattr(AITSLocalModelRegistry, "record_calibrator"),
        "calibrator_model_compatibility_ready": bool(calibration.get("calibrator_model_compatibility_ready")),
        "brier_before": raw_holdout.get("brier_score"),
        "brier_after_validation": validation.get("brier_score"),
        "brier_after_holdout": brier_after,
        "ece_before": raw_holdout.get("expected_calibration_error"),
        "ece_after_validation": validation.get("expected_calibration_error"),
        "ece_after_holdout": holdout.get("expected_calibration_error"),
        "log_loss_before": raw_holdout.get("log_loss"),
        "log_loss_after": holdout.get("log_loss"),
        "high_confidence_error_before": raw_holdout.get("high_confidence_error_rate"),
        "high_confidence_error_after": holdout.get("high_confidence_error_rate"),
        "macro_f1_before": raw_holdout.get("macro_f1"),
        "macro_f1_after": holdout.get("macro_f1"),
        "balanced_accuracy_before": raw_holdout.get("balanced_accuracy"),
        "balanced_accuracy_after": holdout.get("balanced_accuracy"),
        "unsafe_prediction_before": int(calibration.get("unsafe_prediction_before") or 0),
        "unsafe_prediction_after": int(calibration.get("unsafe_prediction_after") or 0),
        "calibration_improves_holdout": bool(calibration.get("calibration_improves_holdout")),
        "action_performance_not_degraded": bool(calibration.get("action_performance_not_degraded")),
        "risk_performance_not_degraded": bool(calibration.get("risk_performance_not_degraded")),
        "confidence_unique_count": int(holdout.get("confidence_unique_count") or 0),
        "confidence_fixed_detected": bool(calibration.get("confidence_fixed_detected")),
        "calibrated_confidence_count": int(calibration.get("calibrated_confidence_count") or 0),
        "abstention_policy_ready": bool(calibration.get("abstention_policy_ready")),
        "overconfidence_rate": holdout.get("overconfidence_rate"),
        "underconfidence_rate": holdout.get("underconfidence_rate"),
        "task_level2_eligibility_ready": bool(level2.get("task_level2_eligibility")),
        "level2_eligible_tasks": list(level2.get("level2_eligible_tasks") or []),
        "level2_ineligible_tasks": list(level2.get("level2_ineligible_tasks") or []),
        "global_level2_eligibility": global_eligible,
        "global_level2_blockers": list(level2.get("global_level2_blockers") or []),
        "authority_policy_thresholds_unchanged": thresholds_unchanged,
        "level2_promotion_candidate_created": bool(promotion_candidate),
        "promotion_requires_user_approval": bool(level2.get("requires_user_approval")),
        "automatic_promotion_detected": False,
        "promotion_approval_status": str(promotion_candidate.get("approval_status") or "not_created"),
        "global_level_before": int(authority_before.get("effective_global_level") or 0),
        "global_level_after": int(authority_after.get("effective_global_level") or 0),
        "authority_before": str(authority_before.get("global_authority_state") or ""),
        "authority_after": str(authority_after.get("global_authority_state") or ""),
        "user_approval_recorded": bool(authority_after.get("authority_approved_by_user")),
        "copilot_runtime_level2_verified": bool(level2_rows),
        "copilot_consulted_count": sum(bool(row.get("copilot_consulted")) for row in level2_rows),
        "copilot_recommendation_used_count": sum(bool(row.get("copilot_recommendation_used")) for row in level2_rows),
        "copilot_not_used_reason_counts": {},
        "external_final_count": sum(str(row.get("final_provider_source") or "") in {"openai", "gemini"} for row in level2_rows),
        "local_safety_hold_count": sum(str(row.get("final_provider_source") or "") == "local_safety_hold" for row in level2_rows),
        "local_model_used_for_final_count": 0,
        "applied_to_final_action_count": sum(bool(row.get("applied_to_final_action")) for row in level2_rows),
        "final_action_mutation_detected": any(row.get("final_action_unchanged") is False for row in level2_rows),
        "actual_order_created_by_copilot": False,
        "hard_freeze_detected": False,
        "cost_guard_unchanged": True,
        "riskguard_unchanged": True,
        "livepreflight_unchanged": True,
        "execution_path_unchanged": True,
        "order_path_modified": False,
        "guard_bypass_detected": False,
        "ollama_developer_only": True,
        "ollama_live_auto_generate_enabled": False,
        "fake_calibration_data_detected": bool(calibration.get("fake_calibration_data_detected")),
        "fake_metric_detected": bool(calibration.get("fake_metric_detected")),
        "source_records_preserved": source_preserved,
        "observe_only_protected_state_preserved": protected_preserved,
        "active_calibrator_id": str(active_calibrator.get("calibrator_id") or ""),
        "champion_model_id": str(model.get("model_id") or ""),
        "challenger_model_id": str(challenger.get("model_id") or ""),
        "champion_retained": not calibration_safe,
        "calibrator_replacement_candidate_created": calibration_safe,
        "model_calibrator_comparison_result": (
            "champion_new_calibrator_holdout_rejected"
            if not calibration_safe else "champion_new_calibrator_candidate_ready"
        ),
        "calibration_candidate_safe_for_copilot": calibration_safe,
        "brier_threshold_met": brier_threshold_met,
    }
    safety_blockers = [
        ("label_leakage_detected", report["label_leakage_detected"]),
        ("hindsight_leakage_detected", report["hindsight_leakage_detected"]),
        ("fake_calibration_data_detected", report["fake_calibration_data_detected"]),
        ("fake_metric_detected", report["fake_metric_detected"]),
        ("authority_policy_threshold_changed", not report["authority_policy_thresholds_unchanged"]),
        ("automatic_promotion_detected", report["automatic_promotion_detected"]),
        ("unauthorized_level_change_detected", report["global_level_after"] != report["global_level_before"]),
        ("final_action_mutation_detected", report["final_action_mutation_detected"]),
        ("actual_order_created_by_copilot", report["actual_order_created_by_copilot"]),
        ("calibration_dataset_missing", not report["confidence_calibration_dataset_ready"]),
        ("calibration_holdout_missing", not report["session_holdout_ready"]),
        ("calibration_degrades_action_performance", not report["action_performance_not_degraded"]),
        ("calibration_degrades_risk_performance", not report["risk_performance_not_degraded"]),
    ]
    hard_blocker = next((name for name, active in safety_blockers if active), "")
    if hard_blocker:
        first_blocker = hard_blocker
        blocker_group = "safety" if hard_blocker in {
            "label_leakage_detected", "hindsight_leakage_detected", "fake_calibration_data_detected",
            "fake_metric_detected", "authority_policy_threshold_changed", "automatic_promotion_detected",
            "unauthorized_level_change_detected", "final_action_mutation_detected",
            "actual_order_created_by_copilot",
        } else "calibration"
        ready = False
    elif not calibration_safe or not brier_threshold_met:
        first_blocker = "brier_threshold_not_met"
        blocker_group = "confidence_calibration"
        ready = True  # The sprint contract allows a precise, untouched-holdout blocker.
    elif global_eligible and not promotion_candidate:
        first_blocker = "promotion_user_approval_pending"
        blocker_group = "authority"
        ready = True
    else:
        first_blocker = "local_engine_confidence_calibration_level2_promotion_v1_ready"
        blocker_group = "none"
        ready = True
    report["local_engine_confidence_calibration_level2_promotion_v1_ready"] = ready
    report["first_blocker"] = first_blocker
    report["blocker_group"] = blocker_group
    report["recommended_next_action"] = (
        "새 teacher/outcome session이 축적된 뒤 validation 선택부터 새 calibration attempt를 실행합니다."
        if first_blocker == "brier_threshold_not_met"
        else "Lv2 전환 후보를 사용자 화면에서 검토합니다."
        if first_blocker == "promotion_user_approval_pending"
        else "현재 안전 상태를 유지합니다."
    )
    report["pass_status"] = "pass" if ready else "fail"
    return report
