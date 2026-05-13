from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field

from app.services.ollama_process_health import OllamaProcessHealthChecker


PREFERRED_MODEL = "qwen2.5:7b-instruct-q4"
DEFAULT_MODEL = "qwen2.5"


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "inference_called": False,
        "generate_called": False,
        "chat_called": False,
        "run_called": False,
        "pull_called": False,
        "real_order": False,
        "submitted": 0,
        "shadow_only": True,
        "research_mode": True,
    }


@dataclass
class OllamaModelInfo:
    name: str
    id: str
    size: str
    modified: str
    metadata: dict = field(default_factory=_metadata)


@dataclass
class OllamaModelInventoryResult:
    available: bool
    executable_path: str
    models: list
    model_count: int
    preferred_model: str
    preferred_model_found: bool
    default_model: str
    default_model_found: bool
    inventory_check_ok: bool
    reason: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class OllamaModelInventory:
    """Lists installed Ollama models using `ollama list` only."""

    def list_models(
        self,
        project_root: str | None = None,
        timeout_sec: int = 5,
    ) -> OllamaModelInventoryResult:
        warnings: list[str] = []
        health = OllamaProcessHealthChecker().check(
            project_root=project_root,
            timeout_sec=3,
        )
        if not health.executable_exists:
            warnings.extend(list(health.warnings or []))
            return self._result(
                health=health,
                models=[],
                ok=False,
                reason="executable_missing",
                warnings=warnings,
            )
        models, ok, reason, extra_warnings = self._run_ollama_list(
            health.executable_path,
            timeout_sec=timeout_sec,
        )
        warnings.extend(list(health.warnings or []))
        warnings.extend(extra_warnings)
        return self._result(
            health=health,
            models=models,
            ok=ok,
            reason=reason,
            warnings=warnings,
        )

    def _run_ollama_list(
        self,
        executable_path: str,
        timeout_sec: int,
    ) -> tuple[list[OllamaModelInfo], bool, str, list[str]]:
        try:
            completed = subprocess.run(
                [executable_path, "list"],
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_sec or 5)),
                check=False,
            )
            text = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
            if completed.returncode != 0:
                return [], False, "ollama_list_nonzero_exit", ["ollama_list_failed"]
            models = self._parse_list_output(text)
            reason = "ok" if models else "no_models"
            return models, True, reason, []
        except subprocess.TimeoutExpired:
            return [], False, "ollama_list_timeout", ["ollama_list_timeout"]
        except Exception:
            return [], False, "ollama_list_failed", ["ollama_list_failed"]

    def _parse_list_output(self, text: str) -> list[OllamaModelInfo]:
        models: list[OllamaModelInfo] = []
        for line in str(text or "").splitlines():
            clean = line.strip()
            if not clean:
                continue
            if clean.upper().startswith("NAME "):
                continue
            parts = clean.split()
            if not parts:
                continue
            name = parts[0]
            model_id = parts[1] if len(parts) > 1 else ""
            size = " ".join(parts[2:4]) if len(parts) >= 4 else (parts[2] if len(parts) > 2 else "")
            modified = " ".join(parts[4:]) if len(parts) > 4 else ""
            metadata = _metadata()
            metadata.update({"source": "ollama_list"})
            models.append(
                OllamaModelInfo(
                    name=name,
                    id=model_id,
                    size=size,
                    modified=modified,
                    metadata=metadata,
                )
            )
        return models

    def _result(
        self,
        health,
        models: list[OllamaModelInfo],
        ok: bool,
        reason: str,
        warnings: list[str],
    ) -> OllamaModelInventoryResult:
        names = [model.name for model in models]
        preferred_found = self._contains_model(names, PREFERRED_MODEL)
        default_model = self._find_default_model(names)
        default_found = bool(default_model)
        metadata = _metadata()
        metadata.update(
            {
                "process_health": asdict(health),
                "provider_api_called": False,
                "inventory_command": "ollama list",
            }
        )
        return OllamaModelInventoryResult(
            available=bool(health.available and ok),
            executable_path=str(health.executable_path or ""),
            models=models,
            model_count=len(models),
            preferred_model=PREFERRED_MODEL,
            preferred_model_found=preferred_found,
            default_model=default_model or DEFAULT_MODEL,
            default_model_found=default_found,
            inventory_check_ok=bool(ok),
            reason=str(reason or "unknown"),
            warnings=list(dict.fromkeys(warnings)),
            metadata=metadata,
        )

    def _contains_model(self, names: list[str], target: str) -> bool:
        target_norm = str(target or "").strip().lower()
        return any(str(name or "").strip().lower() == target_norm for name in names)

    def _find_default_model(self, names: list[str]) -> str:
        for prefix in ("qwen2.5", "qwen", "llama", "mistral"):
            for name in names:
                if str(name or "").strip().lower().startswith(prefix):
                    return name
        return names[0] if names else ""


def build_sample_ollama_model_inventory() -> OllamaModelInventoryResult:
    return OllamaModelInventory().list_models()


__all__ = [
    "OllamaModelInfo",
    "OllamaModelInventoryResult",
    "OllamaModelInventory",
    "build_sample_ollama_model_inventory",
]
