from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any


@dataclass
class ScenarioPerformanceSummary:
    scenario: str
    total: int
    closed: int
    open: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl_pct: float
    avg_confidence: float
    avg_hold_minutes: float
    best_symbol: str
    worst_symbol: str
    metadata: dict = field(default_factory=dict)


class AIScenarioPerformanceTracker:
    """Scenario-level AI shadow performance skeleton. It never executes orders."""

    def build_scenario_stats(self, positions: list) -> dict:
        rows = positions if isinstance(positions, list) else []
        grouped: dict[str, list] = {}
        for position in rows:
            scenario = self._scenario(position)
            grouped.setdefault(scenario, []).append(position)

        summaries = {
            scenario: self._build_summary(scenario, scenario_positions)
            for scenario, scenario_positions in grouped.items()
        }
        result = {
            "total": len(rows),
            "scenarios": summaries,
        }
        logging.getLogger("aits").info(
            "[AITS][AIScenarioStats] scenario_stats_built | total=%s | scenarios=%s",
            result["total"],
            len(summaries),
        )
        return result

    def _build_summary(self, scenario: str, positions: list) -> ScenarioPerformanceSummary:
        closed_positions = [position for position in positions if self._closed(position)]
        open_positions = [position for position in positions if not self._closed(position)]
        pnl_values = [self._pnl_pct(position) for position in closed_positions]
        win_values = [value for value in pnl_values if value > 0.0]
        loss_values = [value for value in pnl_values if value < 0.0]
        confidence_values = [self._confidence(position) for position in positions]
        hold_values = [
            self._safe_float(self._get(position, "hold_minutes", 0.0), 0.0)
            for position in closed_positions
        ]
        hold_values = [value for value in hold_values if value > 0.0]

        closed_count = len(closed_positions)
        win_count = len(win_values)
        loss_count = len(loss_values)
        return ScenarioPerformanceSummary(
            scenario=scenario,
            total=len(positions),
            closed=closed_count,
            open=len(open_positions),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_count / closed_count if closed_count > 0 else 0.0,
            avg_pnl_pct=sum(pnl_values) / closed_count if closed_count > 0 else 0.0,
            avg_confidence=(
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else 0.0
            ),
            avg_hold_minutes=sum(hold_values) / len(hold_values) if hold_values else 0.0,
            best_symbol=self._best_symbol(closed_positions),
            worst_symbol=self._worst_symbol(closed_positions),
            metadata=self._safety_metadata(),
        )

    def _scenario(self, position: Any) -> str:
        direct = str(self._get(position, "scenario", "") or "").strip()
        if direct:
            return direct
        metadata = self._get(position, "metadata", {}) or {}
        if isinstance(metadata, dict):
            value = str(metadata.get("scenario") or "").strip()
            if value:
                return value
        return "-"

    def _confidence(self, position: Any) -> float:
        metadata = self._get(position, "metadata", {}) or {}
        if isinstance(metadata, dict):
            return self._safe_float(metadata.get("confidence"), 0.0)
        return 0.0

    def _closed(self, position: Any) -> bool:
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


def build_sample_scenario_performance_stats() -> dict:
    positions = [
        {
            "symbol": "KRW-BTC",
            "scenario": "횡보 관찰형",
            "pnl_pct": 1.2,
            "closed": True,
            "hold_minutes": 30,
            "metadata": {"confidence": 0.62},
        },
        {
            "symbol": "KRW-ETH",
            "scenario": "횡보 관찰형",
            "pnl_pct": -0.4,
            "closed": True,
            "hold_minutes": 40,
            "metadata": {"confidence": 0.58},
        },
        {
            "symbol": "KRW-XRP",
            "scenario": "리스크 회피형",
            "pnl_pct": 0.0,
            "closed": False,
            "metadata": {"confidence": 0.71},
        },
        {
            "symbol": "KRW-SOL",
            "scenario": "장기 관찰형",
            "pnl_pct": 0.0,
            "closed": False,
            "metadata": {"confidence": 0.49},
        },
    ]
    return AIScenarioPerformanceTracker().build_scenario_stats(positions)


__all__ = [
    "ScenarioPerformanceSummary",
    "AIScenarioPerformanceTracker",
    "build_sample_scenario_performance_stats",
]
