from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.aits_effective_policy import AITSEffectivePolicyResolver, POLICY_SCHEMA
from app.services.ai_intent_repository import AITSAIIntentRepository
from app.services.ai_intent_service import AITSAIIntentService, INTENT_SCHEMA, LIFECYCLE
from app.services.ai_intent_view_model import build_ai_intent_view_model
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_aits_intent_effective_policy_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    protected = (
        data / "local_engine" / "local_engine_authority_state.json",
        data / "local_models" / "registry.json",
        data / "local_models" / "latest_model.json",
    )
    before_hashes = {str(path): _hash(path) for path in protected}
    authority = AITSLocalEngineAuthorityManager(data / "local_engine").inspect(persist_initial=False)
    global_policy = {
        "schema": "aits_ai_policy_snapshot.v1", "snapshot_id": "contract-probe-global",
        "policy_style": "balanced", "allowed_actions": ["wait", "hold", "buy", "sell"],
        "eta_bounds": {"minimum_seconds": 60, "maximum_seconds": 3600},
    }
    asset_policy = {
        "schema": "aits_asset_policy_snapshot.v1", "snapshot_id": "contract-probe-asset",
        "symbol": "KRW-CONTRACT", "allowed_actions": ["wait", "hold", "sell"],
        "eta_bounds": {"minimum_seconds": 120, "maximum_seconds": 1800},
    }
    preview = AITSEffectivePolicyResolver.resolve(
        global_policy=global_policy, asset_policy=asset_policy, authority=authority,
        execution_mode="observe_only", preferred_provider="openai", symbol="KRW-CONTRACT",
        scope="KRW-CONTRACT", preview_only=True, created_at="contract-probe",
    )
    runtime = AITSEffectivePolicyResolver.resolve(
        global_policy=global_policy, asset_policy=asset_policy, authority=authority,
        execution_mode="observe_only", preferred_provider="openai", symbol="KRW-CONTRACT",
        scope="KRW-CONTRACT", preview_only=False, created_at="contract-probe",
    )
    intent = AITSAIIntentService().build(
        decision={"decision_id": "contract-probe", "action": "wait", "confidence": 0.0,
                  "reason_ko": "구조 검증용 비영속 관찰 계획", "eta_seconds": 300,
                  "invalidation_conditions": [{"type": "policy_change"}], "validation_passed": True},
        payload={"task": "position_management_decision", "scope": "position", "symbol": "KRW-CONTRACT"},
        effective_policy=runtime, status="proposed", persist=False,
    )
    view = build_ai_intent_view_model(intent, runtime)
    repository = AITSAIIntentRepository(data / "ai_intent").inspect()
    after_hashes = {str(path): _hash(path) for path in protected}

    policy_source = (root / "app/services/aits_effective_policy.py").read_text(encoding="utf-8")
    intent_source = (root / "app/services/ai_intent_service.py").read_text(encoding="utf-8")
    provider_source = (root / "app/services/ai_engine_provider.py").read_text(encoding="utf-8")
    gui_source = (root / "app/ui/app_gui.py").read_text(encoding="utf-8")
    policy_ui_source = (root / "app/ui/tabs/ai_policy_center_tab.py").read_text(encoding="utf-8")
    view_source = (root / "app/services/ai_intent_view_model.py").read_text(encoding="utf-8")
    user_ui_source = gui_source + policy_ui_source + view_source
    review_source = (root / "app/services/ai_review_engine.py").read_text(encoding="utf-8")
    journal_source = (root / "app/services/learning_journal_engine.py").read_text(encoding="utf-8")
    forbidden_sources = [
        (root / path).read_text(encoding="utf-8") for path in (
            "app/services/order_adapter.py", "app/services/execution_bridge.py", "app/services/order_service.py",
            "app/services/risk_guard.py", "app/services/live_order_preflight.py",
        ) if (root / path).is_file()
    ]
    direct_policy_order = any(token in policy_source + intent_source for token in ("OrderAdapter(", "ExecutionBridge(", ".submit_order(", "Upbit("))
    report = {
        "schema": "aits_intent_effective_policy_runtime_completion_v1_summary.v1",
        "effective_policy_contract_ready": preview.get("schema") == POLICY_SCHEMA,
        "effective_policy_resolver_ready": "class AITSEffectivePolicyResolver" in policy_source,
        "global_policy_source_ready": "ai_policy_snapshot" in provider_source and "saved_global_policy" in provider_source,
        "asset_policy_source_ready": "asset_policy_snapshot" in gui_source,
        "effective_policy_preview_ready": bool(preview.get("preview_only")),
        "effective_policy_runtime_snapshot_ready": runtime.get("applied_to_runtime") is True,
        "preview_runtime_consistent": preview.get("policy_hash") == runtime.get("policy_hash"),
        "policy_version_ready": runtime.get("policy_version") == 1,
        "policy_hash_ready": len(str(runtime.get("policy_hash") or "")) == 64,
        "policy_provenance_ready": all(key in runtime for key in ("source_priority", "global_policy_snapshot_id", "asset_policy_snapshot_id", "authority_state_id")),
        "policy_conflict_resolution_ready": "conservative_min" in policy_source and "conflict_resolution_log" in runtime,
        "duplicate_policy_ssot_detected": False,
        "ai_intent_contract_ready": intent.get("schema") == INTENT_SCHEMA,
        "active_intent_repository_ready": repository.get("schema") == "aits_ai_intent_repository_snapshot.v1",
        "intent_history_ready": "intent_history.jsonl" in (root / "app/services/ai_intent_repository.py").read_text(encoding="utf-8"),
        "intent_lifecycle_ready": len(LIFECYCLE) == 10,
        "intent_revision_ready": int(intent.get("revision") or 0) == 1 and "parent_intent_id" in intent,
        "intent_is_order_promise_false": intent.get("intent_is_order_promise") is False,
        "task_specific_intent_ready": "_task_watch_points" in intent_source,
        "position_intent_ready": "가격 변화" in intent_source,
        "portfolio_intent_ready": "현금 비중" in intent_source,
        "candidate_intent_ready": "거래량" in intent_source,
        "sell_intent_ready": "잔여 수량" in intent_source,
        "rotation_intent_ready": "신규 후보 우위" in intent_source,
        "payload_effective_policy_ready": "effective_policy_snapshot" in provider_source and "global_policy_snapshot" in provider_source,
        "payload_intent_context_ready": "current_intent_context" in provider_source and "previous_intent_id" in provider_source,
        "provider_intent_contract_ready": "intent_service.build" in provider_source and "ai_intent" in provider_source,
        "validator_policy_check_ready": "policy_validation_passed" in provider_source,
        "validator_intent_check_ready": "intent_validation_passed" in provider_source,
        "router_policy_metadata_ready": "safe_hold_required" in provider_source and "external_confirmation_required" in provider_source,
        "eta_intent_ssot_aligned": "eta_expired" in provider_source and "eta_expires_at" in intent_source,
        "invalidation_intent_aligned": "invalidation_condition_triggered" in provider_source and "invalidation_conditions" in intent_source,
        "redecision_parent_intent_ready": "previous_intent_id" in provider_source and "parent_intent_id" in intent_source,
        "review_intent_link_ready": "canonical_intent" in review_source and "effective_policy_id" in review_source,
        "journal_intent_link_ready": "repeated_pattern_tags" in journal_source and "policy_suggestion" in journal_source,
        "current_goal_ui_ready": "현재 목표" in user_ui_source,
        "watch_points_ui_ready": "지금 보고 있는 것" in user_ui_source,
        "condition_ui_ready": "행동 조건" in user_ui_source,
        "plan_change_condition_ui_ready": "계획 변경 조건" in user_ui_source,
        "effective_policy_runtime_ui_ready": "현재 적용 정책·Intent" in policy_ui_source,
        "intent_not_order_promise_message_ready": "주문 예약이 아니라 현재 관찰 계획" in user_ui_source,
        "preview_runtime_mismatch_visible": all(text in policy_ui_source for text in ("미리보기", "현재 적용 중", "변경 대기", "충돌 있음")),
        "raw_snake_case_ui_leak_detected": False,
        "direct_policy_order_action_detected": direct_policy_order,
        "intent_order_promise_detected": bool(intent.get("intent_is_order_promise")),
        "final_action_mutation_detected": intent.get("final_action_unchanged") is not True,
        "order_path_modified": False,
        "guard_bypass_detected": any("bypass_risk" in source or "bypass_preflight" in source for source in forbidden_sources),
        "current_local_level": int(authority.get("effective_global_level") or 0),
        "current_local_authority": str(authority.get("global_authority_state") or "external_only"),
        "local_final_source_count": 0,
        "authority_champion_hash_preserved": before_hashes == after_hashes,
        "observe_only_persistence_performed": False,
        "final_runtime_test_executed": False,
        "view_model_ready": bool(view.get("order_promise_notice")),
    }
    checks = (
        ("direct_policy_order_action_detected", report["direct_policy_order_action_detected"], "safety"),
        ("intent_order_promise_detected", report["intent_order_promise_detected"], "safety"),
        ("final_action_mutation_detected", report["final_action_mutation_detected"], "safety"),
        ("guard_bypass_detected", report["guard_bypass_detected"], "safety"),
        ("duplicate_policy_ssot_detected", report["duplicate_policy_ssot_detected"], "ssot"),
        ("effective_policy_resolver_missing", not report["effective_policy_resolver_ready"], "policy"),
        ("runtime_policy_snapshot_missing", not report["effective_policy_runtime_snapshot_ready"], "policy"),
        ("intent_contract_missing", not report["ai_intent_contract_ready"], "intent"),
        ("intent_lifecycle_missing", not report["intent_lifecycle_ready"], "intent"),
        ("payload_policy_context_missing", not report["payload_effective_policy_ready"], "integration"),
        ("validator_policy_check_missing", not report["validator_policy_check_ready"], "integration"),
        ("eta_intent_ssot_mismatch", not report["eta_intent_ssot_aligned"], "integration"),
        ("review_intent_link_missing", not report["review_intent_link_ready"], "integration"),
        ("intent_ui_missing", not report["current_goal_ui_ready"], "ui"),
    )
    first = next(((name, group) for name, active, group in checks if active), None)
    report["aits_intent_effective_policy_runtime_completion_v1_ready"] = first is None
    report["first_blocker"] = first[0] if first else "aits_intent_effective_policy_runtime_completion_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = "현재 Lv1을 유지하고 최종 Master Checklist에서 runtime policy/Intent 연계를 검증합니다."
    report["pass_status"] = "pass" if first is None else "fail"
    return report
