"""Local AI evaluation dashboard preview report builder.

This module builds dict/JSON/Markdown summaries from already generated preview
artifacts. It is not a PySide6 GUI dashboard and does not run training, model
inference, Router, Runtime, Execution, Order, or Risk Guard paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

DASHBOARD_SCHEMA = "aits_local_ai_evaluation_dashboard_preview.v1"
SECRET_MARKERS = (
    "api_key",
    "secret_key",
    "authorization",
    "SHOULD_NOT_BE_STORED",
)
LEAKAGE_MARKERS = (
    "raw_future_candles",
    "pnl_after_",
    "hit_take_profit",
    "human_review_score",
)
EXECUTION_LINK_MARKERS = ("OrderAdapter", "ExecutionBridge", "order_service")
UI_LINK_MARKERS = ("app_gui", "PySide6", "QWidget")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_div(numerator: int | float, denominator: int | float) -> float | None:
    """Divide safely, returning None for zero denominator."""

    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 4)


def count_by(items: list[dict], getter: Callable[[dict], object]) -> dict:
    """Count distribution values with unknown fallback."""

    counts: dict[str, int] = {}
    for item in items or []:
        try:
            value = getter(item)
        except Exception:
            value = None
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def summarize_distillation_samples(samples: list[dict]) -> dict:
    total = len(samples or [])
    usable = [
        sample
        for sample in samples or []
        if _dict_at(sample, "quality").get("usable_for_distillation") is True
    ]
    weights = [
        _float_or_none(_dict_at(sample, "quality").get("sample_weight_hint"))
        for sample in samples or []
    ]
    weights = [weight for weight in weights if weight is not None]
    return {
        "total_samples": total,
        "usable_samples": len(usable),
        "excluded_samples": total - len(usable),
        "teacher_provider_distribution": count_by(
            samples or [],
            lambda sample: sample.get("source_provider"),
        ),
        "label_ready_count": _count_truthy(samples, "labels", "label_ready"),
        "outcome_ready_count": _count_truthy(samples, "labels", "outcome_ready"),
        "review_ready_count": _count_truthy(samples, "labels", "review_ready"),
        "avg_sample_weight_hint": _avg(weights),
    }


def summarize_shadow_evaluations(evaluations: list[dict]) -> dict:
    total = len(evaluations or [])
    usable = [
        item
        for item in evaluations or []
        if _dict_at(item, "quality").get("usable_for_shadow_eval") is True
    ]
    scores = [
        _float_or_none(_dict_at(item, "comparison").get("agreement_score"))
        for item in evaluations or []
    ]
    scores = [score for score in scores if score is not None]
    action_match_count = _count_truthy(evaluations, "comparison", "action_match")
    intent_match_count = _count_truthy(evaluations, "comparison", "intent_match")
    safety_match_count = _count_truthy(evaluations, "comparison", "safety_match")
    severity_distribution = count_by(
        evaluations or [],
        lambda item: _dict_at(item, "quality").get("severity"),
    )
    return {
        "total_evaluations": total,
        "usable_evaluations": len(usable),
        "agreement_score_avg": _avg(scores),
        "agreement_score_min": min(scores) if scores else None,
        "agreement_score_max": max(scores) if scores else None,
        "action_match_rate": safe_div(action_match_count, total),
        "intent_match_rate": safe_div(intent_match_count, total),
        "safety_match_rate": safe_div(safety_match_count, total),
        "severity_distribution": severity_distribution,
        "review_recommended_count": _count_truthy(
            evaluations,
            "quality",
            "review_recommended",
        ),
        "critical_count": severity_distribution.get("critical", 0),
        "warning_count": severity_distribution.get("warning", 0),
    }


def summarize_lightgbm_dataset_rows(rows: list[dict]) -> dict:
    total = len(rows or [])
    weights = [_float_or_none(row.get("sample_weight")) for row in rows or []]
    weights = [weight for weight in weights if weight is not None]
    return {
        "total_rows": total,
        "training_usable_count": _count_truthy(rows, "quality", "usable_for_training"),
        "inference_preview_usable_count": _count_truthy(
            rows,
            "quality",
            "usable_for_inference_preview",
        ),
        "provider_distribution": count_by(rows or [], lambda row: row.get("provider")),
        "engine_role_distribution": count_by(
            rows or [],
            lambda row: row.get("engine_role"),
        ),
        "label_ready_count": _count_truthy(rows, "labels", "label_ready"),
        "target_available_count": sum(1 for row in rows or [] if _has_target(row)),
        "sample_weight_avg": _avg(weights),
        "excluded_reason_distribution": count_by(
            rows or [],
            lambda row: _dict_at(row, "quality").get("excluded_reason") or "none",
        ),
    }


def detect_summary_safety_flags(
    samples: list[dict],
    evaluations: list[dict],
    rows: list[dict],
) -> dict:
    """Conservative string-based safety scan for preview artifacts."""

    text = json.dumps(
        {
            "samples": samples or [],
            "evaluations": evaluations or [],
            "rows": rows or [],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    notes = []
    raw_secret_detected = _contains_any(text, SECRET_MARKERS)
    leakage_risk_detected = _contains_any(text, LEAKAGE_MARKERS)
    execution_link_detected = _contains_any(text, EXECUTION_LINK_MARKERS)
    ui_link_detected = _contains_any(text, UI_LINK_MARKERS)
    if raw_secret_detected:
        notes.append("secret-like marker detected in preview artifacts")
    if leakage_risk_detected:
        notes.append("future/outcome leakage marker detected in preview artifacts")
    if execution_link_detected:
        notes.append("execution layer marker detected in preview artifacts")
    if ui_link_detected:
        notes.append("ui layer marker detected in preview artifacts")
    return {
        "raw_secret_detected": raw_secret_detected,
        "leakage_risk_detected": leakage_risk_detected,
        "execution_link_detected": execution_link_detected,
        "ui_link_detected": ui_link_detected,
        "notes": notes,
    }


def evaluate_readiness(
    distillation_summary: dict,
    shadow_summary: dict,
    dataset_summary: dict,
    safety_summary: dict,
) -> dict:
    """Evaluate preview readiness without approving training or runtime use."""

    total = (
        int(distillation_summary.get("total_samples") or 0)
        + int(shadow_summary.get("total_evaluations") or 0)
        + int(dataset_summary.get("total_rows") or 0)
    )
    if (
        safety_summary.get("raw_secret_detected")
        or safety_summary.get("leakage_risk_detected")
        or safety_summary.get("execution_link_detected")
        or safety_summary.get("ui_link_detected")
        or int(shadow_summary.get("critical_count") or 0) >= 3
    ):
        return {
            "data_readiness_level": "review_required",
            "local_ai_training_recommended": False,
            "reason": "safety or critical shadow evaluation review is required",
            "next_recommended_action": "review_safety_flags",
        }
    if total == 0:
        return {
            "data_readiness_level": "empty",
            "local_ai_training_recommended": False,
            "reason": "no preview artifacts are available",
            "next_recommended_action": "collect_more_journal_records",
        }
    if (
        int(dataset_summary.get("training_usable_count") or 0) >= 100
        and not safety_summary.get("raw_secret_detected")
        and not safety_summary.get("leakage_risk_detected")
    ):
        return {
            "data_readiness_level": "training_candidate_ready",
            "local_ai_training_recommended": True,
            "reason": "enough training-usable dataset rows are available",
            "next_recommended_action": "proceed_to_trainer_skeleton",
        }
    if (
        int(dataset_summary.get("total_rows") or 0) >= 20
        or int(distillation_summary.get("usable_samples") or 0) >= 10
    ):
        return {
            "data_readiness_level": "preview_ready",
            "local_ai_training_recommended": False,
            "reason": "preview data exists but training threshold is not met",
            "next_recommended_action": "run_shadow_evaluation_preview",
        }
    return {
        "data_readiness_level": "insufficient",
        "local_ai_training_recommended": False,
        "reason": "more Journal records or teacher samples are needed",
        "next_recommended_action": "collect_more_journal_records",
    }


def build_local_ai_evaluation_dashboard_summary(
    samples: list[dict] | None = None,
    evaluations: list[dict] | None = None,
    dataset_rows: list[dict] | None = None,
) -> dict:
    """Build one Local AI evaluation dashboard preview summary."""

    samples = samples or []
    evaluations = evaluations or []
    dataset_rows = dataset_rows or []
    distillation = summarize_distillation_samples(samples)
    shadow = summarize_shadow_evaluations(evaluations)
    dataset = summarize_lightgbm_dataset_rows(dataset_rows)
    safety = detect_summary_safety_flags(samples, evaluations, dataset_rows)
    readiness = evaluate_readiness(distillation, shadow, dataset, safety)
    return {
        "schema": DASHBOARD_SCHEMA,
        "summary_id": f"local-ai-dashboard-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "created_at": _utc_now(),
        "scope": _build_scope(samples, evaluations, dataset_rows),
        "distillation": distillation,
        "shadow_evaluation": shadow,
        "dataset": dataset,
        "safety": safety,
        "readiness": readiness,
        "meta": {
            "builder": "local_ai_evaluation_dashboard.v1",
            "gui_dashboard": False,
            "runtime_connected": False,
            "order_connected": False,
        },
    }


def export_dashboard_summary_json(summary: dict, output_path: Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_export(summary), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def export_dashboard_summary_markdown(summary: dict, output_path: Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_markdown(_sanitize_export(summary)), encoding="utf-8")
    return path


def build_and_export_dashboard_preview(
    samples: list[dict],
    evaluations: list[dict],
    dataset_rows: list[dict],
    json_output_path: Path,
    markdown_output_path: Path | None = None,
) -> dict:
    summary = build_local_ai_evaluation_dashboard_summary(
        samples,
        evaluations,
        dataset_rows,
    )
    json_path = export_dashboard_summary_json(summary, json_output_path)
    markdown_path = (
        export_dashboard_summary_markdown(summary, markdown_output_path)
        if markdown_output_path
        else None
    )
    return {
        "summary": summary,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path) if markdown_path else None,
    }


def _build_scope(samples: list[dict], evaluations: list[dict], rows: list[dict]) -> dict:
    symbols = sorted(
        {
            str(item.get("symbol"))
            for item in [*samples, *evaluations, *rows]
            if item.get("symbol")
        }
    )
    timeframes = sorted(
        {
            str(item.get("timeframe"))
            for item in [*samples, *evaluations, *rows]
            if item.get("timeframe")
        }
    )
    return {
        "source": "in_memory_preview",
        "period_start": None,
        "period_end": None,
        "symbols": symbols,
        "timeframes": timeframes,
    }


def _format_markdown(summary: dict) -> str:
    readiness = _dict_at(summary, "readiness")
    distillation = _dict_at(summary, "distillation")
    shadow = _dict_at(summary, "shadow_evaluation")
    dataset = _dict_at(summary, "dataset")
    safety = _dict_at(summary, "safety")
    lines = [
        "# Local AI Evaluation Dashboard Preview",
        "",
        "## Readiness",
        f"- Level: {readiness.get('data_readiness_level')}",
        f"- Training recommended: {readiness.get('local_ai_training_recommended')}",
        f"- Reason: {readiness.get('reason')}",
        f"- Next action: {readiness.get('next_recommended_action')}",
        "",
        "## Distillation Summary",
        f"- Total samples: {distillation.get('total_samples')}",
        f"- Usable samples: {distillation.get('usable_samples')}",
        f"- Excluded samples: {distillation.get('excluded_samples')}",
        f"- Teacher providers: {distillation.get('teacher_provider_distribution')}",
        "",
        "## Shadow Evaluation Summary",
        f"- Total evaluations: {shadow.get('total_evaluations')}",
        f"- Agreement avg: {shadow.get('agreement_score_avg')}",
        f"- Action match rate: {shadow.get('action_match_rate')}",
        f"- Severity: {shadow.get('severity_distribution')}",
        f"- Review recommended: {shadow.get('review_recommended_count')}",
        "",
        "## Dataset Summary",
        f"- Total rows: {dataset.get('total_rows')}",
        f"- Training usable: {dataset.get('training_usable_count')}",
        f"- Inference preview usable: {dataset.get('inference_preview_usable_count')}",
        f"- Providers: {dataset.get('provider_distribution')}",
        "",
        "## Safety Flags",
        f"- Raw secret detected: {safety.get('raw_secret_detected')}",
        f"- Leakage risk detected: {safety.get('leakage_risk_detected')}",
        f"- Execution link detected: {safety.get('execution_link_detected')}",
        f"- UI link detected: {safety.get('ui_link_detected')}",
        f"- Notes: {safety.get('notes')}",
        "",
        "## Next Recommended Action",
        str(readiness.get("next_recommended_action") or "-"),
        "",
    ]
    return "\n".join(lines)


def _count_truthy(items: list[dict] | None, section: str, key: str) -> int:
    return sum(1 for item in items or [] if _dict_at(item, section).get(key) is True)


def _has_target(row: dict) -> bool:
    targets = _dict_at(row, "targets")
    return any(value is not None for value in targets.values())


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict_at(record: dict, key: str) -> dict:
    value = record.get(key) if isinstance(record, dict) else None
    return value if isinstance(value, dict) else {}


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _sanitize_export(value):
    if isinstance(value, dict):
        clean = {}
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if (
                "api_key" in key_text
                or "secret" in key_text
                or "token" in key_text
                or "authorization" in key_text
            ):
                continue
            clean[key] = _sanitize_export(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_export(item) for item in value]
    return value


__all__ = [
    "DASHBOARD_SCHEMA",
    "build_and_export_dashboard_preview",
    "build_local_ai_evaluation_dashboard_summary",
    "count_by",
    "detect_summary_safety_flags",
    "evaluate_readiness",
    "export_dashboard_summary_json",
    "export_dashboard_summary_markdown",
    "safe_div",
    "summarize_distillation_samples",
    "summarize_lightgbm_dataset_rows",
    "summarize_shadow_evaluations",
]
