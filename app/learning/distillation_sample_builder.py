"""GPT/Gemini teacher distillation sample builder for Local AI.

This module reads Unified Trading Journal records and builds compact teacher
samples for future Local AI comparison or training. It does not call OpenAI,
Gemini, Local AI, Router, UI, Execution, Order, Risk Guard, or training code.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.storage.journal_store import ensure_journal_db

DISTILLATION_SAMPLE_SCHEMA = "aits_distillation_sample.v1"
TEACHER_PROVIDERS = frozenset({"openai", "gemini"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_teacher_provider(provider: str) -> bool:
    """Return True for GPT/Gemini teacher providers."""

    return str(provider or "").strip().lower() in TEACHER_PROVIDERS


def build_distillation_sample_from_record(record: dict) -> dict:
    """Convert one Unified Trading Journal record into a teacher sample."""

    if not isinstance(record, dict):
        return _excluded_sample(
            source_journal_id=None,
            reason="invalid_record",
            provider=None,
        )

    provider = str(record.get("provider") or "").strip().lower()
    journal_id = str(record.get("journal_id") or "")
    if not is_teacher_provider(provider):
        return _excluded_sample(journal_id, "non_teacher_provider", provider)

    ai_output = _dict_at(record, "ai_output_contract")
    if not ai_output:
        return _excluded_sample(journal_id, "missing_ai_output_contract", provider)

    teacher = _build_teacher(record, ai_output)
    if not _has_teacher_signal(teacher):
        return _excluded_sample(journal_id, "missing_teacher_signal", provider)

    label_ready = _bool_at(_dict_at(record, "learning_label"), "label_ready")
    outcome_ready = bool(_dict_at(record, "outcome"))
    review_ready = bool(_dict_at(record, "review"))

    return {
        "schema": DISTILLATION_SAMPLE_SCHEMA,
        "sample_id": f"distill-{journal_id}",
        "source_journal_id": journal_id,
        "created_at": _utc_now(),
        "source_provider": provider,
        "source_engine_role": record.get("engine_role"),
        "symbol": record.get("symbol"),
        "timeframe": record.get("timeframe"),
        "teacher": teacher,
        "student_context": _build_student_context(record),
        "labels": {
            "label_ready": label_ready,
            "outcome_ready": outcome_ready,
            "review_ready": review_ready,
            "label_action_quality": _dict_at(record, "learning_label").get(
                "label_action_quality"
            ),
            "label_pnl_bucket": _dict_at(record, "learning_label").get(
                "label_pnl_bucket"
            )
            or _dict_at(record, "outcome").get("pnl_bucket"),
        },
        "quality": {
            "usable_for_distillation": True,
            "excluded_reason": None,
            "sample_weight_hint": _sample_weight_hint(
                label_ready=label_ready,
                outcome_ready=outcome_ready,
                review_ready=review_ready,
            ),
        },
        "meta": {
            "source_schema": record.get("schema"),
            "asset_name": record.get("asset_name"),
            "builder": "distillation_sample_builder.v1",
        },
    }


def build_distillation_samples_from_records(records: list[dict]) -> list[dict]:
    """Build samples from multiple records, preserving excluded samples."""

    samples: list[dict] = []
    for record in records or []:
        try:
            samples.append(build_distillation_sample_from_record(record))
        except Exception:
            samples.append(
                _excluded_sample(
                    source_journal_id=(
                        record.get("journal_id") if isinstance(record, dict) else None
                    ),
                    reason="invalid_record",
                    provider=(
                        record.get("provider") if isinstance(record, dict) else None
                    ),
                )
            )
    return samples


def load_teacher_records_from_journal(
    db_path: Optional[Path] = None,
    providers: Optional[list[str]] = None,
    limit: int = 500,
    require_label_ready: bool = False,
    require_outcome_ready: bool = False,
    require_review_ready: bool = False,
) -> list[dict]:
    """Load GPT/Gemini Journal records from SQLite for distillation."""

    selected = [
        str(provider or "").strip().lower()
        for provider in (providers or ["openai", "gemini"])
        if is_teacher_provider(str(provider or "").strip().lower())
    ]
    if not selected:
        return []

    safe_limit = max(1, min(int(limit or 500), 5000))
    path = ensure_journal_db(db_path)
    placeholders = ",".join("?" for _ in selected)
    conditions = [f"provider IN ({placeholders})"]
    params: list[object] = list(selected)
    if require_label_ready:
        conditions.append("label_ready = 1")
    if require_outcome_ready:
        conditions.append("outcome_ready = 1")
    if require_review_ready:
        conditions.append("review_ready = 1")

    query = f"""
        SELECT record_json
        FROM journal_records
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(safe_limit)

    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    records: list[dict] = []
    for row in rows:
        try:
            parsed = json.loads(str(row[0]))
            if isinstance(parsed, dict):
                records.append(parsed)
        except json.JSONDecodeError:
            continue
    return records


def export_distillation_samples_jsonl(
    samples: list[dict],
    output_path: Path,
) -> Path:
    """Export distillation samples as JSONL."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for sample in samples or []:
            fh.write(json.dumps(sample, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def build_and_export_distillation_samples(
    db_path: Optional[Path],
    output_path: Path,
    limit: int = 500,
    require_label_ready: bool = False,
    require_outcome_ready: bool = False,
    require_review_ready: bool = False,
) -> Path:
    """Load teacher records, build samples, and export them as JSONL."""

    records = load_teacher_records_from_journal(
        db_path=db_path,
        limit=limit,
        require_label_ready=require_label_ready,
        require_outcome_ready=require_outcome_ready,
        require_review_ready=require_review_ready,
    )
    samples = build_distillation_samples_from_records(records)
    return export_distillation_samples_jsonl(samples, output_path)


def _build_teacher(record: dict, ai_output: dict) -> dict:
    recommendation = _dict_at(record, "recommendation")
    return {
        "action": ai_output.get("action") or recommendation.get("ai_action"),
        "confidence": ai_output.get("confidence"),
        "intent": _dict_at(ai_output, "intent"),
        "scenario": _dict_at(ai_output, "scenario"),
        "why": _dict_at(ai_output, "why"),
        "eta": _dict_at(ai_output, "eta"),
        "safety": _dict_at(ai_output, "safety") or _dict_at(record, "safety"),
    }


def _build_student_context(record: dict) -> dict:
    basic_snapshot = _dict_at(record, "basic_snapshot")
    return {
        "market_snapshot": _compact_dict(_dict_at(record, "market_snapshot")),
        "basic_snapshot": _compact_dict(basic_snapshot),
        "portfolio_context": _compact_dict(
            _dict_at(record, "portfolio_context")
            or _dict_at(basic_snapshot, "portfolio_context")
        ),
        "router_context": _compact_router_context(
            _dict_at(record, "router_validation")
        ),
    }


def _compact_router_context(router_validation: dict) -> dict:
    allowed_keys = (
        "allowed",
        "final_action",
        "risk_guard_status",
        "policy_check",
        "fund_check",
        "rejected_reason",
    )
    return {key: router_validation.get(key) for key in allowed_keys if key in router_validation}


def _has_teacher_signal(teacher: dict) -> bool:
    return bool(
        teacher.get("action")
        or teacher.get("intent")
        or teacher.get("why")
        or teacher.get("scenario")
    )


def _excluded_sample(
    source_journal_id: str | None,
    reason: str,
    provider: str | None,
) -> dict:
    return {
        "schema": DISTILLATION_SAMPLE_SCHEMA,
        "sample_id": f"distill-{source_journal_id or 'invalid'}",
        "source_journal_id": source_journal_id,
        "created_at": _utc_now(),
        "source_provider": provider,
        "source_engine_role": None,
        "symbol": None,
        "timeframe": None,
        "teacher": {
            "action": None,
            "confidence": None,
            "intent": {},
            "scenario": {},
            "why": {},
            "eta": {},
            "safety": {},
        },
        "student_context": {
            "market_snapshot": {},
            "basic_snapshot": {},
            "portfolio_context": {},
            "router_context": {},
        },
        "labels": {
            "label_ready": False,
            "outcome_ready": False,
            "review_ready": False,
            "label_action_quality": None,
            "label_pnl_bucket": None,
        },
        "quality": {
            "usable_for_distillation": False,
            "excluded_reason": reason,
            "sample_weight_hint": 0.0,
        },
        "meta": {"builder": "distillation_sample_builder.v1"},
    }


def _sample_weight_hint(
    label_ready: bool,
    outcome_ready: bool,
    review_ready: bool,
) -> float:
    weight = 1.0
    if label_ready:
        weight += 0.2
    if outcome_ready:
        weight += 0.2
    if review_ready:
        weight += 0.3
    return min(weight, 1.5)


def _dict_at(record: dict, key: str) -> dict:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _bool_at(record: dict, key: str) -> bool:
    return bool(record.get(key))


def _compact_dict(value: dict) -> dict:
    """Return a compact copy without raw bulk or sensitive-looking fields."""

    result = {}
    for key, child in (value or {}).items():
        key_text = str(key).strip().lower()
        if _looks_sensitive_or_bulk(key_text):
            continue
        if isinstance(child, dict):
            result[key] = _compact_dict(child)
        elif isinstance(child, list):
            if len(child) <= 20 and not _looks_raw_ohlcv_key(key_text):
                result[key] = child
        else:
            result[key] = child
    return result


def _looks_sensitive_or_bulk(key: str) -> bool:
    return (
        "key" in key
        or "secret" in key
        or "token" in key
        or "authorization" in key
        or "raw" in key
        or _looks_raw_ohlcv_key(key)
    )


def _looks_raw_ohlcv_key(key: str) -> bool:
    return key in {"ohlcv", "candles", "raw_ohlcv", "raw_candles", "ticks"}


__all__ = [
    "DISTILLATION_SAMPLE_SCHEMA",
    "build_and_export_distillation_samples",
    "build_distillation_sample_from_record",
    "build_distillation_samples_from_records",
    "export_distillation_samples_jsonl",
    "is_teacher_provider",
    "load_teacher_records_from_journal",
]
