from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any


@dataclass
class ShadowPerformanceMetrics:
    total_positions: int
    closed_positions: int
    open_positions: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    max_drawdown_pct: float
    avg_hold_minutes: float
    best_symbol: str
    worst_symbol: str
    provider: str
    metadata: dict = field(default_factory=dict)


class AIShadowPerformanceAnalyzer:
    """AI shadow performance metrics skeleton. It never connects to execution."""

    def build_metrics(
        self,
        positions: list,
        provider: str = "unknown",
    ) -> ShadowPerformanceMetrics:
        provider_name = str(provider or "unknown").strip().lower() or "unknown"
        rows = positions if isinstance(positions, list) else []
        filtered = [
            position
            for position in rows
            if provider_name == "unknown" or self._position_provider(position) == provider_name
        ]
        closed = [position for position in filtered if self._position_closed(position)]
        open_positions = [position for position in filtered if not self._position_closed(position)]
        pnl_values = [self._pnl_pct(position) for position in closed]

        win_values = [value for value in pnl_values if value > 0.0]
        loss_values = [value for value in pnl_values if value < 0.0]
        win_count = len(win_values)
        loss_count = len(loss_values)
        closed_count = len(closed)
        win_rate = win_count / closed_count if closed_count > 0 else 0.0
        avg_pnl_pct = sum(pnl_values) / closed_count if closed_count > 0 else 0.0
        avg_win_pct = sum(win_values) / win_count if win_count > 0 else 0.0
        avg_loss_pct = sum(loss_values) / loss_count if loss_count > 0 else 0.0
        max_drawdown_pct = min(pnl_values) if pnl_values else 0.0
        avg_hold_minutes = self._avg_hold_minutes(closed)
        best_symbol = self._best_symbol(closed)
        worst_symbol = self._worst_symbol(closed)

        metrics = ShadowPerformanceMetrics(
            total_positions=len(filtered),
            closed_positions=closed_count,
            open_positions=len(open_positions),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl_pct,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            max_drawdown_pct=max_drawdown_pct,
            avg_hold_minutes=avg_hold_minutes,
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            provider=provider_name,
            metadata=self._safety_metadata(),
        )
        logging.getLogger("aits").info(
            "[AITS][AIShadowMetrics] metrics_built | provider=%s | win_rate=%.3f",
            metrics.provider,
            metrics.win_rate,
        )
        return metrics

    def _position_provider(self, position: Any) -> str:
        return str(self._get(position, "provider", "unknown") or "unknown").strip().lower() or "unknown"

    def _position_closed(self, position: Any) -> bool:
        return bool(self._get(position, "closed", False))

    def _pnl_pct(self, position: Any) -> float:
        return self._safe_float(self._get(position, "pnl_pct", 0.0), 0.0)

    def _best_symbol(self, positions: list) -> str:
        if not positions:
            return "-"
        best = max(positions, key=lambda position: self._pnl_pct(position))
        return str(self._get(best, "symbol", "-") or "-")

    def _worst_symbol(self, positions: list) -> str:
        if not positions:
            return "-"
        worst = min(positions, key=lambda position: self._pnl_pct(position))
        return str(self._get(worst, "symbol", "-") or "-")

    def _avg_hold_minutes(self, positions: list) -> float:
        values = [
            self._safe_float(self._get(position, "hold_minutes", 0.0), 0.0)
            for position in positions
        ]
        values = [value for value in values if value > 0.0]
        return sum(values) / len(values) if values else 0.0

    def _get(self, obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safety_metadata(self) -> dict:
        return {
            "real_order": False,
            "virtual_only": True,
            "submitted": 0,
            "research_mode": True,
        }


def build_sample_shadow_performance_metrics() -> ShadowPerformanceMetrics:
    positions = [
        {
            "symbol": "KRW-BTC",
            "provider": "mock",
            "pnl_pct": 2.4,
            "closed": True,
            "hold_minutes": 45,
        },
        {
            "symbol": "KRW-ETH",
            "provider": "mock",
            "pnl_pct": -1.1,
            "closed": True,
            "hold_minutes": 30,
        },
        {
            "symbol": "KRW-XRP",
            "provider": "mock",
            "pnl_pct": 0.0,
            "closed": False,
            "hold_minutes": 0,
        },
    ]
    return AIShadowPerformanceAnalyzer().build_metrics(positions, provider="mock")


__all__ = [
    "ShadowPerformanceMetrics",
    "AIShadowPerformanceAnalyzer",
    "build_sample_shadow_performance_metrics",
]
