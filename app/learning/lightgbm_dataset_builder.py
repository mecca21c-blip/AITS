"""LightGBM dataset preview builder for AITS Unified Trading Journal records.

This module converts Journal records into feature/label preview rows. It does
not import LightGBM, train models, call AI providers, connect to Router/UI, or
touch Execution/Order/Risk Guard paths.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.storage.journal_store import ensure_journal_db

DATASET_ROW_SCHEMA = "aits_lightgbm_dataset_row.v1"
JOURNAL_SCHEMA = "aits_unified_trading_journal.v1"

MARKET_FEATURE_KEYS = (
    "timeframe",
    "price_change_1m",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "volatility_short",
    "volatility_mid",
    "volume_change",
    "trade_value_change",
    "spread_proxy",
    "market_regime",
)
TECHNICAL_FEATURE_KEYS = (
    "rsi",
    "macd",
    "macd_signal",
    "macd_hist",
    "moving_average_short",
    "moving_average_mid",
    "moving_average_long",
    "ma_alignment",
    "breakout_score",
    "pullback_score",
    "overheat_score",
)
CANDIDATE_FEATURE_KEYS = (
    "basic_score",
    "candidate_rank",
    "candidate_reason_code",
    "is_rotation_candidate",
    "is_risk_candidate",
    "is_take_profit_candidate",
    "is_stop_loss_candidate",
)
PORTFOLIO_FEATURE_KEYS = (
    "holding_state",
    "position_size_ratio",
    "unrealized_pnl_pct",
    "holding_duration_minutes",
    "cash_ratio",
    "concentration_ratio",
    "max_position_limit_ratio",
    "asset_policy_risk_level",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_future_or_outcome_key(key: str) -> bool:
    """Return True when a key must not be used as an inference feature."""

    normalized = str(key or "").strip().lower()
    return (
        "pnl_after" in normalized
        or "hit_take_profit" in normalized
        or "hit_stop_loss" in normalized
        or "max_drawdown_after" in normalized
        or "max_runup_after" in normalized
        or "opportunity_missed" in normalized
        or "false_buy" in normalized
        or "false_sell" in normalized
        or "human_review_score" in normalized
        or "future" in normalized
        or "raw_future_candles" in normalized
    )


def sanitize_feature_value(value):
    """Keep only primitive feature values for v1 dataset rows."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def extract_market_features(record: dict) -> dict:
    market = _dict_at(record, "market_snapshot")
    features = _select_primitive_features(market, MARKET_FEATURE_KEYS)
    features.setdefault("timeframe", sanitize_feature_value(record.get("timeframe")))
    return features


def extract_technical_features(record: dict) -> dict:
    return _select_primitive_features(_dict_at(record, "basic_snapshot"), TECHNICAL_FEATURE_KEYS)


def extract_candidate_features(record: dict) -> dict:
    basic = _dict_at(record, "basic_snapshot")
    recommendation = _dict_at(record, "recommendation")
    merged = {**basic, **recommendation}
    features = _select_primitive_features(merged, CANDIDATE_FEATURE_KEYS)
    if "risk_level" in basic:
        features["basic_risk_level"] = sanitize_feature_value(basic.get("risk_level"))
    return features


def extract_portfolio_features(record: dict) -> dict:
    basic = _dict_at(record, "basic_snapshot")
    portfolio = _dict_at(record, "portfolio_context") or _dict_at(
        basic, "portfolio_context"
    )
    return _select_primitive_features(portfolio, PORTFOLIO_FEATURE_KEYS)


def extract_ai_output_features(record: dict) -> dict:
    ai_output = _dict_at(record, "ai_output_contract")
    why = _dict_at(ai_output, "why")
    return {
        "provider": sanitize_feature_value(record.get("provider")),
        "engine_role": sanitize_feature_value(record.get("engine_role")),
        "ai_confidence": sanitize_feature_value(ai_output.get("confidence")),
        "ai_action": sanitize_feature_value(ai_output.get("action")),
        "ai_intent_type": sanitize_feature_value(
            _dict_at(ai_output, "intent").get("type")
            or _dict_at(ai_output, "intent").get("intent_type")
        ),
        "ai_eta_bucket": sanitize_feature_value(_dict_at(ai_output, "eta").get("bucket")),
        "ai_safety_level": sanitize_feature_value(
            _dict_at(ai_output, "safety").get("level")
            or _dict_at(ai_output, "safety").get("safety_level")
        ),
        "ai_reason_code": sanitize_feature_value(
            why.get("reason_code") or why.get("code")
        ),
        "teacher_signal_flag": _teacher_signal_flag(record.get("provider")),
    }


def extract_router_features(record: dict) -> dict:
    router = _dict_at(record, "router_validation")
    safety = _dict_at(record, "safety")
    execution = _dict_at(record, "execution")
    return {
        "router_allowed": _bool_to_int(router.get("allowed")),
        "router_block_reason_code": sanitize_feature_value(
            router.get("block_reason_code") or router.get("rejected_reason")
        ),
        "risk_guard_status": sanitize_feature_value(router.get("risk_guard_status")),
        "validation_result": sanitize_feature_value(router.get("validation_result")),
        "final_action": sanitize_feature_value(router.get("final_action")),
        "shadow_only": _bool_to_int(safety.get("shadow_only")),
        "preview_only": _bool_to_int(safety.get("preview_only")),
        "executed": _bool_to_int(execution.get("executed")),
    }


def extract_labels(record: dict) -> dict:
    learning_label = _dict_at(record, "learning_label")
    outcome = _dict_at(record, "outcome")
    return {
        "label_ready": bool(learning_label.get("label_ready")),
        "label_action_quality": sanitize_feature_value(
            learning_label.get("label_action_quality")
        ),
        "label_buy_quality": sanitize_feature_value(
            learning_label.get("label_buy_quality")
        ),
        "label_sell_quality": sanitize_feature_value(
            learning_label.get("label_sell_quality")
        ),
        "label_risk_quality": sanitize_feature_value(
            learning_label.get("label_risk_quality")
        ),
        "label_rank_score": sanitize_feature_value(
            learning_label.get("label_rank_score")
        ),
        "label_pnl_bucket": sanitize_feature_value(
            learning_label.get("label_pnl_bucket") or outcome.get("pnl_bucket")
        ),
    }


def extract_targets(record: dict) -> dict:
    labels = extract_labels(record)
    outcome = _dict_at(record, "outcome")
    return {
        "ranker_target": labels.get("label_rank_score"),
        "classifier_target": labels.get("label_action_quality")
        or labels.get("label_buy_quality"),
        "regressor_target": sanitize_feature_value(
            outcome.get("expected_pnl_proxy") or outcome.get("pnl_proxy")
        ),
    }


def calculate_sample_weight(record: dict, labels: dict) -> float:
    weight = 1.0
    execution = _dict_at(record, "execution")
    safety = _dict_at(record, "safety")
    if execution.get("executed"):
        weight += 0.3
    if safety.get("shadow_only"):
        weight += 0.1
    if labels.get("label_ready"):
        weight += 0.2
    if bool(_dict_at(record, "review")):
        weight += 0.2
    if bool(_dict_at(record, "outcome")):
        weight += 0.2
    return round(min(weight, 1.8), 4)


def build_lightgbm_dataset_row_from_record(record: dict) -> dict:
    """Build one LightGBM dataset preview row from a Journal record."""

    if not isinstance(record, dict) or record.get("schema") != JOURNAL_SCHEMA:
        return _excluded_row(record if isinstance(record, dict) else {}, "missing_required_record")

    features = {
        "market": extract_market_features(record),
        "technical": extract_technical_features(record),
        "candidate": extract_candidate_features(record),
        "portfolio": extract_portfolio_features(record),
        "ai_output": extract_ai_output_features(record),
        "router": extract_router_features(record),
    }
    leakage_detected = _features_have_leakage(features)
    labels = extract_labels(record)
    targets = extract_targets(record)
    has_label = any(
        value is not None
        for key, value in labels.items()
        if key != "label_ready"
    )
    usable_for_training = bool(labels.get("label_ready") and has_label and not leakage_detected)
    excluded_reason = None
    if leakage_detected:
        usable_for_training = False
        excluded_reason = "leakage_detected"
    elif not labels.get("label_ready"):
        excluded_reason = "label_not_ready"
    elif not has_label:
        excluded_reason = "missing_label"

    return {
        "schema": DATASET_ROW_SCHEMA,
        "row_id": f"lgbm-row-{record.get('journal_id')}",
        "source_journal_id": record.get("journal_id"),
        "created_at": record.get("created_at") or _utc_now(),
        "symbol": record.get("symbol"),
        "timeframe": record.get("timeframe"),
        "provider": record.get("provider"),
        "engine_role": record.get("engine_role"),
        "features": features,
        "labels": labels,
        "targets": targets,
        "sample_weight": calculate_sample_weight(record, labels),
        "quality": {
            "usable_for_training": usable_for_training,
            "usable_for_inference_preview": _has_any_feature(features),
            "excluded_reason": excluded_reason,
            "leakage_checked": True,
        },
        "meta": {
            "source_schema": record.get("schema"),
            "feature_schema": "aits_lightgbm_feature_schema.v1",
            "builder": "lightgbm_dataset_builder.v1",
        },
    }


def build_lightgbm_dataset_rows_from_records(records: list[dict]) -> list[dict]:
    return [build_lightgbm_dataset_row_from_record(record) for record in records or []]


def load_journal_records_for_dataset(
    db_path: Optional[Path] = None,
    providers: Optional[list[str]] = None,
    limit: int = 1000,
    require_label_ready: bool = False,
) -> list[dict]:
    """Read Journal records from SQLite for dataset preview building."""

    safe_limit = max(1, min(int(limit or 1000), 10000))
    path = ensure_journal_db(db_path)
    conditions = []
    params: list[object] = []
    selected = [
        str(provider or "").strip().lower()
        for provider in (providers or [])
        if str(provider or "").strip()
    ]
    if selected:
        conditions.append(f"provider IN ({','.join('?' for _ in selected)})")
        params.extend(selected)
    if require_label_ready:
        conditions.append("label_ready = 1")
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT record_json
        FROM journal_records
        {where_sql}
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


def export_lightgbm_dataset_jsonl(rows: list[dict], output_path: Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows or []:
            fh.write(json.dumps(_sanitize_export(row), ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def export_lightgbm_dataset_csv(rows: list[dict], output_path: Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flat_rows = [_flatten_row(_sanitize_export(row)) for row in rows or []]
    columns = sorted({key for row in flat_rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(flat_rows)
    return path


def build_and_export_lightgbm_dataset_preview(
    db_path: Optional[Path],
    jsonl_output_path: Path,
    csv_output_path: Optional[Path] = None,
    limit: int = 1000,
    require_label_ready: bool = False,
) -> dict:
    records = load_journal_records_for_dataset(
        db_path=db_path,
        limit=limit,
        require_label_ready=require_label_ready,
    )
    rows = build_lightgbm_dataset_rows_from_records(records)
    jsonl_path = export_lightgbm_dataset_jsonl(rows, jsonl_output_path)
    csv_path = export_lightgbm_dataset_csv(rows, csv_output_path) if csv_output_path else None
    return {
        "rows": len(rows),
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path) if csv_path else None,
        "training_usable_count": sum(
            1 for row in rows if _dict_at(row, "quality").get("usable_for_training")
        ),
    }


def _select_primitive_features(source: dict, keys: tuple[str, ...]) -> dict:
    selected = {}
    for key in keys:
        if key in source and not is_future_or_outcome_key(key):
            value = sanitize_feature_value(source.get(key))
            if value is not None:
                selected[key] = value
    return selected


def _features_have_leakage(features: dict) -> bool:
    for group in features.values():
        if not isinstance(group, dict):
            continue
        for key in group.keys():
            if is_future_or_outcome_key(str(key)):
                return True
    return False


def _has_any_feature(features: dict) -> bool:
    return any(bool(group) for group in features.values() if isinstance(group, dict))


def _excluded_row(record: dict, reason: str) -> dict:
    return {
        "schema": DATASET_ROW_SCHEMA,
        "row_id": f"lgbm-row-{record.get('journal_id') or 'invalid'}",
        "source_journal_id": record.get("journal_id"),
        "created_at": record.get("created_at") or _utc_now(),
        "symbol": record.get("symbol"),
        "timeframe": record.get("timeframe"),
        "provider": record.get("provider"),
        "engine_role": record.get("engine_role"),
        "features": {
            "market": {},
            "technical": {},
            "candidate": {},
            "portfolio": {},
            "ai_output": {},
            "router": {},
        },
        "labels": {
            "label_ready": False,
            "label_action_quality": None,
            "label_buy_quality": None,
            "label_sell_quality": None,
            "label_risk_quality": None,
            "label_rank_score": None,
            "label_pnl_bucket": None,
        },
        "targets": {
            "ranker_target": None,
            "classifier_target": None,
            "regressor_target": None,
        },
        "sample_weight": 0.0,
        "quality": {
            "usable_for_training": False,
            "usable_for_inference_preview": False,
            "excluded_reason": reason,
            "leakage_checked": True,
        },
        "meta": {"builder": "lightgbm_dataset_builder.v1"},
    }


def _flatten_row(row: dict) -> dict:
    flat = {
        "row_id": row.get("row_id"),
        "source_journal_id": row.get("source_journal_id"),
        "created_at": row.get("created_at"),
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "provider": row.get("provider"),
        "engine_role": row.get("engine_role"),
        "sample_weight": row.get("sample_weight"),
    }
    for group_name, group in _dict_at(row, "features").items():
        if isinstance(group, dict):
            for key, value in group.items():
                flat[f"{group_name}__{key}"] = value
    for key, value in _dict_at(row, "labels").items():
        flat[f"label__{key}"] = value
    for key, value in _dict_at(row, "targets").items():
        flat[f"target__{key}"] = value
    for key, value in _dict_at(row, "quality").items():
        flat[f"quality__{key}"] = value
    return flat


def _teacher_signal_flag(provider: object) -> bool:
    return str(provider or "").strip().lower() in {"openai", "gemini"}


def _bool_to_int(value: object) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _dict_at(record: dict, key: str) -> dict:
    value = record.get(key) if isinstance(record, dict) else None
    return value if isinstance(value, dict) else {}


def _sanitize_export(value):
    if isinstance(value, dict):
        clean = {}
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if (
                "key" in key_text
                or "secret" in key_text
                or "token" in key_text
                or "authorization" in key_text
                or is_future_or_outcome_key(key_text)
            ):
                continue
            clean[key] = _sanitize_export(child)
        return clean
    if isinstance(value, list):
        return []
    return value


__all__ = [
    "DATASET_ROW_SCHEMA",
    "build_and_export_lightgbm_dataset_preview",
    "build_lightgbm_dataset_row_from_record",
    "build_lightgbm_dataset_rows_from_records",
    "calculate_sample_weight",
    "export_lightgbm_dataset_csv",
    "export_lightgbm_dataset_jsonl",
    "extract_ai_output_features",
    "extract_candidate_features",
    "extract_labels",
    "extract_market_features",
    "extract_portfolio_features",
    "extract_router_features",
    "extract_targets",
    "extract_technical_features",
    "is_future_or_outcome_key",
    "load_journal_records_for_dataset",
    "sanitize_feature_value",
]
