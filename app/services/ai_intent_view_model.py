from __future__ import annotations

from typing import Any, Mapping


def build_ai_intent_view_model(intent: Mapping[str, Any] | None, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    intent, policy = dict(intent or {}), dict(policy or {})
    watch = intent.get("watch_points") if isinstance(intent.get("watch_points"), list) else []
    invalidation = intent.get("invalidation_conditions") if isinstance(intent.get("invalidation_conditions"), list) else []
    style = str(policy.get("operating_style") or "균형 운용")
    external = bool(policy.get("external_confirmation_required"))
    return {
        "schema": "aits_ai_intent_user_view.v1",
        "current_goal": str(intent.get("goal_ko") or intent.get("goal") or "AI 판단을 기다리고 있습니다."),
        "watch_points": ", ".join(str(v) for v in watch if str(v).strip()) or "시장과 포지션 변화를 확인합니다.",
        "condition": str(intent.get("condition_ko") or "조건이 충족되면 다시 판단합니다."),
        "plan_change_condition": ", ".join(str(v.get("description") if isinstance(v, dict) else v) for v in invalidation if str(v).strip()) or "무효화 조건이나 위험 변화가 감지될 때 계획을 바꿉니다.",
        "operating_style": style,
        "next_review": str(intent.get("next_review_ko") or "조건 변화 시 재확인"),
        "external_confirmation": "외부 AI 확인이 필요합니다." if external else "현재 정책에 따라 확인합니다.",
        "order_promise_notice": "이 내용은 주문 예약이 아니라 현재 관찰 계획입니다.",
        "status_text": {"active": "관찰 중", "revised": "계획 갱신", "invalidated": "계획 변경 필요", "expired": "재확인 필요", "satisfied": "조건 충족"}.get(str(intent.get("status") or ""), "판단 준비"),
    }
