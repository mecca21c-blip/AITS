from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional


_SYMBOL_RE = re.compile(r"^[A-Z]{2,10}-[A-Z0-9]{2,20}$")


@dataclass
class LiveOrderPreflightInput:
    request_id: str = ""
    symbol: str = ""
    side: str = ""
    amount_krw: float = 0.0
    quantity: float = 0.0
    price: float = 0.0
    execution_mode: str = "disabled"
    aits_enabled: bool = False
    live_order_unlock: bool = False
    user_confirm_token: str = ""
    risk_guard_checked: bool = False
    risk_allowed: bool = False
    one_shot_unlock_valid: bool = False
    one_shot_unlock_id: str = ""
    one_shot_unlock_consumed: bool = False
    emergency_stop: bool = False
    max_order_amount_krw: float = 0.0
    max_daily_loss_krw: float = 0.0
    max_order_count_per_cycle: int = 0
    duplicate_order_lock: bool = False
    min_real_order_amount_krw: float = 0.0
    account_ready: bool = False
    api_key_ready: bool = False
    price_fresh: bool = False
    selected_provider: str = ""
    source: str = ""


@dataclass
class LiveOrderPreflightResult:
    locked: bool = True
    allowed: bool = False
    allowed_for_preflight: bool = False
    blocked_reason: str = ""
    severity: str = "critical"
    required_conditions: List[str] = field(default_factory=list)
    missing_conditions: List[str] = field(default_factory=list)
    submitted: int = 0
    order_allowed: bool = False
    real_order: bool = False
    execution_mode: str = "disabled"
    request_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveOrderPreflight:
    """Final lock before any real order call.

    This evaluator is intentionally pure. It does not call providers, brokers,
    repositories, UI objects, or order services. Passing this evaluator only
    means the preflight contract is satisfied; real order fields remain locked.
    """

    REQUIRED_CONDITIONS = [
        "execution_mode_live",
        "aits_enabled",
        "live_order_unlock",
        "user_confirm_token",
        "risk_guard_checked",
        "risk_allowed",
        "one_shot_unlock_valid",
        "emergency_stop_off",
        "max_order_amount_krw",
        "max_daily_loss_krw",
        "max_order_count_per_cycle",
        "duplicate_order_lock",
        "min_real_order_amount_krw",
        "account_ready",
        "api_key_ready",
        "symbol_valid",
        "side_valid",
        "amount_valid",
        "price_fresh",
        "price_valid",
    ]

    def evaluate(self, data: LiveOrderPreflightInput | Dict[str, Any]) -> LiveOrderPreflightResult:
        item = self._coerce_input(data)
        missing = self._missing_conditions(item)
        blocked_reason = missing[0] if missing else "live_order_preflight_locked"
        if item.max_order_amount_krw > 0 and item.amount_krw > item.max_order_amount_krw:
            blocked_reason = "max_order_amount_exceeded"
            if blocked_reason not in missing:
                missing.append(blocked_reason)
        if not missing:
            blocked_reason = ""
        locked = bool(missing)

        return LiveOrderPreflightResult(
            locked=locked,
            allowed=not locked,
            allowed_for_preflight=not locked,
            blocked_reason=blocked_reason,
            severity="info" if not locked else (
                "critical" if blocked_reason in {"emergency_stop_active", "live_order_preflight_locked"} else "error"
            ),
            required_conditions=list(self.REQUIRED_CONDITIONS),
            missing_conditions=missing,
            submitted=0,
            order_allowed=False,
            real_order=False,
            execution_mode=str(item.execution_mode or "disabled"),
            request_id=str(item.request_id or ""),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def log_summary(self, result: LiveOrderPreflightResult, data: LiveOrderPreflightInput | Dict[str, Any]) -> str:
        item = self._coerce_input(data)
        return (
            "[AITS][LiveOrderPreflight] "
            f"event=evaluate request_id={item.request_id or '-'} "
            f"symbol={item.symbol or '-'} side={item.side or '-'} "
            f"locked={bool(result.locked)} allowed_for_preflight={bool(result.allowed_for_preflight)} "
            f"blocked_reason={result.blocked_reason or '-'} "
            "submitted=0 order_allowed=False real_order=False "
            f"execution_mode={result.execution_mode or 'disabled'}"
        )

    def _missing_conditions(self, item: LiveOrderPreflightInput) -> List[str]:
        missing: List[str] = []
        symbol = str(item.symbol or "").strip().upper()
        side = str(item.side or "").strip().lower()
        amount = _safe_float(item.amount_krw)
        price = _safe_float(item.price)

        if str(item.execution_mode or "").strip().lower() != "live":
            missing.append("execution_mode_not_live")
        if not bool(item.aits_enabled):
            missing.append("aits_off")
        if not bool(item.live_order_unlock):
            missing.append("live_order_unlock_missing")
        if not str(item.user_confirm_token or "").strip():
            missing.append("user_confirm_token_missing")
        if not bool(item.risk_guard_checked):
            missing.append("risk_guard_not_checked")
        if not bool(item.risk_allowed):
            missing.append("risk_guard_not_allowed")
        if bool(item.emergency_stop):
            missing.append("emergency_stop_active")
        if bool(item.one_shot_unlock_consumed):
            missing.append("one_shot_unlock_consumed")
        if not bool(item.one_shot_unlock_valid):
            missing.append("one_shot_unlock_invalid")
        if _safe_float(item.max_order_amount_krw) <= 0:
            missing.append("max_order_amount_missing")
        if _safe_float(item.max_daily_loss_krw) <= 0:
            missing.append("max_daily_loss_missing")
        if int(_safe_float(item.max_order_count_per_cycle)) <= 0:
            missing.append("max_order_count_missing")
        if not bool(item.duplicate_order_lock):
            missing.append("duplicate_order_lock_missing")
        if _safe_float(item.min_real_order_amount_krw) <= 0:
            missing.append("min_real_order_amount_missing")
        if not bool(item.account_ready):
            missing.append("account_not_ready")
        if not bool(item.api_key_ready):
            missing.append("api_key_not_ready")
        if not _SYMBOL_RE.match(symbol):
            missing.append("invalid_symbol")
        if side not in {"buy", "sell"}:
            missing.append("invalid_side")
        if amount <= 0:
            missing.append("invalid_amount")
        if not bool(item.price_fresh):
            missing.append("price_not_fresh")
        if price <= 0:
            missing.append("missing_or_invalid_price")
        return missing

    def _coerce_input(self, data: LiveOrderPreflightInput | Dict[str, Any]) -> LiveOrderPreflightInput:
        if isinstance(data, LiveOrderPreflightInput):
            return data
        if isinstance(data, dict):
            fields = LiveOrderPreflightInput.__dataclass_fields__
            return LiveOrderPreflightInput(**{key: data.get(key) for key in fields if key in data})
        return LiveOrderPreflightInput()


def evaluate_live_order_preflight(data: LiveOrderPreflightInput | Dict[str, Any]) -> LiveOrderPreflightResult:
    return LiveOrderPreflight().evaluate(data)


def build_live_preflight_preview(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a no-apply LivePreflight preview from a RiskGuard preview payload.
    This never performs unlock, confirm phrase entry, execution, or submit.
    """
    data = dict(payload or {}) if isinstance(payload, dict) else {}
    blockers: List[str] = []
    source_request_id = str(data.get("request_id") or "").strip()
    symbol = str(data.get("symbol") or "").strip().upper()
    side = str(data.get("side") or "").strip().lower()
    try:
        amount_krw = int(float(data.get("amount_krw") or 0))
    except Exception:
        amount_krw = 0
    try:
        min_order_krw = int(float(data.get("min_order_krw") or 10000))
    except Exception:
        min_order_krw = 10000
    try:
        max_order_amount_krw = int(float(data.get("max_order_amount_krw") or 12000))
    except Exception:
        max_order_amount_krw = 12000

    if str(data.get("risk_status") or "").lower() != "passed":
        blockers.append("riskguard_preview_not_passed")
    if not bool(data.get("input_valid", True)):
        blockers.append("riskguard_preview_input_invalid")
    if not _SYMBOL_RE.match(symbol):
        blockers.append("invalid_symbol")
    if side not in {"buy", "sell"}:
        blockers.append("invalid_side")
    if amount_krw < min_order_krw:
        blockers.append("amount_below_min_order")
    if max_order_amount_krw > 0 and amount_krw > max_order_amount_krw:
        blockers.append("amount_exceeds_max_order")

    confirm_phrase_required = True
    confirm_phrase_expected = str(
        data.get("confirm_phrase_expected")
        or data.get("expected_confirm_phrase")
        or f"AITS LIVE ORDER {symbol} {side.upper()} {amount_krw}"
    ).strip()
    unlock_required = True
    confirm_phrase_matched = False
    unlock_performed = False
    if confirm_phrase_required and not confirm_phrase_matched:
        blockers.append("confirm_phrase_not_matched")
    if unlock_required and not unlock_performed:
        blockers.append("unlock_not_performed")

    preflight_status = "passed" if not blockers else "blocked"
    return {
        "schema": "aits_live_preflight_preview.v1",
        "source_request_id": source_request_id,
        "symbol": symbol,
        "side": side,
        "amount_krw": amount_krw,
        "input_valid": not any(b for b in blockers if b not in {"confirm_phrase_not_matched", "unlock_not_performed"}),
        "preflight_status": preflight_status,
        "blocker": "" if not blockers else ",".join(blockers),
        "reason": "live_preflight_preview_passed" if not blockers else ",".join(blockers),
        "confirm_phrase_required": confirm_phrase_required,
        "confirm_phrase_expected": confirm_phrase_expected,
        "confirm_phrase_matched": confirm_phrase_matched,
        "unlock_required": unlock_required,
        "unlock_performed": unlock_performed,
        "execution_allowed": False,
        "observe_only": True,
        "live_preflight_apply": False,
        "execution_called": False,
        "order_service_called": False,
        "order_adapter_called": False,
        "submitted": 0,
        "actual_order": False,
    }


def build_guarded_execution_contract_preview(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the final no-apply contract preview before any execution bridge.
    This records the required user approval state and never unlocks or submits.
    """
    data = dict(payload or {}) if isinstance(payload, dict) else {}
    try:
        amount_krw = int(float(data.get("amount_krw") or 0))
    except Exception:
        amount_krw = 0
    try:
        min_order_krw = int(float(data.get("min_order_krw") or 10000))
    except Exception:
        min_order_krw = 10000
    symbol = str(data.get("symbol") or "").strip().upper()
    side = str(data.get("side") or "").strip().lower()
    confirm_phrase_required = bool(data.get("confirm_phrase_required", True))
    confirm_phrase_expected = str(
        data.get("confirm_phrase_expected")
        or data.get("expected_confirm_phrase")
        or f"AITS LIVE ORDER {symbol} {side.upper()} {amount_krw}"
    ).strip()
    confirm_phrase_matched = False
    unlock_required = bool(data.get("unlock_required", True))
    unlock_performed = False
    live_status = str(data.get("live_preflight_preview_status") or data.get("preflight_status") or "").strip().lower()
    blockers: List[str] = []
    if confirm_phrase_required and not confirm_phrase_matched:
        blockers.append("confirm_phrase_not_matched")
    if unlock_required and not unlock_performed:
        blockers.append("unlock_not_performed")
    if live_status not in {"passed", "blocked"}:
        blockers.append("live_preflight_preview_not_confirmed")
    return {
        "schema": "aits_guarded_execution_contract_preview.v1",
        "source_request_id": str(data.get("request_id") or data.get("source_request_id") or "").strip(),
        "symbol": symbol,
        "side": side,
        "amount_krw": amount_krw,
        "min_order_krw": min_order_krw,
        "provider_ready": bool(data.get("provider_ready", True)),
        "market_feed_ok": bool(data.get("market_feed_ok", True)),
        "balance_preflight_passed": bool(data.get("balance_preflight_passed", True)),
        "cap_preflight_passed": bool(data.get("cap_preflight_passed", True)),
        "router_validation_status": str(data.get("router_validation_status") or ""),
        "riskguard_preview_status": str(data.get("riskguard_preview_status") or ""),
        "live_preflight_preview_status": str(data.get("live_preflight_preview_status") or data.get("preflight_status") or ""),
        "confirm_phrase_required": confirm_phrase_required,
        "confirm_phrase_expected": confirm_phrase_expected,
        "confirm_phrase_matched": confirm_phrase_matched,
        "unlock_required": unlock_required,
        "unlock_performed": unlock_performed,
        "execution_allowed": False,
        "execution_called": False,
        "order_service_called": False,
        "order_adapter_called": False,
        "submitted": 0,
        "actual_order": False,
        "blocker": ",".join(blockers),
        "next_required_user_action": "explicit_live_order_approval_required",
        "live_order_approval_required": True,
    }


def build_preflight_input_from_order_request(
    order_request: Dict[str, Any],
    *,
    request_id: str = "",
    execution_mode: str = "disabled",
    risk_guard: Optional[Dict[str, Any]] = None,
) -> LiveOrderPreflightInput:
    risk = dict(risk_guard or {})
    return LiveOrderPreflightInput(
        request_id=str(request_id or order_request.get("request_id") or ""),
        symbol=str(order_request.get("symbol") or ""),
        side=str(order_request.get("side") or ""),
        amount_krw=_safe_float(order_request.get("amount_krw")),
        quantity=_safe_float(order_request.get("volume") or order_request.get("quantity")),
        price=_safe_float(order_request.get("price")),
        execution_mode=str(execution_mode or "disabled"),
        aits_enabled=bool(risk.get("aits_enabled", False)),
        live_order_unlock=bool(risk.get("live_order_unlock", False)),
        user_confirm_token=str(risk.get("user_confirm_token") or ""),
        risk_guard_checked=bool(risk.get("risk_guard_checked", False)),
        risk_allowed=bool(risk.get("risk_allowed", False)),
        one_shot_unlock_valid=bool(risk.get("one_shot_unlock_valid", False)),
        one_shot_unlock_id=str(risk.get("one_shot_unlock_id") or ""),
        one_shot_unlock_consumed=bool(risk.get("one_shot_unlock_consumed", False)),
        emergency_stop=bool(risk.get("emergency_stop", False)),
        max_order_amount_krw=_safe_float(risk.get("max_order_amount_krw")),
        max_daily_loss_krw=_safe_float(risk.get("max_daily_loss_krw")),
        max_order_count_per_cycle=int(_safe_float(risk.get("max_order_count_per_cycle"))),
        duplicate_order_lock=bool(risk.get("duplicate_order_lock", False)),
        min_real_order_amount_krw=_safe_float(risk.get("min_real_order_amount_krw")),
        account_ready=bool(risk.get("account_ready", False)),
        api_key_ready=bool(risk.get("api_key_ready", False)),
        price_fresh=bool(risk.get("price_fresh", False)),
        selected_provider=str(risk.get("source_provider") or ""),
        source="order_adapter_pre_place_order",
    )


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
