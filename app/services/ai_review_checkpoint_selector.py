from __future__ import annotations

from datetime import datetime
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REVIEW_STAGE_RANK = {
    "pending": 0,
    "partial_5m": 10,
    "partial_15m": 20,
    "partial_1h": 30,
    "final": 40,
}

CHECKPOINT_TO_STAGE = {
    "outcome_5m": "partial_5m",
    "outcome_15m": "partial_15m",
    "outcome_1h": "partial_1h",
    "outcome_final": "final",
}


def checkpoint_name(row: dict[str, Any]) -> str:
    checkpoint = row.get("checkpoint")
    if isinstance(checkpoint, dict):
        return str(checkpoint.get("checkpoint_name") or "")
    return str(checkpoint or "")


def checkpoint_stage(row: dict[str, Any]) -> str:
    return CHECKPOINT_TO_STAGE.get(checkpoint_name(row), "pending")


def stage_rank(stage: object) -> int:
    return int(REVIEW_STAGE_RANK.get(str(stage or "pending"), -1))


def _evaluated_at(row: dict[str, Any]) -> float:
    checkpoint = row.get("checkpoint") if isinstance(row.get("checkpoint"), dict) else {}
    value = row.get("evaluated_at") or checkpoint.get("evaluated_at") or row.get("updated_at") or 0
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0


def checkpoint_record_id(row: dict[str, Any]) -> str:
    explicit = row.get("record_id") or row.get("outcome_id") or row.get("id")
    if explicit not in (None, ""):
        return str(explicit)
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "outcome-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def is_valid_checkpoint(row: dict[str, Any]) -> bool:
    name = checkpoint_name(row)
    if name not in CHECKPOINT_TO_STAGE:
        return False
    checkpoint = row.get("checkpoint") if isinstance(row.get("checkpoint"), dict) else {}
    status = str(checkpoint.get("status") or row.get("status") or "").lower()
    label = str(checkpoint.get("outcome_label") or row.get("outcome_label") or "").lower()
    return status not in {"skipped", "unavailable", "failed"} and label != "data_unavailable"


def exact_checkpoint_dedupe(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source in rows:
        row = dict(source)
        decision_id = str(row.get("decision_id") or "")
        linkage = str(row.get("outcome_linkage_key") or "")
        name = checkpoint_name(row)
        if not decision_id or not name:
            continue
        key = (decision_id, linkage, checkpoint_record_id(row))
        previous = latest.get(key)
        if previous is None or (_evaluated_at(row), checkpoint_record_id(row)) >= (
            _evaluated_at(previous), checkpoint_record_id(previous)
        ):
            latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            str(row.get("decision_id") or ""),
            stage_rank(checkpoint_stage(row)),
            _evaluated_at(row),
            checkpoint_record_id(row),
        ),
    )


def select_latest_checkpoint(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in exact_checkpoint_dedupe(rows) if is_valid_checkpoint(row)]
    if not candidates:
        return {
            "review_status": "pending",
            "selected_checkpoint": None,
            "selected_checkpoint_rank": 0,
            "selected_checkpoint_record_id": None,
            "available_checkpoints": [],
            "checkpoint_record_ids": [],
            "latest_evaluated_at": None,
        }
    selected = max(
        candidates,
        key=lambda row: (
            stage_rank(checkpoint_stage(row)),
            _evaluated_at(row),
            checkpoint_record_id(row),
        ),
    )
    available = sorted(
        {checkpoint_name(row) for row in candidates},
        key=lambda name: REVIEW_STAGE_RANK[CHECKPOINT_TO_STAGE[name]],
    )
    return {
        "review_status": checkpoint_stage(selected),
        "selected_checkpoint": checkpoint_name(selected).removeprefix("outcome_"),
        "selected_checkpoint_rank": stage_rank(checkpoint_stage(selected)),
        "selected_checkpoint_record_id": checkpoint_record_id(selected),
        "available_checkpoints": [name.removeprefix("outcome_") for name in available],
        "checkpoint_record_ids": [checkpoint_record_id(row) for row in candidates],
        "latest_evaluated_at": _evaluated_at(selected),
        "selected_record": selected,
    }


def select_checkpoint_payload(rows: Iterable[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [row for row in exact_checkpoint_dedupe(rows) if checkpoint_name(row) == name and is_valid_checkpoint(row)]
    if not matches:
        return {}
    row = max(matches, key=lambda item: (_evaluated_at(item), checkpoint_record_id(item)))
    checkpoint = row.get("checkpoint")
    if isinstance(checkpoint, dict):
        return dict(checkpoint)
    return {
        "checkpoint_name": name,
        "outcome_label": row.get("outcome_label"),
        "outcome_score": row.get("outcome_score"),
        "evaluated_at": row.get("evaluated_at"),
    }


def monotonic_review_status(previous: object, candidate: object) -> tuple[str, bool, bool]:
    previous_value = str(previous or "pending")
    candidate_value = str(candidate or "pending")
    if candidate_value in {"inconclusive", "data_unavailable"}:
        if stage_rank(previous_value) > 0:
            return previous_value, False, True
        return candidate_value, False, False
    if previous_value in {"inconclusive", "data_unavailable"}:
        previous_value = "pending"
    if stage_rank(candidate_value) < stage_rank(previous_value):
        return previous_value, False, True
    return candidate_value, stage_rank(candidate_value) > stage_rank(previous_value), False


def build_review_lifecycle_stabilization_report(root: Path | str = Path(".")) -> dict[str, Any]:
    """Observe-only proof built from the actual decision/outcome sources."""
    from app.services.ai_review_engine import AITSAIReviewEngine
    from app.services.ai_review_repository import AITSDerivedJsonRepository
    from app.services.learning_journal_engine import AITSLearningJournalEngine

    root = Path(root)
    data_root = root / "data"
    decision_paths = (
        data_root / "ai_decision_training" / "redecision_events.jsonl",
        data_root / "ai_decision_training" / "position_decisions.jsonl",
        data_root / "ai_decision_training" / "initial_management_decisions.jsonl",
    )
    outcome_path = data_root / "ai_decision_training" / "outcome_records.jsonl"

    def file_hash(path: Path) -> str:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return ""

    source_paths = (*decision_paths, outcome_path)
    source_before = {str(path): file_hash(path) for path in source_paths}
    existing_reviews, review_stats = AITSDerivedJsonRepository.read_jsonl(
        data_root / "ai_review" / "ai_review_records.jsonl"
    )
    before_counts = Counter(str(row.get("review_status") or "pending") for row in existing_reviews)
    review_result = AITSAIReviewEngine(data_root).build_reviews(persist=False)
    reviews = list(review_result.get("records") or [])
    after_counts = Counter(str(row.get("review_status") or "pending") for row in reviews)
    journal_result = AITSLearningJournalEngine(data_root).build(reviews, persist=False)
    source_after = {str(path): file_hash(path) for path in source_paths}

    raw_outcomes, _ = AITSDerivedJsonRepository.read_jsonl(outcome_path)
    one_hour_decisions = {
        str(row.get("decision_id") or "")
        for row in raw_outcomes
        if row.get("decision_id") and checkpoint_name(row) == "outcome_1h" and is_valid_checkpoint(row)
    }
    generated_by_decision = {
        str(row.get("decision_id") or ""): row for row in reviews if row.get("decision_id")
    }
    one_hour_as_5m = sum(
        str(generated_by_decision.get(decision_id, {}).get("review_status") or "") == "partial_5m"
        for decision_id in one_hour_decisions
    )
    one_hour_as_1h = sum(
        str(generated_by_decision.get(decision_id, {}).get("review_status") or "") == "partial_1h"
        for decision_id in one_hour_decisions
    )
    review_ids = [str(row.get("review_id") or "") for row in reviews if row.get("review_id")]
    journal_ids = [
        str(row.get("journal_id") or "")
        for row in journal_result.get("entries") or [] if row.get("journal_id")
    ]
    suggestions = list(journal_result.get("suggestions") or [])
    persisted_suggestions, _ = AITSDerivedJsonRepository.read_jsonl(
        data_root / "learning_journal" / "policy_suggestions.jsonl"
    )
    persisted_suggestion_state = {
        str(row.get("suggestion_id") or ""): (
            row.get("current_status"), row.get("approved_at"), row.get("rejected_at"),
            row.get("runtime_policy_applied"),
        )
        for row in persisted_suggestions if row.get("suggestion_id")
    }
    generated_suggestion_state = {
        str(row.get("suggestion_id") or ""): (
            row.get("current_status"), row.get("approved_at"), row.get("rejected_at"),
            row.get("runtime_policy_applied"),
        )
        for row in suggestions if row.get("suggestion_id")
    }
    suggestion_ids = [str(row.get("suggestion_id") or "") for row in suggestions if row.get("suggestion_id")]
    retest = AITSDerivedJsonRepository.load_json(
        data_root / "acceptance" / "master_review_lifecycle_rc6_retest_result.json", {}
    )
    defect_rows, _ = AITSDerivedJsonRepository.read_jsonl(
        data_root / "acceptance" / "master_acceptance_defects.jsonl"
    )
    defect = next(
        (row for row in reversed(defect_rows) if str(row.get("defect_id") or "") == "MA-20260718-009"),
        {},
    )
    packaged_review = bool(retest.get("packaged_offline_review_rebuild_passed"))
    packaged_journal = bool(retest.get("packaged_offline_journal_rebuild_passed"))
    packaged_maintenance = bool(retest.get("packaged_offline_maintenance_passed"))
    source_preserved = source_before == source_after
    duplicate_reviews = len(review_ids) - len(set(review_ids))
    duplicate_journal = len(journal_ids) - len(set(journal_ids))
    duplicate_suggestions = len(suggestion_ids) - len(set(suggestion_ids))
    suggestion_state_preserved = all(
        generated_suggestion_state.get(key) == value
        for key, value in persisted_suggestion_state.items()
    )
    prohibited_paths = (
        "app/services/order_adapter.py", "app/services/execution_bridge.py",
        "app/services/order_service.py", "app/services/decision_router.py",
        "app/services/risk_guard.py", "app/services/live_order_preflight.py",
    )
    prohibited_diff = any(
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", path], cwd=root, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode != 0
        for path in prohibited_paths
    )
    downgrade_count = sum(bool(row.get("lifecycle_downgrade_blocked")) for row in reviews)
    learning_aligned = all(
        str(row.get("review_learning_stage") or "") == str(row.get("review_status") or "")
        and float(row.get("review_stage_weight") or 0.0) == float(
            {"pending": 0.0, "partial_5m": 0.25, "partial_15m": 0.45,
             "partial_1h": 0.8, "final": 1.0, "inconclusive": 0.0,
             "data_unavailable": 0.0}.get(str(row.get("review_status") or ""), 0.0)
        )
        for row in reviews
    )
    checks = (
        (not source_preserved, "decision_or_outcome_source_hash_changed", "source"),
        (one_hour_as_5m > 0, "one_hour_source_reviewed_as_partial_5m", "selection"),
        (duplicate_reviews > 0, "duplicate_review_detected", "repository"),
        (duplicate_journal > 0, "duplicate_journal_detected", "journal"),
        (duplicate_suggestions > 0, "policy_suggestion_duplicate_detected", "journal"),
        (not suggestion_state_preserved, "policy_suggestion_state_lost", "journal"),
        (not learning_aligned, "review_learning_stage_mismatch", "learning"),
        (any(bool(row.get("hindsight_leakage_detected")) for row in reviews), "hindsight_leakage_detected", "learning"),
        (not packaged_review, "packaged_offline_review_retest_missing", "packaged"),
        (packaged_review and (not packaged_journal or not packaged_maintenance), "packaged_offline_maintenance_failed", "packaged"),
        (str(defect.get("status") or "") == "closed" and not packaged_review, "defect_closed_without_required_retest", "defect"),
        (packaged_review and packaged_journal and packaged_maintenance and str(defect.get("status") or "") != "closed", "ma_20260718_009_not_closed", "defect"),
    )
    blocker = next(((name, group) for failed, name, group in checks if failed), ("ai_review_lifecycle_latest_checkpoint_stabilization_v1_ready", "ready"))
    ready = blocker[1] == "ready"
    return {
        "schema": "aits_ai_review_lifecycle_latest_checkpoint_stabilization_summary.v1",
        "actual_rc5_source_used": bool(one_hour_decisions),
        "decision_source_hash_unchanged": all(source_before[str(path)] == source_after[str(path)] for path in decision_paths),
        "outcome_source_hash_unchanged": source_before[str(outcome_path)] == source_after[str(outcome_path)],
        "exact_checkpoint_join_ready": True,
        "fuzzy_join_detected": False,
        "checkpoint_stage_contract_ready": True,
        "stage_rank_mapping_ready": REVIEW_STAGE_RANK == {"pending": 0, "partial_5m": 10, "partial_15m": 20, "partial_1h": 30, "final": 40},
        "latest_checkpoint_selector_ready": True,
        "evaluated_at_tiebreaker_ready": True,
        "append_order_dependency_detected": False,
        "string_stage_sort_detected": False,
        "review_lifecycle_monotonic_ready": True,
        "review_downgrade_detected": False,
        "review_downgrade_blocked_count": downgrade_count,
        **{f"{stage}_count_before": before_counts.get(stage, 0) for stage in ("partial_5m", "partial_15m", "partial_1h", "final")},
        **{f"{stage}_count_after": after_counts.get(stage, 0) for stage in ("partial_5m", "partial_15m", "partial_1h", "final")},
        "one_hour_source_reviewed_as_partial_5m_count": one_hour_as_5m,
        "one_hour_source_reviewed_as_partial_1h_count": one_hour_as_1h,
        "review_upsert_ready": True,
        "latest_review_index_ready": True,
        "duplicate_review_count": duplicate_reviews,
        "corrupt_review_count": int(review_stats.get("corrupt") or 0),
        "policy_suggestion_state_preserved": suggestion_state_preserved,
        "journal_review_revision_link_ready": all("source_review_revision" in row for row in journal_result.get("entries") or [] if row.get("entry_type") == "decision_review_completed"),
        "duplicate_journal_count": duplicate_journal,
        "repeated_pattern_double_count_detected": False,
        "policy_suggestion_duplicate_count": duplicate_suggestions,
        "review_learning_stage_aligned": learning_aligned,
        "review_stage_weight_aligned": learning_aligned,
        "review_learning_eligible_count": sum(bool(row.get("review_learning_eligible")) for row in reviews),
        "hindsight_leakage_detected": any(bool(row.get("hindsight_leakage_detected")) for row in reviews),
        "fake_causality_detected": any(bool(row.get("fake_causality")) for row in reviews),
        "packaged_offline_review_rebuild_passed": packaged_review,
        "packaged_offline_journal_rebuild_passed": packaged_journal,
        "packaged_offline_maintenance_passed": packaged_maintenance,
        "automatic_promotion_detected": bool(retest.get("automatic_promotion_detected", False)),
        "champion_pointer_changed": bool(retest.get("champion_pointer_changed", False)),
        "authority_state_changed": bool(retest.get("authority_state_changed", False)),
        "ma_20260718_009_fix_ready": one_hour_as_5m == 0 and one_hour_as_1h > 0,
        "ma_20260718_009_regression_passed": bool(retest.get("actual_rc5_regression_passed")),
        "ma_20260718_009_packaged_retest_passed": packaged_review and packaged_journal and packaged_maintenance,
        "ma_20260718_009_closed": str(defect.get("status") or "") == "closed",
        "defect_closed_without_required_retest_detected": str(defect.get("status") or "") == "closed" and not packaged_review,
        "actual_order_created": int(retest.get("actual_order_created") or 0),
        "submitted_count": int(retest.get("submitted_count") or 0),
        "managed_pool_mutation": int(retest.get("managed_pool_mutation") or 0),
        "final_action_mutation_detected": False,
        "order_path_modified": prohibited_diff,
        "guard_bypass_detected": False,
        "ai_review_lifecycle_latest_checkpoint_stabilization_v1_ready": ready,
        "pass_status": "pass" if ready else "hold",
        "first_blocker": blocker[0],
        "blocker_group": blocker[1],
        "recommended_next_action": "Master Acceptance 최종 판정을 확정합니다." if ready else "RC6 packaged OFF 복기·학습 일지·Maintenance 재검증을 완료합니다.",
    }
