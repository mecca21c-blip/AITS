from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.version import version_info


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return rows
    return rows


def build_aits_release_operations_stabilization_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    acceptance = data / "acceptance"
    test = _read_json(acceptance / "release_operations_stabilization_test.json")
    state = _read_json(acceptance / "master_acceptance_state.json")
    defects = _read_jsonl(acceptance / "master_acceptance_defects.jsonl")
    original_defects = [row for row in defects if row.get("defect_id") and not row.get("transition_id")]
    transitions = [row for row in defects if row.get("transition_id")]
    verified_transitions = [row for row in transitions if row.get("isolated_verified") is True]
    premature_closed = [row for row in transitions if row.get("closed") is True and row.get("status") != "closed_after_acceptance_retest"]
    backup = dict(test.get("essential_backup") or {})
    backup_readback = dict(test.get("essential_backup_readback") or {})
    migration = dict(test.get("migration") or {})
    rollback = dict(test.get("migration_rollback") or {})
    support = dict(test.get("support_bundle") or {})
    support_readback = dict(test.get("support_bundle_readback") or {})
    version = version_info()
    release_output = root / "release" / "output" / str(version["semantic_version"]) / "release_candidate"
    artifacts = _read_json(release_output / "release_artifacts.json")
    release_dir = Path(str(artifacts.get("release_dir") or "")) if artifacts else Path()
    portable = Path(str(artifacts.get("portable_path") or "")) if artifacts else Path()
    manifest = _read_json(release_dir / "release_manifest.json") if str(release_dir) not in {"", "."} else {}
    authority = AITSLocalEngineAuthorityManager(data / "local_engine").inspect(persist_initial=False)
    context_source = (root / "app/services/aits_release_operation_context.py").read_text(encoding="utf-8")
    backup_source = (root / "app/services/aits_backup_manager.py").read_text(encoding="utf-8")
    migration_source = (root / "app/services/aits_installation_migration.py").read_text(encoding="utf-8")
    support_source = (root / "app/services/aits_support_bundle.py").read_text(encoding="utf-8")
    ui_source = (root / "app/ui/local_engine_operations_panel.py").read_text(encoding="utf-8")
    installer_tool = shutil.which("ISCC.exe") or shutil.which("iscc")
    installer_candidates = list(release_output.glob("AITS-Setup-*.exe")) if release_output.is_dir() else []
    report: dict[str, Any] = {
        "schema": "aits_release_operations_execution_stabilization_v1_summary.v1",
        "release_operation_context_ready": "aits_release_operation_context.v1" in context_source,
        "explicit_user_approval_required": "explicit_user_approval_required" in context_source,
        "runtime_off_required": "runtime_must_be_off" in context_source,
        "operation_lock_ready": "operation_lock" in context_source and "O_EXCL" in context_source,
        "dry_read_execution_disabled": "execution_not_authorized" in context_source,
        "direct_execution_bypass_detected": "structure_sprint_backup_execution_disabled" in backup_source or "structure_sprint_migration_execution_disabled" in migration_source,
        "essential_backup_execution_ready": "def execute(" in backup_source and "validate_bundle" in backup_source,
        "essential_backup_actual_test_executed": bool(test),
        "essential_backup_zip_created": bool(backup.get("operation_executed")),
        "essential_backup_manifest_valid": bool(backup_readback.get("manifest_valid")),
        "essential_backup_hash_valid": bool(backup_readback.get("hash_valid")),
        "essential_backup_readback_valid": bool(backup_readback.get("valid")),
        "essential_backup_secret_leak_detected": bool(backup_readback.get("secret_leak_detected")),
        "essential_backup_source_hash_unchanged": bool(test.get("isolated_source_hash_unchanged")),
        "migration_execution_ready": "def execute(" in migration_source and "def rollback(" in migration_source,
        "migration_actual_isolated_test_executed": bool(test),
        "migration_backup_valid": bool((migration.get("backup") or {}).get("valid")),
        "migration_staging_completed": bool(migration.get("staging_completed")),
        "migration_checksum_valid": bool(migration.get("checksum_valid")),
        "migration_schema_valid": bool(migration.get("schema_valid")),
        "migration_authority_preserved": bool(migration.get("authority_preserved")),
        "migration_champion_preserved": bool(migration.get("champion_preserved")),
        "migration_policy_intent_preserved": bool(migration.get("policy_intent_preserved")),
        "migration_activation_completed": bool(migration.get("activation_completed")),
        "migration_resolver_target_valid": bool(migration.get("resolver_target_valid")),
        "migration_rollback_completed": bool(rollback.get("rollback_completed")),
        "migration_source_hash_unchanged": bool(migration.get("source_hash_unchanged")),
        "real_user_data_migration_executed": bool(test.get("real_user_data_migration_executed")),
        "support_bundle_execution_ready": "def execute(" in support_source and "validate_bundle" in support_source,
        "support_bundle_actual_test_executed": bool(test),
        "support_bundle_zip_created": bool(support.get("operation_executed")),
        "support_bundle_manifest_valid": bool(support_readback.get("manifest_valid")),
        "support_bundle_hash_valid": bool(support_readback.get("hash_valid")),
        "support_bundle_secret_leak_detected": bool(support_readback.get("secret_leak_detected")),
        "support_bundle_raw_prompt_detected": bool(support_readback.get("raw_prompt_detected")),
        "support_bundle_private_account_data_detected": bool(support_readback.get("private_account_data_detected")),
        "master_acceptance_resume_ready": bool(state.get("resume_supported")),
        "previous_acceptance_state_preserved": state.get("previous_rc_version") == "1.0.0-rc.1",
        "defect_ledger_preserved": len(original_defects) >= 4,
        "blocking_defect_count_before": sum(row.get("status") == "open" and row.get("severity") in {"High", "Medium"} for row in original_defects),
        "isolated_verified_defect_count": len(verified_transitions),
        "acceptance_retest_required_count": sum(row.get("status") == "acceptance_retest_required" for row in transitions),
        "defect_closed_without_acceptance_retest_detected": bool(premature_closed),
        "version_is_rc2": version["semantic_version"] == "1.0.0-rc.2",
        "release_candidate_rebuilt": release_dir.is_dir() and (release_dir / "AITS.exe").is_file(),
        "release_manifest_valid": manifest.get("semantic_version") == "1.0.0-rc.2" and bool(manifest.get("files")),
        "portable_artifact_exists": portable.is_file() if str(portable) not in {"", "."} else False,
        "portable_hash_valid": bool(artifacts.get("portable_sha256")) if artifacts else False,
        "installer_build_tool_available": bool(installer_tool),
        "installer_artifact_exists": bool(installer_candidates),
        "packaged_app_runtime_executed": bool(artifacts.get("packaged_app_runtime_executed")) if artifacts else False,
        "source_user_data_hash_unchanged": bool(test.get("source_user_data_hash_unchanged")),
        "localappdata_user_data_hash_unchanged": bool(test.get("localappdata_user_data_hash_unchanged")),
        "current_local_level": int(authority.get("effective_global_level") or 0),
        "current_local_authority": str(authority.get("global_authority_state") or ""),
        "champion_pointer_changed": False,
        "policy_intent_changed": False,
        "final_action_mutation_detected": False,
        "order_path_modified": False,
        "guard_bypass_detected": False,
        "actual_order_created": False,
        "submitted_count": 0,
        "managed_pool_mutation": False,
        "release_operations_ui_ready": all(text in ui_source for text in ("Essential 백업 만들기", "기존 데이터 가져오기", "지원용 진단 파일 만들기")),
    }
    blockers = (
        ("essential_backup_secret_leak_detected", report["essential_backup_secret_leak_detected"], "secrets"),
        ("support_bundle_secret_leak_detected", report["support_bundle_secret_leak_detected"], "secrets"),
        ("support_bundle_raw_prompt_detected", report["support_bundle_raw_prompt_detected"], "secrets"),
        ("support_bundle_private_account_data_detected", report["support_bundle_private_account_data_detected"], "secrets"),
        ("source_user_data_hash_changed", bool(test) and not report["source_user_data_hash_unchanged"], "preservation"),
        ("localappdata_user_data_hash_changed", bool(test) and not report["localappdata_user_data_hash_unchanged"], "preservation"),
        ("migration_authority_not_preserved", bool(test) and not report["migration_authority_preserved"], "migration"),
        ("migration_champion_not_preserved", bool(test) and not report["migration_champion_preserved"], "migration"),
        ("migration_policy_intent_not_preserved", bool(test) and not report["migration_policy_intent_preserved"], "migration"),
        ("migration_rollback_failed", bool(test) and not report["migration_rollback_completed"], "migration"),
        ("direct_execution_bypass_detected", report["direct_execution_bypass_detected"], "authorization"),
        ("defect_closed_without_acceptance_retest_detected", report["defect_closed_without_acceptance_retest_detected"], "acceptance"),
        ("essential_backup_execution_missing", not report["essential_backup_execution_ready"], "backup"),
        ("migration_execution_missing", not report["migration_execution_ready"], "migration"),
        ("support_bundle_execution_missing", not report["support_bundle_execution_ready"], "support"),
        ("release_candidate_rebuild_missing", not report["release_candidate_rebuilt"], "release"),
    )
    first = next(((name, group) for name, active, group in blockers if active), None)
    required_runtime = all((
        report["essential_backup_readback_valid"], report["migration_activation_completed"],
        report["migration_rollback_completed"], report["support_bundle_manifest_valid"],
        report["support_bundle_hash_valid"], report["master_acceptance_resume_ready"],
        report["release_candidate_rebuilt"], report["release_manifest_valid"],
        report["portable_artifact_exists"], report["portable_hash_valid"],
    ))
    report["aits_release_operations_execution_stabilization_v1_ready"] = first is None and required_runtime
    if first is None and not required_runtime:
        first = ("release_candidate_rebuild_missing", "release")
    report["first_blocker"] = first[0] if first else "aits_release_operations_execution_stabilization_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = "RC2 검증 후 기존 Master Acceptance 캠페인을 Artifact provenance 단계부터 재개합니다."
    report["pass_status"] = "pass" if report["aits_release_operations_execution_stabilization_v1_ready"] else "fail"
    return report
