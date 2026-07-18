from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Callable, Mapping


SCHEMA = "aits_validated_decision_application.v1"


def _identity(decision: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    existing = str(decision.get("decision_id") or decision.get("response_id") or payload.get("decision_id") or "")
    if existing:
        return existing
    digest_source = {
        "task": payload.get("task"),
        "scope": payload.get("scope"),
        "symbol": payload.get("symbol"),
        "session_id": payload.get("session_id"),
        "action": decision.get("action"),
        "reason_ko": decision.get("reason_ko"),
    }
    return "decision-" + hashlib.sha256(repr(sorted(digest_source.items())).encode("utf-8")).hexdigest()[:20]


class AITSValidatedDecisionApplication:
    """Post-validator application contract; it never routes or submits orders."""

    @staticmethod
    def resolve_decision_id(
        decision: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> str:
        """Resolve the canonical post-validator identity before any derived write."""
        return _identity(dict(decision or {}), dict(payload or {}))

    @classmethod
    def start(
        cls,
        *,
        decision: Mapping[str, Any],
        payload: Mapping[str, Any],
        effective_policy: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision, payload = dict(decision or {}), dict(payload or {})
        policy = dict(effective_policy or decision.get("effective_policy_snapshot") or {})
        intent = dict(decision.get("ai_intent") or {})
        decision_id = cls.resolve_decision_id(decision, payload)
        application_id = "application-" + hashlib.sha256(
            f"{decision_id}|{payload.get('task')}|{payload.get('scope')}|{payload.get('session_id')}".encode("utf-8")
        ).hexdigest()[:20]
        blockers: list[str] = []
        if not bool(decision.get("validation_passed")):
            blockers.append(str(decision.get("blocker") or "validated_decision_required"))
        if not str(policy.get("policy_id") or decision.get("effective_policy_id") or ""):
            blockers.append("effective_policy_link_missing")
        if not str(policy.get("policy_hash") or decision.get("effective_policy_hash") or ""):
            blockers.append("effective_policy_hash_missing")
        if not str(intent.get("intent_id") or decision.get("intent_id") or ""):
            blockers.append("intent_registration_missing")
        if intent and str(intent.get("decision_id") or "") != decision_id:
            blockers.append("intent_decision_id_mismatch")
        policy_decision_id = str(decision.get("effective_policy_decision_id") or decision_id)
        if policy_decision_id != decision_id:
            blockers.append("effective_policy_decision_id_mismatch")
        return {
            "schema": SCHEMA,
            "application_id": application_id,
            "decision_id": decision_id,
            "task": str(payload.get("task") or decision.get("task") or ""),
            "scope": str(payload.get("scope") or decision.get("scope") or payload.get("symbol") or ""),
            "symbol": str(payload.get("symbol") or decision.get("symbol") or ""),
            "session_id": str(payload.get("session_id") or decision.get("session_id") or ""),
            "provider_source": str(decision.get("final_provider_source") or decision.get("provider") or ""),
            "validated_action": str(decision.get("action") or "wait"),
            "validation_passed": bool(decision.get("validation_passed")),
            "effective_policy_id": str(policy.get("policy_id") or decision.get("effective_policy_id") or ""),
            "effective_policy_hash": str(policy.get("policy_hash") or decision.get("effective_policy_hash") or ""),
            "effective_policy_decision_id": policy_decision_id,
            "intent_id": str(intent.get("intent_id") or decision.get("intent_id") or ""),
            "intent_prepared": bool(intent.get("intent_id") and intent.get("status") in {"active", "revised"}),
            "intent_registered": False,
            "eta_registered": False,
            "invalidation_registered": False,
            "runtime_state_registered": False,
            "outcome_tracking_registered": False,
            "ui_status_rendered": False,
            "application_status": "blocked" if blockers else "started",
            "blocker": blockers[0] if blockers else "",
            "blockers": blockers,
            "exception_type": "",
            "actual_order": False,
            "submitted": 0,
            "final_action_unchanged": True,
        }

    @classmethod
    def confirm_intent_registration(
        cls,
        application: Mapping[str, Any],
        persistence_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Confirm the prepared Intent write before runtime/outcome registration."""
        result = deepcopy(dict(application or {}))
        persistence = dict(persistence_result or {})
        persisted_intent = persistence.get("intent") if isinstance(persistence.get("intent"), Mapping) else {}
        persisted = bool(persistence.get("written") or persistence.get("deduplicated"))
        same_identity = bool(
            persisted
            and str(persisted_intent.get("decision_id") or "") == str(result.get("decision_id") or "")
            and str(persisted_intent.get("intent_id") or "") == str(result.get("intent_id") or "")
        )
        result["intent_registered"] = same_identity
        blockers = list(result.get("blockers") or [])
        if not same_identity:
            blockers.append(str(persistence.get("blocker") or "intent_persistence_failed"))
        blockers = list(dict.fromkeys(filter(None, blockers)))
        result["blockers"] = blockers
        result["blocker"] = blockers[0] if blockers else ""
        result["application_status"] = "blocked" if blockers else "started"
        return result

    @classmethod
    def complete_core(
        cls,
        application: Mapping[str, Any],
        *,
        decision: Mapping[str, Any],
        runtime_registration: Mapping[str, Any],
        outcome_tracking_registered: bool,
    ) -> dict[str, Any]:
        result = deepcopy(dict(application or {}))
        registration = dict(runtime_registration or {})
        result["runtime_state_registered"] = bool(registration.get("registered"))
        result["eta_registered"] = bool(registration.get("eta_registered"))
        result["invalidation_registered"] = bool(registration.get("invalidation_registered"))
        result["outcome_tracking_registered"] = bool(outcome_tracking_registered)
        result["intent_registered"] = bool(result.get("intent_registered"))
        blockers = list(result.get("blockers") or [])
        if not result["runtime_state_registered"]:
            blockers.append(str(registration.get("blocker") or "runtime_decision_registration_missing"))
        if not result["intent_registered"]:
            blockers.append("intent_registration_missing")
        if int(float(decision.get("eta_seconds") or 0)) > 0 and not result["eta_registered"]:
            blockers.append("eta_registration_missing")
        if list(decision.get("invalidation_conditions") or []) and not result["invalidation_registered"]:
            blockers.append("invalidation_registration_missing")
        if not result["outcome_tracking_registered"]:
            blockers.append("outcome_tracking_registration_missing")
        blockers = list(dict.fromkeys(filter(None, blockers)))
        result["blockers"] = blockers
        result["blocker"] = blockers[0] if blockers else ""
        result["application_status"] = "blocked" if blockers else "core_registered"
        return result

    @staticmethod
    def render_ui(
        application: Mapping[str, Any],
        renderer: Callable[[], None],
    ) -> dict[str, Any]:
        result = deepcopy(dict(application or {}))
        try:
            renderer()
            result["ui_status_rendered"] = True
            if result.get("application_status") == "core_registered":
                result["application_status"] = "completed"
        except Exception as exc:
            result["ui_status_rendered"] = False
            result["ui_warning"] = type(exc).__name__
        return result
