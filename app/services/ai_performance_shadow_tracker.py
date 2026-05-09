from __future__ import annotations

import logging
from typing import Any

from app.services.paper_shadow_models import PaperShadowPosition, PaperShadowResult


class AIPerformanceShadowTracker:
    """AI judgment performance tracker. This is not a virtual trading engine."""

    def __init__(self) -> None:
        self._positions: dict[str, PaperShadowPosition] = {}
        self._history: list[PaperShadowResult] = []
        self._log = logging.getLogger("aits")

    def track_shadow_action(
        self,
        symbol: str,
        ai_shadow: dict,
        current_price: float,
    ) -> PaperShadowResult:
        symbol_text = str(symbol or "").strip()
        shadow = ai_shadow if isinstance(ai_shadow, dict) else {}
        action = str(shadow.get("next_action") or "wait").strip().lower() or "wait"
        provider = str(shadow.get("provider") or "unknown").strip().lower() or "unknown"
        price = self._safe_float(current_price, 0.0)

        if action == "buy":
            result = self._track_entry(symbol_text, provider, shadow, price)
        elif action in ("hold", "watch", "wait"):
            result = self._track_hold(symbol_text, provider, action, shadow, price)
        elif action in ("sell", "remove"):
            result = self._track_close(symbol_text, provider, action, shadow, price)
        elif action == "reduce":
            result = self._track_reduce_placeholder(symbol_text, provider, shadow, price)
        else:
            result = self._build_result(
                symbol=symbol_text,
                provider=provider,
                action=action,
                position=self._positions.get(symbol_text),
                reason="unsupported_action_monitoring_only",
            )

        self._history.append(result)
        self._log.info(
            "[AITS][AIShadowTracker] shadow_action_tracked | symbol=%s | action=%s | virtual_only=True",
            symbol_text,
            action,
        )
        return result

    def build_tracker_summary(self) -> dict:
        providers = sorted(
            {
                str(result.provider or "unknown")
                for result in self._history
                if str(result.provider or "").strip()
            }
        )
        closed_positions = [
            position
            for position in self._positions.values()
            if bool(position.closed)
        ]
        win_count = sum(1 for position in closed_positions if float(position.pnl_pct or 0.0) > 0.0)
        loss_count = sum(1 for position in closed_positions if float(position.pnl_pct or 0.0) < 0.0)
        return {
            "total_positions": len(self._positions),
            "open_positions": sum(1 for position in self._positions.values() if not position.closed),
            "closed_positions": len(closed_positions),
            "providers": providers,
            "win_count": win_count,
            "loss_count": loss_count,
        }

    def _track_entry(
        self,
        symbol: str,
        provider: str,
        shadow: dict,
        current_price: float,
    ) -> PaperShadowResult:
        position = PaperShadowPosition(
            symbol=symbol,
            provider=provider,
            entry_price=current_price,
            current_price=current_price,
            qty_virtual=1.0,
            entry_time="shadow",
            exit_time=None,
            pnl_pct=0.0,
            pnl_krw=0.0,
            state="open",
            scenario=self._scenario_text(shadow),
            eta_minutes=self._eta_minutes(shadow),
            closed=False,
            metadata=self._safe_metadata({"source": "paper_shadow"}),
        )
        self._positions[symbol] = position
        return self._build_result(
            symbol=symbol,
            provider=provider,
            action="buy",
            position=position,
            reason="shadow_entry_recorded",
        )

    def _track_hold(
        self,
        symbol: str,
        provider: str,
        action: str,
        shadow: dict,
        current_price: float,
    ) -> PaperShadowResult:
        position = self._positions.get(symbol)
        if position is None:
            return self._build_result(
                symbol=symbol,
                provider=provider,
                action=action,
                position=None,
                reason="monitoring_only_no_position",
            )
        position.current_price = current_price
        position.scenario = self._scenario_text(shadow) or position.scenario
        position.eta_minutes = self._eta_minutes(shadow)
        self._update_position_pnl(position)
        return self._build_result(
            symbol=symbol,
            provider=provider,
            action=action,
            position=position,
            reason="shadow_position_held",
        )

    def _track_close(
        self,
        symbol: str,
        provider: str,
        action: str,
        shadow: dict,
        current_price: float,
    ) -> PaperShadowResult:
        position = self._positions.get(symbol)
        if position is None:
            return self._build_result(
                symbol=symbol,
                provider=provider,
                action=action,
                position=None,
                reason="close_signal_without_position",
            )
        position.current_price = current_price
        position.closed = True
        position.exit_time = "shadow"
        position.state = "closed"
        position.scenario = self._scenario_text(shadow) or position.scenario
        position.eta_minutes = self._eta_minutes(shadow)
        self._update_position_pnl(position)
        return self._build_result(
            symbol=symbol,
            provider=provider,
            action=action,
            position=position,
            reason="shadow_position_closed",
        )

    def _track_reduce_placeholder(
        self,
        symbol: str,
        provider: str,
        shadow: dict,
        current_price: float,
    ) -> PaperShadowResult:
        position = self._positions.get(symbol)
        if position is not None:
            position.current_price = current_price
            position.state = "partial_reduce_placeholder"
            position.scenario = self._scenario_text(shadow) or position.scenario
            position.eta_minutes = self._eta_minutes(shadow)
            self._update_position_pnl(position)
        return self._build_result(
            symbol=symbol,
            provider=provider,
            action="reduce",
            position=position,
            reason="partial_reduce_placeholder_only",
        )

    def _build_result(
        self,
        *,
        symbol: str,
        provider: str,
        action: str,
        position: PaperShadowPosition | None,
        reason: str,
        error: str | None = None,
    ) -> PaperShadowResult:
        return PaperShadowResult(
            symbol=symbol,
            provider=provider,
            action=action,
            applied=False,
            virtual_only=True,
            position=position,
            reason=reason,
            error=error,
            metadata=self._safe_metadata({"source": "paper_shadow"}),
        )

    def _update_position_pnl(self, position: PaperShadowPosition) -> None:
        if position.entry_price <= 0:
            position.pnl_pct = 0.0
            position.pnl_krw = 0.0
            return
        position.pnl_pct = ((position.current_price - position.entry_price) / position.entry_price) * 100.0
        position.pnl_krw = (position.current_price - position.entry_price) * position.qty_virtual

    def _scenario_text(self, shadow: dict) -> str:
        scenario = shadow.get("scenario") if isinstance(shadow.get("scenario"), dict) else {}
        if isinstance(scenario, dict):
            return str(scenario.get("label_ko") or scenario.get("name") or "").strip()
        return ""

    def _eta_minutes(self, shadow: dict) -> int:
        eta = shadow.get("eta") if isinstance(shadow.get("eta"), dict) else {}
        return self._safe_int(eta.get("remaining_minutes"), 0)

    def _safe_metadata(self, extra: dict | None = None) -> dict:
        metadata = dict(extra or {})
        metadata["real_order"] = False
        metadata["submitted"] = 0
        return metadata

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return int(default)


def build_sample_shadow_tracker_result() -> PaperShadowResult:
    tracker = AIPerformanceShadowTracker()
    return tracker.track_shadow_action(
        symbol="KRW-BTC",
        ai_shadow={
            "provider": "mock",
            "next_action": "buy",
            "scenario": {"label_ko": "횡보 관찰형", "name": "sideways_watch"},
            "eta": {"remaining_minutes": 30},
            "applied": False,
        },
        current_price=100_000_000.0,
    )


__all__ = [
    "AIPerformanceShadowTracker",
    "build_sample_shadow_tracker_result",
]
