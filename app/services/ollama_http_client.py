from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "localhost_only": True,
        "inference_called": False,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaHttpResult:
    ok: bool
    status_code: int
    elapsed_sec: float
    endpoint: str
    data: dict
    error_type: str
    reason: str
    metadata: dict = field(default_factory=_metadata)


class OllamaHttpClient:
    """Small localhost-only wrapper around the Ollama HTTP API."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = str(base_url or "http://127.0.0.1:11434").rstrip("/")

    def get_tags(self, timeout_sec: int = 5) -> OllamaHttpResult:
        endpoint = "/api/tags"
        if not self._is_localhost_base_url():
            return self._blocked(endpoint, "non_localhost_base_url")
        started = time.perf_counter()
        try:
            response = requests.get(
                self.base_url + endpoint,
                timeout=max(1, int(timeout_sec or 5)),
            )
            elapsed = round(time.perf_counter() - started, 3)
            data = response.json() if response.content else {}
            return OllamaHttpResult(
                ok=bool(response.ok),
                status_code=int(response.status_code),
                elapsed_sec=elapsed,
                endpoint=endpoint,
                data=data if isinstance(data, dict) else {},
                error_type="" if response.ok else "http_status_error",
                reason="ok" if response.ok else "http_status_error",
                metadata=self._safe_metadata(endpoint, elapsed, response.status_code),
            )
        except requests.Timeout:
            return self._error(endpoint, started, "timeout")
        except Exception as exc:
            return self._error(endpoint, started, type(exc).__name__)

    def generate(
        self,
        model: str,
        prompt: str,
        timeout_sec: int = 60,
        options: dict | None = None,
        option_profile: str = "",
    ) -> OllamaHttpResult:
        endpoint = "/api/generate"
        if not self._is_localhost_base_url():
            return self._blocked(endpoint, "non_localhost_base_url")
        started = time.perf_counter()
        prompt_text = str(prompt or "")
        try:
            response = requests.post(
                self.base_url + endpoint,
                json={
                    "model": str(model or ""),
                    "prompt": prompt_text,
                    "stream": False,
                    "options": dict(options or {}),
                },
                timeout=max(1, int(timeout_sec or 60)),
            )
            elapsed = round(time.perf_counter() - started, 3)
            data = response.json() if response.content else {}
            safe_data = data if isinstance(data, dict) else {}
            metadata = self._safe_metadata(endpoint, elapsed, response.status_code)
            metadata.update(
                {
                    "inference_called": True,
                    "prompt_chars": len(prompt_text),
                    "response_chars": len(str(safe_data.get("response") or "")),
                    "option_profile": str(option_profile or ""),
                }
            )
            return OllamaHttpResult(
                ok=bool(response.ok),
                status_code=int(response.status_code),
                elapsed_sec=elapsed,
                endpoint=endpoint,
                data=safe_data,
                error_type="" if response.ok else "http_status_error",
                reason="ok" if response.ok else "http_status_error",
                metadata=metadata,
            )
        except requests.Timeout:
            return self._error(endpoint, started, "timeout", inference_called=True)
        except Exception as exc:
            return self._error(endpoint, started, type(exc).__name__, inference_called=True)

    def _is_localhost_base_url(self) -> bool:
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}

    def _safe_metadata(self, endpoint: str, elapsed_sec: float, status_code: int) -> dict:
        metadata = _metadata()
        metadata.update(
            {
                "base_url": self.base_url,
                "endpoint": endpoint,
                "status_code": int(status_code or 0),
                "elapsed_sec": float(elapsed_sec or 0.0),
            }
        )
        return metadata

    def _blocked(self, endpoint: str, reason: str) -> OllamaHttpResult:
        metadata = self._safe_metadata(endpoint, 0.0, 0)
        return OllamaHttpResult(
            ok=False,
            status_code=0,
            elapsed_sec=0.0,
            endpoint=endpoint,
            data={},
            error_type=reason,
            reason=reason,
            metadata=metadata,
        )

    def _error(
        self,
        endpoint: str,
        started: float,
        error_type: str,
        inference_called: bool = False,
    ) -> OllamaHttpResult:
        elapsed = round(time.perf_counter() - started, 3)
        metadata = self._safe_metadata(endpoint, elapsed, 0)
        metadata["inference_called"] = bool(inference_called)
        return OllamaHttpResult(
            ok=False,
            status_code=0,
            elapsed_sec=elapsed,
            endpoint=endpoint,
            data={},
            error_type=str(error_type or "error"),
            reason=str(error_type or "error"),
            metadata=metadata,
        )


def build_sample_ollama_http_client_result() -> OllamaHttpResult:
    return OllamaHttpResult(
        ok=True,
        status_code=200,
        elapsed_sec=0.001,
        endpoint="/api/tags",
        data={"models": [{"name": "mock"}]},
        error_type="",
        reason="ok",
    )


__all__ = [
    "OllamaHttpResult",
    "OllamaHttpClient",
    "build_sample_ollama_http_client_result",
]
