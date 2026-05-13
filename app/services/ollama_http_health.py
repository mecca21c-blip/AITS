from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ollama_http_client import OllamaHttpClient


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "inference_called": False,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaHttpHealthResult:
    available: bool
    base_url: str
    tags_ok: bool
    model_count: int
    models: list
    selected_model: str
    selected_model_found: bool
    reason: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class OllamaHttpHealthChecker:
    """Checks local Ollama HTTP availability through /api/tags only."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = str(base_url or "http://127.0.0.1:11434")

    def check(self, timeout_sec: int = 5) -> OllamaHttpHealthResult:
        warnings: list[str] = []
        client = OllamaHttpClient(self.base_url)
        result = client.get_tags(timeout_sec=timeout_sec)
        models = self._extract_model_names(result.data)
        selected_model = self._select_model(models)
        if not result.ok:
            warnings.append(result.reason)
        if result.ok and not models:
            warnings.append("no_models")
        metadata = _metadata()
        metadata.update(
            {
                "base_url": self.base_url,
                "tags_status_code": result.status_code,
                "tags_elapsed_sec": result.elapsed_sec,
                "client_reason": result.reason,
            }
        )
        return OllamaHttpHealthResult(
            available=bool(result.ok and selected_model),
            base_url=self.base_url,
            tags_ok=bool(result.ok),
            model_count=len(models),
            models=models,
            selected_model=selected_model,
            selected_model_found=bool(selected_model),
            reason="ok" if result.ok and selected_model else (result.reason or "model_missing"),
            warnings=list(dict.fromkeys(warnings)),
            metadata=metadata,
        )

    def _extract_model_names(self, data: dict) -> list[str]:
        raw_models = data.get("models") if isinstance(data, dict) else []
        names: list[str] = []
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("model") or "").strip()
                else:
                    name = str(item or "").strip()
                if name:
                    names.append(name)
        return names

    def _select_model(self, models: list[str]) -> str:
        lowered = [(name, name.lower()) for name in models]
        for needle in ("qwen2.5", "qwen", "llama", "mistral"):
            for original, lower in lowered:
                if needle in lower:
                    return original
        return models[0] if models else ""


def build_sample_ollama_http_health() -> OllamaHttpHealthResult:
    return OllamaHttpHealthResult(
        available=True,
        base_url="http://127.0.0.1:11434",
        tags_ok=True,
        model_count=1,
        models=["mock"],
        selected_model="mock",
        selected_model_found=True,
        reason="ok",
        warnings=[],
    )


__all__ = [
    "OllamaHttpHealthResult",
    "OllamaHttpHealthChecker",
    "build_sample_ollama_http_health",
]
