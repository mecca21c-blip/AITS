from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
import pickle
from pathlib import Path
import threading
from typing import Any, Optional

from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_model_training import AITSLocalModelTrainingPipeline
from app.services.local_training_dataset_curation import build_training_eligibility_provenance, read_recoverable_jsonl


MODEL_ACTIONS = {"wait", "hold", "buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
QUALITY_FACTORS = {"A": 1.0, "B": 0.85, "C": 0.65}
LOCAL_ENGINE_DECISION_SCHEMA = "aits_local_engine_decision_candidate.v1"
LOCAL_ENGINE_OBSERVATION_SCHEMA = "aits_local_engine_candidate_observation.v1"
LOCAL_ENGINE_VERSION = "v1"
LOCAL_ENGINE_OBSERVATION_WRITER_CONTRACT = "v2"
LOCAL_ENGINE_HEAD_CONTRACTS = {
    "action_head": {"output": "action", "required_source": "trained_model"},
    "confidence_head": {"output": "confidence", "required_source": "calibrated_model"},
    "risk_head": {"output": "risk_level,blockers", "required_source": "observed_risk_evidence"},
    "escalation_head": {"output": "escalation_required,escalation_reason", "required_source": "provider_policy"},
    "eta_head": {"output": "eta_seconds,eta_policy", "required_source": "observed_cadence"},
    "invalidation_head": {"output": "invalidation_conditions", "required_source": "feature_evidence"},
    "reason_composer": {"output": "reason_ko", "required_source": "structured_evidence"},
    "teacher_distillation_contract": {
        "output": "teacher_reference,training_source",
        "required_source": "validated_provider_outcome",
    },
}


class LocalEngineCandidateObservationError(ValueError):
    """Safe, structured failure for candidate observation persistence."""

    def __init__(self, blocker: str, *, status: str, error: str = "") -> None:
        super().__init__(blocker)
        self.blocker = blocker
        self.status = status
        self.error = error


class AITSLocalEngineCandidateObservationWriter:
    """Durably append real model candidates without granting decision authority."""

    _lock = threading.Lock()

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.root = Path(root)
        self.path = self.root / "local_engine_candidate_observations.jsonl"

    @staticmethod
    def validation_blocker(record: dict) -> str:
        if not str(record.get("schema") or ""):
            return "candidate_schema_missing"
        if record.get("schema") != LOCAL_ENGINE_OBSERVATION_SCHEMA:
            return "candidate_schema_invalid"
        if not str(record.get("prediction_id") or ""):
            return "prediction_id_missing"
        if not str(record.get("model_artifact_id") or ""):
            return "model_artifact_id_missing"
        if str(record.get("action") or "") not in MODEL_ACTIONS:
            return "candidate_action_invalid"
        if record.get("candidate_only") is not True:
            return "candidate_only_contract_broken"
        if record.get("applied_to_final_action") is not False:
            return "candidate_applied_to_final_action"
        if "final_action_unchanged" in record and record.get("final_action_unchanged") is not True:
            return "candidate_final_action_unchanged_contract_broken"
        if record.get("safe_for_live_decision") is not False:
            return "candidate_safe_for_live_unexpected"
        if record.get("live_decision_enabled") is not False:
            return "candidate_live_decision_enabled_unexpected"
        if record.get("fake_prediction") is not False:
            return "candidate_prediction_provenance_invalid"
        return ""

    @classmethod
    def validate(cls, record: dict) -> bool:
        return not cls.validation_blocker(record)

    def append(self, record: dict) -> dict:
        value = dict(record or {})
        blocker = self.validation_blocker(value)
        if blocker:
            raise LocalEngineCandidateObservationError(blocker, status="failed_schema_validation")
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, default=str) + "\n").encode("utf-8")
        json.loads(payload.decode("utf-8"))
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise LocalEngineCandidateObservationError(
                "directory_create_failed", status="failed", error=type(exc).__name__
            ) from exc
        with self._lock:
            try:
                with self.path.open("ab") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception as exc:
                raise LocalEngineCandidateObservationError(
                    "writer_exception", status="failed", error=type(exc).__name__
                ) from exc
        return value

    def read(self) -> tuple[list[dict], dict[str, int]]:
        return read_recoverable_jsonl(self.path)


def build_local_engine_candidate_observation(
    *,
    candidate: dict,
    model_state: dict,
    context: dict,
    manifest_summary: dict,
    final_decision: dict,
    cost_guard: dict,
) -> dict:
    """Join a real model prediction to teacher metadata without changing it."""
    source = dict(candidate or {})
    if source.get("schema") != LOCAL_ENGINE_DECISION_SCHEMA:
        raise LocalEngineCandidateObservationError(
            "candidate_schema_missing" if not source.get("schema") else "candidate_schema_invalid",
            status="failed_schema_validation",
        )
    final_provider = str(final_decision.get("final_provider_source") or final_decision.get("provider") or "")
    if final_provider == "local_model":
        raise LocalEngineCandidateObservationError(
            "candidate_observation_final_source_conflict", status="skipped"
        )
    metadata = dict(model_state.get("local_model_metadata") or {})
    model_id = str(model_state.get("local_model_id") or metadata.get("model_id") or "")
    if not model_id or not bool(model_state.get("local_model_trained")):
        raise LocalEngineCandidateObservationError(
            "local_engine_trained_artifact_unavailable", status="skipped"
        )
    task = str(context.get("task") or source.get("task") or "")
    scope = str(context.get("symbol") or context.get("scope") or source.get("scope") or "PORTFOLIO")
    decision_id = str(
        final_decision.get("decision_id")
        or final_decision.get("response_id")
        or manifest_summary.get("payload_hash")
        or ""
    )
    created_at = str(source.get("created_at") or datetime.now().astimezone().isoformat())
    identity = {
        "model_id": model_id,
        "payload_hash": str(manifest_summary.get("payload_hash") or ""),
        "task": task,
        "source_task": str(source.get("source_task") or task),
        "model_task": str(source.get("model_task") or task),
        "scope": scope,
        "created_at": created_at,
    }
    prediction_id = "local-engine-" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    final_reason = str(final_decision.get("final_reason_ko") or final_decision.get("reason_ko") or "")
    outcome_linkage_key = hashlib.sha256(
        f"{decision_id}|{prediction_id}|{task}|{scope}".encode("utf-8")
    ).hexdigest()[:32]
    teacher_present = final_provider in {"openai", "gemini"}
    guard_blocker = str(cost_guard.get("blocker") or final_decision.get("cost_guard_blocker") or "")
    if teacher_present:
        teacher_absent_reason = ""
    elif guard_blocker == "provider_request_cooldown":
        teacher_absent_reason = "provider_request_cooldown"
    elif "network" in guard_blocker.lower():
        teacher_absent_reason = "network_unavailable"
    elif "key" in guard_blocker.lower():
        teacher_absent_reason = "provider_key_missing"
    elif guard_blocker:
        teacher_absent_reason = "provider_unavailable"
    elif final_provider == "local_safety_hold":
        teacher_absent_reason = "external_not_required"
    else:
        teacher_absent_reason = "historical_metadata_missing"
    return {
        "schema": LOCAL_ENGINE_OBSERVATION_SCHEMA,
        "writer_contract": LOCAL_ENGINE_OBSERVATION_WRITER_CONTRACT,
        "prediction_id": prediction_id,
        "created_at": created_at,
        "task": task,
        "scope": scope,
        "payload_snapshot_schema": str(context.get("schema") or "aits_ai_decision_payload.v1"),
        "local_engine_schema": LOCAL_ENGINE_DECISION_SCHEMA,
        "model_artifact_id": model_id,
        "model_registry_version": str(metadata.get("registry_schema") or AITSLocalModelRegistry.REGISTRY_SCHEMA),
        "model_trained": True,
        "calibration_available": bool(model_state.get("local_model_calibration_profile_available")),
        "action": str(source.get("action") or "").lower(),
        "action_probabilities": dict(source.get("action_probabilities") or {}),
        "action_margin": source.get("action_margin"),
        "supported_action": bool(source.get("action_supported", True)),
        "confidence": source.get("confidence"),
        "confidence_calibrated": bool(source.get("confidence_calibrated")),
        "raw_confidence": source.get("raw_confidence"),
        "calibration_method": str(source.get("calibration_method") or ""),
        "abstain_required": bool(source.get("abstain_required")),
        "abstain_reason": str(source.get("abstain_reason") or ""),
        "risk_level": str(source.get("risk_level") or "unknown"),
        "risk_score": source.get("risk_score"),
        "risk_factors": list(source.get("risk_factors") or []),
        "blockers": list(source.get("blockers") or []),
        "escalation_required": bool(source.get("escalation_required")),
        "provider_route_recommendation": str(source.get("provider_route_recommendation") or ""),
        "eta_seconds": int(source.get("eta_seconds") or 0),
        "invalidation_conditions": list(source.get("invalidation_conditions") or []),
        "evidence": list(source.get("evidence") or []),
        "reason_ko": str(source.get("reason_ko") or ""),
        "candidate_schema": str(source.get("schema") or ""),
        "validator_metadata": dict(model_state.get("local_engine_validator_metadata") or {}),
        "candidate_only": True,
        "applied_to_final_action": False,
        "final_action_unchanged": True,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
        "registry_safe_for_live_decision": bool(model_state.get("local_model_safe_for_live_decision")),
        "registry_live_decision_enabled": bool(model_state.get("local_model_live_decision_enabled")),
        "teacher_source": final_provider if teacher_present else "",
        "teacher_present": teacher_present,
        "teacher_provider": final_provider if teacher_present else None,
        "teacher_action": str(final_decision.get("final_action") or final_decision.get("action") or "") if teacher_present else None,
        "teacher_confidence": final_decision.get("final_confidence", final_decision.get("confidence")) if teacher_present else None,
        "teacher_absent_reason": teacher_absent_reason,
        "final_provider_source": final_provider,
        "final_action": str(final_decision.get("final_action") or final_decision.get("action") or ""),
        "final_confidence": final_decision.get("final_confidence", final_decision.get("confidence")),
        "final_reason_digest": hashlib.sha256(final_reason.encode("utf-8")).hexdigest()[:24] if final_reason else "",
        "provider_cost_guard_result": {
            "passed": bool(final_decision.get("cost_guard_passed")),
            "blocker": guard_blocker,
        },
        "decision_id": decision_id,
        "outcome_linkage_key": outcome_linkage_key,
        "fake_prediction": False,
    }


def record_local_engine_candidate_observation(**kwargs: Any) -> dict:
    record = build_local_engine_candidate_observation(**kwargs)
    return AITSLocalEngineCandidateObservationWriter().append(record)


def build_local_engine_decision_candidate(
    *,
    task: str,
    scope: str,
    action: str,
    confidence: float,
    reason_ko: str,
    eta_seconds: int,
    blockers: list[str],
    evidence: list[dict],
    safe_for_live_decision: bool,
    live_decision_enabled: bool,
    confidence_calibrated: bool = False,
    risk_level: str = "unknown",
    escalation_required: bool = True,
    escalation_reason: str = "local_engine_candidate_requires_external_review",
    eta_policy: str = "inherited_observed_cadence",
    invalidation_conditions: Optional[list] = None,
    teacher_reference: Optional[dict] = None,
    training_source: Optional[dict] = None,
    action_probabilities: Optional[dict] = None,
    action_margin: Optional[float] = None,
    action_supported: bool = True,
    unsupported_action_reasons: Optional[list[str]] = None,
    raw_confidence: Optional[float] = None,
    calibration_method: str = "",
    confidence_bucket: str = "",
    confidence_reliability: str = "",
    abstain_required: bool = False,
    abstain_reason: str = "",
    risk_score: Optional[float] = None,
    risk_factors: Optional[list[str]] = None,
    risk_blockers: Optional[list[str]] = None,
    escalation_target: str = "",
    external_confirmation_required: bool = True,
    eta_bucket: Optional[int] = None,
    eta_reason: str = "",
    monitoring_priority: str = "",
    invalidation_supported: bool = False,
    invalidation_missing_reason: str = "",
    evidence_summary: Optional[list[dict]] = None,
    risk_summary_ko: str = "",
    reason_template_id: str = "",
    provider_route_recommendation: str = "",
) -> dict:
    """Build a candidate only from supplied model output and factual evidence."""
    normalized_action = str(action or "").lower()
    if normalized_action not in MODEL_ACTIONS:
        raise ValueError("local_engine_action_unavailable")
    if not str(reason_ko or "").strip():
        raise ValueError("local_engine_reason_unavailable")
    return {
        "schema": LOCAL_ENGINE_DECISION_SCHEMA,
        "engine": "AITS_LOCAL_ENGINE",
        "engine_version": LOCAL_ENGINE_VERSION,
        "task": str(task or ""),
        "scope": str(scope or ""),
        "action": normalized_action,
        "action_probabilities": dict(action_probabilities or {}),
        "action_margin": action_margin,
        "action_supported": bool(action_supported),
        "unsupported_action_reasons": list(unsupported_action_reasons or []),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "confidence_calibrated": bool(confidence_calibrated),
        "raw_confidence": raw_confidence,
        "calibration_method": str(calibration_method or ""),
        "confidence_bucket": str(confidence_bucket or ""),
        "confidence_reliability": str(confidence_reliability or ""),
        "abstain_required": bool(abstain_required),
        "abstain_reason": str(abstain_reason or ""),
        "risk_level": str(risk_level or "unknown"),
        "risk_score": risk_score,
        "risk_factors": list(risk_factors or []),
        "risk_blockers": list(risk_blockers or []),
        "blockers": [str(item) for item in blockers if str(item or "").strip()],
        "escalation_required": bool(escalation_required),
        "escalation_reason": str(escalation_reason or ""),
        "escalation_target": str(escalation_target or ""),
        "external_confirmation_required": bool(external_confirmation_required),
        "provider_route_recommendation": str(provider_route_recommendation or ""),
        "eta_seconds": max(0, int(eta_seconds or 0)),
        "eta_bucket": max(0, int(eta_bucket or eta_seconds or 0)),
        "eta_reason": str(eta_reason or ""),
        "monitoring_priority": str(monitoring_priority or ""),
        "eta_policy": str(eta_policy or ""),
        "invalidation_conditions": list(invalidation_conditions or []),
        "invalidation_supported": bool(invalidation_supported),
        "invalidation_missing_reason": str(invalidation_missing_reason or ""),
        "evidence": [dict(item) for item in evidence if isinstance(item, dict)],
        "evidence_summary": [dict(item) for item in (evidence_summary or []) if isinstance(item, dict)],
        "reason_ko": str(reason_ko),
        "risk_summary_ko": str(risk_summary_ko or ""),
        "reason_template_id": str(reason_template_id or ""),
        "teacher_reference": dict(teacher_reference or {}),
        "training_source": dict(training_source or {}),
        "safe_for_live_decision": bool(safe_for_live_decision),
        "live_decision_enabled": bool(live_decision_enabled),
        "trained_model_required": True,
        "calibration_required": True,
        "fake_decision": False,
        "created_at": datetime.now().astimezone().isoformat(),
    }


def load_latest_local_model(
    root: Path | str = Path("data") / "local_models",
    *,
    task: str = "",
) -> dict:
    registry = AITSLocalModelRegistry(root)
    metadata = registry.latest_multi_head_candidate() or registry.latest_model_candidate()
    # A task-specific Challenger may be observed candidate-only when the global
    # Champion has no support for that task. This does not move any registry
    # pointer and cannot grant final-action authority.
    if task and metadata and task not in set(metadata.get("supported_tasks") or []):
        task_candidates = [
            row for row in registry.list_usable_models()
            if str(row.get("engine_schema") or "").startswith("aits_local_engine_multi_head")
            and task in set(row.get("supported_tasks") or [])
            and row.get("safe_for_live_decision") is False
            and row.get("live_decision_enabled") is False
        ]
        if task_candidates:
            metadata = task_candidates[-1]
    if not metadata:
        latest_attempt = registry.load_latest_training_attempt()
        reason = (
            "local_model_not_trained"
            if latest_attempt and not latest_attempt.get("trained")
            else "local_model_artifact_missing"
        )
        return {
            "status": "unavailable",
            "reason": reason,
            "metadata": latest_attempt,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
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
    legacy_bundle_valid = isinstance(bundle, dict) and isinstance(bundle.get("models"), dict)
    multi_head_bundle_valid = bool(
        isinstance(bundle, dict)
        and bundle.get("schema") == "aits_local_engine_multi_head_bundle.v1"
        and bundle.get("multi_head_model") is not None
    )
    if not legacy_bundle_valid and not multi_head_bundle_valid:
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
    guard = dict(value.get("sell_unit_guard") or value.get("risk") or {})
    candidates = value.get("candidates") or []
    candidate_context = dict(candidates) if isinstance(candidates, dict) else {}
    candidate_count = len(candidates) if isinstance(candidates, (list, tuple)) else len(candidates) if isinstance(candidates, dict) else 0
    total_asset = _numeric(portfolio, "total_asset_krw")
    available = _numeric(portfolio, "available_krw")
    exposure = _numeric(portfolio, "exposure_for_cap")
    current_positions = portfolio.get("current_positions")
    managed_pool_symbols = portfolio.get("managed_pool_symbols")
    position_count = _numeric(portfolio, "position_count", "holding_count")
    if position_count is None and isinstance(current_positions, (list, tuple, set)):
        position_count = float(len(current_positions))
    managed_pool_count = _numeric(portfolio, "managed_pool_count")
    if managed_pool_count is None and isinstance(managed_pool_symbols, (list, tuple, set)):
        managed_pool_count = float(len(managed_pool_symbols))
    macd = indicators.get("macd")
    if isinstance(macd, dict):
        macd = _first(macd, "macd", "value", "line")
    valuation_unit_mismatch = _first(guard, "valuation_unit_mismatch")
    if valuation_unit_mismatch is None:
        valuation_unit_mismatch = _first(position, "valuation_unit_mismatch")
    opportunity_gap = _numeric(candidate_context, "opportunity_gap_change", "opportunity_score_gap", "opportunity_gap")
    if opportunity_gap is None:
        opportunity_gap = _numeric(value, "opportunity_gap_change", "opportunity_score_gap", "opportunity_gap")
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
            "position_count": position_count,
            "managed_pool_count": managed_pool_count if managed_pool_count is not None else float(candidate_count),
            "cash_ratio": _numeric(portfolio, "cash_ratio") or (available / total_asset if total_asset and available is not None else None),
            "exposure_ratio": _numeric(portfolio, "exposure_ratio") or (exposure / total_asset if total_asset and exposure is not None else None),
        },
        "risk_features": {
            "sell_unit_guard_passed": valuation_unit_mismatch is False if isinstance(valuation_unit_mismatch, bool) else None,
            "valuation_unit_mismatch": valuation_unit_mismatch if isinstance(valuation_unit_mismatch, bool) else None,
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
            "opportunity_gap_change": opportunity_gap,
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
    source_task = str(context.get("task") or "")
    scope = str(context.get("symbol") or context.get("scope") or "PORTFOLIO")
    model_task = source_task
    if source_task == "ai_redecision":
        model_task = "portfolio_management_decision" if scope == "PORTFOLIO" else "position_management_decision"
    loaded = load_latest_local_model(task=model_task)
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
        "local_model_metadata": metadata,
    }
    if loaded.get("status") != "available":
        return base
    feature_record = build_local_model_feature_record(context, manifest_summary=manifest_summary, local_decision=local_decision)
    grade = str(feature_record.get("feature_quality_grade") or "F")
    feature_vector = dict(feature_record.get("feature_vector") or {})
    multi_head_feature_context = {
        "market": dict(feature_vector.get("market_features") or {}),
        "indicators": dict(feature_vector.get("indicator_features") or {}),
        "position": dict(feature_vector.get("position_features") or {}),
        "portfolio": dict(feature_vector.get("portfolio_features") or {}),
        "risk": dict(feature_vector.get("risk_features") or {}),
        "provider": dict(feature_vector.get("provider_features") or {}),
        "opportunity": dict(feature_vector.get("opportunity_features") or {}),
        "data_quality": dict(feature_vector.get("data_quality_features") or {}),
    }
    base.update({"local_model_source_task": source_task, "local_model_task": model_task})
    task_provenance = build_training_eligibility_provenance(
        task=model_task,
        scope_type="portfolio" if scope == "PORTFOLIO" else "position",
        scope=str(context.get("symbol") or context.get("scope") or "PORTFOLIO"),
        symbol=str(context.get("symbol") or ""),
        provider_source="local_model",
        final_action=str(local_decision.get("action") or "wait"),
        feature_context=multi_head_feature_context,
        payload_quality={"payload_quality_grade": grade},
    )
    critical_missing = list(task_provenance.get("missing_fields") or [])
    if grade not in QUALITY_FACTORS or critical_missing:
        blocker = "critical_model_feature_missing" if critical_missing else "local_model_feature_quality_too_low"
        return {**base, "local_model_prediction_attempted": True, "local_model_prediction_blocker": blocker,
                "local_model_feature_schema_compatible": True, "local_model_feature_quality_checked": True,
                "local_model_missing_features": critical_missing}
    bundle = dict(loaded.get("bundle") or {})
    multi_head_model = bundle.get("multi_head_model")
    if bundle.get("schema") == "aits_local_engine_multi_head_bundle.v1" and multi_head_model is not None:
        task = model_task
        multi = multi_head_model.predict(
            feature_context=multi_head_feature_context,
            task=task,
            scope=scope,
            quality_grade=grade,
        )
        if multi.get("status") != "available":
            return {
                **base,
                "local_model_prediction_attempted": True,
                "local_model_prediction_blocker": str(multi.get("blocker") or "multi_head_prediction_unavailable"),
                "local_model_feature_schema_compatible": True,
                "local_model_feature_quality_checked": True,
                "local_model_abstain_required": bool(multi.get("abstain_required")),
                "local_model_abstain_reason": str(multi.get("abstain_reason") or ""),
            }
        action = str(multi.get("action") or "").lower()
        confidence = _number(multi.get("calibrated_confidence"))
        if action not in MODEL_ACTIONS or confidence is None:
            return {
                **base,
                "local_model_prediction_attempted": True,
                "local_model_prediction_blocker": "multi_head_output_contract_invalid",
                "local_model_feature_schema_compatible": True,
                "local_model_feature_quality_checked": True,
            }
        live_allowed = bool(base["local_model_safe_for_live_decision"] and base["local_model_live_decision_enabled"])
        blockers = list(multi.get("risk_blockers") or [])
        if not live_allowed:
            blockers.append("local_model_live_disabled_by_registry")
        evidence = [{"type": "payload_quality", "grade": grade}]
        evidence.extend(
            {"type": "feature", **dict(item)} for item in (multi.get("evidence_summary") or []) if isinstance(item, dict)
        )
        candidate = build_local_engine_decision_candidate(
            task=task,
            scope=scope,
            action=action,
            confidence=confidence,
            reason_ko=str(multi.get("reason_ko") or ""),
            eta_seconds=int(multi.get("eta_seconds") or 0),
            blockers=blockers,
            evidence=evidence,
            safe_for_live_decision=base["local_model_safe_for_live_decision"],
            live_decision_enabled=base["local_model_live_decision_enabled"],
            confidence_calibrated=str(multi.get("calibration_method") or "") == "empirical_bucket_shrinkage",
            risk_level=str(multi.get("risk_level") or "unknown"),
            escalation_required=bool(multi.get("escalation_required")),
            escalation_reason=str(multi.get("escalation_reason") or ""),
            eta_policy=str(multi.get("eta_reason") or ""),
            invalidation_conditions=list(multi.get("invalidation_conditions") or []),
            training_source={
                "model_id": str(metadata.get("model_id") or ""),
                "engine_schema": str(metadata.get("engine_schema") or ""),
                "feature_schema": str(metadata.get("feature_schema") or feature_record.get("schema") or ""),
            },
            action_probabilities=dict(multi.get("action_probabilities") or {}),
            action_margin=_number(multi.get("action_margin")),
            action_supported=bool(multi.get("action_supported")),
            unsupported_action_reasons=list(multi.get("unsupported_action_reasons") or []),
            raw_confidence=_number(multi.get("raw_confidence")),
            calibration_method=str(multi.get("calibration_method") or ""),
            confidence_bucket=str(multi.get("confidence_bucket") or ""),
            confidence_reliability=str(multi.get("confidence_reliability") or ""),
            abstain_required=bool(multi.get("abstain_required")),
            abstain_reason=str(multi.get("abstain_reason") or ""),
            risk_score=_number(multi.get("risk_score")),
            risk_factors=list(multi.get("risk_factors") or []),
            risk_blockers=list(multi.get("risk_blockers") or []),
            escalation_target=str(multi.get("escalation_target") or ""),
            external_confirmation_required=bool(multi.get("external_confirmation_required")),
            eta_bucket=int(multi.get("eta_bucket") or 0),
            eta_reason=str(multi.get("eta_reason") or ""),
            monitoring_priority=str(multi.get("monitoring_priority") or ""),
            invalidation_supported=bool(multi.get("invalidation_supported")),
            invalidation_missing_reason=str(multi.get("invalidation_missing_reason") or ""),
            evidence_summary=list(multi.get("evidence_summary") or []),
            risk_summary_ko=str(multi.get("risk_summary_ko") or ""),
            reason_template_id=str(multi.get("reason_template_id") or ""),
            provider_route_recommendation=str(multi.get("provider_route_recommendation") or ""),
        )
        candidate["source_task"] = source_task
        candidate["model_task"] = model_task
        candidate.update({"execution_plan": {}, "risk_notes": ",".join(blockers), "sell_ratio": 0.0, "buy_amount_krw": 0.0})
        return {
            **base,
            "local_model_prediction_attempted": True,
            "local_model_prediction_available": True,
            "local_model_prediction_blocker": "" if live_allowed else "local_model_live_disabled_by_registry",
            "local_model_feature_schema_compatible": True,
            "local_model_feature_quality_checked": True,
            "local_model_feature_quality_grade": grade,
            "local_model_multi_head_ready": True,
            "local_model_source_task": source_task,
            "local_model_task": model_task,
            "model_recommended_action": action,
            "model_action_probabilities": dict(multi.get("action_probabilities") or {}),
            "model_action_quality_score": _number(multi.get("raw_confidence")),
            "model_provider_value_score": None,
            "model_risk_score": _number(multi.get("risk_score")),
            "model_confidence": confidence,
            "model_reason_ko": str(multi.get("reason_ko") or ""),
            "model_blockers": blockers,
            "model_decision_candidate": candidate,
            "local_model_live_allowed": live_allowed,
            "local_model_requires_external_confirmation": bool(multi.get("external_confirmation_required")),
        }
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
    candidate = build_local_engine_decision_candidate(
        task=str(context.get("task") or ""),
        scope=str(context.get("symbol") or context.get("scope") or "PORTFOLIO"),
        action=action,
        confidence=confidence,
        reason_ko=reason,
        eta_seconds=int(_number(local_decision.get("eta_seconds")) or 300),
        blockers=blockers,
        evidence=[
            {"type": "payload_quality", "grade": grade},
            {"type": "model_score", "name": "action_quality_score", "value": action_score},
            {"type": "model_score", "name": "risk_adjusted_score", "value": risk_score},
        ],
        safe_for_live_decision=base["local_model_safe_for_live_decision"],
        live_decision_enabled=base["local_model_live_decision_enabled"],
        escalation_required=bool(not live_allowed or action in ORDER_ACTIONS),
        escalation_reason=(
            "local_engine_order_action_requires_external_confirmation"
            if action in ORDER_ACTIONS
            else "local_engine_live_disabled_by_registry"
        ),
        risk_level="low" if risk_score >= 0.7 else ("medium" if risk_score >= 0.4 else "high"),
        invalidation_conditions=list(local_decision.get("invalidation_conditions") or []),
        training_source={
            "model_id": str(metadata.get("model_id") or ""),
            "feature_schema": str(feature_record.get("schema") or ""),
        },
    )
    candidate.update(
        {
            "execution_plan": {},
            "risk_notes": ",".join(blockers),
            "sell_ratio": 0.0,
            "buy_amount_krw": 0.0,
        }
    )
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
