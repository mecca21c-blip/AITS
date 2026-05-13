from __future__ import annotations

from dataclasses import asdict

from app.services.ollama_provider_bridge import OllamaProviderBridge
from app.services.ollama_runtime_config import (
    OllamaRuntimeConfig,
    OllamaRuntimeConfigBuilder,
)
from app.services.ollama_runtime_status import (
    OllamaRuntimeStatus,
    OllamaRuntimeStatusProbe,
)


class OllamaRuntimeProvider:
    """BASIC(Local) runtime facade for shadow-only one-shot inference skeletons."""

    def __init__(self, config: OllamaRuntimeConfig | None = None) -> None:
        self.config = config or OllamaRuntimeConfigBuilder().build_default_config()
        self._status_probe = OllamaRuntimeStatusProbe()

    def get_status(self) -> OllamaRuntimeStatus:
        return self._status_probe.check_status(self.config)

    def generate_one_shot(
        self,
        context_dict: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        status = self.get_status()
        bridge = OllamaProviderBridge(
            model=self.config.model,
            base_url=self.config.base_url,
            timeout=self.config.timeout_sec,
        )
        result = bridge.run_shadow_cycle(dict(context_dict or {}), dry_run=True)
        result.update(
            {
                "provider": "ollama",
                "engine": "basic",
                "model": self.config.model,
                "dry_run": True,
                "requested_dry_run": bool(dry_run),
                "runtime_status": asdict(status),
                "runtime_ready": bool(status.runtime_ready),
                "local_runtime": True,
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
                "research_mode": True,
            }
        )
        return result


def build_sample_ollama_runtime_one_shot() -> dict:
    provider = OllamaRuntimeProvider(
        OllamaRuntimeConfigBuilder().build_default_config(model="mock")
    )
    return provider.generate_one_shot({"symbol": "KRW-BTC"}, dry_run=True)


__all__ = [
    "OllamaRuntimeProvider",
    "build_sample_ollama_runtime_one_shot",
]
