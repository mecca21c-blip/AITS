from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional


_SYMBOL_RE = re.compile(r"^[A-Z]{2,10}-[A-Z0-9]{2,20}$")


@dataclass
class RiskGuardInput:
    symbol: str = ""
    side: str = ""
    requested_amount_krw: float = 0.0
    price: float = 0.0
    quantity: float = 0.0
    source_provider: str = ""
    confidence: float = 0.0
    action: str = ""
    holdings_value_krw: float = 0.0
    cash_available_krw: float = 0.0
    portfolio_value_krw: float = 0.0
    daily_realized_pnl_krw: float = 0.0
    daily_loss_limit_krw: float = 0.0
    max_order_amount_krw: float = 0.0
    max_position_value_krw: float = 0.0
    emergency_stop: bool = False
    stale_price: bool = False
    execution_mode: str = "disabled"
    dry_run: bool = True
    request_id: str = ""
    valuation_unit_consistency_checked: bool = False
    valuation_unit_mismatch: bool = False
    pnl_valid_for_sell: bool = True


@dataclass
class RiskGuardCheck:
    name: str
    passed: bool
    reason: str = ""


@dataclass
class RiskGuardResult:
    allowed: bool = False
    risk_allowed: bool = False
    blocked_reason: str = ""
    severity: str = "info"
    max_allowed_amount_krw: float = 0.0
    requires_confirm: bool = False
    submitted: int = 0
    order_allowed: bool = False
    real_order: bool = False
    dry_run: bool = True
    checks: List[RiskGuardCheck] = field(default_factory=list)
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [asdict(check) for check in self.checks]
        return data


class RiskGuard:
    """Dry-run order-candidate policy guard.

    This class is intentionally pure: it does not call providers, order
    services, brokers, repositories, or UI objects. `allowed=True` only means a
    dry-run candidate passed policy checks; real order fields remain locked.
    """

    def evaluate_order_candidate(self, candidate: RiskGuardInput | Dict[str, Any]) -> RiskGuardResult:
        data = self._coerce_input(candidate)
        checks: List[RiskGuardCheck] = []

        def add_check(name: str, passed: bool, reason: str = "") -> None:
            checks.append(RiskGuardCheck(name=name, passed=bool(passed), reason=str(reason or "")))

        symbol = str(data.symbol or "").strip().upper()
        side = str(data.side or data.action or "").strip().lower()
        amount = self._safe_float(data.requested_amount_krw)
        price = self._safe_float(data.price)
        holdings = self._safe_float(data.holdings_value_krw)
        cash = self._safe_float(data.cash_available_krw)
        pnl = self._safe_float(data.daily_realized_pnl_krw)
        loss_limit = abs(self._safe_float(data.daily_loss_limit_krw))
        max_order = self._safe_float(data.max_order_amount_krw)
        max_position = self._safe_float(data.max_position_value_krw)

        failure = self._first_failure(
            data=data,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            holdings=holdings,
            cash=cash,
            pnl=pnl,
            loss_limit=loss_limit,
            max_order=max_order,
            max_position=max_position,
            add_check=add_check,
        )

        if failure is None:
            max_allowed = min(value for value in (max_order, max_position - holdings, cash) if value > 0)
            return RiskGuardResult(
                allowed=True,
                risk_allowed=True,
                blocked_reason="",
                severity="info",
                max_allowed_amount_krw=max_allowed,
                requires_confirm=True,
                submitted=0,
                order_allowed=False,
                real_order=False,
                dry_run=bool(data.dry_run),
                checks=checks,
                request_id=str(data.request_id or ""),
            )

        reason, severity = failure
        return RiskGuardResult(
            allowed=False,
            risk_allowed=False,
            blocked_reason=reason,
            severity=severity,
            max_allowed_amount_krw=0.0,
            requires_confirm=False,
            submitted=0,
            order_allowed=False,
            real_order=False,
            dry_run=bool(data.dry_run),
            checks=checks,
            request_id=str(data.request_id or ""),
        )

    def log_summary(self, result: RiskGuardResult, candidate: RiskGuardInput | Dict[str, Any]) -> str:
        data = self._coerce_input(candidate)
        return (
            "[AITS][RiskGuard] "
            f"event=evaluate request_id={data.request_id or '-'} "
            f"symbol={data.symbol or '-'} side={data.side or data.action or '-'} "
            f"allowed={bool(result.allowed)} risk_allowed={bool(result.risk_allowed)} "
            f"blocked_reason={result.blocked_reason or '-'} submitted=0 "
            f"order_allowed=False real_order=False dry_run={bool(result.dry_run)}"
        )

    def _first_failure(
        self,
        *,
        data: RiskGuardInput,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        holdings: float,
        cash: float,
        pnl: float,
        loss_limit: float,
        max_order: float,
        max_position: float,
        add_check: Any,
    ) -> Optional[tuple[str, str]]:
        if data.emergency_stop:
            add_check("emergency_stop", False, "emergency_stop_active")
            return "emergency_stop_active", "critical"
        add_check("emergency_stop", True)

        if not _SYMBOL_RE.match(symbol):
            add_check("symbol", False, "invalid_symbol")
            return "invalid_symbol", "error"
        add_check("symbol", True)

        if side not in {"buy", "sell"}:
            add_check("side", False, "invalid_side")
            return "invalid_side", "error"
        add_check("side", True)

        if amount <= 0:
            add_check("amount", False, "invalid_amount")
            return "invalid_amount", "error"
        add_check("amount", True)

        if price <= 0:
            add_check("price", False, "missing_or_invalid_price")
            return "missing_or_invalid_price", "error"
        add_check("price", True)

        if data.stale_price:
            add_check("freshness", False, "stale_price")
            return "stale_price", "warning"
        add_check("freshness", True)

        if max_order > 0 and amount > max_order:
            add_check("max_order_amount", False, "max_order_amount_exceeded")
            return "max_order_amount_exceeded", "warning"
        add_check("max_order_amount", True)

        if side == "buy" and max_position > 0 and holdings + amount > max_position:
            add_check("position_limit", False, "max_position_value_exceeded")
            return "max_position_value_exceeded", "warning"
        add_check("position_limit", True)

        if loss_limit > 0 and pnl <= -loss_limit:
            add_check("daily_loss_limit", False, "daily_loss_limit_exceeded")
            return "daily_loss_limit_exceeded", "critical"
        add_check("daily_loss_limit", True)

        if side == "buy" and cash < amount:
            add_check("cash_available", False, "insufficient_cash")
            return "insufficient_cash", "warning"
        add_check("cash_available", True)

        if side == "sell" and data.quantity <= 0:
            add_check("sell_quantity", False, "sell_quantity_unavailable")
            return "sell_quantity_unavailable", "warning"
        add_check("sell_quantity", True)

        if side == "sell" and bool(data.valuation_unit_mismatch):
            add_check("sell_valuation_unit_consistency", False, "sell_blocked_by_valuation_unit_mismatch")
            return "sell_blocked_by_valuation_unit_mismatch", "critical"
        add_check("sell_valuation_unit_consistency", True)

        if side == "sell" and bool(data.valuation_unit_consistency_checked) and not bool(data.pnl_valid_for_sell):
            add_check("sell_pnl_validity", False, "sell_blocked_by_invalid_pnl")
            return "sell_blocked_by_invalid_pnl", "critical"
        add_check("sell_pnl_validity", True)

        return None

    def _coerce_input(self, candidate: RiskGuardInput | Dict[str, Any]) -> RiskGuardInput:
        if isinstance(candidate, RiskGuardInput):
            return candidate
        if isinstance(candidate, dict):
            fields = RiskGuardInput.__dataclass_fields__
            return RiskGuardInput(**{key: candidate.get(key) for key in fields if key in candidate})
        return RiskGuardInput()

    def _safe_float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def evaluate_order_candidate(candidate: RiskGuardInput | Dict[str, Any]) -> RiskGuardResult:
    return RiskGuard().evaluate_order_candidate(candidate)


def build_riskguard_preview(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a no-apply RiskGuard preview from a RouterValidation preview payload.
    This does not call RiskGuard.evaluate_order_candidate() or open order paths.
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
        max_order_amount_krw = int(float(data.get("max_order_amount_krw") or 12000))
    except Exception:
        max_order_amount_krw = 12000

    if str(data.get("validation_status") or "").lower() != "passed":
        blockers.append("router_validation_not_passed")
    if not bool(data.get("input_valid", True)):
        blockers.append("router_validation_input_invalid")
    if not _SYMBOL_RE.match(symbol):
        blockers.append("invalid_symbol")
    if side not in {"buy", "sell"}:
        blockers.append("invalid_side")
    if amount_krw <= 0:
        blockers.append("invalid_amount")
    if max_order_amount_krw > 0 and amount_krw > max_order_amount_krw:
        blockers.append("max_order_amount_exceeded")

    risk_status = "passed" if not blockers else "blocked"
    return {
        "schema": "aits_riskguard_preview.v1",
        "source_request_id": source_request_id,
        "symbol": symbol,
        "side": side,
        "amount_krw": amount_krw,
        "input_valid": not blockers,
        "risk_status": risk_status,
        "blocker": "" if not blockers else ",".join(blockers),
        "reason": "risk_preview_contract_passed" if not blockers else ",".join(blockers),
        "observe_only": True,
        "riskguard_apply": False,
        "live_preflight_called": False,
        "execution_called": False,
        "order_service_called": False,
        "order_adapter_called": False,
        "submitted": 0,
        "actual_order": False,
    }


def build_risk_guard_input_from_action(action: Any, context: Optional[Dict[str, Any]] = None) -> RiskGuardInput:
    ctx = dict(context or {})
    action_type = _read_value(action, "action_type", "action")
    side = str(action_type or "").strip().lower()
    if side == "reduce":
        side = "sell"
    return RiskGuardInput(
        symbol=str(_read_value(action, "symbol") or ctx.get("symbol") or ""),
        side=side,
        requested_amount_krw=_safe_float_value(
            _read_value(action, "amount_krw", "requested_amount_krw"),
            ctx.get("requested_amount_krw", 0.0),
        ),
        price=_safe_float_value(ctx.get("price"), 0.0),
        quantity=_safe_float_value(ctx.get("quantity"), 0.0),
        source_provider=str(_read_value(action, "source_provider") or ctx.get("source_provider") or ""),
        confidence=_safe_float_value(_read_value(action, "confidence"), ctx.get("confidence", 0.0)),
        action=str(action_type or ""),
        holdings_value_krw=_safe_float_value(ctx.get("holdings_value_krw"), 0.0),
        cash_available_krw=_safe_float_value(ctx.get("cash_available_krw"), 0.0),
        portfolio_value_krw=_safe_float_value(ctx.get("portfolio_value_krw"), 0.0),
        daily_realized_pnl_krw=_safe_float_value(ctx.get("daily_realized_pnl_krw"), 0.0),
        daily_loss_limit_krw=_safe_float_value(ctx.get("daily_loss_limit_krw"), 0.0),
        max_order_amount_krw=_safe_float_value(ctx.get("max_order_amount_krw"), 0.0),
        max_position_value_krw=_safe_float_value(ctx.get("max_position_value_krw"), 0.0),
        emergency_stop=bool(ctx.get("emergency_stop", False)),
        stale_price=bool(ctx.get("stale_price", False)),
        execution_mode=str(ctx.get("execution_mode") or "disabled"),
        dry_run=True,
        request_id=str(ctx.get("request_id") or ""),
    )


def _read_value(obj: Any, *names: str) -> Any:
    for name in names:
        try:
            if isinstance(obj, dict) and name in obj:
                return obj.get(name)
            if hasattr(obj, name):
                return getattr(obj, name)
        except Exception:
            continue
    return None


def _safe_float_value(value: Any, default: Any = 0.0) -> float:
    try:
        if value is None:
            return float(default or 0.0)
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(default or 0.0)
        except (TypeError, ValueError):
            return 0.0
