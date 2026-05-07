from __future__ import annotations

from dataclasses import dataclass, field
import logging

from app.services.ai_state_machine import AIStateSnapshot


@dataclass
class AIStateHistoryRecord:
    symbol: str
    previous_state: str
    state: str
    reason: str
    scenario: str
    confidence: float
    eta_minutes: int
    timestamp: str
    metadata: dict = field(default_factory=dict)


class AIStateHistoryManager:
    """In-memory AI state history skeleton. It does not execute orders."""

    def __init__(self) -> None:
        self._records: list[AIStateHistoryRecord] = []
        self._log = logging.getLogger("aits")

    def append_snapshot(self, snapshot: AIStateSnapshot) -> AIStateHistoryRecord:
        metadata = getattr(snapshot, "metadata", None)
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        metadata["suggestion_only"] = True
        metadata["applied_to_action"] = False

        record = AIStateHistoryRecord(
            symbol=str(getattr(snapshot, "symbol", "") or "").strip(),
            previous_state=str(getattr(snapshot, "previous_state", "") or "").strip(),
            state=str(getattr(snapshot, "state", "") or "").strip(),
            reason=str(getattr(snapshot, "reason", "") or "").strip(),
            scenario=str(getattr(snapshot, "scenario", "") or "").strip(),
            confidence=self._safe_float(getattr(snapshot, "confidence", 0.0), 0.0),
            eta_minutes=self._safe_int(getattr(snapshot, "eta_minutes", 0), 0),
            timestamp=str(getattr(snapshot, "updated_at", "") or "").strip(),
            metadata=metadata,
        )
        self._records.append(record)
        self._log.info(
            "[AITS][AIStateHistory] record_appended | symbol=%s | from=%s | to=%s",
            record.symbol,
            record.previous_state,
            record.state,
        )
        return record

    def list_records(self, symbol: str | None = None) -> list[AIStateHistoryRecord]:
        key = str(symbol or "").strip()
        if not key:
            return list(self._records)
        return [record for record in self._records if record.symbol == key]

    def latest(self, symbol: str) -> AIStateHistoryRecord | None:
        key = str(symbol or "").strip()
        if not key:
            return None
        for record in reversed(self._records):
            if record.symbol == key:
                return record
        return None

    def clear(self, symbol: str | None = None) -> None:
        key = str(symbol or "").strip()
        if not key:
            self._records.clear()
            return
        self._records = [record for record in self._records if record.symbol != key]

    def build_summary(self) -> dict:
        by_state: dict[str, int] = {}
        symbols: set[str] = set()
        for record in self._records:
            state = str(record.state or "idle").strip().lower() or "idle"
            by_state[state] = int(by_state.get(state, 0)) + 1
            if record.symbol:
                symbols.add(record.symbol)

        summary = {
            "total": len(self._records),
            "by_state": by_state,
            "symbols": len(symbols),
        }
        self._log.info(
            "[AITS][AIStateHistory] summary_built | total=%s | symbols=%s",
            summary["total"],
            summary["symbols"],
        )
        return summary

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_int(self, value, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return int(default)


__all__ = [
    "AIStateHistoryRecord",
    "AIStateHistoryManager",
]
