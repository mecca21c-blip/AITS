from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.local_engine_authority_manager import LEVEL_AUTHORITY, ORDER_ACTIONS
from app.services.local_engine_task_action_matrix import AITSLocalEngineTaskActionMatrix


class AITSLocalEngineAuthorityResolver:
    """Pure Lv0-Lv5 decision authority resolver. It never executes or mutates a decision."""

    SCHEMA = "aits_local_engine_authority_resolution.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.matrix_service = AITSLocalEngineTaskActionMatrix(data_root)

    def resolve(self, *, authority: dict[str, Any], task_key: str, action: str,
                confidence: float = 0.0, risk_level: str = "unknown", abstain: bool = False,
                out_of_distribution: bool = False, teacher_available: bool = True) -> dict[str, Any]:
        action = str(action or "wait").lower()
        matrix = self.matrix_service.build(authority)
        entry = self.matrix_service.find(matrix, task_key, action)
        effective = int(entry.get("effective_level") or 0)
        order_action = action in ORDER_ACTIONS
        blockers = list(entry.get("blockers") or [])
        if abstain: blockers.append("local_abstention_required")
        if out_of_distribution: blockers.append("out_of_distribution")
        if str(risk_level or "").lower() in {"high", "critical", "blocked"}: blockers.append("high_risk_external_escalation")
        confidence_limit = float((authority.get("authority_policy") or {}).get("minimum_local_final_confidence") or 0.75)
        if confidence < confidence_limit: blockers.append("confidence_below_local_final_threshold")
        grant_ready = bool(entry.get("user_grant_id"))
        health_ready = str(entry.get("health_status") or "") in {"stable", "watch"}
        gate_ready = not blockers and grant_ready and health_ready
        non_order_final = bool(effective >= 3 and not order_action and gate_ready)
        order_final_candidate = bool(effective >= 4 and order_action and gate_ready)
        local_primary = bool(effective >= 5 and gate_ready)
        local_final = non_order_final or order_final_candidate or local_primary
        audit = self.teacher_audit(
            effective_level=effective, risk_level=risk_level, confidence=confidence,
            out_of_distribution=out_of_distribution, drift_status=str(entry.get("drift_status") or ""),
        )
        external_required = bool(not local_final or order_action and effective <= 3 or audit["audit_required"] or not teacher_available and not local_final)
        safe_hold = bool(order_action and external_required and not teacher_available)
        return {
            "schema": self.SCHEMA, "task_key": task_key, "action": action,
            "effective_level": effective, "effective_authority": LEVEL_AUTHORITY[effective],
            "local_candidate_allowed": effective >= 1, "local_copilot_allowed": effective >= 2,
            "local_non_order_final_allowed": non_order_final,
            "local_order_final_candidate_allowed": order_final_candidate,
            "local_final_allowed": local_final, "external_confirmation_required": external_required,
            "teacher_sampling_required": bool(audit["audit_required"]), "safe_hold_required": safe_hold,
            "authority_blockers": list(dict.fromkeys(blockers)),
            "decision_reason_ko": self._reason(effective, local_final, external_required),
            "user_grant_id": str(entry.get("user_grant_id") or ""), "model_id": str(entry.get("model_id") or ""),
            "calibrator_id": str(entry.get("calibrator_id") or ""), "matrix_entry": entry,
            "teacher_audit": audit, "validator_required": True, "riskguard_required": True,
            "livepreflight_required": True, "execution_path_required": True,
            "final_action_unchanged": True,
        }

    @staticmethod
    def teacher_audit(*, effective_level: int, risk_level: str, confidence: float,
                      out_of_distribution: bool, drift_status: str) -> dict[str, Any]:
        reasons: list[str] = []
        rate = 0.0
        if effective_level >= 4: rate = 0.10 if effective_level == 4 else 0.05
        if out_of_distribution: reasons.append("out_of_distribution"); rate = 1.0
        if str(risk_level).lower() in {"high", "critical", "blocked"}: reasons.append("high_risk"); rate = 1.0
        if confidence < 0.75: reasons.append("low_confidence"); rate = max(rate, 1.0)
        if drift_status in {"watch", "degraded", "relearning", "blocked"}: reasons.append("drift_or_health_watch"); rate = max(rate, 0.50)
        return {"audit_required": bool(reasons), "audit_reason": reasons or (["periodic_sampling"] if rate else []),
                "audit_sampling_rate": rate, "teacher_provider": "strategy.ai_provider",
                "teacher_result": None, "local_teacher_agreement": None,
                "outcome_followup_required": bool(rate)}

    @staticmethod
    def _reason(level: int, local_final: bool, external: bool) -> str:
        if level <= 1: return "현재는 후보 판단만 기록하며 최종 판단은 외부 AI 또는 안전 보류가 담당합니다."
        if level == 2: return "LOCAL_ENGINE은 보조 판단을 제공하지만 최종 판단은 외부 AI 또는 안전 보류가 담당합니다."
        if local_final and not external: return "사용자가 승인한 범위와 안전 기준을 충족해 LOCAL 판단 후보가 허용됩니다."
        return "승인 범위 또는 안전 기준을 충족하지 않아 외부 AI 확인이 필요합니다."
