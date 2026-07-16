from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any

from app.services.local_engine_capability_evaluator import AITSLocalEngineCapabilityEvaluator
from app.services.local_engine_champion_challenger import AITSLocalEngineChampionChallenger
from app.services.local_engine_drift_monitor import AITSLocalEngineDriftMonitor
from app.services.local_engine_teacher_sync import AITSLocalEngineTeacherSync
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import atomic_write_json, read_json_dict


LEVEL_AUTHORITY = {
    0: "external_only",
    1: "candidate_only",
    2: "co_pilot",
    3: "task_primary",
    4: "local_primary",
    5: "internal_asset_manager",
}
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}


class LocalEngineAuthorityPolicyV1:
    """Single policy SSOT for authority evaluation, never trading thresholds."""

    schema = "aits_local_engine_authority_policy.v1"
    promotion_thresholds = {
        "minimum_teacher_samples": 100,
        "minimum_non_wait_samples": 25,
        "minimum_macro_f1": 0.50,
        "minimum_balanced_accuracy": 0.60,
        "maximum_brier_score": 0.35,
        "maximum_unsafe_predictions": 0,
    }
    demotion_thresholds = {
        "maximum_drift_score": 0.65,
        "maximum_teacher_disagreement": 0.55,
        "maximum_unsafe_predictions": 0,
    }
    recent_data_weight = 0.7
    historical_replay_weight = 0.3
    promotion_requires_user_approval = True
    automatic_promotion_allowed = False
    automatic_demotion_allowed = True
    live_heavy_learning_allowed = False

    @classmethod
    def as_dict(cls) -> dict[str, Any]:
        return {
            "schema": cls.schema,
            "promotion_thresholds": dict(cls.promotion_thresholds),
            "demotion_thresholds": dict(cls.demotion_thresholds),
            "recent_data_weight": cls.recent_data_weight,
            "historical_replay_weight": cls.historical_replay_weight,
            "promotion_requires_user_approval": cls.promotion_requires_user_approval,
            "automatic_promotion_allowed": cls.automatic_promotion_allowed,
            "automatic_demotion_allowed": cls.automatic_demotion_allowed,
            "live_heavy_learning_allowed": cls.live_heavy_learning_allowed,
        }


class AITSLocalEngineAuthorityManager:
    SCHEMA = "aits_local_engine_authority_state.v1"
    HISTORY_SCHEMA = "aits_local_engine_authority_history_event.v1"

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.root = Path(root)
        self.state_path = self.root / "local_engine_authority_state.json"
        self.history_path = self.root / "local_engine_authority_history.jsonl"
        self.capability_path = self.root / "local_engine_capability_matrix.json"
        self.health_path = self.root / "local_engine_health_state.json"
        self.learning_path = self.root / "local_engine_continuous_learning_state.json"
        self.teacher_sync_path = self.root / "local_engine_teacher_sync_state.json"
        self.policy = LocalEngineAuthorityPolicyV1

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _quarantine_if_corrupt(self, path: Path) -> bool:
        if not path.exists() or not path.stat().st_size:
            return False
        try:
            payload = path.read_bytes()
            if b"\x00" in payload:
                raise ValueError("nul_byte")
            value = json.loads(payload.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("not_object")
            return False
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            quarantine = path.with_suffix(path.suffix + f".corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            try:
                shutil.move(str(path), str(quarantine))
            except OSError:
                pass
            return True

    def _derived_state(self) -> dict[str, Any]:
        capability = AITSLocalEngineCapabilityEvaluator().evaluate()
        drift = AITSLocalEngineDriftMonitor().evaluate()
        models = AITSLocalEngineChampionChallenger().inspect()
        model_exists = bool(models.get("champion_model_id"))
        initial_level = 1 if model_exists else 0
        health = "blocked" if not model_exists else str(drift.get("drift_status") or "watch")
        health_cap = 0 if health == "blocked" else 1 if health == "degraded" else 5
        teacher_sync_required = bool(drift.get("teacher_sync_recommended") or not model_exists)
        teacher_sync = AITSLocalEngineTeacherSync.inspect(
            required=teacher_sync_required,
            recent_data_count=int(drift.get("recent_data_count") or 0),
            reasons=[health] if teacher_sync_required else [],
        )
        return {
            "schema": self.SCHEMA,
            "updated_at": self._now(),
            "global_level": initial_level,
            "global_authority_state": LEVEL_AUTHORITY[initial_level],
            "health_status": health,
            "health_level_cap": health_cap,
            "user_level_cap": 1,
            "model_capability_level": int(capability.get("model_capability_level") or 0),
            "effective_global_level": min(initial_level, health_cap, 1),
            "champion_model_id": str(models.get("champion_model_id") or ""),
            "challenger_model_id": str(models.get("challenger_model_id") or ""),
            "task_capabilities": dict(capability.get("task_capabilities") or {}),
            "teacher_sync_required": teacher_sync_required,
            "teacher_sync_reasons": list(teacher_sync.get("teacher_sync_reasons") or []),
            "promotion_candidate": None,
            "demotion_active": False,
            "demotion_reasons": [],
            "rollback_available": bool(models.get("rollback_ready")),
            "previous_champion_model_id": str(models.get("previous_champion_model_id") or ""),
            "last_training_at": "",
            "last_evaluation_at": self._now(),
            "recent_market_window": int(drift.get("recent_data_count") or 0),
            "recent_data_count": int(drift.get("recent_data_count") or 0),
            "historical_replay_count": int(drift.get("historical_replay_count") or 0),
            "authority_approved_by_user": False,
            "authority_approval_at": "",
            "authority_approval_model_id": "",
            "blocker": "user_approval_required_above_candidate" if model_exists else "local_engine_model_missing",
            "level_initialized_from_existing_authority": model_exists,
            "unsafe_candidate_contract_detected": False,
        }

    def inspect(self, *, persist_initial: bool = False) -> dict[str, Any]:
        corrupted = self._quarantine_if_corrupt(self.state_path) if persist_initial else False
        state = read_json_dict(self.state_path, {})
        if not state or state.get("schema") != self.SCHEMA:
            state = self._derived_state()
            if persist_initial:
                self._persist_state(state, event="level_initialized", reason_codes=["existing_candidate_authority_migration"])
        state = dict(state)
        state["corrupted_state_detected"] = corrupted
        return state

    def _append_history(self, event: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        with self.history_path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def _persist_state(self, state: dict[str, Any], *, event: str, reason_codes: list[str]) -> dict[str, Any]:
        state = dict(state)
        state["updated_at"] = self._now()
        atomic_write_json(self.state_path, state)
        atomic_write_json(self.capability_path, {
            "schema": "aits_local_engine_capability_matrix.v1",
            "updated_at": state["updated_at"],
            "task_capabilities": state.get("task_capabilities") or {},
        })
        atomic_write_json(self.health_path, {
            "schema": "aits_local_engine_health_state.v1",
            "updated_at": state["updated_at"],
            "health_status": state.get("health_status"),
            "health_level_cap": state.get("health_level_cap"),
        })
        teacher_sync = AITSLocalEngineTeacherSync.inspect(
            required=bool(state.get("teacher_sync_required")),
            recent_data_count=int(state.get("recent_data_count") or 0),
            reasons=list(state.get("teacher_sync_reasons") or []),
        )
        atomic_write_json(self.teacher_sync_path, teacher_sync)
        atomic_write_json(self.learning_path, {
            "schema": "aits_local_engine_continuous_learning_state.v1",
            "updated_at": state["updated_at"],
            "status": "data_accumulating",
            "training_pending": bool(state.get("teacher_sync_required")),
            "trigger_reasons": list(state.get("teacher_sync_reasons") or []),
            "live_heavy_learning_disabled": True,
        })
        self._append_history({
            "schema": self.HISTORY_SCHEMA,
            "event_id": str(uuid.uuid4()),
            "event": event,
            "timestamp": state["updated_at"],
            "model_id": state.get("champion_model_id"),
            "previous_model_id": state.get("previous_champion_model_id"),
            "global_level_before": state.get("previous_global_level", state.get("global_level")),
            "global_level_after": state.get("global_level"),
            "task_levels_before": {},
            "task_levels_after": {key: value.get("capability_level") for key, value in (state.get("task_capabilities") or {}).items()},
            "health_before": state.get("previous_health_status", state.get("health_status")),
            "health_after": state.get("health_status"),
            "reason_codes": reason_codes,
            "metrics_digest": {},
            "user_approval_required": event.startswith("promotion"),
            "user_approved": event == "promotion_approved",
            "actual_order": False,
            "submitted": 0,
        })
        return state

    def ensure_operating_state_files(self) -> dict[str, Any]:
        """Explicit migration helper; observe-only callers never invoke it."""
        state = self.inspect(persist_initial=True)
        if not all(path.exists() for path in (self.capability_path, self.health_path, self.learning_path, self.teacher_sync_path)):
            self._persist_state(state, event="capability_evaluated", reason_codes=["authority_operating_state_initialized"])
        return state

    def automatic_demotion(self, *, reasons: list[str], target_level: int | None = None, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        before = int(state.get("global_level") or 0)
        after = max(0, min(before, before - 1 if target_level is None else int(target_level)))
        state.update({
            "previous_global_level": before,
            "global_level": after,
            "global_authority_state": LEVEL_AUTHORITY[after],
            "effective_global_level": min(after, int(state.get("health_level_cap") or 0), int(state.get("user_level_cap") or 0)),
            "demotion_active": after < before,
            "demotion_reasons": list(reasons),
            "teacher_sync_required": True,
            "teacher_sync_reasons": list(reasons),
        })
        return self._persist_state(state, event="automatic_demotion", reason_codes=reasons) if persist else state

    def evaluate_and_apply_safety_caps(self, *, persist: bool = False) -> dict[str, Any]:
        """Apply only downward recommendations from current factual health/drift."""
        state = self.inspect()
        drift = AITSLocalEngineDriftMonitor().evaluate()
        status = str(drift.get("drift_status") or "watch")
        recommended_cap = int(drift.get("level_cap_recommendation") or 0)
        state["health_status"] = status
        state["health_level_cap"] = recommended_cap
        state["previous_health_status"] = state.get("health_status")
        if recommended_cap < int(state.get("global_level") or 0):
            return self.automatic_demotion(
                reasons=["drift_level_cap_recommendation"],
                target_level=recommended_cap,
                persist=persist,
            )
        state["effective_global_level"] = min(
            int(state.get("global_level") or 0), recommended_cap,
            int(state.get("user_level_cap") or 0), int(state.get("model_capability_level") or 0),
        )
        state["automatic_demotion_applied"] = False
        return state

    def user_demotion(self, *, task_key: str = "", reason: str = "user_requested", persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        if task_key and task_key in (state.get("task_capabilities") or {}):
            entry = dict(state["task_capabilities"][task_key])
            entry["capability_level"] = max(0, int(entry.get("capability_level") or 0) - 1)
            entry["authority_state"] = LEVEL_AUTHORITY[entry["capability_level"]]
            entry["blocker"] = reason
            state["task_capabilities"][task_key] = entry
        else:
            before = int(state.get("global_level") or 0)
            state["previous_global_level"] = before
            state["global_level"] = max(0, before - 1)
            state["user_level_cap"] = min(int(state.get("user_level_cap") or 0), state["global_level"])
            state["global_authority_state"] = LEVEL_AUTHORITY[state["global_level"]]
            state["effective_global_level"] = min(state["global_level"], state["user_level_cap"], int(state.get("health_level_cap") or 0))
        state["teacher_sync_required"] = True
        return self._persist_state(state, event="user_demotion", reason_codes=[reason]) if persist else state

    def pause_local_authority(self, *, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        state.update({"user_level_cap": 0, "effective_global_level": 0, "global_authority_state": "external_only", "blocker": "user_paused_local_authority"})
        return self._persist_state(state, event="user_demotion", reason_codes=["user_paused_local_authority"]) if persist else state

    def resume_local_authority(self, *, persist: bool = True) -> dict[str, Any]:
        """Resume only up to the already approved global level; never promote."""
        state = self.inspect()
        approved_cap = int(state.get("global_level") or 0)
        state["user_level_cap"] = approved_cap
        state["effective_global_level"] = min(
            approved_cap,
            int(state.get("health_level_cap") or 0),
            int(state.get("model_capability_level") or 0),
        )
        state["global_authority_state"] = LEVEL_AUTHORITY[state["effective_global_level"]]
        state["blocker"] = "user_approval_required_above_candidate"
        return self._persist_state(state, event="authority_resumed", reason_codes=["user_resumed_existing_authority"]) if persist else state

    def reject_promotion(self, *, reason: str = "user_rejected", persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        candidate = dict(state.get("promotion_candidate") or {})
        if not candidate:
            return {**state, "promotion_rejected": False, "promotion_blocker": "promotion_candidate_missing"}
        candidate.update({"approval_status": "rejected", "approved_by": None, "approved_at": self._now()})
        state["promotion_candidate"] = candidate
        result = self._persist_state(state, event="promotion_rejected", reason_codes=[reason]) if persist else state
        return {**result, "promotion_rejected": True}

    def request_promotion(self, proposed_level: int, *, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        current = int(state.get("global_level") or 0)
        proposed = min(5, max(current, int(proposed_level)))
        model = AITSLocalModelRegistry().latest_multi_head_candidate()
        metrics = dict(model.get("metrics") or {})
        classes = dict(model.get("class_distribution") or {})
        thresholds = self.policy.promotion_thresholds
        teacher_samples = sum(int(value or 0) for value in classes.values())
        non_wait_samples = sum(int(value or 0) for action, value in classes.items() if action not in {"wait", "hold"})
        blockers: list[str] = []
        if teacher_samples < int(thresholds["minimum_teacher_samples"]):
            blockers.append("minimum_teacher_samples_not_met")
        if non_wait_samples < int(thresholds["minimum_non_wait_samples"]):
            blockers.append("minimum_non_wait_samples_not_met")
        if float(metrics.get("macro_f1") or 0.0) < float(thresholds["minimum_macro_f1"]):
            blockers.append("minimum_macro_f1_not_met")
        if float(metrics.get("balanced_accuracy") or 0.0) < float(thresholds["minimum_balanced_accuracy"]):
            blockers.append("minimum_balanced_accuracy_not_met")
        brier = metrics.get("brier_score")
        if brier is None or float(brier) > float(thresholds["maximum_brier_score"]):
            blockers.append("maximum_brier_score_exceeded")
        if int(metrics.get("unsafe_prediction_count") or 0) > int(thresholds["maximum_unsafe_predictions"]):
            blockers.append("unsafe_prediction_detected")
        candidate = {
            "promotion_candidate_id": str(uuid.uuid4()),
            "model_id": state.get("champion_model_id"),
            "current_level": current,
            "proposed_level": proposed,
            "affected_tasks": [],
            "metrics": {
                "teacher_sample_count": teacher_samples,
                "non_wait_sample_count": non_wait_samples,
                "macro_f1": metrics.get("macro_f1"),
                "balanced_accuracy": metrics.get("balanced_accuracy"),
                "brier_score": brier,
                "unsafe_prediction_count": int(metrics.get("unsafe_prediction_count") or 0),
            },
            "blockers": blockers,
            "required_user_approval": True,
            "approval_status": "awaiting_user_approval" if not blockers else "blocked_by_evaluation",
            "approved_by": None,
            "approved_at": None,
        }
        state["promotion_candidate"] = candidate
        return self._persist_state(state, event="promotion_candidate_created", reason_codes=candidate["blockers"]) if persist else state

    def approve_promotion(self, *, approved_by: str, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        candidate = dict(state.get("promotion_candidate") or {})
        blockers = list(candidate.get("blockers") or [])
        if not candidate or blockers or not str(approved_by or "").strip():
            return {**state, "promotion_applied": False, "promotion_blocker": "promotion_evidence_or_user_approval_missing"}
        before = int(state.get("global_level") or 0)
        proposed = min(5, max(before, int(candidate.get("proposed_level") or before)))
        state.update({
            "previous_global_level": before,
            "global_level": proposed,
            "user_level_cap": proposed,
            "effective_global_level": min(proposed, int(state.get("health_level_cap") or 0), int(state.get("model_capability_level") or 0)),
            "global_authority_state": LEVEL_AUTHORITY[proposed],
            "authority_approved_by_user": True,
            "authority_approval_at": self._now(),
            "authority_approval_model_id": state.get("champion_model_id"),
            "promotion_candidate": {**candidate, "approval_status": "approved", "approved_by": approved_by, "approved_at": self._now()},
        })
        result = self._persist_state(state, event="promotion_approved", reason_codes=["user_approved_evaluated_promotion"]) if persist else state
        return {**result, "promotion_applied": True}

    def rollback(self, *, reason: str = "user_rollback_requested", persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        previous = str(state.get("previous_champion_model_id") or "")
        before = int(state.get("global_level") or 0)
        after = min(before, 1) if previous else 0
        state.update({
            "previous_global_level": before,
            "global_level": after,
            "user_level_cap": min(int(state.get("user_level_cap") or 0), after),
            "effective_global_level": after,
            "global_authority_state": LEVEL_AUTHORITY[after],
            "champion_model_id": previous or state.get("champion_model_id"),
            "teacher_sync_required": True,
            "blocker": reason,
        })
        return self._persist_state(state, event="rollback_completed", reason_codes=[reason]) if persist else state

    def automatic_rollback_if_critical(self, *, reason_codes: list[str], persist: bool = True) -> dict[str, Any]:
        critical = {
            "model_artifact_corrupt", "unsafe_prediction", "high_risk_miss",
            "repeated_inference_exception", "champion_activation_degradation",
        }
        matched = sorted(critical.intersection(reason_codes))
        if not matched:
            return {**self.inspect(), "rollback_applied": False, "rollback_blocker": "no_critical_rollback_trigger"}
        result = self.rollback(reason=matched[0], persist=persist)
        return {**result, "rollback_applied": True, "rollback_reason_codes": matched}

    def router_metadata(self, *, task_key: str, action: str = "") -> dict[str, Any]:
        state = self.inspect()
        task = dict((state.get("task_capabilities") or {}).get(task_key) or {})
        effective = min(
            int(state.get("global_level") or 0), int(task.get("capability_level") or 0),
            int(state.get("model_capability_level") or 0), int(state.get("health_level_cap") or 0),
            int(state.get("user_level_cap") or 0),
        )
        order_action = str(action or "").lower() in ORDER_ACTIONS
        local_final_allowed = bool(effective >= 3 and not order_action and state.get("authority_approved_by_user"))
        return {
            "global_level": int(state.get("global_level") or 0),
            "task_level": int(task.get("capability_level") or 0),
            "health_level_cap": int(state.get("health_level_cap") or 0),
            "user_level_cap": int(state.get("user_level_cap") or 0),
            "effective_level": effective,
            "authority_state": LEVEL_AUTHORITY[effective],
            "model_id": state.get("champion_model_id"),
            "local_final_allowed": local_final_allowed,
            "external_confirmation_required": not local_final_allowed,
            "escalation_reason": "candidate_only_authority" if effective <= 1 else "external_confirmation_policy",
            "level_decision_reason": state.get("blocker") or "authority_policy_evaluated",
            "riskguard_required": True,
            "livepreflight_required": True,
        }

    def ui_snapshot_ko(self) -> dict[str, str]:
        state = self.inspect(persist_initial=False)
        health = {"stable": "안정", "watch": "관찰 필요", "degraded": "성능 저하", "relearning": "재학습 중", "blocked": "사용 불가"}
        authority = {"external_only": "외부 교사 전용", "candidate_only": "후보 판단만", "co_pilot": "보조 판단", "task_primary": "승인 task 우선", "local_primary": "LOCAL 우선", "internal_asset_manager": "내부 자산운용"}
        task_names = {"position_wait_hold": "보유/대기", "position_buy_add": "매수/추가", "position_sell_reduce": "매도/축소", "take_profit_stop_loss": "익절/손절", "portfolio_management": "포트폴리오", "rotation": "교체", "promotion_candidate_selection": "승격 후보", "risk_pre_assessment": "위험 사전검토", "eta_redecision": "재판단 시각", "invalidation_monitoring": "무효화 감시", "reason_explanation": "판단 설명"}
        action_names = {"wait": "대기", "hold": "보유", "buy": "매수", "add": "추가", "sell": "매도", "reduce": "축소", "take_profit": "익절", "stop_loss": "손절", "rotate": "교체", "promote": "승격", "replace": "교체"}
        lines = []
        for key, entry in (state.get("task_capabilities") or {}).items():
            actions = ", ".join(action_names.get(value, "기타") for value in entry.get("supported_actions") or []) or "지원 판단 없음"
            lines.append(f"{task_names.get(key, '기타')}: Level {int(entry.get('capability_level') or 0)} · {actions} · 표본 {int(entry.get('sample_count') or 0)}")
        reasons = {"user_approval_required_above_candidate": "후보 단계를 넘으려면 성능 검증과 사용자 승인이 필요합니다.", "local_engine_model_missing": "사용 가능한 LOCAL_ENGINE 모델이 없습니다.", "user_paused_local_authority": "사용자가 LOCAL 권한을 일시 중지했습니다."}
        return {
            "summary": f"LOCAL_ENGINE Level {int(state.get('effective_global_level') or 0)} · {health.get(str(state.get('health_status')), '확인 필요')} · {authority.get(str(state.get('global_authority_state')), '외부 교사 전용')}\nChampion: {state.get('champion_model_id') or '없음'} · Challenger: {state.get('challenger_model_id') or '대기'}",
            "capabilities": "\n".join(lines),
            "reason": reasons.get(str(state.get("blocker") or ""), "현재 근거에 따라 보수적으로 유지 중입니다."),
        }
