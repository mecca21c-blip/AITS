from __future__ import annotations

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
        "venv_modified": False,
        "pip_executed": False,
    }


@dataclass
class VenvRepairDiagnosticsResult:
    project_root: str
    current_python: str
    current_python_version: str
    venv_python_path: str
    venv_python_exists: bool
    pyvenv_cfg_path: str
    pyvenv_cfg_exists: bool
    pyvenv_home: str
    pyvenv_home_exists: bool
    pyvenv_executable: str
    pyvenv_executable_exists: bool
    active_is_project_venv: bool
    repair_required: bool
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class VenvRepairDiagnostics:
    """Read-only diagnostics for deciding whether the project venv needs repair."""

    def run(self, project_root: str | None = None) -> VenvRepairDiagnosticsResult:
        root = self._resolve_project_root(project_root)
        venv_python = root / ".venv" / "Scripts" / "python.exe"
        pyvenv_cfg = root / ".venv" / "pyvenv.cfg"
        cfg = self._read_pyvenv_cfg(pyvenv_cfg)
        pyvenv_home = cfg.get("home", "")
        pyvenv_executable = cfg.get("executable", "")
        home_exists = bool(pyvenv_home and Path(pyvenv_home).exists())
        executable_exists = bool(pyvenv_executable and Path(pyvenv_executable).exists())
        active_is_project_venv = self._same_path(Path(sys.executable), venv_python)
        warnings = self._build_warnings(
            venv_python=venv_python,
            pyvenv_cfg=pyvenv_cfg,
            pyvenv_home=pyvenv_home,
            home_exists=home_exists,
            pyvenv_executable=pyvenv_executable,
            executable_exists=executable_exists,
            active_is_project_venv=active_is_project_venv,
        )
        repair_required = (
            not venv_python.exists()
            or not pyvenv_cfg.exists()
            or not home_exists
        )
        metadata = _metadata()
        metadata.update(
            {
                "subprocess_executed": False,
                "requirements_modified": False,
                "venv_deleted": False,
                "venv_recreated": False,
            }
        )
        return VenvRepairDiagnosticsResult(
            project_root=str(root),
            current_python=str(Path(sys.executable)),
            current_python_version=sys.version.split()[0],
            venv_python_path=str(venv_python),
            venv_python_exists=venv_python.exists(),
            pyvenv_cfg_path=str(pyvenv_cfg),
            pyvenv_cfg_exists=pyvenv_cfg.exists(),
            pyvenv_home=pyvenv_home,
            pyvenv_home_exists=home_exists,
            pyvenv_executable=pyvenv_executable,
            pyvenv_executable_exists=executable_exists,
            active_is_project_venv=active_is_project_venv,
            repair_required=repair_required,
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

    def _read_pyvenv_cfg(self, path: Path) -> dict:
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip().lower()] = value.strip()
        except Exception:
            values["read_error"] = "true"
        return values

    def _build_warnings(
        self,
        venv_python: Path,
        pyvenv_cfg: Path,
        pyvenv_home: str,
        home_exists: bool,
        pyvenv_executable: str,
        executable_exists: bool,
        active_is_project_venv: bool,
    ) -> list:
        warnings: list[str] = []
        if not venv_python.exists():
            warnings.append("venv_python_missing")
        if not pyvenv_cfg.exists():
            warnings.append("pyvenv_cfg_missing")
        if pyvenv_cfg.exists() and not pyvenv_home:
            warnings.append("pyvenv_home_missing")
        if pyvenv_home and not home_exists:
            warnings.append("pyvenv_home_not_found")
        if pyvenv_executable and not executable_exists:
            warnings.append("pyvenv_executable_not_found")
        if not pyvenv_executable:
            warnings.append("pyvenv_executable_missing")
        if not active_is_project_venv:
            warnings.append("active_python_is_not_project_venv")
        return warnings

    def _same_path(self, left: Path, right: Path) -> bool:
        try:
            return left.exists() and right.exists() and left.resolve() == right.resolve()
        except Exception:
            return False


def build_sample_venv_repair_diagnostics() -> VenvRepairDiagnosticsResult:
    return VenvRepairDiagnostics().run()


__all__ = [
    "VenvRepairDiagnosticsResult",
    "VenvRepairDiagnostics",
    "build_sample_venv_repair_diagnostics",
]
