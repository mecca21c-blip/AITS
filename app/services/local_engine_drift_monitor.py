from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from app.services.local_model_calibration import AITSLocalModelCalibration


class AITSLocalEngineDriftMonitor:
    """Lightweight recent-vs-history drift and health monitor."""

    SCHEMA = "aits_local_engine_drift_state.v1"

    @staticmethod
    def _distribution_distance(left: list[str], right: list[str]) -> float:
        if not left or not right:
            return 0.0
        a, b = Counter(left), Counter(right)
        keys = set(a) | set(b)
        return 0.5 * sum(abs(a[key] / len(left) - b[key] / len(right)) for key in keys)

    def evaluate(self, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if rows is None:
            source = AITSLocalModelCalibration().load_candidate_observations()
            rows = list(source.get("valid_rows") or [])
        midpoint = max(0, len(rows) - min(50, max(1, len(rows) // 3)))
        historical, recent = rows[:midpoint], rows[midpoint:]
        action_drift = self._distribution_distance(
            [str(row.get("action") or "") for row in historical],
            [str(row.get("action") or "") for row in recent],
        )
        historical_confidence = [float(row["confidence"]) for row in historical if row.get("confidence") is not None]
        recent_confidence = [float(row["confidence"]) for row in recent if row.get("confidence") is not None]
        confidence_drift = abs(mean(recent_confidence) - mean(historical_confidence)) if recent_confidence and historical_confidence else 0.0
        disagreement = [
            row for row in recent
            if row.get("final_action") and str(row.get("action")) != str(row.get("final_action"))
        ]
        disagreement_rate = len(disagreement) / len(recent) if recent else 0.0
        drift_score = min(1.0, 0.45 * action_drift + 0.25 * confidence_drift + 0.30 * disagreement_rate)
        status = "degraded" if drift_score >= 0.65 else "watch" if drift_score >= 0.30 or len(recent) < 20 else "stable"
        return {
            "schema": self.SCHEMA,
            "drift_status": status,
            "drift_score": round(drift_score, 6),
            "action_distribution_drift": round(action_drift, 6),
            "confidence_distribution_drift": round(confidence_drift, 6),
            "teacher_disagreement_rate": round(disagreement_rate, 6),
            "outcome_performance_drift": None,
            "feature_distribution_drift": None,
            "ood_score": None,
            "affected_features": [],
            "affected_tasks": [],
            "recent_data_count": len(recent),
            "historical_replay_count": len(historical),
            "level_cap_recommendation": 1 if status == "degraded" else 5,
            "teacher_sync_recommended": status in {"watch", "degraded"},
            "recent_performance": {"teacher_agreement": round(1.0 - disagreement_rate, 6) if recent else None},
            "historical_performance": {"record_count": len(historical)},
            "regime_performance": {},
            "adaptation_gap": round(disagreement_rate, 6),
            "forgetting_risk": "unknown_without_regime_labels",
            "recent_data_weight": 0.7,
            "historical_replay_weight": 0.3,
        }
