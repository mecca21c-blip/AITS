from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.aits_state import MarketSnapshot, RegimeState

# ---------------------------------------------------------------------------
# Regime detection (Phase 1 — rule-based, no external APIs)
# ---------------------------------------------------------------------------


class RegimeDetector:
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        self.config = config if config is not None else {}
        self.logger = logger
        self.bull_change_pct_threshold = float(
            self.config.get("bull_change_pct_threshold", 1.0)
        )
        self.bear_change_pct_threshold = float(
            self.config.get("bear_change_pct_threshold", -1.0)
        )
        self.high_volatility_threshold = float(
            self.config.get("high_volatility_threshold", 2.5)
        )
        self.low_breadth_threshold = float(self.config.get("low_breadth_threshold", 0.4))
        self.high_breadth_threshold = float(self.config.get("high_breadth_threshold", 0.6))

    def detect(self, snapshot: Optional[MarketSnapshot]) -> RegimeState:
        try:
            if snapshot is None:
                return RegimeState(
                    label="sideways",
                    confidence=0.2,
                    trend_score=0.0,
                    volatility_score=0.0,
                    risk_bias="neutral",
                    summary_reason="시장 데이터가 부족하여 중립(횡보) 상태로 해석합니다.",
                )

            btc_change_pct = self._safe_float(snapshot.btc_change_pct, 0.0)
            breadth = self._safe_float(snapshot.market_breadth, 0.5)
            volatility = self._safe_float(snapshot.market_volatility, 0.0)

            vol_cap = self.high_volatility_threshold * 1.2
            bull_ok = (
                btc_change_pct >= self.bull_change_pct_threshold
                and breadth >= self.high_breadth_threshold
                and volatility <= vol_cap
            )
            bear_ok = btc_change_pct <= self.bear_change_pct_threshold or (
                breadth <= self.low_breadth_threshold and btc_change_pct < 0
            )

            if bull_ok and not bear_ok:
                label = "bull"
                risk_bias = "offensive"
            elif bear_ok:
                label = "bear"
                risk_bias = "defensive"
            else:
                label = "sideways"
                risk_bias = "neutral"

            trend_score = btc_change_pct
            volatility_score = volatility
            confidence = self._compute_confidence(btc_change_pct, breadth, volatility, label)
            summary_reason = self._build_reason(label, btc_change_pct, breadth, volatility)

            return RegimeState(
                label=label,
                confidence=confidence,
                trend_score=trend_score,
                volatility_score=volatility_score,
                risk_bias=risk_bias,
                summary_reason=summary_reason,
            )
        except Exception as exc:
            self._safe_log_debug(f"detect fallback: {exc}")
            return RegimeState(
                label="unknown",
                confidence=0.2,
                trend_score=0.0,
                volatility_score=0.0,
                risk_bias="neutral",
                summary_reason="장세 판별 중 예기치 않은 오류가 있어 중립 상태로 복구했습니다.",
            )

    def detect_from_dict(self, data: Optional[Dict[str, Any]]) -> RegimeState:
        if data is None or not isinstance(data, dict):
            return self.detect(None)
        snap = MarketSnapshot()
        snap.btc_price = self._safe_float(data.get("btc_price"), snap.btc_price)
        snap.btc_change_pct = self._safe_float(data.get("btc_change_pct"), snap.btc_change_pct)
        snap.market_volatility = self._safe_float(
            data.get("market_volatility"), snap.market_volatility
        )
        snap.market_breadth = self._safe_float(data.get("market_breadth"), snap.market_breadth)
        if isinstance(data.get("top_gainers"), list):
            snap.top_gainers = [str(x) for x in data["top_gainers"]]
        if isinstance(data.get("top_losers"), list):
            snap.top_losers = [str(x) for x in data["top_losers"]]
        if isinstance(data.get("volume_leaders"), list):
            snap.volume_leaders = [str(x) for x in data["volume_leaders"]]
        if data.get("snapshot_summary") is not None:
            snap.snapshot_summary = str(data.get("snapshot_summary", ""))
        return self.detect(snap)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _compute_confidence(
        self,
        btc_change_pct: float,
        breadth: float,
        volatility: float,
        label: str,
    ) -> float:
        move_strength = self._clamp(abs(btc_change_pct) / 3.0, 0.0, 1.0)
        breadth_extreme = self._clamp(abs(breadth - 0.5) * 2.0, 0.0, 1.0)
        base = 0.35 + 0.3 * move_strength + 0.25 * breadth_extreme
        if label in ("bull", "bear"):
            base += 0.05
        if volatility > self.high_volatility_threshold:
            excess = volatility - self.high_volatility_threshold
            base -= 0.12 * self._clamp(excess / max(self.high_volatility_threshold, 0.01), 0.0, 1.0)
        return self._clamp(base, 0.2, 0.95)

    def _build_reason(
        self, label: str, btc_change_pct: float, breadth: float, volatility: float
    ) -> str:
        btc_txt = (
            f"BTC 변동은 약 {btc_change_pct:+.2f}% 수준입니다. "
            if abs(btc_change_pct) >= 0.01
            else "BTC 등락 폭은 크지 않습니다. "
        )
        if breadth >= self.high_breadth_threshold:
            breadth_txt = "시장 확산도는 양호한 편으로, 상승 종목 비중이 두드러집니다. "
        elif breadth <= self.low_breadth_threshold:
            breadth_txt = "시장 확산도는 낮아 하락·약세 종목 비중이 상대적으로 큽니다. "
        else:
            breadth_txt = "시장 확산도는 중간대에 머물러 방향성이 엇갈립니다. "
        if volatility > self.high_volatility_threshold:
            vol_txt = (
                f"변동성 지표는 {volatility:.2f}로 다소 높아 불확실성을 키웁니다."
            )
        elif volatility < 0.5:
            vol_txt = f"변동성 지표는 {volatility:.2f}로 상대적으로 안정적입니다."
        else:
            vol_txt = f"변동성 지표는 {volatility:.2f}로 보통 수준입니다."

        if label == "bull":
            return (
                btc_txt
                + breadth_txt
                + vol_txt
                + " 종합하면 BTC 상승과 양호한 시장 확산도를 바탕으로 강세장으로 해석합니다."
            )
        if label == "bear":
            return (
                btc_txt
                + breadth_txt
                + vol_txt
                + " 종합하면 BTC 약세와 낮은 시장 확산도로 인해 방어적 장세로 판단합니다."
            )
        return (
            btc_txt
            + breadth_txt
            + vol_txt
            + " 명확한 일방향 추세가 드러나지 않아 횡보장으로 해석합니다."
        )

    def _safe_log_debug(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "debug"):
                self.logger.debug(message)
        except Exception:
            pass
