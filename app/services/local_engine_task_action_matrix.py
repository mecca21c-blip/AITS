from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.local_engine_authority_grants import AITSLocalEngineAuthorityGrantRepository
from app.services.local_engine_authority_manager import LEVEL_AUTHORITY, LocalEngineAuthorityPolicyV1
from app.services.local_engine_resource_gate import AITSLocalEngineResourceGate
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import atomic_write_json


TASK_ACTIONS = {
    "position_wait_hold": ("wait", "hold"),
    "position_buy_add": ("buy", "add", "wait"),
    "position_sell_reduce": ("sell", "reduce", "hold", "wait"),
    "take_profit_stop_loss": ("take_profit", "stop_loss", "hold", "wait"),
    "portfolio_management": ("wait", "hold", "add", "reduce", "rotate"),
    "rotation": ("rotate", "wait", "hold"),
    "promotion_candidate_selection": ("wait", "hold"),
    "risk_pre_assessment": ("wait", "hold"),
    "eta_redecision": ("wait", "hold"),
    "invalidation_monitoring": ("wait", "hold"),
    "reason_explanation": ("wait", "hold"),
}
ALL_ACTIONS = ("wait", "hold", "buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate")


class AITSLocalEngineTaskActionMatrix:
    """Derived task/action authority SSOT; global level remains owned by Authority Manager."""

    SCHEMA = "aits_local_engine_task_action_authority_matrix.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.registry = AITSLocalModelRegistry(self.data_root / "local_models")
        self.grants = AITSLocalEngineAuthorityGrantRepository(self.data_root / "local_engine")
        self.state_path = self.data_root / "local_engine" / "local_engine_task_action_authority_matrix.json"

    def build(self, authority: dict[str, Any]) -> dict[str, Any]:
        model = self.registry.latest_multi_head_candidate()
        model_id = str(model.get("model_id") or authority.get("champion_model_id") or "")
        calibrator = self.registry.load_latest_usable_calibrator(model_id)
        calibrator_id = str(calibrator.get("calibrator_id") or "")
        resource = AITSLocalEngineResourceGate.evaluate(
            model, policy=LocalEngineAuthorityPolicyV1.as_dict(),
            latency_ms=model.get("inference_latency_ms"), peak_memory_mb=model.get("peak_memory_mb"),
        )
        entries: list[dict[str, Any]] = []
        global_level = int(authority.get("global_level") or 0)
        health_cap = int(authority.get("health_level_cap") or 0)
        user_cap = int(authority.get("user_level_cap") or 0)
        model_cap = int(authority.get("model_capability_level") or 0)
        health = str(authority.get("health_status") or "blocked")
        tasks = dict(authority.get("task_capabilities") or {})
        for task_key, supported_actions in TASK_ACTIONS.items():
            task = dict(tasks.get(task_key) or {})
            task_level = int(task.get("capability_level") or 0)
            per_action = dict(task.get("action_metrics") or {})
            for action in ALL_ACTIONS:
                supported = action in supported_actions
                metrics = dict(per_action.get(action) or {})
                sample_count = int(metrics.get("support") or (task.get("sample_count") if supported else 0) or 0)
                action_cap = task_level if supported and sample_count > 0 else min(task_level, 1 if supported else 0)
                grant = self.grants.active_grant(task_key=task_key, action=action, model_id=model_id, calibrator_id=calibrator_id)
                # Lv0-Lv2 are global observation/co-pilot authority. A durable scoped
                # grant is required only for Lv3+ final-decision participation.
                approved_level = int(grant.get("maximum_level") or min(global_level, 2))
                effective = min(global_level, task_level, action_cap, model_cap, health_cap, user_cap, approved_level)
                order_action = action not in {"wait", "hold"}
                local_final_allowed = bool(
                    grant and resource.get("low_resource_compatible") and
                    ((effective >= 3 and not order_action) or effective >= 4)
                )
                blockers: list[str] = []
                if not supported: blockers.append("unsupported_task_action")
                if not sample_count: blockers.append("insufficient_action_samples")
                if not calibrator_id: blockers.append("compatible_calibrator_missing")
                if not grant: blockers.append("user_authority_grant_missing")
                blockers.extend(resource.get("blockers") or [])
                if health in {"degraded", "relearning", "blocked"}: blockers.append(f"health_{health}_authority_cap")
                entries.append({
                    "task_key": task_key, "action": action, "supported": supported,
                    "trained": bool(model and sample_count), "sample_count": sample_count,
                    "teacher_count": int(task.get("teacher_sample_count") or 0),
                    "outcome_count": int(task.get("outcome_sample_count") or 0),
                    "recent_count": int(task.get("recent_sample_count") or 0),
                    "review_eligible_count": int(task.get("review_eligible_count") or 0),
                    "capability_level": task_level, "action_capability_level": action_cap,
                    "maximum_allowed_level": min(task_level, action_cap, model_cap, health_cap),
                    "approved_level": approved_level, "effective_level": effective,
                    "authority_state": LEVEL_AUTHORITY[effective], "model_id": model_id,
                    "calibrator_id": calibrator_id, "confidence_metrics": dict(task.get("confidence_metrics") or {}),
                    "action_metrics": metrics, "risk_metrics": dict(task.get("risk_metrics") or {}),
                    "recent_metrics": dict(task.get("recent_metrics") or {}),
                    "historical_metrics": dict(task.get("historical_metrics") or {}),
                    "drift_status": str(task.get("drift_status") or authority.get("drift_status") or "unknown"),
                    "health_status": health, "teacher_sync_freshness": str(task.get("data_freshness") or "unknown"),
                    "user_grant_id": str(grant.get("grant_id") or ""),
                    "local_final_allowed": local_final_allowed,
                    "external_confirmation_required": not local_final_allowed or order_action and effective < 4,
                    "blocker": blockers[0] if blockers else "", "blockers": list(dict.fromkeys(blockers)),
                    "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
                })
        return {
            "schema": self.SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "global_authority_state_source": "local_engine_authority_state",
            "global_level": global_level, "task_count": len(TASK_ACTIONS),
            "action_count": len(ALL_ACTIONS), "matrix_entry_count": len(entries),
            "model_id": model_id, "calibrator_id": calibrator_id,
            "resource_gate": resource, "entries": entries,
            "duplicate_authority_ssot_detected": False,
        }

    def persist(self, authority: dict[str, Any]) -> dict[str, Any]:
        """Explicit authority-state projection; observe-only callers use build()."""
        matrix = self.build(authority)
        atomic_write_json(self.state_path, matrix)
        return matrix

    @staticmethod
    def find(matrix: dict[str, Any], task_key: str, action: str) -> dict[str, Any]:
        return next((dict(row) for row in matrix.get("entries") or []
                     if row.get("task_key") == task_key and row.get("action") == action), {})
