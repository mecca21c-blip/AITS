from __future__ import annotations

import logging
from dataclasses import dataclass, field


@dataclass
class ProviderRuntimeStatus:
    provider: str
    available: bool
    key_ready: bool
    model_ready: bool
    runtime_ready: bool
    dry_run_supported: bool
    live_supported: bool
    reason: str
    metadata: dict = field(default_factory=dict)


class ProviderRuntimeValidator:
    """Provider runtime validator for shadow-only one-shot diagnostics."""

    _PROVIDER_ALIASES = {
        "gpt": "openai",
        "openai": "openai",
        "gemini": "gemini",
        "ollama": "ollama",
        "local": "ollama",
        "local_ai": "ollama",
        "mock": "mock",
    }

    def __init__(
        self,
        openai_api_key: str | None = None,
        gemini_api_key: str | None = None,
        openai_model: str = "gpt-5.5-instant",
        gemini_model: str = "gemini-2.5-flash",
        ollama_model: str = "qwen2.5:7b-instruct-q4",
    ) -> None:
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.openai_model = str(openai_model or "").strip()
        self.gemini_model = str(gemini_model or "").strip()
        self.ollama_model = str(ollama_model or "").strip()
        self._log = logging.getLogger("aits")

    def normalize_provider(self, provider: str) -> str:
        name = str(provider or "").strip().lower()
        return self._PROVIDER_ALIASES.get(name, name or "unknown")

    def validate(self, provider: str) -> ProviderRuntimeStatus:
        normalized = self.normalize_provider(provider)
        if normalized not in {"openai", "gemini", "ollama", "mock"}:
            return self._status(
                provider=normalized,
                available=False,
                key_ready=False,
                model_ready=False,
                runtime_ready=False,
                dry_run_supported=False,
                live_supported=False,
                reason="unknown_provider",
                metadata={"requested_provider": str(provider or "")},
            )

        if normalized == "openai":
            key_ready = bool(str(self.openai_api_key or "").strip())
            model_ready = bool(self.openai_model)
            runtime_ready = key_ready and model_ready
            return self._status(
                provider=normalized,
                available=True,
                key_ready=key_ready,
                model_ready=model_ready,
                runtime_ready=runtime_ready,
                dry_run_supported=True,
                live_supported=runtime_ready,
                reason="ready" if runtime_ready else "missing_key_or_model",
                metadata={"key_required": True, "model": self.openai_model},
            )

        if normalized == "gemini":
            key_ready = bool(str(self.gemini_api_key or "").strip())
            model_ready = bool(self.gemini_model)
            runtime_ready = key_ready and model_ready
            return self._status(
                provider=normalized,
                available=True,
                key_ready=key_ready,
                model_ready=model_ready,
                runtime_ready=runtime_ready,
                dry_run_supported=True,
                live_supported=runtime_ready,
                reason="ready" if runtime_ready else "missing_key_or_model",
                metadata={"key_required": True, "model": self.gemini_model},
            )

        if normalized == "ollama":
            model_ready = bool(self.ollama_model)
            return self._status(
                provider=normalized,
                available=True,
                key_ready=True,
                model_ready=model_ready,
                runtime_ready=model_ready,
                dry_run_supported=True,
                live_supported=model_ready,
                reason="ready" if model_ready else "missing_model",
                metadata={
                    "key_required": False,
                    "model": self.ollama_model,
                    "local_runtime": True,
                    "ollama_reachable_checked": False,
                },
            )

        return self._status(
            provider="mock",
            available=True,
            key_ready=True,
            model_ready=True,
            runtime_ready=True,
            dry_run_supported=True,
            live_supported=False,
            reason="mock_dry_run_only",
            metadata={"key_required": False, "model": "mock"},
        )

    def _status(
        self,
        provider: str,
        available: bool,
        key_ready: bool,
        model_ready: bool,
        runtime_ready: bool,
        dry_run_supported: bool,
        live_supported: bool,
        reason: str,
        metadata: dict | None = None,
    ) -> ProviderRuntimeStatus:
        safe_metadata = dict(metadata or {})
        safe_metadata.update(
            {
                "real_order": False,
                "submitted": 0,
                "shadow_only": True,
                "one_shot": True,
            }
        )
        status = ProviderRuntimeStatus(
            provider=provider,
            available=bool(available),
            key_ready=bool(key_ready),
            model_ready=bool(model_ready),
            runtime_ready=bool(runtime_ready),
            dry_run_supported=bool(dry_run_supported),
            live_supported=bool(live_supported),
            reason=str(reason or "unknown"),
            metadata=safe_metadata,
        )
        try:
            self._log.info(
                "[AITS][ProviderRuntime] runtime_validated | provider=%s | available=%s | dry_run=%s | live_supported=%s",
                status.provider,
                status.available,
                status.dry_run_supported,
                status.live_supported,
            )
        except Exception:
            pass
        return status


def build_sample_runtime_status() -> ProviderRuntimeStatus:
    return ProviderRuntimeValidator().validate("mock")


__all__ = [
    "ProviderRuntimeStatus",
    "ProviderRuntimeValidator",
    "build_sample_runtime_status",
]
