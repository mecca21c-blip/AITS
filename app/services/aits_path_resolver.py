from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sys
from typing import Any, Mapping


@dataclass(frozen=True)
class AITSPaths:
    app_root: Path
    user_data_root: Path
    user_config_root: Path
    user_backup_root: Path
    packaged_resource_root: Path
    dev_root: Path
    portable_root: Path | None
    install_type: str

    def as_strings(self) -> dict[str, str]:
        return {key: str(value) if value is not None else "" for key, value in asdict(self).items()}


class AITSPathResolver:
    """Single path SSOT for developer, installer, and explicit portable profiles."""

    SUBDIRECTORIES = ("config", "data", "logs", "models", "backups", "archive", "reports", "crash", "cache", "temp", "migrations")

    @staticmethod
    def _local_app_data(env: Mapping[str, str]) -> Path:
        value = env.get("LOCALAPPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Local"

    @staticmethod
    def _documents(env: Mapping[str, str]) -> Path:
        profile = Path(env.get("USERPROFILE") or Path.home())
        return profile / "Documents"

    @staticmethod
    def _dev_root(module_file: str | None) -> Path:
        start = Path(module_file or __file__).resolve()
        directory = start.parent if start.is_file() or start.suffix else start
        for candidate in (directory, *directory.parents):
            if (candidate / "run.py").is_file() and (candidate / "app").is_dir():
                return candidate
        return Path(__file__).resolve().parents[2]

    @classmethod
    def resolve(cls, *, executable: str | None = None, module_file: str | None = None,
                frozen: bool | None = None, env: Mapping[str, str] | None = None) -> AITSPaths:
        env = dict(os.environ if env is None else env)
        is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
        executable_path = Path(executable or sys.executable).resolve()
        dev_root = cls._dev_root(module_file)
        app_root = executable_path.parent if is_frozen else dev_root
        resource_root = Path(getattr(sys, "_MEIPASS", app_root)).resolve() if is_frozen else app_root
        portable_flag = app_root / "portable.flag"
        explicit_home = env.get("AITS_HOME")
        explicit_data = env.get("AITS_DATA_ROOT")
        portable_root: Path | None = app_root if portable_flag.is_file() else None
        if explicit_data:
            user_root = Path(explicit_data).expanduser().resolve()
            install_type = "override"
        elif portable_root is not None:
            candidate = portable_root / "AITS_Data"
            parent = candidate.parent
            writable = parent.exists() and os.access(parent, os.W_OK)
            user_root = candidate if writable else cls._local_app_data(env) / "AITS"
            install_type = "portable" if writable else "portable_fallback"
        elif is_frozen:
            user_root = cls._local_app_data(env) / "AITS"
            install_type = "installer"
        else:
            user_root = Path(explicit_home).expanduser().resolve() if explicit_home else dev_root
            install_type = "development"
        backup_root = Path(env.get("AITS_BACKUP_ROOT") or (cls._documents(env) / "AITS Backups"))
        return AITSPaths(
            app_root=app_root, user_data_root=user_root, user_config_root=user_root / "config",
            user_backup_root=backup_root, packaged_resource_root=resource_root, dev_root=dev_root,
            portable_root=portable_root, install_type=install_type,
        )

    @classmethod
    def ensure_writable_roots(cls, paths: AITSPaths) -> None:
        paths.user_data_root.mkdir(parents=True, exist_ok=True)
        for name in cls.SUBDIRECTORIES:
            (paths.user_data_root / name).mkdir(parents=True, exist_ok=True)
        paths.user_backup_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def runtime_data_dir(paths: AITSPaths) -> Path:
        return paths.user_data_root / "data" if paths.install_type != "development" else paths.user_data_root / "data"

    @classmethod
    def get_logs_root(cls, paths: AITSPaths) -> Path:
        """Return the one canonical runtime log root for the resolved install profile."""
        if paths.install_type == "development":
            return cls.runtime_data_dir(paths) / "logs"
        return paths.user_data_root / "logs"

    @classmethod
    def get_runtime_log_paths(cls, paths: AITSPaths) -> tuple[Path, ...]:
        """Return deterministic existing AITS log files without consulting the app root."""
        logs_root = cls.get_logs_root(paths)
        try:
            candidates = [
                path for path in logs_root.iterdir()
                if path.is_file() and (path.name == "aits.log" or path.name.startswith("aits.log."))
            ]
        except OSError:
            candidates = []
        return tuple(sorted(candidates, key=lambda path: (-path.stat().st_mtime_ns, path.name.lower())))

    @classmethod
    def resolve_support_log_sources(
        cls,
        *,
        source_root: Path | str | None = None,
        paths: AITSPaths | None = None,
    ) -> dict[str, Any]:
        """Resolve support-log inputs through the path SSOT, including acceptance overrides."""
        resolved = paths or cls.resolve()
        if source_root is not None:
            requested_root = Path(source_root).expanduser().resolve()
            if requested_root != resolved.user_data_root.resolve():
                resolved = AITSPaths(
                    app_root=resolved.app_root,
                    user_data_root=requested_root,
                    user_config_root=requested_root / "config",
                    user_backup_root=resolved.user_backup_root,
                    packaged_resource_root=resolved.packaged_resource_root,
                    dev_root=resolved.dev_root,
                    portable_root=None,
                    install_type="override",
                )
        logs_root = cls.get_logs_root(resolved)
        log_paths = cls.get_runtime_log_paths(resolved)
        root_label = "%PORTABLE_DATA_ROOT%\\logs" if resolved.install_type == "portable" else "%USER_DATA_ROOT%\\logs"
        path_source = "user_data_root"
        return {
            "logs_root": logs_root,
            "log_paths": log_paths,
            "root_label": root_label,
            "path_labels": tuple(f"{root_label}\\{path.name}" for path in log_paths),
            "install_type": resolved.install_type,
            "path_source": path_source,
            "uses_app_root": path_source == "app_root",
        }

    @staticmethod
    def app_root_write_allowed(paths: AITSPaths) -> bool:
        return paths.install_type == "development"
