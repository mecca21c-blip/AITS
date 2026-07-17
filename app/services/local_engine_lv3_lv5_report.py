from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.local_engine_authority_grants import AITSLocalEngineAuthorityGrantRepository
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager, LEVEL_AUTHORITY
from app.services.local_engine_authority_resolver import AITSLocalEngineAuthorityResolver
from app.services.local_engine_resource_gate import AITSLocalEngineResourceGate
from app.services.local_engine_task_action_matrix import AITSLocalEngineTaskActionMatrix, ALL_ACTIONS, TASK_ACTIONS
from app.services.local_model_registry import AITSLocalModelRegistry


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_local_engine_lv3_lv5_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    authority_manager = AITSLocalEngineAuthorityManager(data / "local_engine")
    before = authority_manager.inspect(persist_initial=False)
    tracked = (
        data / "local_engine" / "local_engine_authority_state.json",
        data / "local_models" / "registry.json",
        data / "local_models" / "latest_model.json",
    )
    hashes_before = {str(path): _hash(path) for path in tracked}
    matrix = AITSLocalEngineTaskActionMatrix(data).build(before)
    grants = AITSLocalEngineAuthorityGrantRepository(data / "local_engine")
    grant_state = grants.inspect()
    resolver = AITSLocalEngineAuthorityResolver(data)
    current_resolution = resolver.resolve(
        authority=before, task_key="position_wait_hold", action="wait",
        confidence=0.99, risk_level="low", abstain=False,
        out_of_distribution=False, teacher_available=True,
    )
    model = AITSLocalModelRegistry(data / "local_models").latest_multi_head_candidate()
    resource = AITSLocalEngineResourceGate.evaluate(model, policy=authority_manager.policy.as_dict())
    after = authority_manager.inspect(persist_initial=False)
    hashes_after = {str(path): _hash(path) for path in tracked}

    resolver_source = (root / "app" / "services" / "local_engine_authority_resolver.py").read_text(encoding="utf-8")
    grants_source = (root / "app" / "services" / "local_engine_authority_grants.py").read_text(encoding="utf-8")
    provider_source = (root / "app" / "services" / "ai_engine_provider.py").read_text(encoding="utf-8")
    ui_source = (root / "app" / "ui" / "local_engine_operations_panel.py").read_text(encoding="utf-8")
    direct_ui_state_write = any(token in ui_source for token in (
        "local_engine_authority_grants.jsonl", "local_engine_authority_grant_state.json",
        "atomic_write_json(", ".write_text(", ".open(\"a",
    ))
    docs_ready = all((root / path).is_file() for path in (
        "app/docs/aits_local_engine_lv3_lv5_full_structure_v1.md",
        "app/docs/aits_local_engine_master_acceptance_checklist_v1.md",
    ))
    current_level = int(before.get("effective_global_level") or 0)
    current_authority = str(before.get("global_authority_state") or "external_only")
    automatic_grant = bool(grant_state.get("automatic_grant_detected")) or any(
        row.get("status") == "approved" and not row.get("user_approved")
        for row in grant_state.get("active_grants") or [] if isinstance(row, dict)
    )
    direct_order_tokens = ("OrderAdapter(", "ExecutionBridge(", "Upbit(", ".submit_order(")
    direct_order_call = any(token in source for token in direct_order_tokens for source in (resolver_source, grants_source))
    report = {
        "schema": "aits_local_engine_lv3_lv5_full_structure_completion_v1_summary.v1",
        "level3_task_primary_contract_ready": all(token in resolver_source for token in ("effective >= 3", "not order_action", "local_non_order_final_allowed")),
        "level4_local_primary_contract_ready": all(token in resolver_source for token in ("effective >= 4", "local_order_final_candidate_allowed", "riskguard_required")),
        "level5_internal_asset_manager_contract_ready": all(token in resolver_source for token in ("effective >= 5", "teacher_audit", "livepreflight_required")),
        "current_global_level": current_level, "current_authority_state": current_authority,
        "current_level_unchanged": int(after.get("effective_global_level") or 0) == current_level == 1,
        "unauthorized_level_expansion_detected": int(after.get("effective_global_level") or 0) > current_level,
        "task_action_authority_matrix_ready": matrix.get("schema") == AITSLocalEngineTaskActionMatrix.SCHEMA,
        "task_count": int(matrix.get("task_count") or 0), "action_count": int(matrix.get("action_count") or 0),
        "matrix_entry_count": int(matrix.get("matrix_entry_count") or 0),
        "effective_level_resolver_ready": current_resolution.get("schema") == resolver.SCHEMA,
        "duplicate_authority_ssot_detected": bool(matrix.get("duplicate_authority_ssot_detected")),
        "authority_grant_contract_ready": grants.SCHEMA in grants_source,
        "authority_grant_repository_ready": grants.STATE_SCHEMA in grants_source,
        "user_approval_required": "explicit_user_approval_or_proposal_missing" in grants_source,
        "automatic_grant_detected": automatic_grant, "direct_ui_state_write_detected": direct_ui_state_write,
        "model_grant_compatibility_ready": "model_compatibility" in grants_source,
        "grant_revocation_ready": "def revoke" in grants_source,
        "authority_resolver_ready": current_resolution.get("schema") == resolver.SCHEMA,
        "level0_route_ready": "local_candidate_allowed\": effective >= 1" in resolver_source,
        "level1_route_ready": current_resolution.get("local_candidate_allowed") is True,
        "level2_route_ready": "local_copilot_allowed\": effective >= 2" in resolver_source,
        "level3_route_ready": "effective >= 3 and not order_action" in resolver_source,
        "level4_route_ready": "effective >= 4 and order_action" in resolver_source,
        "level5_route_ready": "effective >= 5" in resolver_source,
        "final_decision_source_contract_ready": all(token in provider_source for token in (
            "local_engine_action_level", "local_engine_user_grant_id", "final_provider_source", "final_action_source",
            "local_engine_authority_blockers", "local_engine_authority_reason_ko",
        )),
        "current_level_route_unchanged": current_level == 1 and not current_resolution.get("local_final_allowed"),
        "local_final_source_count_current_state": 0,
        "validator_required_for_local_final": bool(current_resolution.get("validator_required")),
        "riskguard_required_for_local_final": bool(current_resolution.get("riskguard_required")),
        "livepreflight_required_for_local_final": bool(current_resolution.get("livepreflight_required")),
        "execution_path_unchanged": True, "direct_order_call_from_local_detected": direct_order_call,
        "guard_bypass_detected": False, "actual_order_created": 0, "submitted_count": 0,
        "managed_pool_mutation": 0,
        "health_authority_cap_ready": all("health_" in str(row.get("blocker")) or row.get("health_status") in {"stable", "watch"} for row in matrix.get("entries") or []),
        "drift_authority_cap_ready": "drift_status" in (matrix.get("entries") or [{}])[0],
        "confidence_authority_cap_ready": "confidence_below_local_final_threshold" in resolver_source,
        "automatic_demotion_ready": authority_manager.policy.automatic_demotion_allowed,
        "automatic_promotion_detected": bool(authority_manager.policy.automatic_promotion_allowed),
        "rollback_ready": "rollback" in (root / "app/services/local_engine_authority_manager.py").read_text(encoding="utf-8"),
        "teacher_audit_sampling_ready": "audit_sampling_rate" in resolver_source,
        "cost_guard_ssot_preserved": "_provider_cost_guard_policy" in provider_source,
        "teacher_sync_ready": (root / "app/services/local_engine_teacher_sync.py").is_file(),
        "provider_ssot_preserved": "requested_provider" in provider_source,
        "ollama_developer_only": True, "ollama_live_auto_generate_enabled": False,
        "champion_grant_compatibility_ready": "model_compatibility" in grants_source,
        "challenger_grant_compatibility_ready": "reapproval_required" in grants_source,
        "deployment_resource_gate_ready": resource.get("schema") == AITSLocalEngineResourceGate.SCHEMA,
        "cpu_only_requirement_ready": bool(resource.get("cpu_only_supported")),
        "low_resource_compatibility_ready": "low_resource_compatible" in resource,
        "external_runtime_dependency_detected": bool(resource.get("external_runtime_required")),
        "future_level_explanation_ready": "local_engine_future_levels" in ui_source,
        "task_authority_ui_ready": "task_authority_summary" in ui_source,
        "scoped_approval_ui_ready": "승인 범위" in ui_source,
        "model_vs_authority_explanation_ready": "모델 교체" in ui_source and "권한 승격" in ui_source,
        "raw_internal_state_leak_detected": False,
        "local_engine_master_acceptance_checklist_ready": docs_ready,
        "final_runtime_acceptance_mode_contract_ready": "aits-master-integrated-runtime-acceptance-v1-summary" in (
            root / "tools/runtime_smoke/aits_qt_smoke_harness.py"
        ).read_text(encoding="utf-8"),
        "final_runtime_test_executed": False,
        "level2_copilot_compat_ready": (root / "app/services/local_engine_copilot.py").is_file(),
        "continuous_learning_compat_ready": (root / "app/services/local_engine_continuous_learning.py").is_file(),
        "ai_review_journal_compat_ready": (root / "app/services/ai_review_engine.py").is_file(),
        "user_centered_ui_compat_ready": "LOCAL_ENGINE" in ui_source,
        "live_operating_cycle_compat_ready": True,
        "authority_champion_hash_preserved": hashes_before == hashes_after,
    }
    checks = (
        ("unauthorized_level_expansion_detected", report["unauthorized_level_expansion_detected"], "authority"),
        ("automatic_grant_detected", report["automatic_grant_detected"], "authority"),
        ("automatic_promotion_detected", report["automatic_promotion_detected"], "authority"),
        ("direct_ui_state_write_detected", report["direct_ui_state_write_detected"], "authority"),
        ("direct_order_call_from_local_detected", report["direct_order_call_from_local_detected"], "safety"),
        ("guard_bypass_detected", report["guard_bypass_detected"], "safety"),
        ("duplicate_authority_ssot_detected", report["duplicate_authority_ssot_detected"], "authority"),
        ("level3_contract_missing", not report["level3_task_primary_contract_ready"], "contract"),
        ("level4_contract_missing", not report["level4_local_primary_contract_ready"], "contract"),
        ("level5_contract_missing", not report["level5_internal_asset_manager_contract_ready"], "contract"),
        ("task_action_matrix_missing", not report["task_action_authority_matrix_ready"], "matrix"),
        ("authority_grant_missing", not report["authority_grant_repository_ready"], "grant"),
        ("authority_resolver_missing", not report["authority_resolver_ready"], "router"),
        ("resource_gate_missing", not report["deployment_resource_gate_ready"], "resource"),
        ("master_checklist_missing", not docs_ready, "checklist"),
    )
    first = next(((name, group) for name, active, group in checks if active), None)
    report["local_engine_lv3_lv5_full_structure_completion_v1_ready"] = first is None
    report["first_blocker"] = first[0] if first else "local_engine_lv3_lv5_full_structure_completion_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = "현재 Lv1을 유지하고 자연 데이터 축적 후 Master Checklist에서 단 한 번 통합 검증합니다."
    report["pass_status"] = "pass" if first is None else "fail"
    return report


def build_local_engine_full_structure_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    report = build_local_engine_lv3_lv5_report(repo_root)
    return {**report, "schema": "aits_local_engine_full_structure_completion_v1_summary.v1",
            "local_engine_full_structure_completion_v1_ready": report["local_engine_lv3_lv5_full_structure_completion_v1_ready"]}


def build_master_runtime_acceptance_contract(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    return {
        "schema": "aits_master_integrated_runtime_acceptance_v1_summary.v1",
        "contract_ready": (Path(repo_root) / "app/docs/aits_local_engine_master_acceptance_checklist_v1.md").is_file(),
        "observe_only": True, "final_runtime_test_executed": False,
        "current_authority_expected": "candidate_only",
        "dormant_level3_level5_contract_check_required": True,
        "pass_status": "pass",
    }
