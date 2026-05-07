from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any


ALLOWED_AI_STATES = {
    "idle",
    "watching",
    "entry_wait",
    "entry_ready",
    "holding",
    "reduce_watch",
    "exit_watch",
    "risk_off",
    "removed",
    "long_watch",
}


AI_STATE_KO_LABELS = {
    "idle": "대기",
    "watching": "관찰중",
    "entry_wait": "진입 대기",
    "entry_ready": "진입 준비",
    "holding": "보유중",
    "reduce_watch": "비중 축소 관찰",
    "exit_watch": "매도 관찰",
    "risk_off": "리스크 회피",
    "removed": "관리 제외",
    "long_watch": "장기 관찰",
}


@dataclass
class AIStateSnapshot:
    symbol: str
    state: str
    previous_state: str
    reason: str
    eta_minutes: int
    scenario: str
    confidence: float
    updated_at: str
    metadata: dict = field(default_factory=dict)


class AIStateMachine:
    """State-only AI operation skeleton. It does not execute orders."""

    _NEXT_ACTION_STATE_MAP = {
        "watch": "watching",
        "wait": "entry_wait",
        "buy": "entry_ready",
        "hold": "holding",
        "reduce": "reduce_watch",
        "sell": "exit_watch",
        "remove": "removed",
    }

    def __init__(self) -> None:
        self._log = logging.getLogger("aits")

    def normalize_state(self, state: str) -> str:
        normalized = str(state or "").strip().lower()
        return normalized if normalized in ALLOWED_AI_STATES else "idle"

    def transition(
        self,
        symbol: str,
        current_state: str,
        ai_shadow_record: dict,
    ) -> AIStateSnapshot:
        try:
            sr = ai_shadow_record if isinstance(ai_shadow_record, dict) else {}
            previous_state = self.normalize_state(current_state)
            symbol_text = str(symbol or sr.get("symbol") or sr.get("market") or "").strip()

            eta = sr.get("eta") if isinstance(sr.get("eta"), dict) else {}
            eta_minutes = self._safe_int(eta.get("remaining_minutes"), 0)
            next_action = str(sr.get("next_action") or "").strip().lower()
            pool_action = sr.get("pool_action") if isinstance(sr.get("pool_action"), dict) else {}
            pool_action_name = str(pool_action.get("action") or "").strip().lower()

            if pool_action_name == "remove":
                next_state = "removed"
                reason = "pool_action.remove"
            elif eta_minutes >= 10080:
                next_state = "long_watch"
                reason = "eta.long_watch"
            else:
                next_state = self._NEXT_ACTION_STATE_MAP.get(next_action, "idle")
                reason = f"next_action.{next_action or 'fallback'}"

            scenario = self._extract_scenario(sr)
            confidence = self._extract_confidence(sr)
            metadata = {
                "suggestion_only": True,
                "applied_to_action": False,
                "next_action": next_action,
                "pool_action": pool_action_name,
            }

            snapshot = AIStateSnapshot(
                symbol=symbol_text,
                state=self.normalize_state(next_state),
                previous_state=previous_state,
                reason=reason,
                eta_minutes=eta_minutes,
                scenario=scenario,
                confidence=confidence,
                updated_at=self._now_iso(),
                metadata=metadata,
            )
            self._log_transition(snapshot)
            return snapshot
        except Exception:
            snapshot = AIStateSnapshot(
                symbol=str(symbol or "").strip(),
                state="idle",
                previous_state=self.normalize_state(current_state),
                reason="fallback",
                eta_minutes=0,
                scenario="",
                confidence=0.0,
                updated_at=self._now_iso(),
                metadata={
                    "suggestion_only": True,
                    "applied_to_action": False,
                },
            )
            self._log_transition(snapshot)
            return snapshot

    def _extract_scenario(self, sr: dict[str, Any]) -> str:
        scenario = sr.get("scenario") if isinstance(sr.get("scenario"), dict) else {}
        if isinstance(scenario, dict):
            return str(
                scenario.get("label_ko")
                or scenario.get("name")
                or scenario.get("type")
                or ""
            ).strip()
        return str(sr.get("scenario") or "").strip()

    def _extract_confidence(self, sr: dict[str, Any]) -> float:
        scenario = sr.get("scenario") if isinstance(sr.get("scenario"), dict) else {}
        value = scenario.get("confidence") if isinstance(scenario, dict) else sr.get("confidence")
        try:
            return max(0.0, min(1.0, float(value or 0.0)))
        except Exception:
            return 0.0

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_transition(self, snapshot: AIStateSnapshot) -> None:
        self._log.info(
            "[AITS][AIStateMachine] state_transition | symbol=%s | from=%s | to=%s | reason=%s",
            snapshot.symbol,
            snapshot.previous_state,
            snapshot.state,
            snapshot.reason,
        )


def _format_eta_minutes_for_ui(eta_minutes: int) -> str:
    try:
        minutes = int(float(eta_minutes or 0))
    except Exception:
        minutes = 0

    if minutes <= 0:
        return "-"
    if minutes >= 10080:
        return "장기 관찰"
    if minutes >= 1440:
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        return f"{days}일 {hours}시간"
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}시간 {mins}분"
    return f"{minutes}분"


def format_state_snapshot_for_ui(snapshot: AIStateSnapshot) -> dict:
    try:
        state = AIStateMachine().normalize_state(getattr(snapshot, "state", "idle"))
        previous_state = AIStateMachine().normalize_state(
            getattr(snapshot, "previous_state", "idle")
        )
        eta_text = _format_eta_minutes_for_ui(getattr(snapshot, "eta_minutes", 0))
        scenario = str(getattr(snapshot, "scenario", "") or "").strip()
        confidence = float(getattr(snapshot, "confidence", 0.0) or 0.0)
        confidence_pct = int(round(max(0.0, min(1.0, confidence)) * 100.0))
        state_ko = AI_STATE_KO_LABELS.get(state, AI_STATE_KO_LABELS["idle"])
        previous_state_ko = AI_STATE_KO_LABELS.get(
            previous_state,
            AI_STATE_KO_LABELS["idle"],
        )
        status_parts = [state_ko]
        if scenario:
            status_parts.append(scenario)
        if eta_text:
            status_parts.append(eta_text)

        result = {
            "symbol": str(getattr(snapshot, "symbol", "") or "").strip(),
            "state": state,
            "state_ko": state_ko,
            "previous_state": previous_state,
            "previous_state_ko": previous_state_ko,
            "scenario": scenario,
            "confidence_pct": confidence_pct,
            "eta_text": eta_text,
            "reason": str(getattr(snapshot, "reason", "") or "").strip(),
            "status_line": " · ".join(status_parts),
        }
    except Exception:
        result = {
            "symbol": "",
            "state": "idle",
            "state_ko": AI_STATE_KO_LABELS["idle"],
            "previous_state": "idle",
            "previous_state_ko": AI_STATE_KO_LABELS["idle"],
            "scenario": "",
            "confidence_pct": 0,
            "eta_text": "-",
            "reason": "fallback",
            "status_line": "대기 · -",
        }

    logging.getLogger("aits").info(
        "[AITS][AIStateMachine] state_ui_formatted | symbol=%s | state=%s | eta=%s",
        result["symbol"],
        result["state"],
        result["eta_text"],
    )
    return result


def build_sample_state_pipeline_result() -> dict:
    symbol = "KRW-BTC"
    # Use hardcoded sample shadow_record to avoid external API calls
    shadow_record = {
        'next_action': 'watch',
        'eta': {'remaining_minutes': 30},
        'scenario': {'label_ko': '횡보 관찰형'},
        'confidence': 0.7
    }
    snapshot = None
    suggestion = "샘플 제안"
    next_action = "watch"

    snapshot = AIStateMachine().transition(
        symbol=symbol,
        current_state="idle",
        ai_shadow_record=shadow_record,
    )

    state_snapshot_ready = isinstance(snapshot, AIStateSnapshot)
    shadow_record_ready = isinstance(shadow_record, dict) and bool(shadow_record)
    output = {
        "symbol": symbol,
        "shadow_record_ready": shadow_record_ready,
        "state_snapshot_ready": state_snapshot_ready,
        "previous_state": snapshot.previous_state if state_snapshot_ready else "idle",
        "state": snapshot.state if state_snapshot_ready else "idle",
        "eta_minutes": snapshot.eta_minutes if state_snapshot_ready else 0,
        "scenario": snapshot.scenario if state_snapshot_ready else "",
        "suggestion": suggestion,
        "next_action": next_action,
        "applied": False,
        "applied_to_action": False,
        "ui": format_state_snapshot_for_ui(snapshot) if state_snapshot_ready else {},
    }

    logging.getLogger("aits").info(
        "[AITS][AIStateMachine] sample_state_pipeline_built | symbol=%s | state=%s | suggestion=%s",
        output["symbol"],
        output["state"],
        output["suggestion"],
    )
    return output


__all__ = [
    "AIStateSnapshot",
    "AIStateMachine",
    "ALLOWED_AI_STATES",
    "AI_STATE_KO_LABELS",
    "build_sample_state_pipeline_result",
    "format_state_snapshot_for_ui",
]
