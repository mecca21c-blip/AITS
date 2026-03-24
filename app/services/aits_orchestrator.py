from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.aits_state import (
    AITSRuntimeState,
    RuntimeMeta,
    SystemState,
    MarketState,
    RegimeState,
    PortfolioState,
    IntelligenceState,
    AIDecisionState,
    ControlState,
    ExecutionState,
    ExplainabilityState,
    OversightState,
)

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
        self.regime_detector = regime_detector
        self.portfolio_brain = portfolio_brain
        self.ai_decision_service = ai_decision_service
        self.explainability_service = explainability_service
        self.module_engine = module_engine
        self.scenario_engine = scenario_engine
        self.provider_router = provider_router
        self.execution_adapter = execution_adapter
        self.run_mode = run_mode

        self.initialized = False
        self.paused = False
        self.cycle_counter = 0
        self.last_cycle_result: Optional[CycleResult] = None
        self.last_runtime_state: AITSRuntimeState = AITSRuntimeState()
        self.last_action_plan: Optional[Any] = None
        self.last_explainability: Optional[ExplainabilityState] = None
        self.last_error: str = ""
        self.current_user_controls: Dict[str, Any] = {}

    def initialize(self) -> bool:
        try:
            state = AITSRuntimeState()
            state.meta.run_mode = self.run_mode
            state.system.initialized = True
            state.system.running = False
            state.system.paused = self.paused
            self.last_runtime_state = state
            self.initialized = True
            self._safe_log_info("AITSOrchestrator initialized (Phase 1 skeleton).")
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
                finished = datetime.now()
                result.meta.finished_at = finished
                result.meta.duration_ms = (finished - started_at).total_seconds() * 1000.0
                rs.system.running = False
                result.runtime_state = rs
                result.action_plan = rs.execution.plan
                result.execution_request = ExecutionRequest()
                self.last_action_plan = rs.execution.plan
                self.last_explainability = rs.explainability
                self.last_runtime_state = rs
                self.last_cycle_result = result
                return result

            self._build_market_state(market_snapshot_override)
            self._build_portfolio_state()
            self._build_intelligence_state(forced_mode)
            self._apply_control_state()
            self._build_execution_state()
            self._build_explainability_state()

            rs.execution.plan.reason_summary = (
                rs.execution.plan.reason_summary
                or "Phase 1: 실행 계획은 스켈레톤 단계로, 승인·지연·차단 목록을 비우고 요약만 기록합니다."
            )

            action_plan = rs.execution.plan
            self.last_action_plan = action_plan
            self.last_explainability = rs.explainability
            self.last_runtime_state = rs

            result.runtime_state = rs
            result.action_plan = action_plan
            result.execution_request = ExecutionRequest()
            result.execution_result.execution_summary = (
                "이번 사이클에서는 실제 주문 제출 없이 구조 점검만 수행했습니다."
            )

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
            return err_result

    def get_runtime_state(self) -> AITSRuntimeState:
        return self.last_runtime_state

    def get_last_action_plan(self) -> Optional[Any]:
        return self.last_action_plan

    def get_last_explainability(self) -> Optional[ExplainabilityState]:
        return self.last_explainability

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

    def _build_market_state(self, market_snapshot_override: Optional[Any] = None) -> None:
        rs = self.last_runtime_state
        snap = rs.market.snapshot
        regime = rs.market.regime
        if market_snapshot_override is not None:
            snap.snapshot_summary = (
                "외부에서 전달된 시장 스냅샷 오버라이드가 적용되었습니다. (override_used)"
            )
        else:
            snap.snapshot_summary = (
                "아직 실시간 시장 데이터 파이프는 연결되지 않았으며, "
                "다음 단계에서 스냅샷이 채워집니다."
            )
        if not regime.label or not str(regime.label).strip():
            regime.label = "unknown"
        regime.summary_reason = (
            "레짐 분석기가 연결되기 전이라 기본 레이블을 유지합니다. "
            "추후 추세·변동성 점수와 함께 갱신됩니다."
        )

    def _build_portfolio_state(self) -> None:
        rs = self.last_runtime_state
        ps = rs.portfolio
        ps.summary.position_count = len(ps.positions)

    def _build_intelligence_state(self, forced_mode: Optional[str] = None) -> None:
        rs = self.last_runtime_state
        ai = rs.intelligence.ai_decision
        ai.action = "wait"
        ai.ai_summary_for_user = (
            "AITS Phase 1 기본 판단: 현재는 관망·대기 상태입니다. "
            "연결된 데이터와 전략이 준비되면 우선순위가 정리됩니다."
        )
        ai.market_interpretation = (
            "시장 데이터와 전략 판단이 아직 최소 구조 단계이므로 보수적으로 해석합니다."
        )
        if forced_mode:
            ai.action_bias = str(forced_mode)
            ai.selected_strategy_logic = str(forced_mode)
        sm = self.current_user_controls.get("selected_modules")
        if isinstance(sm, list):
            rs.intelligence.modules.selected_modules = list(sm)
            rs.intelligence.modules.active_modules = list(sm)
            rs.intelligence.modules.dominant_module = sm[0] if sm else ""

    def _apply_control_state(self) -> None:
        rs = self.last_runtime_state
        rs.system.paused = self.paused
        ctrl = rs.control
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

    def _build_execution_state(self) -> None:
        rs = self.last_runtime_state
        plan = rs.execution.plan
        res = rs.execution.result
        plan.execution_mode = "normal"
        blocked = self.paused or rs.control.pause_logic.pause_requested
        if blocked:
            plan.reason_summary = (
                "일시정지 또는 사용자 요청으로 실행 단계가 제한되었습니다. "
                "재개 후 다시 평가합니다."
            )
        else:
            plan.reason_summary = (
                "Phase 1에서는 승인·차단·지연 액션 목록을 비우고, "
                "실제 브로커 연동 전 구조만 점검합니다."
            )
        res.execution_summary = (
            "주문 실행 어댑터가 연결되기 전이므로 제출·체결 내역은 비어 있습니다."
        )

    def _build_explainability_state(self) -> None:
        rs = self.last_runtime_state
        ex = rs.explainability
        ai = rs.intelligence.ai_decision
        regime = rs.market.regime
        ex.current_ai_view = ai.ai_summary_for_user
        ex.current_market_story = regime.summary_reason or (
            "시장 스토리는 레짐 요약과 유동성 흐름이 연결되면 풍부해집니다."
        )
        ex.why_continue_trading = (
            "현재는 구조 점검 단계이며, 허용된 조건에서만 제한적으로 매매를 검토합니다."
        )
        pr = rs.control.pause_logic.pause_reason
        if pr:
            ex.why_pause_trading = f"일시정지 사유: {pr}"
        else:
            ex.why_pause_trading = (
                "일시정지가 걸리면 리스크·유동성·사용자 의사를 우선하고 실행을 멈춥니다."
            )
        rs.oversight.oversight_summary = (
            "사용자는 현재 AI 판단을 검토하고 필요 시 일시정지할 수 있습니다."
        )
