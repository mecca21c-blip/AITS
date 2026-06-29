from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LiveGuardedWindowConfig:
    window_id: str = ""
    duration_min: int = 120
    per_order_krw: float = 10000.0
    per_order_hard_cap_krw: float = 12000.0
    total_window_cap_krw: float = 20000.0
    max_order_count: int = 2
    min_order_interval_sec: int = 600
    symbol_allowlist: list[str] = field(default_factory=lambda: ["KRW-BTC"])
    side_allowlist: list[str] = field(default_factory=lambda: ["buy"])
    sell_allowed: bool = False
    cancel_allowed: bool = False
    retry_allowed: bool = False
    emergency_stop_required: bool = True
    incident_stop_required: bool = True
    approval_phrase_hash: str = ""
    created_at_utc: str = ""
    expires_at_utc: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "LiveGuardedWindowConfig":
        raw = data or {}
        return cls(
            window_id=str(raw.get("window_id") or "guarded-window-preflight"),
            duration_min=_safe_int(raw.get("duration_min"), 120),
            per_order_krw=_safe_float(raw.get("per_order_krw"), 10000.0),
            per_order_hard_cap_krw=_safe_float(raw.get("per_order_hard_cap_krw"), 12000.0),
            total_window_cap_krw=_safe_float(raw.get("total_window_cap_krw"), 20000.0),
            max_order_count=_safe_int(raw.get("max_order_count"), 2),
            min_order_interval_sec=_safe_int(raw.get("min_order_interval_sec"), 600),
            symbol_allowlist=[str(x).upper() for x in raw.get("symbol_allowlist", ["KRW-BTC"])],
            side_allowlist=[str(x).lower() for x in raw.get("side_allowlist", ["buy"])],
            sell_allowed=bool(raw.get("sell_allowed", False)),
            cancel_allowed=bool(raw.get("cancel_allowed", False)),
            retry_allowed=bool(raw.get("retry_allowed", False)),
            emergency_stop_required=bool(raw.get("emergency_stop_required", True)),
            incident_stop_required=bool(raw.get("incident_stop_required", True)),
            approval_phrase_hash=str(raw.get("approval_phrase_hash") or ""),
            created_at_utc=str(raw.get("created_at_utc") or _now_utc()),
            expires_at_utc=str(raw.get("expires_at_utc") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveGuardedWindowState:
    window_id: str = ""
    active: bool = False
    locked: bool = True
    started_at_utc: str = ""
    ended_at_utc: str = ""
    order_count: int = 0
    total_order_amount_krw: float = 0.0
    last_order_at_utc: str = ""
    order_uuids: list[str] = field(default_factory=list)
    incident_triggered: bool = False
    incident_report_path: str = ""
    relocked: bool = True
    duplicate_lock_ok: bool = True
    repeat_block_ok: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "LiveGuardedWindowState":
        raw = data or {}
        return cls(
            window_id=str(raw.get("window_id") or ""),
            active=bool(raw.get("active", False)),
            locked=bool(raw.get("locked", True)),
            started_at_utc=str(raw.get("started_at_utc") or ""),
            ended_at_utc=str(raw.get("ended_at_utc") or ""),
            order_count=_safe_int(raw.get("order_count"), 0),
            total_order_amount_krw=_safe_float(raw.get("total_order_amount_krw"), 0.0),
            last_order_at_utc=str(raw.get("last_order_at_utc") or ""),
            order_uuids=[str(x) for x in raw.get("order_uuids", [])],
            incident_triggered=bool(raw.get("incident_triggered", False)),
            incident_report_path=str(raw.get("incident_report_path") or ""),
            relocked=bool(raw.get("relocked", True)),
            duplicate_lock_ok=bool(raw.get("duplicate_lock_ok", True)),
            repeat_block_ok=bool(raw.get("repeat_block_ok", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveGuardedWindowCheckResult:
    allowed_to_start: bool = False
    locked: bool = True
    blocked_reason: str = ""
    severity: str = "info"
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    order_allowed: bool = False
    real_order: bool = False
    submitted: int = 0
    place_order_call_count: int = 0
    cancel_call_count: int = 0
    sell_call_count: int = 0
    retry_call_count: int = 0
    incident_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveGuardedWindow:
    """Pure read-only contract evaluator for a future live guarded window."""

    def evaluate_window_start(
        self,
        config: LiveGuardedWindowConfig | dict[str, Any],
        state: LiveGuardedWindowState | dict[str, Any] | None = None,
    ) -> LiveGuardedWindowCheckResult:
        cfg = config if isinstance(config, LiveGuardedWindowConfig) else LiveGuardedWindowConfig.from_mapping(config)
        st = state if isinstance(state, LiveGuardedWindowState) else LiveGuardedWindowState.from_mapping(state)
        reason = self._config_block_reason(cfg)
        if reason:
            return self._result(cfg, st, reason, severity="error", incident_required=False)
        if st.incident_triggered:
            return self._result(cfg, st, "incident_already_triggered", severity="critical", incident_required=True)
        if not st.relocked:
            return self._result(cfg, st, "relock_not_confirmed", severity="critical", incident_required=True)
        if not st.duplicate_lock_ok:
            return self._result(cfg, st, "duplicate_lock_not_confirmed", severity="critical", incident_required=True)
        if not st.repeat_block_ok:
            return self._result(cfg, st, "repeat_block_not_confirmed", severity="critical", incident_required=True)
        return self._result(cfg, st, "preflight_only_aits_on_not_clicked", severity="info")

    def evaluate_order_attempt(
        self,
        config: LiveGuardedWindowConfig | dict[str, Any],
        state: LiveGuardedWindowState | dict[str, Any] | None,
        candidate: dict[str, Any],
    ) -> LiveGuardedWindowCheckResult:
        cfg = config if isinstance(config, LiveGuardedWindowConfig) else LiveGuardedWindowConfig.from_mapping(config)
        st = state if isinstance(state, LiveGuardedWindowState) else LiveGuardedWindowState.from_mapping(state)
        reason = self._config_block_reason(cfg)
        if reason:
            return self._result(cfg, st, reason, severity="error", incident_required=False)

        side = str(candidate.get("side") or "").lower()
        symbol = str(candidate.get("symbol") or "").upper()
        amount = _safe_float(candidate.get("amount_krw"), 0.0)
        elapsed = _safe_float(candidate.get("elapsed_since_last_order_sec"), 999999.0)

        if bool(candidate.get("cancel_attempt", False)):
            return self._result(cfg, st, "cancel_attempt_blocked", severity="critical", incident_required=True)
        if bool(candidate.get("retry_attempt", False)):
            if str(candidate.get("normalized_order_state") or "") in {
                "unknown_requires_manual_review",
                "query_failed_no_retry",
            }:
                return self._result(cfg, st, "unknown_state_retry_blocked", severity="critical", incident_required=True)
            if not cfg.retry_allowed:
                return self._result(cfg, st, "retry_attempt_blocked", severity="critical", incident_required=True)
        if side == "sell" or side not in cfg.side_allowlist or not cfg.sell_allowed and side != "buy":
            return self._result(cfg, st, "sell_attempt_blocked", severity="critical", incident_required=True)
        if symbol not in cfg.symbol_allowlist:
            return self._result(cfg, st, "symbol_not_allowed", severity="error", incident_required=True)
        if amount <= 0:
            return self._result(cfg, st, "invalid_order_amount", severity="error", incident_required=True)
        if amount > cfg.per_order_hard_cap_krw:
            return self._result(cfg, st, "per_order_cap_exceeded", severity="critical", incident_required=True)
        if st.order_count >= cfg.max_order_count:
            return self._result(cfg, st, "max_order_count_exceeded", severity="critical", incident_required=True)
        if st.total_order_amount_krw + amount > cfg.total_window_cap_krw:
            return self._result(cfg, st, "total_window_cap_exceeded", severity="critical", incident_required=True)
        if st.order_count > 0 and elapsed < cfg.min_order_interval_sec:
            return self._result(cfg, st, "min_order_interval_violation", severity="critical", incident_required=True)
        return self._result(cfg, st, "preflight_only_order_not_submitted", severity="info")

    def record_incident(
        self,
        *,
        goal: str,
        trigger_condition: str,
        severity: str,
        report_path: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "goal": goal,
            "incident_time_utc": _now_utc(),
            "severity": str(severity or "HIGH"),
            "trigger_condition": str(trigger_condition or ""),
            "immediate_stop": True,
            "report_path": str(report_path or ""),
            "extra": dict(extra or {}),
            "submitted": 0,
            "order_allowed": False,
            "real_order": False,
        }

    def _config_block_reason(self, cfg: LiveGuardedWindowConfig) -> str:
        if cfg.duration_min > 120 or cfg.duration_min <= 0:
            return "duration_policy_invalid"
        if abs(cfg.per_order_krw - 10000.0) > 0.0001:
            return "per_order_amount_policy_invalid"
        if cfg.per_order_hard_cap_krw > 12000.0 or cfg.per_order_hard_cap_krw < cfg.per_order_krw:
            return "per_order_hard_cap_policy_invalid"
        if cfg.total_window_cap_krw > 20000.0 or cfg.total_window_cap_krw < cfg.per_order_krw:
            return "total_window_cap_policy_invalid"
        if cfg.max_order_count > 2 or cfg.max_order_count <= 0:
            return "max_order_count_policy_invalid"
        if cfg.min_order_interval_sec < 600:
            return "min_order_interval_policy_invalid"
        if cfg.sell_allowed:
            return "sell_must_remain_disabled"
        if cfg.cancel_allowed:
            return "cancel_must_remain_disabled"
        if cfg.retry_allowed:
            return "retry_must_remain_disabled"
        if not cfg.emergency_stop_required:
            return "emergency_stop_requirement_missing"
        if not cfg.incident_stop_required:
            return "incident_stop_requirement_missing"
        return ""

    def _result(
        self,
        cfg: LiveGuardedWindowConfig,
        st: LiveGuardedWindowState,
        reason: str,
        *,
        severity: str,
        incident_required: bool = False,
    ) -> LiveGuardedWindowCheckResult:
        return LiveGuardedWindowCheckResult(
            allowed_to_start=False,
            locked=True,
            blocked_reason=str(reason or ""),
            severity=str(severity or "info"),
            config=cfg.to_dict(),
            state=st.to_dict(),
            order_allowed=False,
            real_order=False,
            submitted=0,
            place_order_call_count=0,
            cancel_call_count=0,
            sell_call_count=0,
            retry_call_count=0,
            incident_required=bool(incident_required),
        )
