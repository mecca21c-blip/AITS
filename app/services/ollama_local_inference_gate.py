from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.ollama_model_inventory import OllamaModelInventory
from app.services.ollama_model_selector import OllamaModelSelector
from app.services.ollama_process_health import OllamaProcessHealthChecker


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local",
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "one_shot": True,
        "inference_called": False,
    }


@dataclass
class OllamaLocalInferenceGateResult:
    allowed: bool
    provider: str
    model: str
    reason: str
    explicit_enable: bool
    runtime_ready: bool
    model_ready: bool
    timeout_sec: int
    metadata: dict = field(default_factory=_metadata)


class OllamaLocalInferenceGate:
    """Final explicit gate before a single local Ollama shadow inference."""

    def evaluate(
        self,
        explicit_enable: bool = False,
        timeout_sec: int = 30,
        project_root: str | None = None,
    ) -> OllamaLocalInferenceGateResult:
        timeout = int(timeout_sec or 0)
        health = OllamaProcessHealthChecker().check(
            project_root=project_root,
            timeout_sec=min(max(timeout, 1), 5) if timeout > 0 else 3,
        )
        inventory = OllamaModelInventory().list_models(
            project_root=project_root,
            timeout_sec=5,
        )
        selection = OllamaModelSelector().select(inventory)
        runtime_ready = bool(health.available)
        model_ready = bool(selection.selected)
        allowed = False
        reason = "explicit_enable_required"
        if not explicit_enable:
            reason = "explicit_enable_required"
        elif timeout <= 0:
            reason = "invalid_timeout"
        elif not runtime_ready:
            reason = "runtime_not_ready"
        elif not model_ready:
            reason = "model_not_ready"
        else:
            allowed = True
            reason = "allowed"
        metadata = _metadata()
        metadata.update(
            {
                "process_health": asdict(health),
                "model_inventory": asdict(inventory),
                "model_selection": asdict(selection),
                "provider_api_called": False,
                "downloads_started": False,
                "directories_created": False,
            }
        )
        return OllamaLocalInferenceGateResult(
            allowed=allowed,
            provider="ollama",
            model=str(selection.selected_model or ""),
            reason=reason,
            explicit_enable=bool(explicit_enable),
            runtime_ready=runtime_ready,
            model_ready=model_ready,
            timeout_sec=timeout,
            metadata=metadata,
        )


def build_sample_ollama_local_inference_gate() -> OllamaLocalInferenceGateResult:
    return OllamaLocalInferenceGate().evaluate()


__all__ = [
    "OllamaLocalInferenceGateResult",
    "OllamaLocalInferenceGate",
    "build_sample_ollama_local_inference_gate",
]
