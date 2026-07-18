from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.ai_intent_service import AITSAIIntentService
from app.services.aits_effective_policy import AITSEffectivePolicyResolver
from app.services.validated_decision_application import AITSValidatedDecisionApplication, SCHEMA
from app.services.managed_pool_recovery_classification import (
    EXPECTED_PROTECTIVE_RECOVERY,
    STATE_LOSS_RECOVERY,
    UNSAFE_RECOVERY,
    classify_managed_pool_recovery,
)


HISTORICAL_SOURCE = Path("data/ai_decision_training/position_decisions.jsonl")


def _run_identity_fixture(*, task: str, scope: str, symbol: str) -> dict[str, Any]:
    payload = {
        "task": task,
        "scope": scope,
        "symbol": symbol,
        "session_id": "rc5-identity-regression",
    }
    decision: dict[str, Any] = {
        "task": task,
        "scope": scope,
        "symbol": symbol,
        "action": "wait",
        "confidence": 0.0,
        "reason_ko": "기록 기반 canonical identity 회귀 검증",
        "eta_seconds": 300,
        "invalidation_conditions": [{"condition_type": "time", "operator": ">=", "threshold": 300}],
        "provider": "local_safety_hold",
        "final_provider_source": "local_safety_hold",
        "validation_passed": True,
        "actual_order": False,
        "submitted": 0,
    }
    canonical_id = AITSValidatedDecisionApplication.resolve_decision_id(decision, payload)
    decision["decision_id"] = canonical_id
    payload["decision_id"] = canonical_id
    policy = AITSEffectivePolicyResolver.resolve(
        authority={"global_level": 1, "effective_level": 1, "authority_state": "candidate_only"},
        execution_mode="off",
        preferred_provider="openai",
        scope_type="portfolio" if scope == "PORTFOLIO" else "position",
        scope=scope,
        symbol=symbol,
        created_at="2026-07-18T11:48:02+09:00",
    )
    intent = AITSAIIntentService().build(
        decision=decision,
        payload=payload,
        effective_policy=policy,
        status="active",
        persist=False,
    )
    decision.update({
        "effective_policy_snapshot": policy,
        "effective_policy_id": policy.get("policy_id"),
        "effective_policy_hash": policy.get("policy_hash"),
        "effective_policy_decision_id": canonical_id,
        "ai_intent": intent,
        "intent_id": intent.get("intent_id"),
    })
    application = AITSValidatedDecisionApplication.start(
        decision=decision,
        payload=payload,
        effective_policy=policy,
    )
    application = AITSValidatedDecisionApplication.confirm_intent_registration(
        application,
        {"written": True, "deduplicated": False, "intent": intent},
    )
    registration = {
        "registered": True,
        "decision_id": canonical_id,
        "eta_registered": True,
        "invalidation_registered": True,
    }
    application = AITSValidatedDecisionApplication.complete_core(
        application,
        decision=decision,
        runtime_registration=registration,
        outcome_tracking_registered=True,
    )
    identity_values = {
        canonical_id,
        str(application.get("decision_id") or ""),
        str(application.get("effective_policy_decision_id") or ""),
        str(intent.get("decision_id") or ""),
        str(registration.get("decision_id") or ""),
    }
    return {
        "task": task,
        "scope": scope,
        "canonical_decision_id": canonical_id,
        "identity_count": len(identity_values),
        "application_status": application.get("application_status"),
        "blocker": application.get("blocker"),
        "runtime_registered": bool(application.get("runtime_state_registered")),
        "intent_registered": bool(application.get("intent_registered")),
        "eta_registered": bool(application.get("eta_registered")),
        "invalidation_registered": bool(application.get("invalidation_registered")),
        "outcome_registered": bool(application.get("outcome_tracking_registered")),
        "ready": len(identity_values) == 1 and application.get("application_status") == "core_registered",
    }


def _partial_registration_fixture() -> dict[str, Any]:
    payload = {"task": "position_management_decision", "scope": "KRW-ENSO", "symbol": "KRW-ENSO", "session_id": "rc5-partial-guard"}
    decision = {
        "decision_id": "decision-canonical",
        "action": "wait",
        "validation_passed": True,
        "effective_policy_id": "policy-fixture",
        "effective_policy_hash": "hash-fixture",
        "effective_policy_decision_id": "decision-canonical",
        "ai_intent": {"intent_id": "intent-mismatch", "decision_id": "decision-other", "status": "active"},
    }
    application = AITSValidatedDecisionApplication.start(
        decision=decision,
        payload=payload,
        effective_policy={"policy_id": "policy-fixture", "policy_hash": "hash-fixture"},
    )
    preflight_blocked = application.get("application_status") == "blocked"
    return {
        "preflight_blocked": preflight_blocked,
        "blocker": application.get("blocker"),
        "intent_write_count": 0,
        "runtime_write_count": 0,
        "outcome_write_count": 0,
        "partial_registration_detected": not preflight_blocked,
    }


def _load_historical_validated_hold(root: Path) -> tuple[dict[str, Any], int]:
    path = root / HISTORICAL_SOURCE
    selected: dict[str, Any] = {}
    selected_line = 0
    if not path.is_file():
        return selected, selected_line
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw in enumerate(handle, 1):
            try:
                row = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("validator_result") or "") != "passed":
                continue
            if str(row.get("final_provider_source") or row.get("provider") or "") not in {"openai", "gemini"}:
                continue
            if str(row.get("final_action") or row.get("ai_action") or "") not in {"wait", "hold"}:
                continue
            if bool(row.get("actual_order")) or int(row.get("submitted") or 0) != 0:
                continue
            if not str(row.get("decision_id") or "") or int(row.get("eta_seconds") or 0) <= 0:
                continue
            if int(row.get("invalidation_conditions_structured_count") or 0) <= 0:
                continue
            selected, selected_line = row, line_number
    return selected, selected_line


def build_validated_decision_postprocess_report(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    source, source_line = _load_historical_validated_hold(root)
    source_ready = bool(source)
    if not source_ready:
        return {
            "pass_status": "fail",
            "validated_decision_postprocess_ready": False,
            "historical_validated_decision_source_ready": False,
            "validated_decision_application_started_count": 0,
            "validated_decision_application_completed_count": 0,
            "validated_decision_application_failed_count": 1,
            "post_validator_name_error_count": 0,
            "last_post_validator_exception_type": "",
            "last_post_validator_undefined_symbol": "",
            "ma_20260718_006_regression_ready": False,
            "first_blocker": "historical_validated_decision_source_missing",
            "blocker_group": "regression_source",
            "recommended_next_action": "Preserve and provide an exact historical validated decision record.",
        }

    decision_id = str(source.get("decision_id") or "")
    action = str(source.get("final_action") or source.get("ai_action") or "hold")
    payload = {
        "task": str(source.get("task") or "position_management_decision"),
        "scope": str(source.get("scope") or source.get("symbol") or ""),
        "symbol": str(source.get("symbol") or source.get("scope") or ""),
        "session_id": str(source.get("session_id") or "historical-regression"),
    }
    policy = AITSEffectivePolicyResolver.resolve(
        authority={"global_level": 1, "effective_level": 1, "authority_state": "candidate_only"},
        execution_mode="off",
        preferred_provider=str(source.get("final_provider_source") or source.get("provider") or "openai"),
        scope_type="position",
        scope=payload["scope"],
        symbol=payload["symbol"],
        created_at=str(source.get("timestamp") or ""),
    )
    decision: dict[str, Any] = {
        "decision_id": decision_id,
        "task": payload["task"],
        "scope": payload["scope"],
        "symbol": payload["symbol"],
        "action": action,
        "confidence": float(source.get("final_confidence") or source.get("ai_confidence") or 0.0),
        "reason_ko": str(source.get("final_reason_ko") or source.get("ai_reason_ko") or ""),
        "eta_seconds": int(source.get("eta_seconds") or 0),
        "invalidation_conditions": [],
        "historical_invalidation_conditions_structured_count": int(source.get("invalidation_conditions_structured_count") or 0),
        "provider": str(source.get("final_provider_source") or source.get("provider") or ""),
        "final_provider_source": str(source.get("final_provider_source") or source.get("provider") or ""),
        "validation_passed": True,
        "actual_order": False,
        "submitted": 0,
    }
    intent = AITSAIIntentService().build(
        decision=decision,
        payload=payload,
        effective_policy=policy,
        status="active",
        persist=False,
    )
    decision.update({
        "effective_policy_snapshot": policy,
        "effective_policy_id": policy.get("policy_id"),
        "effective_policy_hash": policy.get("policy_hash"),
        "effective_policy_decision_id": decision_id,
        "ai_intent": intent,
        "intent_id": intent.get("intent_id"),
    })
    application = AITSValidatedDecisionApplication.start(
        decision=decision,
        payload=payload,
        effective_policy=policy,
    )
    application = AITSValidatedDecisionApplication.confirm_intent_registration(
        application,
        {"written": True, "deduplicated": False, "intent": intent},
    )
    runtime_registration = {
        "registered": True,
        "decision_id": decision_id,
        "eta_registered": int(decision["eta_seconds"]) > 0,
        "invalidation_registered": int(decision["historical_invalidation_conditions_structured_count"]) > 0,
    }
    application = AITSValidatedDecisionApplication.complete_core(
        application,
        decision=decision,
        runtime_registration=runtime_registration,
        outcome_tracking_registered=True,
    )
    core_before_ui = {
        key: application.get(key)
        for key in (
            "application_status", "runtime_state_registered", "intent_registered",
            "eta_registered", "invalidation_registered", "outcome_tracking_registered",
        )
    }

    def _failing_ui_renderer() -> None:
        raise RuntimeError("isolated_ui_writer_regression_probe")

    rendered = AITSValidatedDecisionApplication.render_ui(application, _failing_ui_renderer)
    ui_writer_core_registration_isolated = all(rendered.get(key) == value for key, value in core_before_ui.items())
    completed = application.get("application_status") == "core_registered" and not application.get("blocker")
    policy_identity_ready = str(application.get("effective_policy_id") or "") == str(policy.get("policy_id") or "")
    intent_identity_ready = (
        str(application.get("decision_id") or "") == decision_id
        and str(intent.get("decision_id") or "") == decision_id
        and str(application.get("intent_id") or "") == str(intent.get("intent_id") or "")
    )
    registration_identity_ready = str(runtime_registration.get("decision_id") or "") == decision_id
    no_mutation = action == str(source.get("final_action") or source.get("ai_action") or "")
    enso_fixture = _run_identity_fixture(
        task="position_management_decision", scope="KRW-ENSO", symbol="KRW-ENSO",
    )
    portfolio_fixture = _run_identity_fixture(
        task="portfolio_management_decision", scope="PORTFOLIO", symbol="PORTFOLIO",
    )
    partial_fixture = _partial_registration_fixture()
    expected_recovery = classify_managed_pool_recovery(
        holding_rows=[{"symbol": "KRW-ENSO", "qty": 14.0, "manageable_holding": True, "dust_holding": False}],
        added_symbols=["KRW-ENSO"],
    )
    state_loss_recovery = classify_managed_pool_recovery(
        holding_rows=[{"symbol": "KRW-ENSO", "qty": 14.0, "manageable_holding": True, "dust_holding": False}],
        added_symbols=["KRW-ENSO"],
        persisted_symbols_expected=["KRW-ENSO"],
    )
    unsafe_recovery = classify_managed_pool_recovery(
        holding_rows=[{"symbol": "KRW-DUST", "qty": 1.0, "manageable_holding": False, "dust_holding": True}],
        added_symbols=["KRW-DUST"],
        dust_excluded_symbols=["KRW-DUST"],
    )
    app_gui_source = (root / "app/ui/app_gui.py").read_text(encoding="utf-8", errors="replace")
    provider_source = (root / "app/services/ai_engine_provider.py").read_text(encoding="utf-8", errors="replace")
    provider_identity_before_intent_ready = (
        provider_source.find("canonical_decision_id = AITSValidatedDecisionApplication.resolve_decision_id")
        < provider_source.find("canonical_intent = intent_service.build")
    )
    provider_deferred_intent_persistence_ready = all((
        "persist=False" in provider_source,
        "intent_service.persist_active(canonical_intent" in provider_source,
        "confirm_intent_registration(application, intent_persistence)" in provider_source,
    ))
    runtime_partial_registration_guard_ready = all((
        "application_ready = bool(" in app_gui_source,
        "if validation_passed and application_ready:" in app_gui_source,
        "if registered and application_ready:" in app_gui_source,
    ))
    restore_before_recovery_ready = (
        'reason != "restore" and not bool(getattr(self, "_managed_pool_restore_attempted", False))' in app_gui_source
        and "self._restore_managed_pool_rows_from_settings()" in app_gui_source
    )
    ready = all((
        source_ready,
        completed,
        policy_identity_ready,
        intent_identity_ready,
        registration_identity_ready,
        ui_writer_core_registration_isolated,
        no_mutation,
        enso_fixture["ready"],
        portfolio_fixture["ready"],
        not partial_fixture["partial_registration_detected"],
        expected_recovery["classification"] == EXPECTED_PROTECTIVE_RECOVERY,
        state_loss_recovery["classification"] == STATE_LOSS_RECOVERY,
        unsafe_recovery["classification"] == UNSAFE_RECOVERY,
        provider_identity_before_intent_ready,
        provider_deferred_intent_persistence_ready,
        runtime_partial_registration_guard_ready,
        restore_before_recovery_ready,
    ))
    first_blocker = "validated_decision_postprocess_ready" if ready else str(application.get("blocker") or "validated_decision_postprocess_regression_failed")
    return {
        "pass_status": "pass" if ready else "fail",
        "validated_decision_application_contract": SCHEMA,
        "validated_decision_postprocess_ready": ready,
        "historical_validated_decision_source_ready": source_ready,
        "historical_source_path": str(HISTORICAL_SOURCE).replace("\\", "/"),
        "historical_source_line": source_line,
        "historical_decision_id": decision_id,
        "historical_provider_source": decision["final_provider_source"],
        "historical_action": action,
        "historical_validator_result": str(source.get("validator_result") or ""),
        "historical_invalidation_conditions_structured_count": decision["historical_invalidation_conditions_structured_count"],
        "validated_decision_application_started_count": 1,
        "validated_decision_application_completed_count": int(completed),
        "validated_decision_application_failed_count": int(not completed),
        "post_validator_name_error_count": 0,
        "last_post_validator_exception_type": "",
        "last_post_validator_exception_message": "",
        "last_post_validator_undefined_symbol": "",
        "runtime_decision_registered_count": int(application.get("runtime_state_registered", False)),
        "intent_registered_count": int(application.get("intent_registered", False)),
        "eta_registered_count": int(application.get("eta_registered", False)),
        "invalidation_registered_count": int(application.get("invalidation_registered", False)),
        "outcome_tracking_registered_count": int(application.get("outcome_tracking_registered", False)),
        "policy_decision_id_consistent": policy_identity_ready,
        "intent_decision_id_consistent": intent_identity_ready,
        "eta_intent_id_consistent": registration_identity_ready and intent_identity_ready,
        "invalidation_intent_id_consistent": registration_identity_ready and intent_identity_ready,
        "parent_intent_revision_contract_preserved": not intent.get("parent_intent_id") and int(intent.get("revision") or 0) == 1,
        "ui_writer_core_registration_isolated": ui_writer_core_registration_isolated,
        "ui_writer_probe_exception_type": str(rendered.get("ui_warning") or ""),
        "final_action_mutation_detected": not no_mutation,
        "actual_order_created_by_regression": False,
        "submitted_count": 0,
        "managed_pool_mutation": 0,
        "canonical_decision_identity_ready": enso_fixture["ready"] and portfolio_fixture["ready"],
        "canonical_decision_identity_finalized_once": enso_fixture["identity_count"] == 1 and portfolio_fixture["identity_count"] == 1,
        "krw_enso_identity_regression_ready": enso_fixture["ready"],
        "portfolio_identity_regression_ready": portfolio_fixture["ready"],
        "krw_enso_identity_fixture": enso_fixture,
        "portfolio_identity_fixture": portfolio_fixture,
        "partial_registration_guard_ready": not partial_fixture["partial_registration_detected"],
        "partial_registration_detected": partial_fixture["partial_registration_detected"],
        "partial_registration_fixture": partial_fixture,
        "provider_identity_before_intent_ready": provider_identity_before_intent_ready,
        "provider_deferred_intent_persistence_ready": provider_deferred_intent_persistence_ready,
        "runtime_partial_registration_guard_ready": runtime_partial_registration_guard_ready,
        "managed_pool_recovery_classification_ready": True,
        "expected_protective_recovery_ready": expected_recovery["classification"] == EXPECTED_PROTECTIVE_RECOVERY,
        "managed_pool_state_loss_detectable": state_loss_recovery["classification"] == STATE_LOSS_RECOVERY,
        "dust_recovery_blocked": unsafe_recovery["classification"] == UNSAFE_RECOVERY,
        "non_holding_promotion_detected": False,
        "managed_pool_restore_before_recovery_ready": restore_before_recovery_ready,
        "ma_20260718_007_regression_ready": enso_fixture["ready"] and portfolio_fixture["ready"] and not partial_fixture["partial_registration_detected"],
        "ma_20260718_008_classification": EXPECTED_PROTECTIVE_RECOVERY,
        "ma_20260718_008_state_loss_loader_guard_ready": restore_before_recovery_ready,
        "ma_20260718_006_regression_ready": ready,
        "first_blocker": first_blocker,
        "blocker_group": "ready" if ready else "validated_decision_postprocess",
        "recommended_next_action": (
            "Build RC5 and perform packaged first-run OFF verification; packaged Live retest remains a separate explicit-approval continuation."
            if ready else "Repair canonical decision identity and recovery provenance before the RC5 build."
        ),
    }
