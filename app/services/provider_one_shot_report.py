from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderOneShotReport:
    provider: str
    parsed_valid: bool
    next_action: str
    scenario: str
    eta: str
    state: str
    reliability_hint: str
    summary_line: str
    metadata: dict = field(default_factory=dict)


class ProviderOneShotReportBuilder:
    """Builds compact report data from a shadow-only one-shot result."""

    def build_report(
        self,
        one_shot_result: dict,
        reliability_score: Any | None = None,
        runtime_status: Any | None = None,
    ) -> ProviderOneShotReport:
        result = dict(one_shot_result or {})
        provider = str(result.get("provider") or "-")
        parsed_valid = bool(result.get("parsed_valid"))
        next_action = str(result.get("next_action") or "wait")
        scenario = self._extract_scenario(result)
        eta = self._extract_eta(result)
        state = str(result.get("state") or "-")
        reliability_hint = self._extract_reliability(reliability_score)
        summary_line = " | ".join(
            part for part in [provider, next_action, scenario, state] if part and part != "-"
        )
        metadata = {
            "runtime_ready": bool(getattr(runtime_status, "runtime_ready", False)),
            "runtime_reason": str(getattr(runtime_status, "reason", "") or ""),
            "real_order": False,
            "virtual_only": False,
            "shadow_only": True,
            "one_shot": True,
            "applied": False,
            "applied_to_action": False,
            "submitted": 0,
        }
        return ProviderOneShotReport(
            provider=provider,
            parsed_valid=parsed_valid,
            next_action=next_action,
            scenario=scenario,
            eta=eta,
            state=state,
            reliability_hint=reliability_hint,
            summary_line=summary_line or "-",
            metadata=metadata,
        )

    def _extract_scenario(self, result: dict) -> str:
        scenario = result.get("scenario")
        if isinstance(scenario, dict):
            return str(scenario.get("label_ko") or scenario.get("name") or "-")
        if scenario:
            return str(scenario)
        parts = self._split_status_line(str(result.get("status_line") or ""))
        return parts[1] if len(parts) >= 2 else "-"

    def _extract_eta(self, result: dict) -> str:
        eta = result.get("eta")
        if isinstance(eta, dict):
            value = eta.get("remaining_minutes")
            return "-" if value is None else str(value)
        if eta:
            return str(eta)
        eta_text = str(result.get("eta_text") or "")
        if eta_text:
            return eta_text
        parts = self._split_status_line(str(result.get("status_line") or ""))
        return parts[2] if len(parts) >= 3 else "-"

    def _split_status_line(self, status_line: str) -> list[str]:
        text = str(status_line or "")
        separator = "·" if "·" in text else "|"
        return [part.strip() for part in text.split(separator) if part.strip()]

    def _extract_reliability(self, reliability_score: Any | None) -> str:
        if reliability_score is None:
            return "-"
        if isinstance(reliability_score, dict):
            value = reliability_score.get("reliability_score")
        else:
            value = getattr(reliability_score, "reliability_score", None)
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "-"


__all__ = ["ProviderOneShotReport", "ProviderOneShotReportBuilder"]
