from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sys
from typing import Mapping


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

    @staticmethod
    def app_root_write_allowed(paths: AITSPaths) -> bool:
        return paths.install_type == "development"
