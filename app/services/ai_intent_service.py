from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Mapping

from app.services.ai_intent_repository import AITSAIIntentRepository


INTENT_SCHEMA = "aits_ai_intent.v1"
LIFECYCLE = {"proposed", "active", "revised", "satisfied", "invalidated", "expired", "completed", "cancelled", "blocked", "inconclusive"}
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}


class AITSAIIntentService:
    schema = INTENT_SCHEMA

    def __init__(self, repository: AITSAIIntentRepository | None = None) -> None:
        self.repository = repository or AITSAIIntentRepository()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _task_watch_points(task: str, payload: Mapping[str, Any]) -> list[str]:
        explicit = payload.get("watch_points") or payload.get("required_watch_points")
        if isinstance(explicit, list) and explicit:
            return [str(v) for v in explicit if str(v).strip()]
        task = str(task or "")
        if "portfolio" in task:
            return ["현금 비중", "총 노출", "종목 집중도", "후보 대안"]
        if "rotation" in task:
            return ["기존 종목 추세", "신규 후보 우위", "포트폴리오 영향"]
        if "buy" in task or "candidate" in task:
            return ["시장 방향", "거래량", "모멘텀", "현금·노출 제약"]
        if "sell" in task:
            return ["손익", "모멘텀", "변동성", "잔여 수량"]
        return ["가격 변화", "모멘텀", "변동성", "포지션 위험"]

    def build(
        self,
        *,
        decision: Mapping[str, Any],
        payload: Mapping[str, Any] | None = None,
        effective_policy: Mapping[str, Any] | None = None,
        parent_intent: Mapping[str, Any] | None = None,
        status: str = "proposed",
        persist: bool = False,
    ) -> dict[str, Any]:
        decision, payload = dict(decision or {}), dict(payload or {})
        policy, parent = dict(effective_policy or {}), dict(parent_intent or {})
        provider_intent = decision.get("ai_intent") if isinstance(decision.get("ai_intent"), dict) else {}
        now = self._now()
        decision_id = str(decision.get("decision_id") or decision.get("response_id") or payload.get("decision_id") or "")
        task = str(payload.get("task") or decision.get("task") or "ai_decision")
        scope = str(payload.get("scope") or decision.get("scope") or payload.get("symbol") or "")
        symbol = str(payload.get("symbol") or decision.get("symbol") or "").strip().upper()
        if parent and str(parent.get("decision_id") or "") == decision_id:
            revision = max(1, int(parent.get("revision") or 1))
        else:
            requested_revision = int(payload.get("intent_revision") or 0)
            revision = max(1, requested_revision, int(parent.get("revision") or 0) + (1 if parent else 0))
        identity = f"{decision_id}|{task}|{scope}|{revision}"
        intent_id = "intent-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        action = str(decision.get("action") or "wait").lower()
        eta_seconds = max(0, int(float(decision.get("eta_seconds") or 0)))
        reason = str(decision.get("reason_ko") or decision.get("reason") or "").strip()
        invalidation = decision.get("invalidation_conditions") or []
        if isinstance(invalidation, dict):
            invalidation = [invalidation]
        expected = str(provider_intent.get("expected_scenario") or decision.get("expected_scenario") or payload.get("expected_scenario") or "").strip()
        watch = self._task_watch_points(task, {
            **payload,
            "watch_points": provider_intent.get("watch_points") or payload.get("watch_points"),
            "required_watch_points": policy.get("required_watch_points"),
        })
        status = status if status in LIFECYCLE else "inconclusive"
        intent = {
            "schema": INTENT_SCHEMA, "intent_id": intent_id, "decision_id": decision_id,
            "parent_intent_id": str(parent.get("intent_id") or payload.get("previous_intent_id") or ""),
            "session_id": str(payload.get("session_id") or decision.get("session_id") or ""),
            "task": task, "scope": scope, "symbol": symbol,
            "created_at": now.isoformat(), "updated_at": now.isoformat(), "revision": revision, "status": status,
            "goal": str(provider_intent.get("goal") or reason or "현재 조건을 관찰하고 다음 판단 시점을 준비합니다."),
            "goal_type": "observe" if action in {"wait", "hold"} else "decision_followup",
            "current_plan": f"{action} 판단의 조건과 결과를 관찰합니다.",
            "expected_scenario": expected,
            "expected_market_behavior": expected,
            "watch_points": watch,
            "confirmation_conditions": list(provider_intent.get("confirmation_conditions") or decision.get("confirmation_conditions") or []),
            "invalidation_conditions": list(invalidation),
            "risk_watch_points": list(decision.get("risk_watch_points") or []),
            "alternative_scenarios": list(provider_intent.get("alternative_scenarios") or decision.get("alternative_scenarios") or []),
            "next_possible_actions": list(policy.get("allowed_actions") or ["wait", "hold"]),
            "actions_not_promised": sorted(ORDER_ACTIONS),
            "eta_seconds": eta_seconds,
            "eta_expires_at": (now + timedelta(seconds=eta_seconds)).isoformat() if eta_seconds else "",
            "eta_reason": str(decision.get("eta_reason") or "판단 조건을 다시 확인할 시점입니다."),
            "monitoring_priority": str(decision.get("monitoring_priority") or "normal"),
            "effective_policy_id": str(policy.get("policy_id") or ""),
            "effective_policy_version": policy.get("policy_version"),
            "effective_policy_hash": str(policy.get("policy_hash") or ""),
            "allowed_actions": list(policy.get("allowed_actions") or []),
            "policy_constraints": {key: policy.get(key) for key in ("max_asset_weight", "max_total_exposure", "max_order_krw", "cash_reserve", "portfolio_cap") if policy.get(key) not in (None, "", 0, 0.0)},
            "policy_blockers": list(policy.get("policy_conflicts") or []),
            "headline_ko": "현재 판단의 관찰 계획",
            "goal_ko": reason or "현재 조건을 관찰하고 있습니다.",
            "watching_ko": ", ".join(watch),
            "condition_ko": "판단 조건이 충족되면 다시 확인합니다.",
            "waiting_reason_ko": reason if action in {"wait", "hold"} else "판단 이후 조건 변화를 확인합니다.",
            "risk_ko": str(decision.get("risk_notes") or "위험 조건과 무효화 조건을 함께 확인합니다."),
            "next_review_ko": f"약 {max(1, eta_seconds // 60)}분 후 재확인" if eta_seconds else "조건 변화 시 재확인",
            "intent_is_order_promise": False, "direct_order_authority": False, "final_action_unchanged": True,
        }
        if persist:
            if status == "proposed":
                intent["status"] = "active"
            self.repository.upsert_active(intent, event_type="intent_activated" if not parent else "intent_revised")
        return intent

    def transition(self, intent_id: str, status: str, *, reason: str = "") -> dict[str, Any]:
        if status not in LIFECYCLE - {"proposed", "active", "revised"}:
            return {"written": False, "blocker": "intent_lifecycle_transition_invalid"}
        return self.repository.transition(intent_id, status, reason=reason)
