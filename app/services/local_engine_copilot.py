from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.local_engine_review_learning_bridge import AITSLocalEngineReviewLearningBridge


TASK_KEY_MAP = {
    "portfolio_management_decision": "portfolio_management",
    "rotation_decision": "rotation",
    "buy_decision": "position_buy_add",
    "sell_decision": "position_sell_reduce",
    "post_order_replanning": "position_wait_hold",
    "remaining_position_redecision": "position_wait_hold",
}


def copilot_task_key(task: object, action: object = "") -> str:
    value = str(task or "")
    if value in TASK_KEY_MAP:
        return TASK_KEY_MAP[value]
    action_value = str(action or "").lower()
    if action_value in {"buy", "add"}:
        return "position_buy_add"
    if action_value in {"sell", "reduce"}:
        return "position_sell_reduce"
    if action_value in {"take_profit", "stop_loss"}:
        return "take_profit_stop_loss"
    if action_value == "rotate":
        return "rotation"
    return "position_wait_hold"


class AITSLocalEngineCopilot:
    SCHEMA = "aits_local_engine_copilot_decision.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)

    @staticmethod
    def _candidate_value(candidate: dict[str, Any], model_state: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if candidate.get(key) is not None:
                return candidate.get(key)
            if model_state.get(key) is not None:
                return model_state.get(key)
        return None

    def build(
        self,
        *,
        candidate: dict[str, Any],
        model_state: dict[str, Any],
        context: dict[str, Any],
        authority: dict[str, Any],
        requested_provider: str = "",
    ) -> dict[str, Any]:
        action = str(
            self._candidate_value(candidate, model_state, "action", "model_recommended_action") or "wait"
        ).lower()
        effective = int(authority.get("effective_level") or 0)
        confidence = self._candidate_value(candidate, model_state, "confidence", "model_confidence")
        risk_level = str(
            self._candidate_value(candidate, model_state, "risk_level", "model_risk_level") or "medium"
        )
        abstain = bool(self._candidate_value(candidate, model_state, "abstain_required"))
        escalation = bool(
            self._candidate_value(candidate, model_state, "escalation_required")
            or abstain
            or action in {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}
            or risk_level in {"high", "blocked"}
        )
        requested = str(requested_provider or "").lower()
        provider_recommendation = requested if requested in {"openai", "gemini"} else "external_teacher"
        priority = AITSLocalEngineReviewLearningBridge(self.data_root).inspect_priority()
        priority_actions = list(priority.get("priority_actions") or [])
        task_key = copilot_task_key(context.get("task"), action)
        teacher_priority = action in priority_actions or task_key in (priority.get("priority_tasks") or [])
        blockers = list(candidate.get("blockers") or [])
        if not candidate:
            blockers.append("local_engine_candidate_unavailable")
        authority_state = str(authority.get("authority_state") or "external_only")
        preview_only = effective < 2
        return {
            "schema": self.SCHEMA,
            "decision_id": context.get("decision_id") or context.get("request_id"),
            "prediction_id": candidate.get("prediction_id") or model_state.get("local_model_prediction_id"),
            "task": context.get("task"),
            "scope": context.get("symbol") or context.get("scope") or "PORTFOLIO",
            "model_id": candidate.get("model_artifact_id") or model_state.get("local_model_id"),
            "global_level": int(authority.get("global_level") or 0),
            "task_level": int(authority.get("task_level") or 0),
            "effective_level": effective,
            "authority_state": authority_state,
            "action_candidate": action,
            "action_probabilities": dict(candidate.get("action_probabilities") or {}),
            "confidence": confidence,
            "confidence_calibrated": bool(candidate.get("confidence_calibrated")),
            "confidence_reliability": candidate.get("confidence_reliability") or (
                "calibrated" if candidate.get("confidence_calibrated") else "uncalibrated"
            ),
            "risk_level": risk_level,
            "risk_score": self._candidate_value(candidate, model_state, "risk_score", "model_risk_score"),
            "blockers": sorted(set(str(value) for value in blockers if value)),
            "abstain_required": abstain,
            "abstain_reason": str(candidate.get("abstain_reason") or ""),
            "escalation_required": escalation,
            "escalation_target": provider_recommendation,
            "escalation_reason": str(candidate.get("escalation_reason") or (
                "external_confirmation_required" if escalation else "external_teacher_policy"
            )),
            "teacher_confirmation_required": True,
            "teacher_sampling_recommended": bool(teacher_priority or escalation),
            "provider_route_recommendation": provider_recommendation,
            "eta_seconds": candidate.get("eta_seconds"),
            "invalidation_conditions": list(candidate.get("invalidation_conditions") or []),
            "evidence": list(candidate.get("evidence") or []),
            "reason_ko": str(candidate.get("reason_ko") or "LOCAL_ENGINE 후보 판단을 외부 AI가 확인해야 합니다."),
            "review_pattern_context": {
                "priority_task": task_key in (priority.get("priority_tasks") or []),
                "priority_action": action in priority_actions,
                "retraining_reason_codes": list(priority.get("retraining_reason_codes") or [])[:10],
            },
            "copilot_preview_only": preview_only,
            "copilot_routing_allowed": effective >= 2,
            "candidate_only": True,
            "applied_to_final_action": False,
            "final_action_unchanged": True,
            "local_final_allowed": False,
            "external_final_required": True,
            "riskguard_required": True,
            "livepreflight_required": True,
            "cost_guard_required": True,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "safe_for_live_expansion": False,
            "actual_order": False,
            "submitted": 0,
        }
