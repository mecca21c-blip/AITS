from __future__ import annotations

from collections import Counter, defaultdict
import math
from statistics import fmean
from typing import Any, Iterable

from app.services.local_model_calibration import AITSLocalModelCalibration


class AITSLocalEnginePerformanceReport:
    """Build a read-only LOCAL_ENGINE performance report from observed records."""

    SCHEMA = "aits_local_engine_performance_report.v1"

    def __init__(self, calibration: AITSLocalModelCalibration | None = None) -> None:
        self.calibration = calibration or AITSLocalModelCalibration()

    @staticmethod
    def _action(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _rate(matches: int, total: int) -> float | None:
        return round(matches / total, 6) if total else None

    @staticmethod
    def _counter(values: Iterable[Any]) -> dict[str, int]:
        return dict(sorted(Counter(str(value or "") for value in values).items()))

    @classmethod
    def _matrix(cls, rows: Iterable[dict], right_key: str) -> dict[str, dict[str, int]]:
        matrix: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            left = cls._action(row.get("action")) or "unknown"
            right = cls._action(row.get(right_key)) or "unknown"
            matrix[left][right] += 1
        return {left: dict(sorted(counts.items())) for left, counts in sorted(matrix.items())}

    @classmethod
    def _match_summary(cls, rows: list[dict], right_key: str) -> dict[str, Any]:
        comparable = [row for row in rows if cls._action(row.get(right_key))]
        matched = sum(cls._action(row.get("action")) == cls._action(row.get(right_key)) for row in comparable)
        return {
            "count": len(comparable),
            "matched_count": matched,
            "match_rate": cls._rate(matched, len(comparable)),
        }

    @classmethod
    def _group_match(cls, rows: list[dict], key: str, right_key: str = "final_action") -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[str(row.get(key) or "unknown")].append(row)
        return {
            name: cls._match_summary(group, right_key)
            for name, group in sorted(groups.items())
        }

    @staticmethod
    def _numeric_summary(values: Iterable[Any]) -> dict[str, Any]:
        numbers: list[float] = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                numbers.append(number)
        return {
            "count": len(numbers),
            "min": round(min(numbers), 6) if numbers else None,
            "max": round(max(numbers), 6) if numbers else None,
            "avg": round(fmean(numbers), 6) if numbers else None,
        }

    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        if len(xs) < 2 or len(xs) != len(ys):
            return None
        x_avg = fmean(xs)
        y_avg = fmean(ys)
        numerator = sum((x - x_avg) * (y - y_avg) for x, y in zip(xs, ys))
        x_var = sum((x - x_avg) ** 2 for x in xs)
        y_var = sum((y - y_avg) ** 2 for y in ys)
        if x_var <= 0.0 or y_var <= 0.0:
            return None
        return round(numerator / math.sqrt(x_var * y_var), 6)

    @classmethod
    def _checkpoint_metrics(cls, rows: list[dict]) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            checkpoint = dict(row.get("checkpoint") or {})
            name = str(checkpoint.get("checkpoint_name") or "unknown")
            groups[name].append(checkpoint)
        result: dict[str, dict[str, Any]] = {}
        for name, checkpoints in sorted(groups.items()):
            result[name] = {
                "count": len(checkpoints),
                "price_change_pct": cls._numeric_summary(row.get("price_change_pct") for row in checkpoints),
                "pnl_change_pct": cls._numeric_summary(row.get("pnl_change_pct") for row in checkpoints),
                "portfolio_change_pct": cls._numeric_summary(row.get("portfolio_change_pct") for row in checkpoints),
            }
        return result

    def build(self) -> dict[str, Any]:
        source = self.calibration.load_sources()
        candidate_source = self.calibration.load_candidate_observations()
        candidates = list(candidate_source.get("valid_rows") or [])
        joined_outcomes = [
            row for row in source.get("rows_by_source", {}).get("outcomes", [])
            if row.get("local_engine_candidate_join_status") == "matched"
        ]
        usable = list(source.get("records") or [])

        teacher_rows = [row for row in candidates if str(row.get("teacher_source") or "").strip()]
        openai_rows = [row for row in candidates if str(row.get("teacher_source") or "").lower() == "openai"]
        teacher_blank_rows = [row for row in candidates if not str(row.get("teacher_source") or "").strip()]
        safety_hold_rows = [
            row for row in candidates if str(row.get("final_provider_source") or "").lower() == "local_safety_hold"
        ]
        cooldown_rows = [
            row for row in teacher_blank_rows
            if str((row.get("provider_cost_guard_result") or {}).get("blocker") or "")
            == "provider_request_cooldown"
        ]

        # Candidate observations do not carry a separate teacher_action field. When an
        # external teacher exists, final_action is the recorded teacher decision proxy.
        teacher_comparable = [dict(row, teacher_action=row.get("final_action")) for row in teacher_rows]
        final_match = self._match_summary(candidates, "final_action")
        teacher_match = self._match_summary(teacher_comparable, "teacher_action")
        openai_match = self._match_summary(
            [dict(row, teacher_action=row.get("final_action")) for row in openai_rows], "teacher_action"
        )
        safety_hold_match = self._match_summary(safety_hold_rows, "final_action")

        confidences = [float(row["confidence"]) for row in candidates]
        unique_confidences = sorted(set(confidences))
        confidence_counts = Counter(confidences)
        confidence_dominant_count = max(confidence_counts.values(), default=0)
        confidence_dominant_ratio = self._rate(confidence_dominant_count, len(confidences))
        confidence_fixed = bool(
            len(candidates) > 1
            and (len(unique_confidences) == 1 or float(confidence_dominant_ratio or 0.0) >= 0.95)
        )
        confidence_calibrated_count = sum(row.get("confidence_calibrated") is True for row in candidates)
        confidence_uncalibrated_count = sum(row.get("confidence_calibrated") is not True for row in candidates)

        confidence_outcome_pairs = [
            (float(row["model_confidence"]), float(row["outcome_score"]))
            for row in usable
            if row.get("model_confidence") is not None and row.get("outcome_score") is not None
        ]
        confidence_outcome_correlation_raw = self._pearson(
            [pair[0] for pair in confidence_outcome_pairs],
            [pair[1] for pair in confidence_outcome_pairs],
        )
        confidence_learning_signal_valid = bool(
            confidence_outcome_correlation_raw is not None
            and len(unique_confidences) >= 3
            and not confidence_fixed
        )
        confidence_outcome_correlation = (
            confidence_outcome_correlation_raw if confidence_learning_signal_valid else None
        )
        confidence_outcome_correlation_blocker = (
            "" if confidence_learning_signal_valid else "confidence_concentrated_correlation_not_reliable"
        )
        outcome_metric_available = bool(usable)
        if not usable:
            outcome_metric_blocker = "usable_calibration_zero"
        else:
            outcome_metric_blocker = ""

        local_actions = Counter(self._action(row.get("action")) or "unknown" for row in candidates)
        non_wait_actions = sum(count for action, count in local_actions.items() if action not in {"wait", "hold"})
        wait_count = sum(local_actions[action] for action in ("wait", "hold"))
        blockers = Counter(
            str(blocker) for row in candidates for blocker in (row.get("blockers") or []) if str(blocker)
        )
        invalidation_empty_count = sum(not list(row.get("invalidation_conditions") or []) for row in candidates)

        outcome_labels = Counter(str(row.get("outcome_label") or "") for row in usable)
        outcome_correct_count = sum(bool(row.get("model_action_correct")) for row in usable)
        matched_checkpoint_equal = [
            row for row in joined_outcomes
            if self._action(row.get("local_model_action"))
            == self._action((row.get("final_decision") or {}).get("action"))
        ]
        matched_checkpoint_different = [row for row in joined_outcomes if row not in matched_checkpoint_equal]

        all_outcomes = list(source.get("rows_by_source", {}).get("outcomes", []))
        portfolio_blocked = len({
            str(row.get("decision_id") or "")
            for row in all_outcomes
            if str(row.get("task") or "") == "portfolio_management_decision"
            and bool(row.get("local_engine_candidate_observation_blocker") or row.get("local_engine_observation_blocker"))
            and str(row.get("decision_id") or "")
        })
        local_final_action_used_count = sum(row.get("local_model_used_for_final") is True for row in all_outcomes)
        applied_count = sum(row.get("applied_to_final_action") is True for row in candidates)

        recommended = ["F. non-wait candidate 확보를 위한 data collection", "B. confidence calibration 개선"]
        first_blocker = "local_engine_performance_report_ready"
        if candidate_source.get("fake_prediction_detected"):
            first_blocker = "fake_prediction_detected"
        elif candidate_source.get("unsafe_candidate_contract_detected"):
            first_blocker = "unsafe_candidate_contract_detected"
        elif not candidate_source.get("candidate_observation_source_loaded"):
            first_blocker = "candidate_observation_source_missing"
        elif not source.get("candidate_join_matched_count"):
            first_blocker = "candidate_join_no_matches"
        elif not source.get("calibration_usable_records_count"):
            first_blocker = "usable_calibration_zero"

        report = {
            "schema": self.SCHEMA,
            "local_engine_performance_report_ready": first_blocker == "local_engine_performance_report_ready",
            "candidate_observation_records_count": int(candidate_source.get("candidate_observation_records_count") or 0),
            "valid_candidate_count": len(candidates),
            "joined_checkpoint_count": int(source.get("candidate_join_matched_count") or 0),
            "unique_joined_decision_count": len({
                str(row.get("decision_id") or "") for row in joined_outcomes if str(row.get("decision_id") or "")
            }),
            "usable_calibration_count": len(usable),
            "excluded_no_candidate_count": int(source.get("missing_local_model_prediction_after_join") or 0),
            "corrupt_candidate_count": int(candidate_source.get("candidate_observation_corrupt_count") or 0),
            "unsafe_candidate_contract_count": int(candidate_source.get("candidate_observation_invalid_count") or 0),
            "local_action_counts": dict(sorted(local_actions.items())),
            "final_action_counts": self._counter(row.get("final_action") for row in candidates),
            "teacher_action_counts": self._counter(row.get("final_action") for row in teacher_rows),
            "local_vs_final_matrix": self._matrix(candidates, "final_action"),
            "local_vs_teacher_matrix": self._matrix(teacher_comparable, "teacher_action"),
            "local_final_exact_match_rate": final_match["match_rate"],
            "local_final_exact_match_count": final_match["matched_count"],
            "local_teacher_exact_match_rate": teacher_match["match_rate"],
            "local_teacher_exact_match_count": teacher_match["matched_count"],
            "local_openai_exact_match_rate": openai_match["match_rate"],
            "local_openai_exact_match_count": openai_match["matched_count"],
            "local_safety_hold_match_rate": safety_hold_match["match_rate"],
            "action_match_rates": self._group_match(candidates, "action"),
            "scope_match_rates": self._group_match(candidates, "scope"),
            "task_match_rates": self._group_match(candidates, "task"),
            "wait_ratio": self._rate(wait_count, len(candidates)),
            "non_wait_ratio": self._rate(non_wait_actions, len(candidates)),
            "non_wait_candidate_present": non_wait_actions > 0,
            "buy_candidate_present": bool(local_actions.get("buy") or local_actions.get("add")),
            "sell_candidate_present": bool(local_actions.get("sell") or local_actions.get("reduce")),
            "take_profit_candidate_present": bool(local_actions.get("take_profit")),
            "rotate_candidate_present": bool(local_actions.get("rotate")),
            "confidence_distribution": self._counter(row.get("confidence") for row in candidates),
            "confidence_unique_count": len(unique_confidences),
            "confidence_min": round(min(confidences), 6) if confidences else None,
            "confidence_max": round(max(confidences), 6) if confidences else None,
            "confidence_avg": round(fmean(confidences), 6) if confidences else None,
            "confidence_fixed_detected": confidence_fixed,
            "confidence_dominant_value_count": confidence_dominant_count,
            "confidence_dominant_ratio": confidence_dominant_ratio,
            "confidence_calibrated_count": confidence_calibrated_count,
            "confidence_uncalibrated_count": confidence_uncalibrated_count,
            "confidence_outcome_correlation": confidence_outcome_correlation,
            "confidence_outcome_correlation_raw": confidence_outcome_correlation_raw,
            "confidence_outcome_correlation_blocker": confidence_outcome_correlation_blocker,
            "confidence_learning_signal_valid": confidence_learning_signal_valid,
            "scope_candidate_counts": self._counter(row.get("scope") for row in candidates),
            "task_candidate_counts": self._counter(row.get("task") for row in candidates),
            "teacher_source_counts": self._counter(row.get("teacher_source") for row in candidates),
            "teacher_blank_count": len(teacher_blank_rows),
            "local_safety_hold_count": len(safety_hold_rows),
            "cost_guard_cooldown_teacher_absent_count": len(cooldown_rows),
            "teacher_present_local_final_match_rate": teacher_match["match_rate"],
            "teacher_absent_local_final_match_rate": safety_hold_match["match_rate"],
            "teacher_action_derivation": "final_action_when_teacher_source_present",
            "teacher_absent_reason_recommended": bool(teacher_blank_rows),
            "risk_distribution": self._counter(row.get("risk_level") for row in candidates),
            "blocker_distribution": dict(sorted(blockers.items())),
            "eta_distribution": self._counter(row.get("eta_seconds") for row in candidates),
            "invalidation_empty_count": invalidation_empty_count,
            "invalidation_empty_ratio": self._rate(invalidation_empty_count, len(candidates)),
            "portfolio_prediction_blocked_count": portfolio_blocked,
            "outcome_metric_available": outcome_metric_available,
            "outcome_metric_blocker": outcome_metric_blocker,
            "outcome_label_counts": dict(sorted(outcome_labels.items())),
            "outcome_action_correct_count": outcome_correct_count,
            "outcome_action_correct_rate": self._rate(outcome_correct_count, len(usable)),
            "outcome_score_summary": self._numeric_summary(row.get("outcome_score") for row in usable),
            "price_change_pct_summary": self._numeric_summary(row.get("price_change_pct") for row in usable),
            "pnl_change_pct_summary": self._numeric_summary(row.get("pnl_change_pct") for row in usable),
            "checkpoint_metrics": self._checkpoint_metrics(joined_outcomes),
            "same_as_final_checkpoint_count": len(matched_checkpoint_equal),
            "different_from_final_checkpoint_count": len(matched_checkpoint_different),
            "recommended_next_sprint": recommended,
            "safe_for_live_expansion": False,
            "local_final_action_used_count": local_final_action_used_count,
            "applied_to_final_action_count": applied_count,
            "fake_prediction_detected": bool(candidate_source.get("fake_prediction_detected")),
            "source_records_modified": False,
            "first_blocker": first_blocker,
        }
        return report
