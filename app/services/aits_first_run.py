from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_path_resolver import AITSPathResolver, AITSPaths
from app.version import version_info


class AITSFirstRunService:
    def plan(self, paths: AITSPaths) -> dict[str, Any]:
        return {
            "schema": "aits_first_run_plan.v1", "app_version": version_info()["semantic_version"],
            "install_type": paths.install_type, "data_root": str(paths.user_data_root),
            "backup_root": str(paths.user_backup_root), "runtime_initial_state": "off",
            "automatic_on": False, "automatic_order": False, "low_resource_mode_enabled": True,
            "background_chart_rendering": False, "heavy_learning_auto_run": False,
            "ollama_developer_only": True, "ollama_auto_generate": False,
            "provider_key_missing_is_error": False, "release_manifest_validation_required": True,
            "governance_defaults_required": True, "local_authority_expansion": False,
            "user_notice_ko": "최초 실행은 OFF 상태이며 자동 실거래가 시작되지 않습니다.",
        }

    def initialize_directories(self, paths: AITSPaths, *, explicit: bool = False) -> dict[str, Any]:
        if not explicit:
            return {**self.plan(paths), "initialized": False, "blocker": "explicit_first_run_required"}
        AITSPathResolver.ensure_writable_roots(paths)
        return {**self.plan(paths), "initialized": True, "blocker": ""}
