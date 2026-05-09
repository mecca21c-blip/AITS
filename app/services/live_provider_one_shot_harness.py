from __future__ import annotations

import logging
from dataclasses import asdict

from app.services.ai_context_builder import build_sample_context_pack
from app.services.ai_provider_router import AIProviderRouter
from app.services.ai_response_quality_score import AIResponseQualityScorer
from app.services.ai_response_schema_validator import AIResponseSchemaValidator
from app.services.ai_state_machine import (
    AIStateMachine,
    format_state_snapshot_for_ui,
)
from app.services.provider_capability_matrix import ProviderCapabilityMatrix
from app.services.provider_cooldown_manager import ProviderCooldownManager
from app.services.provider_guard_report import ProviderGuardReportBuilder
from app.services.provider_health_monitor import ProviderHealthMonitor
from app.services.provider_one_shot_report import ProviderOneShotReportBuilder
from app.services.provider_runtime_validator import ProviderRuntimeValidator
from app.services.provider_retry_policy import ProviderRetryPolicy
from app.services.provider_timeout_guard import ProviderTimeoutGuard


class LiveProviderOneShotHarness:
    """Shadow-only one-shot provider harness. It never submits orders."""

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
        self._log = logging.getLogger("aits")
        self._runtime_validator = ProviderRuntimeValidator(
            openai_api_key=self.openai_api_key,
            gemini_api_key=self.gemini_api_key,
            openai_model=self.openai_model,
            gemini_model=self.gemini_model,
            ollama_model=self.ollama_model,
        )
        self._capability_matrix = ProviderCapabilityMatrix()
        self._report_builder = ProviderOneShotReportBuilder()
        self._schema_validator = AIResponseSchemaValidator()
        self._quality_scorer = AIResponseQualityScorer()
        self._timeout_guard = ProviderTimeoutGuard()
        self._retry_policy = ProviderRetryPolicy()
        self._cooldown_manager = ProviderCooldownManager()
        self._health_monitor = ProviderHealthMonitor()
        self._guard_report_builder = ProviderGuardReportBuilder()

    def run_one_shot(
        self,
        provider: str,
        context_dict: dict | None = None,
        allow_live: bool = False,
    ) -> dict:
        provider_name = self._runtime_validator.normalize_provider(provider)
        runtime_status = self._runtime_validator.validate(provider_name)
        capability = self._capability_matrix.get_capability(provider_name)
        capability_ready = capability is not None
        guard_bundle = self._build_guard_bundle(provider_name, error_type=None)
        guard_report = guard_bundle["guard_report"]
        live_allowed = self._is_live_allowed(
            bool(allow_live),
            runtime_status,
            capability,
            guard_report,
        )
        safety_blocked = (
            (not runtime_status.available)
            or bool(guard_bundle["cooldown_blocked"])
            or (bool(allow_live) and not live_allowed)
        )
        if not runtime_status.available:
            output = self._build_fallback_output(
                provider_name=provider_name,
                allow_live=bool(allow_live),
                runtime_status=runtime_status,
                capability=capability,
                capability_ready=capability_ready,
                live_allowed=False,
                safety_blocked=True,
                error_type="unknown_provider",
                guard_bundle=guard_bundle,
            )
            self._log_result(output)
            return output
        try:
            context = (
                dict(context_dict)
                if isinstance(context_dict, dict)
                else build_sample_context_pack().to_compact_dict()
            )
            dry_run = not live_allowed
            result = AIProviderRouter(
                openai_api_key=self.openai_api_key,
                gemini_api_key=self.gemini_api_key,
                openai_model=self.openai_model,
                gemini_model=self.gemini_model,
                ollama_model=self.ollama_model,
            ).run_shadow_cycle(
                provider_name,
                context,
                dry_run=dry_run,
            )

            shadow_record = result.get("shadow_record") if isinstance(result, dict) else {}
            if not isinstance(shadow_record, dict):
                shadow_record = {}
            validation = self._schema_validator.validate(shadow_record)
            quality_score = self._quality_scorer.score(shadow_record, validation)
            recovery_used = bool(
                (shadow_record.get("metadata") or {}).get("recovery_used")
            ) if isinstance(shadow_record.get("metadata"), dict) else False
            symbol = str(
                shadow_record.get("symbol")
                or shadow_record.get("market")
                or context.get("symbol")
                or "KRW-BTC"
            ).strip() or "KRW-BTC"
            snapshot = AIStateMachine().transition(
                symbol=symbol,
                current_state="idle",
                ai_shadow_record=shadow_record,
            )
            state_ui = format_state_snapshot_for_ui(snapshot)
            output = {
                "provider": provider_name,
                "allow_live": bool(allow_live),
                "one_shot": True,
                "shadow_only": True,
                "parsed_valid": bool(result.get("parsed_valid")) if isinstance(result, dict) else False,
                "shadow_record_ready": bool(shadow_record),
                "state_ready": snapshot is not None,
                "state_ui_ready": bool(state_ui),
                "suggestion": str(
                    result.get("suggestion")
                    or shadow_record.get("suggestion")
                    or "skip"
                ),
                "next_action": str(
                    result.get("next_action")
                    or shadow_record.get("next_action")
                    or "wait"
                ),
                "state": str(getattr(snapshot, "state", "") or ""),
                "status_line": str(state_ui.get("status_line") or ""),
                "applied": False,
                "applied_to_action": False,
                "submitted": 0,
                "real_order": False,
                "runtime_ready": bool(runtime_status.runtime_ready),
                "capability_ready": bool(capability_ready),
                "report_ready": False,
                "live_allowed": bool(live_allowed),
                "safety_blocked": bool(safety_blocked),
                "runtime_status": asdict(runtime_status),
                "capability": asdict(capability) if capability is not None else {},
                **self._guard_output_fields(guard_bundle),
                "schema_valid": bool(validation.valid),
                "response_quality_score": float(quality_score.quality_score),
                "response_quality_ready": True,
                "recovery_used": recovery_used,
                "quality_warnings": list(quality_score.warnings or []),
                "schema_validation": asdict(validation),
                "response_quality": asdict(quality_score),
            }
            report = self._report_builder.build_report(output, runtime_status=runtime_status)
            output["report"] = asdict(report)
            output["report_ready"] = True
            self._health_monitor.record_success(provider_name)
            self._log_result(output)
            return output
        except Exception as exc:
            self._health_monitor.record_failure(provider_name, type(exc).__name__)
            failure_guard_bundle = self._build_guard_bundle(
                provider_name,
                error_type=type(exc).__name__,
            )
            output = self._build_fallback_output(
                provider_name=provider_name,
                allow_live=bool(allow_live),
                runtime_status=runtime_status,
                capability=capability,
                capability_ready=capability_ready,
                live_allowed=live_allowed,
                safety_blocked=True,
                error_type=type(exc).__name__,
                guard_bundle=failure_guard_bundle,
            )
            self._log_result(output)
            return output

    def _is_live_allowed(self, allow_live: bool, runtime_status, capability, guard_report) -> bool:
        if not allow_live or capability is None:
            return False
        return bool(
            runtime_status.available
            and runtime_status.key_ready
            and runtime_status.model_ready
            and runtime_status.runtime_ready
            and runtime_status.live_supported
            and capability.live_one_shot
            and getattr(guard_report, "runtime_allowed", False)
        )

    def _build_guard_bundle(self, provider_name: str, error_type: str | None) -> dict:
        timeout_policy = self._timeout_guard.get_policy(provider_name)
        retry_decision = self._retry_policy.decide(provider_name, error_type, 0)
        cooldown_state = self._cooldown_manager.get_state(provider_name)
        health_status = self._health_monitor.get_status(provider_name)
        guard_report = self._guard_report_builder.build_report(
            provider_name,
            timeout_policy=timeout_policy,
            retry_decision=retry_decision,
            cooldown_state=cooldown_state,
            health_status=health_status,
        )
        return {
            "timeout_policy": timeout_policy,
            "retry_decision": retry_decision,
            "cooldown_state": cooldown_state,
            "health_status": health_status,
            "guard_report": guard_report,
            "cooldown_blocked": bool(guard_report.cooldown_blocked),
        }

    def _guard_output_fields(self, guard_bundle: dict) -> dict:
        guard_report = guard_bundle["guard_report"]
        cooldown_state = guard_bundle.get("cooldown_state")
        return {
            "timeout_policy": asdict(guard_bundle["timeout_policy"]),
            "retry_decision": asdict(guard_bundle["retry_decision"]),
            "cooldown_state": asdict(cooldown_state) if cooldown_state is not None else {},
            "health_status": asdict(guard_bundle["health_status"]),
            "guard_report": asdict(guard_report),
            "guard_ready": True,
            "runtime_allowed": bool(guard_report.runtime_allowed),
            "cooldown_blocked": bool(guard_report.cooldown_blocked),
            "degraded": bool(guard_report.degraded),
            "retry_allowed": bool(guard_report.retry_allowed),
            "timeout_sec": int(guard_report.timeout_sec),
            "guard_reason": str(guard_report.reason or ""),
        }

    def _build_fallback_output(
        self,
        provider_name: str,
        allow_live: bool,
        runtime_status,
        capability,
        capability_ready: bool,
        live_allowed: bool,
        safety_blocked: bool,
        error_type: str,
        guard_bundle: dict | None = None,
    ) -> dict:
        if guard_bundle is None:
            guard_bundle = self._build_guard_bundle(provider_name, error_type=error_type)
        output = {
            "provider": provider_name,
            "allow_live": bool(allow_live),
            "one_shot": True,
            "shadow_only": True,
            "parsed_valid": False,
            "shadow_record_ready": False,
            "state_ready": False,
            "state_ui_ready": False,
            "suggestion": "skip",
            "next_action": "wait",
            "state": "idle",
            "status_line": "",
            "applied": False,
            "applied_to_action": False,
            "submitted": 0,
            "real_order": False,
            "runtime_ready": bool(getattr(runtime_status, "runtime_ready", False)),
            "capability_ready": bool(capability_ready),
            "report_ready": False,
            "live_allowed": bool(live_allowed),
            "safety_blocked": bool(safety_blocked),
            "runtime_status": asdict(runtime_status),
            "capability": asdict(capability) if capability is not None else {},
            "error_type": str(error_type or "error"),
            **self._guard_output_fields(guard_bundle),
            "schema_valid": False,
            "response_quality_score": 0.0,
            "response_quality_ready": False,
            "recovery_used": False,
            "quality_warnings": [],
        }
        report = self._report_builder.build_report(output, runtime_status=runtime_status)
        output["report"] = asdict(report)
        output["report_ready"] = True
        return output

    def _log_result(self, output: dict) -> None:
        try:
            self._log.info(
                "[AITS][LiveProviderOneShot] one_shot_done | provider=%s | allow_live=%s | parsed_valid=%s | submitted=0",
                output.get("provider"),
                bool(output.get("allow_live")),
                bool(output.get("parsed_valid")),
            )
        except Exception:
            pass


__all__ = ["LiveProviderOneShotHarness"]
