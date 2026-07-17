from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


PERIOD_SUMMARY_SCHEMA = "aits_data_period_summary.v1"


class AITSDataCompactor:
    """Factual period summaries; summaries never replace their source."""

    PERIODS = ("daily", "weekly", "monthly")

    @staticmethod
    def summarize(records: Iterable[dict[str, Any]], *, period_type: str, period_start: str, period_end: str,
                  source_dataset_ids: list[str]) -> dict[str, Any]:
        if period_type not in AITSDataCompactor.PERIODS:
            raise ValueError("unsupported_period_type")
        rows = list(records)
        actions: dict[str, int] = {}
        providers: dict[str, int] = {}
        for row in rows:
            action = str(row.get("action") or row.get("final_action") or "unavailable")
            provider = str(row.get("provider") or row.get("provider_source") or "unavailable")
            actions[action] = actions.get(action, 0) + 1
            providers[provider] = providers.get(provider, 0) + 1
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
        return {
            "schema": PERIOD_SUMMARY_SCHEMA,
            "summary_id": f"{period_type}:{period_start}:{period_end}",
            "period_type": period_type, "period_start": period_start, "period_end": period_end,
            "source_dataset_ids": source_dataset_ids, "source_record_count": len(rows),
            "source_checksum_digest": digest,
            "decision_summary": {"action_counts": actions, "provider_counts": providers},
            "outcome_summary": {}, "review_summary": {}, "learning_summary": {},
            "model_summary": {}, "authority_summary": {}, "safety_summary": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "factual_only": True, "source_preserved": True,
        }
