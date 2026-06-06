"""Packaged LightGBM dependency probe for AITS.

This probe is intentionally standalone. It checks LightGBM/scipy import,
dependency gate reporting, and a tiny real-trainer smoke without connecting to
UI, Router, Runtime, Execution, Order, Risk Guard, or live trading.
"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_packaged_lightgbm_probe() -> dict:
    """Run import, dependency gate, and tiny trainer checks."""

    report = {
        "schema": "aits_packaged_lightgbm_probe.v1",
        "created_at": utc_now_iso(),
        "environment": {
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "imports": {
            "lightgbm": _import_version("lightgbm"),
            "scipy": _import_version("scipy"),
        },
        "dependency_gate": {
            "ok": False,
            "importable": False,
            "version": None,
            "error": None,
        },
        "real_trainer_smoke": {
            "ok": False,
            "train_status": None,
            "model_file_created": False,
            "prediction_executed": False,
            "error": None,
        },
        "safety": {
            "router_connected": False,
            "execution_connected": False,
            "ui_connected": False,
            "training_scope": "tiny_probe_only",
            "model_auto_approved": False,
        },
    }

    report["dependency_gate"] = _run_dependency_gate_probe()
    report["real_trainer_smoke"] = _run_real_trainer_smoke()
    return report


def main() -> None:
    print(json.dumps(run_packaged_lightgbm_probe(), ensure_ascii=False, sort_keys=True))


def _import_version(module_name: str) -> dict:
    try:
        module = __import__(module_name)
        return {
            "ok": True,
            "version": str(getattr(module, "__version__", "")) or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_dependency_gate_probe() -> dict:
    try:
        from app.learning.lightgbm_dependency_gate import (
            build_lightgbm_dependency_gate_report,
        )

        gate = build_lightgbm_dependency_gate_report()
        dependency = gate.get("dependency", {})
        return {
            "ok": bool(dependency.get("importable")),
            "importable": bool(dependency.get("importable")),
            "version": dependency.get("version"),
            "error": dependency.get("import_error"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "importable": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_real_trainer_smoke() -> dict:
    try:
        from app.learning.lightgbm_real_trainer import (
            train_lightgbm_classifier_prototype,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = train_lightgbm_classifier_prototype(
                _tiny_rows(),
                output_dir=Path(temp_dir) / "trainer",
                num_boost_round=5,
            )
        safety = result.get("safety", {})
        training = result.get("training", {})
        prediction = result.get("prediction", {})
        artifact = result.get("artifact", {})
        return {
            "ok": training.get("status") == "success"
            and bool(artifact.get("model_file_created"))
            and bool(prediction.get("executed"))
            and safety.get("router_connected") is False
            and safety.get("execution_connected") is False,
            "train_status": training.get("status"),
            "model_file_created": bool(artifact.get("model_file_created")),
            "prediction_executed": bool(prediction.get("executed")),
            "error": training.get("error"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "train_status": None,
            "model_file_created": False,
            "prediction_executed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _tiny_rows() -> list[dict]:
    return [
        _make_row(1, "good", 42.0, 0.72, "breakout"),
        _make_row(2, "good", 45.0, 0.68, "breakout"),
        _make_row(3, "neutral", 55.0, 0.44, "sideways"),
        _make_row(4, "neutral", 58.0, 0.39, "sideways"),
    ]


def _make_row(i: int, label: str, rsi: float, score: float, regime: str) -> dict:
    return {
        "schema": "aits_lightgbm_dataset_row.v1",
        "row_id": f"row-{i:03d}",
        "source_journal_id": f"journal-{i:03d}",
        "created_at": "2026-06-05T00:00:00+00:00",
        "symbol": "KRW-BTC",
        "timeframe": "5m",
        "provider": "openai" if i % 2 else "gemini",
        "engine_role": "preview",
        "features": {
            "market": {"market_regime": regime, "price_change_5m": score},
            "technical": {"rsi": rsi, "macd": score / 10.0},
            "candidate": {"basic_score": score},
            "portfolio": {"holding_state": "not_holding"},
            "ai_output": {"ai_action": "observe", "ai_confidence": 0.6 + score / 10.0},
            "router": {"final_action": "wait", "router_allowed": False},
        },
        "labels": {
            "label_ready": True,
            "label_action_quality": label,
            "label_pnl_bucket": "flat",
        },
        "targets": {
            "ranker_target": score,
            "classifier_target": label,
            "regressor_target": score / 10.0,
        },
        "sample_weight": 1.0,
        "quality": {
            "usable_for_training": True,
            "usable_for_inference_preview": True,
            "excluded_reason": None,
            "leakage_checked": True,
        },
        "meta": {"note": "safe"},
    }


if __name__ == "__main__":
    main()
