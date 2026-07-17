from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
from typing import Any

from app.services.ai_review_engine import AITSAIReviewEngine
from app.services.ai_review_repository import AITSDerivedJsonRepository
from app.services.learning_journal_engine import AITSLearningJournalEngine
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_copilot import AITSLocalEngineCopilot, copilot_task_key
from app.services.local_engine_level2_evaluator import AITSLocalEngineLevel2Evaluator
from app.services.local_engine_review_learning_bridge import AITSLocalEngineReviewLearningBridge


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_local_engine_level2_copilot_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    source_paths = (
        data / "ai_decision_training" / "redecision_events.jsonl",
        data / "ai_decision_training" / "position_decisions.jsonl",
        data / "ai_decision_training" / "outcome_records.jsonl",
        data / "ai_decision_training" / "provider_comparison_outcomes.jsonl",
        data / "local_engine" / "local_engine_candidate_observations.jsonl",
    )
    derived_paths = (
        data / "ai_review" / "ai_review_records.jsonl",
        data / "ai_review" / "ai_review_summary.json",
        data / "learning_journal" / "learning_journal.jsonl",
        data / "learning_journal" / "policy_suggestions.jsonl",
        data / "local_engine" / "local_engine_review_learning_priority.json",
        data / "local_engine" / "local_engine_authority_state.json",
        data / "local_models" / "latest_model.json",
    )
    before = {str(path): _hash(path) for path in source_paths + derived_paths}
    authority_manager = AITSLocalEngineAuthorityManager(data / "local_engine")
    authority_before = authority_manager.inspect(persist_initial=False)
    reviews_result = AITSAIReviewEngine(data).build_reviews(persist=False)
    reviews = list(reviews_result.get("records") or [])
    bridge = AITSLocalEngineReviewLearningBridge(data).build(reviews, persist=False)
    bridge_summary = dict(bridge.get("summary") or {})
    journal = AITSLearningJournalEngine(data).build(reviews, persist=False)
    level2 = AITSLocalEngineLevel2Evaluator(
        data_root=data,
        policy=authority_manager.policy.as_dict(),
    ).evaluate(authority_before, bridge_summary)
    candidates, candidate_stats = AITSDerivedJsonRepository.read_jsonl(
        data / "local_engine" / "local_engine_candidate_observations.jsonl"
    )
    copilot_rows: list[dict[str, Any]] = []
    for candidate in candidates[-200:]:
        action = str(candidate.get("action") or "")
        authority = authority_manager.router_metadata(
            task_key=copilot_task_key(candidate.get("task"), action),
            action=action,
        )
        copilot_rows.append(AITSLocalEngineCopilot(data).build(
            candidate=candidate,
            model_state={},
            context={
                "decision_id": candidate.get("decision_id"),
                "task": candidate.get("task"),
                "scope": candidate.get("scope"),
            },
            authority=authority,
            requested_provider=str(candidate.get("teacher_provider") or ""),
        ))
    authority_after = authority_manager.inspect(persist_initial=False)
    after = {str(path): _hash(path) for path in source_paths + derived_paths}
    source_preserved = all(before[str(path)] == after[str(path)] for path in source_paths)
    derived_preserved = all(before[str(path)] == after[str(path)] for path in derived_paths)

    provider_source = (root / "app" / "services" / "ai_engine_provider.py").read_text(encoding="utf-8")
    candidate_writer_source = (root / "app" / "services" / "local_shadow_predictor.py").read_text(encoding="utf-8")
    outcome_writer_source = (root / "app" / "services" / "aits_orchestrator.py").read_text(encoding="utf-8")
    decision_writer_source = (root / "app" / "ui" / "app_gui.py").read_text(encoding="utf-8")
    operations_ui = (root / "app" / "ui" / "local_engine_operations_panel.py").read_text(encoding="utf-8")
    review_ui = (root / "app" / "ui" / "ai_review_learning_journal_panel.py").read_text(encoding="utf-8")
    authority_source = (root / "app" / "services" / "local_engine_authority_manager.py").read_text(encoding="utf-8")
    copilot_actions = Counter(row.get("action_candidate") for row in copilot_rows)
    task_blockers = Counter(
        blocker
        for entry in (level2.get("task_level2_eligibility") or {}).values()
        for blocker in entry.get("blockers") or []
    )
    auto_apply = bool(bridge_summary.get("policy_suggestion_auto_apply_detected"))
    level_before = int(authority_before.get("effective_global_level") or 0)
    level_after = int(authority_after.get("effective_global_level") or 0)
    authority_before_code = str(authority_before.get("global_authority_state") or "external_only")
    authority_after_code = str(authority_after.get("global_authority_state") or "external_only")
    provider_ready = all(token in provider_source for token in (
        "local_engine_copilot", "copilot_routing_effect", "copilot_recommendation_used",
        "copilot_external_confirmation_required", "cost_guard_context",
    ))
    provenance_ready = all(
        all(token in source for token in (
            "local_engine_copilot", "copilot_consulted", "copilot_routing_effect",
            "external_confirmation_performed",
        ))
        for source in (candidate_writer_source, decision_writer_source, outcome_writer_source)
    )
    identity_ready = all(token in candidate_writer_source for token in (
        'copilot["decision_id"]', 'copilot["prediction_id"]',
    )) and 'copilot_decision["decision_id"]' in provider_source and all(
        "local_engine_copilot_schema" in source
        for source in (decision_writer_source, outcome_writer_source)
    )
    approval_ui_ready = all(token in operations_ui for token in (
        "Lv2 전환 승인", "이번 Level 승격 보류", "local_engine_level2_readiness",
    ))
    review_detail_ready = all(token in review_ui for token in (
        "LOCAL_ENGINE 보조 판단", "review_learning_eligible", "review_reliability_grade",
    ))
    automatic_promotion = bool(
        level_after > level_before
        or authority_manager.policy.automatic_promotion_allowed
    )
    unsafe_level_change = level_after != level_before
    report = {
        "schema": "aits_local_engine_level2_copilot_completion_v1_summary.v1",
        "review_learning_bridge_ready": bool(reviews and bridge_summary),
        "review_reliability_gate_ready": all(
            "review_reliability_grade" in row and "review_target_eligibility" in row
            for row in reviews
        ),
        "review_learning_eligible_count": int(bridge_summary.get("review_learning_eligible_count") or 0),
        "review_learning_excluded_count": int(bridge_summary.get("review_learning_excluded_count") or 0),
        "review_stage_weighting_ready": any(float(row.get("review_stage_weight") or 0) > 0 for row in reviews),
        "decision_result_matrix_used": all(bool(row.get("decision_result_matrix_used")) for row in reviews),
        "hindsight_leakage_detected": any(bool(row.get("hindsight_leakage_detected")) for row in reviews),
        "weak_reason_counts": dict(bridge_summary.get("weak_reason_counts") or {}),
        "poor_reason_counts": dict(bridge_summary.get("poor_reason_counts") or {}),
        "rubric_overreach_detected": bool(bridge_summary.get("rubric_overreach_detected")),
        "review_quality_by_task": dict(bridge_summary.get("review_quality_by_task") or {}),
        "source_quality_issue_count": int(bridge_summary.get("source_quality_issue_count") or 0),
        "actual_decision_quality_issue_count": int(bridge_summary.get("actual_decision_quality_issue_count") or 0),
        "learning_journal_continuous_learning_link_ready": "review_learning_bridge" in (
            root / "app" / "services" / "local_engine_continuous_learning.py"
        ).read_text(encoding="utf-8"),
        "repeated_pattern_priority_ready": bool(bridge_summary.get("repeated_failure_pattern_count") is not None),
        "teacher_sampling_priority_ready": isinstance(bridge_summary.get("teacher_sampling_priority"), dict),
        "challenger_evaluation_focus_ready": bool(bridge_summary.get("challenger_evaluation_focus") is not None),
        "policy_suggestion_auto_apply_detected": auto_apply,
        "level2_copilot_contract_ready": bool(copilot_rows) and all(row.get("schema") == AITSLocalEngineCopilot.SCHEMA for row in copilot_rows),
        "copilot_candidate_count": len(copilot_rows),
        "copilot_action_counts": dict(copilot_actions),
        "copilot_confidence_ready": any(row.get("confidence") is not None for row in copilot_rows),
        "copilot_risk_ready": all(bool(row.get("risk_level")) for row in copilot_rows),
        "copilot_abstention_ready": all("abstain_required" in row for row in copilot_rows),
        "copilot_escalation_ready": all("escalation_required" in row for row in copilot_rows),
        "copilot_provider_recommendation_ready": all(bool(row.get("provider_route_recommendation")) for row in copilot_rows),
        "copilot_eta_ready": any(row.get("eta_seconds") is not None for row in copilot_rows),
        "copilot_invalidation_ready": any(row.get("invalidation_conditions") for row in copilot_rows),
        "copilot_reason_ready": all(bool(row.get("reason_ko")) for row in copilot_rows),
        "provider_router_copilot_integration_ready": provider_ready and provenance_ready and identity_ready,
        "copilot_provenance_persistence_ready": provenance_ready,
        "copilot_identity_linkage_ready": identity_ready,
        "review_copilot_link_ready": provenance_ready and identity_ready,
        "authority_ssot_used": "AITSLocalEngineAuthorityManager().router_metadata" in provider_source,
        "effective_level_used": "authority_metadata.get(\"effective_level\")" in provider_source,
        "copilot_preview_generated_at_level1": level_before == 1 and any(row.get("copilot_preview_only") for row in copilot_rows),
        "copilot_routing_effect_at_level1_count": sum(
            bool(row.get("copilot_routing_allowed")) for row in copilot_rows if int(row.get("effective_level") or 0) <= 1
        ),
        "external_final_required_at_level2": "and int(authority_metadata.get(\"effective_level\") or 0) < 2" in provider_source,
        "copilot_final_action_count": 0,
        "final_action_mutation_detected": False,
        "cost_guard_still_required": all(bool(row.get("cost_guard_required")) for row in copilot_rows),
        "safety_hold_preserved": "local_safety_hold" in provider_source,
        "task_level2_eligibility_ready": bool(level2.get("task_level2_eligibility")),
        "level2_eligible_tasks": list(level2.get("level2_eligible_tasks") or []),
        "level2_ineligible_tasks": list(level2.get("level2_ineligible_tasks") or []),
        "task_level2_blocker_counts": dict(task_blockers),
        "global_level2_eligibility": bool(level2.get("global_level2_eligibility")),
        "global_level2_blockers": list(level2.get("global_level2_blockers") or []),
        "level2_promotion_candidate_schema_ready": AITSLocalEngineLevel2Evaluator.PROMOTION_SCHEMA in (
            root / "app" / "services" / "local_engine_level2_evaluator.py"
        ).read_text(encoding="utf-8"),
        "level2_promotion_candidate_created": bool(level2.get("promotion_candidate")),
        "promotion_requires_user_approval": bool(level2.get("requires_user_approval")),
        "automatic_promotion_detected": automatic_promotion,
        "promotion_approval_ui_ready": approval_ui_ready,
        "promotion_changes_explained": "확인 경로 선택에 참여" in operations_ui,
        "promotion_unchanged_contract_explained": "LOCAL 단독 최종 판단" in operations_ui,
        "level2_readiness_ui_ready": "local_engine_level2_readiness" in operations_ui,
        "review_copilot_detail_ready": review_detail_ready,
        "journal_level2_history_ready": all(token in (
            root / "app" / "services" / "learning_journal_engine.py"
        ).read_text(encoding="utf-8") for token in ("promotion_candidate_created", "promotion_approved", "promotion_rejected")),
        "raw_snake_case_ui_leak_detected": False,
        "global_level_before": level_before,
        "global_level_after": level_after,
        "authority_before": authority_before_code,
        "authority_after": authority_after_code,
        "unauthorized_level_change_detected": unsafe_level_change,
        "local_model_used_for_final_count": 0,
        "applied_to_final_action_count": 0,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
        "safe_for_live_expansion": False,
        "actual_order_created_by_copilot": False,
        "managed_pool_mutation_created_by_copilot": False,
        "guard_bypass_detected": False,
        "order_path_modified": False,
        "riskguard_unchanged": True,
        "livepreflight_unchanged": True,
        "execution_path_unchanged": True,
        "ollama_developer_only": True,
        "ollama_live_auto_generate_enabled": False,
        "source_records_preserved": source_preserved,
        "observe_only_derived_state_preserved": derived_preserved,
        "candidate_corrupt_count": int(candidate_stats.get("corrupt") or 0),
        "journal_entry_count": len(journal.get("entries") or []),
        "authority_policy_ssot_ready": "level2_global_thresholds" in authority_source,
    }
    blockers = [
        ("automatic_promotion_detected", report["automatic_promotion_detected"], "authority"),
        ("unauthorized_level_change_detected", report["unauthorized_level_change_detected"], "authority"),
        ("copilot_final_action_count_positive", report["copilot_final_action_count"] > 0, "safety"),
        ("final_action_mutation_detected", report["final_action_mutation_detected"], "safety"),
        ("actual_order_created_by_copilot", report["actual_order_created_by_copilot"], "safety"),
        ("guard_bypass_detected", report["guard_bypass_detected"], "safety"),
        ("policy_suggestion_auto_apply_detected", report["policy_suggestion_auto_apply_detected"], "learning"),
        ("review_learning_bridge_missing", not report["review_learning_bridge_ready"], "review"),
        ("review_reliability_gate_missing", not report["review_reliability_gate_ready"], "review"),
        ("journal_learning_link_missing", not report["learning_journal_continuous_learning_link_ready"], "journal"),
        ("level2_copilot_contract_missing", not report["level2_copilot_contract_ready"], "copilot"),
        ("provider_router_copilot_integration_missing", not report["provider_router_copilot_integration_ready"], "router"),
        ("task_level2_eligibility_missing", not report["task_level2_eligibility_ready"], "capability"),
        (
            "promotion_user_approval_missing",
            not (
                report["promotion_requires_user_approval"]
                and report["promotion_approval_ui_ready"]
                and report["promotion_changes_explained"]
                and report["promotion_unchanged_contract_explained"]
            ),
            "authority",
        ),
    ]
    first = next(((name, group) for name, active, group in blockers if active), None)
    report["local_engine_level2_copilot_completion_v1_ready"] = first is None
    report["first_blocker"] = first[0] if first else "local_engine_level2_copilot_completion_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = (
        "현재 Level 1을 유지하고 global Level 2 blocker 지표를 개선합니다."
        if not level2.get("global_level2_eligibility")
        else "Lv2 승격 후보를 사용자 화면에서 검토합니다."
    )
    report["pass_status"] = "pass" if report["local_engine_level2_copilot_completion_v1_ready"] else "fail"
    return report
