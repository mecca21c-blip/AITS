from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.services.ollama_distribution_paths import OllamaDistributionPathResolver


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "inference_called": False,
        "generate_called": False,
        "chat_called": False,
        "real_order": False,
        "submitted": 0,
        "shadow_only": True,
        "research_mode": True,
    }


@dataclass
class OllamaProcessHealthResult:
    available: bool
    executable_path: str
    executable_exists: bool
    version: str
    version_check_ok: bool
    process_check_supported: bool
    process_running: bool
    model_dir: str
    model_dir_exists: bool
    preferred_source: str
    reason: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class OllamaProcessHealthChecker:
    """Checks Ollama executable/process health without inference calls."""

    def check(
        self,
        project_root: str | None = None,
        timeout_sec: int = 3,
    ) -> OllamaProcessHealthResult:
        warnings: list[str] = []
        paths = OllamaDistributionPathResolver().resolve(project_root)
        exe_path = str(paths.preferred_ollama_exe or "")
        model_dir = str(paths.preferred_models_dir or paths.bundled_models_dir or "")
        executable_exists = bool(exe_path and Path(exe_path).exists())
        model_dir_exists = bool(model_dir and Path(model_dir).exists())
        preferred_source = self._preferred_source(paths, exe_path)
        version = ""
        version_check_ok = False
        if executable_exists:
            version, version_check_ok, version_warning = self._check_version(
                exe_path,
                timeout_sec=timeout_sec,
            )
            if version_warning:
                warnings.append(version_warning)
        else:
            warnings.append("ollama_executable_missing")
        if not model_dir_exists:
            warnings.append("ollama_model_dir_missing")
        process_supported, process_running = self._check_process_running()
        if not process_supported:
            warnings.append("process_check_not_supported")
        available = bool(executable_exists and version_check_ok)
        reason = "ready" if available else "not_ready"
        if executable_exists and not version_check_ok:
            reason = "version_check_failed"
        if not executable_exists:
            reason = "executable_missing"
        metadata = _metadata()
        metadata.update(
            {
                "distribution_paths": asdict(paths),
                "timeout_sec": int(timeout_sec or 3),
                "directories_created": False,
                "downloads_started": False,
                "provider_api_called": False,
                "ollama_inference_called": False,
            }
        )
        return OllamaProcessHealthResult(
            available=available,
            executable_path=exe_path,
            executable_exists=executable_exists,
            version=version,
            version_check_ok=version_check_ok,
            process_check_supported=process_supported,
            process_running=process_running,
            model_dir=model_dir,
            model_dir_exists=model_dir_exists,
            preferred_source=preferred_source,
            reason=reason,
            warnings=warnings,
            metadata=metadata,
        )

    def _check_version(self, executable_path: str, timeout_sec: int) -> tuple[str, bool, str]:
        try:
            completed = subprocess.run(
                [executable_path, "--version"],
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_sec or 3)),
                check=False,
            )
            text = ((completed.stdout or "") + " " + (completed.stderr or "")).strip()
            if completed.returncode == 0:
                return text, True, ""
            return text, False, "ollama_version_nonzero_exit"
        except subprocess.TimeoutExpired:
            return "", False, "ollama_version_timeout"
        except Exception:
            return "", False, "ollama_version_check_failed"

    def _check_process_running(self) -> tuple[bool, bool]:
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ollama.exe"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if completed.returncode != 0:
                return True, False
            output = (completed.stdout or "").lower()
            return True, "ollama.exe" in output
        except Exception:
            return False, False

    def _preferred_source(self, paths, exe_path: str) -> str:
        if not exe_path:
            return "none"
        if exe_path == str(paths.bundled_ollama_exe):
            return "bundled"
        user_exe = str(Path(paths.user_runtime_dir) / "ollama.exe")
        if exe_path.replace("\\", "/") == user_exe.replace("\\", "/"):
            return "user"
        return "path"


def build_sample_ollama_process_health() -> OllamaProcessHealthResult:
    return OllamaProcessHealthChecker().check()


__all__ = [
    "OllamaProcessHealthResult",
    "OllamaProcessHealthChecker",
    "build_sample_ollama_process_health",
]
