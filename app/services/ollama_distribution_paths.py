from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "path_resolution_only": True,
    }


@dataclass
class OllamaDistributionPaths:
    project_root: str
    bundled_runtime_dir: str
    bundled_ollama_exe: str
    bundled_models_dir: str
    user_runtime_dir: str
    user_models_dir: str
    preferred_ollama_exe: str
    preferred_models_dir: str
    path_policy: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class OllamaDistributionPathResolver:
    """Resolves AITS Ollama runtime paths without creating or executing anything."""

    def resolve(self, project_root: str | None = None) -> OllamaDistributionPaths:
        root = self._resolve_project_root(project_root)
        exe_dir = self._executable_dir()
        bundled_base = exe_dir / "runtime" / "ollama" if self._is_frozen() else root / "runtime" / "ollama"
        bundled_exe = bundled_base / "ollama.exe"
        bundled_models = bundled_base / "models"
        local_app_data = Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
        user_base = local_app_data / "AITS" / "runtime" / "ollama"
        user_models = user_base / "models"
        path_ollama = shutil.which("ollama") or ""

        preferred_exe = ""
        preferred_models = ""
        policy = "bundled_runtime > user_runtime > PATH"
        warnings: list[str] = []
        if bundled_exe.exists():
            preferred_exe = str(bundled_exe)
            preferred_models = str(bundled_models)
        elif (user_base / "ollama.exe").exists():
            preferred_exe = str(user_base / "ollama.exe")
            preferred_models = str(user_models)
            warnings.append("using_user_runtime_fallback")
        elif path_ollama:
            preferred_exe = path_ollama
            preferred_models = str(user_models)
            warnings.append("using_path_ollama_fallback")
        else:
            preferred_exe = str(bundled_exe)
            preferred_models = str(bundled_models)
            warnings.append("ollama_executable_not_found")
        if not bundled_models.exists():
            warnings.append("bundled_models_missing")

        metadata = _metadata()
        metadata.update(
            {
                "frozen": self._is_frozen(),
                "executable_dir": str(exe_dir),
                "path_ollama_found": bool(path_ollama),
                "directories_created": False,
                "downloads_started": False,
                "ollama_executed": False,
            }
        )
        return OllamaDistributionPaths(
            project_root=self._display_path(root),
            bundled_runtime_dir=self._display_path(bundled_base),
            bundled_ollama_exe=self._display_path(bundled_exe),
            bundled_models_dir=self._display_path(bundled_models),
            user_runtime_dir=self._display_path(user_base),
            user_models_dir=self._display_path(user_models),
            preferred_ollama_exe=self._display_path(Path(preferred_exe)) if preferred_exe else "",
            preferred_models_dir=self._display_path(Path(preferred_models)) if preferred_models else "",
            path_policy=policy,
            warnings=warnings,
            metadata=metadata,
        )

    def _resolve_project_root(self, project_root: str | None) -> Path:
        if project_root:
            return Path(project_root).resolve()
        current = Path.cwd().resolve()
        if (current / "app").exists() and (current / "requirements.txt").exists():
            return current
        for parent in [current, *current.parents]:
            if (parent / "app").exists() and (parent / "requirements.txt").exists():
                return parent
        return current

    def _is_frozen(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    def _executable_dir(self) -> Path:
        if self._is_frozen():
            return Path(sys.executable).resolve().parent
        return self._resolve_project_root(None)

    def _display_path(self, path: Path) -> str:
        return path.as_posix()


def build_sample_ollama_distribution_paths() -> OllamaDistributionPaths:
    return OllamaDistributionPathResolver().resolve()


__all__ = [
    "OllamaDistributionPaths",
    "OllamaDistributionPathResolver",
    "build_sample_ollama_distribution_paths",
]
