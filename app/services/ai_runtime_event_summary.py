from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_runtime_event import build_sample_runtime_event


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
    }


@dataclass
class AIRuntimeEventSummaryReport:
    total_events: int
    warnings: int
    errors: int
    critical: int
    dominant_event_type: str
    summary_line: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeEventSummaryBuilder:
    """Builds a compact event stream summary report."""

    def build_report(self, events: list) -> AIRuntimeEventSummaryReport:
        payloads = list(events or [])
        by_type: dict[str, int] = {}
        warnings = 0
        errors = 0
        critical = 0
        for event in payloads:
            event_type = str(self._get(event, "event_type", "runtime_event") or "runtime_event")
            severity = str(self._get(event, "severity", "info") or "info")
            by_type[event_type] = by_type.get(event_type, 0) + 1
            if severity == "warning":
                warnings += 1
            elif severity == "error":
                errors += 1
            elif severity == "critical":
                critical += 1
        dominant = max(by_type.items(), key=lambda item: item[1])[0] if by_type else "-"
        total = len(payloads)
        summary_line = (
            f"events={total} | warnings={warnings} | errors={errors} | "
            f"critical={critical} | dominant={dominant}"
        )
        return AIRuntimeEventSummaryReport(
            total_events=total,
            warnings=warnings,
            errors=errors,
            critical=critical,
            dominant_event_type=dominant,
            summary_line=summary_line,
            metadata=_metadata(),
        )

    def _get(self, value: Any, name: str, fallback: Any) -> Any:
        if isinstance(value, dict):
            return value.get(name, fallback)
        return getattr(value, name, fallback)


def build_sample_event_summary_report() -> AIRuntimeEventSummaryReport:
    return AIRuntimeEventSummaryBuilder().build_report([build_sample_runtime_event()])


__all__ = [
    "AIRuntimeEventSummaryReport",
    "AIRuntimeEventSummaryBuilder",
    "build_sample_event_summary_report",
]
