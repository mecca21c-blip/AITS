from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Any

from app.services.ai_review_repository import (
    AITSDerivedJsonRepository,
    AITSLearningJournalRepository,
)
from app.services.aits_data_source_resolver import AITSDataSourceResolver


MIN_PATTERN_SAMPLES = 3

FAILURE_PATTERN_TYPES = {
    "unnecessary_wait": "반복 대기 편향",
    "missed_opportunity": "반복 기회 상실",
    "confidence_overestimated": "높은 확신의 반복 과대평가",
    "teacher_disagreement": "교사 AI 판단 불일치 증가",
    "stale_data": "오래된 데이터 관련 반복 문제",
    "insufficient_data": "핵심 데이터 부족 반복",
    "order_not_submitted": "주문 요청과 제출 기록 불일치",
    "trend_reversed": "판단 이후 추세 반전 반복",
    "intent_expired_without_resolution": "재확인 시점이 반복적으로 만료됨",
    "intent_invalidation_repeated": "관찰 계획 무효화 반복",
    "effective_policy_conflict": "운용 정책 충돌 반복",
}
SUCCESS_PATTERN_TYPES = {
    "good_wait": "대기 판단 성공 반복",
    "avoided_loss": "손실 회피 반복",
    "evidence_aligned": "근거가 기록된 판단 반복",
    "execution_clean": "안정적인 주문 처리 반복",
}

SUGGESTION_TEMPLATES = {
    "confidence_overestimated": (
        "데이터 부족 구간의 확신 상한 검증",
        "핵심 데이터가 부족한 상황에서 높은 확신이 반복됐습니다. 확신 상한을 낮추는 검증을 제안합니다.",
        "confidence_policy",
        "과도한 확신 감소 가능",
        "확신을 지나치게 낮추면 외부 AI 확인이 늘어날 수 있습니다.",
    ),
    "unnecessary_wait": (
        "반복 대기 판단의 교사 AI 확인 확대 검증",
        "대기 중 상승 기회를 놓친 사례가 반복됐습니다. 비대기 판단의 교사 AI 확인 비율을 높이는 검증을 제안합니다.",
        "teacher_confirmation_policy",
        "불필요한 대기 감소 가능",
        "교사 AI 호출 비용이 늘어날 수 있습니다.",
    ),
    "missed_opportunity": (
        "기회 상실 구간 재판단 시간 검증",
        "상승 기회를 놓친 사례가 반복됐습니다. 해당 task의 재판단 시간을 짧게 하는 검증을 제안합니다.",
        "eta_redecision_policy",
        "기회 변화 확인 속도 개선 가능",
        "재판단 빈도와 처리 비용이 늘어날 수 있습니다.",
    ),
    "stale_data": (
        "오래된 데이터 사용 제한 검증",
        "오래된 데이터와 관련된 개선 필요 판단이 반복됐습니다. 판단 전 데이터 신선도 확인 강화를 제안합니다.",
        "data_freshness_policy",
        "오래된 근거 사용 감소 가능",
        "시장 데이터 지연 시 판단 보류가 늘어날 수 있습니다.",
    ),
    "teacher_disagreement": (
        "교사 AI 불일치 task 재학습 검증",
        "특정 판단에서 교사 AI와 불일치가 반복됐습니다. 해당 task 재학습과 외부 확인 강화를 제안합니다.",
        "teacher_sync_policy",
        "교사 판단 일치도 개선 가능",
        "재학습 전까지 외부 AI 의존도가 높아질 수 있습니다.",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


class AITSLearningJournalEngine:
    JOURNAL_SCHEMA = "aits_ai_learning_journal_entry.v1"
    POLICY_SCHEMA = "aits_ai_policy_suggestion.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.data_source_resolver = AITSDataSourceResolver(self.data_root)
        self.repository = AITSLearningJournalRepository(self.data_root)
        self.suggestion_repository = AITSDerivedJsonRepository(
            self.repository.suggestions_path,
            id_field="suggestion_id",
            schema=self.POLICY_SCHEMA,
        )

    @staticmethod
    def detect_patterns(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for review in reviews:
            for code in review.get("success_reasons") or []:
                if code in SUCCESS_PATTERN_TYPES:
                    evidence[("success", code)].append(review)
            for code in review.get("failure_reasons") or []:
                if code in FAILURE_PATTERN_TYPES:
                    evidence[("failure", code)].append(review)
            intent_status = str(review.get("intent_status") or "")
            if intent_status == "expired":
                evidence[("failure", "intent_expired_without_resolution")].append(review)
            elif intent_status == "invalidated":
                evidence[("failure", "intent_invalidation_repeated")].append(review)
            if "effective_policy_conflict" in (review.get("review_limitations") or []):
                evidence[("failure", "effective_policy_conflict")].append(review)
        patterns = []
        for (kind, code), rows in evidence.items():
            if len(rows) < MIN_PATTERN_SAMPLES:
                continue
            dates = [str(row.get("updated_at") or row.get("created_at") or "") for row in rows]
            tasks = sorted({str(row.get("task") or "") for row in rows if row.get("task")})
            actions = sorted({str(row.get("final_action") or "") for row in rows if row.get("final_action")})
            patterns.append({
                "schema": "aits_ai_repeated_pattern.v1",
                "pattern_id": _id("pattern", kind, code),
                "pattern_type": code,
                "pattern_kind": kind,
                "title_ko": (SUCCESS_PATTERN_TYPES if kind == "success" else FAILURE_PATTERN_TYPES)[code],
                "count": len(rows),
                "minimum_sample_count": MIN_PATTERN_SAMPLES,
                "first_seen": min(dates) if dates else "",
                "last_seen": max(dates) if dates else "",
                "affected_tasks": tasks,
                "affected_actions": actions,
                "severity": "높음" if kind == "failure" and len(rows) >= 10 else "관찰",
                "confidence": min(1.0, len(rows) / 10.0),
                "evidence_review_ids": [row.get("review_id") for row in rows],
                "evidence_decision_ids": [row.get("decision_id") for row in rows],
                "recommended_response": "정책 검증 검토" if kind == "failure" else "현재 근거 유지 검토",
            })
        return sorted(patterns, key=lambda row: (row["pattern_kind"], -row["count"], row["pattern_type"]))

    @staticmethod
    def build_policy_suggestions(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        suggestions = []
        now = _now()
        for pattern in patterns:
            code = str(pattern.get("pattern_type") or "")
            template = SUGGESTION_TEMPLATES.get(code)
            if not template or int(pattern.get("count") or 0) < MIN_PATTERN_SAMPLES:
                continue
            title, description, policy, effect, risk = template
            suggestions.append({
                "schema": "aits_ai_policy_suggestion.v1",
                "suggestion_id": _id("suggestion", pattern.get("pattern_id"), policy),
                "created_at": now,
                "title_ko": title,
                "description_ko": description,
                "affected_policy": policy,
                "affected_tasks": pattern.get("affected_tasks") or [],
                "reason_codes": [code],
                "evidence_count": int(pattern.get("count") or 0),
                "supporting_review_ids": pattern.get("evidence_review_ids") or [],
                "expected_effect_ko": effect,
                "risk_ko": risk,
                "current_status": "awaiting_review",
                "requires_user_approval": True,
                "approved_at": None,
                "rejected_at": None,
                "applied_at": None,
                "validation_required": True,
                "runtime_policy_applied": False,
            })
        return suggestions

    def review_policy_suggestion(self, suggestion_id: str, action: str) -> dict[str, Any]:
        rows, stats = AITSDerivedJsonRepository.read_jsonl(self.repository.suggestions_path)
        target = next((row for row in rows if str(row.get("suggestion_id") or "") == str(suggestion_id)), None)
        if not target:
            return {"updated": False, "blocker": "suggestion_not_found"}
        now = _now()
        if action == "approve":
            target["current_status"] = "approved_for_validation"
            target["approved_at"] = now
        elif action == "reject":
            target["current_status"] = "rejected"
            target["rejected_at"] = now
        elif action == "hold":
            target["current_status"] = "awaiting_review"
        else:
            return {"updated": False, "blocker": "unsupported_review_action"}
        target["runtime_policy_applied"] = False
        target["applied_at"] = None
        self.suggestion_repository.write_records(rows)
        AITSDerivedJsonRepository.atomic_write_json(self.repository.suggestion_summary_path, {
            "schema": "aits_ai_policy_suggestion_summary.v1",
            "suggestion_count": len(rows),
            "runtime_policy_applied_count": sum(bool(row.get("runtime_policy_applied")) for row in rows),
            "suggestions": rows,
        })
        return {
            "updated": True,
            "current_status": target["current_status"],
            "runtime_policy_applied": False,
            "corrupt_source_count": stats["corrupt"],
        }

    def build(self, reviews: list[dict[str, Any]] | None = None, *, persist: bool = False) -> dict[str, Any]:
        if reviews is None:
            reviews, _ = self.data_source_resolver.read_records("ai_reviews")
        patterns = self.detect_patterns(reviews)
        suggestions = self.build_policy_suggestions(patterns)
        previous_suggestions, _ = AITSDerivedJsonRepository.read_jsonl(
            self.repository.suggestions_path
        )
        previous_by_id = {
            str(row.get("suggestion_id") or ""): row
            for row in previous_suggestions
            if row.get("suggestion_id")
        }
        for suggestion in suggestions:
            previous = previous_by_id.get(str(suggestion.get("suggestion_id") or ""), {})
            if not previous:
                continue
            for field in (
                "current_status", "approved_at", "rejected_at", "applied_at",
                "validation_required", "runtime_policy_applied",
            ):
                if field in previous:
                    suggestion[field] = previous[field]
        now = _now()
        authority_state = AITSDerivedJsonRepository.load_json(
            self.data_root / "local_engine" / "local_engine_authority_state.json", {}
        )
        authority_history, _ = AITSDerivedJsonRepository.read_jsonl(
            self.data_root / "local_engine" / "local_engine_authority_history.jsonl"
        )
        latest_training = AITSDerivedJsonRepository.load_json(
            self.data_root / "local_models" / "latest_training_attempt.json", {}
        )
        latest_calibration = AITSDerivedJsonRepository.load_json(
            self.data_root / "local_models" / "latest_confidence_calibration_attempt.json", {}
        )
        entries: list[dict[str, Any]] = []
        for review in reviews:
            if review.get("review_status") == "pending":
                continue
            entries.append({
                "schema": self.JOURNAL_SCHEMA,
                "journal_id": _id("journal", "review", review.get("review_id"), review.get("review_stage")),
                "entry_type": "decision_review_completed",
                "created_at": review.get("updated_at") or now,
                "period_start": review.get("created_at"),
                "period_end": review.get("updated_at"),
                "title_ko": f"{review.get('symbol') or review.get('scope') or '전체'} 판단 복기 완료",
                "summary_ko": review.get("review_summary_ko"),
                "evidence_count": 1,
                "decision_ids": [review.get("decision_id")],
                "affected_tasks": [review.get("task")] if review.get("task") else [],
                "affected_actions": [review.get("final_action")] if review.get("final_action") else [],
                "affected_symbols": [review.get("symbol")] if review.get("symbol") else [],
                "market_regime": None,
                "model_id": (review.get("local_engine_candidate") or {}).get("model_artifact_id"),
                "authority_level": authority_state.get("effective_global_level"),
                "health_status": authority_state.get("health_status"),
                "lesson_tags": review.get("repeated_pattern_tags") or [],
                "policy_suggestion_ids": review.get("policy_suggestion_ids") or [],
                "user_attention_required": review.get("decision_quality") in {"weak", "poor"},
                "source_digest": _id("digest", review.get("review_id"), review.get("decision_id")),
                "safe_for_learning": bool(review.get("safe_for_learning")),
            })
        for pattern in patterns:
            kind = str(pattern.get("pattern_kind") or "")
            entries.append({
                "schema": self.JOURNAL_SCHEMA,
                "journal_id": _id("journal", "pattern", pattern.get("pattern_id")),
                "entry_type": "repeated_success_pattern" if kind == "success" else "repeated_failure_pattern",
                "created_at": now,
                "period_start": pattern.get("first_seen"),
                "period_end": pattern.get("last_seen"),
                "title_ko": pattern.get("title_ko"),
                "summary_ko": f"근거가 있는 복기 {pattern.get('count', 0)}건에서 같은 패턴이 확인됐습니다.",
                "evidence_count": pattern.get("count"),
                "decision_ids": pattern.get("evidence_decision_ids") or [],
                "affected_tasks": pattern.get("affected_tasks") or [],
                "affected_actions": pattern.get("affected_actions") or [],
                "affected_symbols": [],
                "market_regime": None,
                "model_id": None,
                "authority_level": authority_state.get("effective_global_level"),
                "health_status": authority_state.get("health_status"),
                "lesson_tags": [pattern.get("pattern_type")],
                "policy_suggestion_ids": [],
                "user_attention_required": kind == "failure",
                "source_digest": _id("digest", pattern.get("pattern_id"), pattern.get("count")),
                "safe_for_learning": True,
            })
        event_types = {
            "level_initialized": "level_changed", "automatic_demotion": "level_changed",
            "user_demotion": "level_changed", "health_changed": "health_changed",
            "teacher_sync_requested": "teacher_sync_started",
            "challenger_evaluated": "challenger_evaluated",
            "champion_replaced": "champion_replaced", "rollback_completed": "rollback_completed",
            "promotion_candidate_created": "level2_promotion_candidate_created",
            "promotion_approved": "level_changed",
            "promotion_rejected": "level2_promotion_rejected",
            "authority_resumed": "health_changed",
        }
        for event in authority_history:
            event_type = event_types.get(str(event.get("event") or ""))
            if not event_type:
                continue
            entries.append({
                "schema": self.JOURNAL_SCHEMA,
                "journal_id": _id("journal", "authority", event.get("timestamp"), event.get("event")),
                "entry_type": event_type,
                "created_at": event.get("timestamp") or now,
                "period_start": event.get("timestamp"),
                "period_end": event.get("timestamp"),
                "title_ko": "LOCAL_ENGINE 운영 상태 변경",
                "summary_ko": "기존 Authority Manager 이력에서 확인된 변경입니다.",
                "evidence_count": 1,
                "decision_ids": [],
                "affected_tasks": [],
                "affected_actions": [],
                "affected_symbols": [],
                "market_regime": None,
                "model_id": event.get("model_id"),
                "authority_level": event.get("global_level_after"),
                "health_status": authority_state.get("health_status"),
                "lesson_tags": [event.get("event")],
                "policy_suggestion_ids": [],
                "user_attention_required": event_type in {"level_changed", "health_changed"},
                "source_digest": _id("digest", event.get("timestamp"), event.get("event")),
                "safe_for_learning": True,
            })

        if latest_training.get("model_id") and latest_training.get("trained_at"):
            entries.append({
                "schema": self.JOURNAL_SCHEMA,
                "journal_id": _id(
                    "journal", "training", latest_training.get("model_id"),
                    latest_training.get("trained_at"),
                ),
                "entry_type": "model_training_completed",
                "created_at": latest_training.get("trained_at"),
                "period_start": latest_training.get("trained_at"),
                "period_end": latest_training.get("trained_at"),
                "title_ko": "LOCAL_ENGINE 새 모델 학습 완료",
                "summary_ko": (
                    f"실제 학습 데이터 {int(latest_training.get('source_record_count') or 0):,}건으로 "
                    "새 모델 학습을 완료했습니다. 모델 적용과 Level 변경은 별도 승인 절차를 따릅니다."
                ),
                "evidence_count": int(latest_training.get("source_record_count") or 0),
                "decision_ids": [],
                "affected_tasks": list(latest_training.get("supported_tasks") or []),
                "affected_actions": list(latest_training.get("supported_actions") or []),
                "affected_symbols": [],
                "market_regime": None,
                "model_id": latest_training.get("model_id"),
                "authority_level": authority_state.get("effective_global_level"),
                "health_status": authority_state.get("health_status"),
                "lesson_tags": ["model_training_completed"],
                "policy_suggestion_ids": [],
                "user_attention_required": False,
                "source_digest": _id(
                    "digest", latest_training.get("model_id"), latest_training.get("trained_at")
                ),
                "safe_for_learning": not bool(latest_training.get("blocker")),
            })

        if latest_calibration.get("calibrator_id"):
            accepted = latest_calibration.get("attempt_status") == "usable"
            entries.append({
                "schema": self.JOURNAL_SCHEMA,
                "journal_id": _id("journal", "confidence_calibration", latest_calibration.get("calibrator_id")),
                "entry_type": "confidence_calibration_completed",
                "created_at": latest_calibration.get("fitted_at") or now,
                "period_start": latest_calibration.get("fitted_at") or now,
                "period_end": latest_calibration.get("fitted_at") or now,
                "title_ko": "LOCAL_ENGINE 신뢰도 보정 평가 완료",
                "summary_ko": (
                    "최신 검증 구간에서 신뢰도 오차가 개선되어 보정 후보를 사용할 수 있습니다."
                    if accepted else
                    "최신 검증 구간에서 신뢰도 오차가 개선되지 않아 기존 모델 신뢰도 경로를 유지합니다."
                ),
                "evidence_count": int(latest_calibration.get("holdout_count") or 0),
                "decision_ids": [],
                "affected_tasks": list(latest_calibration.get("supported_tasks") or []),
                "affected_actions": [],
                "affected_symbols": [],
                "market_regime": None,
                "model_id": latest_calibration.get("source_model_id"),
                "authority_level": authority_state.get("effective_global_level"),
                "health_status": authority_state.get("health_status"),
                "lesson_tags": ["confidence_calibration", latest_calibration.get("attempt_status")],
                "policy_suggestion_ids": [],
                "user_attention_required": not accepted,
                "source_digest": _id("digest", latest_calibration.get("calibrator_id")),
                "safe_for_learning": True,
            })

        status_counts = Counter(review.get("review_status") for review in reviews)
        decision_quality = Counter(review.get("decision_quality") for review in reviews)
        reason_counts = Counter(code for review in reviews for code in review.get("failure_reasons") or [])
        summary = {
            "schema": "aits_ai_learning_journal_summary.v1",
            "generated_at": now,
            "journal_entry_count": len(entries),
            "review_count": len(reviews),
            "review_status_counts": dict(status_counts),
            "decision_quality_counts": dict(decision_quality),
            "repeated_success_pattern_count": sum(row.get("pattern_kind") == "success" for row in patterns),
            "repeated_failure_pattern_count": sum(row.get("pattern_kind") == "failure" for row in patterns),
            "policy_suggestion_count": len(suggestions),
            "runtime_policy_applied_count": 0,
            "daily_summary": {
                "decision_reviews": len(reviews),
                "good_decisions": decision_quality.get("good", 0) + decision_quality.get("acceptable", 0),
                "improvement_needed": decision_quality.get("weak", 0) + decision_quality.get("poor", 0),
                "avoided_loss": sum("avoided_loss" in (row.get("success_reasons") or []) for row in reviews),
                "missed_opportunity": reason_counts.get("missed_opportunity", 0),
                "teacher_disagreement": reason_counts.get("teacher_disagreement", 0),
            },
            "weekly_summary": {
                "top_failure_patterns": [row.get("title_ko") for row in patterns if row.get("pattern_kind") == "failure"][:5],
                "next_learning_priorities": [row.get("title_ko") for row in suggestions][:5],
                "authority_level": authority_state.get("effective_global_level"),
                "health_status": authority_state.get("health_status"),
            },
            "monthly_summary": {
                "status": "structure_ready",
                "generated": False,
                "reason": "월간 표본이 충분할 때 명시적으로 생성합니다.",
            },
            "recent_entries": [
                {
                    key: row.get(key)
                    for key in (
                        "journal_id", "entry_type", "created_at", "title_ko",
                        "summary_ko", "evidence_count", "affected_tasks",
                        "affected_actions", "affected_symbols", "model_id",
                        "authority_level", "health_status", "user_attention_required",
                        "policy_suggestion_ids",
                    )
                }
                for row in entries[-100:]
            ],
            "recent_patterns": patterns[:50],
            "recent_suggestions": suggestions[:50],
            "policy_auto_apply_detected": False,
        }
        if persist:
            self.repository.write_records(entries)
            self.suggestion_repository.write_records(suggestions)
            AITSDerivedJsonRepository.atomic_write_json(self.repository.suggestion_summary_path, {
                "schema": "aits_ai_policy_suggestion_summary.v1",
                "suggestion_count": len(suggestions),
                "runtime_policy_applied_count": 0,
                "suggestions": suggestions,
            })
            AITSDerivedJsonRepository.atomic_write_json(self.repository.patterns_path, {
                "schema": "aits_ai_repeated_patterns.v1", "patterns": patterns,
                "minimum_sample_count": MIN_PATTERN_SAMPLES,
            })
            AITSDerivedJsonRepository.atomic_write_json(self.repository.summary_path, summary)
        return {
            "entries": entries, "patterns": patterns, "suggestions": suggestions,
            "summary": summary, "persisted": bool(persist),
        }
