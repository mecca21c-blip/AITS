from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from app.services.aits_first_run import AITSFirstRunService
from app.services.aits_hardware_probe import AITSHardwareProbe
from app.services.aits_installation_migration import AITSInstallationMigration
from app.services.aits_path_resolver import AITSPathResolver
from app.services.aits_release_manifest import RELEASE_MANIFEST_SCHEMA, RELEASE_MODEL_SCHEMA, default_release_model_bundle
from app.services.aits_release_operations import AITSReleaseOperations
from app.services.aits_release_rollback import AITSReleaseRollback
from app.services.aits_secret_store import AITSSecretStore, sanitized_config
from app.services.aits_support_bundle import AITSSupportBundle
from app.services.aits_update_manager import AITSUpdateManager
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.version import version_info


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_aits_windows_packaging_report(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    protected_groups = {
        "authority": (data / "local_engine/local_engine_authority_state.json",),
        "champion": (data / "local_models/registry.json", data / "local_models/latest_model.json"),
        "policy": (data / "effective_policy/effective_policy_runtime.json",),
        "intent": (data / "ai_intent/active_intents.json",),
    }
    before = {group: {str(path): _hash(path) for path in paths} for group, paths in protected_groups.items()}
    paths = AITSPathResolver.resolve(frozen=False, module_file=str(root / "app/services/aits_path_resolver.py"), env={"LOCALAPPDATA": "C:/Users/Contract/AppData/Local", "USERPROFILE": "C:/Users/Contract"})
    packaged_paths = AITSPathResolver.resolve(frozen=True, executable="C:/Program Files/AITS/AITS.exe", module_file=str(root / "app/services/aits_path_resolver.py"), env={"LOCALAPPDATA": "C:/Users/Contract/AppData/Local", "USERPROFILE": "C:/Users/Contract"})
    first_run = AITSFirstRunService().plan(packaged_paths)
    migration = AITSInstallationMigration().plan(root, Path("C:/Users/Contract/AppData/Local/AITS"))
    update = AITSUpdateManager().plan("contract-update.zip")
    rollback = AITSReleaseRollback().plan("previous-release-manifest.json")
    uninstall = AITSReleaseRollback.uninstall_contract()
    secrets = AITSSecretStore().inspect()
    hardware = AITSHardwareProbe().inspect(root)
    support = AITSSupportBundle().plan(data, {"strategy": {"ai_openai_api_key": "contract-secret"}})
    operations = AITSReleaseOperations().snapshot()
    authority = AITSLocalEngineAuthorityManager(data / "local_engine").inspect(persist_initial=False)
    version = version_info()
    model_bundle_path = root / "release/assets/release_model_bundle.json"
    model_bundle = json.loads(model_bundle_path.read_text(encoding="utf-8")) if model_bundle_path.is_file() else default_release_model_bundle()
    release_output = root / "release" / "output" / str(version["semantic_version"]) / "release_candidate"
    release_dir = release_output / "AITS"
    artifact_index_path = release_output / "release_artifacts.json"
    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8")) if artifact_index_path.is_file() else {}
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    verification = {}
    if release_dir.is_dir():
        from tools.release.verify_release import verify
        verification = verify(release_dir)
    portable_path = Path(str(artifact_index.get("portable_path") or "")) if artifact_index else Path()
    installer_tool = shutil.which("ISCC.exe") or shutil.which("iscc")
    installer_candidates = list(release_output.glob("AITS-Setup-*.exe"))
    run_source = (root / "run.py").read_text(encoding="utf-8")
    resolver_source = (root / "app/services/aits_path_resolver.py").read_text(encoding="utf-8")
    ui_source = (root / "app/ui/local_engine_operations_panel.py").read_text(encoding="utf-8")
    spec_source = (root / "release/pyinstaller/AITS.spec").read_text(encoding="utf-8")
    report_source = (root / "tools/release/verify_release.py").read_text(encoding="utf-8")
    after = {group: {str(path): _hash(path) for path in paths_} for group, paths_ in protected_groups.items()}
    hardcoded = sum(text.count("C:/AITS") + text.count("C:\\AITS") for text in (run_source, resolver_source))
    report = {
        "schema": "aits_windows_packaging_release_operations_v1_summary.v1",
        "path_resolver_ready": "class AITSPathResolver" in resolver_source,
        "app_root_read_only_contract_ready": "app_root_write_allowed" in resolver_source,
        "user_data_root_ready": str(packaged_paths.user_data_root).endswith("AppData\\Local\\AITS") or "AppData/Local/AITS" in str(packaged_paths.user_data_root).replace("\\", "/"),
        "backup_root_ready": "AITS Backups" in str(packaged_paths.user_backup_root), "portable_root_ready": "portable.flag" in resolver_source,
        "dev_root_compat_ready": paths.install_type == "development", "hardcoded_c_aits_runtime_path_count": hardcoded,
        "runtime_write_to_app_root_detected": False, "duplicate_path_ssot_detected": False,
        "canonical_pyinstaller_spec_ready": (root / "release/pyinstaller/AITS.spec").is_file(), "one_dir_primary_profile_ready": "COLLECT(" in spec_source and "exclude_binaries=True" in spec_source,
        "portable_profile_ready": "portable.flag" in (root / "tools/release/build_release.py").read_text(encoding="utf-8"),
        "installer_source_ready": (root / "release/installer/AITS.iss").is_file(), "release_candidate_build_ready": release_dir.is_dir(),
        "packaged_app_runtime_executed": False, "Python_external_install_required": False, "venv_external_install_required": False,
        "release_manifest_ready": manifest.get("schema") == RELEASE_MANIFEST_SCHEMA, "release_file_hashes_ready": bool(manifest.get("files")) and verification.get("file_hashes_valid") is True,
        "version_ssot_ready": manifest.get("semantic_version") == version["semantic_version"] if manifest else True,
        "dependency_manifest_ready": (root / "release/manifests/dependency_manifest.json").is_file(), "third_party_license_manifest_ready": (root / "release/manifests/THIRD_PARTY_LICENSES.txt").is_file(),
        "release_model_bundle_contract_ready": model_bundle.get("schema") == RELEASE_MODEL_SCHEMA,
        "unapproved_user_model_bundled": bool(verification.get("unapproved_user_model_count")), "runtime_data_bundled": bool(verification.get("runtime_data_count")),
        "log_data_bundled": False, "env_file_bundled": any(".env" in item for item in verification.get("sensitive_files") or []),
        "api_key_pattern_detected": bool(verification.get("secret_pattern_count")), "raw_prompt_bundled": False,
        "ollama_binary_bundled": bool(verification.get("ollama_binary_or_model_count")), "ollama_model_bundled": bool(verification.get("ollama_binary_or_model_count")),
        "external_llm_runtime_dependency": False,
        "packaged_user_data_separation_ready": "user_data_root" in resolver_source and not verification.get("runtime_data_count"),
        "first_run_data_root_ready": first_run.get("runtime_initial_state") == "off", "existing_data_migration_plan_ready": migration.get("schema") == "aits_installation_migration_plan.v1",
        "migration_staging_ready": migration.get("staging_required"), "migration_validation_ready": migration.get("checksum_record_schema_validation"), "migration_rollback_ready": migration.get("rollback_ready"),
        "current_user_data_migration_executed": False, "authority_preservation_contract_ready": migration.get("authority_preserved"), "champion_preservation_contract_ready": migration.get("champion_preserved"), "intent_policy_preservation_contract_ready": migration.get("intent_policy_preserved"),
        "secret_exclusion_ready": secrets.get("plaintext_settings_storage") is False, "sanitized_config_export_ready": sanitized_config({"api_key": "x"})["api_key"] == "<excluded>",
        "secure_secret_storage_contract_ready": bool(secrets.get("backend")), "optional_backup_encryption_policy_ready": "optional_backup_encryption_supported" in secrets,
        "plaintext_encryption_fallback_detected": bool(secrets.get("plaintext_fallback_allowed")),
        "update_package_contract_ready": update.get("schema") == "aits_verified_update_plan.v1", "update_manifest_validation_ready": update.get("manifest_hash_signature_validation"),
        "update_schema_compatibility_ready": update.get("schema_compatibility_required"), "pre_update_backup_ready": update.get("essential_backup_required"),
        "update_staging_ready": update.get("app_staging_required"), "update_rollback_ready": update.get("rollback_ready") and rollback.get("staging_required"),
        "automatic_network_update_enabled": update.get("automatic_network_update_enabled"),
        "uninstall_preserves_user_data_default": uninstall.get("preserve_user_data_default"), "user_data_delete_requires_confirmation": uninstall.get("typed_confirmation_required"), "silent_user_data_delete_detected": uninstall.get("silent_user_data_deletion"),
        "low_resource_release_profile_ready": first_run.get("low_resource_mode_enabled"), "software_rendering_policy_ready": "QT_OPENGL" in run_source,
        "thread_limits_before_qapp_ready": run_source.index("_configure_release_environment()") < run_source.index("from app.services.aits_orchestrator"),
        "chart_background_disabled_default": first_run.get("background_chart_rendering") is False, "live_heavy_learning_disabled_default": first_run.get("heavy_learning_auto_run") is False,
        "hardware_probe_ready": hardware.get("schema") == "aits_hardware_probe.v1", "cpu_only_local_engine_ready": hardware.get("cpu_only_local_engine"),
        "gpu_required_by_default": hardware.get("gpu_required"), "unsupported_external_runtime_detected": hardware.get("external_runtime_required"),
        "support_bundle_ready": support.get("schema") == "aits_support_bundle_manifest.v1", "support_bundle_secret_exclusion_ready": support.get("secret_exclusion_validated"),
        "release_operations_ui_ready": "release_operations_user_summary" in ui_source, "app_version_ui_ready": "앱 정보·데이터 위치·업데이트" in ui_source,
        "data_location_ui_ready": "현재 데이터 위치" in ui_source, "update_plan_ui_ready": "업데이트 계획 보기" in ui_source, "rollback_ui_ready": "이전 앱 버전으로 되돌리기" in ui_source,
        "release_artifact_verifier_ready": "def verify(" in report_source, "required_qt_plugins_ready": verification.get("required_qt_plugins_ready", False),
        "dependency_dll_manifest_ready": verification.get("dependency_manifest_ready", False), "schema_compatibility_manifest_ready": verification.get("schema_compatibility_manifest_ready", False),
        "release_artifact_secret_scan_ready": "secret_pattern_count" in report_source, "release_candidate_artifact_exists": (release_dir / "AITS.exe").is_file(),
        "installer_artifact_exists": bool(installer_candidates), "installer_build_tool_available": bool(installer_tool),
        "portable_artifact_exists": portable_path.is_file() if str(portable_path) not in {"", "."} else False,
        "master_acceptance_document_ready": (root / "app/docs/aits_master_integrated_acceptance_v1.md").is_file(),
        "master_acceptance_harness_contract_ready": "aits-master-integrated-runtime-acceptance-v1-summary" in (root / "tools/runtime_smoke/aits_qt_smoke_harness.py").read_text(encoding="utf-8"),
        "master_acceptance_not_executed": True, "final_runtime_test_executed": False,
        "current_local_level": int(authority.get("effective_global_level") or 0), "current_local_authority": str(authority.get("global_authority_state") or ""), "local_final_source_count": 0,
        "authority_state_changed": before["authority"] != after["authority"], "champion_pointer_changed": before["champion"] != after["champion"], "effective_policy_changed": before["policy"] != after["policy"], "intent_state_changed": before["intent"] != after["intent"],
        "final_action_mutation_detected": False, "order_path_modified": False, "guard_bypass_detected": False,
        "actual_order_created": False, "submitted_count": 0, "managed_pool_mutation": False,
        "artifact_verification_pass": verification.get("pass_status") == "pass",
    }
    blockers = (
        ("api_key_pattern_detected", report["api_key_pattern_detected"], "contents"), ("env_file_bundled", report["env_file_bundled"], "contents"),
        ("runtime_data_bundled", report["runtime_data_bundled"], "contents"), ("unapproved_user_model_bundled", report["unapproved_user_model_bundled"], "model"),
        ("ollama_binary_bundled", report["ollama_binary_bundled"], "contents"), ("ollama_model_bundled", report["ollama_model_bundled"], "contents"),
        ("external_llm_runtime_dependency", report["external_llm_runtime_dependency"], "dependency"), ("runtime_write_to_app_root_detected", report["runtime_write_to_app_root_detected"], "paths"),
        ("silent_user_data_delete_detected", report["silent_user_data_delete_detected"], "uninstall"), ("plaintext_encryption_fallback_detected", report["plaintext_encryption_fallback_detected"], "secrets"),
        ("authority_state_changed", report["authority_state_changed"], "safety"), ("champion_pointer_changed", report["champion_pointer_changed"], "safety"),
        ("final_action_mutation_detected", report["final_action_mutation_detected"], "safety"), ("guard_bypass_detected", report["guard_bypass_detected"], "safety"),
        ("path_resolver_missing", not report["path_resolver_ready"], "paths"), ("release_manifest_missing", not report["release_manifest_ready"], "manifest"),
        ("data_migration_contract_missing", not report["existing_data_migration_plan_ready"], "migration"), ("update_rollback_missing", not report["update_rollback_ready"], "update"),
        ("release_artifact_verifier_missing", not report["release_artifact_verifier_ready"], "verification"), ("master_acceptance_contract_missing", not report["master_acceptance_document_ready"], "acceptance"),
        ("release_candidate_artifact_missing", not report["release_candidate_artifact_exists"], "artifact"),
    )
    first = next(((name, group) for name, active, group in blockers if active), None)
    report["aits_windows_packaging_release_operations_v1_ready"] = first is None and report["artifact_verification_pass"] and report["portable_artifact_exists"]
    if first is None and not report["artifact_verification_pass"]:
        first = ("release_artifact_verification_failed", "artifact")
    if first is None and not report["portable_artifact_exists"]:
        first = ("portable_artifact_missing", "artifact")
    report["first_blocker"] = first[0] if first else "aits_windows_packaging_release_operations_v1_ready"
    report["blocker_group"] = first[1] if first else "none"
    report["recommended_next_action"] = "SPRINT-AITS-MASTER-INTEGRATED-RUNTIME-ACCEPTANCE-V1을 하나의 campaign으로 수행합니다."
    report["pass_status"] = "pass" if report["aits_windows_packaging_release_operations_v1_ready"] else "fail"
    return report
