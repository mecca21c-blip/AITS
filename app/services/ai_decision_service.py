from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.aits_state import AIDecisionState, PortfolioState, PortfolioTarget, RegimeState
from app.core.module_pack_state import ModulePackRuntimeState

# ---------------------------------------------------------------------------
# Rule-based AI decision (Phase 1 — local only, provider-ready structure)
# ---------------------------------------------------------------------------


class AIDecisionService:
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        self.config = config if config is not None else {}
        self.logger = logger
        self.high_cash_threshold = float(self.config.get("high_cash_threshold", 0.45))
        self.low_cash_threshold = float(self.config.get("low_cash_threshold", 0.10))
        self.high_profit_threshold = float(self.config.get("high_profit_threshold", 5.0))
        self.loss_warning_threshold = float(self.config.get("loss_warning_threshold", -3.0))
        self.low_regime_confidence_threshold = float(
            self.config.get("low_regime_confidence_threshold", 0.35)
        )
        self.bullish_buy_confidence = float(self.config.get("bullish_buy_confidence", 0.75))
        self.bearish_defensive_confidence = float(self.config.get("bearish_defensive_confidence", 0.80))
        self.neutral_wait_confidence = float(self.config.get("neutral_wait_confidence", 0.60))
        # Module pack override: bias thresholds (config overrides)
        self.wait_to_hold_threshold = float(self.config.get("wait_to_hold_threshold", 0.10))
        self.hold_to_buy_threshold = float(self.config.get("hold_to_buy_threshold", 0.15))
        self.hold_to_wait_threshold = float(self.config.get("hold_to_wait_threshold", 0.15))
        self.hold_to_reduce_threshold = float(self.config.get("hold_to_reduce_threshold", 0.10))
        self.reduce_to_sell_threshold = float(self.config.get("reduce_to_sell_threshold", 0.10))
        self.buy_to_hold_threshold = float(self.config.get("buy_to_hold_threshold", 0.10))
        self.offensive_buy_bonus = float(self.config.get("offensive_buy_bonus", 0.05))
        self.offensive_wait_penalty = float(self.config.get("offensive_wait_penalty", -0.02))
        self.defensive_buy_penalty = float(self.config.get("defensive_buy_penalty", -0.05))
        self.defensive_wait_bonus = float(self.config.get("defensive_wait_bonus", 0.05))
        self.defensive_reduce_bonus = float(self.config.get("defensive_reduce_bonus", 0.05))
        self.defensive_sell_bonus = float(self.config.get("defensive_sell_bonus", 0.03))

    def decide(
        self,
        regime: Optional[RegimeState],
        portfolio: Optional[PortfolioState],
        target: Optional[PortfolioTarget],
        pack_runtime: Optional[ModulePackRuntimeState] = None,
    ) -> AIDecisionState:
        try:
            if regime is None and target is None:
                d = AIDecisionState(
                    action="wait",
                    action_bias="neutral",
                    confidence=self._clamp(0.30, 0.0, 1.0),
                    market_interpretation="시장 및 포트폴리오 목표 정보가 부족하여 보수적으로 대기합니다.",
                    selected_strategy_logic="insufficient_input_fallback",
                    why_this_symbol="",
                    why_not_others="",
                    ai_summary_for_user="현재는 판단 정보가 부족하여 신규 진입보다 대기를 우선합니다.",
                    ai_warning_for_user="시장 정보가 충분히 확보되기 전까지 공격적 매매를 피하는 것이 좋습니다.",
                )
                return self._apply_module_pack_override(d, regime, portfolio, target, pack_runtime)

            if regime is None:
                d = self._build_sideways_decision(None, portfolio, target)
                d = self._apply_low_regime_confidence(None, d)
                return self._apply_module_pack_override(d, regime, portfolio, target, pack_runtime)

            label = (regime.label or "").strip().lower()
            if label == "bear":
                d = self._build_bear_decision(regime, portfolio, target)
            elif label == "bull":
                d = self._build_bull_decision(regime, portfolio, target)
            else:
                d = self._build_sideways_decision(regime, portfolio, target)

            d = self._apply_low_regime_confidence(regime, d)
            return self._apply_module_pack_override(d, regime, portfolio, target, pack_runtime)
        except Exception as exc:
            self._safe_log_debug(f"decide fallback: {exc}")
            return AIDecisionState(
                action="wait",
                action_bias="neutral",
                confidence=0.25,
                market_interpretation="판단 중 문제가 발생하여 보수적으로 대기합니다.",
                selected_strategy_logic="decision_error_fallback",
                why_this_symbol="",
                why_not_others="",
                ai_summary_for_user="현재는 시스템 안정성을 위해 대기 판단을 우선합니다.",
                ai_warning_for_user="판단 로직 복구 전까지 공격적 매매를 피하는 것이 좋습니다.",
            )

    def decide_from_dict(
        self,
        regime_data: Optional[Dict[str, Any]],
        portfolio_data: Optional[Dict[str, Any]],
        target_data: Optional[Dict[str, Any]],
        pack_runtime_data: Optional[Dict[str, Any]] = None,
    ) -> AIDecisionState:
        regime: Optional[RegimeState] = None
        portfolio: Optional[PortfolioState] = None
        target: Optional[PortfolioTarget] = None

        if isinstance(regime_data, dict):
            regime = RegimeState(
                label=str(regime_data.get("label", "unknown")),
                confidence=self._safe_float(regime_data.get("confidence"), 0.0),
                trend_score=self._safe_float(regime_data.get("trend_score"), 0.0),
                volatility_score=self._safe_float(regime_data.get("volatility_score"), 0.0),
                risk_bias=str(regime_data.get("risk_bias", "neutral")),
                summary_reason=str(regime_data.get("summary_reason", "")),
            )
        if isinstance(portfolio_data, dict):
            portfolio = PortfolioState()
            summ = portfolio.summary
            sraw = portfolio_data.get("summary")
            if isinstance(sraw, dict):
                summ.total_equity = self._safe_float(sraw.get("total_equity"), summ.total_equity)
                summ.cash_balance = self._safe_float(sraw.get("cash_balance"), summ.cash_balance)
                summ.invested_balance = self._safe_float(sraw.get("invested_balance"), summ.invested_balance)
                summ.portfolio_pnl_pct = self._safe_float(sraw.get("portfolio_pnl_pct"), summ.portfolio_pnl_pct)
                summ.realized_pnl = self._safe_float(sraw.get("realized_pnl"), summ.realized_pnl)
                summ.unrealized_pnl = self._safe_float(sraw.get("unrealized_pnl"), summ.unrealized_pnl)
                summ.available_cash_ratio = self._safe_float(
                    sraw.get("available_cash_ratio"), summ.available_cash_ratio
                )
                if sraw.get("position_count") is not None:
                    try:
                        summ.position_count = int(sraw["position_count"])
                    except (TypeError, ValueError):
                        pass
        if isinstance(target_data, dict):
            target = PortfolioTarget(
                target_cash_weight=self._safe_float(target_data.get("target_cash_weight"), 0.0),
                target_major_weight=self._safe_float(target_data.get("target_major_weight"), 0.0),
                target_alt_weight=self._safe_float(target_data.get("target_alt_weight"), 0.0),
                rebalance_needed=bool(target_data.get("rebalance_needed", False)),
                target_reason=str(target_data.get("target_reason", "")),
            )
        pack_runtime: Optional[ModulePackRuntimeState] = None
        if isinstance(pack_runtime_data, dict):
            prd = pack_runtime_data
            apid = prd.get("active_pack_id")
            pack_runtime = ModulePackRuntimeState(
                active_pack_id=str(apid) if apid is not None else None,
                pack_name_ko=str(prd.get("pack_name_ko", "") or ""),
                effective_risk_bias=str(prd.get("effective_risk_bias", "none") or "none"),
                effective_buy_bias_delta=self._safe_float(prd.get("effective_buy_bias_delta"), 0.0),
                effective_wait_bias_delta=self._safe_float(prd.get("effective_wait_bias_delta"), 0.0),
                effective_reduce_bias_delta=self._safe_float(prd.get("effective_reduce_bias_delta"), 0.0),
                effective_sell_bias_delta=self._safe_float(prd.get("effective_sell_bias_delta"), 0.0),
                timer_enabled=bool(prd.get("timer_enabled", False)),
                remaining_seconds=int(self._safe_float(prd.get("remaining_seconds"), 0.0)),
                expired=bool(prd.get("expired", False)),
                runtime_summary_ko=str(prd.get("runtime_summary_ko", "") or ""),
            )
        return self.decide(regime, portfolio, target, pack_runtime=pack_runtime)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _apply_low_regime_confidence(
        self, regime: Optional[RegimeState], decision: AIDecisionState
    ) -> AIDecisionState:
        if regime is None:
            decision.confidence = self._clamp(decision.confidence, 0.0, 1.0)
            return decision
        rc = self._safe_float(regime.confidence, 0.5)
        if rc < self.low_regime_confidence_threshold and decision.action == "buy":
            decision.action = "wait"
            decision.action_bias = "neutral"
            decision.confidence = min(decision.confidence, 0.45)
            decision.selected_strategy_logic = (
                decision.selected_strategy_logic + "_low_regime_confidence"
            )
            warn = " 장세 신뢰도가 낮아 공격적 매수보다는 관망이 유리합니다."
            decision.ai_warning_for_user = (decision.ai_warning_for_user + warn).strip()
            decision.market_interpretation = (
                "장세 신뢰도가 낮아 공격적 매수보다는 관망이 유리합니다. "
                + decision.market_interpretation
            )
        decision.confidence = self._clamp(decision.confidence, 0.0, 1.0)
        return decision

    def _is_pack_runtime_active(self, pack_runtime: Optional[ModulePackRuntimeState]) -> bool:
        if pack_runtime is None:
            return False
        apid = pack_runtime.active_pack_id
        if apid is None or not str(apid).strip():
            return False
        if bool(pack_runtime.expired):
            return False
        return True

    def _append_text_once(self, base: str, extra: str) -> str:
        b = (base or "").strip()
        e = (extra or "").strip()
        if not e:
            return b
        if e in b:
            return b
        return (b + " " + e).strip() if b else e

    def _adjust_confidence_for_pack(
        self, decision: AIDecisionState, pack_runtime: ModulePackRuntimeState
    ) -> AIDecisionState:
        rb = (pack_runtime.effective_risk_bias or "").strip().lower()
        action = decision.action
        delta = 0.0
        if rb == "defensive":
            if action in ("reduce", "sell", "wait"):
                delta = 0.05
            elif action == "buy":
                delta = -0.05
            elif action == "hold":
                delta = 0.03
        elif rb == "offensive":
            if action in ("buy", "hold"):
                delta = 0.05
            elif action == "sell":
                delta = -0.05
            elif action in ("wait", "reduce"):
                delta = -0.03
        decision.confidence = self._clamp(decision.confidence + delta, 0.0, 1.0)
        return decision

    def _append_pack_reasoning(
        self,
        decision: AIDecisionState,
        pack_runtime: ModulePackRuntimeState,
        action_changed: bool = False,
    ) -> AIDecisionState:
        pid = (pack_runtime.active_pack_id or "").strip()
        pname = (pack_runtime.pack_name_ko or "").strip()
        if not pname and pid:
            pname = pid
        tag = f" | module_pack={pid}" if pid else ""
        base_logic = decision.selected_strategy_logic or ""
        if tag and tag.strip() not in base_logic:
            decision.selected_strategy_logic = (base_logic + tag).strip()
        if action_changed and "override_applied" not in (decision.selected_strategy_logic or ""):
            decision.selected_strategy_logic = (
                (decision.selected_strategy_logic or "").strip() + " | override_applied"
            ).strip()

        summary = (decision.ai_summary_for_user or "").strip()
        if pname and "모듈팩" not in summary and "모듈 팩" not in summary:
            rb = (pack_runtime.effective_risk_bias or "").strip().lower()
            if rb == "defensive":
                extra = f"{pname} 성향을 반영해 방어적 판단을 더 우선합니다."
            elif rb == "offensive":
                extra = f"{pname} 성향을 반영해 추세 편향을 약간 강화했습니다."
            else:
                extra = f"선택된 모듈팩({pname}) 설정을 참고했습니다."
            decision.ai_summary_for_user = (summary + " " + extra).strip()

        if action_changed and pname:
            rb_adj = (pack_runtime.effective_risk_bias or "").strip().lower()
            if rb_adj == "offensive":
                adj_sent = (
                    f"현재 선택된 {pname}의 영향으로 판단이 한 단계 공격적으로 조정되었습니다."
                )
            elif rb_adj == "defensive":
                adj_sent = (
                    f"현재 선택된 {pname}의 영향으로 판단이 한 단계 보수적으로 조정되었습니다."
                )
            else:
                adj_sent = (
                    f"현재 선택된 모듈팩({pname})의 영향으로 판단이 조정되었습니다."
                )
            decision.ai_summary_for_user = self._append_text_once(
                decision.ai_summary_for_user or "", adj_sent
            )

        warn = (decision.ai_warning_for_user or "").strip()
        rbw = (pack_runtime.effective_risk_bias or "").strip().lower()
        if rbw == "defensive" and "모듈팩" not in warn:
            wadd = "현재 모듈팩은 신규 매수보다 리스크 관리와 방어를 더 우선합니다."
            decision.ai_warning_for_user = (warn + " " + wadd).strip() if warn else wadd
        elif rbw == "offensive" and "모듈팩" not in warn:
            wadd = "현재 모듈팩은 추세 추종 성향을 강화하므로 변동성에 유의해야 합니다."
            decision.ai_warning_for_user = (warn + " " + wadd).strip() if warn else wadd

        warn = (decision.ai_warning_for_user or "").strip()
        if action_changed:
            if rbw == "offensive" and "추세 추종 성향이 강화" not in warn:
                decision.ai_warning_for_user = self._append_text_once(
                    warn, "현재 모듈팩 영향으로 추세 추종 성향이 강화되었습니다."
                )
            elif rbw == "defensive" and "방어적 대응이 강화" not in warn:
                decision.ai_warning_for_user = self._append_text_once(
                    warn, "현재 모듈팩 영향으로 방어적 대응이 강화되었습니다."
                )
        return decision

    def _get_effective_pack_biases(self, pack_runtime: ModulePackRuntimeState) -> Dict[str, float]:
        buy = self._safe_float(getattr(pack_runtime, "effective_buy_bias_delta", None), 0.0)
        wait = self._safe_float(getattr(pack_runtime, "effective_wait_bias_delta", None), 0.0)
        reduce = self._safe_float(getattr(pack_runtime, "effective_reduce_bias_delta", None), 0.0)
        sell = self._safe_float(getattr(pack_runtime, "effective_sell_bias_delta", None), 0.0)
        rb = (pack_runtime.effective_risk_bias or "").strip().lower()
        if rb == "offensive":
            buy += self.offensive_buy_bonus
            wait += self.offensive_wait_penalty
        elif rb == "defensive":
            buy += self.defensive_buy_penalty
            wait += self.defensive_wait_bonus
            reduce += self.defensive_reduce_bonus
            sell += self.defensive_sell_bonus
        return {
            "buy": self._clamp(buy, -1.0, 1.0),
            "wait": self._clamp(wait, -1.0, 1.0),
            "reduce": self._clamp(reduce, -1.0, 1.0),
            "sell": self._clamp(sell, -1.0, 1.0),
        }

    def _apply_module_pack_override(
        self,
        decision: AIDecisionState,
        regime: Optional[RegimeState],
        portfolio: Optional[PortfolioState],
        target: Optional[PortfolioTarget],
        pack_runtime: Optional[ModulePackRuntimeState],
    ) -> AIDecisionState:
        try:
            if not self._is_pack_runtime_active(pack_runtime):
                return decision
            pr = pack_runtime
            _ = (portfolio, target)
            original_action = decision.action
            regime_label = (regime.label or "").strip().lower() if regime else ""
            biases = self._get_effective_pack_biases(pr)
            buy_bias = biases["buy"]
            wait_bias = biases["wait"]
            reduce_bias = biases["reduce"]
            sell_bias = biases["sell"]
            apid = str(pr.active_pack_id or "").strip()

            action = decision.action

            if regime_label == "bull":
                if action == "hold" and buy_bias >= self.hold_to_buy_threshold:
                    action = "buy"
                elif action == "wait" and buy_bias >= self.wait_to_hold_threshold:
                    action = "hold"
                elif action == "buy" and wait_bias >= self.buy_to_hold_threshold:
                    action = "hold"
            elif regime_label == "bear":
                if action == "hold" and reduce_bias >= self.hold_to_reduce_threshold:
                    action = "reduce"
                elif action == "reduce" and sell_bias >= self.reduce_to_sell_threshold:
                    action = "sell"
                elif action == "buy" and wait_bias >= self.buy_to_hold_threshold:
                    action = "hold"
            else:
                if action == "wait" and apid == "reversal_pack":
                    action = "hold"
                elif action == "wait" and buy_bias >= self.wait_to_hold_threshold:
                    action = "hold"
                elif action == "hold" and wait_bias >= self.hold_to_wait_threshold:
                    action = "wait"
                elif action == "buy" and wait_bias >= self.buy_to_hold_threshold:
                    action = "hold"

            decision.action = action
            action_changed = original_action != decision.action
            self._adjust_confidence_for_pack(decision, pr)
            self._append_pack_reasoning(decision, pr, action_changed=action_changed)
            return decision
        except Exception:
            return decision

    def _build_bear_decision(
        self,
        regime: RegimeState,
        portfolio: Optional[PortfolioState],
        target: Optional[PortfolioTarget],
    ) -> AIDecisionState:
        pnl = self._safe_float(portfolio.summary.portfolio_pnl_pct if portfolio else None, 0.0)
        cash = self._safe_float(portfolio.summary.available_cash_ratio if portfolio else None, 0.0)
        pos = int(portfolio.summary.position_count) if portfolio else 0
        tc = self._safe_float(target.target_cash_weight if target else None, 0.50)

        conf = self._clamp(self.bearish_defensive_confidence, 0.70, 0.85)

        if pnl <= self.loss_warning_threshold:
            action = "sell"
            interp = "약세장에서 손실 폭이 커지고 있어 리스크 축소를 위해 매도 쪽을 우선 검토합니다."
            summary = "약세·손실 확대 구간으로 보여 보유 물량을 줄이는 방향이 안전합니다."
            warn = "손실이 경고 수준에 근접했습니다. 추가 하락에 대비해 노출을 줄이세요."
            logic = "bear_defensive_sell"
        elif cash >= tc + 0.05:
            action = "wait"
            interp = "약세장이나 현금 비중은 이미 충분해 추가 방어 조정보다 관망이 적절합니다."
            summary = "현금 버퍼가 확보된 상태라 급한 매도보다 상황을 지켜보는 편이 낫습니다."
            warn = "추가 하락 시에도 대응할 여유가 있는지 주기적으로 확인하세요."
            logic = "bear_defensive_wait"
        elif pos >= 1 and cash < tc - 0.05:
            action = "reduce"
            interp = "약세장으로 해석되며 현금 비중이 목표보다 낮아 비중 축소가 우선입니다."
            summary = "방어적 비중 조정을 위해 일부 포지션을 줄이는 쪽을 권합니다."
            warn = "현금 확보가 부족하면 변동성에 취약할 수 있습니다."
            logic = "bear_defensive_reduce"
        elif pos >= 1:
            action = "reduce"
            interp = "약세장으로 해석되며 현재는 방어적 비중 조정이 우선입니다."
            summary = "포트폴리오 노출을 조금씩 줄여 방어력을 높이는 방향을 권합니다."
            warn = "약세장에서는 알트·고위험 자산 비중을 특히 줄이는 것이 좋습니다."
            logic = "bear_defensive_reduce_mild"
        else:
            action = "wait"
            interp = "약세장으로 해석되며 아직 보유 포지션이 없거나 현금 비중을 판단하기 어려워 관망이 적절합니다."
            summary = "추가 정보가 쌓일 때까지 방어적 관점에서 천천히 대응하는 편이 낫습니다."
            warn = "약세장에서는 급한 진입·회전보다 현금과 정보 확보를 우선하세요."
            logic = "bear_defensive_wait_no_positions"

        return AIDecisionState(
            action=action,
            action_bias="defensive",
            confidence=conf,
            market_interpretation=interp,
            selected_strategy_logic=logic,
            why_this_symbol="",
            why_not_others="",
            ai_summary_for_user=summary,
            ai_warning_for_user=warn,
        )

    def _build_bull_decision(
        self,
        regime: RegimeState,
        portfolio: Optional[PortfolioState],
        target: Optional[PortfolioTarget],
    ) -> AIDecisionState:
        cash = self._safe_float(portfolio.summary.available_cash_ratio if portfolio else None, 0.0)
        tc = self._safe_float(target.target_cash_weight if target else None, 0.10)

        if cash > tc + 0.10:
            conf = self._clamp(self.bullish_buy_confidence, 0.70, 0.80)
            return AIDecisionState(
                action="buy",
                action_bias="offensive",
                confidence=conf,
                market_interpretation="강세장으로 해석되며 남아 있는 현금을 활용한 점진적 진입이 유리합니다.",
                selected_strategy_logic="bull_offensive_buy",
                why_this_symbol="",
                why_not_others="",
                ai_summary_for_user="현금 여유가 있어 목표 비중에 맞추며 단계적으로 매수하는 편이 좋습니다.",
                ai_warning_for_user="한 번에 크게 들어가기보다 분할·선별 매수를 권장합니다.",
            )

        conf = self._clamp(self.bullish_buy_confidence - 0.03, 0.70, 0.80)
        return AIDecisionState(
            action="hold",
            action_bias="offensive",
            confidence=conf,
            market_interpretation="강세장이나 이미 투자 비중이 목표에 근접해 보유를 유지하는 편이 낫습니다.",
            selected_strategy_logic="bull_offensive_hold",
            why_this_symbol="",
            why_not_others="",
            ai_summary_for_user="추가 매수 여력이 크지 않아 기존 포지션을 유지하며 추세를 따릅니다.",
            ai_warning_for_user="과도한 레버리지나 집중 투자는 피하는 것이 좋습니다.",
        )

    def _build_sideways_decision(
        self,
        regime: Optional[RegimeState],
        portfolio: Optional[PortfolioState],
        target: Optional[PortfolioTarget],
    ) -> AIDecisionState:
        cash = self._safe_float(portfolio.summary.available_cash_ratio if portfolio else None, 0.0)
        pos = int(portfolio.summary.position_count) if portfolio else 0
        reb = bool(target.rebalance_needed) if target else False

        if pos > 0:
            conf = self._clamp(self.neutral_wait_confidence + 0.05, 0.55, 0.70)
            return AIDecisionState(
                action="hold",
                action_bias="neutral",
                confidence=conf,
                market_interpretation="횡보장으로 보이며 명확한 방향성이 부족하므로 무리한 신규 진입보다 보유 유지가 적절합니다.",
                selected_strategy_logic="sideways_hold_positions",
                why_this_symbol="",
                why_not_others="",
                ai_summary_for_user="이미 보유 중인 포지션이 있어 횡보 구간에서는 유지·조정에 집중합니다.",
                ai_warning_for_user="리밸런싱이 필요하면 소폭 조정만 검토하고 급격한 회전은 피하세요.",
            )

        if cash > self.high_cash_threshold and pos == 0:
            conf = self._clamp(self.neutral_wait_confidence, 0.55, 0.70)
            return AIDecisionState(
                action="buy",
                action_bias="neutral",
                confidence=conf,
                market_interpretation="횡보장이나 현금 비중이 높고 포지션이 거의 없어 제한적인 소액 진입을 검토할 수 있습니다.",
                selected_strategy_logic="sideways_limited_buy",
                why_this_symbol="",
                why_not_others="",
                ai_summary_for_user="현금이 많이 남아 있어 선별적으로 소량만 배분하는 수준을 권합니다.",
                ai_warning_for_user="횡보장에서는 방향성이 약하므로 소액·분할만 고려하세요.",
            )

        if reb and pos == 0:
            sideways_probe_confidence_min = 0.60
            rb = (regime.risk_bias or "").strip().lower() if regime else ""
            rc = self._safe_float(regime.confidence, 0.0) if regime else 0.0
            if rb == "defensive" or rc < sideways_probe_confidence_min:
                conf = self._clamp(self.neutral_wait_confidence - 0.05, 0.55, 0.70)
                return AIDecisionState(
                    action="wait",
                    action_bias="neutral",
                    confidence=conf,
                    market_interpretation="횡보장으로 보이며 현재 보유 포지션이 없어 신규 진입보다 대기를 우선합니다.",
                    selected_strategy_logic="sideways_wait_no_positions",
                    why_this_symbol="",
                    why_not_others="",
                    ai_summary_for_user="현재는 횡보장으로 해석되며, 보유 포지션이 없어 무리한 진입보다 관망이 적절합니다.",
                    ai_warning_for_user="리밸런싱이 필요해 보여도 횡보장에서는 급한 진입보다 계획 수립을 우선하세요.",
                    selected_symbol="",
                )
            conf = self._clamp(self.neutral_wait_confidence, 0.55, 0.70)

            resolved_symbol = ""
            if target is not None:
                # Phase 2: probe buy 대상 심볼을 '현재 입력'에서만 단일 후보일 때만 해석
                for attr_name in ("selected_symbol", "target_symbol", "primary_symbol"):
                    v = getattr(target, attr_name, None)
                    if isinstance(v, str) and v.strip():
                        resolved_symbol = v.strip()
                        break

                if not resolved_symbol:
                    tsw = getattr(target, "target_symbol_weights", None)
                    if isinstance(tsw, dict) and len(tsw) == 1:
                        k = next(iter(tsw.keys()))
                        if isinstance(k, str) and k.strip():
                            resolved_symbol = k.strip()

                if not resolved_symbol:
                    cs = getattr(target, "candidate_symbols", None)
                    if isinstance(cs, list) and cs:
                        first = cs[0]
                        if isinstance(first, str) and first.strip():
                            resolved_symbol = first.strip()

            if not resolved_symbol and pack_runtime is not None:
                cs = getattr(pack_runtime, "candidate_symbols", None)
                if isinstance(cs, list) and cs:
                    first = cs[0]
                    if isinstance(first, str) and first.strip():
                        resolved_symbol = first.strip()

            if not resolved_symbol and portfolio is not None:
                cs = getattr(portfolio, "candidate_symbols", None)
                if isinstance(cs, list) and cs:
                    first = cs[0]
                    if isinstance(first, str) and first.strip():
                        resolved_symbol = first.strip()

            return AIDecisionState(
                action="buy" if resolved_symbol else "wait",
                action_bias="neutral",
                confidence=conf,
                market_interpretation=(
                    "횡보장으로 보이지만 무포지션 상태가 길어질 수 있어 소규모 탐색 진입을 검토합니다."
                    if resolved_symbol
                    else "횡보장으로 해석되며 탐색 진입 여건은 있으나, 현재는 대상 심볼이 확정되지 않아 관망합니다."
                ),
                selected_strategy_logic=(
                    "sideways_probe_buy_no_positions"
                    if resolved_symbol
                    else "sideways_wait_no_symbol_source"
                ),
                why_this_symbol=resolved_symbol if resolved_symbol else "",
                why_not_others="",
                ai_summary_for_user=(
                    "현재는 횡보장으로 해석되지만 무포지션 상태이므로, 조건부로 소규모 탐색 진입이 가능합니다."
                    if resolved_symbol
                    else "현재는 횡보장이며 소규모 탐색 진입 여건은 있지만, 대상 심볼 정보가 부족해 관망이 적절합니다."
                ),
                ai_warning_for_user=(
                    "횡보장에서는 변동성이 제한적일 수 있으므로 첫 진입은 탐색 수준으로 보수적으로 접근하세요."
                    if resolved_symbol
                    else "대상 심볼이 확정되지 않은 상태에서는 무리한 진입보다 후보 선별을 우선하세요."
                ),
                selected_symbol=resolved_symbol if resolved_symbol else "",
            )

        conf = self._clamp(self.neutral_wait_confidence, 0.55, 0.70)
        return AIDecisionState(
            action="wait",
            action_bias="neutral",
            confidence=conf,
            market_interpretation="횡보장으로 해석되며 방향성이 불명확해 관망이 적절합니다.",
            selected_strategy_logic="sideways_wait",
            why_this_symbol="",
            why_not_others="",
            ai_summary_for_user="명확한 추세가 보이기 전까지는 대기하며 정보를 보강하는 것이 좋습니다.",
            ai_warning_for_user="횡보장에서는 잦은 매매보다 기다림이 손실을 줄이는 경우가 많습니다.",
        )

    def _safe_log_debug(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "debug"):
                self.logger.debug(message)
        except Exception:
            pass
