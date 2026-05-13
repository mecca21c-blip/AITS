from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.ollama_runtime_config import (
    OllamaRuntimeConfig,
    OllamaRuntimeConfigBuilder,
)


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "local_runtime": True,
    }


@dataclass
class OllamaRuntimeStatus:
    provider: str
    engine: str
    model: str
    executable_found: bool
    executable_path: str
    model_configured: bool
    executable_ready: bool
    model_dir_ready: bool
    inference_ready: bool
    process_health: dict
    runtime_ready: bool
    dry_run_supported: bool
    live_supported: bool
    status: str
    reason: str
    metadata: dict = field(default_factory=_metadata)


class OllamaRuntimeStatusProbe:
    """Inspects local runtime availability without calling Ollama inference."""

    def check_status(
        self,
        config: OllamaRuntimeConfig | None = None,
        model: str | None = None,
    ) -> OllamaRuntimeStatus:
        cfg = config or OllamaRuntimeConfigBuilder().build_default_config(
            model=model or "qwen2.5:7b-instruct-q4"
        )
        from app.services.ollama_process_health import OllamaProcessHealthChecker

        process_health = OllamaProcessHealthChecker().check(timeout_sec=3)
        executable_path = process_health.executable_path
        executable_found = bool(process_health.executable_exists)
        model_configured = bool(str(cfg.model or "").strip())
        executable_ready = bool(process_health.available)
        model_dir_ready = bool(process_health.model_dir_exists)
        inference_ready = False
        runtime_ready = bool(executable_ready)
        status = "dry-run-only"
        if executable_ready and model_configured:
            status = "available"
        elif not model_configured:
            status = "unavailable"
        elif executable_found and not executable_ready:
            status = "degraded"
        reason = "local_runtime_detected" if executable_ready else process_health.reason
        if not model_configured:
            reason = "missing_model"
        metadata = _metadata()
        metadata.update(
            {
                "base_url": cfg.base_url,
                "timeout_sec": cfg.timeout_sec,
                "ollama_executable_found": executable_found,
                "ollama_executable_ready": executable_ready,
                "ollama_model_dir_ready": model_dir_ready,
                "ollama_inference_ready": inference_ready,
                "ollama_service_checked": bool(process_health.version_check_ok),
                "model_list_checked": False,
                "process_health": asdict(process_health),
                "dry_run_only": True,
            }
        )
        return OllamaRuntimeStatus(
            provider="ollama",
            engine="basic",
            model=cfg.model,
            executable_found=executable_found,
            executable_path=executable_path,
            model_configured=model_configured,
            executable_ready=executable_ready,
            model_dir_ready=model_dir_ready,
            inference_ready=inference_ready,
            process_health=asdict(process_health),
            runtime_ready=runtime_ready,
            dry_run_supported=True,
            live_supported=False,
            status=status,
            reason=reason,
            metadata=metadata,
        )


def build_sample_ollama_runtime_status() -> OllamaRuntimeStatus:
    return OllamaRuntimeStatusProbe().check_status(model="mock")


__all__ = [
    "OllamaRuntimeStatus",
    "OllamaRuntimeStatusProbe",
    "build_sample_ollama_runtime_status",
]
