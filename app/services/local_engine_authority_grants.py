from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid
from typing import Any

from app.services.local_training_dataset_curation import atomic_write_json, read_json_dict


class AITSLocalEngineAuthorityGrantRepository:
    """Durable, explicit-user authority grants; never creates an approved grant implicitly."""

    SCHEMA = "aits_local_engine_authority_grant.v1"
    STATE_SCHEMA = "aits_local_engine_authority_grant_state.v1"
    VALID_STATUSES = {"proposed", "approved", "revoked", "expired", "superseded", "blocked"}

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.root = Path(root)
        self.ledger_path = self.root / "local_engine_authority_grants.jsonl"
        self.state_path = self.root / "local_engine_authority_grant_state.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def inspect(self) -> dict[str, Any]:
        state = read_json_dict(self.state_path, {})
        if state.get("schema") != self.STATE_SCHEMA:
            state = {
                "schema": self.STATE_SCHEMA,
                "updated_at": "",
                "active_grants": [],
                "revoked_grants": [],
                "automatic_grant_detected": False,
            }
        return state

    def active_grant(self, *, task_key: str, action: str, model_id: str, calibrator_id: str = "") -> dict[str, Any]:
        now = self._now()
        for grant in self.inspect().get("active_grants") or []:
            if not isinstance(grant, dict) or grant.get("status") != "approved" or not grant.get("user_approved"):
                continue
            if str(grant.get("task_key") or "") != str(task_key or "") or str(grant.get("action") or "") != str(action or ""):
                continue
            if str(grant.get("model_id") or "") != str(model_id or ""):
                continue
            if calibrator_id and str(grant.get("calibrator_id") or "") != str(calibrator_id):
                continue
            expires_at = str(grant.get("expires_at") or "")
            if expires_at and expires_at <= now:
                continue
            return dict(grant)
        return {}

    def propose(self, *, model_id: str, calibrator_id: str, global_level: int, task_key: str,
                action: str, authority_type: str, maximum_level: int, approval_scope: str,
                approval_reason: str, evidence_digest: dict[str, Any],
                source_promotion_candidate_id: str = "", expires_at: str = "") -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "grant_id": str(uuid.uuid4()),
            "created_at": self._now(),
            "approved_at": "", "revoked_at": "", "status": "proposed",
            "model_id": str(model_id or ""), "calibrator_id": str(calibrator_id or ""),
            "global_level": int(global_level), "task_key": str(task_key or ""),
            "action": str(action or ""), "authority_type": str(authority_type or ""),
            "maximum_level": max(0, min(5, int(maximum_level))),
            "approval_scope": str(approval_scope or ""), "approval_reason": str(approval_reason or ""),
            "evidence_digest": dict(evidence_digest or {}), "user_approved": False,
            "expires_at": str(expires_at or ""), "rollback_grant_id": "",
            "source_promotion_candidate_id": str(source_promotion_candidate_id or ""),
        }

    def approve(self, proposal: dict[str, Any], *, approved_by: str, persist: bool = True) -> dict[str, Any]:
        value = dict(proposal or {})
        if value.get("schema") != self.SCHEMA or value.get("status") != "proposed" or not str(approved_by or "").strip():
            return {"approved": False, "blocker": "explicit_user_approval_or_proposal_missing"}
        required = ("grant_id", "model_id", "task_key", "action", "authority_type")
        if any(not str(value.get(key) or "").strip() for key in required):
            return {"approved": False, "blocker": "grant_contract_incomplete"}
        value.update({"status": "approved", "approved_at": self._now(), "approved_by": str(approved_by), "user_approved": True})
        if persist:
            self._append(value)
            state = self.inspect()
            active = [dict(row) for row in state.get("active_grants") or [] if row.get("grant_id") != value["grant_id"]]
            active.append(value)
            atomic_write_json(self.state_path, {**state, "updated_at": self._now(), "active_grants": active, "automatic_grant_detected": False})
        return {"approved": True, "grant": value}

    def revoke(self, grant_id: str, *, reason: str, persist: bool = True) -> dict[str, Any]:
        state = self.inspect()
        active = [dict(row) for row in state.get("active_grants") or []
                  if isinstance(row, dict) and row.get("grant_id") == grant_id]
        if not active:
            return {"revoked": False, "blocker": "active_grant_missing"}
        value = {**active[0], "status": "revoked", "revoked_at": self._now(), "revocation_reason": str(reason or "user_revoked")}
        if persist:
            self._append(value)
            remaining = [dict(row) for row in state.get("active_grants") or [] if row.get("grant_id") != grant_id]
            revoked = [dict(row) for row in state.get("revoked_grants") or []] + [value]
            atomic_write_json(self.state_path, {**state, "updated_at": self._now(), "active_grants": remaining, "revoked_grants": revoked})
        return {"revoked": True, "grant": value}

    def model_compatibility(self, *, model_id: str, calibrator_id: str = "") -> dict[str, Any]:
        active = [dict(row) for row in self.inspect().get("active_grants") or [] if row.get("status") == "approved"]
        incompatible = [row.get("grant_id") for row in active if str(row.get("model_id") or "") != str(model_id or "") or
                        (calibrator_id and str(row.get("calibrator_id") or "") != str(calibrator_id))]
        return {"compatible": not incompatible, "incompatible_grant_ids": incompatible, "reapproval_required": bool(incompatible)}

    def _append(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("ab") as handle:
            handle.write((json.dumps(value, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
