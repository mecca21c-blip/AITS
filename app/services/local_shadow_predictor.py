from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_model_training import AITSLocalModelTrainingPipeline


def load_latest_local_model(root: Path | str = Path("data") / "local_models") -> dict:
    metadata = AITSLocalModelRegistry(root).latest_shadow_model()
    if not metadata:
        return {
            "status": "unavailable",
            "reason": "no_trained_shadow_model",
            "shadow_only": True,
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
            "shadow_only": True,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
        }
    if not isinstance(bundle, dict) or bundle.get("safe_for_live_decision") or bundle.get("live_decision_enabled"):
        return {
            "status": "unavailable",
            "reason": "model_safety_contract_invalid",
            "shadow_only": True,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
        }
    return {
        "status": "available",
        "metadata": metadata,
        "bundle": bundle,
        "shadow_only": True,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
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


def _predict_target(feature_record: dict, target: str) -> dict[str, Any]:
    loaded = load_latest_local_model()
    if loaded.get("status") != "available":
        return loaded
    bundle = dict(loaded.get("bundle") or {})
    models = dict(bundle.get("models") or {})
    model = models.get(target)
    if model is None:
        return {
            "status": "unavailable",
            "reason": f"target_not_trained:{target}",
            "shadow_only": True,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
        }
    vector = _transform_feature_record(feature_record, bundle)
    try:
        prediction = float(model.predict(1)[0])
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"prediction_failed:{type(exc).__name__}",
            "shadow_only": True,
            "safe_for_live_decision": False,
            "live_decision_enabled": False,
        }
    return {
        "status": "available",
        "target": target,
        "score": prediction,
        "feature_count": len(vector),
        "model_id": str((loaded.get("metadata") or {}).get("model_id") or ""),
        "shadow_only": True,
        "safe_for_live_decision": False,
        "live_decision_enabled": False,
    }


def predict_local_action_quality(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "action_quality_score")


def predict_provider_value(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "provider_value_score")


def predict_risk_score(feature_record: dict) -> dict[str, Any]:
    return _predict_target(feature_record, "risk_adjusted_score")
