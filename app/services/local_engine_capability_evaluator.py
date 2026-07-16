from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import read_json_dict


TASK_CAPABILITY_ACTIONS = {
    "position_wait_hold": ("wait", "hold"),
    "position_buy_add": ("buy", "add"),
    "position_sell_reduce": ("sell", "reduce"),
    "take_profit_stop_loss": ("take_profit", "stop_loss"),
    "portfolio_management": ("wait", "hold", "reduce"),
    "rotation": ("rotate",),
    "promotion_candidate_selection": ("wait", "promote", "replace"),
    "risk_pre_assessment": (),
    "eta_redecision": (),
    "invalidation_monitoring": (),
    "reason_explanation": (),
}


class AITSLocalEngineCapabilityEvaluator:
    """Conservative, evidence-only task capability evaluator."""

    SCHEMA = "aits_local_engine_capability_matrix.v1"

    def __init__(
        self,
        *,
        registry: AITSLocalModelRegistry | None = None,
        training_root: Path | str = Path("data") / "ai_decision_training",
    ) -> None:
        self.registry = registry or AITSLocalModelRegistry()
        self.training_root = Path(training_root)

    def evaluate(self) -> dict[str, Any]:
        model = self.registry.latest_multi_head_candidate()
        metrics = dict(model.get("metrics") or {})
        per_action = dict(model.get("per_action_metrics") or metrics.get("per_action_metrics") or {})
        class_distribution = Counter(model.get("class_distribution") or {})
        supported_actions = set(model.get("supported_actions") or [])
        supported_tasks = set(model.get("supported_tasks") or [])
        dataset = read_json_dict(
            self.training_root / "local_engine_teacher_distillation_summary.json", {}
        )
        teacher_count = int(dataset.get("teacher_present_count") or sum(class_distribution.values()))
        outcome_count = int(dataset.get("outcome_label_present_count") or 0)
        entries: dict[str, dict[str, Any]] = {}

        for task_key, requested_actions in TASK_CAPABILITY_ACTIONS.items():
            supported = [action for action in requested_actions if action in supported_actions]
            unsupported = [action for action in requested_actions if action not in supported_actions]
            action_samples = sum(int(class_distribution.get(action) or 0) for action in requested_actions)
            level = 0
            blocker = "insufficient_task_evidence"
            if task_key == "position_wait_hold" and supported and action_samples >= 10:
                level, blocker = 1, "user_approval_required_above_candidate"
            elif task_key in {"risk_pre_assessment", "eta_redecision", "invalidation_monitoring", "reason_explanation"} and model:
                level, blocker = 1, "candidate_only_evidence"
            elif task_key == "position_sell_reduce" and action_samples:
                level, blocker = 1, "non_wait_recall_insufficient"
            elif task_key == "take_profit_stop_loss" and action_samples:
                level, blocker = 1, "non_wait_recall_insufficient"
            elif task_key == "portfolio_management":
                blocker = "portfolio_teacher_labels_missing"
            elif task_key == "rotation":
                blocker = "rotation_teacher_labels_missing"
            elif task_key == "position_buy_add":
                blocker = "buy_add_teacher_labels_missing"

            entries[task_key] = {
                "task_key": task_key,
                "capability_level": level,
                "authority_state": "candidate_only" if level else "external_only",
                "supported_actions": supported,
                "unsupported_actions": unsupported,
                "model_id": str(model.get("model_id") or ""),
                "sample_count": action_samples or teacher_count if not requested_actions else action_samples,
                "recent_sample_count": int(dataset.get("recent_record_count") or 0),
                "teacher_sample_count": action_samples,
                "outcome_sample_count": outcome_count,
                "non_wait_sample_count": sum(
                    int(class_distribution.get(action) or 0)
                    for action in requested_actions if action not in {"wait", "hold"}
                ),
                "action_metrics": {action: per_action.get(action, {}) for action in requested_actions},
                "confidence_metrics": {
                    "brier_score": metrics.get("brier_score"),
                    "expected_calibration_error": metrics.get("expected_calibration_error"),
                },
                "risk_metrics": {
                    "unsafe_prediction_count": int(metrics.get("unsafe_prediction_count") or 0),
                    "blocker_recall": metrics.get("blocker_recall"),
                },
                "drift_metrics": {},
                "data_freshness": "available" if model else "missing",
                "health_status": "watch" if blocker else "stable",
                "blocker": blocker,
                "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "schema": self.SCHEMA,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "model_id": str(model.get("model_id") or ""),
            "model_capability_level": max((entry["capability_level"] for entry in entries.values()), default=0),
            "task_capabilities": entries,
            "task_capability_matrix_ready": bool(entries),
            "portfolio_capability_status": entries["portfolio_management"]["blocker"],
            "sell_capability_status": entries["position_sell_reduce"]["blocker"],
            "buy_capability_status": entries["position_buy_add"]["blocker"],
            "rotation_capability_status": entries["rotation"]["blocker"],
        }
