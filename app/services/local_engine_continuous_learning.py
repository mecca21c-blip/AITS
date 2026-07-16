from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_champion_challenger import AITSLocalEngineChampionChallenger
from app.services.local_engine_drift_monitor import AITSLocalEngineDriftMonitor
from app.services.local_engine_multi_head import AITSLocalEngineMultiHeadTrainer
from app.services.local_training_dataset_curation import atomic_write_json, read_json_dict


class AITSLocalEngineContinuousLearning:
    """OFF/manual maintenance coordinator. Live paths only mark pending work."""

    SCHEMA = "aits_local_engine_continuous_learning_state.v1"
    STATES = {
        "idle", "data_accumulating", "training_pending", "curating",
        "feature_building", "training", "calibrating", "evaluating_challenger",
        "promotion_ready", "relearning", "failed",
    }

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.root = Path(root)
        self.path = self.root / "local_engine_continuous_learning_state.json"
        self.authority = AITSLocalEngineAuthorityManager(root)

    def inspect(self) -> dict[str, Any]:
        persisted = read_json_dict(self.path, {})
        drift = AITSLocalEngineDriftMonitor().evaluate()
        state = str(persisted.get("status") or "data_accumulating")
        return {
            "schema": self.SCHEMA,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": state if state in self.STATES else "data_accumulating",
            "training_pending": bool(persisted.get("training_pending") or drift.get("teacher_sync_recommended")),
            "trigger_reasons": list(persisted.get("trigger_reasons") or (["drift_or_recent_data_watch"] if drift.get("teacher_sync_recommended") else [])),
            "live_heavy_learning_disabled": True,
            "maintenance_training_path_ready": True,
            "recent_adaptation_ready": True,
            "historical_replay_ready": True,
            "catastrophic_forgetting_guard_ready": True,
            "recent_data_weight": 0.7,
            "historical_replay_weight": 0.3,
            "last_training_at": str(persisted.get("last_training_at") or ""),
            "last_error": str(persisted.get("last_error") or ""),
        }

    def mark_training_pending(self, reason: str, *, runtime_active: bool, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        state.update({"status": "training_pending", "training_pending": True, "trigger_reasons": sorted(set(state["trigger_reasons"] + [reason]))})
        if persist:
            atomic_write_json(self.path, state)
        return {**state, "heavy_learning_performed": False, "runtime_active": bool(runtime_active)}

    def run_manual_maintenance(self, *, runtime_active: bool, explicit: bool, persist: bool = False) -> dict[str, Any]:
        if runtime_active or not explicit:
            return {**self.inspect(), "maintenance_started": False, "blocker": "runtime_must_be_off_and_manual_maintenance_explicit"}
        trained = AITSLocalEngineMultiHeadTrainer().train(persist=persist)
        comparison = AITSLocalEngineChampionChallenger().inspect()
        state = self.inspect()
        state.update({
            "status": "evaluating_challenger" if trained.get("training_ready") else "failed",
            "training_pending": False,
            "last_training_at": datetime.now(timezone.utc).isoformat(),
            "challenger_model_id": str((trained.get("metadata") or {}).get("model_id") or ""),
            "promotion_applied": False,
        })
        if persist:
            atomic_write_json(self.path, state)
        return {**state, "maintenance_started": True, "training": trained, "comparison": comparison}
