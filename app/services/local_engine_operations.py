from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
from typing import Any

from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_continuous_learning import AITSLocalEngineContinuousLearning
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_engine_authority_grants import AITSLocalEngineAuthorityGrantRepository


class AITSLocalEngineOperations:
    """Validated user operations. UI callers never write LOCAL state files directly."""

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.authority = AITSLocalEngineAuthorityManager(root)
        self.learning = AITSLocalEngineContinuousLearning(root)
        self.registry = AITSLocalModelRegistry()

    def request_manual_demotion(self, *, task_key: str = "") -> dict[str, Any]:
        return self.authority.user_demotion(task_key=task_key, reason="user_requested_from_operations_ui", persist=True)

    def pause_local_authority(self) -> dict[str, Any]:
        return self.authority.pause_local_authority(persist=True)

    def resume_local_authority(self) -> dict[str, Any]:
        return self.authority.resume_local_authority(persist=True)

    def approve_promotion(self, *, approved_by: str) -> dict[str, Any]:
        return self.authority.approve_promotion(approved_by=approved_by, persist=True)

    def reject_promotion(self) -> dict[str, Any]:
        return self.authority.reject_promotion(persist=True)

    def approve_same_level_champion_replacement(self, *, approved_by: str) -> dict[str, Any]:
        state = self.authority.inspect()
        registry = self.registry.load_registry()
        challenger_id = str(registry.get("latest_multi_head_training_attempt_id") or "")
        champion_id = str(registry.get("latest_usable_multi_head_model_id") or "")
        if not approved_by.strip() or not challenger_id or challenger_id == champion_id:
            return {"approved": False, "blocker": "challenger_or_user_approval_missing"}
        restored = self.registry.restore_multi_head_pointer(
            challenger_id, reason="explicit_same_level_user_approval"
        )
        if not restored.get("restored"):
            return {"approved": False, **restored}
        grant_repo = AITSLocalEngineAuthorityGrantRepository(self.authority.root)
        grant_state = grant_repo.inspect()
        revoked_grants = []
        for grant in list(grant_state.get("active_grants") or []):
            if str(grant.get("model_id") or "") == challenger_id:
                continue
            revoked = grant_repo.revoke(
                str(grant.get("grant_id") or ""),
                reason="champion_model_changed_reapproval_required",
                persist=True,
            )
            if revoked.get("revoked"):
                revoked_grants.append(str(grant.get("grant_id") or ""))
        state["previous_champion_model_id"] = champion_id
        state["champion_model_id"] = challenger_id
        state["challenger_model_id"] = ""
        state["authority_approved_by_user"] = bool(state.get("authority_approved_by_user"))
        self.authority._persist_state(
            state,
            event="champion_replaced",
            reason_codes=["same_level_user_approved_challenger"],
        )
        return {"approved": True, "champion_model_id": challenger_id, "authority_level_changed": False,
                "revoked_incompatible_grants": revoked_grants, "grant_reapproval_required": bool(revoked_grants)}

    def rollback_champion(self) -> dict[str, Any]:
        state = self.authority.inspect()
        previous = str(state.get("previous_champion_model_id") or "")
        if not previous:
            return {"rolled_back": False, "blocker": "previous_champion_missing"}
        restored = self.registry.restore_multi_head_pointer(previous, reason="explicit_user_rollback")
        if not restored.get("restored"):
            return {"rolled_back": False, **restored}
        result = self.authority.rollback(persist=True)
        return {**result, "rolled_back": True}

    def request_teacher_sync(self, *, provider: str) -> dict[str, Any]:
        state = self.authority.inspect()
        state["teacher_sync_required"] = True
        state["teacher_sync_reasons"] = sorted(set(list(state.get("teacher_sync_reasons") or []) + ["user_teacher_sync_requested"]))
        result = self.authority._persist_state(
            state, event="teacher_sync_requested", reason_codes=["user_teacher_sync_requested", f"provider:{provider or 'none'}"]
        )
        return {**result, "teacher_sync_requested": True, "provider_mutated": False}

    def request_maintenance_training(self, *, runtime_active: bool, execute: bool = False) -> dict[str, Any]:
        if runtime_active:
            return {"maintenance_started": False, "blocker": "runtime_must_be_off"}
        if not execute:
            state = self.learning.mark_training_pending(
                "user_maintenance_requested", runtime_active=False, persist=True
            )
            return {**state, "maintenance_started": False, "maintenance_queued": True}
        return self.learning.run_manual_maintenance(runtime_active=False, explicit=True, persist=True)

    def request_derived_regeneration(self, *, runtime_active: bool) -> dict[str, Any]:
        """Queue regeneration through maintenance; source records are never modified."""
        return self.request_maintenance_training(runtime_active=runtime_active, execute=False)

    def quarantine_corrupt_derived(self, path: Path | str) -> dict[str, Any]:
        candidate = Path(path).resolve()
        allowed_roots = {(Path("data") / "local_engine").resolve(), (Path("data") / "local_models").resolve(), (Path("data") / "ai_decision_training").resolve()}
        source_names = {"outcome_records.jsonl", "provider_comparison_outcomes.jsonl", "local_engine_candidate_observations.jsonl", "local_engine_teacher_distillation_records.jsonl"}
        if candidate.name in source_names or not any(root == candidate.parent or root in candidate.parents for root in allowed_roots):
            return {"quarantined": False, "blocker": "source_or_out_of_scope_file_protected"}
        try:
            raw = candidate.read_bytes()
            if candidate.suffix == ".json":
                json.loads(raw.decode("utf-8"))
            elif b"\x00" not in raw:
                return {"quarantined": False, "blocker": "derived_file_not_corrupt"}
            else:
                raise ValueError("nul_byte")
            return {"quarantined": False, "blocker": "derived_file_not_corrupt"}
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            quarantine = candidate.with_suffix(candidate.suffix + f".corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
            try:
                shutil.move(str(candidate), str(quarantine))
            except OSError as exc:
                return {"quarantined": False, "blocker": type(exc).__name__}
            return {"quarantined": True, "path": str(quarantine)}

    def backup_state_snapshot(self) -> dict[str, Any]:
        source = self.authority.state_path
        if not source.exists():
            return {"backed_up": False, "blocker": "authority_state_missing"}
        backup_dir = self.authority.root / "snapshots"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"authority-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            return {"backed_up": False, "blocker": type(exc).__name__}
        return {"backed_up": True, "path": str(target)}
