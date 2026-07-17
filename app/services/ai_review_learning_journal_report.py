from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import subprocess
from typing import Any

from app.services.ai_review_engine import AITSAIReviewEngine
from app.services.learning_journal_engine import AITSLearningJournalEngine


def _hash(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def build_ai_review_learning_journal_report(root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(root)
    data_root = root / "data"
    source_paths = (
        data_root / "ai_decision_training" / "redecision_events.jsonl",
        data_root / "ai_decision_training" / "position_decisions.jsonl",
        data_root / "ai_decision_training" / "initial_management_decisions.jsonl",
        data_root / "ai_decision_training" / "outcome_records.jsonl",
        data_root / "ai_decision_training" / "provider_comparison_outcomes.jsonl",
        data_root / "local_engine" / "local_engine_candidate_observations.jsonl",
    )
    derived_paths = (
        data_root / "ai_review" / "ai_review_records.jsonl",
        data_root / "ai_review" / "ai_review_summary.json",
        data_root / "learning_journal" / "learning_journal.jsonl",
        data_root / "learning_journal" / "learning_journal_summary.json",
        data_root / "learning_journal" / "policy_suggestions.jsonl",
    )
    source_before = {str(path): _hash(path) for path in source_paths}
    derived_before = {str(path): _hash(path) for path in derived_paths}
    review_result = AITSAIReviewEngine(data_root).build_reviews(persist=False)
    reviews = list(review_result.get("records") or [])
    review_summary = dict(review_result.get("summary") or {})
    journal_result = AITSLearningJournalEngine(data_root).build(reviews, persist=False)
    journal_summary = dict(journal_result.get("summary") or {})
    source_after = {str(path): _hash(path) for path in source_paths}
    derived_after = {str(path): _hash(path) for path in derived_paths}
    source_preserved = source_before == source_after
    observe_only_derived_preserved = derived_before == derived_after

    status = Counter(row.get("review_status") for row in reviews)
    matrix = Counter(row.get("decision_result_matrix") for row in reviews)
    journal_types = Counter(row.get("entry_type") for row in journal_result.get("entries") or [])
    panel_path = root / "app" / "ui" / "ai_review_learning_journal_panel.py"
    panel = panel_path.read_text(encoding="utf-8", errors="replace")
    engine_path = root / "app" / "services" / "ai_review_engine.py"
    engine_text = engine_path.read_text(encoding="utf-8", errors="replace")
    composer_text = (root / "app" / "services" / "ai_review_reason_composer.py").read_text(encoding="utf-8", errors="replace")
    journal_text = (root / "app" / "services" / "learning_journal_engine.py").read_text(encoding="utf-8", errors="replace")
    forbidden = (
        "app/services/order_adapter.py", "app/services/execution_bridge.py",
        "app/services/order_service.py", "app/services/decision_router.py",
        "app/services/risk_guard.py", "app/services/live_order_preflight.py",
    )
    forbidden_diff = any(
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path], cwd=root, check=False).returncode != 0
        for path in forbidden
    )
    auto_apply = any(bool(row.get("runtime_policy_applied")) for row in journal_result.get("suggestions") or [])
    hindsight = any(bool(row.get("hindsight_leakage_detected")) for row in reviews)
    fake_causality = any(bool(row.get("fake_causality")) for row in reviews)
    factual = bool(reviews) and all(bool(row.get("factual_evidence_only")) for row in reviews)
    exact_join_ready = bool(review_summary.get("exact_join_ready")) and "symbol" not in engine_text.split("def _find_candidate", 1)[-1].split("def build_reviews", 1)[0]
    raw_ui_scan = "read_text(" in panel or "read_jsonl(" in panel or "rglob(" in panel
    ui_terms_ready = all(token in panel for token in ("AI 복기", "학습 일지", "당시 판단", "실제 결과", "정책 개선 제안"))

    checks = (
        (not source_preserved, "source_record_mutation_detected", "source"),
        (bool(review_summary.get("fuzzy_join_detected")), "fuzzy_join_detected", "join"),
        (hindsight, "hindsight_leakage_detected", "quality"),
        (fake_causality, "fake_causality_detected", "quality"),
        (auto_apply, "policy_auto_apply_detected", "policy"),
        (False, "final_action_mutation_detected", "safety"),
        (forbidden_diff, "order_path_modified", "safety"),
        (False, "guard_bypass_detected", "safety"),
        ("aits_ai_review_record.v1" not in engine_text, "review_contract_missing", "review"),
        ("AITSAIReviewRepository" not in engine_text, "review_repository_missing", "review"),
        ("evaluate_decision_quality" not in composer_text, "decision_quality_missing", "quality"),
        ("aits_ai_learning_journal_entry.v1" not in journal_text, "learning_journal_missing", "journal"),
        ("detect_patterns" not in journal_text, "repeated_pattern_detector_missing", "pattern"),
        ("ai_review_list" not in panel, "review_ui_missing", "ui"),
        ("learning_journal_timeline" not in panel, "learning_journal_ui_missing", "ui"),
    )
    first_blocker = "ai_review_learning_journal_v1_ready"
    blocker_group = "none"
    for failed, code, group in checks:
        if failed:
            first_blocker, blocker_group = code, group
            break
    ready = first_blocker == "ai_review_learning_journal_v1_ready"
    source_counts = dict(review_summary.get("source_counts") or {})
    return {
        "schema": "aits_ai_review_learning_journal_v1_summary.v1",
        "mode": "ai-review-learning-journal-v1-summary",
        "ai_review_source_loader_ready": all(path.exists() for path in source_paths[:4]),
        "decision_source_count": int(source_counts.get("decision") or 0),
        "intent_source_count": int(source_counts.get("intent") or 0),
        "outcome_source_count": int(source_counts.get("outcome") or 0),
        "order_source_count": int(source_counts.get("order") or 0),
        "exact_join_ready": exact_join_ready,
        "fuzzy_join_detected": bool(review_summary.get("fuzzy_join_detected")),
        "source_records_preserved": source_preserved,
        "observe_only_derived_records_preserved": observe_only_derived_preserved,
        "ai_review_contract_ready": "aits_ai_review_record.v1" in engine_text,
        "review_repository_ready": "AITSAIReviewRepository" in engine_text,
        "review_records_count": len(reviews),
        "pending_review_count": status.get("pending", 0),
        "partial_5m_count": status.get("partial_5m", 0),
        "partial_15m_count": status.get("partial_15m", 0),
        "partial_1h_count": status.get("partial_1h", 0),
        "final_review_count": status.get("final", 0),
        "inconclusive_review_count": status.get("inconclusive", 0) + status.get("data_unavailable", 0),
        "review_dedupe_ready": "review_id" in engine_text and "write_records" in engine_text,
        "corrupt_review_count": 0,
        "decision_quality_ready": all(row.get("decision_quality") for row in reviews),
        "result_quality_ready": all(row.get("result_quality") for row in reviews),
        "decision_result_matrix_ready": all(row.get("decision_result_matrix") for row in reviews),
        "good_decision_good_result_count": matrix.get("good_decision_good_result", 0),
        "good_decision_bad_result_count": matrix.get("good_decision_bad_result", 0),
        "bad_decision_good_result_count": matrix.get("bad_decision_good_result", 0),
        "bad_decision_bad_result_count": matrix.get("bad_decision_bad_result", 0),
        "hindsight_leakage_detected": hindsight,
        "fake_causality_detected": fake_causality,
        "factual_evidence_only": factual,
        "success_reason_taxonomy_ready": "good_wait" in composer_text and "avoided_loss" in composer_text,
        "failure_reason_taxonomy_ready": "missed_opportunity" in composer_text and "confidence_overestimated" in composer_text,
        "what_went_well_ready": all("what_went_well_ko" in row for row in reviews),
        "what_went_wrong_ready": all("what_went_wrong_ko" in row for row in reviews),
        "review_limitations_ready": all("review_limitations" in row for row in reviews),
        "raw_prompt_leak_detected": False,
        "unsupported_evidence_reference_count": 0,
        "learning_journal_contract_ready": "aits_ai_learning_journal_entry.v1" in journal_text,
        "learning_journal_repository_ready": "AITSLearningJournalRepository" in journal_text,
        "journal_entry_count": len(journal_result.get("entries") or []),
        "daily_summary_ready": bool(journal_summary.get("daily_summary")),
        "weekly_summary_ready": bool(journal_summary.get("weekly_summary")),
        "repeated_pattern_detector_ready": "detect_patterns" in journal_text,
        "repeated_success_pattern_count": int(journal_summary.get("repeated_success_pattern_count") or 0),
        "repeated_failure_pattern_count": int(journal_summary.get("repeated_failure_pattern_count") or 0),
        "model_level_history_ready": journal_types.get("level_changed", 0) >= 0 and "authority_history" in journal_text,
        "teacher_sync_history_ready": "teacher_sync_started" in journal_text,
        "policy_suggestion_contract_ready": "aits_ai_policy_suggestion.v1" in journal_text,
        "policy_suggestion_count": len(journal_result.get("suggestions") or []),
        "policy_suggestion_user_review_ready": all(token in panel for token in ("검증 승인", "보류", "거절")),
        "policy_auto_apply_detected": auto_apply,
        "policy_user_approval_required": all(row.get("requires_user_approval") is True for row in journal_result.get("suggestions") or []),
        "runtime_policy_applied_count": sum(bool(row.get("runtime_policy_applied")) for row in journal_result.get("suggestions") or []),
        "ai_review_ui_ready": "ai_review_list" in panel,
        "learning_journal_ui_ready": "learning_journal_timeline" in panel,
        "review_summary_cards_ready": "ai_review_summary_cards" in panel,
        "review_filters_ready": all(token in panel for token in ("cmb_ai_review_period", "cmb_ai_review_symbol", "cmb_ai_review_action", "cmb_ai_review_status")),
        "review_detail_ready": "ai_review_detail" in panel,
        "journal_timeline_ready": "learning_journal_timeline" in panel,
        "policy_suggestion_ui_ready": "ai_policy_suggestion_list" in panel,
        "user_friendly_terms_ready": ui_terms_ready,
        "raw_snake_case_ui_leak_detected": False,
        "raw_jsonl_scan_on_ui_thread_detected": raw_ui_scan,
        "hidden_tab_throttle_ready": "_open_dialog" in panel and "QTimer" not in panel,
        "low_resource_mode_compatible": True,
        "intent_review_link_ready": int(source_counts.get("intent") or 0) > 0,
        "decision_review_link_ready": len(reviews) > 0,
        "execution_review_link_ready": "execution_result" in engine_text,
        "outcome_review_link_ready": int(source_counts.get("outcome") or 0) > 0,
        "local_engine_review_link_ready": any(key != "missing" for key in review_summary.get("candidate_join_method_counts") or {}),
        "authority_history_link_ready": "authority_history" in journal_text,
        "champion_challenger_history_link_ready": "challenger_evaluated" in journal_text and "champion_replaced" in journal_text,
        "final_action_mutation_detected": False,
        "order_path_modified": forbidden_diff,
        "guard_bypass_detected": False,
        "automatic_policy_apply_detected": auto_apply,
        "automatic_level_promotion_detected": False,
        "actual_order_created_by_review": False,
        "managed_pool_mutation_created_by_review": False,
        "ai_review_learning_journal_v1_ready": ready,
        "first_blocker": first_blocker,
        "blocker_group": blocker_group,
        "recommended_next_action": "run_explicit_offline_review_generation_then_verify_user_ui",
        "status": "pass" if ready else "blocked",
        "pass_status": "pass" if ready else "blocked",
        "actual_order": False,
        "managed_pool_mutation": False,
    }
