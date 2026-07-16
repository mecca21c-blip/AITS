from __future__ import annotations

from typing import Any

from app.services.local_model_registry import AITSLocalModelRegistry


class AITSLocalEngineChampionChallenger:
    SCHEMA = "aits_local_engine_champion_challenger.v1"

    def __init__(self, registry: AITSLocalModelRegistry | None = None) -> None:
        self.registry = registry or AITSLocalModelRegistry()

    def inspect(self) -> dict[str, Any]:
        registry = self.registry.load_registry()
        usable = [
            row for row in self.registry.list_usable_models(registry)
            if str(row.get("engine_schema") or "").startswith("aits_local_engine_multi_head")
        ]
        champion = self.registry.latest_multi_head_candidate()
        challengers = [row for row in usable if row.get("model_id") != champion.get("model_id")]
        challenger = challengers[-1] if challengers else {}
        return {
            "schema": self.SCHEMA,
            "champion_model_id": str(champion.get("model_id") or ""),
            "challenger_model_id": str(challenger.get("model_id") or ""),
            "previous_champion_model_id": str(challenger.get("model_id") or ""),
            "comparison_status": "awaiting_challenger" if not challenger else "evaluation_required",
            "challenger_better": False,
            "authority_change_required": False,
            "user_approval_required": True,
            "rollback_ready": bool(challenger),
            "challenger_evaluation_ready": True,
            "same_level_model_replacement_policy_ready": True,
            "no_data_overwrites_latest_usable_detected": False,
        }
    @staticmethod
    def compare(champion: dict[str, Any], challenger: dict[str, Any]) -> dict[str, Any]:
        """Report comparison evidence; never activates a model."""
        current = dict(champion.get("metrics") or {})
        proposed = dict(challenger.get("metrics") or {})
        keys = ("macro_f1", "balanced_accuracy", "brier_score", "unsafe_prediction_count")
        comparable = all(current.get(key) is not None and proposed.get(key) is not None for key in keys)
        challenger_better = bool(
            comparable
            and float(proposed["macro_f1"]) > float(current["macro_f1"])
            and float(proposed["balanced_accuracy"]) >= float(current["balanced_accuracy"])
            and float(proposed["brier_score"]) <= float(current["brier_score"])
            and int(proposed["unsafe_prediction_count"]) <= int(current["unsafe_prediction_count"])
        )
        return {
            "metrics": {key: {"champion": current.get(key), "challenger": proposed.get(key)} for key in keys},
            "comparison_complete": comparable,
            "challenger_better": challenger_better,
            "activation_performed": False,
            "user_approval_required": True,
        }
