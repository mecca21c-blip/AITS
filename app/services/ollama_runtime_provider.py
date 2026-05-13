from __future__ import annotations

import subprocess
import time
from dataclasses import asdict

from app.services.ai_response_parser import AIResponseParser
from app.services.ollama_inference_timing import OllamaInferenceTimingResult
from app.services.ollama_local_inference_gate import OllamaLocalInferenceGate
from app.services.ollama_provider_bridge import OllamaProviderBridge
from app.services.ollama_response_quality import OllamaResponseQualityChecker
from app.services.ollama_runtime_config import (
    OllamaRuntimeConfig,
    OllamaRuntimeConfigBuilder,
)
from app.services.ollama_runtime_status import (
    OllamaRuntimeStatus,
    OllamaRuntimeStatusProbe,
)
from app.services.ollama_structured_prompt import OllamaStructuredPromptBuilder


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

    def generate_local_one_shot(
        self,
        prompt: str,
        explicit_enable: bool = False,
        timeout_sec: int = 60,
        prompt_profile: str = "compact",
    ) -> dict:
        gate = OllamaLocalInferenceGate().evaluate(
            explicit_enable=bool(explicit_enable),
            timeout_sec=int(timeout_sec or 60),
        )
        profile_name = str(prompt_profile or "compact")
        base = {
            "provider": "ollama",
            "engine": "basic",
            "model": gate.model or self.config.model,
            "explicit_enable": bool(explicit_enable),
            "local_inference_gate": asdict(gate),
            "local_inference_allowed": bool(gate.allowed),
            "actual_inference_called": False,
            "actual_local_inference_called": False,
            "parsed_valid": False,
            "ollama_schema_valid": False,
            "ollama_quality_score": 0.0,
            "ollama_recovery_used": False,
            "ollama_quality_warnings": [],
            "shadow_record_ready": False,
            "suggestion": "skip",
            "next_action": "wait",
            "applied": False,
            "applied_to_action": False,
            "submitted": 0,
            "real_order": False,
            "shadow_only": True,
            "suggestion_only": True,
            "one_shot": True,
            "research_mode": True,
            "prompt_profile": profile_name,
            "elapsed_sec": 0.0,
            "timed_out": False,
            "timing": asdict(
                self._timing(
                    gate.model or self.config.model,
                    profile_name,
                    int(timeout_sec or 60),
                    0.0,
                    False,
                    False,
                    False,
                )
            ),
        }
        if not gate.allowed:
            base["error_type"] = gate.reason
            return base
        exe_path = str(
            ((gate.metadata.get("process_health") or {}).get("executable_path"))
            or "ollama"
        )
        model = str(gate.model or self.config.model)
        final_prompt = self._build_structured_prompt(prompt, profile_name)
        started = time.perf_counter()
        try:
            base["actual_inference_called"] = True
            base["actual_local_inference_called"] = True
            completed = subprocess.run(
                [exe_path, "run", model, final_prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(timeout_sec or 60),
                check=False,
            )
            elapsed = round(time.perf_counter() - started, 3)
            base["elapsed_sec"] = elapsed
            base["model"] = model
            if completed.returncode != 0:
                base["error_type"] = "ollama_run_nonzero_exit"
                base["timing"] = asdict(
                    self._timing(model, profile_name, timeout_sec, elapsed, False, False, False)
                )
                return base
            quality = OllamaResponseQualityChecker().check(
                completed.stdout or "",
                provider="ollama",
            )
            parsed = AIResponseParser().parse_json_response(
                completed.stdout or "",
                provider="ollama",
            )
            shadow_record = parsed.to_shadow_record()
            shadow_record.update(
                {
                    "shadow_only": True,
                    "suggestion_only": True,
                    "applied": False,
                    "applied_to_action": False,
                    "real_order": False,
                    "submitted": 0,
                    "research_mode": True,
                }
            )
            base.update(
                {
                    "parsed_valid": bool(parsed.valid),
                    "ollama_schema_valid": bool(quality.schema_valid),
                    "ollama_quality_score": float(quality.quality_score),
                    "ollama_recovery_used": bool(quality.recovery_used),
                    "ollama_quality_warnings": list(quality.warnings or []),
                    "response_quality": asdict(quality),
                    "shadow_record": shadow_record,
                    "shadow_record_ready": bool(shadow_record),
                    "suggestion": str(parsed.suggestion or "skip"),
                    "next_action": str(parsed.next_action or "wait"),
                    "error_type": None if parsed.valid else (parsed.error or "parse_failed"),
                    "timed_out": False,
                    "timing": asdict(
                        self._timing(
                            model,
                            profile_name,
                            timeout_sec,
                            elapsed,
                            False,
                            True,
                            bool(parsed.valid),
                        )
                    ),
                }
            )
            return base
        except subprocess.TimeoutExpired:
            elapsed = round(time.perf_counter() - started, 3)
            base["elapsed_sec"] = elapsed
            base["timed_out"] = True
            base["timing"] = asdict(
                self._timing(model, profile_name, timeout_sec, elapsed, True, False, False)
            )
            base["error_type"] = "ollama_run_timeout"
            return base
        except Exception as exc:
            elapsed = round(time.perf_counter() - started, 3)
            base["elapsed_sec"] = elapsed
            base["timing"] = asdict(
                self._timing(model, profile_name, timeout_sec, elapsed, False, False, False)
            )
            base["error_type"] = type(exc).__name__
            return base

    def _build_structured_prompt(self, prompt: str, prompt_profile: str = "compact") -> str:
        raw = str(prompt or "").strip()
        if not raw or len(raw) < 40:
            return OllamaStructuredPromptBuilder().build_prompt(
                {"user_prompt": raw},
                profile=prompt_profile,
            )
        wrapper = OllamaStructuredPromptBuilder().build_prompt(
            {"source": "wrapped_prompt"},
            profile=prompt_profile,
        )
        return "\n".join(
            [
                wrapper,
                "User/request context, summarize into the required JSON only:",
                raw[:800],
            ]
        )

    def _timing(
        self,
        model: str,
        prompt_profile: str,
        timeout_sec: int,
        elapsed_sec: float,
        timed_out: bool,
        completed: bool,
        parsed_valid: bool,
    ) -> OllamaInferenceTimingResult:
        return OllamaInferenceTimingResult(
            model=str(model or ""),
            prompt_profile=str(prompt_profile or "compact"),
            timeout_sec=int(timeout_sec or 60),
            elapsed_sec=float(elapsed_sec or 0.0),
            timed_out=bool(timed_out),
            completed=bool(completed),
            parsed_valid=bool(parsed_valid),
        )


def build_sample_ollama_runtime_one_shot() -> dict:
    provider = OllamaRuntimeProvider(
        OllamaRuntimeConfigBuilder().build_default_config(model="mock")
    )
    return provider.generate_one_shot({"symbol": "KRW-BTC"}, dry_run=True)


__all__ = [
    "OllamaRuntimeProvider",
    "build_sample_ollama_runtime_one_shot",
]
