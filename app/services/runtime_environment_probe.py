from __future__ import annotations

import os
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
        "diagnostic_only": True,
    }


@dataclass
class RuntimeEnvironmentProbeResult:
    python_executable: str
    python_version: str
    sys_prefix: str
    base_prefix: str
    is_venv: bool
    cwd: str
    project_root_guess: str
    venv_python_exists: bool
    venv_python_path: str
    requirements_exists: bool
    requirements_path: str
    pyinstaller_frozen: bool
    executable_dir: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class RuntimeEnvironmentProbe:
    """Read-only Python/runtime environment probe for AITS diagnostics."""

    def probe(self, project_root: str | None = None) -> RuntimeEnvironmentProbeResult:
        root = self._resolve_project_root(project_root)
        venv_python = root / ".venv" / "Scripts" / "python.exe"
        requirements = root / "requirements.txt"
        executable = Path(sys.executable or "")
        frozen = bool(getattr(sys, "frozen", False))
        executable_dir = executable.parent if executable else Path("")
        is_venv = bool(sys.prefix != getattr(sys, "base_prefix", sys.prefix))
        warnings = self._build_warnings(
            root=root,
            venv_python=venv_python,
            requirements=requirements,
            executable=executable,
            is_venv=is_venv,
            frozen=frozen,
        )
        metadata = _metadata()
        metadata.update(
            {
                "probe_only": True,
                "file_write": False,
                "pip_executed": False,
                "venv_modified": False,
                "ollama_executed": False,
            }
        )
        return RuntimeEnvironmentProbeResult(
            python_executable=str(executable),
            python_version=sys.version.split()[0],
            sys_prefix=str(sys.prefix),
            base_prefix=str(getattr(sys, "base_prefix", sys.prefix)),
            is_venv=is_venv,
            cwd=str(Path.cwd()),
            project_root_guess=str(root),
            venv_python_exists=venv_python.exists(),
            venv_python_path=str(venv_python),
            requirements_exists=requirements.exists(),
            requirements_path=str(requirements),
            pyinstaller_frozen=frozen,
            executable_dir=str(executable_dir),
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

    def _build_warnings(
        self,
        root: Path,
        venv_python: Path,
        requirements: Path,
        executable: Path,
        is_venv: bool,
        frozen: bool,
    ) -> list:
        warnings: list[str] = []
        if not requirements.exists():
            warnings.append("requirements_missing")
        if not venv_python.exists():
            warnings.append("project_venv_python_missing")
        if not is_venv and not frozen:
            warnings.append("running_outside_project_venv")
        try:
            if venv_python.exists() and executable.resolve() != venv_python.resolve() and not frozen:
                warnings.append("active_python_differs_from_project_venv")
        except Exception:
            warnings.append("python_path_compare_failed")
        if ".venv" not in str(venv_python):
            warnings.append("unexpected_venv_path")
        if not (root / "app").exists():
            warnings.append("project_root_app_missing")
        return warnings


def build_sample_runtime_environment_probe() -> RuntimeEnvironmentProbeResult:
    return RuntimeEnvironmentProbe().probe()


__all__ = [
    "RuntimeEnvironmentProbeResult",
    "RuntimeEnvironmentProbe",
    "build_sample_runtime_environment_probe",
]
