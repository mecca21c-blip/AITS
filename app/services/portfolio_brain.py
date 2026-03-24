from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.aits_state import PortfolioState, PortfolioTarget, PositionState, RegimeState

# ---------------------------------------------------------------------------
# Portfolio target construction (Phase 1 — rule-based)
# ---------------------------------------------------------------------------


class PortfolioBrain:
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        self.config = config if config is not None else {}
        self.logger = logger
        self.bull_target_cash_weight = float(self.config.get("bull_target_cash_weight", 0.10))
        self.bull_target_major_weight = float(self.config.get("bull_target_major_weight", 0.50))
        self.bull_target_alt_weight = float(self.config.get("bull_target_alt_weight", 0.40))
        self.sideways_target_cash_weight = float(self.config.get("sideways_target_cash_weight", 0.25))
        self.sideways_target_major_weight = float(self.config.get("sideways_target_major_weight", 0.45))
        self.sideways_target_alt_weight = float(self.config.get("sideways_target_alt_weight", 0.30))
        self.bear_target_cash_weight = float(self.config.get("bear_target_cash_weight", 0.50))
        self.bear_target_major_weight = float(self.config.get("bear_target_major_weight", 0.40))
        self.bear_target_alt_weight = float(self.config.get("bear_target_alt_weight", 0.10))
        self.max_total_weight_tolerance = float(self.config.get("max_total_weight_tolerance", 0.15))

    def build_target(
        self, regime: Optional[RegimeState], portfolio: Optional[PortfolioState]
    ) -> PortfolioTarget:
        try:
            regime_label = "sideways"
            confidence = 0.5
            if regime is not None:
                regime_label = (regime.label or "sideways").strip().lower() or "sideways"
                confidence = self._safe_float(regime.confidence, 0.5)

            if regime is None:
                c, m, a = (
                    self.sideways_target_cash_weight,
                    self.sideways_target_major_weight,
                    self.sideways_target_alt_weight,
                )
                target_reason = "장세 정보가 부족하여 중립 포트폴리오 목표를 사용합니다."
            elif regime_label == "bull":
                c, m, a = (
                    self.bull_target_cash_weight,
                    self.bull_target_major_weight,
                    self.bull_target_alt_weight,
                )
                target_reason = ""
            elif regime_label == "bear":
                c, m, a = (
                    self.bear_target_cash_weight,
                    self.bear_target_major_weight,
                    self.bear_target_alt_weight,
                )
                target_reason = ""
            else:
                c, m, a = (
                    self.sideways_target_cash_weight,
                    self.sideways_target_major_weight,
                    self.sideways_target_alt_weight,
                )
                target_reason = ""

            if regime is not None and confidence < 0.35:
                c += 0.05
                a -= 0.05
                if a < 0.0:
                    short = -a
                    a = 0.0
                    m -= short
                    if m < 0.0:
                        m = 0.0

            c, m, a = self._normalize_weights(c, m, a)

            rebalance = self._should_rebalance(portfolio, c, regime_label)

            if regime is not None:
                target_reason = self._build_reason(regime_label, confidence, c, m, a)

            return PortfolioTarget(
                target_cash_weight=c,
                target_major_weight=m,
                target_alt_weight=a,
                target_symbol_weights={},
                rebalance_needed=rebalance,
                target_reason=target_reason,
            )
        except Exception as exc:
            self._safe_log_debug(f"build_target fallback: {exc}")
            return PortfolioTarget(
                target_cash_weight=0.30,
                target_major_weight=0.50,
                target_alt_weight=0.20,
                target_symbol_weights={},
                rebalance_needed=False,
                target_reason="포트폴리오 목표 계산 중 문제가 발생하여 보수적인 기본 목표를 사용합니다.",
            )

    def build_target_from_dict(
        self,
        regime_data: Optional[Dict[str, Any]],
        portfolio_data: Optional[Dict[str, Any]],
    ) -> PortfolioTarget:
        regime: Optional[RegimeState] = None
        portfolio: Optional[PortfolioState] = None
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
                summ.available_cash_ratio = self._safe_float(
                    sraw.get("available_cash_ratio"), summ.available_cash_ratio
                )
                if sraw.get("position_count") is not None:
                    try:
                        summ.position_count = int(sraw["position_count"])
                    except (TypeError, ValueError):
                        pass
            pos = portfolio_data.get("positions")
            if isinstance(pos, list):
                portfolio.positions = [PositionState() for _ in pos]
                if summ.position_count == 0:
                    summ.position_count = len(pos)
        return self.build_target(regime, portfolio)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_weights(self, cash_weight: float, major_weight: float, alt_weight: float) -> tuple[float, float, float]:
        c = max(0.0, cash_weight)
        m = max(0.0, major_weight)
        a = max(0.0, alt_weight)
        s = c + m + a
        if s <= 0.0:
            return (1.0, 0.0, 0.0)
        return (c / s, m / s, a / s)

    def _should_rebalance(
        self, portfolio: Optional[PortfolioState], target_cash_weight: float, regime_label: str
    ) -> bool:
        if portfolio is None:
            return False
        summ = portfolio.summary
        cash_ratio = self._safe_float(summ.available_cash_ratio, 0.0)
        pos_count = int(summ.position_count) if summ.position_count is not None else len(portfolio.positions)
        diff = abs(cash_ratio - target_cash_weight)
        if diff > self.max_total_weight_tolerance:
            return True
        invest_target = 1.0 - target_cash_weight
        if regime_label in ("bull", "sideways") and pos_count == 0 and invest_target > 0.55:
            return True
        if regime_label == "bear" and pos_count >= 2 and cash_ratio < target_cash_weight - 0.10:
            return True
        return False

    def _build_reason(
        self,
        regime_label: str,
        confidence: float,
        cash_weight: float,
        major_weight: float,
        alt_weight: float,
    ) -> str:
        conf_note = ""
        if confidence < 0.35:
            conf_note = " 장세 신뢰도가 낮아 현금 비중을 소폭 높이고 알트 비중을 줄였습니다."

        if regime_label == "bull":
            return (
                "강세장으로 해석되어 현금 비중을 낮추고 메이저 및 알트 비중을 확대하는 목표를 사용합니다."
                + conf_note
                + f" (목표: 현금 {cash_weight:.0%}, 메이저 {major_weight:.0%}, 알트 {alt_weight:.0%})"
            )
        if regime_label == "bear":
            return (
                "약세장으로 판단되어 현금 비중을 높이고 알트 노출을 낮추는 방어적 목표를 사용합니다."
                + conf_note
                + f" (목표: 현금 {cash_weight:.0%}, 메이저 {major_weight:.0%}, 알트 {alt_weight:.0%})"
            )
        return (
            "횡보장으로 해석되어 현금 여유를 유지하면서 선별적 운용을 위한 중립 목표를 사용합니다."
            + conf_note
            + f" (목표: 현금 {cash_weight:.0%}, 메이저 {major_weight:.0%}, 알트 {alt_weight:.0%})"
        )

    def _safe_log_debug(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "debug"):
                self.logger.debug(message)
        except Exception:
            pass
