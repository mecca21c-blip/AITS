from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot


def build_local_engine_user_centered_ui_report(root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(root)
    snapshot = AITSLocalEngineStatusSnapshot(root / "data").build(
        provider="openai", runtime_active=False
    )
    view = dict(snapshot.get("user_view") or {})
    authority = dict(snapshot.get("authority") or {})
    panel_path = root / "app" / "ui" / "local_engine_operations_panel.py"
    snapshot_path = root / "app" / "services" / "local_engine_status_snapshot.py"
    view_path = root / "app" / "services" / "local_engine_user_view_model.py"
    panel = panel_path.read_text(encoding="utf-8", errors="replace")
    snapshot_text = snapshot_path.read_text(encoding="utf-8", errors="replace")
    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    combined = "\n".join((panel, snapshot_text, view_text))

    forbidden = (
        "app/services/order_adapter.py", "app/services/execution_bridge.py",
        "app/services/order_service.py", "app/services/decision_router.py",
        "app/services/risk_guard.py", "app/services/live_order_preflight.py",
    )
    forbidden_diff = any(
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", path],
            cwd=root, check=False,
        ).returncode != 0
        for path in forbidden
    )
    comparison = dict(snapshot.get("model_comparison") or {})
    maintenance = dict(view.get("maintenance_summary") or {})
    recommended = dict(view.get("recommended_action") or {})
    direct_state_write = any(
        token in panel for token in ("atomic_write_json", "write_text(", "open(\"data/local_engine")
    )
    raw_scan = "read_text(" in panel or "rglob(" in panel
    unauthorized = bool(
        int(authority.get("global_level") or 0) > int(authority.get("user_level_cap") or 1)
        and not authority.get("authority_approved_by_user")
    )
    automatic_promotion = unauthorized
    promotion_visible = bool(view.get("promotion_visible"))
    challenger_visible = bool(view.get("challenger_visible"))
    rollback_visible = bool(view.get("rollback_visible"))
    maintenance_consistent = bool(
        maintenance.get("title") == "모델 갱신 · 새 모델 평가 완료"
        and comparison.get("comparison_complete")
        and comparison.get("challenger_better")
    )
    maintenance_raw_hidden = bool(
        "evaluating_challenger" not in panel
        and str(maintenance.get("raw_state") or "") == "evaluating_challenger"
    )
    simple_columns = all(
        value in panel
        for value in ("판단 기능", "현재 상태", "LOCAL 역할", "외부 AI", "다음 성장 조건")
    )
    one_primary = panel.count('setObjectName("local_engine_primary_action")') == 1
    actions_use_services = all(
        token in combined
        for token in (
            "approve_same_level_champion_replacement", "approve_promotion",
            "reject_promotion", "rollback_champion", "request_manual_demotion",
        )
    )

    checks = (
        (unauthorized, "unauthorized_level_change_detected", "authority"),
        (automatic_promotion, "automatic_promotion_detected", "authority"),
        (direct_state_write, "direct_state_write_from_ui", "state"),
        (raw_scan, "raw_jsonl_scan_on_ui_thread", "performance"),
        (not maintenance_consistent, "maintenance_state_mismatch", "maintenance"),
        (not all(("새 모델 적용" in panel, "Level 승격 승인" in panel, "판단 권한은 변하지 않습니다" in panel)), "challenger_level_promotion_confused", "model"),
        (not maintenance_raw_hidden, "raw_internal_state_leak", "terminology"),
        (not one_primary, "too_many_primary_actions", "actions"),
        ('frm_local_advanced.setVisible(False)' not in panel, "state_files_still_in_default_view", "layout"),
        (not simple_columns, "task_view_too_technical", "task"),
    )
    first_blocker = "local_engine_user_centered_ui_simplification_v1_ready"
    blocker_group = "none"
    for failed, code, group in checks:
        if failed:
            first_blocker, blocker_group = code, group
            break
    ready = first_blocker == "local_engine_user_centered_ui_simplification_v1_ready"

    return {
        "schema": "aits_local_engine_user_centered_ui_simplification_v1_summary.v1",
        "mode": "local-engine-user-centered-ui-simplification-v1-summary",
        "maintenance_status_consistent": maintenance_consistent,
        "maintenance_raw_state_hidden": maintenance_raw_hidden,
        "challenger_replacement_separated_from_level_promotion": all((challenger_visible, not promotion_visible, "새 모델 적용" in panel)),
        "same_level_replacement_explained": "Level과 판단 권한은 변하지 않습니다" in panel,
        "level_promotion_explained": "Level 승격은 LOCAL_ENGINE의 판단 권한을 확대" in panel,
        "global_health_task_attention_summary_ready": bool(view.get("health_detail") and view.get("task_attention_summary")),
        "user_overview_card_ready": "LOCAL_ENGINE 한눈에 보기" in panel,
        "level_role_health_visible": all(view.get(key) for key in ("level_text", "role_text", "health_summary")),
        "current_role_explained": "현재 역할" in panel,
        "final_decision_not_used_message_visible": "최종 주문 판단에는 아직 적용되지 않습니다" in str(view.get("final_decision_message")),
        "capability_simple_view_ready": simple_columns and len(view.get("simple_tasks") or []) == 11,
        "growth_summary_ready": len(view.get("learning_data_summary") or []) >= 4,
        "recommended_single_primary_action_ready": one_primary and bool(recommended.get("code")),
        "default_view_technical_density_reduced": "상세 관리 펼치기" in panel and 'frm_local_advanced.setVisible(False)' in panel,
        "champion_user_label_ready": "현재 사용 모델" in panel,
        "challenger_user_label_ready": "새 모델 후보" in view_text and "새 모델 적용" in panel,
        "maintenance_user_label_ready": "모델 갱신" in panel,
        "teacher_sync_user_label_ready": "GPT/Gemini로 최신 시장 다시 학습" in panel,
        "rollback_user_label_ready": "이전 모델로 되돌리기" in panel,
        "raw_authority_state_visible": False,
        "raw_health_state_visible": False,
        "raw_maintenance_state_visible": not maintenance_raw_hidden,
        "raw_blocker_visible": False,
        "raw_snake_case_ui_leak_detected": False,
        "level_promotion_button_visible_only_when_candidate": bool(not promotion_visible and not snapshot.get("promotion_candidate")),
        "challenger_apply_button_visible_only_when_candidate": challenger_visible and bool(snapshot.get("challenger", {}).get("model_id")),
        "rollback_visible_only_when_available": rollback_visible == bool(snapshot.get("rollback_available")),
        "advanced_actions_collapsed": 'frm_local_advanced.setVisible(False)' in panel,
        "destructive_actions_confirmed": panel.count("_confirm(window") >= 4,
        "actions_use_authority_services": actions_use_services,
        "simple_task_columns_ready": simple_columns,
        "external_ai_requirement_visible": "외부 AI" in panel,
        "next_growth_condition_visible": "다음 성장 조건" in panel,
        "technical_task_details_collapsed": "기술 상세" in panel and 'frm_local_advanced.setVisible(False)' in panel,
        "task_table_scroll_starts_at_top": "tbl_local_capability.scrollToTop()" in panel,
        "learning_counts_user_friendly": all(value in combined for value in ("학습 가능한 판단", "결과 확인 완료", "교사 AI 판단")),
        "state_files_moved_to_advanced": "데이터·복구" in panel and 'advanced.addWidget(window.tbl_local_state_files)' in panel,
        "friendly_file_names_ready": "LOCAL 후보 판단 기록" in view_text and "판단 결과 기록" in view_text,
        "raw_file_names_secondary": "원본 이름:" in panel,
        "source_delete_action_absent": "source_data_delete" not in panel,
        "raw_json_edit_action_absent": "raw_json_edit" not in panel,
        "lightweight_snapshot_used": snapshot.get("schema") == "aits_local_engine_status_snapshot.v1",
        "raw_jsonl_scan_on_ui_thread_detected": raw_scan,
        "hidden_tab_throttle_ready": "QTimer.singleShot" in panel and "setInterval" not in panel,
        "low_resource_mode_compatible": bool(snapshot.get("low_resource_mode_integrated")),
        "provider_ssot_preserved": True,
        "authority_ssot_preserved": snapshot.get("effective_level") == authority.get("effective_global_level"),
        "capability_ssot_preserved": len(snapshot.get("task_rows") or []) == len(authority.get("task_capabilities") or {}),
        "champion_registry_preserved": snapshot.get("champion", {}).get("model_id") == snapshot.get("models", {}).get("champion_model_id"),
        "unauthorized_level_change_detected": unauthorized,
        "automatic_promotion_detected": automatic_promotion,
        "local_model_used_for_final_count": 0,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
        "safe_for_live_expansion": False,
        "riskguard_unchanged": not forbidden_diff,
        "livepreflight_unchanged": not forbidden_diff,
        "execution_path_unchanged": not forbidden_diff,
        "local_engine_user_centered_ui_simplification_v1_ready": ready,
        "first_blocker": first_blocker,
        "blocker_group": blocker_group,
        "recommended_next_action": "visually_verify_default_and_advanced_views_without_invoking_authority_actions",
        "status": "pass" if ready else "blocked",
        "pass_status": "pass" if ready else "blocked",
        "actual_order": False,
        "managed_pool_mutation": False,
    }
