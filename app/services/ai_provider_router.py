from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.ai_provider_mock_bridge import AIProviderMockBridge
from app.services.gemini_provider_bridge import GeminiProviderBridge
from app.services.gpt_provider_bridge import GPTProviderBridge
from app.services.ollama_provider_bridge import OllamaProviderBridge


class AIProviderRouter:
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
        self.openai_model = str(openai_model or "gpt-5.5-instant")
        self.gemini_model = str(gemini_model or "gemini-2.5-flash")
        self.ollama_model = str(ollama_model or "qwen2.5:7b-instruct-q4")

    def run_shadow_cycle(
        self,
        provider: str,
        context_dict: dict,
        dry_run: bool = True,
    ) -> dict:
        selected_provider = str(provider or "ollama")
        normalized_provider = self._normalize_provider(selected_provider)
        if bool(dry_run):
            result = AIProviderMockBridge().run_mock_cycle(normalized_provider)
            result["dry_run"] = True
        else:
            bridge = self._build_bridge(normalized_provider)
            result = bridge.run_shadow_cycle(
                dict(context_dict or {}),
                dry_run=False,
            )
        if "shadow_record" not in result:
            result["shadow_record"] = {}
        result["selected_provider"] = selected_provider
        result["normalized_provider"] = normalized_provider

        self._safe_log_info(
            "[AITS][AIProviderRouter] provider_routed"
            f" | selected={selected_provider}"
            f" | normalized={normalized_provider}"
            f" | dry_run={bool(dry_run)}"
            f" | parsed_valid={result.get('parsed_valid')}"
        )
        return result

    def _normalize_provider(self, provider: str) -> str:
        provider_norm = str(provider or "").strip().lower()
        if provider_norm in ("gpt", "openai"):
            return "openai"
        if provider_norm == "gemini":
            return "gemini"
        if provider_norm in ("ollama", "local", "local_ai"):
            return "ollama"
        return "ollama"

    def _build_bridge(self, normalized_provider: str) -> Any:
        if normalized_provider == "openai":
            return GPTProviderBridge(
                api_key=self.openai_api_key,
                model=self.openai_model,
            )
        if normalized_provider == "gemini":
            return GeminiProviderBridge(
                api_key=self.gemini_api_key,
                model=self.gemini_model,
            )
        return OllamaProviderBridge(model=self.ollama_model)

    def _safe_log_info(self, message: str) -> None:
        # Do not log keys, prompt bodies, response bodies, or order data.
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass
