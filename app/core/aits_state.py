from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

# 공통 / 메타


@dataclass
class RuntimeMeta:
    cycle_id: int = 0
    timestamp: Optional[datetime] = None
    run_mode: str = "ui"
    state_version: str = "1.0"
    source: str = "aits_orchestrator"


@dataclass
class SystemState:
    initialized: bool = False
    running: bool = False
    paused: bool = False
    degraded_mode: bool = False
    active_provider: str = "openai"
    last_provider_used: str = ""
    last_error: str = ""
    warnings: List[str] = field(default_factory=list)


# 시장 상태


@dataclass
class MarketSnapshot:
    btc_price: float = 0.0
    btc_change_pct: float = 0.0
    market_volatility: float = 0.0
    market_breadth: float = 0.0
    top_gainers: List[str] = field(default_factory=list)
    top_losers: List[str] = field(default_factory=list)
    volume_leaders: List[str] = field(default_factory=list)
    snapshot_summary: str = ""


@dataclass
class RegimeState:
    label: str = "unknown"
    confidence: float = 0.0
    trend_score: float = 0.0
    volatility_score: float = 0.0
    risk_bias: str = "neutral"
    summary_reason: str = ""


@dataclass
class FlowState:
    leader_symbols: List[str] = field(default_factory=list)
    major_vs_alt_flow: str = ""
    rotation_signal: bool = False
    inflow_score: float = 0.0
    flow_summary: str = ""


@dataclass
class MarketState:
    snapshot: MarketSnapshot = field(default_factory=MarketSnapshot)
    regime: RegimeState = field(default_factory=RegimeState)
    flow: FlowState = field(default_factory=FlowState)


# 포트폴리오 상태


@dataclass
class PortfolioSummary:
    total_equity: float = 0.0
    cash_balance: float = 0.0
    invested_balance: float = 0.0
    portfolio_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    available_cash_ratio: float = 0.0
    position_count: int = 0


@dataclass
class PositionState:
    symbol: str = ""
    qty: float = 0.0
    avg_price: float = 0.0
    current_price: float = 0.0
    pnl_pct: float = 0.0
    weight: float = 0.0
    holding_time: str = ""
    status: str = "holding"
    module_origin: str = ""
    notes: str = ""


@dataclass
class PortfolioTarget:
    target_cash_weight: float = 0.0
    target_major_weight: float = 0.0
    target_alt_weight: float = 0.0
    target_symbol_weights: Dict[str, float] = field(default_factory=dict)
    rebalance_needed: bool = False
    target_reason: str = ""


@dataclass
class PortfolioState:
    summary: PortfolioSummary = field(default_factory=PortfolioSummary)
    positions: List[PositionState] = field(default_factory=list)
    target: PortfolioTarget = field(default_factory=PortfolioTarget)


# 인텔리전스 상태


@dataclass
class ModuleState:
    selected_modules: List[str] = field(default_factory=list)
    active_modules: List[str] = field(default_factory=list)
    dominant_module: str = ""
    module_scores: Dict[str, float] = field(default_factory=dict)
    module_decision_reason: str = ""


@dataclass
class ScenarioState:
    active_scenarios: List[str] = field(default_factory=list)
    scenario_summary: str = ""
    scenario_reason: str = ""
    scenario_blocked: bool = False


@dataclass
class OpportunityCandidate:
    symbol: str = ""
    score: float = 0.0
    confidence: float = 0.0
    matched_module: str = ""
    reason: str = ""
    risk_level: str = ""


@dataclass
class OpportunityState:
    top_candidates: List[OpportunityCandidate] = field(default_factory=list)
    rejected_candidates: List[str] = field(default_factory=list)
    market_opportunity_score: float = 0.0
    selection_summary: str = ""


@dataclass
class AIDecisionState:
    action: str = "wait"
    action_bias: str = "neutral"
    confidence: float = 0.0
    market_interpretation: str = ""
    selected_strategy_logic: str = ""
    why_this_symbol: str = ""
    why_not_others: str = ""
    ai_summary_for_user: str = ""
    ai_warning_for_user: str = ""


@dataclass
class IntelligenceState:
    modules: ModuleState = field(default_factory=ModuleState)
    scenarios: ScenarioState = field(default_factory=ScenarioState)
    opportunities: OpportunityState = field(default_factory=OpportunityState)
    ai_decision: AIDecisionState = field(default_factory=AIDecisionState)


# 제어 상태


@dataclass
class ProtectionState:
    stage: str = "none"
    trigger_reason: str = ""
    new_buy_limited: bool = False
    partial_take_profit_required: bool = False
    force_cash_buffer: float = 0.0
    protection_summary: str = ""


@dataclass
class RiskState:
    account_risk_score: float = 0.0
    market_risk_score: float = 0.0
    trading_allowed: bool = True
    max_new_allocation: float = 0.0
    emergency_flags: List[str] = field(default_factory=list)
    risk_summary: str = ""


@dataclass
class ConstraintState:
    new_buy_enabled: bool = True
    reentry_enabled: bool = True
    allowed_asset_scope: str = "all"
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)
    blocked_symbols: List[str] = field(default_factory=list)
    constraint_summary: str = ""


@dataclass
class PauseLogicState:
    pause_requested: bool = False
    pause_reason: str = ""
    resume_allowed: bool = True
    suggested_pause: bool = False
    suggested_pause_reason: str = ""


@dataclass
class ControlState:
    protection: ProtectionState = field(default_factory=ProtectionState)
    risk: RiskState = field(default_factory=RiskState)
    constraints: ConstraintState = field(default_factory=ConstraintState)
    pause_logic: PauseLogicState = field(default_factory=PauseLogicState)


# 실행 상태


@dataclass
class ActionItem:
    symbol: str = ""
    action_type: str = "wait"
    target_weight: float = 0.0
    amount_krw: float = 0.0
    priority: int = 0
    source_module: str = ""
    source_provider: str = ""
    reason: str = ""


@dataclass
class ExecutionDraft:
    buy_candidates: List[ActionItem] = field(default_factory=list)
    sell_candidates: List[ActionItem] = field(default_factory=list)
    reduce_candidates: List[ActionItem] = field(default_factory=list)
    hold_candidates: List[ActionItem] = field(default_factory=list)
    wait_reason: str = ""


@dataclass
class ExecutionPlan:
    approved_actions: List[ActionItem] = field(default_factory=list)
    blocked_actions: List[ActionItem] = field(default_factory=list)
    delayed_actions: List[ActionItem] = field(default_factory=list)
    reason_summary: str = ""
    requires_user_attention: bool = False
    execution_mode: str = "normal"


@dataclass
class ExecutionResult:
    submitted_orders: List[str] = field(default_factory=list)
    filled_orders: List[str] = field(default_factory=list)
    rejected_orders: List[str] = field(default_factory=list)
    pending_orders: List[str] = field(default_factory=list)
    execution_errors: List[str] = field(default_factory=list)
    execution_summary: str = ""


@dataclass
class ExecutionState:
    draft: ExecutionDraft = field(default_factory=ExecutionDraft)
    plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    result: ExecutionResult = field(default_factory=ExecutionResult)


# 설명 / 감독 상태


@dataclass
class ExplainabilityState:
    current_ai_view: str = ""
    current_market_story: str = ""
    selected_module_story: str = ""
    reason_for_recent_buy: str = ""
    reason_for_recent_sell: str = ""
    reason_for_recent_wait: str = ""
    why_continue_trading: str = ""
    why_pause_trading: str = ""
    confidence_story: str = ""
    caution_story: str = ""


@dataclass
class OversightState:
    auto_trading_enabled: bool = True
    user_pause_allowed: bool = True
    review_required_actions: List[str] = field(default_factory=list)
    recent_conflict_points: List[str] = field(default_factory=list)
    trust_alerts: List[str] = field(default_factory=list)
    oversight_summary: str = ""


# 최상위 런타임 상태


@dataclass
class AITSRuntimeState:
    meta: RuntimeMeta = field(default_factory=RuntimeMeta)
    system: SystemState = field(default_factory=SystemState)
    market: MarketState = field(default_factory=MarketState)
    portfolio: PortfolioState = field(default_factory=PortfolioState)
    intelligence: IntelligenceState = field(default_factory=IntelligenceState)
    control: ControlState = field(default_factory=ControlState)
    execution: ExecutionState = field(default_factory=ExecutionState)
    explainability: ExplainabilityState = field(default_factory=ExplainabilityState)
    oversight: OversightState = field(default_factory=OversightState)

    def is_trading_active(self) -> bool:
        return (
            self.system.initialized
            and self.system.running
            and not self.system.paused
            and self.control.risk.trading_allowed
        )

    def current_regime(self) -> str:
        return self.market.regime.label

    def current_ai_action(self) -> str:
        return self.intelligence.ai_decision.action

    def summary_text(self) -> str:
        return (
            f"[{self.meta.cycle_id}] regime={self.market.regime.label}, "
            f"action={self.intelligence.ai_decision.action}, "
            f"pnl={self.portfolio.summary.portfolio_pnl_pct:.2f}%"
        )
