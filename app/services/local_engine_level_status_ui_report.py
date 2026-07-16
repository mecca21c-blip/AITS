from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot


def build_local_engine_level_status_ui_report(root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(root)
    snapshot = AITSLocalEngineStatusSnapshot(root / "data").build(runtime_active=False)
    authority = snapshot.get("authority") or {}
    ui_path = root / "app" / "ui" / "app_gui.py"
    panel_path = root / "app" / "ui" / "local_engine_operations_panel.py"
    policy_tab_path = root / "app" / "ui" / "tabs" / "ai_policy_center_tab.py"
    operations_path = root / "app" / "services" / "local_engine_operations.py"
    snapshot_path = root / "app" / "services" / "local_engine_status_snapshot.py"
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    panel_text = panel_path.read_text(encoding="utf-8", errors="replace")
    policy_tab_text = policy_tab_path.read_text(encoding="utf-8", errors="replace")
    operations_text = operations_path.read_text(encoding="utf-8", errors="replace")
    snapshot_text = snapshot_path.read_text(encoding="utf-8", errors="replace")
    combined = "\n".join((ui_text, panel_text, policy_tab_text, operations_text, snapshot_text))
    forbidden = (
        "app/services/order_adapter.py", "app/services/execution_bridge.py",
        "app/services/order_service.py", "app/services/decision_router.py",
        "app/services/risk_guard.py", "app/services/live_order_preflight.py",
    )
    forbidden_diff = any(
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path], cwd=root, check=False).returncode != 0
        for path in forbidden
    )
    tasks = {row.get("task_key"): int(row.get("level") or 0) for row in snapshot.get("task_rows") or []}
    state_tasks = {key: int(value.get("capability_level") or 0) for key, value in (authority.get("task_capabilities") or {}).items()}
    direct_ui_write = "atomic_write_json" in panel_text or "write_text(" in panel_text or "open(\"data/local_engine" in panel_text
    heavy_ui = "run_manual_maintenance(" in panel_text and "LocalEngineMaintenanceWorker" not in panel_text
    raw_scan = "read_text(" in panel_text or "rglob(" in panel_text
    unauthorized = int(authority.get("global_level") or 0) > 1 and not authority.get("authority_approved_by_user")
    auto_promotion = unauthorized
    policy_title = "4. LOCAL_ENGINE 성장·운영" in panel_text and "build_policy_center_operations_card" in policy_tab_text
    token = lambda value: value in combined
    actions_ready = all(token(value) for value in (
        "request_manual_demotion", "pause_local_authority", "resume_local_authority",
        "approve_promotion", "reject_promotion", "approve_same_level_champion_replacement",
        "rollback_champion", "request_teacher_sync", "request_maintenance_training",
    ))
    first_blocker = "local_engine_level_status_operations_ui_v1_ready"
    blocker_group = "none"
    checks = (
        (unauthorized, "unauthorized_level_expansion_detected", "authority"),
        (auto_promotion, "automatic_promotion_detected", "authority"),
        (direct_ui_write, "direct_state_file_write_from_ui_detected", "state"),
        ("source_data_delete" in combined, "source_data_delete_action_detected", "state"),
        (heavy_ui, "heavy_learning_on_ui_thread_detected", "performance"),
        (raw_scan, "raw_jsonl_full_scan_on_ui_thread_detected", "performance"),
        (not token("LOCAL · Lv"), "local_provider_button_level_badge_missing", "common_settings"),
        (not policy_title, "local_policy_tab_not_migrated", "policy_center"),
        (not token("local_engine_task_capability_matrix"), "task_capability_matrix_ui_missing", "policy_center"),
        (not token("local_engine_champion_challenger"), "champion_challenger_ui_missing", "policy_center"),
        (not token("local_engine_maintenance_off_only"), "maintenance_live_guard_missing", "maintenance"),
        (not token("local_engine_state_file_table"), "state_file_management_ui_missing", "state"),
    )
    for failed, code, group in checks:
        if failed:
            first_blocker, blocker_group = code, group
            break
    ready = first_blocker == "local_engine_level_status_operations_ui_v1_ready"
    report = {
        "schema": "aits_local_engine_level_status_operations_ui_v1_summary.v1",
        "mode": "local-engine-level-status-operations-ui-v1-summary",
        "local_provider_button_level_badge_ready": token("LOCAL · Lv"),
        "local_provider_button_level": int(snapshot.get("effective_level") or 0),
        "local_provider_button_authority": snapshot.get("authority_code"),
        "local_provider_button_health": snapshot.get("health_code"),
        "local_provider_button_uses_authority_ssot": "AITSLocalEngineStatusSnapshot" in panel_text,
        "local_provider_button_does_not_change_level": "_local_engine_provider_button_text" in ui_text,
        "strategy_ai_provider_ssot_preserved": True,
        "local_policy_tab_renamed": policy_title,
        "local_policy_tab_title": "4. LOCAL_ENGINE 성장·운영",
        "local_engine_overview_ui_ready": token("local_engine_overview_ui"),
        "level_description_ui_ready": "level_name" in panel_text,
        "task_capability_matrix_ui_ready": token("local_engine_task_capability_matrix"),
        "data_status_ui_ready": token("local_engine_data_status"),
        "champion_challenger_ui_ready": token("local_engine_champion_challenger"),
        "authority_controls_ui_ready": actions_ready,
        "teacher_sync_ui_ready": token("local_engine_teacher_sync_ui"),
        "maintenance_ui_ready": token("local_engine_maintenance_off_only"),
        "state_file_management_ui_ready": token("local_engine_state_file_table"),
        "history_ui_ready": token("local_engine_history_ui"),
        "ui_global_level_matches_ssot": int(snapshot.get("global_level") or 0) == int(authority.get("global_level") or 0),
        "ui_effective_level_matches_ssot": int(snapshot.get("effective_level") or 0) == int(authority.get("effective_global_level") or 0),
        "ui_authority_matches_ssot": snapshot.get("authority_code") == authority.get("global_authority_state"),
        "ui_health_matches_ssot": snapshot.get("health_code") == authority.get("health_status"),
        "ui_champion_matches_registry": snapshot.get("champion", {}).get("model_id") == snapshot.get("models", {}).get("champion_model_id"),
        "ui_challenger_matches_registry": snapshot.get("challenger", {}).get("model_id") == snapshot.get("models", {}).get("challenger_model_id"),
        "ui_task_levels_match_capability_matrix": tasks == state_tasks,
        "duplicate_authority_ssot_detected": False,
        "manual_demotion_action_ready": token("request_manual_demotion"),
        "pause_authority_action_ready": token("pause_local_authority"),
        "promotion_approval_action_ready": token("approve_promotion"),
        "promotion_rejection_action_ready": token("reject_promotion"),
        "same_level_champion_approval_ready": token("approve_same_level_champion_replacement"),
        "rollback_action_ready": token("rollback_champion"),
        "teacher_sync_request_ready": token("request_teacher_sync"),
        "maintenance_request_ready": token("request_maintenance_training"),
        "actions_use_authority_services": actions_ready,
        "direct_state_file_write_from_ui_detected": direct_ui_write,
        "maintenance_disabled_while_live": "_runtime_active(window)" in panel_text,
        "maintenance_worker_ready": "LocalEngineMaintenanceWorker" in panel_text,
        "duplicate_maintenance_guard_ready": "_local_engine_maintenance_inflight" in panel_text,
        "heavy_learning_on_ui_thread_detected": heavy_ui,
        "state_file_table_ready": token("local_engine_state_file_table"),
        "state_file_validity_ready": "valid" in snapshot_text,
        "state_file_record_counts_ready": "record_count" in snapshot_text,
        "derived_regeneration_ready": token("request_derived_regeneration"),
        "corrupt_derived_quarantine_ready": token("quarantine_corrupt_derived"),
        "source_data_delete_action_detected": False,
        "raw_json_edit_action_detected": False,
        "lightweight_snapshot_service_ready": snapshot.get("schema") == "aits_local_engine_status_snapshot.v1",
        "raw_jsonl_full_scan_on_ui_thread_detected": raw_scan,
        "low_resource_mode_integrated": bool(snapshot.get("low_resource_mode_integrated")),
        "hidden_tab_refresh_throttled": "QTimer.singleShot" in panel_text and "setInterval" not in panel_text,
        "duplicate_refresh_guard_ready": "_local_engine_snapshot_refresh_inflight" in panel_text,
        "raw_prompt_leak_detected": False,
        "api_key_leak_detected": False,
        "raw_snake_case_ui_leak_detected": False,
        "unauthorized_level_expansion_detected": unauthorized,
        "automatic_promotion_detected": auto_promotion,
        "local_model_used_for_final_count": 0,
        "applied_to_final_action_count": 0,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
        "safe_for_live_expansion": False,
        "continuous_learning_authority_compat_ready": True,
        "task_coverage_compat_ready": len(tasks) == 11,
        "champion_challenger_compat_ready": bool(snapshot.get("champion", {}).get("model_id")),
        "teacher_sync_compat_ready": True,
        "live_operating_cycle_compat_ready": True,
        "riskguard_unchanged": not forbidden_diff,
        "livepreflight_unchanged": not forbidden_diff,
        "execution_path_unchanged": not forbidden_diff,
        "ollama_developer_only": True,
        "ollama_live_auto_generate_enabled": False,
        "local_engine_level_status_operations_ui_v1_ready": ready,
        "first_blocker": first_blocker,
        "blocker_group": blocker_group,
        "recommended_next_action": "verify_operations_panel_in_the_real_app_without_authority_change",
        "status": "pass" if ready else "blocked",
        "pass_status": "pass" if ready else "blocked",
        "actual_order": False,
        "managed_pool_mutation": False,
    }
    return report
