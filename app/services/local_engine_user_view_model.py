from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


LEVEL_ROLES = {
    0: "외부전용",
    1: "학습자",
    2: "보조판단",
    3: "제한독립",
    4: "주판단",
    5: "내부운용",
}

BLOCKER_TEXT = {
    "user_approval_required_above_candidate": "현재 Level 이상의 판단 권한은 사용자 승인이 필요합니다.",
    "candidate_only_evidence": "실제 결과를 더 확인해 판단 기능을 검증해야 합니다.",
    "non_wait_recall_insufficient": "매도·익절 등 비대기 판단의 실제 결과가 더 필요합니다.",
    "portfolio_teacher_labels_missing": "포트폴리오 교사 판단과 실제 결과 표본이 더 필요합니다.",
    "rotation_teacher_labels_missing": "로테이션 교사 판단과 실제 결과 표본이 필요합니다.",
    "buy_add_teacher_labels_missing": "매수·추가 교사 판단과 실제 결과 표본이 필요합니다.",
    "insufficient_task_evidence": "이 판단 기능을 검증할 실제 데이터가 부족합니다.",
    "critical_model_feature_missing": "판단에 필요한 시장 정보가 아직 충분하지 않습니다.",
}

FILE_NAMES = {
    "local_engine_authority_state.json": "LOCAL 판단 권한 상태",
    "local_engine_authority_history.jsonl": "LOCAL 권한 변경 이력",
    "local_engine_capability_matrix.json": "기능별 학습 단계",
    "local_engine_health_state.json": "엔진 전체 상태",
    "local_engine_continuous_learning_state.json": "모델 학습 진행 상태",
    "local_engine_teacher_sync_state.json": "교사 AI 학습 상태",
    "local_engine_candidate_observations.jsonl": "LOCAL 후보 판단 기록",
    "outcome_records.jsonl": "판단 결과 기록",
    "provider_comparison_outcomes.jsonl": "교사 AI 비교 기록",
    "curated_local_training_records.jsonl": "정리된 학습 데이터",
    "local_training_features.jsonl": "학습용 특징 데이터",
    "local_engine_teacher_distillation_records.jsonl": "교사 AI 학습 데이터",
    "registry.json": "LOCAL 모델 목록",
    "latest_model.json": "최근 모델 상태",
    "calibration_profile.json": "모델 신뢰도 보정",
    "latest_calibration_summary.json": "최근 신뢰도 보정 결과",
}

EVENT_NAMES = {
    "level_initialized": "LOCAL_ENGINE 학습 단계 확인",
    "capability_evaluated": "기능별 학습 상태 평가",
    "automatic_demotion": "안전을 위한 자동 단계 조정",
    "user_demotion": "사용자가 학습 단계를 낮춤",
    "teacher_sync_requested": "GPT/Gemini 최신 시장 학습 요청",
    "training_triggered": "새 모델 학습 시작",
    "challenger_trained": "새 모델 학습 완료",
    "challenger_evaluated": "새 모델 성능 평가 완료",
    "promotion_candidate_created": "Level 승격 검토 준비",
    "promotion_approved": "Level 승격 승인",
    "promotion_rejected": "이번 Level 승격 보류",
    "champion_replaced": "새 모델 적용",
    "rollback_triggered": "이전 모델 복구 시작",
    "rollback_completed": "이전 모델로 복구 완료",
    "health_changed": "엔진 전체 상태 변경",
    "authority_resumed": "LOCAL 판단 권한 재개",
}


def _local_time(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "기록 없음"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return "기록 확인 필요"


def _task_status(row: dict[str, Any]) -> str:
    health = str(row.get("health") or "")
    blocker = str(row.get("blocker") or "")
    level = int(row.get("level") or 0)
    if health in {"차단됨", "성능 저하"}:
        return "문제 발생"
    if level <= 0 and int(row.get("teacher_samples") or 0) <= 0:
        return "데이터 부족"
    if blocker == "non_wait_recall_insufficient":
        return "검증 중"
    if level >= 3:
        return "준비됨"
    return "학습 중"


def _maintenance_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    learning = dict(snapshot.get("learning") or {})
    comparison = dict(snapshot.get("model_comparison") or {})
    raw = str(learning.get("status") or "idle")
    if bool(snapshot.get("runtime_active")):
        return {
            "raw_state": raw,
            "title": "모델 갱신 · 실시간 감시 중",
            "detail": "실시간 감시 중에는 모델 학습을 실행할 수 없습니다.",
        }
    labels = {
        "idle": ("모델 갱신 · 대기 중", "새 학습 요청을 기다리고 있습니다."),
        "data_accumulating": ("모델 갱신 · 학습 데이터 수집 중", "실제 판단과 결과를 모으고 있습니다."),
        "training_pending": ("모델 갱신 · 새 학습 준비됨", "앱이 OFF일 때 새 모델을 학습할 수 있습니다."),
        "curating": ("모델 갱신 · 데이터 정리 중", "학습 데이터를 정리하고 있습니다."),
        "feature_building": ("모델 갱신 · 특징 생성 중", "학습용 특징을 만들고 있습니다."),
        "training": ("모델 갱신 · 학습 중", "새 모델을 학습하고 있습니다."),
        "calibrating": ("모델 갱신 · 신뢰도 조정 중", "모델 신뢰도를 조정하고 있습니다."),
        "promotion_ready": ("Level 승격 검토 가능", "판단 권한 확대에는 사용자 승인이 필요합니다."),
        "failed": ("모델 갱신 · 문제 발생", "학습 작업에 문제가 발생했습니다."),
    }
    if raw == "evaluating_challenger":
        if bool(comparison.get("comparison_complete")) and bool(comparison.get("challenger_better")):
            title, detail = "모델 갱신 · 새 모델 평가 완료", "더 나은 새 모델이 준비되어 적용 여부를 확인하고 있습니다."
        elif bool(comparison.get("comparison_complete")):
            title, detail = "모델 갱신 · 평가 완료", "평가 결과 현재 모델을 유지합니다."
        else:
            title, detail = "모델 갱신 · 새 모델 평가 중", "새 모델의 성능을 평가하고 있습니다."
    else:
        title, detail = labels.get(raw, ("모델 갱신 · 상태 확인 필요", "학습 진행 상태를 새로고침해 주세요."))
    return {"raw_state": raw, "title": title, "detail": detail}


def build_local_engine_user_view_model(snapshot: dict[str, Any]) -> dict[str, Any]:
    level = int(snapshot.get("effective_level") or 0)
    task_rows = list(snapshot.get("task_rows") or [])
    counts = dict(snapshot.get("data_counts") or {})
    comparison = dict(snapshot.get("model_comparison") or {})
    champion = dict(snapshot.get("champion") or {})
    challenger = dict(snapshot.get("challenger") or {})
    provider = str(snapshot.get("provider") or "").lower()
    attention = sum(1 for row in task_rows if _task_status(row) != "준비됨")
    stable_tasks = len(task_rows) - attention
    simple_tasks = []
    for row in task_rows:
        level_value = int(row.get("level") or 0)
        simple_tasks.append({
            "task_key": row.get("task_key"),
            "name": row.get("task_name") or "기타 판단",
            "status": _task_status(row),
            "local_role": "사용 안 함" if level_value <= 0 else ("후보 판단 가능" if level_value < 3 else "제한된 판단 가능"),
            "external_ai": "필수" if level_value <= 0 else "필요",
            "next_condition": BLOCKER_TEXT.get(str(row.get("blocker") or ""), "실제 판단과 결과를 더 학습해야 합니다."),
            "technical": row,
        })

    challenger_ready = bool(challenger.get("model_id"))
    challenger_better = bool(comparison.get("comparison_complete") and comparison.get("challenger_better"))
    promotion_visible = bool(snapshot.get("promotion_candidate"))
    if challenger_ready and challenger_better:
        recommended = {"code": "apply_challenger", "text": "새 모델 적용 검토", "button": "새 모델 적용"}
    elif snapshot.get("teacher_sync_required"):
        recommended = {"code": "teacher_sync", "text": "GPT/Gemini로 최신 시장 다시 학습", "button": "GPT/Gemini로 다시 학습"}
    elif str((snapshot.get("learning") or {}).get("status") or "") == "training_pending":
        recommended = {"code": "maintenance", "text": "앱을 OFF로 전환한 후 새 모델 학습", "button": "앱 OFF 후 모델 갱신"}
    else:
        recommended = {"code": "collect_data", "text": "추가 데이터 수집 중", "button": "상태 새로고침"}

    teacher_name = {"openai": "OpenAI", "gemini": "Gemini"}.get(provider, "교사 AI")
    file_rows = []
    for row in snapshot.get("state_files") or []:
        item = dict(row)
        item["friendly_name"] = FILE_NAMES.get(str(row.get("name") or ""), "LOCAL_ENGINE 운영 데이터")
        item["local_modified_at"] = _local_time(row.get("modified_at"))
        file_rows.append(item)

    return {
        "schema": "aits_local_engine_user_view_model.v1",
        "headline": f"LOCAL_ENGINE Lv{level} · 학습 중" if level <= 1 else f"LOCAL_ENGINE Lv{level} · {LEVEL_ROLES.get(level, '상태 확인 필요')}",
        "level_text": f"Lv{level} · {LEVEL_ROLES.get(level, '상태 확인 필요')}",
        "role_text": snapshot.get("authority_name") or "상태 확인 필요",
        "health_summary": f"전체 상태 · {snapshot.get('health_name') or '상태 확인 필요'}",
        "health_detail": f"전체 엔진은 정상이며, {attention}개 판단 기능은 아직 학습 중입니다." if snapshot.get("health_code") == "stable" else "전체 엔진 상태와 기능별 학습 상태를 확인해 주세요.",
        "task_attention_summary": {"total": len(task_rows), "stable": stable_tasks, "attention": attention},
        "final_decision_message": "최종 주문 판단에는 아직 적용되지 않습니다.",
        "current_model_text": champion.get("model_id") or "현재 모델 확인 필요",
        "last_training_text": _local_time((snapshot.get("learning") or {}).get("last_training_at")),
        "teacher_sync_summary": {
            "title": f"교사 AI · {teacher_name} 연결됨" if provider in {"openai", "gemini"} else "교사 AI · 연결 상태 확인 필요",
            "detail": "최근 시장 판단을 LOCAL_ENGINE 학습에 사용하고 있습니다." if provider in {"openai", "gemini"} else "AI 연결 설정에서 GPT/Gemini 상태를 확인해 주세요.",
            "required": bool(snapshot.get("teacher_sync_required")),
        },
        "maintenance_summary": _maintenance_summary(snapshot),
        "simple_tasks": simple_tasks,
        "learning_data_summary": [
            ("학습 가능한 판단", counts.get("curated_records", 0)),
            ("결과 확인 완료", counts.get("calibration_usable", 0)),
            ("교사 AI 판단", counts.get("distillation_records", 0)),
            ("포트폴리오 학습", counts.get("portfolio_teacher", 0)),
            ("매도·익절 학습", sum(int(row.get("non_wait_samples") or 0) for row in task_rows)),
        ],
        "challenger_visible": challenger_ready,
        "challenger_better": challenger_better,
        "challenger_title": "더 나은 새 모델이 준비됐습니다." if challenger_better else "새 모델 후보를 평가했습니다.",
        "challenger_detail": "판단 균형과 신뢰도 오차가 개선됐고 위험 예측 악화는 없습니다." if challenger_better else "평가 결과를 기술 성능 지표에서 확인할 수 있습니다.",
        "challenger_model_text": challenger.get("model_id") or "",
        "same_level_explanation": "모델만 교체되며 LOCAL_ENGINE Level과 판단 권한은 변하지 않습니다.",
        "promotion_visible": promotion_visible,
        "promotion_explanation": "Level 승격은 LOCAL_ENGINE의 판단 권한을 확대하며 사용자 승인이 필요합니다.",
        "rollback_visible": bool(snapshot.get("rollback_available")),
        "recommended_action": recommended,
        "friendly_state_files": file_rows,
        "technical_metrics": comparison.get("metrics") or {},
    }


def human_blocker(value: object) -> str:
    text = str(value or "")
    return BLOCKER_TEXT.get(text, "없음" if not text else "추가 평가가 필요합니다.")


def human_event(value: object) -> str:
    return EVENT_NAMES.get(str(value or ""), "LOCAL_ENGINE 운영 상태 변경")


def local_time(value: object) -> str:
    return _local_time(value)
