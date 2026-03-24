from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.aits_state import AIDecisionState, ExplainabilityState, PortfolioTarget, RegimeState

# ---------------------------------------------------------------------------
# Explainability (Phase 1 — template-based, no LLM)
# ---------------------------------------------------------------------------


class ExplainabilityService:
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        self.config = config if config is not None else {}
        self.logger = logger
        self.low_confidence_threshold = float(self.config.get("low_confidence_threshold", 0.35))
        self.strong_confidence_threshold = float(self.config.get("strong_confidence_threshold", 0.75))

    def build(
        self,
        regime: Optional[RegimeState],
        target: Optional[PortfolioTarget],
        decision: Optional[AIDecisionState],
    ) -> ExplainabilityState:
        try:
            if regime is None and target is None and decision is None:
                return ExplainabilityState(
                    current_ai_view="현재는 판단 정보가 충분하지 않아 보수적으로 상태를 해석합니다.",
                    current_market_story="시장 정보가 충분하지 않아 방향성을 명확히 설명하기 어렵습니다.",
                    selected_module_story="",
                    reason_for_recent_buy="",
                    reason_for_recent_sell="",
                    reason_for_recent_wait="충분한 정보가 확보되기 전까지는 신규 진입보다 대기를 우선합니다.",
                    why_continue_trading="현재는 제한적 판단만 수행하며 보수적으로 상태를 모니터링합니다.",
                    why_pause_trading="정보 부족 상태가 지속되면 일시정지를 고려할 수 있습니다.",
                    confidence_story="현재 판단 신뢰도는 낮은 편입니다.",
                    caution_story="시장 정보와 내부 상태가 충분히 정리되기 전까지 공격적 매매를 피하는 것이 좋습니다.",
                )

            current_ai_view = self._compose_ai_view(decision, target)
            current_market_story = self._compose_market_story(regime, target)
            rb, rs, rw = self._action_reason_triple(decision)
            why_continue = self._build_continue_story(regime)
            why_pause = self._build_pause_story(regime, decision)
            conf_story = self._build_confidence_story(regime, decision)
            caution = self._build_caution_story(regime, decision, target)

            return ExplainabilityState(
                current_ai_view=current_ai_view,
                current_market_story=current_market_story,
                selected_module_story="",
                reason_for_recent_buy=rb,
                reason_for_recent_sell=rs,
                reason_for_recent_wait=rw,
                why_continue_trading=why_continue,
                why_pause_trading=why_pause,
                confidence_story=conf_story,
                caution_story=caution,
            )
        except Exception as exc:
            self._safe_log_debug(f"build fallback: {exc}")
            return ExplainabilityState(
                current_ai_view="설명 생성 중 문제가 발생하여 보수적으로 상태를 해석합니다.",
                current_market_story="시장 설명을 생성하는 중 문제가 발생했습니다.",
                selected_module_story="",
                reason_for_recent_buy="",
                reason_for_recent_sell="",
                reason_for_recent_wait="현재는 시스템 안정성을 위해 대기 상태를 우선합니다.",
                why_continue_trading="현재는 제한적 상태 모니터링만 유지합니다.",
                why_pause_trading="설명 생성 문제가 반복되면 일시정지를 검토할 수 있습니다.",
                confidence_story="현재 설명 신뢰도는 낮은 편입니다.",
                caution_story="시스템이 안정화되기 전까지 공격적 판단을 피하는 것이 좋습니다.",
            )

    def build_from_dict(
        self,
        regime_data: Optional[Dict[str, Any]],
        target_data: Optional[Dict[str, Any]],
        decision_data: Optional[Dict[str, Any]],
    ) -> ExplainabilityState:
        regime: Optional[RegimeState] = None
        target: Optional[PortfolioTarget] = None
        decision: Optional[AIDecisionState] = None

        if isinstance(regime_data, dict):
            regime = RegimeState(
                label=str(regime_data.get("label", "unknown")),
                confidence=self._safe_float(regime_data.get("confidence"), 0.0),
                trend_score=self._safe_float(regime_data.get("trend_score"), 0.0),
                volatility_score=self._safe_float(regime_data.get("volatility_score"), 0.0),
                risk_bias=str(regime_data.get("risk_bias", "neutral")),
                summary_reason=str(regime_data.get("summary_reason", "")),
            )
        if isinstance(target_data, dict):
            target = PortfolioTarget(
                target_cash_weight=self._safe_float(target_data.get("target_cash_weight"), 0.0),
                target_major_weight=self._safe_float(target_data.get("target_major_weight"), 0.0),
                target_alt_weight=self._safe_float(target_data.get("target_alt_weight"), 0.0),
                rebalance_needed=bool(target_data.get("rebalance_needed", False)),
                target_reason=str(target_data.get("target_reason", "")),
            )
        if isinstance(decision_data, dict):
            decision = AIDecisionState(
                action=str(decision_data.get("action", "wait")),
                action_bias=str(decision_data.get("action_bias", "neutral")),
                confidence=self._safe_float(decision_data.get("confidence"), 0.0),
                market_interpretation=str(decision_data.get("market_interpretation", "")),
                selected_strategy_logic=str(decision_data.get("selected_strategy_logic", "")),
                why_this_symbol=str(decision_data.get("why_this_symbol", "")),
                why_not_others=str(decision_data.get("why_not_others", "")),
                ai_summary_for_user=str(decision_data.get("ai_summary_for_user", "")),
                ai_warning_for_user=str(decision_data.get("ai_warning_for_user", "")),
            )
        return self.build(regime, target, decision)

    def _compose_ai_view(self, decision: Optional[AIDecisionState], target: Optional[PortfolioTarget]) -> str:
        if decision is not None and (decision.ai_summary_for_user or "").strip():
            base = (decision.ai_summary_for_user or "").strip()
        else:
            base = self._build_ai_view(decision)
        if target is not None and target.rebalance_needed:
            base += " 현재 목표 비중과 실제 상태 차이가 있어 포트폴리오 재정렬이 필요할 수 있습니다."
        if target is not None and (target.target_reason or "").strip():
            tr = (target.target_reason or "").strip()
            if tr and tr not in base:
                base += f" ({tr})"
        return base.strip()

    def _compose_market_story(self, regime: Optional[RegimeState], target: Optional[PortfolioTarget]) -> str:
        base = self._build_market_story(regime)
        if target is not None and (target.target_reason or "").strip():
            tr = (target.target_reason or "").strip()
            if tr and tr not in base:
                base += f" 목표 관점: {tr}"
        return base.strip()

    def _action_reason_triple(self, decision: Optional[AIDecisionState]) -> tuple[str, str, str]:
        if decision is None:
            return ("", "", "판단 정보가 부족해 대기 쪽으로 해석합니다.")
        action = (decision.action or "wait").strip().lower()
        if action == "buy":
            return (
                self._build_action_reason("buy"),
                "",
                "",
            )
        if action == "sell":
            return (
                "",
                self._build_action_reason("sell"),
                "",
            )
        if action == "reduce":
            return (
                "",
                self._build_action_reason("reduce"),
                "",
            )
        if action == "hold":
            return (
                "",
                "",
                "보유를 유지하는 편이 적절하다고 판단했습니다.",
            )
        return ("", "", self._build_action_reason("wait"))

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _build_ai_view(self, decision: Optional[AIDecisionState]) -> str:
        if decision is None:
            return "현재는 신규 행동보다 관망이 우선이라고 판단합니다."
        action = (decision.action or "wait").strip().lower()
        mapping = {
            "buy": "현재는 점진적 신규 진입이 가능한 상태로 해석합니다.",
            "hold": "현재는 보유 포지션을 유지하는 쪽이 더 적절하다고 판단합니다.",
            "reduce": "현재는 포지션 일부 축소를 우선하는 것이 적절하다고 판단합니다.",
            "sell": "현재는 위험 축소를 위해 청산 또는 강한 축소가 우선이라고 판단합니다.",
            "wait": "현재는 신규 행동보다 관망이 우선이라고 판단합니다.",
        }
        return mapping.get(action, mapping["wait"])

    def _build_market_story(self, regime: Optional[RegimeState]) -> str:
        if regime is None:
            return "시장의 방향성이 아직 명확하지 않습니다."
        sr = (regime.summary_reason or "").strip()
        if sr:
            return sr
        label = (regime.label or "").strip().lower()
        if label == "bull":
            return "시장은 강세 흐름으로 해석됩니다."
        if label == "bear":
            return "시장은 방어적으로 접근해야 하는 약세 흐름으로 해석됩니다."
        if label == "sideways":
            return "시장은 뚜렷한 방향성 없이 횡보하는 흐름으로 해석됩니다."
        return "시장의 방향성이 아직 명확하지 않습니다."

    def _build_action_reason(self, action: str) -> str:
        a = (action or "wait").strip().lower()
        if a == "buy":
            return "강세 또는 유리한 현금 비중을 바탕으로 신규 진입 여력이 있다고 판단했습니다."
        if a == "sell":
            return "약세 또는 손실 확대 가능성을 고려해 위험 축소가 필요하다고 판단했습니다."
        if a == "reduce":
            return "전량 청산보다는 일부 축소가 적절하다고 판단했습니다."
        return "장세 신뢰도나 방향성이 충분하지 않아 대기를 우선했습니다."

    def _build_continue_story(self, regime: Optional[RegimeState]) -> str:
        if regime is None:
            return "상태가 정리되면 계속 판단을 이어가며 기회를 점검합니다."
        label = (regime.label or "").strip().lower()
        if label == "bull":
            return "시장에 기회가 남아 있어 조건이 맞는 경우 계속 판단을 이어가는 것이 유리합니다."
        if label == "bear":
            return "약세장에서도 방어적 관리와 제한적 기회 탐색을 위해 판단을 계속합니다."
        if label == "sideways":
            return "횡보장에서도 선별적 기회가 있을 수 있어 상태 감시는 계속 유지합니다."
        return "현재는 제한적 판단만 수행하며 보수적으로 상태를 모니터링합니다."

    def _build_pause_story(self, regime: Optional[RegimeState], decision: Optional[AIDecisionState]) -> str:
        rc = self._regime_confidence(regime)
        label = (regime.label or "").strip().lower() if regime else ""
        dc = self._safe_float(decision.confidence, 0.5) if decision is not None else None

        if label == "bear" and rc <= self.low_confidence_threshold:
            return "약세장과 낮은 신뢰도가 겹치면 일시정지를 고려할 수 있습니다."
        if dc is not None and dc <= self.low_confidence_threshold:
            return "현재 판단 신뢰도가 낮아 보수적 사용자라면 일시정지를 검토할 수 있습니다."
        if regime is not None and rc <= self.low_confidence_threshold:
            return "현재 판단 신뢰도가 낮아 보수적 사용자라면 일시정지를 검토할 수 있습니다."
        return "현재는 즉시 일시정지가 필요한 상태는 아니지만, 사용자는 언제든 개입할 수 있습니다."

    def _build_confidence_story(self, regime: Optional[RegimeState], decision: Optional[AIDecisionState]) -> str:
        if decision is not None:
            c = self._safe_float(decision.confidence, 0.5)
        elif regime is not None:
            c = self._safe_float(regime.confidence, 0.5)
        else:
            c = 0.5

        if c >= self.strong_confidence_threshold:
            return "현재 판단 신뢰도는 비교적 높은 편입니다."
        if c <= self.low_confidence_threshold:
            return "현재 판단 신뢰도는 낮은 편이므로 보수적으로 해석하는 것이 좋습니다."
        return "현재 판단 신뢰도는 중간 수준입니다."

    def _build_caution_story(
        self,
        regime: Optional[RegimeState],
        decision: Optional[AIDecisionState],
        target: Optional[PortfolioTarget],
    ) -> str:
        if decision is not None and (decision.ai_warning_for_user or "").strip():
            base = (decision.ai_warning_for_user or "").strip()
        else:
            base = ""
        label = (regime.label or "").strip().lower() if regime else ""
        action = (decision.action or "wait").strip().lower() if decision else "wait"
        dc = self._safe_float(decision.confidence, 0.5) if decision is not None else 0.5

        extra = ""
        if label == "bear":
            extra = "약세장에서는 무리한 신규 진입보다 리스크 관리가 우선입니다."
        elif action == "buy" and dc <= self.low_confidence_threshold:
            extra = "매수 판단이 있더라도 신뢰도가 낮다면 진입 강도를 낮추는 것이 좋습니다."
        elif action == "wait":
            extra = "관망 구간에서는 조급한 진입이 오히려 불리할 수 있습니다."
        else:
            extra = "변동성과 목표 비중을 주기적으로 확인하는 것이 좋습니다."

        if target is not None and target.rebalance_needed:
            extra += " 목표 비중과 실제 상태 차이가 있어 재정렬 시점을 점검하세요."

        if base:
            return (base + " " + extra).strip()
        return extra.strip()

    def _regime_confidence(self, regime: Optional[RegimeState]) -> float:
        if regime is None:
            return 0.5
        return self._safe_float(regime.confidence, 0.5)

    def _safe_log_debug(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "debug"):
                self.logger.debug(message)
        except Exception:
            pass
