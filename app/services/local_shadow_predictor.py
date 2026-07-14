from __future__ import annotations

from datetime import datetime
import math
import pickle
from pathlib import Path
from typing import Any, Optional

from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_model_training import AITSLocalModelTrainingPipeline


MODEL_ACTIONS = {"wait", "hold", "buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
QUALITY_FACTORS = {"A": 1.0, "B": 0.85, "C": 0.65}


def load_latest_local_model(root: Path | str = Path("data") / "local_models") -> dict:
    registry = AITSLocalModelRegistry(root)
    latest = registry.load_latest()
    metadata = registry.latest_model_candidate()
    if not metadata:
        reason = "local_model_not_trained" if latest and not latest.get("trained") else "local_model_artifact_missing"
        return {
            "status": "unavailable",
            "reason": reason,
            "metadata": latest,
            "safe_for_live_decision": bool(latest.get("safe_for_live_decision")),
            "live_decision_enabled": bool(latest.get("live_decision_enabled")),
        }
    try:
        with Path(metadata["model_path"]).open("rb") as handle:
            bundle = pickle.load(handle)
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"model_load_failed:{type(exc).__name__}",
            "metadata": metadata,
            "safe_for_live_decision": bool(metadata.get("safe_for_live_decision")),
            "live_decision_enabled": bool(metadata.get("live_decision_enabled")),
        }
    if not isinstance(bundle, dict) or not isinstance(bundle.get("models"), dict):
        return {
            "status": "unavailable",
            "reason": "model_artifact_contract_invalid",
            "metadata": metadata,
            "safe_for_live_decision": bool(metadata.get("safe_for_live_decision")),
            "live_decision_enabled": bool(metadata.get("live_decision_enabled")),
        }
    return {
        "status": "available",
        "metadata": metadata,
        "bundle": bundle,
        "safe_for_live_decision": bool(metadata.get("safe_for_live_decision")),
        "live_decision_enabled": bool(metadata.get("live_decision_enabled")),
    }


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _first(mapping: dict, *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _numeric(mapping: dict, *keys: str) -> Optional[float]:
    return _number(_first(mapping, *keys))


def build_local_model_feature_record(
    context: dict,
    *,
    manifest_summary: Optional[dict] = None,
    local_decision: Optional[dict] = None,
) -> dict:
    """Build the inference vector from factual live payload fields only."""
    value = dict(context or {})
    manifest = dict(manifest_summary or {})
    local = dict(local_decision or {})
    market = dict(value.get("market") or value.get("market_data") or {})
    indicators = dict(value.get("indicators") or value.get("basic_market_indicators") or {})
    position = dict(value.get("current_position") or value.get("position") or {})
    portfolio = dict(value.get("portfolio") or value.get("portfolio_context") or {})
    guard = dict(value.get("sell_unit_guard") or {})
    candidates = value.get("candidates") or []
    candidate_count = len(candidates) if isinstance(candidates, (list, tuple)) else len(candidates) if isinstance(candidates, dict) else 0
    total_asset = _numeric(portfolio, "total_asset_krw")
    available = _numeric(portfolio, "available_krw")
    exposure = _numeric(portfolio, "exposure_for_cap")
    macd = indicators.get("macd")
    if isinstance(macd, dict):
        macd = _first(macd, "macd", "value", "line")
    grade = str(manifest.get("payload_quality_grade") or "F").upper()
    created = datetime.now()
    feature_vector = {
        "market_features": {
            "price_change_1m": _numeric(market, "price_change_1m", "change_1m_pct"),
            "price_change_5m": _numeric(market, "price_change_5m", "change_5m_pct"),
            "price_change_15m": _numeric(market, "price_change_15m", "change_15m_pct"),
            "price_change_1h": _numeric(market, "price_change_1h", "change_1h_pct"),
            "volume_change": _numeric(market, "volume_change", "volume_change_pct"),
            "trade_value": _numeric(market, "trade_value", "trade_value_krw", "acc_trade_price_24h"),
            "volatility": _numeric(market, "volatility", "volatility_pct"),
            "market_data_stale": market.get("market_data_stale") if isinstance(market.get("market_data_stale"), bool) else None,
        },
        "indicator_features": {
            "rsi": _numeric(indicators, "rsi", "RSI"), "macd": _number(macd),
            "ma5": _numeric(indicators, "ma5", "MA5"), "ma20": _numeric(indicators, "ma20", "MA20"),
            "ma60": _numeric(indicators, "ma60", "MA60"), "momentum": _numeric(indicators, "momentum", "momentum_pct"),
            "trend_strength": _numeric(indicators, "trend_strength"),
        },
        "position_features": {
            "qty": _numeric(position, "qty", "quantity"), "avg_buy_price": _numeric(position, "avg_buy_price", "average_buy_price"),
            "current_price": _numeric(position, "current_price", "price", "trade_price"),
            "position_value_krw": _numeric(position, "position_value_krw", "selected_valuation_krw", "valuation_krw", "eval_krw"),
            "pnl_pct": _numeric(position, "pnl_pct", "profit_rate"), "weight_pct": _numeric(position, "weight_pct", "position_weight_pct"),
            "target_weight_pct": _numeric(position, "target_weight_pct"), "holding_age": _numeric(position, "holding_age", "holding_age_seconds"),
            "dust": _first(position, "dust", "final_dust", "is_dust_holding"),
            "manageable": _first(position, "manageable", "final_manageable", "manageable_holding"),
        },
        "portfolio_features": {
            "total_asset_krw": total_asset, "available_krw": available,
            "total_budget_krw": _numeric(portfolio, "total_budget_krw", "budget_krw"), "exposure_for_cap": exposure,
            "cap_remaining_krw": _numeric(portfolio, "cap_remaining_krw"),
            "position_count": _numeric(portfolio, "position_count", "holding_count"),
            "managed_pool_count": _numeric(portfolio, "managed_pool_count") or float(candidate_count),
            "cash_ratio": _numeric(portfolio, "cash_ratio") or (available / total_asset if total_asset and available is not None else None),
            "exposure_ratio": _numeric(portfolio, "exposure_ratio") or (exposure / total_asset if total_asset and exposure is not None else None),
        },
        "risk_features": {
            "sell_unit_guard_passed": guard.get("valuation_unit_mismatch") is False if guard else None,
            "valuation_unit_mismatch": guard.get("valuation_unit_mismatch") if isinstance(guard.get("valuation_unit_mismatch"), bool) else None,
            "risk_blocker_count": len(value.get("risk_blockers") or []), "safety_blocker_count": len(value.get("safety_blockers") or []),
            "livepreflight_blocker_count": len(value.get("livepreflight_blockers") or []),
            "dust_excluded": bool(position.get("dust") or position.get("final_dust")) if position else None,
            "cap_near_limit": portfolio.get("cap_near_limit") if isinstance(portfolio.get("cap_near_limit"), bool) else None,
        },
        "provider_features": {
            "local_confidence": _number(local.get("confidence")), "external_confidence": None, "confidence_gap": None,
            "local_external_agreed": None, "external_called": False, "external_blocked": False,
            "final_provider_source": None, "escalation_required": None, "cost_guard_blocked": False,
        },
        "opportunity_features": {
            "candidate_move_pct": None, "held_symbol_move_pct": None,
            "opportunity_gap_change": _numeric(value, "opportunity_gap_change", "opportunity_score_gap"),
            "missed_move_detected": None, "avoided_drawdown_detected": None,
        },
        "time_features": {
            "hour_of_day": created.hour, "day_of_week": created.weekday(), "time_since_last_decision": None,
            "eta_seconds": _number(local.get("eta_seconds") or value.get("eta_seconds")), "checkpoint_horizon": None,
        },
        "data_quality_features": {
            "payload_quality_numeric": {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.3, "F": 0.0}.get(grade),
            "data_quality_numeric": {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.3, "F": 0.0}.get(grade),
            "missing_feature_count": _number(manifest.get("payload_missing_feature_count")),
            "stale_feature_count": float(len(manifest.get("stale_features") or [])),
            "unavailable_feature_count": _number(manifest.get("payload_unavailable_feature_count")),
        },
    }
    return {
        "schema": AITSLocalModelTrainingPipeline.FEATURE_SCHEMA,
        "feature_vector": feature_vector,
        "feature_quality_grade": grade,
        "critical_missing_features": list(manifest.get("critical_missing_features") or []),
        "payload_hash": str(manifest.get("payload_hash") or ""),
    }


def _transform_feature_record(feature_record: dict, bundle: dict) -> list[float]:
    flattened = AITSLocalModelTrainingPipeline._flatten(dict(feature_record.get("feature_vector") or {}))
    columns = list(bundle.get("feature_columns") or [])
    feature_types = dict(bundle.get("feature_types") or {})
    encoding_map = dict(bundle.get("encoding_map") or {})
    vector: list[float] = []
    for column in columns:
        value = flattened.get(column)
        kind = feature_types.get(column)
        if kind == "numeric":
            number = AITSLocalModelTrainingPipeline._number(value)
            vector.append(float(number) if number is not None else 0.0)
        elif kind == "boolean":
            vector.append(1.0 if value is True else 0.0)
        else:
            vector.append(float((encoding_map.get(column) or {}).get(str(value), 0)) if value is not None else 0.0)
    return vector


def _predict_target(feature_record: dict, target: str, *, loaded: Optional[dict] = None) -> dict[str, Any]:
    model_state = dict(loaded or load_latest_local_model())
    if model_state.get("status") != "available":
        return model_state
    bundle = dict(model_state.get("bundle") or {})
    model = dict(bundle.get("models") or {}).get(target)
    if model is None:
        return {**model_state, "status": "unavailable", "reason": f"target_not_trained:{target}"}
    vector = _transform_feature_record(feature_record, bundle)
    try:
        prediction = model.predict(1)[0]
    except Exception as exc:
        return {**model_state, "status": "unavailable", "reason": f"prediction_failed:{type(exc).__name__}"}
    return {
        "status": "available", "target": target, "prediction": prediction,
        "score": _number(prediction), "feature_count": len(vector),
        "model_id": str((model_state.get("metadata") or {}).get("model_id") or ""),
        "safe_for_live_decision": bool(model_state.get("safe_for_live_decision")),
        "live_decision_enabled": bool(model_state.get("live_decision_enabled")),
    }


def predict_local_action_quality(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "action_quality_score")


def predict_provider_value(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "provider_value_score")


def predict_risk_score(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "risk_adjusted_score")


def predict_local_model_decision(context: dict, manifest_summary: dict, local_decision: dict) -> dict[str, Any]:
    loaded = load_latest_local_model()
    metadata = dict(loaded.get("metadata") or {})
    base = {
        "local_model_provider_available": loaded.get("status") == "available",
        "local_model_loaded": loaded.get("status") == "available",
        "local_model_id": str(metadata.get("model_id") or ""),
        "local_model_trained": bool(metadata.get("trained")),
        "local_model_safe_for_live_decision": bool(loaded.get("safe_for_live_decision")),
        "local_model_live_decision_enabled": bool(loaded.get("live_decision_enabled")),
        "local_model_prediction_attempted": False,
        "local_model_prediction_available": False,
        "local_model_prediction_blocker": str(loaded.get("reason") or ""),
    }
    if loaded.get("status") != "available":
        return base
    feature_record = build_local_model_feature_record(context, manifest_summary=manifest_summary, local_decision=local_decision)
    grade = str(feature_record.get("feature_quality_grade") or "F")
    critical_missing = list(feature_record.get("critical_missing_features") or [])
    if grade not in QUALITY_FACTORS or critical_missing:
        blocker = "critical_model_feature_missing" if critical_missing else "local_model_feature_quality_too_low"
        return {**base, "local_model_prediction_attempted": True, "local_model_prediction_blocker": blocker,
                "local_model_feature_schema_compatible": True, "local_model_feature_quality_checked": True}
    action_result = _predict_target(feature_record, "recommended_action_label", loaded=loaded)
    action = str(action_result.get("prediction") or "").lower()
    if action_result.get("status") != "available" or action not in MODEL_ACTIONS:
        return {**base, "local_model_prediction_attempted": True,
                "local_model_prediction_blocker": str(action_result.get("reason") or "recommended_action_target_invalid"),
                "local_model_feature_schema_compatible": True, "local_model_feature_quality_checked": True}
    quality_result = _predict_target(feature_record, "action_quality_score", loaded=loaded)
    provider_result = _predict_target(feature_record, "provider_value_score", loaded=loaded)
    risk_result = _predict_target(feature_record, "risk_adjusted_score", loaded=loaded)
    action_score = _number(quality_result.get("score"))
    provider_score = _number(provider_result.get("score"))
    risk_score = _number(risk_result.get("score"))
    if action_score is None or risk_score is None:
        return {**base, "local_model_prediction_attempted": True,
                "local_model_prediction_blocker": "required_model_score_unavailable",
                "local_model_feature_schema_compatible": True, "local_model_feature_quality_checked": True}
    confidence = max(0.0, min(1.0, ((max(0.0, min(1.0, action_score)) + max(0.0, min(1.0, risk_score))) / 2.0) * QUALITY_FACTORS[grade]))
    live_allowed = bool(base["local_model_safe_for_live_decision"] and base["local_model_live_decision_enabled"])
    reason = f"LOCAL 학습 모델이 {action} 판단을 제안했습니다. 품질 {grade}, 신뢰도 {confidence:.2f}."
    blockers = [] if live_allowed else ["local_model_live_disabled_by_registry"]
    candidate = {
        "action": action, "confidence": confidence, "reason_ko": reason,
        "eta_seconds": int(_number(local_decision.get("eta_seconds")) or 300),
        "execution_plan": {}, "risk_notes": ",".join(blockers), "invalidation_conditions": [],
        "sell_ratio": 0.0, "buy_amount_krw": 0.0,
    }
    return {
        **base,
        "local_model_prediction_attempted": True,
        "local_model_prediction_available": True,
        "local_model_prediction_blocker": "" if live_allowed else "local_model_live_disabled_by_registry",
        "local_model_feature_schema_compatible": True,
        "local_model_feature_quality_checked": True,
        "local_model_feature_quality_grade": grade,
        "model_recommended_action": action,
        "model_action_quality_score": action_score,
        "model_provider_value_score": provider_score,
        "model_risk_score": risk_score,
        "model_confidence": confidence,
        "model_reason_ko": reason,
        "model_blockers": blockers,
        "model_decision_candidate": candidate,
        "local_model_live_allowed": live_allowed,
        "local_model_requires_external_confirmation": action in ORDER_ACTIONS,
    }
