from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.aits_state import (
    ActionItem,
    AITSRuntimeState,
    ExecutionState,
    ExplainabilityState,
    IntelligenceState,
    MarketSnapshot,
    OversightState,
    PortfolioState,
    RegimeState,
    RuntimeMeta,
    SystemState,
)
from app.services.ai_decision_service import AIDecisionService
from app.services.explainability_service import ExplainabilityService
from app.services.portfolio_brain import PortfolioBrain
from app.services.regime_detector import RegimeDetector
from app.services.module_pack_resolver import ModulePackResolver
from app.services.order_service import OrderService
from app.core.module_pack_state import (
    DEFAULT_MODULE_PACK_DEFINITIONS,
    DEFAULT_USER_MODULE_PACK_SELECTION,
    UserModulePackSelection,
    ModulePackRuntimeState,
)
try:
    from app.services.order_adapter import AITSOrderAdapter
except Exception:
    AITSOrderAdapter = None

# ---------------------------------------------------------------------------
# Cycle result types (Phase 1)
# ---------------------------------------------------------------------------


@dataclass
class CycleMeta:
    cycle_id: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: float = 0.0
    run_mode: str = "ui"
    source: str = "aits_orchestrator"


@dataclass
class CycleStatus:
    ok: bool = True
    status: str = "success"
    phase: str = "completed"
    execution_attempted: bool = False
    execution_completed: bool = False
    degraded_mode: bool = False
    paused: bool = False


@dataclass
class ExecutionRequest:
    actions: List[Any] = field(default_factory=list)
    priority: int = 0
    source: str = "aits"
    decision_trace_id: str = ""
    dry_run: bool = False
    request_summary: str = ""


@dataclass
class CycleExecutionResult:
    submitted_orders: List[str] = field(default_factory=list)
    filled_orders: List[str] = field(default_factory=list)
    rejected_orders: List[str] = field(default_factory=list)
    pending_orders: List[str] = field(default_factory=list)
    execution_errors: List[str] = field(default_factory=list)
    execution_summary: str = ""


@dataclass
class CycleDiagnostics:
    provider_used: str = ""
    fallback_used: bool = False
    provider_latency_ms: float = 0.0
    market_data_latency_ms: float = 0.0
    decision_trace_id: str = ""
    blocked_reason_codes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleResult:
    meta: CycleMeta = field(default_factory=CycleMeta)
    status: CycleStatus = field(default_factory=CycleStatus)
    runtime_state: Optional[AITSRuntimeState] = None
    action_plan: Optional[Any] = None
    execution_request: Optional[ExecutionRequest] = None
    execution_result: CycleExecutionResult = field(default_factory=CycleExecutionResult)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    diagnostics: CycleDiagnostics = field(default_factory=CycleDiagnostics)

    def is_success(self) -> bool:
        return self.status.ok and self.status.status in ("success", "partial")

    def is_blocked(self) -> bool:
        return self.status.status in ("blocked", "paused")

    def has_errors(self) -> bool:
        return len(self.errors) > 0 or len(self.execution_result.execution_errors) > 0

    def summary_text(self) -> str:
        return (
            f"[cycle={self.meta.cycle_id}] status={self.status.status}, "
            f"duration_ms={self.meta.duration_ms:.1f}, warnings={len(self.warnings)}, "
            f"errors={len(self.errors)}"
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AITSOrchestrator:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        app_state: Optional[Any] = None,
        logger: Optional[Any] = None,
        regime_detector: Optional[Any] = None,
        portfolio_brain: Optional[Any] = None,
        ai_decision_service: Optional[Any] = None,
        explainability_service: Optional[Any] = None,
        module_engine: Optional[Any] = None,
        scenario_engine: Optional[Any] = None,
        provider_router: Optional[Any] = None,
        execution_adapter: Optional[Any] = None,
        run_mode: str = "ui",
    ) -> None:
        self.config = config if config is not None else {}
        self.app_state = app_state
        self.logger = logger
        self.regime_detector = regime_detector or RegimeDetector(config=self.config, logger=self.logger)
        self.portfolio_brain = portfolio_brain or PortfolioBrain(config=self.config, logger=self.logger)
        self.ai_decision_service = ai_decision_service or AIDecisionService(
            config=self.config, logger=self.logger
        )
        self.explainability_service = explainability_service or ExplainabilityService(
            config=self.config, logger=self.logger
        )
        self.module_engine = module_engine
        self.scenario_engine = scenario_engine
        self.provider_router = provider_router
        self.execution_adapter = execution_adapter
        self.run_mode = run_mode
        from app.services.execution_bridge import ExecutionBridge

        self.execution_bridge = ExecutionBridge(config=self.config, logger=self.logger)

        self.initialized = False
        self.paused = False
        self.cycle_counter = 0
        self.last_cycle_result: Optional[CycleResult] = None
        self.last_runtime_state: AITSRuntimeState = AITSRuntimeState()
        self.last_action_plan: Optional[Any] = None
        self.last_explainability: Optional[ExplainabilityState] = None
        self.last_error: str = ""
        self.current_user_controls: Dict[str, Any] = {}
        self.last_bridge_result: Optional[Any] = None
        _oa_cls = AITSOrderAdapter
        if _oa_cls is None:
            from app.services.order_adapter import AITSOrderAdapter as _oa_cls
        self.order_adapter = _oa_cls(
            execution_mode="disabled",
            min_order_krw=5000.0,
            allow_reduce_live=False,
            logger=self.logger,
        )
        self.last_order_adapter_result: Optional[Any] = None
        self.execution_mode: str = "disabled"

        self.module_pack_resolver = ModulePackResolver(
            pack_definitions=DEFAULT_MODULE_PACK_DEFINITIONS,
            base_pack_id="ai_default",
            logger=self.logger,
        )
        _mps = DEFAULT_USER_MODULE_PACK_SELECTION
        self.module_pack_selection = UserModulePackSelection(
            active_pack_id=_mps.active_pack_id,
            is_active=_mps.is_active,
            timer_enabled=_mps.timer_enabled,
            duration_minutes=_mps.duration_minutes,
            remaining_seconds=_mps.remaining_seconds,
            activated_at=_mps.activated_at,
            expires_at=_mps.expires_at,
            auto_revert_to_ai_default=_mps.auto_revert_to_ai_default,
            manual_deactivation_allowed=_mps.manual_deactivation_allowed,
            selection_reason=_mps.selection_reason,
            status_text_ko=_mps.status_text_ko,
        )
        self.last_module_pack_runtime: Optional[ModulePackRuntimeState] = None

    def initialize(self) -> bool:
        try:
            state = AITSRuntimeState()
            state.meta.run_mode = self.run_mode
            state.system.initialized = True
            state.system.running = False
            state.system.paused = self.paused
            state.system.active_provider = "local_rule_based"
            state.explainability.current_ai_view = (
                "AITS Phase 1: 초기화되었습니다. 장세·포트폴리오·판단을 연결할 준비가 되었습니다."
            )
            state.oversight.oversight_summary = (
                "시스템이 초기화되었습니다. 사용자는 언제든 판단을 검토하고 일시정지할 수 있습니다."
            )
            self.last_runtime_state = state
            self.last_bridge_result = None
            self.last_order_adapter_result = None
            self.order_adapter.set_execution_mode(self.execution_mode)
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(
                    self.module_pack_selection
                )
            except Exception:
                self.last_module_pack_runtime = None
            self.initialized = True
            self._safe_log_info("AITS orchestrator initialized")
            self._safe_log_info(
                "Module pack runtime initialized: "
                + (
                    (self.last_module_pack_runtime.pack_name_ko or "AI 기본 모드")
                    if self.last_module_pack_runtime is not None
                    else "AI 기본 모드"
                )
            )
            return True
        except Exception:
            return False

    def run_cycle(
        self,
        market_snapshot_override: Optional[Any] = None,
        forced_mode: Optional[str] = None,
        user_override_flags: Optional[Dict[str, Any]] = None,
    ) -> CycleResult:
        started_at = datetime.now()
        try:
            order_service = None
            execution_mode = self.execution_mode
            if execution_mode == "live":
                try:
                    order_service = OrderService()
                except Exception:
                    order_service = None

            self.cycle_counter += 1
            result = CycleResult()
            result.status.phase = "collecting"
            result.meta.cycle_id = self.cycle_counter
            result.meta.started_at = started_at
            result.meta.run_mode = self.run_mode
            result.meta.source = "aits_orchestrator"

            if not self.initialized:
                self.initialize()

            rs = self.last_runtime_state
            rs.meta.cycle_id = self.cycle_counter
            rs.meta.timestamp = started_at
            rs.meta.run_mode = self.run_mode

            rs.system.running = True
            rs.system.paused = self.paused

            if user_override_flags:
                self.current_user_controls.update(user_override_flags)

            self._refresh_module_pack_runtime()

            if self.paused:
                result.status.ok = True
                result.status.status = "paused"
                result.status.phase = "completed"
                result.status.paused = True
                msg = (
                    "거래 사이클이 일시정지되어 있습니다. 재개하면 최신 시장·포트폴리오 "
                    "상태를 다시 평가합니다."
                )
                rs.explainability.current_ai_view = msg
                rs.oversight.oversight_summary = (
                    "현재 일시정지 상태입니다. 재개 전까지 자동 실행은 진행되지 않습니다."
                )
                rs.system.running = False
                result.runtime_state = rs
                result.action_plan = rs.execution.plan
                result.execution_request = ExecutionRequest(
                    actions=[],
                    priority=1,
                    source="aits",
                    decision_trace_id=f"cycle-{self.cycle_counter}",
                    dry_run=True,
                    request_summary=rs.execution.plan.reason_summary or "일시정지 중입니다.",
                )
                result.execution_result.execution_summary = rs.execution.result.execution_summary
                result.diagnostics.provider_used = rs.system.active_provider
                result.diagnostics.decision_trace_id = f"cycle-{self.cycle_counter}"
                self.last_action_plan = rs.execution.plan
                self.last_explainability = rs.explainability
                self.last_runtime_state = rs
                self._update_bridge_result(result)
                try:
                    print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(result.execution_request.actions) if result.execution_request and result.execution_request.actions else 0}")
                    self.last_order_adapter_result = self.order_adapter.execute(
                        self.last_bridge_result, order_service=order_service
                    )
                except Exception as exc:
                    try:
                        if self.logger is not None and hasattr(self.logger, "debug"):
                            self.logger.debug(f"order adapter execute skipped: {exc}")
                    except Exception:
                        pass
                self._update_order_adapter_result()
                finished = datetime.now()
                result.meta.finished_at = finished
                result.meta.duration_ms = (finished - started_at).total_seconds() * 1000.0
                self.last_cycle_result = result
                return result

            self._build_market_state(market_snapshot_override)
            self._build_portfolio_state()
            self._build_intelligence_state(forced_mode)
            self._apply_control_state()
            self._build_execution_state()
            self._build_explainability_state()

            action_plan = rs.execution.plan
            self.last_action_plan = action_plan
            self.last_explainability = rs.explainability
            self.last_runtime_state = rs

            result.runtime_state = rs
            result.action_plan = action_plan
            result.execution_request = ExecutionRequest(
                actions=rs.execution.plan.approved_actions,
                priority=1,
                source="aits",
                decision_trace_id=f"cycle-{self.cycle_counter}",
                dry_run=True,
                request_summary=rs.execution.plan.reason_summary,
            )
            result.execution_result.execution_summary = rs.execution.result.execution_summary
            result.diagnostics.provider_used = rs.system.active_provider
            result.diagnostics.decision_trace_id = f"cycle-{self.cycle_counter}"

            print(f"[AITS][Orchestrator] decision_state | action={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'action', '')} | logic={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'selected_strategy_logic', '')} | symbol={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'selected_symbol', '')} | approved={len(action_plan.approved_actions) if action_plan and getattr(action_plan, 'approved_actions', None) else 0} | blocked={len(action_plan.blocked_actions) if action_plan and getattr(action_plan, 'blocked_actions', None) else 0} | actions={len(result.execution_request.actions) if result.execution_request and getattr(result.execution_request, 'actions', None) else 0}")
            self._update_bridge_result(result)
            try:
                print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(result.execution_request.actions) if result.execution_request and result.execution_request.actions else 0}")
                self.last_order_adapter_result = self.order_adapter.execute(
                    self.last_bridge_result, order_service=order_service
                )
            except Exception as exc:
                try:
                    if self.logger is not None and hasattr(self.logger, "debug"):
                        self.logger.debug(f"order adapter execute skipped: {exc}")
                except Exception:
                    pass
            self._update_order_adapter_result()

            self._log_module_pack_effect()

            result.status.phase = "completed"
            result.status.status = "success"
            result.status.ok = True

            finished = datetime.now()
            result.meta.finished_at = finished
            result.meta.duration_ms = (finished - started_at).total_seconds() * 1000.0

            rs.system.running = False
            self.last_cycle_result = result
            return result

        except Exception as exc:
            self.last_error = str(exc)
            err_result = CycleResult()
            err_result.meta.cycle_id = getattr(self, "cycle_counter", 0)
            err_result.meta.started_at = started_at
            err_result.meta.run_mode = self.run_mode
            err_result.status.ok = False
            err_result.status.status = "failed"
            err_result.status.phase = "failed"
            err_result.errors.append(str(exc))
            rs_fail = self.last_runtime_state
            rs_fail.system.last_error = str(exc)
            rs_fail.system.running = False
            err_result.runtime_state = rs_fail
            err_result.execution_request = ExecutionRequest()
            fin = datetime.now()
            err_result.meta.finished_at = fin
            err_result.meta.duration_ms = (fin - started_at).total_seconds() * 1000.0
            self._safe_log_error(f"run_cycle failed: {exc}")
            self.last_cycle_result = err_result
            self._update_bridge_result(err_result)
            try:
                print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(err_result.execution_request.actions) if err_result.execution_request and err_result.execution_request.actions else 0}")
                self.last_order_adapter_result = self.order_adapter.execute(
                    self.last_bridge_result, order_service=order_service
                )
            except Exception as exc:
                try:
                    if self.logger is not None and hasattr(self.logger, "debug"):
                        self.logger.debug(f"order adapter execute skipped: {exc}")
                except Exception:
                    pass
            self._update_order_adapter_result()
            return err_result

    def get_runtime_state(self) -> AITSRuntimeState:
        return self.last_runtime_state

    def get_last_action_plan(self) -> Optional[Any]:
        return self.last_action_plan

    def get_last_explainability(self) -> Optional[ExplainabilityState]:
        return self.last_explainability

    def get_last_bridge_result(self) -> Optional[Any]:
        return self.last_bridge_result

    def get_last_order_adapter_result(self) -> Optional[Any]:
        return self.last_order_adapter_result

    def set_execution_mode(self, execution_mode: str) -> None:
        self.execution_mode = str(execution_mode or "").strip() or "disabled"
        try:
            self.order_adapter.set_execution_mode(self.execution_mode)
            self.execution_mode = self.order_adapter.execution_mode
        except Exception:
            self.execution_mode = "disabled"
            try:
                self.order_adapter.set_execution_mode("disabled")
            except Exception:
                pass

    def get_execution_mode(self) -> str:
        return self.execution_mode

    def get_module_pack_selection(self) -> UserModulePackSelection:
        return self.module_pack_selection

    def get_last_module_pack_runtime(self) -> Optional[ModulePackRuntimeState]:
        return self.last_module_pack_runtime

    def activate_module_pack(
        self,
        pack_id: str,
        duration_minutes: int = 0,
        reason: str = "",
    ) -> None:
        if not pack_id or not str(pack_id).strip():
            return
        sel = self.module_pack_selection
        now = datetime.now()
        pid = str(pack_id).strip()
        sel.active_pack_id = pid
        sel.is_active = True
        sel.auto_revert_to_ai_default = True
        sel.selection_reason = reason or ""
        if duration_minutes > 0:
            try:
                dm = int(duration_minutes)
            except (TypeError, ValueError):
                dm = 0
            if dm > 0:
                sel.timer_enabled = True
                sel.duration_minutes = dm
                sel.remaining_seconds = dm * 60
                sel.activated_at = now
                sel.expires_at = now + timedelta(minutes=dm)
                sel.status_text_ko = f"모듈팩 활성: {pid} (타이머)"
            else:
                sel.timer_enabled = False
                sel.duration_minutes = 0
                sel.remaining_seconds = 0
                sel.activated_at = now
                sel.expires_at = None
                sel.status_text_ko = f"모듈팩 활성: {pid} / 무기한"
        else:
            sel.timer_enabled = False
            sel.duration_minutes = 0
            sel.remaining_seconds = 0
            sel.activated_at = now
            sel.expires_at = None
            sel.status_text_ko = f"모듈팩 활성: {pid} / 무기한"
        try:
            self.last_module_pack_runtime = self.module_pack_resolver.resolve(
                self.module_pack_selection,
                current_time=datetime.now(),
            )
        except Exception:
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(None)
            except Exception:
                self.last_module_pack_runtime = None
        self._safe_log_info(f"Module pack activation updated: {pid}")

    def request_pause(self, reason: Optional[str] = None) -> None:
        self.paused = True
        rs = self.last_runtime_state
        rs.system.paused = True
        rs.control.pause_logic.pause_requested = True
        rs.control.pause_logic.pause_reason = reason or "user_requested_pause"
        rs.oversight.oversight_summary = (
            "사용자 요청으로 일시정지되었습니다. 재개하면 운영 규칙에 따라 다시 평가합니다."
        )
        self._safe_log_info(f"Pause requested: {rs.control.pause_logic.pause_reason}")

    def request_resume(self) -> None:
        self.paused = False
        rs = self.last_runtime_state
        rs.system.paused = False
        rs.control.pause_logic.pause_requested = False
        rs.control.pause_logic.pause_reason = ""
        self._safe_log_info("Resume requested; pause flags cleared.")

    def update_user_controls(self, **kwargs: Any) -> None:
        try:
            self.current_user_controls.update(kwargs)
            rs = self.last_runtime_state
            if "whitelist" in kwargs and isinstance(kwargs["whitelist"], list):
                rs.control.constraints.whitelist = list(kwargs["whitelist"])
            if "blacklist" in kwargs and isinstance(kwargs["blacklist"], list):
                rs.control.constraints.blacklist = list(kwargs["blacklist"])
            if "selected_modules" in kwargs and isinstance(kwargs["selected_modules"], list):
                mods = list(kwargs["selected_modules"])
                rs.intelligence.modules.selected_modules = mods
                rs.intelligence.modules.active_modules = list(mods)
                rs.intelligence.modules.dominant_module = mods[0] if mods else ""
            if "new_buy_enabled" in kwargs and isinstance(kwargs["new_buy_enabled"], bool):
                rs.control.constraints.new_buy_enabled = kwargs["new_buy_enabled"]
            if "reentry_enabled" in kwargs and isinstance(kwargs["reentry_enabled"], bool):
                rs.control.constraints.reentry_enabled = kwargs["reentry_enabled"]
            if "strategy_mode" in kwargs:
                rs.intelligence.ai_decision.selected_strategy_logic = str(kwargs["strategy_mode"])
            if "risk_mode" in kwargs:
                rs.control.risk.risk_summary = (
                    f"사용자 위험 모드: {kwargs['risk_mode']} (Phase 1 스켈레톤 반영)"
                )
        except Exception:
            pass

    def shutdown(self) -> None:
        self.last_runtime_state.system.running = False
        self._safe_log_info("AITSOrchestrator shutdown.")

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_symbol_list_for_snapshot(self, raw: Any) -> List[str]:
        if not isinstance(raw, (list, tuple)):
            return []
        out: List[str] = []
        seen: set[str] = set()
        for x in raw:
            if not isinstance(x, str):
                continue
            s = x.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= 5:
                break
        return out

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
        except Exception:
            pass

    def _safe_log_error(self, message: str) -> None:
        try:
            if self.logger is not None:
                if hasattr(self.logger, "exception"):
                    self.logger.exception(message)
                elif hasattr(self.logger, "error"):
                    self.logger.error(message)
        except Exception:
            pass

    def _update_bridge_result(self, result: CycleResult) -> None:
        try:
            self.last_bridge_result = self.execution_bridge.build_from_cycle_result(result)
            br = self.last_bridge_result
            if br is not None and hasattr(br, "summary_text"):
                self._safe_log_info(br.summary_text())
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"bridge result update skipped: {exc}")
            except Exception:
                pass

    def _update_order_adapter_result(self) -> None:
        try:
            ar = self.last_order_adapter_result
            if ar is not None and hasattr(ar, "summary_text"):
                self._safe_log_info(f"[AITS][OrderAdapter] {ar.summary_text()}")
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"order adapter update skipped: {exc}")
            except Exception:
                pass

    def _refresh_module_pack_runtime(self) -> None:
        try:
            self.last_module_pack_runtime = self.module_pack_resolver.tick(
                self.module_pack_selection,
                current_time=datetime.now(),
            )
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"module pack runtime refresh failed: {exc}")
            except Exception:
                pass
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(None)
            except Exception:
                self.last_module_pack_runtime = None

    def _format_seconds_hhmmss(self, seconds: int) -> str:
        try:
            s = int(seconds)
        except (TypeError, ValueError):
            s = 0
        if s < 0:
            s = 0
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _log_module_pack_effect(self) -> None:
        try:
            rs = getattr(self, "last_runtime_state", None)
            if rs is None:
                return
            intel = getattr(rs, "intelligence", None)
            decision = getattr(intel, "ai_decision", None) if intel else None
            if decision is None:
                return
            logic = (getattr(decision, "selected_strategy_logic", None) or "")
            action = (getattr(decision, "action", None) or "")
            pr = getattr(self, "last_module_pack_runtime", None)
            if pr is None:
                return
            apid = getattr(pr, "active_pack_id", None)
            apid_str = "" if apid is None else str(apid).strip()
            if not apid_str:
                return
            pname = (getattr(pr, "pack_name_ko", None) or "").strip() or apid_str
            override_applied = "override_applied" in logic
            rem_suffix = ""
            if bool(getattr(pr, "timer_enabled", False)):
                try:
                    rem = int(getattr(pr, "remaining_seconds", 0))
                except (TypeError, ValueError):
                    rem = 0
                if rem > 0:
                    rem_suffix = f", remaining={self._format_seconds_hhmmss(rem)}"
            if override_applied:
                msg = (
                    f"[AITS][ModulePack] {pname} applied -> action={action}, override=yes{rem_suffix}"
                )
            else:
                msg = (
                    f"[AITS][ModulePack] {pname} active -> action={action}, override=no{rem_suffix}"
                )
            self._safe_log_info(msg)
        except Exception:
            pass

    def _build_market_state(self, market_snapshot_override: Optional[Any] = None) -> None:
        rs = self.last_runtime_state
        rs.system.active_provider = "local_rule_based"
        snap = rs.market.snapshot
        top_src: Any = None
        vol_src: Any = None
        base: Dict[str, Any] = {
            "btc_price": 0.0,
            "btc_change_pct": 0.0,
            "market_volatility": 0.0,
            "market_breadth": 0.5,
            "snapshot_summary": "기본 시장 스냅샷을 사용합니다.",
        }

        if market_snapshot_override is None:
            data = dict(base)
            data["btc_price"] = self._safe_float(snap.btc_price, 0.0)
            data["btc_change_pct"] = self._safe_float(snap.btc_change_pct, 0.0)
            data["market_volatility"] = self._safe_float(snap.market_volatility, 0.0)
            data["market_breadth"] = self._safe_float(snap.market_breadth, 0.5)
            if (snap.snapshot_summary or "").strip():
                data["snapshot_summary"] = snap.snapshot_summary
            try:
                from app.services.market_feed import (
                    calc_market_breadth,
                    get_tickers,
                    get_top_markets_by_volume,
                )

                blacklist_raw = getattr(getattr(rs.control, "constraints", None), "blacklist", None) or []
                blacklist = {str(x).strip() for x in blacklist_raw if isinstance(x, str) and x.strip()}

                top_rows = get_top_markets_by_volume(
                    limit=20,
                    quote="KRW",
                    exclude_black=blacklist,
                    min_price=10.0,
                )
                if top_rows:
                    volume_leaders = [m for (m, _) in top_rows[:5] if isinstance(m, str) and m.strip()]
                    sorted_by_change = sorted(
                        top_rows,
                        key=lambda x: float(((x[1] or {}).get("signed_change_rate") if isinstance(x[1], dict) else 0.0) or 0.0),
                        reverse=True,
                    )
                    top_gainers = [m for (m, _) in sorted_by_change[:5] if isinstance(m, str) and m.strip()]

                    ticks_map = {
                        m: t for (m, t) in top_rows if isinstance(m, str) and m.strip() and isinstance(t, dict)
                    }
                    breadth, _mean_chg = calc_market_breadth(ticks_map)

                    if volume_leaders:
                        data["volume_leaders"] = volume_leaders
                    if top_gainers:
                        data["top_gainers"] = top_gainers
                    data["market_breadth"] = self._safe_float(breadth, data.get("market_breadth", 0.5))

                    btc = ticks_map.get("KRW-BTC")
                    if btc is None:
                        btc_tick = get_tickers(["KRW-BTC"])
                        btc = btc_tick.get("KRW-BTC") if isinstance(btc_tick, dict) else None
                    if isinstance(btc, dict):
                        data["btc_price"] = self._safe_float(btc.get("trade_price"), data.get("btc_price", 0.0))
                        data["btc_change_pct"] = self._safe_float(
                            btc.get("signed_change_rate"), data.get("btc_change_pct", 0.0)
                        )

                    if not str(data.get("snapshot_summary") or "").strip():
                        data["snapshot_summary"] = "market_feed 기반 시장 스냅샷이 적용되었습니다."
            except Exception:
                pass
            regime = self.regime_detector.detect_from_dict(data)
            snap.btc_price = data["btc_price"]
            snap.btc_change_pct = data["btc_change_pct"]
            snap.market_volatility = data["market_volatility"]
            snap.market_breadth = data["market_breadth"]
            snap.snapshot_summary = data.get("snapshot_summary", base["snapshot_summary"])
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")
        elif isinstance(market_snapshot_override, dict):
            data = {**base, **market_snapshot_override}
            regime = self.regime_detector.detect_from_dict(data)
            snap.btc_price = self._safe_float(data.get("btc_price"), 0.0)
            snap.btc_change_pct = self._safe_float(data.get("btc_change_pct"), 0.0)
            snap.market_volatility = self._safe_float(data.get("market_volatility"), 0.0)
            snap.market_breadth = self._safe_float(data.get("market_breadth"), 0.5)
            snap.snapshot_summary = str(
                data.get("snapshot_summary") or "외부 시장 스냅샷 오버라이드가 적용되었습니다."
            )
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")
        elif isinstance(market_snapshot_override, MarketSnapshot):
            regime = self.regime_detector.detect(market_snapshot_override)
            snap.btc_price = self._safe_float(market_snapshot_override.btc_price, 0.0)
            snap.btc_change_pct = self._safe_float(market_snapshot_override.btc_change_pct, 0.0)
            snap.market_volatility = self._safe_float(market_snapshot_override.market_volatility, 0.0)
            snap.market_breadth = self._safe_float(market_snapshot_override.market_breadth, 0.5)
            ss = (market_snapshot_override.snapshot_summary or "").strip()
            snap.snapshot_summary = ss or "MarketSnapshot 오버라이드가 적용되었습니다."
            top_src = getattr(market_snapshot_override, "top_gainers", None)
            vol_src = getattr(market_snapshot_override, "volume_leaders", None)
        else:
            data = dict(base)
            data["snapshot_summary"] = "지원하지 않는 오버라이드 형식입니다. 기본 스냅샷을 사용합니다."
            regime = self.regime_detector.detect_from_dict(data)
            snap.snapshot_summary = data["snapshot_summary"]
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")

        try:
            snap.top_gainers = self._normalize_symbol_list_for_snapshot(top_src)
            snap.volume_leaders = self._normalize_symbol_list_for_snapshot(vol_src)
        except Exception:
            snap.top_gainers = []
            snap.volume_leaders = []

        rs.market.regime = regime
        if not (regime.summary_reason or "").strip():
            rs.market.regime.summary_reason = (
                "장세는 규칙 기반 로컬 판별기로 산출되었습니다."
            )
        if not (snap.snapshot_summary or "").strip():
            snap.snapshot_summary = "기본 시장 스냅샷을 사용합니다."

    def _build_portfolio_state(self) -> None:
        rs = self.last_runtime_state
        ps = rs.portfolio
        summ = ps.summary
        positions = ps.positions
        try:
            if summ.position_count is None:
                current_count = 0
            else:
                current_count = int(summ.position_count)
        except (TypeError, ValueError):
            current_count = 0
        if current_count < 0:
            current_count = 0
        if positions and len(positions) > 0:
            summ.position_count = len(positions)
        else:
            summ.position_count = current_count
        acr = self._safe_float(ps.summary.available_cash_ratio, 0.0)
        if acr < 0.0:
            ps.summary.available_cash_ratio = 0.0
        elif acr > 1.0:
            ps.summary.available_cash_ratio = 1.0

    def _build_intelligence_state(self, forced_mode: Optional[str] = None) -> None:
        rs = self.last_runtime_state
        regime = rs.market.regime
        portfolio = rs.portfolio
        opp = rs.intelligence.opportunities
        try:
            sources: List[Any] = []
            flow = getattr(rs.market, "flow", None)
            snap = getattr(rs.market, "snapshot", None)
            sources.extend(list(getattr(flow, "leader_symbols", None) or []))
            sources.extend(list(getattr(snap, "volume_leaders", None) or []))
            sources.extend(list(getattr(snap, "top_gainers", None) or []))

            seen: set[str] = set()
            cleaned: List[str] = []
            for sym in sources:
                if not isinstance(sym, str):
                    continue
                s = sym.strip()
                if not s:
                    continue
                if s in seen:
                    continue
                seen.add(s)
                cleaned.append(s)
                if len(cleaned) >= 5:
                    break
            opp.candidate_symbols = cleaned
        except Exception:
            opp.candidate_symbols = []

        target = self.portfolio_brain.build_target(regime, portfolio)
        try:
            mirrored: List[str] = []
            source_candidates = getattr(opp, "candidate_symbols", None)
            if isinstance(source_candidates, (list, tuple)):
                mirrored = list(source_candidates)
            if target is not None:
                target.candidate_symbols = mirrored
        except Exception:
            if target is not None:
                try:
                    target.candidate_symbols = []
                except Exception:
                    pass

        decision = self.ai_decision_service.decide(
            regime,
            portfolio,
            target,
            pack_runtime=self.last_module_pack_runtime,
        )
        rs.portfolio.target = target
        rs.intelligence.ai_decision = decision

        if forced_mode:
            fm = str(forced_mode)
            base_logic = (decision.selected_strategy_logic or "").strip()
            decision.selected_strategy_logic = (
                f"rule_based_phase1 | forced_mode={fm}"
                if not base_logic
                else f"{base_logic} | forced_mode={fm}"
            )

        sm = self.current_user_controls.get("selected_modules")
        if isinstance(sm, list):
            rs.intelligence.modules.selected_modules = list(sm)
            rs.intelligence.modules.active_modules = list(sm)
            rs.intelligence.modules.dominant_module = sm[0] if sm else ""

        if not (opp.selection_summary or "").strip():
            opp.selection_summary = (
                "Phase 1에서는 종목 후보 탐색보다 장세 및 포트폴리오 판단을 우선합니다."
            )

    def _apply_control_state(self) -> None:
        rs = self.last_runtime_state
        rs.system.paused = self.paused
        ctrl = rs.control
        decision = rs.intelligence.ai_decision
        regime = rs.market.regime
        if not ctrl.protection.stage:
            ctrl.protection.stage = "none"
        nb = self.current_user_controls.get("new_buy_enabled")
        if isinstance(nb, bool) and not nb:
            ctrl.constraints.new_buy_enabled = False
        wl = self.current_user_controls.get("whitelist")
        if isinstance(wl, list):
            ctrl.constraints.whitelist = list(wl)
        bl = self.current_user_controls.get("blacklist")
        if isinstance(bl, list):
            ctrl.constraints.blacklist = list(bl)
            ctrl.constraints.blocked_symbols = list(bl)
        ree = self.current_user_controls.get("reentry_enabled")
        if isinstance(ree, bool):
            ctrl.constraints.reentry_enabled = ree

        ctrl.risk.risk_summary = ctrl.risk.risk_summary or (
            "리스크 엔진이 연결되기 전입니다. 계좌·시장 리스크는 기본값으로 유지합니다."
        )
        ctrl.protection.protection_summary = ctrl.protection.protection_summary or (
            "보호 단계는 아직 트리거되지 않았으며, 정책에 따라 단계적으로 강화될 수 있습니다."
        )
        ctrl.constraints.constraint_summary = (
            "사용자·시스템 제약을 반영합니다. 화이트리스트/블랙리스트와 신규 매수 허용 여부를 "
            "우선 적용합니다."
        )
        if isinstance(nb, bool) and not nb:
            ctrl.constraints.constraint_summary += " 신규 매수는 사용자 설정에 의해 제한됩니다."

        lbl = (regime.label or "").strip().lower()
        if decision.action in ("sell", "reduce") and lbl == "bear":
            ctrl.risk.risk_summary = (ctrl.risk.risk_summary or "").strip() + (
                " 약세장 환경에서 손실·노출 축소가 우선입니다."
            )
            ctrl.protection.protection_summary = (ctrl.protection.protection_summary or "").strip() + (
                " 방어적 조정이 반영되었습니다."
            )

        if lbl == "bear" and self._safe_float(regime.confidence, 1.0) < 0.35:
            ctrl.pause_logic.suggested_pause = True
            ctrl.pause_logic.suggested_pause_reason = (
                "약세장과 낮은 장세 신뢰도가 겹쳐 일시정지를 고려할 수 있습니다."
            )

    def _build_execution_state(self) -> None:
        rs = self.last_runtime_state
        plan = rs.execution.plan
        res = rs.execution.result
        decision = rs.intelligence.ai_decision

        plan.approved_actions = []
        plan.blocked_actions = []
        plan.delayed_actions = []
        plan.requires_user_attention = False

        paused = self.paused or rs.control.pause_logic.pause_requested
        new_buy_ok = rs.control.constraints.new_buy_enabled

        if paused:
            plan.execution_mode = "blocked"
            plan.reason_summary = (
                "일시정지 또는 사용자 요청으로 실행이 차단되었습니다. 재개 후 다시 평가합니다."
            )
        elif decision.action == "wait":
            plan.execution_mode = "normal"
            plan.reason_summary = "현재는 신규 행동보다 관망이 우선입니다."
        elif decision.action == "hold":
            plan.execution_mode = "normal"
            plan.reason_summary = "현재 보유 포지션 유지가 우선입니다."
        elif decision.action in ("buy", "sell", "reduce"):
            resolved_symbol = ""
            raw_symbol = getattr(decision, "selected_symbol", "")
            if isinstance(raw_symbol, str):
                rsym = raw_symbol.strip()
                if rsym:
                    resolved_symbol = rsym
            item = ActionItem(
                symbol=resolved_symbol,
                action_type=decision.action,
                reason=decision.ai_summary_for_user or "",
            )
            if not new_buy_ok and decision.action == "buy":
                plan.blocked_actions = [item]
                plan.approved_actions = []
                plan.reason_summary = "신규 매수 제한이 활성화되어 매수 실행이 차단되었습니다."
            else:
                plan.approved_actions = [item]
                plan.reason_summary = decision.ai_summary_for_user or "실행 계획이 생성되었습니다."
            plan.execution_mode = "normal"
        else:
            plan.execution_mode = "normal"
            plan.reason_summary = decision.ai_summary_for_user or "실행 계획이 생성되었습니다."

        res.execution_summary = (
            "Phase 1에서는 실제 주문 실행 없이 실행 계획만 생성합니다."
        )

    def _build_explainability_state(self) -> None:
        rs = self.last_runtime_state
        regime = rs.market.regime
        target = rs.portfolio.target
        decision = rs.intelligence.ai_decision
        explain = self.explainability_service.build(regime, target, decision)
        rs.explainability = explain
        self.last_explainability = explain

        ov = rs.oversight
        if not (ov.oversight_summary or "").strip():
            ov.oversight_summary = (
                explain.why_pause_trading or explain.current_ai_view or "사용자 검토가 가능합니다."
            )

        mpr = self.last_module_pack_runtime
        if mpr is not None and (mpr.active_pack_id or "").strip():
            pname = (mpr.pack_name_ko or "").strip() or str(mpr.active_pack_id)
            suffix = f" / 현재 모듈팩: {pname}"
            cur = (ov.oversight_summary or "").strip()
            if suffix.strip() not in cur:
                ov.oversight_summary = (cur + suffix).strip()

        if decision.action == "sell":
            if "sell_review" not in ov.review_required_actions:
                ov.review_required_actions.append("sell_review")

        if decision.action == "buy" and self._safe_float(regime.confidence, 1.0) < 0.35:
            ov.trust_alerts.append(
                "장세 신뢰도가 낮은 상태에서 매수 신호가 있습니다. 주의하세요."
            )
