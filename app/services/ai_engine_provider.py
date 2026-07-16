from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
import math
import os
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from app.services.ollama_http_client import OllamaHttpClient
from app.services.local_shadow_predictor import (
    LOCAL_ENGINE_DECISION_SCHEMA,
    LOCAL_ENGINE_OBSERVATION_WRITER_CONTRACT,
    LocalEngineCandidateObservationError,
    predict_local_model_decision,
    record_local_engine_candidate_observation,
)
from app.services.local_model_calibration import load_local_model_calibration_profile
from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_task_coverage import AITSLocalEngineTaskCoverage


RUNTIME_DECISION_ALLOWED_TASKS = {
    "initial_management_decision",
    "position_management_decision",
    "portfolio_management_decision",
    "buy_decision",
    "sell_decision",
    "managed_pool_promotion_decision",
    "rotation_decision",
    "ai_redecision",
}
AI_POSITION_TASK_CANONICAL = "position_management_decision"
AI_POSITION_TASK_ALIASES = {"manage_position_decision": AI_POSITION_TASK_CANONICAL}
_RUNTIME_DECISION_CALL_TIMES: list[float] = []
_RUNTIME_DECISION_PAYLOAD_LAST_CALL: dict[str, float] = {}
_PROVIDER_CALL_HISTORY: list[dict[str, Any]] = []
_PROVIDER_PAYLOAD_LAST_CALL: dict[str, float] = {}
_PROVIDER_LAST_CALL: dict[str, float] = {}

_LOCAL_SAFE_ACTIONS = {"wait", "hold", "reject", "rotate_review"}
_LOCAL_EXTERNAL_CONFIRMATION_ACTIONS = {
    "buy", "add", "sell", "reduce", "rotate", "promote", "replace",
    "reduce_and_rotate", "take_profit", "stop_loss",
}


def _local_engine_authority_task_key(task: str, action: str = "") -> str:
    normalized_task = str(task or "").lower()
    normalized_action = str(action or "").lower()
    if normalized_task == "portfolio_management_decision":
        return "portfolio_management"
    if normalized_task == "rotation_decision" or normalized_action == "rotate":
        return "rotation"
    if normalized_task in {"buy_decision", "managed_pool_promotion_decision"}:
        return "position_buy_add" if normalized_task == "buy_decision" else "promotion_candidate_selection"
    if normalized_action in {"sell", "reduce"}:
        return "position_sell_reduce"
    if normalized_action in {"take_profit", "stop_loss"}:
        return "take_profit_stop_loss"
    return "position_wait_hold"


AI_VERIFICATION_ALLOWED_SUGGESTIONS = {
    "confirm",
    "override_wait",
    "override_buy",
    "override_reduce",
    "override_sell",
    "reject_signal",
}


def _safe_log_info(message: str) -> None:
    try:
        logging.getLogger("aits").info(message)
    except Exception:
        pass


AI_DECISION_ALLOWED_ACTIONS = {
    "hold",
    "wait",
    "buy",
    "add",
    "sell",
    "reduce",
    "rotate",
    "promote",
    "reject",
    "replace",
    "rotate_review",
    "reduce_and_rotate",
    "take_profit",
    "stop_loss",
}


AI_DECISION_REQUIRED_FIELDS = (
    "action",
    "confidence",
    "reason_ko",
    "eta_seconds",
    "execution_plan",
    "risk_notes",
    "invalidation_conditions",
)


_PAYLOAD_REQUIRED_FEATURES = {
    "position": (
        "qty", "avg_buy_price", "current_price", "position_value_krw", "pnl_krw",
        "pnl_pct", "weight_pct", "target_weight_pct", "holding_age", "source_type", "dust",
    ),
    "market": (
        "current_price", "price_change_1m", "price_change_5m", "price_change_15m",
        "price_change_1h", "volume_change", "trade_value", "volatility", "market_data_stale",
    ),
    "indicators": ("RSI", "MACD", "moving_averages", "momentum", "trend_strength"),
    "portfolio": (
        "total_asset_krw", "available_krw", "total_budget_krw", "exposure_for_cap",
        "cap_remaining_krw", "current_positions",
    ),
    "candidates": (
        "scanner_top_candidates", "rotation_candidates", "managed_pool_symbols", "opportunity_gap",
    ),
    "constraints": (
        "min_order_krw", "available_qty", "buy_blocked", "buy_blocker",
        "sell_allowed_precheck", "duplicate_locks", "dust_excluded",
    ),
    "prior_decision": ("prior_ai_decision",),
    "eta_state": ("eta_state", "invalidation_conditions"),
    "output_schema": ("action", "confidence", "reason_ko", "eta_seconds", "invalidation_conditions"),
}


def _payload_feature_value(payload: Dict[str, Any], group: str, name: str) -> tuple[bool, Any]:
    aliases = {
        ("candidates", "opportunity_gap"): ("opportunity_score_gap",),
        ("constraints", "sell_allowed_precheck"): ("sell_allowed_guard_precheck",),
        ("constraints", "dust_excluded"): ("dust", "dust_holdings_excluded"),
    }
    if group in ("prior_decision", "eta_state"):
        container = payload
    elif group == "output_schema":
        container = payload.get("output_schema") or payload.get("required_output_schema") or {}
    else:
        container = payload.get(group) or {}
    if not isinstance(container, dict):
        return False, None
    for key in (name, *aliases.get((group, name), ())):
        if key in container:
            return True, container.get(key)
    if group == "market" and name == "current_price":
        position = payload.get("position") or {}
        if isinstance(position, dict) and "current_price" in position:
            return True, position.get("current_price")
    if group == "eta_state" and name == "invalidation_conditions":
        prior = payload.get("prior_ai_decision") or {}
        if isinstance(prior, dict) and "invalidation_conditions" in prior:
            return True, prior.get("invalidation_conditions")
    return False, None


def _safe_payload_preview(value: Any) -> Any:
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return {"count": len(value)}
    text = str(value or "").strip()
    if text.lower() in {"none", "unavailable", "unknown", "fresh", "stale"}:
        return text.lower()
    return None


def build_ai_payload_feature_manifest(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    safe_payload = dict(payload or {})
    encoded = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    payload_hash = hashlib.sha256(encoded).hexdigest()[:24]
    task = str(safe_payload.get("task") or "")
    symbol = str(safe_payload.get("symbol") or "PORTFOLIO")
    is_portfolio = task == "portfolio_management_decision" or (
        task == "ai_redecision"
        and (
            str(safe_payload.get("scope") or "") == "portfolio_management"
            or symbol == "PORTFOLIO"
        )
    )
    groups: Dict[str, list[Dict[str, Any]]] = {}
    available = missing = stale = unavailable = unknown_freshness = 0
    critical_missing: list[str] = []
    stale_features: list[str] = []
    required_total = 0
    market_stale = bool((safe_payload.get("market") or {}).get("market_data_stale")) if isinstance(safe_payload.get("market"), dict) else False
    feature_metadata = safe_payload.get("feature_metadata") if isinstance(safe_payload.get("feature_metadata"), dict) else {}
    computed_names = {"pnl_krw", "pnl_pct", "weight_pct", "position_value_krw", "opportunity_gap"}
    for group, names in _PAYLOAD_REQUIRED_FEATURES.items():
        entries = []
        group_required = not is_portfolio or group in {"portfolio", "candidates", "constraints", "output_schema"}
        for name in names:
            present, value = _payload_feature_value(safe_payload, group, name)
            required = bool(group_required)
            required_total += int(required)
            value_state = "missing" if not present else "null" if value is None else "available"
            if present and isinstance(value, str) and value.strip().lower() in {"unavailable", "n/a", "unknown"}:
                value_state = "unavailable"
            if present and value_state == "available" and name in computed_names:
                value_state = "computed"
            metadata = feature_metadata.get(f"{group}.{name}") if isinstance(feature_metadata.get(f"{group}.{name}"), dict) else {}
            freshness = str(metadata.get("freshness") or "").lower()
            if freshness not in {"fresh", "stale", "unknown"}:
                freshness = "stale" if market_stale and group in {"market", "indicators"} else "unknown"
            if group == "market" and name == "market_data_stale" and present:
                freshness = "stale" if bool(value) else "fresh"
            if freshness == "stale":
                stale += int(required)
                stale_features.append(f"{group}.{name}")
            elif required and freshness == "unknown" and group in {"market", "indicators"} and value_state in {"available", "computed"}:
                unknown_freshness += 1
            if required:
                if value_state in {"available", "computed"}:
                    available += 1
                elif value_state == "unavailable":
                    unavailable += 1
                    critical_missing.append(f"{group}.{name}")
                else:
                    missing += 1
                    critical_missing.append(f"{group}.{name}")
            entries.append({
                "name": name,
                "present": present,
                "value_state": value_state,
                "source": str(metadata.get("source") or (f"payload.{group}" if present else "")),
                "updated_at": metadata.get("updated_at"),
                "age_sec": metadata.get("age_sec"),
                "freshness": freshness,
                "required": required,
                "blocker": "" if value_state in {"available", "computed"} else f"feature_{value_state}",
                "safe_preview_value": _safe_payload_preview(value),
            })
        groups[group] = entries
    coverage = available / max(required_total, 1)
    if coverage >= 0.90 and stale == 0 and unknown_freshness == 0:
        grade = "A"
    elif coverage >= 0.75:
        grade = "B"
    elif coverage >= 0.50:
        grade = "C"
    elif coverage >= 0.25:
        grade = "D"
    else:
        grade = "F"
    manifest = {
        "payload_hash": payload_hash,
        "task": task,
        "symbol_or_scope": symbol,
        "created_at": int(time.time()),
        "feature_groups": groups,
        "payload_quality_grade": grade,
        "payload_required_feature_count": required_total,
        "payload_available_feature_count": available,
        "payload_missing_feature_count": missing,
        "payload_stale_feature_count": stale,
        "payload_unavailable_feature_count": unavailable,
        "payload_unknown_freshness_count": unknown_freshness,
        "critical_missing_features": critical_missing,
        "stale_features": sorted(set(stale_features)),
        "recommended_blocker": "" if grade in {"A", "B"} else "ai_payload_critical_features_missing",
    }
    manifest_basis = dict(manifest)
    manifest_basis.pop("created_at", None)
    manifest["feature_manifest_hash"] = hashlib.sha256(
        json.dumps(manifest_basis, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]
    return manifest


def summarize_ai_payload_feature_manifest(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(manifest or {})
    return {key: source.get(key) for key in (
        "payload_hash", "feature_manifest_hash", "payload_quality_grade",
        "payload_required_feature_count", "payload_available_feature_count",
        "payload_missing_feature_count", "payload_stale_feature_count",
        "payload_unavailable_feature_count", "critical_missing_features", "stale_features",
        "payload_unknown_freshness_count",
        "recommended_blocker",
    )}


def correlate_ai_data_gap_reason(decision: Optional[Dict[str, Any]], manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    decision = dict(decision or {})
    reason = f"{decision.get('reason_ko') or ''} {decision.get('risk_notes') or ''}".lower()
    phrases = (
        "데이터 부족", "데이터가 부족", "정보 부족", "추가 데이터 필요", "추가적인 데이터 분석이 필요",
        "판단 근거 부족", "지표 부족", "시장 데이터 부족", "분석 정보 부족", "불충분",
        "insufficient data", "insufficient information", "more data needed", "additional data needed",
        "lack of data", "limited data", "not enough data", "missing data",
    )
    matched_phrase = next((token for token in phrases if token in reason), "")
    mentions = bool(matched_phrase)
    missing_features = list((manifest or {}).get("critical_missing_features") or []) if mentions else []
    stale_features = list((manifest or {}).get("stale_features") or []) if mentions else []
    return {
        "ai_reason_mentions_insufficient_data": mentions,
        "insufficient_data_phrase_matched": matched_phrase,
        "insufficient_data_related_missing_features": missing_features,
        "insufficient_data_related_stale_features": stale_features,
        "ai_wait_due_to_data_gap": bool(mentions and str(decision.get("action") or "").lower() in {"wait", "hold"}),
    }


def summarize_invalidation_condition_shapes(decision: Optional[Dict[str, Any]]) -> Dict[str, int]:
    conditions = list((decision or {}).get("invalidation_conditions") or [])
    structured = sum(1 for item in conditions if isinstance(item, dict) and all(key in item for key in ("condition_type", "feature", "operator")))
    natural = sum(1 for item in conditions if isinstance(item, str) and item.strip())
    return {
        "invalidation_conditions_structured_count": structured,
        "invalidation_conditions_natural_language_count": natural,
        "invalidation_conditions_missing_count": int(not conditions),
    }


def log_ai_payload_feature_manifest(manifest: Optional[Dict[str, Any]]) -> None:
    item = dict(manifest or {})
    missing = list(item.get("critical_missing_features") or [])
    stale_items = list(item.get("stale_features") or [])
    common = (
        f"task={item.get('task') or '-'} symbol={item.get('symbol_or_scope') or '-'} "
        f"payload_hash={item.get('payload_hash') or '-'} feature_manifest_hash={item.get('feature_manifest_hash') or '-'}"
    )
    _safe_log_info(f"[AITS][AIPayloadQuality] event=payload_feature_manifest_created {common} actual_order=False submitted=0")
    _safe_log_info(
        f"[AITS][AIPayloadQuality] event=payload_quality_scored {common} "
        f"payload_quality_grade={item.get('payload_quality_grade') or '-'} "
        f"required_count={int(item.get('payload_required_feature_count') or 0)} "
        f"available_count={int(item.get('payload_available_feature_count') or 0)} "
        f"missing_count={int(item.get('payload_missing_feature_count') or 0)} "
        f"stale_count={int(item.get('payload_stale_feature_count') or 0)} "
        f"unavailable_count={int(item.get('payload_unavailable_feature_count') or 0)} "
        f"unknown_freshness_count={int(item.get('payload_unknown_freshness_count') or 0)} actual_order=False submitted=0"
    )
    if missing:
        _safe_log_info(f"[AITS][AIPayloadQuality] event=payload_feature_missing {common} features={','.join(missing)} actual_order=False submitted=0")
    if stale_items:
        _safe_log_info(f"[AITS][AIPayloadQuality] event=payload_feature_stale {common} features={','.join(stale_items)} actual_order=False submitted=0")


def build_ai_decision_blocker(blockers: Any) -> str:
    if isinstance(blockers, (list, tuple)):
        for item in blockers:
            text = str(item or "").strip()
            if text:
                return text
        return ""
    return str(blockers or "").strip()


def _decision_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def populate_position_payload_market_indicators(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = dict(context or {})
    task = str(payload.get("task") or "").strip()
    scope = str(payload.get("scope") or "").strip().lower()
    symbol = str(payload.get("symbol") or "").strip().upper()
    is_position_redecision = bool(
        task == "ai_redecision"
        and scope != "portfolio_management"
        and symbol != "PORTFOLIO"
    )
    if task != AI_POSITION_TASK_CANONICAL and not is_position_redecision:
        return payload
    if not symbol:
        return payload
    market = dict(payload.get("market") or {})
    indicators = dict(payload.get("indicators") or {})
    metadata = dict(payload.get("feature_metadata") or {})
    candles = []
    try:
        from app.services.market_feed import get_candle_minute
        candles = list(get_candle_minute(symbol, unit=1, count=121, ttl=30.0) or [])
    except Exception:
        candles = []
    candles = [item for item in reversed(candles) if isinstance(item, dict) and _decision_float(item.get("trade_price"), 0.0) > 0.0]
    closes = [_decision_float(item.get("trade_price"), 0.0) for item in candles]
    volumes = [_decision_float(item.get("candle_acc_trade_volume"), 0.0) for item in candles]
    latest_ts = str(candles[-1].get("candle_date_time_kst") or "") if candles else ""
    age_sec = None
    if latest_ts:
        try:
            from datetime import datetime
            age_sec = max(0.0, time.time() - datetime.fromisoformat(latest_ts).timestamp())
        except Exception:
            age_sec = None
    def _pct(minutes: int) -> Optional[float]:
        if len(closes) <= minutes or closes[-(minutes + 1)] <= 0.0:
            return None
        return (closes[-1] / closes[-(minutes + 1)] - 1.0) * 100.0
    def _ema(values: list[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        alpha = 2.0 / (period + 1.0)
        result = sum(values[:period]) / period
        for value in values[period:]:
            result = alpha * value + (1.0 - alpha) * result
        return result
    for minutes in (1, 5, 15, 60):
        key = "price_change_1h" if minutes == 60 else f"price_change_{minutes}m"
        if market.get(key) is None:
            market[key] = _pct(minutes)
    if market.get("current_price") is None:
        market["current_price"] = (payload.get("position") or {}).get("current_price")
    if market.get("volume_change") is None and len(volumes) >= 10:
        recent, prior = sum(volumes[-5:]) / 5.0, sum(volumes[-10:-5]) / 5.0
        market["volume_change"] = ((recent / prior) - 1.0) * 100.0 if prior > 0.0 else None
    if market.get("volatility") is None and len(closes) >= 11:
        returns = [(closes[idx] / closes[idx - 1] - 1.0) * 100.0 for idx in range(max(1, len(closes) - 30), len(closes)) if closes[idx - 1] > 0.0]
        if returns:
            mean = sum(returns) / len(returns)
            market["volatility"] = math.sqrt(sum((item - mean) ** 2 for item in returns) / len(returns))
    if market.get("trade_value") is None and candles:
        market["trade_value"] = sum(_decision_float(item.get("candle_acc_trade_price"), 0.0) for item in candles[-60:])
    if age_sec is not None:
        market["market_data_stale"] = bool(age_sec > 180.0)
    elif "market_data_stale" not in market:
        market["market_data_stale"] = None
    if indicators.get("RSI") is None and indicators.get("rsi") is None and len(closes) >= 15:
        changes = [closes[idx] - closes[idx - 1] for idx in range(len(closes) - 14, len(closes))]
        gain = sum(max(item, 0.0) for item in changes) / 14.0
        loss = sum(max(-item, 0.0) for item in changes) / 14.0
        indicators["RSI"] = 100.0 if loss == 0.0 and gain > 0.0 else (50.0 if loss == 0.0 else 100.0 - 100.0 / (1.0 + gain / loss))
    ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
    if indicators.get("MACD") is None and indicators.get("macd") is None and ema12 is not None and ema26 is not None:
        macd_series = []
        for end in range(26, len(closes) + 1):
            fast, slow = _ema(closes[:end], 12), _ema(closes[:end], 26)
            if fast is not None and slow is not None:
                macd_series.append(fast - slow)
        signal = _ema(macd_series, 9)
        value = ema12 - ema26
        indicators["MACD"] = {"macd": value, "signal": signal, "histogram": value - signal if signal is not None else None}
    moving = indicators.get("moving_averages") if isinstance(indicators.get("moving_averages"), dict) else {}
    for period in (5, 20, 60):
        if len(closes) >= period and moving.get(f"ma{period}") is None:
            moving[f"ma{period}"] = sum(closes[-period:]) / period
    indicators["moving_averages"] = moving or None
    if indicators.get("momentum") is None:
        indicators["momentum"] = _pct(10)
    if indicators.get("trend_strength") is None and moving.get("ma5") is not None and moving.get("ma20"):
        indicators["trend_strength"] = (float(moving["ma5"]) / float(moving["ma20"]) - 1.0) * 100.0
    freshness = "stale" if age_sec is not None and age_sec > 180.0 else ("fresh" if age_sec is not None else "unknown")
    for group, names in {
        "market": ("price_change_1m", "price_change_5m", "price_change_15m", "price_change_1h", "volume_change", "trade_value", "volatility", "market_data_stale"),
        "indicators": ("RSI", "MACD", "moving_averages", "momentum", "trend_strength"),
    }.items():
        for name in names:
            metadata[f"{group}.{name}"] = {"source": "market_feed.minute_candle_cache" if candles else "payload", "updated_at": latest_ts or None, "age_sec": age_sec, "freshness": freshness}
    payload["market"], payload["indicators"], payload["feature_metadata"] = market, indicators, metadata
    if is_position_redecision and isinstance(payload.get("current_state"), dict):
        current_state = dict(payload["current_state"])
        current_state["market"] = dict(market)
        current_state["indicators"] = dict(indicators)
        payload["current_state"] = current_state
    _safe_log_info(
        "[AITS][AIPayloadPopulation] event=market_indicator_snapshot_built "
        f"symbol={symbol or '-'} candle_count={len(candles)} source={'market_feed.minute_candle_cache' if candles else 'payload'} "
        f"updated_at={latest_ts or '-'} age_sec={age_sec} "
        f"rsi_available={indicators.get('RSI') is not None or indicators.get('rsi') is not None} "
        f"macd_available={indicators.get('MACD') is not None or indicators.get('macd') is not None} "
        f"price_change_available={all(market.get(key) is not None for key in ('price_change_1m', 'price_change_5m', 'price_change_15m', 'price_change_1h'))} "
        f"volume_available={market.get('volume_change') is not None} volatility_available={market.get('volatility') is not None} "
        "actual_order=False submitted=0"
    )
    return payload


def _decision_allowed_rotation_symbols(candidates: Any) -> set[str]:
    allowed: set[str] = set()

    def _add(value: Any) -> None:
        symbol = str(value or "").strip().upper()
        if symbol:
            allowed.add(symbol)

    if isinstance(candidates, dict):
        for key in ("rotation_candidates", "scanner_top_candidates", "managed_pool_symbols", "holdings_symbols"):
            values = candidates.get(key)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        _add(item.get("symbol") or item.get("market") or item.get("ticker"))
                    else:
                        _add(item)
        for key in ("rotate_to_symbol", "symbol"):
            _add(candidates.get(key))
    elif isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                _add(item.get("symbol") or item.get("market") or item.get("ticker"))
            else:
                _add(item)
    return allowed


def validate_ai_decision_response(
    response: Optional[Dict[str, Any]],
    *,
    provider: Any = "",
    task: str = "",
    symbol: str = "",
    candidates: Any = None,
) -> Dict[str, Any]:
    """Normalize and validate the final AI decision contract.

    The validator never executes orders. Invalid decisions are converted into a
    non-executable wait decision with an explicit blocker.
    """
    provider_text = str(provider or "").strip().lower() or "unknown"
    task_text = str(task or "").strip() or "ai_decision"
    symbol_text = str(symbol or "").strip().upper()
    _safe_log_info(
        "[AITS][AIDecisionValidator] event=validation_started "
        f"provider={provider_text} task={task_text} symbol={symbol_text or '-'} "
        "actual_order=False submitted=0"
    )

    if not isinstance(response, dict) or not response:
        blocker = "ai_decision_response_missing"
        decision = {
            "schema": "aits_ai_decision_response_v1",
            "action": "wait",
            "confidence": 0.0,
            "reason_ko": "AI 판단 응답이 없어 주문을 보류합니다.",
            "eta_seconds": 300,
            "execution_plan": {},
            "risk_notes": "",
            "invalidation_conditions": [],
            "sell_ratio": 0.0,
            "buy_amount_krw": 0.0,
            "rotate_to_symbol": "",
            "validation_passed": False,
            "validator_result": "failed",
            "validation_blocker": blocker,
            "blocker": blocker,
            "actual_order": False,
            "submitted": 0,
        }
        _safe_log_info(
            "[AITS][AIDecisionValidator] event=validation_failed "
            f"provider={provider_text} task={task_text} symbol={symbol_text or '-'} "
            f"action=wait confidence=0 blocker={blocker} reason=response_missing actual_order=False submitted=0"
        )
        return {"valid": False, "validation_passed": False, "blocker": blocker, "blockers": [blocker], "decision": decision}

    source = dict(response or {})
    blockers: list[str] = []
    execution_plan = source.get("execution_plan")
    if not isinstance(execution_plan, dict):
        execution_plan = {}
        blockers.append("ai_decision_execution_plan_missing")

    action = str(source.get("action") or source.get("decision") or "").strip().lower()
    if action not in AI_DECISION_ALLOWED_ACTIONS:
        blockers.append("ai_decision_action_invalid")
        action = "wait"

    confidence_raw = source.get("confidence")
    confidence = _decision_float(confidence_raw, -1.0)
    if confidence < 0.0 or confidence > 1.0:
        blockers.append("ai_decision_confidence_invalid")
        confidence = max(0.0, min(1.0, _decision_float(confidence_raw, 0.0)))

    reason_ko = str(source.get("reason_ko") or source.get("reason") or "").strip()
    if not reason_ko:
        blockers.append("ai_decision_reason_missing")
        reason_ko = "AI 판단 근거가 비어 있어 주문을 보류합니다."

    eta_raw = source.get("eta_seconds", 300)
    eta_seconds = int(_decision_float(eta_raw, -1.0))
    if eta_seconds < 0:
        blockers.append("ai_decision_eta_invalid")
        eta_seconds = 300

    invalidation_conditions = source.get("invalidation_conditions")
    if invalidation_conditions is None:
        invalidation_conditions = []
    elif isinstance(invalidation_conditions, dict):
        invalidation_conditions = [invalidation_conditions]
    elif not isinstance(invalidation_conditions, list):
        invalidation_conditions = [str(invalidation_conditions)]

    risk_notes = str(source.get("risk_notes") or "")[:1000]
    sell_ratio = _decision_float(source.get("sell_ratio", execution_plan.get("sell_ratio", 0.0)), 0.0)
    buy_amount_krw = _decision_float(source.get("buy_amount_krw", execution_plan.get("buy_amount_krw", 0.0)), 0.0)
    rotate_to_symbol = str(source.get("rotate_to_symbol") or execution_plan.get("rotate_to_symbol") or "").strip().upper()
    replace_symbol = str(
        source.get("replace_symbol")
        or execution_plan.get("replace_symbol")
        or source.get("replace_target_symbol")
        or execution_plan.get("replace_target_symbol")
        or ""
    ).strip().upper()

    if action in {"buy", "add"} and buy_amount_krw <= 0.0:
        blockers.append("ai_decision_buy_amount_missing")
    if action in {"sell", "reduce", "take_profit", "stop_loss"}:
        if sell_ratio <= 0.0:
            blockers.append("ai_decision_sell_ratio_missing")
        elif sell_ratio > 1.0:
            blockers.append("ai_decision_sell_ratio_invalid")
    if action in {"rotate", "reduce_and_rotate"}:
        if not rotate_to_symbol:
            blockers.append("ai_decision_rotate_target_missing")
        else:
            allowed_rotation_symbols = _decision_allowed_rotation_symbols(candidates)
            if allowed_rotation_symbols and rotate_to_symbol not in allowed_rotation_symbols:
                blockers.append("ai_decision_rotate_target_invalid")
    if action == "reduce_and_rotate":
        if sell_ratio <= 0.0:
            blockers.append("rotation_sell_ratio_missing")
        elif sell_ratio > 1.0:
            blockers.append("ai_decision_sell_ratio_invalid")
    if action == "replace" and not replace_symbol:
        blockers.append("rotation_replace_target_missing" if task_text == "rotation_decision" else "promotion_replace_target_missing")

    sell_ratio = max(0.0, min(1.0, sell_ratio))
    buy_amount_krw = max(0.0, buy_amount_krw)
    blocker = build_ai_decision_blocker(blockers)
    valid = not blockers
    if not valid:
        action = "wait"

    decision = dict(source)
    decision.update(
        {
            "schema": "aits_ai_decision_response_v1",
            "action": action,
            "confidence": confidence,
            "reason_ko": reason_ko[:1000],
            "eta_seconds": eta_seconds,
            "execution_plan": execution_plan,
            "risk_notes": risk_notes,
            "invalidation_conditions": invalidation_conditions,
            "sell_ratio": sell_ratio,
            "buy_amount_krw": buy_amount_krw,
            "rotate_to_symbol": rotate_to_symbol,
            "replace_symbol": replace_symbol,
            "validation_passed": bool(valid),
            "validator_result": "passed" if valid else "failed",
            "validation_blocker": blocker,
            "blocker": blocker or str(source.get("blocker") or ""),
            "actual_order": False,
            "submitted": 0,
        }
    )
    _safe_log_info(
        "[AITS][AIDecisionValidator] event=validation_%s provider=%s task=%s symbol=%s "
        "action=%s confidence=%s blocker=%s reason=%s actual_order=False submitted=0"
        % (
            "passed" if valid else "failed",
            provider_text,
            task_text,
            symbol_text or "-",
            action or "-",
            confidence,
            blocker or "-",
            "ok" if valid else blocker or "invalid_schema",
        )
    )
    return {"valid": bool(valid), "validation_passed": bool(valid), "blocker": blocker, "blockers": blockers, "decision": decision}


def normalize_ai_decision_response(response: Optional[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
    return validate_ai_decision_response(response, **kwargs)


@dataclass
class AIEngineDecision:
    action: str = "hold"
    confidence: float = 0.0
    risk: str = "medium"
    reason: str = ""
    engine: str = "local"
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "risk": self.risk,
            "reason": self.reason,
            "engine": self.engine,
            "raw": dict(self.raw or {}),
        }


class AIEngineProvider:
    name: str = "base"
    api_required: bool = False
    ready_reason: str = "Provider not configured"

    def __init__(
        self,
        api_key: str = "",
        settings: Optional[Any] = None,
        strategy: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.settings = settings
        self.strategy = strategy
        self.config = config

    def is_ready(self) -> bool:
        return False

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="AIEngineProvider skeleton fallback",
            engine=self.name,
            raw={"mode": "skeleton", "context": dict(context or {})},
        )

    def _get_config_api_key(self, provider: Any) -> str:
        """
        Return API key from settings first, then env fallback.
        Never log the key value.
        """
        provider = normalize_provider_name(provider)
        resolved_key = ""
        key_method = "missing"

        def _iter_config_roots():
            for obj in (
                getattr(self, "strategy", None),
                getattr(self, "settings", None),
                getattr(self, "config", None),
            ):
                if obj is None:
                    continue
                yield obj
                try:
                    if isinstance(obj, dict):
                        for key in ("strategy", "settings", "config"):
                            child = obj.get(key)
                            if child is not None:
                                yield child
                    else:
                        for key in ("strategy", "settings", "config"):
                            child = getattr(obj, key, None)
                            if child is not None:
                                yield child
                except Exception:
                    pass

        def _read_config_key(obj: Any, names: tuple[str, ...]) -> str:
            try:
                for name in names:
                    if isinstance(obj, dict):
                        key = obj.get(name)
                    else:
                        key = getattr(obj, name, None)
                    if hasattr(key, "get_secret_value"):
                        key = key.get_secret_value()
                    if key:
                        return str(key).strip()
            except Exception:
                pass
            return ""

        if provider == "openai":
            for obj in _iter_config_roots():
                key = _read_config_key(obj, ("ai_openai_api_key", "openai_api_key"))
                if key:
                    resolved_key = key
                    key_method = "settings"
                    break
            if not resolved_key:
                key = os.getenv("OPENAI_API_KEY")
                if key:
                    resolved_key = key
                    key_method = "environment"

        elif provider == "gemini":
            for obj in _iter_config_roots():
                key = _read_config_key(
                    obj,
                    ("ai_gemini_api_key", "gemini_api_key", "google_api_key"),
                )
                if key:
                    resolved_key = key
                    key_method = "settings"
                    break
            if not resolved_key:
                key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if key:
                    resolved_key = key
                    key_method = "environment"
        try:
            _provider_name = normalize_provider_label(provider)

            print(
                "[AITS][AIEngineProvider] key_resolution "
                f"| provider={_provider_name or 'unknown'} "
                f"| resolved={bool(resolved_key)} "
                f"| method={key_method}"
            )
        except Exception:
            pass

        return resolved_key

    def _get_runtime_decision_model(self, provider: str) -> str:
        provider = normalize_provider_name(provider)
        names = ("ai_openai_model", "openai_model") if provider == "openai" else ("ai_gemini_model", "gemini_model")
        for root in (self.strategy, self.settings, self.config):
            if root is None:
                continue
            roots = [root]
            if isinstance(root, dict):
                roots.extend(root.get(key) for key in ("strategy", "settings", "config") if root.get(key) is not None)
            for item in roots:
                for name in names:
                    value = item.get(name) if isinstance(item, dict) else getattr(item, name, None)
                    value = str(value or "").strip()
                    if value:
                        return "chat-latest" if provider == "openai" and value == "gpt-5.5-instant" else value
        if provider == "openai":
            return str(os.getenv("AITS_OPENAI_POSITION_DECISION_MODEL") or os.getenv("AITS_OPENAI_VERIFY_MODEL") or "gpt-4o-mini").strip()
        return str(os.getenv("AITS_GEMINI_POSITION_DECISION_MODEL") or os.getenv("AITS_GEMINI_VERIFY_MODEL") or "gemini-2.0-flash").strip()

    def _read_runtime_config(self, names: tuple[str, ...], default: Any) -> Any:
        for root in (self.strategy, self.settings, self.config):
            if root is None:
                continue
            roots = [root]
            if isinstance(root, dict):
                roots.extend(root.get(key) for key in ("strategy", "settings", "config") if root.get(key) is not None)
            for item in roots:
                for name in names:
                    value = item.get(name) if isinstance(item, dict) else getattr(item, name, None)
                    if value not in (None, ""):
                        return value
        return default

    def _get_local_runtime_config(self) -> Dict[str, Any]:
        def _as_bool(value: Any, default: bool) -> bool:
            if value in (None, ""):
                return default
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        return {
            "base_url": str(self._read_runtime_config(("ai_local_url", "local_ai_url"), "http://127.0.0.1:11434")).strip(),
            "model": str(self._read_runtime_config(("ai_local_model", "local_ai_model"), "qwen2.5")).strip(),
            "timeout_sec": max(5, int(self._read_runtime_config(("ai_local_timeout_seconds",), 45) or 45)),
            "confidence_threshold": max(0.0, min(1.0, float(self._read_runtime_config(("ai_local_confidence_threshold",), 0.72) or 0.72))),
            "developer_only": _as_bool(
                self._read_runtime_config(("local_ollama_developer_only",), True), True
            ),
            "auto_generate_enabled": _as_bool(
                self._read_runtime_config(("local_ollama_auto_generate_enabled",), False), False
            ),
            "auto_generate_on_live_enabled": _as_bool(
                self._read_runtime_config(("local_ollama_auto_generate_on_live_enabled",), False), False
            ),
        }

    def _provider_cost_guard_policy(
        self,
        *,
        provider: str,
        context: Dict[str, Any],
        payload_hash: str,
        reserve: bool,
    ) -> Dict[str, Any]:
        """Gate external judgment calls. This never grants execution permission."""
        provider = normalize_provider_name(provider)
        task = str(context.get("task") or "").strip()
        now = time.time()
        prefix = f"AITS_{provider.upper()}_"
        enabled_default = self._read_runtime_config((f"ai_{provider}_enabled",), True)
        enabled = str(os.getenv(prefix + "ENABLED", str(enabled_default))).strip().lower() not in {"0", "false", "off", "no"}
        request_default = self._read_runtime_config(("ai_external_request_cooldown_seconds",), 15)
        duplicate_default = self._read_runtime_config(("ai_external_duplicate_payload_cooldown_seconds",), 600)
        max_hour_default = self._read_runtime_config(("ai_external_max_calls_per_hour",), 60)
        max_day_default = self._read_runtime_config(("ai_external_max_calls_per_day",), 500)
        max_live_default = self._read_runtime_config(("ai_external_max_live_order_calls_per_hour",), 20)
        max_tokens_default = self._read_runtime_config(("ai_external_max_tokens_estimate_per_call",), 1200)
        daily_cost_default = self._read_runtime_config(("ai_external_daily_estimated_cost_limit",), 5.0)
        request_cooldown = max(0, int(os.getenv(prefix + "REQUEST_COOLDOWN_SECONDS", str(request_default)) or request_default))
        duplicate_cooldown = max(0, int(os.getenv(prefix + "DUPLICATE_PAYLOAD_COOLDOWN_SECONDS", str(duplicate_default)) or duplicate_default))
        max_hour = max(1, int(os.getenv(prefix + "MAX_CALLS_PER_HOUR", str(max_hour_default)) or max_hour_default))
        max_day = max(1, int(os.getenv(prefix + "MAX_CALLS_PER_DAY", str(max_day_default)) or max_day_default))
        max_live_hour = max(1, int(os.getenv(prefix + "MAX_LIVE_ORDER_CALLS_PER_HOUR", str(max_live_default)) or max_live_default))
        max_tokens = max(1, int(os.getenv(prefix + "MAX_TOKENS_ESTIMATE_PER_CALL", str(max_tokens_default)) or max_tokens_default))
        daily_cost_limit = max(0.0, float(os.getenv(prefix + "DAILY_ESTIMATED_COST_LIMIT", str(daily_cost_default)) or daily_cost_default))
        estimated_cost = max_tokens / 1_000_000.0 * (0.60 if provider == "openai" else 0.35)
        api_key = self._get_config_api_key(provider)
        model = self._get_runtime_decision_model(provider)
        order_related = task in {"buy_decision", "sell_decision", "rotation_decision", "managed_pool_promotion_decision"}
        _PROVIDER_CALL_HISTORY[:] = [
            row for row in _PROVIDER_CALL_HISTORY
            if now - float(row.get("at") or 0.0) < 86400
        ]
        history = [row for row in _PROVIDER_CALL_HISTORY if row.get("provider") == provider]
        hour_rows = [row for row in history if now - float(row.get("at") or 0.0) < 3600]
        day_rows = [row for row in history if now - float(row.get("at") or 0.0) < 86400]
        live_hour_rows = [row for row in hour_rows if bool(row.get("order_related"))]
        projected_daily_cost = sum(float(row.get("estimated_cost") or 0.0) for row in day_rows) + estimated_cost
        payload_key = f"{provider}:{payload_hash}"
        request_remaining = max(0.0, request_cooldown - (now - _PROVIDER_LAST_CALL.get(provider, 0.0)))
        duplicate_remaining = max(0.0, duplicate_cooldown - (now - _PROVIDER_PAYLOAD_LAST_CALL.get(payload_key, 0.0)))

        blocker = ""
        event = "cost_guard_passed"
        if provider not in {"openai", "gemini"}:
            blocker, event = "provider_unavailable", "provider_unavailable"
        elif not enabled:
            blocker, event = "provider_disabled", "provider_unavailable"
        elif task not in RUNTIME_DECISION_ALLOWED_TASKS:
            blocker, event = "external_payload_invalid", "cost_guard_blocked"
        elif str(os.getenv("AITS_DISABLE_RUNTIME_AI_DECISIONS", "")).strip() == "1":
            blocker, event = "runtime_decision_calls_disabled", "cost_guard_blocked"
        elif not api_key:
            blocker, event = "provider_api_key_missing", "provider_key_missing"
        elif not model:
            blocker, event = "provider_model_missing", "provider_unavailable"
        elif request_remaining > 0:
            blocker, event = "provider_request_cooldown", "cost_guard_blocked"
        elif duplicate_remaining > 0:
            blocker, event = "duplicate_payload_cooldown", "duplicate_payload_blocked"
        elif len(hour_rows) >= max_hour:
            blocker, event = "hourly_call_limit_reached", "hourly_budget_blocked"
        elif len(day_rows) >= max_day:
            blocker, event = "daily_call_limit_reached", "daily_budget_blocked"
        elif order_related and len(live_hour_rows) >= max_live_hour:
            blocker, event = "live_order_related_hourly_limit_reached", "hourly_budget_blocked"
        elif daily_cost_limit > 0 and projected_daily_cost > daily_cost_limit:
            blocker, event = "daily_estimated_cost_limit_reached", "daily_budget_blocked"

        allowed = not blocker
        if allowed and reserve:
            row = {"provider": provider, "at": now, "estimated_cost": estimated_cost, "order_related": order_related}
            _PROVIDER_CALL_HISTORY.append(row)
            _PROVIDER_LAST_CALL[provider] = now
            if payload_hash:
                _PROVIDER_PAYLOAD_LAST_CALL[payload_key] = now
            _RUNTIME_DECISION_CALL_TIMES.append(now)
            _RUNTIME_DECISION_PAYLOAD_LAST_CALL[payload_hash] = now
        _safe_log_info(
            f"[AITS][ProviderCostGuard] event={event} provider={provider or '-'} task={task or '-'} "
            f"scope={context.get('symbol') or context.get('scope') or 'PORTFOLIO'} payload_hash={payload_hash or '-'} "
            f"cooldown_remaining_sec={round(max(request_remaining, duplicate_remaining), 3)} "
            f"hourly_call_count={len(hour_rows)} daily_call_count={len(day_rows)} "
            f"estimated_cost={estimated_cost:.6f} cost_limit={daily_cost_limit:.4f} "
            f"blocked_reason={blocker or '-'} external_provider_call_allowed={str(allowed).lower()} "
            "actual_order=False submitted=0"
        )
        return {
            "allowed": allowed,
            "blocker": blocker,
            "reason": "cost_guard_ready" if allowed else blocker,
            "task": task,
            "model": model,
            "api_key": api_key,
            "key_masked": bool(api_key),
            "cost_guard_result": "passed" if allowed else "blocked",
            "cooldown_remaining_sec": round(max(request_remaining, duplicate_remaining), 3),
            "hourly_call_count": len(hour_rows),
            "daily_call_count": len(day_rows),
            "estimated_cost": estimated_cost,
            "cost_limit": daily_cost_limit,
            "now": now,
        }

    def _runtime_decision_call_policy(self, *, provider: str, context: Dict[str, Any], payload_hash: str) -> Dict[str, Any]:
        return self._provider_cost_guard_policy(
            provider=provider,
            context=context,
            payload_hash=payload_hash,
            reserve=True,
        )

    def _call_local_first_decision(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        config = self._get_local_runtime_config()
        runtime_context = context.get("runtime_context") if isinstance(context.get("runtime_context"), dict) else {}
        live_runtime_active = bool(
            runtime_context.get("runtime_contract_active", context.get("runtime_contract_active", False))
        )
        auto_generate_enabled = bool(config.get("auto_generate_enabled"))
        auto_generate_on_live_enabled = bool(config.get("auto_generate_on_live_enabled"))
        developer_only = bool(config.get("developer_only", True))
        blocker = ""
        if live_runtime_active and developer_only:
            blocker = "local_ollama_developer_only_live_blocked"
        elif live_runtime_active and not auto_generate_on_live_enabled:
            blocker = "local_ollama_auto_generate_disabled_on_live"
        elif not auto_generate_enabled:
            blocker = "local_ollama_auto_generate_disabled"
        if blocker:
            _safe_log_info(
                "[AITS][LocalFirstDecision] event=local_ollama_auto_generate_blocked "
                f"task={context.get('task') or '-'} scope={context.get('symbol') or context.get('scope') or 'PORTFOLIO'} "
                f"provider=local/ollama live_runtime_active={str(live_runtime_active).lower()} "
                f"developer_only={str(developer_only).lower()} "
                f"auto_generate_enabled={str(auto_generate_enabled).lower()} "
                f"auto_generate_on_live_enabled={str(auto_generate_on_live_enabled).lower()} "
                f"blocker={blocker} elapsed_ms=0 actual_order=False submitted=0"
            )
            raise NotImplementedError(blocker)
        result = OllamaHttpClient(config["base_url"]).generate(
            config["model"],
            prompt,
            timeout_sec=config["timeout_sec"],
            options={"temperature": 0.1, "num_predict": 420},
            option_profile="aits_local_first_v1",
        )
        content = str((result.data or {}).get("response") or "").strip()
        if not result.ok or not content:
            raise NotImplementedError("provider_local_unavailable" if not result.ok else "provider_local_failed")
        return {
            "content": content,
            "model": config["model"],
            "elapsed_sec": result.elapsed_sec,
        }

    def _evaluate_external_escalation(
        self,
        *,
        requested_provider: str,
        local_decision: Dict[str, Any],
        local_available: bool,
        feature_manifest: Dict[str, Any],
        context: Dict[str, Any],
        local_model: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        action = str(local_decision.get("action") or "wait").lower()
        confidence = float(local_decision.get("confidence") or 0.0)
        quality = str(summarize_ai_payload_feature_manifest(feature_manifest).get("payload_quality_grade") or "F")
        threshold = self._get_local_runtime_config()["confidence_threshold"]
        unit_mismatch = bool(context.get("valuation_unit_mismatch")) or bool(
            (context.get("sell_unit_guard") or {}).get("valuation_unit_mismatch")
            if isinstance(context.get("sell_unit_guard"), dict) else False
        )
        post_order = bool(context.get("post_order_replanning") or context.get("post_order_cycle_id"))
        model_state = dict(local_model or {})
        model_action = str(model_state.get("model_recommended_action") or "").lower()
        reasons: list[str] = []
        blocker = ""
        if not local_available:
            reasons.append("local_provider_unavailable")
        if confidence < threshold:
            reasons.append("local_confidence_below_threshold")
        if action in _LOCAL_EXTERNAL_CONFIRMATION_ACTIONS:
            reasons.append("local_order_action_requires_external_confirmation")
        if model_state.get("local_model_prediction_available") and model_action in _LOCAL_EXTERNAL_CONFIRMATION_ACTIONS:
            reasons.append("local_model_order_action_requires_external_confirmation")
        if model_state.get("local_model_prediction_available") and model_action and model_action != action:
            reasons.append("local_model_local_action_disagreement")
        if requested_provider in {"openai", "gemini"}:
            reasons.append("user_external_provider_policy")
        if post_order:
            reasons.append("post_order_replanning")
        if unit_mismatch:
            blocker = "live_safety_blocker_present"
        elif quality in {"D", "F"}:
            blocker = "payload_quality_too_low"
        target = requested_provider if requested_provider in {"openai", "gemini"} else ""
        if not target and reasons:
            target = "openai" if self._get_config_api_key("openai") else ("gemini" if self._get_config_api_key("gemini") else "")
        required = bool(reasons) and not blocker
        if not target and required:
            blocker = "external_provider_unavailable"
        _safe_log_info(
            "[AITS][EscalationPolicy] event=escalation_policy_evaluated "
            f"task={context.get('task') or '-'} scope={context.get('symbol') or context.get('scope') or 'PORTFOLIO'} "
            f"local_action={action} local_confidence={confidence:.4f} payload_quality_grade={quality} "
            f"escalation_required={str(required).lower()} escalation_target_provider={target or '-'} "
            f"escalation_reason={','.join(reasons) or 'local_decision_sufficient'} "
            f"escalation_blocker={blocker or '-'} actual_order=False submitted=0"
        )
        return {
            "escalation_policy_ready": True,
            "escalation_required": required,
            "escalation_target_provider": target,
            "escalation_reason": ",".join(reasons) or "local_decision_sufficient",
            "escalation_blocker": blocker,
        }

    def _evaluate_local_model_provider(
        self,
        *,
        context: Dict[str, Any],
        manifest_summary: Dict[str, Any],
        local_decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        task = str(context.get("task") or "")
        scope = str(context.get("symbol") or context.get("scope") or "PORTFOLIO")
        _safe_log_info(
            "[AITS][LocalModelProvider] event=model_load_attempted "
            f"task={task or '-'} scope={scope} actual_order=False submitted=0"
        )
        try:
            result = predict_local_model_decision(context, manifest_summary, local_decision)
        except Exception as exc:
            result = {
                "local_model_provider_available": False,
                "local_model_loaded": False,
                "local_model_prediction_attempted": False,
                "local_model_prediction_available": False,
                "local_model_prediction_blocker": f"local_model_provider_failed:{type(exc).__name__}",
            }
        calibration = load_local_model_calibration_profile()
        calibration_profile = dict(calibration.get("profile") or {})
        current_model_id = str(result.get("local_model_id") or "")
        profile_model_id = str(calibration_profile.get("source_model_id") or "")
        calibration_available = calibration.get("status") == "available"
        calibration_model_matches = bool(
            calibration_available and (not current_model_id or not profile_model_id or current_model_id == profile_model_id)
        )
        calibration_blocker = str(calibration.get("reason") or "")
        if calibration_available and not calibration_model_matches:
            calibration_blocker = "calibration_model_mismatch"
        elif calibration_available and not calibration.get("data_sufficient"):
            calibration_blocker = str(calibration_profile.get("blocker") or "calibration_data_insufficient")
        result.update({
            "local_model_calibration_profile_loaded": calibration_available,
            "local_model_calibration_profile_available": calibration_available,
            "local_model_calibration_data_sufficient": bool(calibration.get("data_sufficient") and calibration_model_matches),
            "local_model_calibration_recommendation_recorded": bool(calibration_profile.get("provider_routing_recommendation")),
            "local_model_calibration_recommendation": dict(calibration_profile.get("provider_routing_recommendation") or {}),
            "local_model_calibration_safe_for_policy_use": bool(calibration.get("safe_for_policy_use") and calibration_model_matches),
            "local_model_calibration_safe_for_live_expansion": bool(calibration.get("safe_for_live_expansion") and calibration_model_matches),
            "local_model_calibration_blocker": calibration_blocker,
            "local_model_calibration_applied_to_final_policy": False,
        })
        _safe_log_info(
            f"[AITS][LocalModelCalibration] event={'calibration_profile_loaded' if calibration_available else 'calibration_profile_unavailable'} "
            f"task={task or '-'} scope={scope} model_id={current_model_id or '-'} profile_model_id={profile_model_id or '-'} "
            f"data_sufficient={str(bool(result.get('local_model_calibration_data_sufficient'))).lower()} "
            f"safe_for_live_expansion={str(bool(result.get('local_model_calibration_safe_for_live_expansion'))).lower()} "
            f"policy_update_applied=false blocker={calibration_blocker or '-'} actual_order=False submitted=0"
        )
        if result.get("local_model_calibration_recommendation_recorded"):
            _safe_log_info(
                "[AITS][LocalModelCalibration] event=calibration_recommendation_recorded "
                f"task={task or '-'} scope={scope} policy_update_applied=false "
                "riskguard_required=true livepreflight_required=true actual_order=False submitted=0"
            )
        loaded = bool(result.get("local_model_loaded"))
        blocker = str(result.get("local_model_prediction_blocker") or "")
        _safe_log_info(
            f"[AITS][LocalModelProvider] event={'model_loaded' if loaded else 'model_unavailable'} "
            f"task={task or '-'} scope={scope} model_id={result.get('local_model_id') or '-'} "
            f"trained={str(bool(result.get('local_model_trained'))).lower()} "
            f"safe_for_live_decision={str(bool(result.get('local_model_safe_for_live_decision'))).lower()} "
            f"live_decision_enabled={str(bool(result.get('local_model_live_decision_enabled'))).lower()} "
            f"blocker={blocker or '-'} actual_order=False submitted=0"
        )
        if result.get("local_model_prediction_attempted"):
            _safe_log_info(
                "[AITS][LocalModelProvider] event=prediction_attempted "
                f"task={task or '-'} scope={scope} model_id={result.get('local_model_id') or '-'} "
                "actual_order=False submitted=0"
            )
            event = "prediction_completed" if result.get("local_model_prediction_available") else "prediction_blocked"
            _safe_log_info(
                f"[AITS][LocalModelProvider] event={event} task={task or '-'} scope={scope} "
                f"model_action={result.get('model_recommended_action') or '-'} "
                f"model_confidence={float(result.get('model_confidence') or 0.0):.4f} "
                f"model_risk_score={result.get('model_risk_score')} blocker={blocker or '-'} "
                "actual_order=False submitted=0"
            )
        if result.get("local_model_prediction_available") and not result.get("local_model_live_allowed"):
            _safe_log_info(
                "[AITS][LocalModelProvider] event=live_decision_disabled "
                f"task={task or '-'} scope={scope} blocker={blocker or 'local_model_live_disabled_by_registry'} "
                "actual_order=False submitted=0"
            )
        return result

    def verify_router_decision(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        AITS Decision Router v2.7
        Standard AI verification adapter.

        Safety:
        - Router decision 검증 의견만 반환한다.
        - 주문/action/final decision을 변경하지 않는다.
        - Local/basic은 API 호출하지 않는다.
        - OpenAI/Gemini도 실제 호출 메서드가 명확히 있을 때만 호출한다.
        """
        provider = str(provider or "local").strip().lower()
        context = context or {}

        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"

        try:
            _provider_norm = str(provider or "local").strip().lower()

            _openai_key = self._get_config_api_key("openai")
            _gemini_key = self._get_config_api_key("gemini")

            _openai_ready = bool(_openai_key)
            _gemini_ready = bool(_gemini_key)

            _reason = ""
            if _provider_norm == "openai" and not _openai_ready:
                _reason = "openai_api_key_missing"
            elif _provider_norm == "gemini" and not _gemini_ready:
                _reason = "gemini_api_key_missing"
            elif _provider_norm not in ("openai", "gemini", "local", "basic", "none", ""):
                _reason = f"unsupported_provider:{_provider_norm}"
            else:
                _reason = "ready" if (
                    (_provider_norm == "openai" and _openai_ready)
                    or (_provider_norm == "gemini" and _gemini_ready)
                    or (_provider_norm == "local")
                ) else "not_applicable"

            logging.getLogger("aits").info(
                "[AITS][AIProviderReadiness] "
                f"provider={_provider_norm} | "
                f"openai_ready={_openai_ready} | "
                f"gemini_ready={_gemini_ready} | "
                f"reason={_reason}"
            )
        except Exception:
            pass

        if provider in ("basic", "local", "localprovider", "none", ""):
            try:
                import random

                _force_ai = str(os.getenv("AITS_FORCE_AI_SAMPLE", "0")).lower() in ("1", "true", "yes", "on")

                if _force_ai:
                    _r = random.random()

                    if _r < 0.2:
                        return self._with_ai_result_contract({
                            "suggestion": "confirm",
                            "reason": "local_forced_confirm",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        })

                    if _r < 0.3:
                        return self._with_ai_result_contract({
                            "suggestion": "reject_signal",
                            "reason": "local_forced_reject",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        })
            except Exception:
                pass

            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": "local_provider_no_api_call",
                "risk_note": None,
                "provider": "local",
                "applied": False,
            })

        if provider not in ("openai", "gemini"):
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": f"unsupported_provider:{provider}",
                "provider": provider,
                "applied": False,
            })

        try:
            prompt = self._build_router_verification_prompt(context)
            raw_response = None

            if provider == "openai":
                raw_response = self._call_openai_router_verification(prompt, context)
            elif provider == "gemini":
                raw_response = self._call_gemini_router_verification(prompt, context)

            return self._parse_router_verification_response(
                raw_response=raw_response,
                provider=provider,
            )
        except NotImplementedError as exc:
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": str(exc) or f"{provider}_verifier_not_implemented",
                "provider": provider,
                "applied": False,
            })
        except Exception as exc:
            error_reason = str(exc)[:500]
            if not error_reason:
                error_reason = f"{provider}_verifier_error:{type(exc).__name__}"
            result_reason = error_reason
            if error_reason in (
                "openai_quota_exceeded",
                "openai_api_key_invalid",
                "openai_bad_request",
                "gemini_quota_exceeded",
                "gemini_api_key_invalid",
                "gemini_bad_request",
            ):
                result_reason = f"{error_reason}:error"
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": result_reason,
                "provider": provider,
                "applied": False,
                "error": error_reason,
            })

    def generate_managed_pool_opinion(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Managed Pool opinion-only provider call.

        This path is intentionally separate from Router verification: it asks for
        a display/review opinion and never applies, routes, or executes an order.
        """
        provider = str(provider or "local").strip().lower()
        context = dict(context or {})
        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"
        if provider not in ("openai", "gemini"):
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": f"unsupported_provider:{provider}",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })

        try:
            prompt = self._build_managed_pool_opinion_prompt(context)
            if provider == "openai":
                raw = self._call_openai_managed_pool_opinion(prompt, context)
            else:
                raw = self._call_gemini_managed_pool_opinion(prompt, context)
            parsed = self._parse_managed_pool_opinion_response(raw.get("content"), context)
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": True,
                "response_id": str(raw.get("response_id") or ""),
                "usage_input_tokens": raw.get("usage_input_tokens"),
                "usage_output_tokens": raw.get("usage_output_tokens"),
                "usage_total_tokens": raw.get("usage_total_tokens"),
                "opinion": parsed.get("opinion"),
                "status_label": parsed.get("status_label"),
                "confidence": parsed.get("confidence"),
                "reason": parsed.get("reason"),
                "next_action": parsed.get("next_action"),
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })
        except NotImplementedError as exc:
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": str(exc) or f"{provider}_managed_pool_opinion_not_implemented",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })
        except Exception as exc:
            reason = str(exc)[:500] or f"{provider}_managed_pool_opinion_error:{type(exc).__name__}"
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": reason,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })

    def generate_position_management_decision(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ask the selected AI provider for a position-management decision.

        This returns a decision contract only. It never routes or submits orders.
        """
        provider = str(provider or "local").strip().lower()
        context = dict(context or {})
        raw_task = str(context.get("task") or "").strip()
        canonical_task = AI_POSITION_TASK_ALIASES.get(raw_task, raw_task)
        if canonical_task != raw_task:
            context["task"] = canonical_task
            _safe_log_info(
                "[AITS][AITaskContract] event=task_alias_normalized "
                f"input_task={raw_task} canonical_task={canonical_task} symbol={context.get('symbol') or '-'} "
                "blocker=- actual_order=False submitted=0"
            )
        task_valid = canonical_task in RUNTIME_DECISION_ALLOWED_TASKS
        _safe_log_info(
            f"[AITS][AITaskContract] event={'task_contract_validated' if task_valid else 'task_contract_invalid'} "
            f"input_task={raw_task or '-'} canonical_task={canonical_task or '-'} symbol={context.get('symbol') or '-'} "
            f"blocker={'-' if task_valid else 'ai_position_task_contract_invalid'} actual_order=False submitted=0"
        )
        context = populate_position_payload_market_indicators(context)
        feature_manifest = build_ai_payload_feature_manifest(context)
        log_ai_payload_feature_manifest(feature_manifest)

        def _with_payload_quality(decision: Dict[str, Any]) -> Dict[str, Any]:
            result = dict(decision or {})
            summary = summarize_ai_payload_feature_manifest(feature_manifest)
            correlation = correlate_ai_data_gap_reason(result, feature_manifest)
            condition_shapes = summarize_invalidation_condition_shapes(result)
            result["payload_feature_manifest_summary"] = summary
            result.update(correlation)
            result.update(condition_shapes)
            if str(feature_manifest.get("task") or "") == "ai_redecision":
                _safe_log_info(
                    "[AITS][AIReDecisionPayload] event=redecision_payload_quality_scored "
                    f"symbol={feature_manifest.get('symbol_or_scope') or '-'} "
                    f"scope={context.get('scope') or 'position_management'} "
                    f"payload_quality_grade={summary.get('payload_quality_grade') or '-'} "
                    f"required_count={summary.get('payload_required_feature_count') or 0} "
                    f"available_count={summary.get('payload_available_feature_count') or 0} "
                    f"missing_count={summary.get('payload_missing_feature_count') or 0} "
                    f"payload_hash={summary.get('payload_hash') or '-'} provider_population_applied=True "
                    "actual_order=False submitted=0"
                )
            if correlation["ai_reason_mentions_insufficient_data"]:
                _safe_log_info(
                    "[AITS][AIPayloadQuality] event=ai_data_gap_reason_correlated "
                    f"task={feature_manifest.get('task') or '-'} symbol={feature_manifest.get('symbol_or_scope') or '-'} "
                    f"payload_hash={feature_manifest.get('payload_hash') or '-'} "
                    f"ai_wait_due_to_data_gap={correlation['ai_wait_due_to_data_gap']} "
                    f"missing_features={','.join(correlation['insufficient_data_related_missing_features']) or '-'} "
                    f"stale_features={','.join(correlation['insufficient_data_related_stale_features']) or '-'} "
                    "actual_order=False submitted=0"
                )
            _safe_log_info(
                "[AITS][AIPayloadQuality] event=invalidation_condition_shape_checked "
                f"task={feature_manifest.get('task') or '-'} symbol={feature_manifest.get('symbol_or_scope') or '-'} "
                f"payload_hash={feature_manifest.get('payload_hash') or '-'} "
                f"structured_count={condition_shapes['invalidation_conditions_structured_count']} "
                f"natural_language_count={condition_shapes['invalidation_conditions_natural_language_count']} "
                f"missing_count={condition_shapes['invalidation_conditions_missing_count']} "
                "actual_order=False submitted=0"
            )
            return result
        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"
        return _with_payload_quality(
            self._route_local_first_decision(
                requested_provider=provider,
                context=context,
                feature_manifest=feature_manifest,
            )
        )
        try:
            if provider in ("basic", "local", "local_ai", ""):
                parsed = self._build_local_position_management_decision(context)
                validation = validate_ai_decision_response(
                    parsed,
                    provider="local",
                    task=str(context.get("task") or "manage_position_decision"),
                    symbol=str(context.get("symbol") or ""),
                    candidates=context.get("candidates"),
                )
                parsed = dict(validation.get("decision") or {})
                parsed["provider"] = "local"
                parsed["response_confirmed"] = bool(validation.get("validation_passed"))
                parsed["provider_call_attempted"] = False
                parsed["reason"] = parsed.get("reason_ko") or parsed.get("reason") or "LOCAL AI decision"
                return _with_payload_quality(parsed)
            if provider not in ("openai", "gemini"):
                return {
                    "schema": "aits_position_management_decision_v1",
                    "provider": provider,
                    "response_confirmed": False,
                    "provider_call_attempted": False,
                    "action": "wait",
                    "confidence": 0.0,
                    "reason_ko": f"지원하지 않는 AI 제공자입니다: {provider}",
                    "eta_seconds": 300,
                    "sell_ratio": 0.0,
                    "buy_amount_krw": 0.0,
                    "blocker": f"unsupported_provider:{provider}",
                    "actual_order": False,
                    "submitted": 0,
                }
            prompt = self._build_position_management_decision_prompt(context)
            if provider == "openai":
                raw = self._call_openai_position_management_decision(prompt, context)
            else:
                raw = self._call_gemini_position_management_decision(prompt, context)
            parsed = self._parse_position_management_decision_response(raw.get("content"), context)
            validation_passed = bool(parsed.get("validation_passed"))
            if not validation_passed:
                parsed["provider_validation_blocker"] = str(parsed.get("blocker") or parsed.get("validation_blocker") or "")
                parsed["blocker"] = f"{provider}_response_invalid_schema"
            parsed.update(
                {
                    "schema": "aits_position_management_decision_v1",
                    "provider": provider,
                    "response_confirmed": True,
                    "provider_call_attempted": True,
                    "response_id": str(raw.get("response_id") or ""),
                    "usage_input_tokens": raw.get("usage_input_tokens"),
                    "usage_output_tokens": raw.get("usage_output_tokens"),
                    "usage_total_tokens": raw.get("usage_total_tokens"),
                    "actual_order": False,
                    "submitted": 0,
                }
            )
            return _with_payload_quality(parsed)
        except NotImplementedError as exc:
            return {
                "schema": "aits_position_management_decision_v1",
                "provider": provider,
                "response_confirmed": False,
                "provider_call_attempted": True,
                "action": "wait",
                "confidence": 0.0,
                "reason_ko": "AI 판단이 필요하지만 제공자 호출이 차단되어 대기합니다.",
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "blocker": str(exc) or f"{provider}_position_decision_not_available",
                "actual_order": False,
                "submitted": 0,
            }
        except Exception as exc:
            return {
                "schema": "aits_position_management_decision_v1",
                "provider": provider,
                "response_confirmed": False,
                "provider_call_attempted": True,
                "action": "wait",
                "confidence": 0.0,
                "reason_ko": "AI 판단 응답을 확인하지 못해 주문을 보류합니다.",
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "blocker": str(exc)[:300] or f"{provider}_position_decision_error:{type(exc).__name__}",
                "actual_order": False,
                "submitted": 0,
            }

    def _route_local_first_decision(
        self,
        *,
        requested_provider: str,
        context: Dict[str, Any],
        feature_manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        requested_provider = requested_provider if requested_provider in {"openai", "gemini"} else "local"
        prompt = self._build_position_management_decision_prompt(context)
        manifest_summary = summarize_ai_payload_feature_manifest(feature_manifest)
        payload_hash = str(manifest_summary.get("payload_hash") or "")
        symbol_or_scope = str(context.get("symbol") or context.get("scope") or "PORTFOLIO")
        task = str(context.get("task") or "")
        local_available = False
        local_status = "provider_local_unavailable"
        local_decision: Dict[str, Any] = {
            "action": "wait",
            "confidence": 0.0,
            "reason_ko": "LOCAL 판단을 사용할 수 없어 외부 확인 또는 다음 재판단을 기다립니다.",
            "eta_seconds": 300,
            "risk_notes": "",
            "invalidation_conditions": [],
            "blocker": "provider_local_unavailable",
        }
        _safe_log_info(
            "[AITS][LocalFirstDecision] event=local_decision_started "
            f"task={task or '-'} scope={symbol_or_scope} payload_hash={payload_hash or '-'} "
            "actual_order=False submitted=0"
        )
        try:
            local_raw = self._call_local_first_decision(prompt, context)
            local_context = dict(context)
            local_context["provider"] = "local"
            local_decision = self._parse_position_management_decision_response(local_raw.get("content"), local_context)
            local_available = bool(local_decision.get("validation_passed"))
            local_status = "ready" if local_available else "provider_local_schema_mismatch"
        except NotImplementedError as exc:
            local_status = str(exc) or "provider_local_unavailable"
        except Exception as exc:
            local_status = f"provider_local_failed:{type(exc).__name__}"
        _safe_log_info(
            f"[AITS][LocalFirstDecision] event={'local_decision_recorded' if local_available else 'local_decision_unavailable'} "
            f"task={task or '-'} scope={symbol_or_scope} local_provider_status={local_status} "
            f"local_action={local_decision.get('action') or 'wait'} local_confidence={float(local_decision.get('confidence') or 0.0):.4f} "
            f"payload_hash={payload_hash or '-'} actual_order=False submitted=0"
        )

        local_model = self._evaluate_local_model_provider(
            context=context,
            manifest_summary=manifest_summary,
            local_decision=local_decision,
        )
        model_decision = dict(local_model.get("model_decision_candidate") or {})
        model_routing_decision = dict(model_decision)
        model_validation: Dict[str, Any] = {}
        if local_model.get("local_model_prediction_available") and model_decision:
            model_validation = validate_ai_decision_response(
                model_decision,
                provider="local_model",
                task=str(context.get("task") or "position_management_decision"),
                symbol=str(context.get("symbol") or ""),
                candidates=context.get("candidates"),
            )
            model_routing_decision = dict(model_validation.get("decision") or model_decision)
            local_model["local_model_decision_available"] = bool(model_validation.get("validation_passed"))
            local_model["local_model_decision_candidate_ready"] = bool(model_validation.get("validation_passed"))
            local_model["local_engine_validator_metadata"] = {
                "validator_schema": str(model_routing_decision.get("schema") or "aits_ai_decision_response_v1"),
                "validation_status": "passed" if model_validation.get("validation_passed") else "failed",
                "validation_errors": list(model_validation.get("blockers") or []),
                "normalized_action": str(model_routing_decision.get("action") or ""),
                "normalized_confidence": model_routing_decision.get("confidence"),
                "contract_warnings": [],
            }
            if not model_validation.get("validation_passed"):
                local_model["local_model_prediction_blocker"] = "local_model_candidate_validator_rejected"
        else:
            local_model["local_model_decision_available"] = False
            local_model["local_model_decision_candidate_ready"] = False
            local_model["local_engine_validator_metadata"] = {
                "validator_schema": "aits_ai_decision_response_v1",
                "validation_status": "skipped",
                "validation_errors": [str(local_model.get("local_model_prediction_blocker") or "local_model_prediction_unavailable")],
                "normalized_action": "",
                "normalized_confidence": None,
                "contract_warnings": [],
            }

        escalation = self._evaluate_external_escalation(
            requested_provider=requested_provider,
            local_decision=local_decision,
            local_available=local_available,
            feature_manifest=feature_manifest,
            context=context,
            local_model=local_model,
        )
        external_provider = str(escalation.get("escalation_target_provider") or "")
        if not local_available and escalation.get("escalation_required") and external_provider:
            _safe_log_info(
                "[AITS][LocalFirstDecision] event=local_first_external_fallback_allowed "
                f"task={task or '-'} scope={symbol_or_scope} provider={external_provider} "
                f"blocker={local_status or '-'} elapsed_ms=0 actual_order=False submitted=0"
            )
        external_decision: Dict[str, Any] = {}
        external_called = False
        external_blocker = str(escalation.get("escalation_blocker") or "")
        cost_guard_passed = False
        cost_guard: Dict[str, Any] = {}
        if escalation.get("escalation_required") and external_provider:
            cost_guard = self._provider_cost_guard_policy(
                provider=external_provider,
                context=context,
                payload_hash=payload_hash,
                reserve=False,
            )
            cost_guard_passed = bool(cost_guard.get("allowed"))
            if cost_guard_passed:
                try:
                    external_called = True
                    raw = (
                        self._call_openai_position_management_decision(prompt, context)
                        if external_provider == "openai"
                        else self._call_gemini_position_management_decision(prompt, context)
                    )
                    external_context = dict(context)
                    external_context["provider"] = external_provider
                    external_decision = self._parse_position_management_decision_response(raw.get("content"), external_context)
                    external_decision.update(
                        {
                            "response_id": str(raw.get("response_id") or ""),
                            "usage_input_tokens": raw.get("usage_input_tokens"),
                            "usage_output_tokens": raw.get("usage_output_tokens"),
                            "usage_total_tokens": raw.get("usage_total_tokens"),
                        }
                    )
                    if not bool(external_decision.get("validation_passed")):
                        external_blocker = f"{external_provider}_response_invalid_schema"
                except NotImplementedError as exc:
                    external_blocker = str(exc) or f"{external_provider}_unavailable"
                except Exception as exc:
                    external_blocker = f"{external_provider}_call_failed:{type(exc).__name__}"
            else:
                external_blocker = str(cost_guard.get("blocker") or "provider_cost_guard_blocked")

        external_valid = bool(external_decision.get("validation_passed")) and not external_blocker
        local_action = str(local_decision.get("action") or "wait").lower()
        model_action = str(local_model.get("model_recommended_action") or "").lower()
        model_available = bool(local_model.get("local_model_decision_available"))
        authority_metadata = AITSLocalEngineAuthorityManager().router_metadata(
            task_key=_local_engine_authority_task_key(task, model_action),
            action=model_action,
        )
        model_live_allowed = bool(
            local_model.get("local_model_live_allowed")
            and authority_metadata.get("local_final_allowed")
        )
        model_safe_action = model_action in _LOCAL_SAFE_ACTIONS
        model_confidence = float(local_model.get("model_confidence") or 0.0)
        local_model_agrees_with_local = bool(model_available and model_action == local_action)
        if external_valid:
            final_decision = dict(external_decision)
            final_provider_source = external_provider
            source_reason = "external_provider_validated_after_local_first"
        elif (
            model_available
            and model_live_allowed
            and model_safe_action
            and (not local_available or local_model_agrees_with_local or model_confidence >= float(local_decision.get("confidence") or 0.0))
        ):
            final_decision = dict(model_routing_decision)
            final_provider_source = "local_model"
            source_reason = "registry_approved_local_model_safe_decision"
            _safe_log_info(
                "[AITS][LocalModelProvider] event=provider_candidate_created "
                f"task={task or '-'} scope={symbol_or_scope} model_action={model_action} "
                f"model_confidence={model_confidence:.4f} actual_order=False submitted=0"
            )
        elif local_available and local_action in _LOCAL_SAFE_ACTIONS:
            final_decision = dict(local_decision)
            final_provider_source = "local"
            source_reason = "local_decision_retained"
        else:
            final_decision = dict(local_decision)
            safety_blocker = external_blocker or escalation.get("escalation_blocker") or "local_order_action_requires_external_confirmation"
            final_decision.update(
                {
                    "action": "wait",
                    "confidence": min(0.49, float(local_decision.get("confidence") or 0.0)),
                    "reason_ko": "LOCAL 주문성 판단은 외부 확인 전까지 실행하지 않습니다.",
                    "sell_ratio": 0.0,
                    "buy_amount_krw": 0.0,
                    "rotate_to_symbol": "",
                    "replace_symbol": "",
                    "execution_plan": {},
                    "risk_notes": str(local_decision.get("risk_notes") or "external confirmation required"),
                    "invalidation_conditions": local_decision.get("invalidation_conditions") or [],
                    "blocker": safety_blocker,
                }
            )
            safety_validation = validate_ai_decision_response(
                final_decision,
                provider="local",
                task=str(context.get("task") or "position_management_decision"),
                symbol=str(context.get("symbol") or ""),
                candidates=context.get("candidates"),
            )
            final_decision = dict(safety_validation.get("decision") or final_decision)
            final_decision["blocker"] = safety_blocker
            final_provider_source = "local_safety_hold"
            source_reason = "local_order_action_blocked_without_external_confirmation"

        final_decision.update(
            {
                "schema": "aits_position_management_decision_v1",
                "provider": final_provider_source,
                "response_confirmed": bool(final_decision.get("validation_passed")),
                "provider_call_attempted": True,
                "local_decision_attempted": True,
                "local_decision_available": local_available,
                "local_provider_status": local_status,
                "local_action": local_action,
                "local_confidence": float(local_decision.get("confidence") or 0.0),
                "local_reason_ko": str(local_decision.get("reason_ko") or ""),
                "local_eta_seconds": int(local_decision.get("eta_seconds") or 300),
                "local_risk_notes": str(local_decision.get("risk_notes") or ""),
                "local_invalidation_conditions": local_decision.get("invalidation_conditions") or [],
                "local_decision_quality": str(manifest_summary.get("payload_quality_grade") or "F"),
                "local_blockers": [local_status] if not local_available else [],
                "local_payload_hash": payload_hash,
                "local_generated_at": int(time.time()),
                **local_model,
                **escalation,
                "local_decision_retained": final_provider_source.startswith("local"),
                "external_provider_requested": bool(external_provider),
                "external_provider_called": external_called,
                "external_provider_blocked": bool(external_provider and not external_valid),
                "external_provider_name": external_provider,
                "external_blocker": external_blocker,
                "external_action": str(external_decision.get("action") or ""),
                "external_confidence": float(external_decision.get("confidence") or 0.0),
                "cost_guard_passed": cost_guard_passed,
                "cost_guard_blocker": str(cost_guard.get("blocker") or external_blocker or ""),
                "final_provider_source": final_provider_source,
                "final_action": str(final_decision.get("action") or "wait"),
                "final_confidence": float(final_decision.get("confidence") or 0.0),
                "final_reason_ko": str(final_decision.get("reason_ko") or ""),
                "final_decision_source_reason": source_reason,
                "local_model_action": model_action,
                "local_model_confidence": model_confidence,
                "local_model_risk_score": local_model.get("model_risk_score"),
                "local_model_agrees_with_local": local_model_agrees_with_local,
                "local_model_agrees_with_external": bool(model_available and external_valid and model_action == str(external_decision.get("action") or "").lower()),
                "local_model_changed_final_decision": final_provider_source == "local_model" and model_action != local_action,
                "local_model_used_for_final": final_provider_source == "local_model",
                "local_model_prediction_vs_local": "agree" if local_model_agrees_with_local else ("disagree" if model_available else "unavailable"),
                "local_model_prediction_vs_external": "agree" if model_available and external_valid and model_action == str(external_decision.get("action") or "").lower() else ("disagree" if model_available and external_valid else "not_compared"),
                "local_model_prediction_vs_final": "agree" if model_available and model_action == str(final_decision.get("action") or "").lower() else ("disagree" if model_available else "unavailable"),
                "local_model_prediction_outcome_pending": bool(model_available),
                "local_model_not_used_reason": "" if final_provider_source == "local_model" else str(local_model.get("local_model_prediction_blocker") or ("external_provider_selected" if external_valid else "existing_local_decision_retained")),
                "local_model_live_blocker": str(local_model.get("local_model_prediction_blocker") or ""),
                "local_engine_authority": authority_metadata,
                "local_engine_global_level": int(authority_metadata.get("global_level") or 0),
                "local_engine_task_level": int(authority_metadata.get("task_level") or 0),
                "local_engine_effective_level": int(authority_metadata.get("effective_level") or 0),
                "local_engine_authority_state": str(authority_metadata.get("authority_state") or "external_only"),
                "local_engine_local_final_allowed": bool(authority_metadata.get("local_final_allowed")),
                "local_engine_external_confirmation_required": bool(authority_metadata.get("external_confirmation_required", True)),
                "validator_applied_to_external_response": bool(external_called),
                "local_only_order_action_blocked_without_external_confirmation": source_reason == "local_order_action_blocked_without_external_confirmation",
                "actual_order": False,
                "submitted": 0,
            }
        )
        final_action_before_observation = str(final_decision.get("action") or "wait")
        observation_status = "skipped"
        observation_blocker = str(local_model.get("local_model_prediction_blocker") or "local_model_prediction_unavailable")
        observation_error = ""
        writer_attempted = bool(model_available and model_decision)
        writer_success = False
        prediction_id = ""
        outcome_linkage_key = ""
        if writer_attempted:
            try:
                observation = record_local_engine_candidate_observation(
                    candidate=model_decision,
                    model_state=local_model,
                    context=context,
                    manifest_summary=manifest_summary,
                    final_decision=final_decision,
                    cost_guard=cost_guard,
                )
                prediction_id = str(observation.get("prediction_id") or "")
                outcome_linkage_key = str(observation.get("outcome_linkage_key") or "")
                observation_status = "recorded"
                observation_blocker = ""
                writer_success = True
            except LocalEngineCandidateObservationError as exc:
                observation_status = exc.status
                observation_blocker = exc.blocker
                observation_error = exc.error
            except Exception as exc:
                observation_status = "failed"
                observation_blocker = "writer_exception"
                observation_error = type(exc).__name__
        final_decision.update(
            {
                "local_engine_candidate_observation_schema": "aits_local_engine_candidate_observation.v1",
                "local_engine_candidate_observation_status": observation_status,
                "local_engine_candidate_observation_blocker": observation_blocker,
                "local_engine_observation_status": observation_status,
                "local_engine_observation_blocker": observation_blocker,
                "local_engine_observation_error": observation_error,
                "local_engine_candidate_schema": str(model_decision.get("schema") or LOCAL_ENGINE_DECISION_SCHEMA),
                "local_engine_candidate_writer_contract": LOCAL_ENGINE_OBSERVATION_WRITER_CONTRACT,
                "local_engine_candidate_writer_attempted": writer_attempted,
                "local_engine_candidate_writer_success": writer_success,
                "local_engine_validator_metadata": dict(local_model.get("local_engine_validator_metadata") or {}),
                "local_engine_prediction_id": prediction_id,
                "local_engine_candidate_observation_ids": [prediction_id] if prediction_id else [],
                "local_engine_outcome_linkage_key": outcome_linkage_key,
                "local_engine_candidate_only": True,
                "local_engine_applied_to_final_action": False,
                "local_engine_final_action_unchanged": str(final_decision.get("action") or "wait") == final_action_before_observation,
            }
        )
        supported_tasks = set((local_model.get("local_model_metadata") or {}).get("supported_tasks") or [])
        source_task = str(context.get("task") or "")
        model_task = str(local_model.get("local_model_task") or source_task)
        coverage_record = {
            "decision_id": str(final_decision.get("decision_id") or final_decision.get("response_id") or payload_hash),
            "payload_hash": payload_hash,
            "task": source_task,
            "source_task": source_task,
            "model_task": model_task,
            "scope": str(context.get("symbol") or context.get("scope") or "PORTFOLIO"),
            "symbol": str(context.get("symbol") or ""),
            "local_candidate_eligible": bool(local_model.get("local_model_loaded") and model_task in supported_tasks),
            "local_candidate_attempted": bool(local_model.get("local_model_prediction_attempted")),
            "local_candidate_available": model_available,
            "local_candidate_recorded": writer_success,
            "candidate_blocker": observation_blocker,
            "feature_contract": str(local_model.get("local_model_feature_quality_grade") or manifest_summary.get("payload_quality_grade") or ""),
            "missing_features": sorted(set(
                list(manifest_summary.get("critical_missing_features") or [])
                + list(local_model.get("local_model_missing_features") or [])
            )),
            "model_supported_task": model_task in supported_tasks,
            "model_supported_actions": list((local_model.get("local_model_metadata") or {}).get("supported_actions") or []),
            "teacher_present": bool(external_valid and external_provider in {"openai", "gemini"}),
            "teacher_provider": external_provider if external_valid else None,
            "teacher_action": str(external_decision.get("action") or "").lower() if external_valid else None,
            "teacher_absent_reason": "" if external_valid else str(cost_guard.get("blocker") or external_blocker or "external_not_required"),
            "final_provider_source": final_provider_source,
            "final_action": str(final_decision.get("action") or "wait").lower(),
            "prediction_id": prediction_id,
            "outcome_linkage_key": outcome_linkage_key,
            "outcome_linkage_ready": bool(prediction_id or outcome_linkage_key),
            "candidate_only": True,
            "applied_to_final_action": False,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
            "fake_candidate": False,
        }
        try:
            coverage = AITSLocalEngineTaskCoverage().append(coverage_record)
            final_decision["local_engine_task_coverage_id"] = str(coverage.get("coverage_id") or "")
            final_decision["local_engine_task_coverage_recorded"] = True
        except Exception as exc:
            final_decision["local_engine_task_coverage_id"] = ""
            final_decision["local_engine_task_coverage_recorded"] = False
            final_decision["local_engine_task_coverage_blocker"] = type(exc).__name__
        _safe_log_info(
            "[AITS][ProviderDecisionRouter] event=final_decision_selected "
            f"task={task or '-'} scope={symbol_or_scope} final_provider_source={final_provider_source} "
            f"local_action={local_action} external_provider_called={str(external_called).lower()} "
            f"external_provider_blocked={str(bool(external_provider and not external_valid)).lower()} "
            f"external_action={external_decision.get('action') or '-'} final_action={final_decision.get('action') or 'wait'} "
            f"local_model_action={model_action or '-'} local_model_used_for_final={str(final_provider_source == 'local_model').lower()} "
            f"local_model_not_used_reason={final_decision.get('local_model_not_used_reason') or '-'} "
            f"source_reason={source_reason} blocker={final_decision.get('blocker') or '-'} "
            "actual_order=False submitted=0"
        )
        return final_decision

    def _build_position_management_decision_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        safe_context = dict(context or {})
        if str(safe_context.get("task") or "").strip() == "ai_redecision":
            return (
                "You are the AITS final AI authority re-evaluating a prior scenario.\n"
                "ETA expiry or invalidation is a request for judgment, never a direct trade action.\n"
                "Compare prior_decision, current_state, and delta_since_prior_decision.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, sell_ratio, buy_amount_krw, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
                "Allowed action values: hold, wait, sell, reduce, add, buy, rotate, stop_loss, take_profit.\n"
                "Each invalidation condition should be an object with condition_type, feature, operator, threshold, current_value, expected_direction, and reason_ko.\n"
                "If evidence is incomplete, choose wait or hold with a new ETA and explicit invalidation conditions.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        if str(safe_context.get("task") or "").strip() == "rotation_decision":
            return (
                "You are the AITS final AI decision authority for managed-pool rotation.\n"
                "BASIC has collected rotation score evidence only. normalized_rotation_score is a trigger, not action.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, replace_symbol, rotate_to_symbol, sell_ratio, buy_amount_krw, risk_notes, invalidation_conditions.\n"
                "Allowed action values: rotate, wait, hold, replace, reduce_and_rotate, reject.\n"
                "Each invalidation condition should be a structured object with condition_type, feature, operator, threshold, current_value, expected_direction, and reason_ko.\n"
                "Protected, user-added, live holding, or external holding rows must not be removed by simple replacement.\n"
                "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        if str(safe_context.get("task") or "").strip() == "managed_pool_promotion_decision":
            return (
                "You are the AITS final AI decision authority for managed-pool promotion.\n"
                "BASIC has collected candidate and portfolio data only. Decide whether the candidate should enter the Managed Pool.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, replace_symbol, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
                "Allowed action values: promote, reject, wait, replace, rotate_review, hold.\n"
                "Each invalidation condition should be a structured object with condition_type, feature, operator, threshold, current_value, expected_direction, and reason_ko.\n"
                "Do not decide from scanner score alone. Use market context, current pool, holdings protection, cap, and alternatives together.\n"
                "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        return (
            "You are the AITS final AI decision authority for live position management.\n"
            "BASIC has collected data only. Decide action; do not claim execution.\n"
            "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
            "sell_ratio, buy_amount_krw, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
            "Allowed action values: hold, wait, sell, reduce, add, buy, rotate, stop_loss, take_profit.\n"
            "Each invalidation condition should be a structured object with condition_type, feature, operator, threshold, current_value, expected_direction, and reason_ko.\n"
            "Use pnl, RSI, MACD, volume, volatility, portfolio cap, alternatives, and risk context together; "
            "do not decide from pnl threshold alone.\n"
            "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
            "Context JSON:\n"
            + json.dumps(safe_context, ensure_ascii=False, default=str)
        )

    def _call_openai_position_management_decision(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        task = str(context.get("task") or "").strip()
        symbol = str(context.get("symbol") or "PORTFOLIO").strip().upper()
        payload_hash = hashlib.sha256(
            json.dumps(context, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:24]
        runtime_policy = self._runtime_decision_call_policy(
            provider="openai", context=context, payload_hash=payload_hash
        )
        current_policy = context.get("current_policy") if isinstance(context.get("current_policy"), dict) else {}
        runtime_context = context.get("runtime_context") if isinstance(context.get("runtime_context"), dict) else {}
        if "runtime_contract_active" in runtime_context:
            runtime_active = runtime_context.get("runtime_contract_active")
        elif "runtime_contract_active" in context:
            runtime_active = context.get("runtime_contract_active")
        else:
            runtime_active = None
        execution_mode = str(runtime_context.get("execution_mode") or current_policy.get("execution_mode") or "").strip()
        session_id = str(runtime_context.get("session_id") or context.get("session_id") or "").strip()
        context_source = str(
            runtime_context.get("context_source")
            or ("legacy_request_metadata" if runtime_context else "unknown")
        ).strip()
        runtime_active_text = "unknown" if runtime_active is None else str(bool(runtime_active)).lower()
        context_complete = runtime_active is not None and bool(execution_mode) and bool(session_id)
        _safe_log_info(
            f"[AITS][ProviderRuntimeContext] event={'context_collected' if context_complete else 'context_missing'} "
            f"provider=openai task={task or '-'} scope={symbol or '-'} "
            f"runtime_contract_active={runtime_active_text} execution_mode={execution_mode or 'unknown'} "
            f"session_id={session_id or 'unknown'} context_source={context_source or 'unknown'} "
            f"mismatch=unknown blocker={'-' if context_complete else 'provider_runtime_context_metadata_missing'} "
            "actual_order=False submitted=0"
        )
        log_fields = (
            f"provider=openai task={task or '-'} symbol={symbol or '-'} payload_hash={payload_hash} "
            f"model={runtime_policy.get('model') or '-'} key_masked={str(bool(runtime_policy.get('key_masked'))).lower()} "
            f"runtime_contract_active={runtime_active_text} "
            f"execution_mode={execution_mode or 'unknown'} session_id={session_id or 'unknown'} "
            f"context_source={context_source or 'unknown'} "
            f"cost_guard_result={runtime_policy.get('cost_guard_result') or '-'}"
        )
        _safe_log_info(
            f"[AITS][AIEngineProvider] event=runtime_decision_call_requested {log_fields} blocker=- reason=management_decision_requested actual_order=False submitted=0"
        )
        if not runtime_policy.get("allowed"):
            blocker = str(runtime_policy.get("blocker") or "openai_runtime_decision_call_disabled_by_policy")
            _safe_log_info(
                f"[AITS][AIEngineProvider] event=runtime_decision_call_blocked {log_fields} blocker={blocker} reason={runtime_policy.get('reason') or '-'} actual_order=False submitted=0"
            )
            raise NotImplementedError(blocker)
        _safe_log_info(
            f"[AITS][AIEngineProvider] event=runtime_decision_call_allowed {log_fields} blocker=- reason=provider_policy_passed actual_order=False submitted=0"
        )
        _safe_log_info(
            f"[AITS][AIEngineProvider] event=api_call_entry {log_fields} blocker=- reason=runtime_management_decision actual_order=False submitted=0"
        )
        _RUNTIME_DECISION_CALL_TIMES.append(float(runtime_policy.get("now") or time.time()))
        _RUNTIME_DECISION_PAYLOAD_LAST_CALL[payload_hash] = float(runtime_policy.get("now") or time.time())
        api_key = str(runtime_policy.get("api_key") or "")
        model = str(runtime_policy.get("model") or "")
        payload = {
            "model": model,
            "temperature": 0.1,
            "max_tokens": 420,
            "messages": [
                {"role": "system", "content": "Return only JSON. You are an AI portfolio decision engine. Do not execute trades."},
                {"role": "user", "content": prompt},
            ],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            _safe_log_info(
                f"[AITS][AIEngineProvider] event=runtime_decision_response_missing {log_fields} blocker=openai_network_unavailable reason={type(exc).__name__} actual_order=False submitted=0"
            )
            raise NotImplementedError("openai_network_unavailable") from exc
        usage = data.get("usage") or {}
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not str(content or "").strip():
            _safe_log_info(
                f"[AITS][AIEngineProvider] event=runtime_decision_response_missing {log_fields} blocker=openai_response_missing reason=empty_provider_content actual_order=False submitted=0"
            )
            raise NotImplementedError("openai_response_missing")
        _safe_log_info(
            f"[AITS][AIEngineProvider] event=runtime_decision_response_received {log_fields} blocker=- reason=response_confirmed actual_order=False submitted=0"
        )
        return {
            "content": content,
            "response_id": data.get("id") or "",
            "usage_input_tokens": usage.get("prompt_tokens"),
            "usage_output_tokens": usage.get("completion_tokens"),
            "usage_total_tokens": usage.get("total_tokens"),
        }

    def _call_gemini_position_management_decision(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        payload_hash = hashlib.sha256(
            json.dumps(context, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:24]
        runtime_policy = self._runtime_decision_call_policy(
            provider="gemini", context=context, payload_hash=payload_hash
        )
        if not runtime_policy.get("allowed"):
            raise NotImplementedError(str(runtime_policy.get("blocker") or "gemini_cost_guard_blocked"))
        api_key = str(runtime_policy.get("api_key") or "")
        model = str(runtime_policy.get("model") or "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 420},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = ((candidates[0].get("content") or {}).get("parts") or [])
            content = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        usage = data.get("usageMetadata") or {}
        return {
            "content": content,
            "response_id": str(data.get("responseId") or ""),
            "usage_input_tokens": usage.get("promptTokenCount"),
            "usage_output_tokens": usage.get("candidatesTokenCount"),
            "usage_total_tokens": usage.get("totalTokenCount"),
        }

    def _parse_position_management_decision_response(self, raw_response: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = dict(context or {})
        text = str(raw_response or "").strip()
        parsed: Dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(text[start:end + 1])
                    except Exception:
                        parsed = {}
        allowed = AI_DECISION_ALLOWED_ACTIONS
        action = str(parsed.get("action") or parsed.get("decision") or "").strip().lower()
        if action not in allowed:
            action = "wait"
        try:
            confidence = float(parsed.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        try:
            eta_seconds = int(float(parsed.get("eta_seconds") or 300))
        except Exception:
            eta_seconds = 300
        try:
            sell_ratio = float(parsed.get("sell_ratio") or 0.0)
        except Exception:
            sell_ratio = 0.0
        sell_ratio = max(0.0, min(1.0, sell_ratio))
        try:
            buy_amount_krw = float(parsed.get("buy_amount_krw") or 0.0)
        except Exception:
            buy_amount_krw = 0.0
        reason_ko = str(parsed.get("reason_ko") or parsed.get("reason") or "").strip()
        if not reason_ko:
            reason_ko = "AI 판단 근거가 비어 있어 실행하지 않고 대기합니다."
            action = "wait"
        raw_decision = {
            "action": action,
            "confidence": confidence,
            "reason_ko": reason_ko[:800],
            "eta_seconds": eta_seconds,
            "sell_ratio": sell_ratio,
            "buy_amount_krw": max(0.0, buy_amount_krw),
            "rotate_to_symbol": str(parsed.get("rotate_to_symbol") or "").strip().upper(),
            "replace_symbol": str(parsed.get("replace_symbol") or parsed.get("replace_target_symbol") or "").strip().upper(),
            "execution_plan": parsed.get("execution_plan") if isinstance(parsed.get("execution_plan"), dict) else {},
            "risk_notes": str(parsed.get("risk_notes") or "")[:800],
            "invalidation_conditions": parsed.get("invalidation_conditions") or [],
            "blocker": "",
        }
        validation = validate_ai_decision_response(
            raw_decision,
            provider=str(context.get("provider") or ""),
            task=str(context.get("task") or "manage_position_decision"),
            symbol=str(context.get("symbol") or ""),
            candidates=context.get("candidates"),
        )
        return dict(validation.get("decision") or raw_decision)

    def _build_local_position_management_decision(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        context = dict(context or {})
        symbol = str(context.get("symbol") or "").strip().upper()
        task = str(context.get("task") or "").strip()
        if task == "rotation_decision":
            rotation_candidate = context.get("rotation_candidate") if isinstance(context.get("rotation_candidate"), dict) else {}
            old_position = context.get("old_position") if isinstance(context.get("old_position"), dict) else {}
            new_candidate = context.get("new_candidate") if isinstance(context.get("new_candidate"), dict) else {}
            old_symbol = str(rotation_candidate.get("old_symbol") or old_position.get("symbol") or symbol or "").strip().upper()
            new_symbol = str(rotation_candidate.get("new_symbol") or new_candidate.get("symbol") or "").strip().upper()
            gap = _clamp_float(rotation_candidate.get("score_gap"), lo=-100.0, hi=100.0, default=0.0)
            new_score = _clamp_float(
                rotation_candidate.get("new_score") or new_candidate.get("scanner_score") or new_candidate.get("basic_score"),
                lo=0.0,
                hi=100.0,
                default=0.0,
            )
            source_type = str(old_position.get("source_type") or "").strip()
            old_protected = bool(old_position.get("protected") or old_position.get("managed_protected"))
            old_holding = bool(old_position.get("holding"))
            execution_plan: Dict[str, Any] = {
                "replace_symbol": old_symbol,
                "rotate_to_symbol": new_symbol,
                "rotation_execution": False,
                "execution_pending": False,
            }
            action = "wait"
            confidence = 0.52
            reason = "로테이션 후보는 추가 관찰 후 다시 판단합니다."
            if old_holding or old_protected or source_type in {"user_added", "live_holding", "external_holding"}:
                action = "wait"
                confidence = 0.62
                execution_plan["replace_symbol"] = ""
                reason = "보유/보호 종목은 단순 로테이션 교체 대상에서 제외합니다."
            elif old_symbol and new_symbol and gap >= 8.0 and new_score >= 65.0:
                action = "replace"
                confidence = min(0.90, 0.64 + min(gap, 25.0) / 100.0)
                reason = f"{new_symbol} 후보가 {old_symbol}보다 우위라 관리종목 교체 검토를 승인합니다."
            elif old_symbol and new_symbol and gap >= 5.0:
                action = "wait"
                confidence = 0.57
                reason = f"{new_symbol} 후보가 우위지만 교체 확정 전 추가 관찰이 필요합니다."
            else:
                action = "reject"
                confidence = 0.60
                execution_plan["replace_symbol"] = ""
                reason = "로테이션 점수 격차가 충분하지 않아 교체하지 않습니다."
            return {
                "schema": "aits_position_management_decision_v1",
                "task": task,
                "provider": "local",
                "action": action,
                "confidence": round(float(confidence), 4),
                "reason_ko": reason,
                "eta_seconds": 600,
                "execution_plan": execution_plan,
                "replace_symbol": execution_plan.get("replace_symbol", ""),
                "rotate_to_symbol": execution_plan.get("rotate_to_symbol", ""),
                "sell_ratio": _clamp_float(execution_plan.get("sell_ratio"), lo=0.0, hi=1.0, default=0.0),
                "buy_amount_krw": 0.0,
                "risk_notes": "LOCAL rotation gate decision; no order submit in this stage.",
                "invalidation_conditions": [
                    "rotation_score_gap_reverses",
                    "protected_or_holding_status_changes",
                    "market_data_stale",
                ],
                "actual_order": False,
                "submitted": 0,
            }
        if task == "managed_pool_promotion_decision":
            candidate = context.get("candidate") if isinstance(context.get("candidate"), dict) else {}
            constraints = context.get("constraints") if isinstance(context.get("constraints"), dict) else {}
            comparison = context.get("comparison") if isinstance(context.get("comparison"), dict) else {}
            symbol = str(candidate.get("symbol") or symbol or "").strip().upper()
            score = _clamp_float(
                candidate.get("scanner_score") or candidate.get("basic_score"),
                lo=0.0,
                hi=100.0,
                default=0.0,
            )
            trade_value = _clamp_float(candidate.get("trade_value"), lo=0.0, hi=10**15, default=0.0)
            current_count = int(_clamp_float((context.get("current_managed_pool") or {}).get("count"), 0.0))
            max_count = int(_clamp_float((context.get("current_managed_pool") or {}).get("max_count"), 0.0))
            has_free_slot = max_count <= 0 or current_count < max_count
            replace_symbol = str(comparison.get("weakest_non_holding_symbol") or "").strip().upper()
            action = "wait"
            confidence = 0.48
            execution_plan: Dict[str, Any] = {}
            reason = f"{symbol or '候補'} 관리종목 편입은 추가 시장 확인을 기다립니다."
            if score >= 70.0 and (trade_value > 0.0 or candidate.get("market_reason")):
                if has_free_slot:
                    action = "promote"
                    confidence = 0.66
                    reason = f"{symbol} 후보는 점수와 시장 근거가 충분해 관리종목 편입을 승인합니다."
                elif replace_symbol:
                    action = "replace"
                    confidence = 0.61
                    execution_plan["replace_symbol"] = replace_symbol
                    reason = f"{symbol} 후보는 기존 비보유 관리종목보다 우위라 교체 검토를 승인합니다."
                else:
                    reason = f"{symbol} 후보는 매력적이지만 최대 관리종목수 여유가 없어 대기합니다."
            elif score < 60.0:
                action = "reject"
                confidence = 0.58
                reason = f"{symbol} 후보는 현재 점수와 시장 근거가 부족해 편입하지 않습니다."
            return {
                "schema": "aits_position_management_decision_v1",
                "action": action,
                "confidence": confidence,
                "reason_ko": reason,
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "rotate_to_symbol": "",
                "replace_symbol": execution_plan.get("replace_symbol", ""),
                "execution_plan": execution_plan,
                "risk_notes": "LOCAL AI promotion decision; Basic candidate score is trigger data only.",
                "invalidation_conditions": [],
                "blocker": "",
                "actual_order": False,
                "submitted": 0,
            }
        if task == "ai_redecision":
            current_state = context.get("current_state") if isinstance(context.get("current_state"), dict) else {}
            context = dict(context)
            context["position"] = current_state.get("position") if isinstance(current_state.get("position"), dict) else {}
            context["market"] = current_state.get("market") if isinstance(current_state.get("market"), dict) else {}
            context["indicators"] = current_state.get("indicators") if isinstance(current_state.get("indicators"), dict) else {}
            context["portfolio"] = current_state.get("portfolio") if isinstance(current_state.get("portfolio"), dict) else {}
            context["requested_decision"] = {
                "trigger": str(context.get("trigger_reason") or "ai_redecision"),
                "allowed_actions": list((context.get("requested_decision") or {}).get("allowed_actions") or []),
            }
        trigger = str((context.get("requested_decision") or {}).get("trigger") or context.get("trigger") or "").strip()
        position = context.get("position") if isinstance(context.get("position"), dict) else {}
        market = context.get("market") if isinstance(context.get("market"), dict) else {}
        indicators = context.get("indicators") if isinstance(context.get("indicators"), dict) else {}
        pnl_pct = _clamp_float(position.get("pnl_pct"), lo=-1000.0, hi=1000.0, default=0.0)
        rsi = _clamp_float(indicators.get("RSI") or indicators.get("rsi"), lo=0.0, hi=100.0, default=0.0)
        trend_strength = _clamp_float(indicators.get("trend_strength"), lo=-100.0, hi=100.0, default=0.0)
        volume_change = _clamp_float(market.get("volume_change"), lo=-1000.0, hi=1000.0, default=0.0)
        action = "wait"
        confidence = 0.45
        eta_seconds = 600
        reason = (
            f"{symbol or '보유종목'}은 {trigger or '관리'} 조건으로 AI 판단이 요청됐지만, "
            "LOCAL AI는 추가 시장 확증을 기다리도록 판단했습니다."
        )
        if trigger in {"take_profit", "strong_take_profit"} and rsi >= 70.0 and volume_change < 0.0 and trend_strength < 0.0:
            action = "reduce"
            confidence = 0.62
            eta_seconds = 0
            reason = f"{symbol} 수익 구간에서 RSI 과열, 거래량 둔화, 추세 약화가 함께 보여 일부 익절이 적절합니다."
        elif trigger in {"stop_loss", "emergency_stop_loss"} and trend_strength < -30.0:
            action = "stop_loss"
            confidence = 0.64 if pnl_pct <= -20.0 else 0.58
            eta_seconds = 0
            reason = f"{symbol} 손실 구간에서 하락 추세가 강해 손절 검토가 필요합니다."
        return {
            "schema": "aits_position_management_decision_v1",
            "action": action,
            "confidence": confidence,
            "reason_ko": reason,
            "eta_seconds": eta_seconds,
            "sell_ratio": 1.0 if trigger == "emergency_stop_loss" and action == "stop_loss" else (0.5 if action in {"reduce", "sell", "stop_loss", "take_profit"} else 0.0),
            "buy_amount_krw": 0.0,
            "rotate_to_symbol": "",
            "execution_plan": {},
            "risk_notes": "LOCAL AI decision; no direct threshold execution.",
            "invalidation_conditions": [],
            "blocker": "",
            "actual_order": False,
            "submitted": 0,
        }

    def _build_managed_pool_opinion_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        context = dict(context or {})
        safe_context = {
            "schema": context.get("schema") or "managed_pool_ai_opinion_request_v1",
            "symbol": context.get("symbol"),
            "display_name": context.get("display_name"),
            "aits_score": context.get("aits_score"),
            "status": context.get("status"),
            "status_reason": context.get("status_reason"),
            "managed_source": context.get("managed_source"),
            "candidate_reason": context.get("candidate_reason"),
            "recent_move": context.get("recent_move"),
            "safety_constraints": context.get("safety_constraints"),
        }
        return (
            "You are generating an AITS Managed Pool operation opinion for display only.\n"
            "This is NOT router verification and NOT an order approval request.\n"
            "Never ask to buy, sell, cancel, retry, or execute an order.\n"
            "Return only compact JSON with keys: opinion, status_label, confidence, reason, next_action.\n"
            "Allowed opinion values: watch, buy_wait, rotate_review, sell_review, data_insufficient.\n"
            "Allowed Korean status_label values: 관망, 매수대기, 교체검토, 매도검토, 데이터부족.\n"
            "The reason must be user-facing market/managed-pool rationale, not an execution-block reason.\n"
            "The next_action must be review-only and must include no order execution.\n"
            "Context JSON:\n"
            + json.dumps(safe_context, ensure_ascii=False, default=str)
        )

    def _call_openai_managed_pool_opinion(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("openai_live_call_disabled")
        api_key = self._get_config_api_key("openai")
        if not api_key:
            raise NotImplementedError("openai_api_key_missing")
        model = os.getenv("AITS_OPENAI_OPINION_MODEL", os.getenv("AITS_OPENAI_VERIFY_MODEL", "gpt-4o-mini"))
        payload = {
            "model": model,
            "temperature": 0.2,
            "max_tokens": 260,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON. You write Korean Managed Pool review opinions. Never execute trades.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            _safe_log_info("[AITS][ManagedPoolOpinionOpenAI] step=before_request")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage") or {}
            return {
                "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "response_id": data.get("id") or "",
                "usage_input_tokens": usage.get("prompt_tokens"),
                "usage_output_tokens": usage.get("completion_tokens"),
                "usage_total_tokens": usage.get("total_tokens"),
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800].lower()
            if exc.code == 429 or "quota" in body or "rate limit" in body or "insufficient_quota" in body:
                raise RuntimeError("openai_quota_exceeded")
            if exc.code in (401, 403) or "invalid api key" in body or "incorrect api key" in body:
                raise RuntimeError("openai_api_key_invalid")
            if exc.code == 400:
                raise RuntimeError("openai_bad_request")
            raise

    def _call_gemini_managed_pool_opinion(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("gemini_live_call_disabled")
        api_key = self._get_config_api_key("gemini")
        if not api_key:
            raise NotImplementedError("gemini_api_key_missing")
        model = os.getenv("AITS_GEMINI_OPINION_MODEL", os.getenv("AITS_GEMINI_VERIFY_MODEL", "gemini-1.5-flash"))
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 260},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            _safe_log_info("[AITS][ManagedPoolOpinionGemini] step=before_request")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = ""
            candidates = data.get("candidates") or []
            if candidates:
                parts = ((candidates[0].get("content") or {}).get("parts") or [])
                content = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
            usage = data.get("usageMetadata") or {}
            return {
                "content": content,
                "response_id": str(data.get("responseId") or ""),
                "usage_input_tokens": usage.get("promptTokenCount"),
                "usage_output_tokens": usage.get("candidatesTokenCount"),
                "usage_total_tokens": usage.get("totalTokenCount"),
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800].lower()
            if exc.code == 429 or "quota" in body or "rate limit" in body:
                raise RuntimeError("gemini_quota_exceeded")
            if exc.code in (401, 403) or "api key not valid" in body or "invalid api key" in body:
                raise RuntimeError("gemini_api_key_invalid")
            if exc.code == 400:
                raise RuntimeError("gemini_bad_request")
            raise

    def _parse_managed_pool_opinion_response(self, raw_response: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        text = str(raw_response or "").strip()
        parsed: Dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(text[start:end + 1])
                    except Exception:
                        parsed = {}
        opinion_raw = str(parsed.get("opinion") or parsed.get("recommendation") or parsed.get("status") or "").strip().lower()
        status_raw = str(parsed.get("status_label") or "").strip()
        status_map = {
            "watch": ("watch", "관망"),
            "hold": ("watch", "관망"),
            "관망": ("watch", "관망"),
            "buy_wait": ("buy_wait", "매수대기"),
            "buy": ("buy_wait", "매수대기"),
            "매수대기": ("buy_wait", "매수대기"),
            "rotate_review": ("rotate_review", "교체검토"),
            "rotation": ("rotate_review", "교체검토"),
            "교체검토": ("rotate_review", "교체검토"),
            "sell_review": ("sell_review", "매도검토"),
            "sell": ("sell_review", "매도검토"),
            "매도검토": ("sell_review", "매도검토"),
            "data_insufficient": ("data_insufficient", "데이터부족"),
            "insufficient": ("data_insufficient", "데이터부족"),
            "데이터부족": ("data_insufficient", "데이터부족"),
        }
        opinion, status_label = status_map.get(opinion_raw) or status_map.get(status_raw) or ("data_insufficient", "데이터부족")
        try:
            confidence = float(parsed.get("confidence"))
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        reason = str(parsed.get("reason") or parsed.get("rationale") or "").strip()
        if not reason or reason.lower() in {"execution not allowed", "order execution not allowed"}:
            reason = "관리종목 운용 의견 생성을 위한 근거가 제한적입니다. 추가 데이터 확인 후 참고만 합니다."
        next_action = str(parsed.get("next_action") or "").strip()
        if not next_action:
            next_action = "운용 의견 참고만 수행; 주문 실행 없음"
        return {
            "opinion": opinion,
            "status_label": status_label,
            "confidence": confidence,
            "reason": reason[:500],
            "next_action": next_action[:300],
        }

    def _with_ai_result_contract(self, result: Dict[str, Any]) -> Dict[str, Any]:
        result["suggestion_only"] = True
        result["applied_to_action"] = False
        try:
            print(
                "[AITS][AIEngineProvider] ai_result_contract "
                "| suggestion_only=True | applied_to_action=False"
            )
        except Exception:
            pass
        return result

    def _build_router_verification_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """
        Build compact prompt for Router verification.

        Token policy:
        - RouterSummary 수준의 compact context만 사용한다.
        - 장문 시장 데이터/캔들 원본/전체 로그는 포함하지 않는다.
        """
        context = context or {}
        allowed = ", ".join(sorted(AI_VERIFICATION_ALLOWED_SUGGESTIONS))
        lines = [
            "You are a safety verifier for an AI trading decision router.",
            "Return only a compact JSON object.",
            "Do not place orders.",
            "Do not execute trades.",
            "Do not assume authority over final action.",
            f"Allowed suggestion values: {allowed}",
            "",
            "Context:",
        ]

        for key in (
            "router_version",
            "final_action",
            "final_confidence",
            "fusion_signal",
            "performance_boost",
            "soft_override_candidate",
            "dryrun_compare",
            "mismatch_reason",
            "market_regime",
            "candidate_count",
            "positions_count",
            "symbol",
            "execution_allowed",
            "safety_note",
        ):
            if key in context:
                lines.append(f"- {key}: {context.get(key)}")

        lines.extend(
            [
                "",
                "Return JSON format:",
                '{"suggestion":"confirm","reason":"short reason","risk_note":"short risk note"}',
            ]
        )
        return "\n".join(lines)

    def _call_openai_router_verification(self, prompt: str, context: Dict[str, Any]) -> Any:
        """
        OpenAI router verification call.

        Safety:
        - 기존 OpenAI 호출 메서드가 명확히 있을 때만 위임한다.
        - 없으면 NotImplementedError로 안전하게 skip 처리된다.
        - 여기서 신규 SDK/키 로딩/설정 변경을 하지 않는다.
        """
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        api_call_enabled = real_call_enabled and one_shot_enabled
        if api_call_enabled:
            gate_reason = "enabled"
        elif real_call_enabled:
            gate_reason = "missing_one_shot"
        else:
            gate_reason = "dryrun_mode"
        _safe_log_info(
            "[AITS][AIEngineProvider] api_call_entry "
            f"| provider=openai | enabled={api_call_enabled} | reason={gate_reason}"
        )
        if not api_call_enabled:
            raise NotImplementedError("openai_live_call_disabled")

        api_key = self._get_config_api_key("openai")
        if not api_key:
            raise NotImplementedError("openai_api_key_missing")

        model = os.getenv("AITS_OPENAI_VERIFY_MODEL", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"

        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": 120,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON. You are a trading router verifier. Never execute trades.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            _safe_log_info("[AITS][OpenAIHTTP] step=before_request")
            with urllib.request.urlopen(req, timeout=20) as resp:
                response_text = resp.read().decode("utf-8")
                _safe_log_info(f"[AITS][OpenAIHTTP] status={resp.status}")
                _safe_log_info(
                    "[AITS][OpenAIHTTP] body="
                    + str(response_text)[:300].replace("\n", " ").replace("\r", " ")
                )
                data = json.loads(response_text)
            _raw_preview = str(data).replace("\n", " ").replace("\r", " ")[:500]
            logging.getLogger("aits").info(
                "[AITS][OpenAIRaw] "
                f"preview={_raw_preview}"
            )
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800]
            body_lower = body.lower()

            reason = f"openai_http_error:{exc.code}"

            if exc.code == 429 or "quota" in body_lower or "rate limit" in body_lower or "too many requests" in body_lower or "insufficient_quota" in body_lower:
                reason = "openai_quota_exceeded"
            elif exc.code in (401, 403) or "invalid api key" in body_lower or "incorrect api key" in body_lower:
                reason = "openai_api_key_invalid"
            elif exc.code == 400:
                reason = "openai_bad_request"

            _safe_log_info(f"[AITS][OpenAIHTTP] status={exc.code}")
            _safe_log_info(
                "[AITS][OpenAIHTTP] body="
                + str(body)[:300].replace("\n", " ").replace("\r", " ")
            )
            _safe_log_info(
                "[AITS][OpenAIHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            _safe_log_info(
                "[AITS][OpenAIHTTP] classified_error | "
                f"code={exc.code} | reason={reason}"
            )
            raise RuntimeError(reason)
        except Exception as exc:
            _safe_log_info(
                "[AITS][OpenAIHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            raise
        finally:
            os.environ["AITS_AI_VERIFY_LIVE_ONCE"] = "0"

    def _call_gemini_router_verification(self, prompt: str, context: Dict[str, Any]) -> Any:
        """
        Gemini router verification call.

        Safety:
        - 기존 Gemini 호출 메서드가 명확히 있을 때만 위임한다.
        - 없으면 NotImplementedError로 안전하게 skip 처리된다.
        - 여기서 신규 SDK/키 로딩/설정 변경을 하지 않는다.
        """
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        api_call_enabled = real_call_enabled and one_shot_enabled
        if api_call_enabled:
            gate_reason = "enabled"
        elif real_call_enabled:
            gate_reason = "missing_one_shot"
        else:
            gate_reason = "dryrun_mode"
        _safe_log_info(
            "[AITS][AIEngineProvider] api_call_entry "
            f"| provider=gemini | enabled={api_call_enabled} | reason={gate_reason}"
        )
        if not api_call_enabled:
            raise NotImplementedError("gemini_live_call_disabled")

        api_key = self._get_config_api_key("gemini")
        if not api_key:
            raise NotImplementedError("gemini_api_key_missing")

        model = os.getenv("AITS_GEMINI_VERIFY_MODEL", "gemini-2.0-flash")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Return only JSON. You are a trading router verifier. "
                                "Never execute trades.\n\n" + prompt
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 120,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            _safe_log_info("[AITS][GeminiHTTP] step=before_request")
            with urllib.request.urlopen(req, timeout=20) as resp:
                response_text = resp.read().decode("utf-8")
                _safe_log_info(f"[AITS][GeminiHTTP] status={resp.status}")
                _safe_log_info(
                    "[AITS][GeminiHTTP] body="
                    + str(response_text)[:300].replace("\n", " ").replace("\r", " ")
                )
                data = json.loads(response_text)
            _raw_preview = str(data).replace("\n", " ").replace("\r", " ")[:500]
            logging.getLogger("aits").info(
                "[AITS][GeminiRaw] "
                f"preview={_raw_preview}"
            )
            return (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800]
            body_lower = body.lower()

            reason = f"gemini_http_error:{exc.code}"

            if exc.code == 429 or "quota" in body_lower or "rate limit" in body_lower or "too many requests" in body_lower:
                reason = "gemini_quota_exceeded"
            elif exc.code in (401, 403) or "api key not valid" in body_lower or "api_key_invalid" in body_lower:
                reason = "gemini_api_key_invalid"
            elif exc.code == 400:
                reason = "gemini_bad_request"

            _safe_log_info(f"[AITS][GeminiHTTP] status={exc.code}")
            _safe_log_info(
                "[AITS][GeminiHTTP] body="
                + str(body)[:300].replace("\n", " ").replace("\r", " ")
            )
            _safe_log_info(
                "[AITS][GeminiHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            _safe_log_info(
                "[AITS][GeminiHTTP] classified_error | "
                f"code={exc.code} | reason={reason}"
            )
            raise RuntimeError(reason)
        except Exception as exc:
            _safe_log_info(
                "[AITS][GeminiHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            raise
        finally:
            os.environ["AITS_AI_VERIFY_LIVE_ONCE"] = "0"

    def _parse_router_verification_response(self, *, raw_response: Any = None, provider: Any = None) -> Dict[str, Any]:
        """
        Parse AI verifier response into standard suggestion dict.
        """
        import json

        provider = str(provider or "unknown").strip().lower()

        if isinstance(raw_response, dict):
            parsed = raw_response
        else:
            text = str(raw_response or "").strip()
            if not text:
                return self._with_ai_result_contract({
                    "suggestion": "skip",
                    "reason": "empty_response",
                    "provider": provider,
                    "applied": False,
                })
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = {
                    "suggestion": "confirm",
                    "reason": "non_json_response_default_confirm",
                    "risk_note": text[:500],
                }

        suggestion = str(parsed.get("suggestion") or parsed.get("decision") or "confirm").strip().lower()
        if suggestion not in AI_VERIFICATION_ALLOWED_SUGGESTIONS:
            suggestion = "confirm"

        return self._with_ai_result_contract({
            "suggestion": suggestion,
            "reason": str(parsed.get("reason") or parsed.get("summary") or "provider_response")[:500],
            "risk_note": str(parsed.get("risk_note") or parsed.get("note") or "")[:500],
            "provider": provider,
            "applied": False,
            "raw_response": parsed,
        })

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "api_required": self.api_required,
            "ready": self.is_ready(),
            "ready_reason": self.get_ready_reason(),
        }

    def get_ready_reason(self) -> str:
        return self.ready_reason


class LocalProvider(AIEngineProvider):
    name = "local"
    api_required = False

    def is_ready(self) -> bool:
        return True

    def get_ready_reason(self) -> str:
        return "Local Engine ready"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        raw_context = dict(context or {})
        rule_action = str(
            raw_context.get("rule_action")
            or raw_context.get("original_action")
            or ""
        ).strip().lower()
        if rule_action == "watch":
            normalized_rule_action = "wait"
        else:
            normalized_rule_action = rule_action
        rule_confidence = _clamp_float(
            raw_context.get("rule_confidence"),
            lo=0.0,
            hi=1.0,
            default=0.50,
        )
        market_regime = str(raw_context.get("market_regime") or "").strip().lower()
        candidate_count = _safe_int(raw_context.get("candidate_count"), 0)
        positions_count = _safe_int(raw_context.get("positions_count"), 0)
        shadow_action = "hold"
        shadow_rule = "hold_wait"
        risk = "medium"
        confidence = _clamp_float(rule_confidence, lo=0.45, hi=0.60, default=0.50)
        reason = (
            "Local shadow HOLD: "
            f"conditions not strong enough, regime={market_regime or 'unknown'}, "
            f"candidates={candidate_count}"
        )
        buy_regimes = ("sideways", "bull", "alt", "neutral")
        sell_regimes = ("bear", "crash", "risk_off")
        if (
            positions_count == 0
            and candidate_count >= 3
            and market_regime in buy_regimes
            and normalized_rule_action in ("wait", "hold", "buy")
            and rule_confidence >= 0.50
        ):
            shadow_action = "buy"
            shadow_rule = "buy_candidate"
            confidence = min(0.70, max(0.55, rule_confidence))
            risk = "medium" if market_regime in buy_regimes else "high"
            reason = (
                "Local shadow BUY candidate: "
                f"no positions, candidates={candidate_count}, "
                f"regime={market_regime}, rule={rule_action or 'unknown'}"
            )
        elif (
            positions_count > 0
            and market_regime in sell_regimes
            and normalized_rule_action in ("sell", "reduce", "hold", "wait")
            and rule_confidence >= 0.45
        ):
            shadow_action = "sell"
            shadow_rule = "sell_candidate"
            confidence = min(0.70, max(0.55, rule_confidence))
            risk = "high"
            reason = (
                "Local shadow SELL candidate: "
                f"positions={positions_count}, regime={market_regime}, "
                f"rule={rule_action or 'unknown'}"
            )
        elif normalized_rule_action in ("wait", "watch"):
            shadow_action = "wait"
            reason = (
                "Local shadow WAIT: "
                f"conditions not strong enough, regime={market_regime or 'unknown'}, "
                f"candidates={candidate_count}"
            )
        risk_hint = _build_local_risk_hint(
            shadow_action=shadow_action,
            market_regime=market_regime,
            candidate_count=candidate_count,
        )
        shadow_summary = _trim_text(
            "Local shadow: "
            f"rule={rule_action or 'unknown'}, "
            f"regime={market_regime or 'unknown'}, "
            f"candidates={candidate_count}, "
            f"positions={positions_count}, "
            f"conf={confidence:.2f}",
            160,
        )
        return AIEngineDecision(
            action=shadow_action,
            confidence=confidence,
            risk=risk,
            reason=reason,
            engine="local",
            raw={
                "mode": "rule_shadow_v1",
                "has_context": bool(raw_context),
                "rule_action": rule_action,
                "rule_confidence": rule_confidence,
                "rule_reason": str(raw_context.get("rule_reason") or ""),
                "market_regime": market_regime,
                "positions_count": positions_count,
                "candidate_count": candidate_count,
                "portfolio_value": raw_context.get("portfolio_value"),
                "cycle": raw_context.get("cycle"),
                "shadow_rule": shadow_rule,
                "execution_allowed": False,
                "note": "shadow only; final decision unchanged",
                "shadow_summary": shadow_summary,
                "risk_hint": risk_hint,
            },
        )


class OpenAIProvider(AIEngineProvider):
    name = "openai"
    api_required = True

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def get_ready_reason(self) -> str:
        if self.is_ready():
            return "OpenAI API key configured"
        return "OpenAI API key missing"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="OpenAIProvider shadow only; API call disabled",
            engine="openai",
            raw={"mode": "shadow_provider", "api_call": "disabled"},
        )


class GeminiProvider(AIEngineProvider):
    name = "gemini"
    api_required = True

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def get_ready_reason(self) -> str:
        if self.is_ready():
            return "Gemini API key configured"
        return "Gemini API key missing"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="GeminiProvider shadow only; API call disabled",
            engine="gemini",
            raw={"mode": "shadow_provider", "api_call": "disabled"},
        )


def normalize_provider_name(provider_name: Any) -> str:
    provider_norm = str(provider_name or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    if provider_norm in ("local", "basic"):
        return "local"
    return "local"


def normalize_provider_label(provider_name: Any) -> str:
    provider_norm = str(provider_name or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    return "basic"


def _clamp_float(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    try:
        if value is None:
            result = default
        else:
            result = float(value)
    except (TypeError, ValueError):
        result = default
    if result < lo:
        return lo
    if result > hi:
        return hi
    return result


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_local_risk_hint(
    *,
    shadow_action: str,
    market_regime: str,
    candidate_count: int,
) -> str:
    action = str(shadow_action or "").strip().lower()
    if action == "buy":
        return "buy_candidate_shadow"
    if action == "sell":
        return "sell_candidate_shadow"
    regime = str(market_regime or "").strip().lower()
    if regime in ("bear", "crash", "risk_off", "risk-off"):
        return "defensive"
    if candidate_count >= 5:
        return "watchlist_active"
    return "neutral"


def _trim_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _read_value(root: Any, key: str) -> str:
    try:
        if root is None:
            return ""
        if isinstance(root, dict):
            value = root.get(key)
        else:
            value = getattr(root, key, "")
        return str(value or "").strip()
    except Exception:
        return ""


def _iter_roots(*roots: Any):
    seen = set()
    stack = [root for root in roots if root is not None]
    while stack:
        root = stack.pop(0)
        ident = id(root)
        if ident in seen:
            continue
        seen.add(ident)
        yield root
        try:
            if isinstance(root, dict):
                children = [root.get(key) for key in ("strategy", "settings", "prefs", "config")]
            else:
                children = [getattr(root, key, None) for key in ("strategy", "settings", "prefs", "config")]
            stack.extend(child for child in children if child is not None)
        except Exception:
            continue


def _find_api_key(
    candidates: tuple[str, ...],
    *roots: Any,
    env_keys: tuple[str, ...] = (),
    provider: Any = None,
) -> str:
    resolved_key = ""
    key_method = "missing"
    for root in _iter_roots(*roots):
        for key in candidates:
            value = _read_value(root, key)
            if value:
                resolved_key = value
                key_method = "settings"
                break
        if resolved_key:
            break
    if not resolved_key:
        for env_key in env_keys:
            value = (os.getenv(env_key) or "").strip()
            if value:
                resolved_key = value
                key_method = "environment"
                break
    try:
        _provider_name = normalize_provider_label(provider)

        print(
            "[AITS][AIEngineProvider] key_resolution "
            f"| provider={_provider_name or 'unknown'} "
            f"| resolved={bool(resolved_key)} "
            f"| method={key_method}"
        )
    except Exception:
        pass
    return resolved_key


def build_default_provider_registry(
    settings: Optional[Any] = None,
    prefs: Optional[Any] = None,
    config: Optional[Any] = None,
) -> Dict[str, AIEngineProvider]:
    openai_api_key = _find_api_key(
        ("ai_openai_api_key", "openai_api_key", "gpt_api_key"),
        settings,
        prefs,
        config,
        env_keys=("OPENAI_API_KEY",),
        provider="openai",
    )
    gemini_api_key = _find_api_key(
        (
            "ai_gemini_api_key",
            "gemini_api_key",
            "google_api_key",
            "google_gemini_api_key",
        ),
        settings,
        prefs,
        config,
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        provider="gemini",
    )
    return {
        "local": LocalProvider(),
        "openai": OpenAIProvider(api_key=openai_api_key),
        "gemini": GeminiProvider(api_key=gemini_api_key),
    }


def get_provider(
    registry: Optional[Dict[str, AIEngineProvider]], provider_name: Any
) -> AIEngineProvider:
    try:
        provider_key = normalize_provider_name(provider_name)
        provider_label = normalize_provider_label(provider_name or provider_key)
        try:
            print(
                "[AITS][AIEngineProvider] provider_selected "
                f"| provider={provider_label}"
            )
        except Exception:
            pass
        providers = registry or {}
        provider = providers.get(provider_key) or providers.get("local")
        if provider is not None:
            return provider
    except Exception:
        pass
    return LocalProvider()
