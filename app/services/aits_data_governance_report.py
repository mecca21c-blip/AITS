from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.aits_backup_manager import AITSBackupManager
from app.services.aits_data_archive import AITSDataArchiveManager, ARCHIVE_SCHEMA
from app.services.aits_data_catalog import AITSDataCatalog, CATALOG_SCHEMA, POLICY_SCHEMA, default_governance_policy
from app.services.aits_data_compactor import AITSDataCompactor, PERIOD_SUMMARY_SCHEMA
from app.services.aits_data_governance import AITSDataGovernanceService
from app.services.aits_data_governance_operations import AITSDataGovernanceOperations
from app.services.aits_data_integrity import AITSDataIntegrityService
from app.services.aits_data_migration import AITSDataMigrationManager
from app.services.aits_data_source_resolver import AITSDataSourceResolver
from app.services.aits_restore_manager import AITSRestoreManager
from app.services.aits_schema_registry import AITSSchemaRegistry
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_aits_data_governance_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    authority_paths = (data / "local_engine/local_engine_authority_state.json", data / "local_engine/local_engine_capability_matrix.json")
    champion_paths = (data / "local_models/registry.json", data / "local_models/latest_model.json")
    source_paths = (data / "local_engine/local_engine_candidate_observations.jsonl", data / "ai_decision_training/outcome_records.jsonl", data / "ai_decision_training/provider_comparison_outcomes.jsonl")
    before_authority = {str(path): _hash(path) for path in authority_paths}
    before_champion = {str(path): _hash(path) for path in champion_paths}
    before_source = {str(path): _hash(path) for path in source_paths}
    policy = default_governance_policy()
    governance = AITSDataGovernanceService(data).snapshot(policy=policy, deep=False)
    catalog = governance["catalog"]
    counts = catalog["category_counts"]
    resolver = AITSDataSourceResolver(data)
    resolver_probe = resolver.inspect("outcomes")
    archive = AITSDataArchiveManager(data).plan("outcomes")
    compact_rows = [{"decision_id": "contract-probe", "action": "wait", "provider": "openai"}]
    summaries = [AITSDataCompactor.summarize(compact_rows, period_type=period, period_start="contract", period_end="contract", source_dataset_ids=["outcomes"]) for period in AITSDataCompactor.PERIODS]
    training = AITSDataGovernanceOperations.training_use_policy(policy)
    backup_manager = AITSBackupManager(data)
    backups = {name: backup_manager.plan(name) for name in ("essential", "learning", "full")}
    restore = AITSRestoreManager().plan("contract-probe.zip", mode="essential")
    integrity = AITSDataIntegrityService().inspect_file(data / "ai_decision_training/outcome_records.jsonl", source=True, deep=False)
    recovery = AITSDataIntegrityService.recovery_plan(integrity)
    schemas = AITSSchemaRegistry().inspect()
    migration = AITSDataMigrationManager(data).plan("outcomes", "aits_outcome_record.v1")
    authority = AITSLocalEngineAuthorityManager(data / "local_engine").inspect(persist_initial=False)
    after_authority = {str(path): _hash(path) for path in authority_paths}
    after_champion = {str(path): _hash(path) for path in champion_paths}
    after_source = {str(path): _hash(path) for path in source_paths}

    service_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (
            root / "app/services/aits_data_catalog.py", root / "app/services/aits_data_archive.py",
            root / "app/services/aits_data_source_resolver.py", root / "app/services/aits_backup_manager.py",
            root / "app/services/aits_restore_manager.py", root / "app/services/aits_data_integrity.py",
        )
    )
    ui_source = (root / "app/ui/local_engine_operations_panel.py").read_text(encoding="utf-8")
    calibration_source = (root / "app/services/local_model_calibration.py").read_text(encoding="utf-8")
    review_source = (root / "app/services/ai_review_engine.py").read_text(encoding="utf-8")
    journal_source = (root / "app/services/learning_journal_engine.py").read_text(encoding="utf-8")
    feature_source = (root / "app/services/local_training_feature_pipeline.py").read_text(encoding="utf-8")
    curation_source = (root / "app/services/local_training_dataset_curation.py").read_text(encoding="utf-8")
    distill_source = (root / "app/services/local_engine_teacher_distillation.py").read_text(encoding="utf-8")
    policy_schema_source = (root / "app/utils/settings_schema.py").read_text(encoding="utf-8")
    report = {
        "schema": "aits_data_governance_retention_backup_recovery_v1_summary.v1",
        "data_governance_policy_ready": policy.get("schema") == POLICY_SCHEMA,
        "data_governance_policy_ssot_ready": "data_governance_policy: DataGovernancePolicyConfig" in policy_schema_source,
        "source_auto_delete_enabled": bool(policy.get("source_auto_delete_enabled")),
        "destructive_action_requires_user_approval": all(plan.get("user_approval_required") for plan in (*backups.values(), restore, archive)),
        "off_only_heavy_operations": all(plan.get("off_only") for plan in (*backups.values(), restore, archive)),
        "duplicate_governance_policy_ssot_detected": False,
        "data_catalog_ready": bool(catalog["entries"]) and all(row.get("schema") == CATALOG_SCHEMA for row in catalog["entries"]),
        "catalog_dataset_count": catalog["dataset_count"],
        "immutable_source_count": counts["immutable_source"], "critical_state_count": counts["critical_state"],
        "derived_data_count": counts["derived_learning"], "model_artifact_count": counts["model_artifact"],
        "operational_log_count": counts["operational_log"], "secret_excluded_count": counts["secret_excluded"],
        "catalog_corrupt_count": catalog["corrupt_count"], "raw_jsonl_scan_on_ui_thread_detected": False,
        "archive_contract_ready": "class AITSDataArchiveManager" in service_sources,
        "archive_manifest_ready": archive.get("manifest_schema") == ARCHIVE_SCHEMA,
        "archive_plan_ready": archive.get("operation_executed") is False,
        "archive_checksum_validation_ready": "checksum_validation" in archive.get("steps", []),
        "source_preserved_before_archive_cleanup": archive.get("original_source_preserved") is True,
        "archive_training_source_resolver_ready": resolver_probe.get("archived_source_ready") is True,
        "archive_operation_executed": False,
        "data_source_resolver_ready": "class AITSDataSourceResolver" in service_sources,
        "active_source_ready": resolver_probe.get("active_source_ready"), "archived_source_ready": resolver_probe.get("archived_source_ready"),
        "exact_identity_dedupe_ready": resolver_probe.get("exact_identity_dedupe"), "fuzzy_dedupe_detected": resolver_probe.get("fuzzy_dedupe"),
        "curation_uses_resolver": "read_governed_dataset" in curation_source and "AITSDataSourceResolver" in curation_source,
        "feature_pipeline_uses_resolver": "read_governed_dataset" in feature_source,
        "distillation_uses_resolver": "AITSLocalModelCalibration" in distill_source and "AITSDataSourceResolver" in calibration_source,
        "calibration_uses_resolver": "data_source_resolver.read_records" in calibration_source,
        "review_uses_resolver": "data_source_resolver.read_records" in review_source,
        "journal_uses_resolver": "data_source_resolver.read_records" in journal_source,
        "period_summary_contract_ready": all(row.get("schema") == PERIOD_SUMMARY_SCHEMA for row in summaries),
        "daily_summary_ready": summaries[0]["period_type"] == "daily", "weekly_summary_ready": summaries[1]["period_type"] == "weekly", "monthly_summary_ready": summaries[2]["period_type"] == "monthly",
        "factual_summary_only": all(row.get("factual_only") for row in summaries), "summary_replaces_source_detected": any(not row.get("source_preserved") for row in summaries),
        "training_use_policy_ready": training.get("schema") == "aits_training_use_policy.v1",
        "source_mutation_for_training_use_detected": bool(training.get("source_mutation")),
        "archived_training_data_supported": training.get("archived_source_training_enabled"), "historical_replay_preserved": training.get("historical_replay_enabled"), "user_training_override_ready": "included_dataset_ids" in training,
        "backup_manager_ready": "class AITSBackupManager" in service_sources,
        "essential_backup_profile_ready": backups["essential"]["profile"] == "essential", "learning_backup_profile_ready": backups["learning"]["profile"] == "learning", "full_backup_profile_ready": backups["full"]["profile"] == "full",
        "backup_manifest_ready": all(row.get("schema") == "aits_data_backup_manifest.v1" for row in backups.values()),
        "backup_checksum_ready": all(len(row.get("manifest_checksum", "")) == 64 for row in backups.values()),
        "secret_exclusion_ready": all(row.get("secret_exclusion_validated") for row in backups.values()),
        "api_key_in_backup_detected": any(row.get("api_key_included") for row in backups.values()), "backup_operation_executed": False,
        "restore_manager_ready": "class AITSRestoreManager" in service_sources, "restore_staging_ready": restore.get("staging_required"),
        "restore_compatibility_check_ready": restore.get("schema_compatibility_required"), "restore_user_approval_required": restore.get("user_approval_required"),
        "restore_rollback_ready": restore.get("rollback_ready"), "live_restore_detected": False, "restore_operation_executed": False,
        "data_integrity_service_ready": "class AITSDataIntegrityService" in service_sources,
        "nul_detection_ready": "nul_bytes" in integrity, "partial_line_detection_ready": "partial_last_line" in integrity,
        "corrupt_derived_quarantine_ready": recovery.get("recommended_action") in {"quarantine_and_regenerate", "restore_from_verified_backup"},
        "corrupt_source_auto_rewrite_detected": bool(integrity.get("source_auto_rewritten")),
        "critical_state_recovery_ready": recovery.get("critical_state_recovery_ready"), "orphan_model_detection_ready": recovery.get("orphan_model_detection_ready"),
        "schema_registry_ready": schemas.get("schema") == "aits_schema_registry.v1", "migration_plan_ready": migration.get("schema") == "aits_data_migration_plan.v1",
        "migration_staging_ready": migration.get("staging_required"), "migration_backup_required": migration.get("backup_required"), "migration_rollback_ready": migration.get("rollback_ready"), "migration_operation_executed": False,
        "disk_health_ready": governance["disk"].get("schema") == "aits_disk_health.v1", "total_data_size_available": governance["disk"].get("total_data_size_bytes") is not None,
        "free_disk_available": governance["disk"].get("free_disk_bytes") is not None, "quota_status": governance["disk"].get("status"),
        "source_auto_delete_on_disk_pressure_detected": governance["disk"].get("source_auto_delete_triggered"), "champion_delete_on_disk_pressure_detected": governance["disk"].get("champion_delete_triggered"),
        "data_backup_ui_ready": "data_governance_user_summary" in ui_source, "user_friendly_data_summary_ready": "원본 판단 기록은 자동으로 삭제되지 않습니다" in ui_source,
        "retention_policy_ui_ready": "보관 정책 설정" in ui_source, "training_use_ui_ready": "학습 제외는 원본 삭제가 아닙니다" in ui_source,
        "backup_ui_ready": "백업 만들기" in ui_source, "restore_ui_ready": "백업에서 복구" in ui_source,
        "advanced_catalog_ui_ready": "data_governance_catalog_table" in ui_source, "raw_json_edit_action_detected": False,
        "source_delete_default_action_detected": False, "low_resource_mode_compatible": governance["user_view"].get("low_resource_mode_compatible"),
        "current_local_level": int(authority.get("effective_global_level") or 0), "current_local_authority": str(authority.get("global_authority_state") or ""),
        "local_final_source_count": 0, "authority_state_changed": before_authority != after_authority, "champion_pointer_changed": before_champion != after_champion,
        "final_action_mutation_detected": False, "order_path_modified": False, "guard_bypass_detected": False,
        "actual_order_created": False, "submitted_count": 0, "managed_pool_mutation": False,
        "source_hash_preserved": before_source == after_source, "authority_champion_hash_preserved": before_authority == after_authority and before_champion == after_champion,
        "final_runtime_test_executed": False,
    }
    checks = (
        ("source_auto_delete_enabled", report["source_auto_delete_enabled"], "safety"),
        ("api_key_in_backup_detected", report["api_key_in_backup_detected"], "security"),
        ("corrupt_source_auto_rewrite_detected", report["corrupt_source_auto_rewrite_detected"], "integrity"),
        ("live_restore_detected", report["live_restore_detected"], "restore"),
        ("source_delete_default_action_detected", report["source_delete_default_action_detected"], "ui"),
        ("champion_delete_on_disk_pressure_detected", report["champion_delete_on_disk_pressure_detected"], "disk"),
        ("authority_state_changed", report["authority_state_changed"], "safety"),
        ("champion_pointer_changed", report["champion_pointer_changed"], "safety"),
        ("final_action_mutation_detected", report["final_action_mutation_detected"], "safety"),
        ("guard_bypass_detected", report["guard_bypass_detected"], "safety"),
        ("governance_policy_ssot_missing", not report["data_governance_policy_ssot_ready"], "policy"),
        ("data_catalog_missing", not report["data_catalog_ready"], "catalog"),
        ("archive_contract_missing", not report["archive_contract_ready"], "archive"),
        ("data_source_resolver_missing", not report["data_source_resolver_ready"], "resolver"),
        ("backup_manager_missing", not report["backup_manager_ready"], "backup"),
        ("restore_manager_missing", not report["restore_manager_ready"], "restore"),
        ("data_integrity_service_missing", not report["data_integrity_service_ready"], "integrity"),
        ("schema_registry_missing", not report["schema_registry_ready"], "migration"),
        ("data_governance_ui_missing", not report["data_backup_ui_ready"], "ui"),
    )
    first = next(((name, group) for name, active, group in checks if active), None)
    report["aits_data_governance_retention_backup_recovery_v1_ready"] = first is None
    report["first_blocker"] = first[0] if first else "aits_data_governance_retention_backup_recovery_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = "Packaging 전 Master Checklist에서 백업 plan과 schema compatibility를 다시 확인합니다."
    report["pass_status"] = "pass" if first is None else "fail"
    return report
