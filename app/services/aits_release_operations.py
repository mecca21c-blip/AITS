from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_path_resolver import AITSPathResolver
from app.services.aits_release_view_model import build_release_view_model
from app.services.aits_update_manager import AITSUpdateManager
from app.services.aits_release_rollback import AITSReleaseRollback
from app.version import version_info


class AITSReleaseOperations:
    def snapshot(self) -> dict[str, Any]:
        paths = AITSPathResolver.resolve()
        info = version_info()
        result = {
            "schema": "aits_release_operations_snapshot.v1", "app_version": info["semantic_version"],
            "release_channel": info["release_channel"], "channel_ko": "릴리스 후보",
            "build_number": info["build_number"], "install_type": paths.install_type,
            "install_type_ko": {"installer": "Windows 설치형", "portable": "Portable 진단형", "development": "개발 환경", "override": "사용자 지정"}.get(paths.install_type, "Windows 설치형"),
            "data_root": str(paths.user_data_root), "backup_root": str(paths.user_backup_root),
            "schema_compatible": True, "runtime_active": False, "manifest_status": "structure_ready",
            "packaged_app_runtime_executed": False,
        }
        result["user_view"] = build_release_view_model(result)
        return result

    def update_plan(self, package: str, *, runtime_active: bool) -> dict[str, Any]:
        plan = AITSUpdateManager().plan(package)
        return {**plan, "blocker": "runtime_must_be_off" if runtime_active else "", "operation_executed": False}

    def rollback_plan(self, manifest: str, *, runtime_active: bool) -> dict[str, Any]:
        plan = AITSReleaseRollback().plan(manifest)
        return {**plan, "blocker": "runtime_must_be_off" if runtime_active else "", "operation_executed": False}
