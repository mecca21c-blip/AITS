"""Local AI shadow evaluator for GPT/Gemini teacher samples.

This module compares an existing teacher distillation sample with a caller
provided Local AI student output. It does not run Local AI inference, training,
Router, UI, Execution, Order, Risk Guard, or external AI providers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SHADOW_EVALUATION_SCHEMA = "aits_local_ai_shadow_evaluation.v1"
DISTILLATION_SAMPLE_SCHEMA = "aits_distillation_sample.v1"
OBSERVE_ACTIONS = frozenset({"observe", "wait", "hold", "stay", "watch"})
BUY_ACTIONS = frozenset({"buy", "buy_candidate", "entry", "entry_candidate"})
SELL_ACTIONS = frozenset(
    {"sell", "sell_candidate", "reduce", "reduce_candidate", "exit"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_action(action: object) -> str | None:
    """Normalize comparable action candidates without creating orders."""

    if action is None:
        return None
    normalized = str(action).strip().lower()
    if not normalized:
        return None
    if normalized in OBSERVE_ACTIONS:
        return "observe"
    if normalized in BUY_ACTIONS:
        return "buy_candidate"
    if normalized in SELL_ACTIONS:
        return "sell_or_reduce_candidate"
    return normalized


def extract_teacher_signal(sample: dict) -> dict:
    """Extract compact teacher signal from a distillation sample."""

    if not isinstance(sample, dict):
        raise ValueError("sample must be a dict")
    if sample.get("schema") != DISTILLATION_SAMPLE_SCHEMA:
        raise ValueError(f"sample schema must be {DISTILLATION_SAMPLE_SCHEMA}")
    teacher = _dict_at(sample, "teacher")
    if not teacher:
        raise ValueError("missing teacher signal")
    return {
        "action": normalize_action(teacher.get("action")),
        "raw_action": teacher.get("action"),
        "confidence": _float_or_none(teacher.get("confidence")),
        "intent_type": _intent_type(_dict_at(teacher, "intent")),
        "safety_level": _safety_level(_dict_at(teacher, "safety")),
    }


def extract_student_signal(student_output: dict) -> dict:
    """Extract compact signal from caller-provided Local AI output."""

    if not isinstance(student_output, dict):
        raise ValueError("student_output must be a dict")
    return {
        "provider": str(student_output.get("provider") or "local_ai"),
        "model_id": student_output.get("model_id"),
        "action": normalize_action(student_output.get("action")),
        "raw_action": student_output.get("action"),
        "confidence": _float_or_none(student_output.get("confidence")),
        "intent_type": _intent_type(_dict_at(student_output, "intent")),
        "safety_level": _safety_level(_dict_at(student_output, "safety")),
    }


def compare_teacher_student(teacher: dict, student: dict) -> dict:
    """Compare teacher and student compact signals."""

    teacher_action = teacher.get("action")
    student_action = student.get("action")
    action_match = bool(teacher_action and student_action and teacher_action == student_action)
    intent_match = _nullable_match(teacher.get("intent_type"), student.get("intent_type"))
    safety_match = _nullable_match(teacher.get("safety_level"), student.get("safety_level"))
    confidence_delta = _confidence_delta(
        teacher.get("confidence"),
        student.get("confidence"),
    )
    confidence_score = 0.0
    if confidence_delta is not None:
        confidence_score = max(0.0, 1.0 - confidence_delta) * 0.20

    score = 0.0
    if action_match:
        score += 0.45
    if intent_match:
        score += 0.20
    if safety_match:
        score += 0.15
    score += confidence_score
    score = round(max(0.0, min(score, 1.0)), 4)

    reasons = []
    if not teacher_action:
        reasons.append("missing_teacher_signal")
    if not student_action:
        reasons.append("missing_student_signal")
    if teacher_action and student_action and not action_match:
        reasons.append("action_mismatch")
    if teacher.get("intent_type") and student.get("intent_type") and not intent_match:
        reasons.append("intent_mismatch")
    if teacher.get("safety_level") and student.get("safety_level") and not safety_match:
        reasons.append("safety_mismatch")
    if confidence_delta is not None and confidence_delta >= 0.30:
        reasons.append("confidence_gap")

    return {
        "action_match": action_match,
        "confidence_delta": confidence_delta,
        "intent_match": intent_match,
        "safety_match": safety_match,
        "agreement_score": score,
        "disagreement_reason": ",".join(reasons) if reasons else None,
    }


def evaluate_local_ai_shadow_sample(sample: dict, student_output: dict) -> dict:
    """Compare one teacher sample with one Local AI shadow output."""

    sample_quality = _dict_at(sample, "quality") if isinstance(sample, dict) else {}
    labels = _dict_at(sample, "labels") if isinstance(sample, dict) else {}
    try:
        teacher = extract_teacher_signal(sample)
    except Exception as exc:
        return _excluded_result(sample, None, f"missing_teacher_signal:{type(exc).__name__}")

    try:
        student = extract_student_signal(student_output)
    except Exception as exc:
        return _excluded_result(sample, teacher, f"missing_student_signal:{type(exc).__name__}")

    comparison = compare_teacher_student(teacher, student)
    usable = bool(sample_quality.get("usable_for_distillation", True))
    excluded_reason = None
    if not usable:
        excluded_reason = str(sample_quality.get("excluded_reason") or "sample_not_usable")
    elif not student.get("action"):
        usable = False
        excluded_reason = "missing_student_signal"

    severity = _severity(comparison.get("agreement_score"), usable)
    review_recommended = bool(
        (not comparison.get("action_match"))
        or severity == "critical"
        or not usable
    )

    return {
        "schema": SHADOW_EVALUATION_SCHEMA,
        "evaluation_id": f"shadow-{sample.get('sample_id') if isinstance(sample, dict) else 'invalid'}",
        "created_at": _utc_now(),
        "source_sample_id": sample.get("sample_id") if isinstance(sample, dict) else None,
        "source_journal_id": sample.get("source_journal_id") if isinstance(sample, dict) else None,
        "symbol": sample.get("symbol") if isinstance(sample, dict) else None,
        "timeframe": sample.get("timeframe") if isinstance(sample, dict) else None,
        "teacher_provider": sample.get("source_provider") if isinstance(sample, dict) else None,
        "student_provider": student.get("provider") or "local_ai",
        "teacher": {
            "action": teacher.get("action"),
            "confidence": teacher.get("confidence"),
            "intent_type": teacher.get("intent_type"),
            "safety_level": teacher.get("safety_level"),
        },
        "student": {
            "action": student.get("action"),
            "confidence": student.get("confidence"),
            "intent_type": student.get("intent_type"),
            "safety_level": student.get("safety_level"),
        },
        "comparison": comparison,
        "quality": {
            "usable_for_shadow_eval": usable,
            "excluded_reason": excluded_reason,
            "severity": severity,
            "review_recommended": review_recommended,
        },
        "labels": {
            "label_ready": bool(labels.get("label_ready")),
            "outcome_ready": bool(labels.get("outcome_ready")),
            "review_ready": bool(labels.get("review_ready")),
            "teacher_label_action_quality": labels.get("label_action_quality"),
            "teacher_label_pnl_bucket": labels.get("label_pnl_bucket"),
        },
        "meta": {
            "student_model_id": student.get("model_id"),
            "evaluator": "local_ai_shadow_evaluator.v1",
        },
    }


def evaluate_local_ai_shadow_samples(
    samples: list[dict],
    student_outputs: list[dict],
) -> list[dict]:
    """Evaluate multiple samples using v1 order-based matching."""

    results: list[dict] = []
    max_len = max(len(samples or []), len(student_outputs or []))
    for idx in range(max_len):
        sample = samples[idx] if idx < len(samples or []) else None
        student = student_outputs[idx] if idx < len(student_outputs or []) else None
        if sample is None or student is None:
            results.append(
                _excluded_result(
                    sample if isinstance(sample, dict) else {},
                    None,
                    "sample_student_count_mismatch",
                )
            )
            continue
        results.append(evaluate_local_ai_shadow_sample(sample, student))
    return results


def export_shadow_evaluations_jsonl(
    results: list[dict],
    output_path: Path,
) -> Path:
    """Export shadow evaluation results as JSONL."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for result in results or []:
            fh.write(json.dumps(_sanitize_result(result), ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def build_mock_student_output_from_sample(
    sample: dict,
    *,
    action_override: str | None = None,
    confidence_delta: float = -0.05,
) -> dict:
    """Build a mock Local AI output for smoke tests only.

    This helper does not run a model. It mirrors the teacher signal with a small
    confidence adjustment so the evaluator can be tested independently.
    """

    teacher = _dict_at(sample, "teacher")
    confidence = _float_or_none(teacher.get("confidence"))
    if confidence is not None:
        confidence = max(0.0, min(confidence + float(confidence_delta), 1.0))
    return {
        "provider": "local_ai",
        "model_id": "local-ai-shadow-mock-v1",
        "action": action_override or teacher.get("action"),
        "confidence": confidence,
        "intent": _dict_at(teacher, "intent"),
        "why": {"summary": "mock local shadow output for evaluator smoke test"},
        "safety": _dict_at(teacher, "safety"),
        "meta": {"source": "mock_shadow"},
    }


def _excluded_result(sample: dict | None, teacher: dict | None, reason: str) -> dict:
    labels = _dict_at(sample or {}, "labels")
    return {
        "schema": SHADOW_EVALUATION_SCHEMA,
        "evaluation_id": f"shadow-{(sample or {}).get('sample_id') or 'invalid'}",
        "created_at": _utc_now(),
        "source_sample_id": (sample or {}).get("sample_id"),
        "source_journal_id": (sample or {}).get("source_journal_id"),
        "symbol": (sample or {}).get("symbol"),
        "timeframe": (sample or {}).get("timeframe"),
        "teacher_provider": (sample or {}).get("source_provider"),
        "student_provider": "local_ai",
        "teacher": {
            "action": (teacher or {}).get("action"),
            "confidence": (teacher or {}).get("confidence"),
            "intent_type": (teacher or {}).get("intent_type"),
            "safety_level": (teacher or {}).get("safety_level"),
        },
        "student": {
            "action": None,
            "confidence": None,
            "intent_type": None,
            "safety_level": None,
        },
        "comparison": {
            "action_match": False,
            "confidence_delta": None,
            "intent_match": False,
            "safety_match": False,
            "agreement_score": 0.0,
            "disagreement_reason": reason,
        },
        "quality": {
            "usable_for_shadow_eval": False,
            "excluded_reason": reason,
            "severity": "critical",
            "review_recommended": True,
        },
        "labels": {
            "label_ready": bool(labels.get("label_ready")),
            "outcome_ready": bool(labels.get("outcome_ready")),
            "review_ready": bool(labels.get("review_ready")),
            "teacher_label_action_quality": labels.get("label_action_quality"),
            "teacher_label_pnl_bucket": labels.get("label_pnl_bucket"),
        },
        "meta": {"evaluator": "local_ai_shadow_evaluator.v1"},
    }


def _severity(score: object, usable: bool) -> str:
    if not usable:
        return "critical"
    value = _float_or_none(score) or 0.0
    if value >= 0.75:
        return "info"
    if value >= 0.45:
        return "warning"
    return "critical"


def _nullable_match(left: object, right: object) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _confidence_delta(left: object, right: object) -> float | None:
    left_float = _float_or_none(left)
    right_float = _float_or_none(right)
    if left_float is None or right_float is None:
        return None
    return round(abs(left_float - right_float), 4)


def _intent_type(intent: dict) -> str | None:
    return intent.get("type") or intent.get("intent_type") or intent.get("name")


def _safety_level(safety: dict) -> str | None:
    return safety.get("level") or safety.get("safety_level") or safety.get("risk_level")


def _dict_at(record: dict, key: str) -> dict:
    value = record.get(key) if isinstance(record, dict) else None
    return value if isinstance(value, dict) else {}


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sanitize_result(result: dict) -> dict:
    if isinstance(result, dict):
        sanitized = {}
        for key, value in result.items():
            key_text = str(key).strip().lower()
            if (
                "key" in key_text
                or "secret" in key_text
                or "token" in key_text
                or "authorization" in key_text
            ):
                continue
            sanitized[key] = _sanitize_result(value)
        return sanitized
    if isinstance(result, list):
        return [_sanitize_result(item) for item in result]
    return result


__all__ = [
    "SHADOW_EVALUATION_SCHEMA",
    "build_mock_student_output_from_sample",
    "compare_teacher_student",
    "evaluate_local_ai_shadow_sample",
    "evaluate_local_ai_shadow_samples",
    "export_shadow_evaluations_jsonl",
    "extract_student_signal",
    "extract_teacher_signal",
    "normalize_action",
]
