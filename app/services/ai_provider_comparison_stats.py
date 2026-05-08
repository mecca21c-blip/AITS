from __future__ import annotations

import logging
from typing import Any


class AIProviderComparisonStats:
    """Provider comparison stats for AI shadow records. It never applies actions."""

    _SUGGESTION_FIELDS = ("confirm", "reject", "skip")
    _ACTION_FIELDS = ("watch", "buy", "sell", "hold", "remove")

    def build_stats(self, records: list[dict]) -> dict:
        rows = records if isinstance(records, list) else []
        providers: dict[str, dict] = {}
        total = 0

        for record in rows:
            if not isinstance(record, dict):
                continue
            shadow = record.get("ai_shadow")
            if not isinstance(shadow, dict):
                continue

            provider = str(shadow.get("provider") or "unknown").strip().lower() or "unknown"
            suggestion = self._normalize_suggestion(shadow.get("suggestion"))
            next_action = self._normalize_action(shadow.get("next_action"))
            confidence = self._safe_float(shadow.get("confidence"), 0.0)
            applied = bool(shadow.get("applied"))

            bucket = providers.setdefault(provider, self._empty_provider_bucket())
            bucket["total"] += 1
            bucket[suggestion] += 1
            bucket[next_action] += 1
            bucket["applied_count"] += 1 if applied else 0
            bucket["_confidence_sum"] += confidence
            total += 1

        for bucket in providers.values():
            count = int(bucket.get("total") or 0)
            confidence_sum = float(bucket.pop("_confidence_sum", 0.0) or 0.0)
            bucket["avg_confidence"] = confidence_sum / count if count > 0 else 0.0

        result = {
            "total": total,
            "providers": providers,
        }
        logging.getLogger("aits").info(
            "[AITS][AIProviderStats] stats_built | total=%s | providers=%s",
            total,
            len(providers),
        )
        return result

    def _empty_provider_bucket(self) -> dict:
        return {
            "total": 0,
            "confirm": 0,
            "reject": 0,
            "skip": 0,
            "watch": 0,
            "buy": 0,
            "sell": 0,
            "hold": 0,
            "remove": 0,
            "avg_confidence": 0.0,
            "applied_count": 0,
            "_confidence_sum": 0.0,
        }

    def _normalize_suggestion(self, value: Any) -> str:
        suggestion = str(value or "skip").strip().lower() or "skip"
        if suggestion in self._SUGGESTION_FIELDS:
            return suggestion
        if suggestion.startswith("reject"):
            return "reject"
        return "skip"

    def _normalize_action(self, value: Any) -> str:
        action = str(value or "wait").strip().lower() or "wait"
        if action in self._ACTION_FIELDS:
            return action
        if action == "wait":
            return "watch"
        return "watch"

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)


def build_sample_provider_comparison_stats() -> dict:
    records = [
        {
            "ai_shadow": {
                "provider": "openai",
                "suggestion": "confirm",
                "next_action": "watch",
                "confidence": 0.71,
                "applied": False,
            }
        },
        {
            "ai_shadow": {
                "provider": "gemini",
                "suggestion": "skip",
                "next_action": "wait",
                "confidence": 0.42,
                "applied": False,
            }
        },
        {
            "ai_shadow": {
                "provider": "ollama",
                "suggestion": "confirm",
                "next_action": "watch",
                "confidence": 0.64,
                "applied": False,
            }
        },
        {
            "ai_shadow": {
                "provider": "mock",
                "suggestion": "reject",
                "next_action": "remove",
                "confidence": 0.38,
                "applied": False,
            }
        },
    ]
    return AIProviderComparisonStats().build_stats(records)


__all__ = [
    "AIProviderComparisonStats",
    "build_sample_provider_comparison_stats",
]
