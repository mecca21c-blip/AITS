from __future__ import annotations

from app.services.ai_observation_record import (
    AIObservationRecord,
    build_sample_observation_record,
)


class AIObservationStore:
    """Memory-only observation store for AI research diagnostics."""

    def __init__(self) -> None:
        self._records: list[AIObservationRecord] = []

    def append(self, record: AIObservationRecord) -> AIObservationRecord:
        safe_record = self._safe_record(record)
        self._records.append(safe_record)
        return safe_record

    def list_records(
        self,
        provider: str | None = None,
        symbol: str | None = None,
    ) -> list[AIObservationRecord]:
        provider_filter = str(provider or "").strip().lower()
        symbol_filter = str(symbol or "").strip().upper()
        records = list(self._records)
        if provider_filter:
            records = [
                record
                for record in records
                if str(record.provider or "").strip().lower() == provider_filter
            ]
        if symbol_filter:
            records = [
                record
                for record in records
                if str(record.symbol or "").strip().upper() == symbol_filter
            ]
        return records

    def latest(
        self,
        provider: str | None = None,
        symbol: str | None = None,
    ) -> AIObservationRecord | None:
        records = self.list_records(provider=provider, symbol=symbol)
        return records[-1] if records else None

    def clear(self) -> None:
        self._records.clear()

    def build_summary(self) -> dict:
        total = len(self._records)
        providers: dict[str, int] = {}
        symbols: dict[str, int] = {}
        confidence_sum = 0.0
        quality_sum = 0.0
        for record in self._records:
            provider = str(record.provider or "unknown")
            symbol = str(record.symbol or "-")
            providers[provider] = providers.get(provider, 0) + 1
            symbols[symbol] = symbols.get(symbol, 0) + 1
            confidence_sum += self._safe_float(record.confidence)
            quality_sum += self._safe_float(record.quality_score)
        return {
            "total": total,
            "providers": providers,
            "symbols": symbols,
            "avg_confidence": confidence_sum / total if total else 0.0,
            "avg_quality": quality_sum / total if total else 0.0,
            "shadow_only": True,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }

    def _safe_record(self, record: AIObservationRecord) -> AIObservationRecord:
        record.applied = False
        record.submitted = 0
        metadata = dict(record.metadata or {})
        metadata.update(
            {
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
                "research_mode": True,
            }
        )
        record.metadata = metadata
        return record

    def _safe_float(self, value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_observation_store_summary() -> dict:
    store = AIObservationStore()
    store.append(build_sample_observation_record())
    return store.build_summary()


__all__ = [
    "AIObservationStore",
    "build_sample_observation_store_summary",
]
