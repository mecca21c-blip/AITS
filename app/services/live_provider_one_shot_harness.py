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
        session_store = None
        session = None
        try:
            from app.services.ai_runtime_session_store import AIRuntimeSessionStore

            session_store = AIRuntimeSessionStore()
            session = session_store.create_session(
                provider_name,
                model=self._model_for_provider(provider_name),
            )
        except Exception:
            session_store = None
            session = None
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
            output = self._attach_observation(output)
            output = self._attach_runtime_session(output, session_store, session)
            output = self._attach_runtime_ui(output)
            output = self._attach_runtime_events(output)
            output = self._attach_runtime_incidents(output)
            output = self._attach_runtime_snapshot(output)
            output = self._attach_runtime_capability(output)
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
            output = self._attach_observation(output, symbol=symbol)
            output = self._attach_runtime_session(output, session_store, session)
            output = self._attach_runtime_ui(output)
            output = self._attach_runtime_events(output)
            output = self._attach_runtime_incidents(output)
            output = self._attach_runtime_snapshot(output)
            output = self._attach_runtime_capability(output)
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
            output = self._attach_observation(output)
            output = self._attach_runtime_session(output, session_store, session)
            output = self._attach_runtime_ui(output)
            output = self._attach_runtime_events(output)
            output = self._attach_runtime_incidents(output)
            output = self._attach_runtime_snapshot(output)
            output = self._attach_runtime_capability(output)
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

    def _model_for_provider(self, provider_name: str) -> str:
        normalized = str(provider_name or "").strip().lower()
        if normalized == "openai":
            return self.openai_model
        if normalized == "gemini":
            return self.gemini_model
        if normalized == "ollama":
            return self.ollama_model
        return "-"

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

    def _attach_observation(self, output: dict, symbol: str = "KRW-BTC") -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_observation_pipeline import AIObservationPipeline
            from app.services.ai_observation_report_formatter import (
                AIObservationReportFormatter,
            )

            pipeline_result = AIObservationPipeline().run_once(safe_output, symbol=symbol)
            observation_report = dict(pipeline_result.get("report") or {})
            formatted = AIObservationReportFormatter().format_report(observation_report)
            safe_output.update(
                {
                    "observation_ready": bool(pipeline_result.get("report_ready")),
                    "observation_health_label": str(
                        pipeline_result.get("health_label") or ""
                    ),
                    "observation_summary_line": str(
                        pipeline_result.get("summary_line") or ""
                    ),
                    "observation_report": observation_report,
                    "observation_formatted": formatted,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "observation_ready": False,
                    "observation_health_label": "",
                    "observation_summary_line": "",
                    "observation_report": {},
                    "observation_formatted": {},
                    "observation_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _attach_runtime_session(self, output: dict, session_store, session) -> dict:
        safe_output = dict(output or {})
        if session_store is None or session is None:
            safe_output.update(
                {
                    "session_ready": False,
                    "session_id": "",
                    "session_status": "",
                    "session_diagnosis": "",
                    "session_report": {},
                    "runtime_memory_summary": {},
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
            return safe_output

        try:
            from app.services.ai_runtime_memory import AIRuntimeMemory
            from app.services.ai_session_diagnostics import AISessionDiagnosticsBuilder
            from app.services.ai_session_report import AISessionReportBuilder

            error = bool(safe_output.get("error_type"))
            success = bool(safe_output.get("report_ready")) and not error
            session_store.record_one_shot(
                session.session_id,
                success=success,
                error=error,
            )
            if bool(safe_output.get("observation_ready")):
                session_store.record_observation(session.session_id)
            session_store.mark_degraded(
                session.session_id,
                bool(safe_output.get("degraded", False)),
            )
            session_store.mark_cooldown(
                session.session_id,
                bool(safe_output.get("cooldown_blocked", False)),
            )

            memory = AIRuntimeMemory()
            if isinstance(safe_output.get("observation_report"), dict):
                memory.set_item(
                    session.session_id,
                    "last_observation_report",
                    safe_output["observation_report"],
                )
            if isinstance(safe_output.get("response_quality"), dict):
                memory.set_item(
                    session.session_id,
                    "last_quality_score",
                    safe_output["response_quality"],
                )
            else:
                memory.set_item(
                    session.session_id,
                    "last_quality_score",
                    {"quality_score": safe_output.get("response_quality_score", 0.0)},
                )
            if isinstance(safe_output.get("guard_report"), dict):
                memory.set_item(
                    session.session_id,
                    "last_guard_report",
                    safe_output["guard_report"],
                )
            memory.set_item(
                session.session_id,
                "last_state_ui",
                {
                    "state": safe_output.get("state", ""),
                    "status_line": safe_output.get("status_line", ""),
                    "state_ready": bool(safe_output.get("state_ready", False)),
                    "state_ui_ready": bool(safe_output.get("state_ui_ready", False)),
                },
            )
            memory_summary = memory.build_summary()
            diagnostics = AISessionDiagnosticsBuilder().build(
                session,
                observation_report=safe_output.get("observation_report"),
                guard_report=safe_output.get("guard_report"),
                quality_score=safe_output.get("response_quality"),
            )
            session_report = AISessionReportBuilder().build_report(
                session,
                diagnostics=diagnostics,
                memory_summary=memory_summary,
            )
            safe_output.update(
                {
                    "session_ready": True,
                    "session_id": str(session.session_id or ""),
                    "session_status": str(session.status or ""),
                    "session_diagnosis": str(diagnostics.diagnosis or ""),
                    "session_report": asdict(session_report),
                    "runtime_memory_summary": memory_summary,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "session_ready": False,
                    "session_id": str(getattr(session, "session_id", "") or ""),
                    "session_status": str(getattr(session, "status", "") or ""),
                    "session_diagnosis": "",
                    "session_report": {},
                    "runtime_memory_summary": {},
                    "session_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _attach_runtime_ui(self, output: dict) -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_runtime_badge_builder import AIRuntimeBadgeBuilder
            from app.services.ai_runtime_dashboard_summary import (
                AIRuntimeDashboardSummaryBuilder,
            )
            from app.services.ai_runtime_status_color import AIRuntimeStatusColorResolver
            from app.services.ai_runtime_ui_bundle import AIRuntimeUIBundleBuilder
            from app.services.ai_runtime_ui_formatter import AIRuntimeUIFormatter

            bundle = AIRuntimeUIBundleBuilder().build_bundle(
                safe_output,
                session_report=safe_output.get("session_report"),
                observation_report=safe_output.get("observation_report"),
                guard_report=safe_output.get("guard_report"),
                quality_score=safe_output.get("response_quality"),
            )
            badges = AIRuntimeBadgeBuilder().build_badges(bundle)
            bundle.badges = badges
            formatted = AIRuntimeUIFormatter().format_bundle(bundle)
            dashboard_summary = AIRuntimeDashboardSummaryBuilder().build_summary([bundle])
            colors = AIRuntimeStatusColorResolver().resolve(bundle.diagnosis)
            safe_output.update(
                {
                    "runtime_ui_ready": True,
                    "runtime_ui_bundle": asdict(bundle),
                    "runtime_ui_formatted": formatted,
                    "runtime_dashboard_summary": asdict(dashboard_summary),
                    "runtime_badges": badges,
                    "runtime_status_colors": colors,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "runtime_ui_ready": False,
                    "runtime_ui_bundle": {},
                    "runtime_ui_formatted": {},
                    "runtime_dashboard_summary": {},
                    "runtime_badges": [],
                    "runtime_status_colors": {},
                    "runtime_ui_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _attach_runtime_events(self, output: dict) -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_runtime_event import build_runtime_event
            from app.services.ai_runtime_event_formatter import AIRuntimeEventFormatter
            from app.services.ai_runtime_event_stream import AIRuntimeEventStream
            from app.services.ai_runtime_event_summary import AIRuntimeEventSummaryBuilder
            from app.services.ai_runtime_timeline import AIRuntimeTimelineBuilder

            provider = str(safe_output.get("provider") or "unknown")
            session_id = str(safe_output.get("session_id") or "")
            symbol = self._symbol_from_result(safe_output)
            stream = AIRuntimeEventStream()
            events = [
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="one_shot_started",
                    severity="info",
                    title="One-shot started",
                    message=f"{provider} one-shot started",
                    source="live_provider_one_shot_harness",
                ),
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="guard_checked",
                    severity="warning" if safe_output.get("degraded") else "info",
                    title="Guard checked",
                    message=str(safe_output.get("guard_reason") or "runtime guard checked"),
                    source="provider_guard_report",
                    metadata={
                        "guard_ready": bool(safe_output.get("guard_ready", False)),
                        "degraded": bool(safe_output.get("degraded", False)),
                        "cooldown_blocked": bool(safe_output.get("cooldown_blocked", False)),
                    },
                ),
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="quality_scored",
                    severity="warning"
                    if float(safe_output.get("response_quality_score") or 0.0) < 0.4
                    else "info",
                    title="Quality scored",
                    message=f"quality={float(safe_output.get('response_quality_score') or 0.0):.2f}",
                    source="ai_response_quality_score",
                    metadata={
                        "quality_ready": bool(safe_output.get("response_quality_ready", False)),
                        "quality_score": float(safe_output.get("response_quality_score") or 0.0),
                    },
                ),
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="observation_recorded",
                    severity="info" if safe_output.get("observation_ready") else "warning",
                    title="Observation recorded",
                    message=str(safe_output.get("observation_summary_line") or "observation unavailable"),
                    source="ai_observation_pipeline",
                    metadata={
                        "observation_ready": bool(safe_output.get("observation_ready", False)),
                        "health_label": str(safe_output.get("observation_health_label") or ""),
                    },
                ),
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="session_reported",
                    severity="info" if safe_output.get("session_ready") else "warning",
                    title="Session reported",
                    message=str(safe_output.get("session_diagnosis") or "session unavailable"),
                    source="ai_session_report",
                    metadata={
                        "session_ready": bool(safe_output.get("session_ready", False)),
                        "session_status": str(safe_output.get("session_status") or ""),
                    },
                ),
            ]
            if bool(safe_output.get("safety_blocked")):
                events.append(
                    build_runtime_event(
                        session_id=session_id,
                        provider=provider,
                        symbol=symbol,
                        event_type="safety_blocked",
                        severity="critical",
                        title="Safety blocked",
                        message="one-shot remained blocked by runtime safety",
                        source="live_provider_one_shot_harness",
                    )
                )
            observation_report = safe_output.get("observation_report")
            if isinstance(observation_report, dict):
                if bool(observation_report.get("anomaly_detected", False)):
                    events.append(
                        build_runtime_event(
                            session_id=session_id,
                            provider=provider,
                            symbol=symbol,
                            event_type="anomaly_detected",
                            severity="warning",
                            title="Anomaly detected",
                            message="observation anomaly detected",
                            source="ai_observation_report",
                        )
                    )
                if bool(observation_report.get("confidence_drift", False)) or bool(
                    observation_report.get("scenario_drift", False)
                ):
                    events.append(
                        build_runtime_event(
                            session_id=session_id,
                            provider=provider,
                            symbol=symbol,
                            event_type="drift_detected",
                            severity="warning",
                            title="Drift detected",
                            message="runtime observation drift detected",
                            source="ai_observation_report",
                            metadata={
                                "confidence_drift": bool(
                                    observation_report.get("confidence_drift", False)
                                ),
                                "scenario_drift": bool(
                                    observation_report.get("scenario_drift", False)
                                ),
                            },
                        )
                    )
            events.append(
                build_runtime_event(
                    session_id=session_id,
                    provider=provider,
                    symbol=symbol,
                    event_type="one_shot_completed",
                    severity="error" if safe_output.get("error_type") else "info",
                    title="One-shot completed",
                    message=str(safe_output.get("status_line") or "one-shot completed"),
                    source="live_provider_one_shot_harness",
                    metadata={
                        "report_ready": bool(safe_output.get("report_ready", False)),
                        "runtime_ui_ready": bool(safe_output.get("runtime_ui_ready", False)),
                    },
                )
            )
            for event in events:
                stream.append(event)
            event_list = stream.list_events()
            timeline = AIRuntimeTimelineBuilder().build_timeline(event_list)
            formatter = AIRuntimeEventFormatter()
            feed = [formatter.format_timeline_item(item) for item in timeline]
            summary = AIRuntimeEventSummaryBuilder().build_report(event_list)
            safe_output.update(
                {
                    "runtime_events_ready": True,
                    "runtime_events": [asdict(event) for event in event_list],
                    "runtime_timeline": [asdict(item) for item in timeline],
                    "runtime_event_summary": asdict(summary),
                    "runtime_event_feed": feed,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "runtime_events_ready": False,
                    "runtime_events": [],
                    "runtime_timeline": [],
                    "runtime_event_summary": {},
                    "runtime_event_feed": [],
                    "runtime_event_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _symbol_from_result(self, output: dict) -> str:
        shadow = output.get("shadow_record") if isinstance(output.get("shadow_record"), dict) else {}
        return str(
            shadow.get("symbol")
            or shadow.get("market")
            or output.get("symbol")
            or "KRW-BTC"
        ).strip() or "KRW-BTC"

    def _attach_runtime_incidents(self, output: dict) -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_runtime_alert_builder import AIRuntimeAlertBuilder
            from app.services.ai_runtime_incident_escalation import (
                AIRuntimeIncidentEscalation,
            )
            from app.services.ai_runtime_incident_report import (
                AIRuntimeIncidentReportBuilder,
            )
            from app.services.ai_runtime_incident_store import AIRuntimeIncidentStore

            incidents = AIRuntimeAlertBuilder().build_alerts(
                safe_output,
                observation_report=safe_output.get("observation_report"),
                diagnostics=safe_output.get("session_report"),
                guard_report=safe_output.get("guard_report"),
            )
            store = AIRuntimeIncidentStore()
            for incident in incidents:
                store.append(incident)
            stored = store.list_incidents()
            report = AIRuntimeIncidentReportBuilder().build_report(stored)
            escalation = AIRuntimeIncidentEscalation().evaluate(stored)
            alert_feed = [
                {
                    "label": incident.title,
                    "message": incident.description,
                    "severity": incident.severity,
                    "incident_type": incident.incident_type,
                    "active": bool(incident.active),
                    "metadata": dict(incident.metadata or {}),
                }
                for incident in stored
            ]
            safe_output.update(
                {
                    "runtime_incidents_ready": True,
                    "runtime_incidents": [asdict(incident) for incident in stored],
                    "runtime_incident_report": asdict(report),
                    "runtime_escalation": asdict(escalation),
                    "runtime_alert_feed": alert_feed,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "runtime_incidents_ready": False,
                    "runtime_incidents": [],
                    "runtime_incident_report": {},
                    "runtime_escalation": {},
                    "runtime_alert_feed": [],
                    "runtime_incident_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _attach_runtime_snapshot(self, output: dict) -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_runtime_export_payload import (
                AIRuntimeExportPayloadBuilder,
            )
            from app.services.ai_runtime_snapshot_builder import AIRuntimeSnapshotBuilder
            from app.services.ai_runtime_snapshot_formatter import (
                AIRuntimeSnapshotFormatter,
            )

            snapshot = AIRuntimeSnapshotBuilder().build_snapshot(
                safe_output,
                symbol=self._symbol_from_result(safe_output),
            )
            export_payload = AIRuntimeExportPayloadBuilder().build_payload(
                snapshot,
                format="json",
            )
            formatted = AIRuntimeSnapshotFormatter().format_snapshot(snapshot)
            safe_output.update(
                {
                    "runtime_snapshot_ready": True,
                    "runtime_snapshot": asdict(snapshot),
                    "runtime_export_payload": asdict(export_payload),
                    "runtime_snapshot_formatted": formatted,
                    "runtime_export_safe": bool(export_payload.safe_to_persist),
                    "runtime_export_redacted": bool(export_payload.redacted),
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "runtime_snapshot_ready": False,
                    "runtime_snapshot": {},
                    "runtime_export_payload": {},
                    "runtime_snapshot_formatted": {},
                    "runtime_export_safe": False,
                    "runtime_export_redacted": True,
                    "runtime_snapshot_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

    def _attach_runtime_capability(self, output: dict) -> dict:
        safe_output = dict(output or {})
        try:
            from app.services.ai_runtime_capability_formatter import AIRuntimeCapabilityFormatter
            from app.services.ai_runtime_capability_registry import AIRuntimeCapabilityRegistry
            from app.services.ai_runtime_capability_report import AIRuntimeCapabilityReportBuilder
            from app.services.ai_runtime_compatibility_checker import AIRuntimeCompatibilityChecker
            from app.services.ai_runtime_feature_matrix import AIRuntimeFeatureMatrixBuilder

            provider = str(safe_output.get("provider") or "unknown")
            model = str(safe_output.get("model") or self._model_for_provider(provider) or "-")
            requested_feature = "one_shot_live" if bool(safe_output.get("allow_live")) else "one_shot_dry_run"

            profile = AIRuntimeCapabilityRegistry().get_profile(provider, model)
            matrix = AIRuntimeFeatureMatrixBuilder().build_matrix(profile)
            compatibility = AIRuntimeCompatibilityChecker().check(provider, model, requested_feature)
            report = AIRuntimeCapabilityReportBuilder().build_report(
                profile=profile,
                matrix=matrix,
                compatibility=compatibility,
            )
            formatted = AIRuntimeCapabilityFormatter().format_report(report, matrix=matrix)
            safe_output.update(
                {
                    "runtime_capability_ready": True,
                    "runtime_capability_profile": asdict(profile),
                    "runtime_feature_matrix": asdict(matrix),
                    "runtime_compatibility": asdict(compatibility),
                    "runtime_capability_report": asdict(report),
                    "runtime_capability_formatted": formatted,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        except Exception as exc:
            safe_output.update(
                {
                    "runtime_capability_ready": False,
                    "runtime_capability_profile": {},
                    "runtime_feature_matrix": {},
                    "runtime_compatibility": {},
                    "runtime_capability_report": {},
                    "runtime_capability_formatted": {},
                    "runtime_capability_error": type(exc).__name__,
                    "submitted": 0,
                    "real_order": False,
                    "applied": False,
                    "applied_to_action": False,
                }
            )
        return safe_output

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
