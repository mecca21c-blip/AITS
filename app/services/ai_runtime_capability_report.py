from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from app.services.ai_runtime_capability_registry import AIRuntimeCapabilityRegistry
from app.services.ai_runtime_compatibility_checker import AIRuntimeCompatibilityChecker
from app.services.ai_runtime_feature_matrix import AIRuntimeFeatureMatrixBuilder


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
        "capability_only": True,
    }


@dataclass
class AIRuntimeCapabilityReport:
    provider: str
    model: str
    compatible: bool
    enabled_count: int
    disabled_count: int
    summary_line: str
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeCapabilityReportBuilder:
    """Builds compact capability reports from profile/matrix/compatibility results."""

    def build_report(self, profile=None, matrix=None, compatibility=None) -> AIRuntimeCapabilityReport:
        p = self._to_dict(profile)
        m = self._to_dict(matrix)
        c = self._to_dict(compatibility)
        provider = str(p.get("provider") or m.get("provider") or c.get("provider") or "unknown")
        model = str(p.get("model") or m.get("model") or c.get("model") or "-")
        compatible = bool(c.get("compatible", False))
        enabled_count = int(m.get("enabled_count") or 0)
        disabled_count = int(m.get("disabled_count") or 0)
        warnings: list[str] = []
        missing = c.get("missing_capabilities")
        if isinstance(missing, list) and missing:
            warnings.append("missing: " + ", ".join(str(item) for item in missing))
        if not compatible:
            warnings.append(str(c.get("reason") or "incompatible"))
        summary_line = (
            f"{provider}/{model} | compatible={compatible} | "
            f"enabled={enabled_count} | disabled={disabled_count}"
        )
        return AIRuntimeCapabilityReport(
            provider=provider,
            model=model,
            compatible=compatible,
            enabled_count=enabled_count,
            disabled_count=disabled_count,
            summary_line=summary_line,
            warnings=warnings,
            metadata=_metadata(),
        )

    def _to_dict(self, value: Any) -> dict:
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        return {}


def build_sample_capability_report() -> AIRuntimeCapabilityReport:
    profile = AIRuntimeCapabilityRegistry().get_profile("mock", "mock")
    matrix = AIRuntimeFeatureMatrixBuilder().build_matrix(profile)
    compatibility = AIRuntimeCompatibilityChecker().check("mock", "mock", "one_shot_dry_run")
    return AIRuntimeCapabilityReportBuilder().build_report(profile, matrix, compatibility)


__all__ = [
    "AIRuntimeCapabilityReport",
    "AIRuntimeCapabilityReportBuilder",
    "build_sample_capability_report",
]
