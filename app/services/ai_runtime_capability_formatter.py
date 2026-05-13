from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.services.ai_runtime_capability_report import build_sample_capability_report
from app.services.ai_runtime_feature_matrix import build_sample_feature_matrix


class AIRuntimeCapabilityFormatter:
    """Formats capability report and matrix for UI-ready consumption."""

    def format_report(self, report, matrix=None) -> dict:
        r = self._to_dict(report)
        m = self._to_dict(matrix)
        badges = self._badges(m.get("features") if isinstance(m.get("features"), dict) else {})
        features = [
            {"name": name, "enabled": bool(value)}
            for name, value in (m.get("features") or {}).items()
        ]
        return {
            "title": "AI Runtime Capability",
            "summary": str(r.get("summary_line") or ""),
            "badges": badges,
            "features": features,
            "metadata": dict(r.get("metadata") or {}),
        }

    def _badges(self, features: dict) -> list[str]:
        labels = {
            "dry_run": "Dry-run",
            "live_one_shot": "Live One-shot",
            "structured_json": "Structured JSON",
            "state_context": "State Context",
            "local_runtime": "Local Runtime",
            "observation": "Observation",
            "replay": "Replay",
            "snapshot_export": "Export-ready",
        }
        return [label for key, label in labels.items() if bool(features.get(key, False))]

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_capability_format() -> dict:
    return AIRuntimeCapabilityFormatter().format_report(
        build_sample_capability_report(),
        build_sample_feature_matrix(),
    )


__all__ = [
    "AIRuntimeCapabilityFormatter",
    "build_sample_capability_format",
]
