from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ai_review_repository import AITSDerivedJsonRepository


STAGE_WEIGHTS = {
    "final": 1.0,
    "partial_1h": 0.8,
    "partial_15m": 0.45,
    "partial_5m": 0.25,
    "pending": 0.0,
    "inconclusive": 0.0,
    "data_unavailable": 0.0,
}

TASK_FEATURE_PREFIXES = {
    "position": ("position.", "market.", "indicators.", "portfolio.exposure", "sell_unit"),
    "portfolio": ("portfolio.", "market.", "candidates.", "managed_pool", "risk"),
    "buy": ("candidates.", "candidate.", "market.", "portfolio.", "risk"),
    "sell": ("position.", "market.", "indicators.", "portfolio.", "sell_unit"),
    "rotation": ("candidates.", "candidate.", "market.", "portfolio.", "risk"),
}


def canonical_review_task(task: object, action: object = "") -> str:
    value = str(task or "").lower()
    action_value = str(action or "").lower()
    if "portfolio" in value:
        return "portfolio"
    if "rotation" in value or action_value == "rotate":
        return "rotation"
    if "buy" in value or action_value in {"buy", "add"}:
        return "buy"
    if "sell" in value or action_value in {"sell", "reduce", "take_profit", "stop_loss"}:
        return "sell"
    return "position"


def relevant_missing_features(task: object, action: object, missing: list[object]) -> tuple[list[str], list[str]]:
    kind = canonical_review_task(task, action)
    prefixes = TASK_FEATURE_PREFIXES[kind]
    relevant: list[str] = []
    ignored: list[str] = []
    optional_position = {"position.holding_age", "position.source_type", "position.dust"}
    for raw in missing:
        feature = str(raw or "")
        if kind == "position" and (feature in optional_position or feature == "candidates.opportunity_gap"):
            ignored.append(feature)
        elif any(feature.startswith(prefix) for prefix in prefixes):
            relevant.append(feature)
        else:
            ignored.append(feature)
    return sorted(set(relevant)), sorted(set(ignored))


class AITSLocalEngineReviewLearningBridge:
    SCHEMA = "aits_local_engine_review_learning_bridge.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.priority_path = self.data_root / "local_engine" / "local_engine_review_learning_priority.json"

    @staticmethod
    def evaluate_review(review: dict[str, Any]) -> dict[str, Any]:
        stage = str(review.get("review_stage") or review.get("review_status") or "pending")
        stage_weight = float(STAGE_WEIGHTS.get(stage, 0.0))
        decision_available = str(review.get("decision_quality") or "") != "inconclusive"
        result_available = str(review.get("result_quality") or "") != "unavailable"
        factual = bool(review.get("factual_evidence_only")) and not bool(
            review.get("hindsight_leakage_detected") or review.get("fake_causality")
        )
        reason_present = bool(str(review.get("reason_ko") or "").strip())
        evidence_present = bool(review.get("evidence"))
        identity_present = bool(review.get("decision_id"))
        completeness = sum((identity_present, reason_present, evidence_present, result_available)) / 4.0
        factual_score = round(
            min(1.0, (0.45 if factual else 0.0) + (0.2 if reason_present else 0.0)
                + (0.2 if evidence_present else 0.0) + (0.15 if identity_present else 0.0)),
            4,
        )
        missing = list(review.get("blockers") or [])
        relevant, ignored = relevant_missing_features(review.get("task"), review.get("final_action"), missing)
        rubric_overreach = bool(
            str(review.get("decision_quality") or "") == "poor"
            and len(missing) >= 3
            and len(relevant) < 3
            and "evidence_conflicted" not in (review.get("failure_reasons") or [])
        )
        core_ready = factual and decision_available and result_available and completeness >= 0.5
        target_eligibility = {
            "action": core_ready and stage in {"final", "partial_1h"},
            "confidence": core_ready and stage in {"final", "partial_1h"},
            "risk": factual and identity_present and stage_weight > 0,
            "abstention": factual and identity_present,
            "escalation": factual and identity_present,
            "eta": core_ready and stage in {"final", "partial_1h", "partial_15m"},
            "invalidation": core_ready and stage in {"final", "partial_1h"},
            "teacher_sync_priority": factual and identity_present,
            "task_capability_evidence": core_ready and stage in {"final", "partial_1h"},
        }
        exclusions: list[str] = []
        if stage_weight <= 0:
            exclusions.append("review_stage_not_learning_ready")
        if not factual:
            exclusions.append("factual_evidence_contract_failed")
        if not decision_available:
            exclusions.append("decision_quality_unavailable")
        if not result_available:
            exclusions.append("result_quality_unavailable")
        if completeness < 0.5:
            exclusions.append("source_completeness_insufficient")
        reliability_score = round(stage_weight * factual_score * completeness, 4)
        if reliability_score >= 0.7:
            grade = "A"
        elif reliability_score >= 0.45:
            grade = "B"
        elif reliability_score > 0:
            grade = "C"
        else:
            grade = "D"
        learning_eligible = bool(target_eligibility["action"] or target_eligibility["task_capability_evidence"])
        return {
            "review_learning_eligible": learning_eligible,
            "review_reliability_grade": grade,
            "review_learning_weight": reliability_score,
            "review_stage_weight": stage_weight,
            "factual_evidence_score": factual_score,
            "source_completeness": round(completeness, 4),
            "decision_quality_available": decision_available,
            "result_quality_available": result_available,
            "review_target_eligibility": target_eligibility,
            "review_exclusion_reasons": exclusions,
            "task_specific_relevant_missing_features": relevant,
            "task_specific_ignored_missing_features": ignored,
            "rubric_overreach_detected": rubric_overreach,
            "decision_result_matrix_used": bool(review.get("decision_result_matrix")),
            "weak_or_poor_used_as_action_label": False,
        }

    def build(self, reviews: list[dict[str, Any]], *, persist: bool = False) -> dict[str, Any]:
        enriched: list[dict[str, Any]] = []
        priority_tasks: Counter[str] = Counter()
        priority_actions: Counter[str] = Counter()
        weak_reasons: Counter[str] = Counter()
        poor_reasons: Counter[str] = Counter()
        review_by_task: dict[str, Counter[str]] = defaultdict(Counter)
        for source in reviews:
            row = dict(source)
            gate = self.evaluate_review(row)
            row.update(gate)
            enriched.append(row)
            task = canonical_review_task(row.get("task"), row.get("final_action"))
            review_by_task[task][str(row.get("review_reliability_grade") or "D")] += 1
            if row.get("decision_quality") in {"weak", "poor"}:
                for reason in row.get("failure_reasons") or []:
                    (poor_reasons if row.get("decision_quality") == "poor" else weak_reasons)[str(reason)] += 1
                    priority_tasks[task] += 1
                action = str(row.get("final_action") or "")
                if action:
                    priority_actions[action] += 1

        patterns_doc = AITSDerivedJsonRepository.load_json(
            self.data_root / "learning_journal" / "repeated_patterns.json", {}
        )
        suggestions_doc = AITSDerivedJsonRepository.load_json(
            self.data_root / "learning_journal" / "policy_suggestion_summary.json", {}
        )
        patterns = list(patterns_doc.get("patterns") or [])
        suggestions = list(suggestions_doc.get("suggestions") or [])
        for pattern in patterns:
            if pattern.get("pattern_kind") != "failure":
                continue
            for task in pattern.get("affected_tasks") or []:
                priority_tasks[canonical_review_task(task)] += int(pattern.get("count") or 1)
            for action in pattern.get("affected_actions") or []:
                priority_actions[str(action)] += int(pattern.get("count") or 1)

        eligible_count = sum(bool(row.get("review_learning_eligible")) for row in enriched)
        overreach_count = sum(bool(row.get("rubric_overreach_detected")) for row in enriched)
        priority = {
            "schema": self.SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_count": len(enriched),
            "review_learning_eligible_count": eligible_count,
            "review_learning_excluded_count": len(enriched) - eligible_count,
            "priority_tasks": [key for key, _ in priority_tasks.most_common()],
            "priority_actions": [key for key, _ in priority_actions.most_common()],
            "priority_market_regimes": [],
            "teacher_sampling_priority": dict(priority_actions),
            "recent_data_weight_adjustment": 0.0,
            "review_required_before_training": True,
            "challenger_evaluation_focus": {
                "tasks": [key for key, _ in priority_tasks.most_common(5)],
                "actions": [key for key, _ in priority_actions.most_common(5)],
            },
            "retraining_reason_codes": sorted(set(
                list(weak_reasons.keys()) + list(poor_reasons.keys())
            )),
            "weak_reason_counts": dict(weak_reasons),
            "poor_reason_counts": dict(poor_reasons),
            "review_quality_by_task": {key: dict(value) for key, value in review_by_task.items()},
            "rubric_overreach_detected": bool(overreach_count),
            "rubric_overreach_count": overreach_count,
            "source_quality_issue_count": sum(
                "source_completeness_insufficient" in (row.get("review_exclusion_reasons") or [])
                for row in enriched
            ),
            "actual_decision_quality_issue_count": sum(
                row.get("decision_quality") in {"weak", "poor"}
                and not row.get("rubric_overreach_detected") for row in enriched
            ),
            "repeated_failure_pattern_count": sum(
                pattern.get("pattern_kind") == "failure" for pattern in patterns
            ),
            "policy_suggestion_count": len(suggestions),
            "policy_suggestion_auto_apply_detected": any(
                bool(row.get("runtime_policy_applied")) for row in suggestions
            ),
            "journal_patterns_used_as_action_labels": False,
            "source_records_preserved": True,
        }
        if persist:
            AITSDerivedJsonRepository.atomic_write_json(self.priority_path, priority)
        return {"summary": priority, "records": enriched}

    def inspect_priority(self) -> dict[str, Any]:
        return AITSDerivedJsonRepository.load_json(self.priority_path, {})
