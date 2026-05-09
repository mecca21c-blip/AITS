from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class AIRuntimeUIFormatter:
    """Formats runtime UI bundles into compact UI-ready dictionaries."""

    def format_bundle(self, bundle) -> dict:
        payload = self._to_dict(bundle)
        diagnosis = str(payload.get("diagnosis") or payload.get("health_label") or "관찰 필요")
        risk_level = self._risk_level(diagnosis)
        provider = str(payload.get("provider") or "unknown")
        status = str(payload.get("status") or "-")
        return {
            "header": f"{provider} runtime session",
            "status_line": str(payload.get("summary_line") or f"{provider} | {status} | {diagnosis}"),
            "badges": list(payload.get("badges") or []),
            "risk_level": risk_level,
            "compact_rows": [
                {"label": "Provider", "value": provider},
                {"label": "Session", "value": str(payload.get("session_id") or "-")},
                {"label": "Diagnosis", "value": diagnosis},
                {"label": "Quality", "value": f"{self._safe_float(payload.get('quality_score')):.2f}"},
                {"label": "Observation", "value": str(payload.get("observation_summary") or "-")},
            ],
            "metadata": dict(payload.get("metadata") or {}),
        }

    def _risk_level(self, diagnosis: str) -> str:
        if diagnosis == "정상":
            return "low"
        if diagnosis == "관찰 필요":
            return "medium"
        if diagnosis in ("불안정", "런타임 불안정"):
            return "high"
        if diagnosis == "차단 필요":
            return "critical"
        return "medium"

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_sample_runtime_ui_format() -> dict:
    from app.services.ai_runtime_ui_bundle import build_sample_runtime_ui_bundle

    return AIRuntimeUIFormatter().format_bundle(build_sample_runtime_ui_bundle())


__all__ = [
    "AIRuntimeUIFormatter",
    "build_sample_runtime_ui_format",
]
