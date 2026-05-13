from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.ollama_http_client import OllamaHttpClient
from app.services.ollama_model_runtime_profile import OllamaModelRuntimeProfile


DEFAULT_BENCHMARK_MODELS = [
    "qwen2.5:latest",
    "llama3.1:latest",
    "mistral:latest",
]


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "runtime": "local_http",
        "benchmark_only": True,
        "prompt_chars": len('Return JSON: {"ok": true}'),
        "num_predict": 16,
        "timeout_sec": 45,
        "shadow_only": True,
        "real_order": False,
        "submitted": 0,
    }


@dataclass
class OllamaModelBenchmarkResult:
    models_tested: int
    completed: int
    timed_out: int
    usable_models: list
    selected_runtime_model: str
    profiles: list
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class OllamaModelBenchmark:
    """Benchmarks tiny local generate calls without attaching to AITS decisions."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.client = OllamaHttpClient(base_url)

    def run(
        self,
        models: list[str] | None = None,
        timeout_sec: int = 45,
        num_predict: int = 16,
    ) -> OllamaModelBenchmarkResult:
        targets = list(models or DEFAULT_BENCHMARK_MODELS)
        profiles: list[OllamaModelRuntimeProfile] = []
        for model in targets:
            profiles.append(
                self.benchmark_model(
                    model=model,
                    timeout_sec=timeout_sec,
                    num_predict=num_predict,
                )
            )
        usable = [p for p in profiles if p.usable_for_basic]
        fastest = sorted(usable, key=lambda item: item.elapsed_sec)[0] if usable else None
        selected = fastest.model if fastest else ""
        metadata = _metadata()
        metadata.update(
            {
                "models": targets,
                "selected_runtime_model": selected,
            }
        )
        return OllamaModelBenchmarkResult(
            models_tested=len(profiles),
            completed=sum(1 for p in profiles if p.completed),
            timed_out=sum(1 for p in profiles if p.timed_out),
            usable_models=[p.model for p in usable],
            selected_runtime_model=selected,
            profiles=[asdict(p) for p in profiles],
            summary_line=self._summary_line(profiles, selected),
            metadata=metadata,
        )

    def benchmark_model(
        self,
        model: str,
        timeout_sec: int = 45,
        num_predict: int = 16,
    ) -> OllamaModelRuntimeProfile:
        result = self.client.generate(
            model=str(model or ""),
            prompt='Return JSON: {"ok": true}',
            timeout_sec=int(timeout_sec or 45),
            options={
                "num_predict": int(num_predict or 16),
                "temperature": 0.0,
                "top_p": 0.8,
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "```"],
            },
            option_profile="benchmark_minimal",
        )
        response_chars = int(result.metadata.get("response_chars") or 0)
        timed_out = result.error_type == "timeout"
        completed = bool(result.ok and not timed_out)
        first_response_available = response_chars > 0
        usable = bool(result.elapsed_sec <= int(timeout_sec or 45) and first_response_available)
        metadata = _metadata()
        metadata.update(
            {
                "model": str(model or ""),
                "http_status_code": result.status_code,
                "endpoint": result.endpoint,
                "inference_called": bool(result.metadata.get("inference_called")),
            }
        )
        return OllamaModelRuntimeProfile(
            model=str(model or ""),
            completed=completed,
            timed_out=bool(timed_out),
            elapsed_sec=float(result.elapsed_sec or 0.0),
            response_chars=response_chars,
            first_response_available=first_response_available,
            usable_for_basic=usable,
            error_type=str(result.error_type or ""),
            metadata=metadata,
        )

    def _summary_line(self, profiles: list[OllamaModelRuntimeProfile], selected: str) -> str:
        if selected:
            return f"Selected BASIC candidate: {selected}"
        if profiles:
            return "No tested model produced a response within the benchmark window."
        return "No models tested."


def build_sample_ollama_model_benchmark() -> OllamaModelBenchmarkResult:
    profile = build_sample_profile = OllamaModelRuntimeProfile(
        model="mock",
        completed=True,
        timed_out=False,
        elapsed_sec=0.1,
        response_chars=12,
        first_response_available=True,
        usable_for_basic=True,
        error_type="",
    )
    return OllamaModelBenchmarkResult(
        models_tested=1,
        completed=1,
        timed_out=0,
        usable_models=[profile.model],
        selected_runtime_model=build_sample_profile.model,
        profiles=[asdict(profile)],
        summary_line="Selected BASIC candidate: mock",
    )


__all__ = [
    "DEFAULT_BENCHMARK_MODELS",
    "OllamaModelBenchmarkResult",
    "OllamaModelBenchmark",
    "build_sample_ollama_model_benchmark",
]
