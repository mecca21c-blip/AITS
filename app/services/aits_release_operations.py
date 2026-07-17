from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.aits_backup_manager import AITSBackupManager
from app.services.aits_installation_migration import AITSInstallationMigration
from app.services.aits_path_resolver import AITSPathResolver
from app.services.aits_release_operation_context import AITSReleaseOperationContext
from app.services.aits_release_rollback import AITSReleaseRollback
from app.services.aits_release_view_model import build_release_view_model
from app.services.aits_support_bundle import AITSSupportBundle
from app.services.aits_update_manager import AITSUpdateManager
from app.version import version_info


class AITSReleaseOperations:
    """OFF-only, explicit-approval entrypoint for release file operations."""

    def snapshot(self, *, runtime_active: bool = False) -> dict[str, Any]:
        paths = AITSPathResolver.resolve()
        info = version_info()
        result = {
            "schema": "aits_release_operations_snapshot.v1",
            "app_version": info["semantic_version"],
            "release_channel": info["release_channel"],
            "channel_ko": "릴리스 후보",
            "build_number": info["build_number"],
            "install_type": paths.install_type,
            "install_type_ko": {
                "installer": "Windows 설치형",
                "portable": "Portable 진단형",
                "portable_fallback": "Portable 사용자 데이터 분리형",
                "development": "개발 환경",
                "override": "사용자 지정 데이터 위치",
            }.get(paths.install_type, "Windows 설치형"),
            "data_root": str(paths.user_data_root),
            "backup_root": str(paths.user_backup_root),
            "schema_compatible": True,
            "runtime_active": bool(runtime_active),
            "operations_enabled": not runtime_active,
            "explicit_user_approval_required": True,
            "source_preservation_required": True,
            "manifest_status": "execution_ready",
            "packaged_app_runtime_executed": False,
        }
        result["user_view"] = build_release_view_model(result)
        return result

    @staticmethod
    def _context(
        operation_type: str,
        source_root: Path,
        target_root: Path,
        *,
        runtime_active: bool,
        approved: bool,
        isolated_acceptance_mode: bool = False,
    ) -> AITSReleaseOperationContext:
        return AITSReleaseOperationContext.create(
            operation_type=operation_type,
            source_root=source_root,
            target_root=target_root,
            staging_root=target_root.parent / ".aits-release-staging" / operation_type,
            explicit_user_approval=approved,
            runtime_off_confirmed=not runtime_active,
            execution_authorized=approved and not runtime_active,
            isolated_acceptance_mode=isolated_acceptance_mode,
            destructive_operation=False,
            source_preservation_required=True,
            rollback_required=True,
            requested_by="user",
            authorization_reason="confirmed_release_operations_ui",
        )

    def create_essential_backup(self, *, runtime_active: bool, approved: bool) -> dict[str, Any]:
        paths = AITSPathResolver.resolve()
        context = self._context(
            "essential_backup", paths.user_data_root, paths.user_backup_root,
            runtime_active=runtime_active, approved=approved,
        )
        return AITSBackupManager(paths.user_data_root / "data", app_root=paths.app_root).execute(
            "essential", context=context,
        )

    def create_support_bundle(self, *, runtime_active: bool, approved: bool) -> dict[str, Any]:
        paths = AITSPathResolver.resolve()
        target = paths.user_data_root / "reports" / "support"
        context = self._context(
            "support_bundle", paths.user_data_root, target,
            runtime_active=runtime_active, approved=approved,
        )
        return AITSSupportBundle().execute(context=context)

    def migrate(
        self,
        source_root: Path | str,
        target_root: Path | str,
        *,
        runtime_active: bool,
        approved: bool,
        isolated_acceptance_mode: bool = False,
    ) -> dict[str, Any]:
        source, target = Path(source_root), Path(target_root)
        context = self._context(
            "migration", source, target,
            runtime_active=runtime_active, approved=approved,
            isolated_acceptance_mode=isolated_acceptance_mode,
        )
        return AITSInstallationMigration().execute(context)

    def update_plan(self, package: str, *, runtime_active: bool) -> dict[str, Any]:
        plan = AITSUpdateManager().plan(package)
        return {**plan, "blocker": "runtime_must_be_off" if runtime_active else "", "operation_executed": False}

    def rollback_plan(self, manifest: str, *, runtime_active: bool) -> dict[str, Any]:
        plan = AITSReleaseRollback().plan(manifest)
        return {**plan, "blocker": "runtime_must_be_off" if runtime_active else "", "operation_executed": False}
