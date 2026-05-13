from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.ollama_http_health import OllamaHttpHealthChecker


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaHttpInferenceGateResult:
    allowed: bool
    provider: str
    model: str
    reason: str
    explicit_enable: bool
    http_ready: bool
    model_ready: bool
    timeout_sec: int
    metadata: dict = field(default_factory=_metadata)


class OllamaHttpInferenceGate:
    """Explicit gate for one-shot local HTTP generation."""

    def evaluate(
        self,
        explicit_enable: bool = False,
        timeout_sec: int = 60,
    ) -> OllamaHttpInferenceGateResult:
        timeout = int(timeout_sec) if timeout_sec is not None else 60
        health = OllamaHttpHealthChecker().check(timeout_sec=min(max(timeout, 1), 10))
        metadata = _metadata()
        metadata["http_health"] = asdict(health)
        if not explicit_enable:
            return self._result(False, health, "explicit_enable_required", explicit_enable, timeout, metadata)
        if timeout <= 0:
            return self._result(False, health, "invalid_timeout", explicit_enable, timeout, metadata)
        if not health.available:
            return self._result(False, health, health.reason or "http_unavailable", explicit_enable, timeout, metadata)
        if not health.selected_model_found:
            return self._result(False, health, "model_missing", explicit_enable, timeout, metadata)
        return self._result(True, health, "allowed", explicit_enable, timeout, metadata)

    def _result(
        self,
        allowed: bool,
        health,
        reason: str,
        explicit_enable: bool,
        timeout_sec: int,
        metadata: dict,
    ) -> OllamaHttpInferenceGateResult:
        return OllamaHttpInferenceGateResult(
            allowed=bool(allowed),
            provider="ollama",
            model=str(getattr(health, "selected_model", "") or ""),
            reason=str(reason or ""),
            explicit_enable=bool(explicit_enable),
            http_ready=bool(getattr(health, "available", False)),
            model_ready=bool(getattr(health, "selected_model_found", False)),
            timeout_sec=int(timeout_sec or 60),
            metadata=metadata,
        )


def build_sample_ollama_http_inference_gate() -> OllamaHttpInferenceGateResult:
    return OllamaHttpInferenceGate().evaluate(explicit_enable=False)


__all__ = [
    "OllamaHttpInferenceGateResult",
    "OllamaHttpInferenceGate",
    "build_sample_ollama_http_inference_gate",
]
