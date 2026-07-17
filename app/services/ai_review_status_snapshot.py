from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
from typing import Any

from app.services.ai_review_repository import (
    AITSAIReviewRepository,
    AITSDerivedJsonRepository,
    AITSLearningJournalRepository,
)


QUALITY_NAMES = {
    "good": "좋음", "acceptable": "타당", "weak": "개선 필요",
    "poor": "취약", "inconclusive": "판단 불가",
}
RESULT_NAMES = {
    "positive": "긍정", "neutral": "중립", "negative": "부정",
    "unavailable": "확인 불가",
}
STATUS_NAMES = {
    "pending": "결과 대기", "partial_5m": "5분 결과 확인",
    "partial_15m": "15분 결과 확인", "partial_1h": "1시간 결과 확인",
    "final": "복기 완료", "inconclusive": "판단 불가",
    "data_unavailable": "결과 확인 불가",
}
ACTION_NAMES = {
    "wait": "대기", "hold": "보유", "buy": "매수", "add": "추가 매수",
    "sell": "매도", "reduce": "축소", "take_profit": "익절",
    "stop_loss": "손절", "rotate": "교체",
}
SUGGESTION_STATUS_NAMES = {
    "proposed": "제안됨", "awaiting_review": "검토 대기",
    "approved_for_validation": "검증 승인", "rejected": "거절",
    "validated": "검증 완료", "ready_to_apply": "적용 준비",
    "applied": "적용됨", "expired": "만료",
}


class AITSAIReviewStatusSnapshot:
    SCHEMA = "aits_ai_review_learning_journal_status_snapshot.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.review_repository = AITSAIReviewRepository(self.data_root)
        self.journal_repository = AITSLearningJournalRepository(self.data_root)

    @staticmethod
    def _file_status(path: Path, name: str, count: int, learning_use: bool) -> dict[str, Any]:
        try:
            stat = path.stat()
            return {
                "name": name,
                "available": True,
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                "record_count": count,
                "derived": True,
                "regeneratable": True,
                "learning_use": learning_use,
            }
        except OSError:
            return {
                "name": name, "available": False, "size_bytes": 0,
                "updated_at": None, "record_count": 0, "derived": True,
                "regeneratable": True, "learning_use": learning_use,
            }

    @staticmethod
    def _review_item(row: dict[str, Any]) -> dict[str, Any]:
        symbol = str(row.get("symbol") or row.get("scope") or "전체")
        action = str(row.get("final_action") or "")
        return {
            "review_id": row.get("review_id"),
            "created_at": row.get("created_at"),
            "symbol": symbol,
            "task": row.get("task"),
            "action": action,
            "action_text": ACTION_NAMES.get(action, "확인 필요"),
            "status": row.get("review_status"),
            "status_text": STATUS_NAMES.get(str(row.get("review_status") or ""), "확인 필요"),
            "decision_quality": row.get("decision_quality"),
            "decision_quality_text": QUALITY_NAMES.get(str(row.get("decision_quality") or ""), "확인 필요"),
            "result_quality": row.get("result_quality"),
            "result_quality_text": RESULT_NAMES.get(str(row.get("result_quality") or ""), "확인 필요"),
            "decision_summary_ko": row.get("decision_summary_ko"),
            "result_summary_ko": row.get("result_summary_ko"),
            "review_summary_ko": row.get("review_summary_ko"),
            "what_went_well_ko": row.get("what_went_well_ko"),
            "what_went_wrong_ko": row.get("what_went_wrong_ko"),
            "what_was_unknown_ko": row.get("what_was_unknown_ko"),
            "lesson_ko": row.get("lesson_ko"),
            "order_submitted": bool(row.get("order_submitted")),
            "review_limitations": row.get("review_limitations") or [],
            "copilot_decision": dict(row.get("copilot_decision") or {}),
            "copilot_consulted": bool(row.get("copilot_consulted")),
            "copilot_routing_used": bool(row.get("copilot_routing_used")),
            "copilot_routing_effect": row.get("copilot_routing_effect"),
            "task_capability_level": int(row.get("task_capability_level") or 0),
            "review_learning_eligible": bool(row.get("review_learning_eligible")),
            "review_reliability_grade": row.get("review_reliability_grade"),
        }

    def build(self, *, review_limit: int = 100) -> dict[str, Any]:
        review_summary = AITSDerivedJsonRepository.load_json(self.review_repository.summary_path, {})
        journal_summary = AITSDerivedJsonRepository.load_json(self.journal_repository.summary_path, {})
        patterns = AITSDerivedJsonRepository.load_json(self.journal_repository.patterns_path, {})
        suggestion_summary = AITSDerivedJsonRepository.load_json(
            self.journal_repository.suggestion_summary_path, {}
        )
        suggestions = list(suggestion_summary.get("suggestions") or [])
        reviews = list(review_summary.get("recent_reviews") or [])[-max(1, min(review_limit, 100)):]
        journal = list(journal_summary.get("recent_entries") or [])[-100:]
        status_counts = dict(review_summary.get("review_status_counts") or {})
        decision_counts = dict(review_summary.get("decision_quality_counts") or {})
        matrix_counts = dict(review_summary.get("decision_result_matrix_counts") or {})
        daily = dict(journal_summary.get("daily_summary") or {})
        from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
        from app.services.local_engine_level2_evaluator import AITSLocalEngineLevel2Evaluator
        authority_manager = AITSLocalEngineAuthorityManager(self.data_root / "local_engine")
        authority = authority_manager.inspect(persist_initial=False)
        level2 = AITSLocalEngineLevel2Evaluator(
            data_root=self.data_root,
            policy=authority_manager.policy.as_dict(),
        ).evaluate(authority)
        return {
            "schema": self.SCHEMA,
            "snapshot_ready": bool(review_summary or journal_summary),
            "review_summary_cards": {
                "복기 완료": status_counts.get("final", 0) + status_counts.get("partial_1h", 0),
                "결과 대기": status_counts.get("pending", 0),
                "좋은 판단": decision_counts.get("good", 0) + decision_counts.get("acceptable", 0),
                "개선 필요": decision_counts.get("weak", 0) + decision_counts.get("poor", 0),
                "손실 회피": daily.get("avoided_loss", 0),
                "기회 상실": daily.get("missed_opportunity", 0),
            },
            "reviews": [self._review_item(row) for row in reversed(reviews)],
            "journal_entries": list(reversed(journal)),
            "patterns": list(patterns.get("patterns") or [])[:50],
            "policy_suggestions": [
                {
                    **row,
                    "status_text": SUGGESTION_STATUS_NAMES.get(str(row.get("current_status") or ""), "확인 필요"),
                }
                for row in suggestions
            ],
            "review_record_count": int(review_summary.get("review_records_count") or 0),
            "journal_entry_count": int(journal_summary.get("journal_entry_count") or 0),
            "repeated_success_pattern_count": int(journal_summary.get("repeated_success_pattern_count") or 0),
            "repeated_failure_pattern_count": int(journal_summary.get("repeated_failure_pattern_count") or 0),
            "policy_suggestion_count": len(suggestions),
            "suggestion_corrupt_count": 0,
            "daily_summary": daily,
            "weekly_summary": journal_summary.get("weekly_summary") or {},
            "monthly_summary": journal_summary.get("monthly_summary") or {"status": "structure_ready"},
            "level2_summary": {
                "eligible": bool(level2.get("global_level2_eligibility")),
                "eligible_tasks": list(level2.get("level2_eligible_tasks") or []),
                "ineligible_tasks": list(level2.get("level2_ineligible_tasks") or []),
                "blockers": list(level2.get("global_level2_blockers") or []),
                "promotion_candidate": level2.get("promotion_candidate"),
            },
            "data_files": [
                self._file_status(
                    self.review_repository.path, "AI 복기 기록",
                    int(review_summary.get("review_records_count") or 0), True,
                ),
                self._file_status(
                    self.journal_repository.path, "학습 일지",
                    int(journal_summary.get("journal_entry_count") or 0), True,
                ),
                self._file_status(
                    self.journal_repository.patterns_path, "반복 패턴",
                    len(patterns.get("patterns") or []), True,
                ),
                self._file_status(
                    self.journal_repository.suggestions_path, "정책 개선 제안",
                    len(suggestions), False,
                ),
            ],
            "raw_jsonl_scanned_on_ui_thread": False,
            "summary_cache_used": True,
            "pagination_ready": self.review_repository.index_path.exists(),
            "lazy_detail_ready": self.review_repository.index_path.exists(),
            "low_resource_mode_compatible": True,
        }

    def review_detail(self, review_id: str) -> dict[str, Any]:
        return self._review_item(self.review_repository.get(review_id))

    def backup_derived(self) -> dict[str, Any]:
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        backup_root = self.data_root / "ai_review" / "backups" / stamp
        sources = (
            self.review_repository.path,
            self.review_repository.summary_path,
            self.review_repository.state_path,
            self.journal_repository.path,
            self.journal_repository.summary_path,
            self.journal_repository.patterns_path,
            self.journal_repository.suggestions_path,
            self.journal_repository.suggestion_summary_path,
        )
        copied: list[str] = []
        backup_root.mkdir(parents=True, exist_ok=False)
        for source in sources:
            if not source.exists():
                continue
            shutil.copy2(source, backup_root / source.name)
            copied.append(source.name)
        return {
            "completed": bool(copied),
            "backup_path": str(backup_root),
            "copied_files": copied,
            "source_records_modified": False,
        }
