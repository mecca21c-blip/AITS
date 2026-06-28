from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any, Dict, Optional, Set


_SYMBOL_RE = re.compile(r"^[A-Z]{2,10}-[A-Z0-9]{2,20}$")


@dataclass
class LiveOneShotUnlockRequest:
    request_id: str = ""
    symbol: str = ""
    side: str = ""
    amount_krw: float = 0.0
    max_order_amount_krw: float = 0.0
    min_order_amount_krw: float = 0.0
    user_confirm_phrase: str = ""
    confirm_token: str = ""
    expires_at_utc: str = ""
    ttl_sec: int = 0
    duplicate_lock_key: str = ""
    created_at_utc: str = ""
    source: str = ""
    operator_note: str = ""


@dataclass
class LiveOneShotUnlockState:
    unlock_id: str = ""
    active: bool = False
    consumed: bool = False
    expired: bool = False
    symbol: str = ""
    side: str = ""
    amount_krw: float = 0.0
    max_order_amount_krw: float = 0.0
    min_order_amount_krw: float = 0.0
    confirm_token_hash: str = ""
    expires_at_utc: str = ""
    duplicate_lock_key: str = ""
    created_at_utc: str = ""
    consumed_at_utc: str = ""
    consume_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiveOneShotUnlockResult:
    unlock_valid: bool = False
    locked: bool = True
    allowed_for_preflight: bool = False
    blocked_reason: str = ""
    severity: str = "critical"
    unlock_id: str = ""
    consumed: bool = False
    expired: bool = False
    duplicate_locked: bool = False
    max_order_amount_krw: float = 0.0
    submitted: int = 0
    order_allowed: bool = False
    real_order: bool = False
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveOneShotUnlock:
    """In-memory one-shot live-order unlock contract.

    The contract is intentionally pure and process-local for proof purposes. It
    does not call providers, order services, brokers, repositories, or UI code.
    """

    def __init__(self) -> None:
        self._states: Dict[str, LiveOneShotUnlockState] = {}
        self._duplicate_keys: Set[str] = set()

    def create_one_shot_unlock(self, request: LiveOneShotUnlockRequest | Dict[str, Any]) -> LiveOneShotUnlockState:
        data = self._coerce_request(request)
        created_at = _parse_dt(data.created_at_utc) or datetime.now(timezone.utc)
        expires_at = _parse_dt(data.expires_at_utc)
        if expires_at is None:
            ttl = int(_safe_float(data.ttl_sec))
            expires_at = created_at + timedelta(seconds=max(ttl, 0))
        unlock_id = self._make_unlock_id(data, created_at)
        state = LiveOneShotUnlockState(
            unlock_id=unlock_id,
            active=True,
            consumed=False,
            expired=False,
            symbol=str(data.symbol or "").strip().upper(),
            side=str(data.side or "").strip().lower(),
            amount_krw=_safe_float(data.amount_krw),
            max_order_amount_krw=_safe_float(data.max_order_amount_krw),
            min_order_amount_krw=_safe_float(data.min_order_amount_krw),
            confirm_token_hash=self._hash_token(data.confirm_token),
            expires_at_utc=expires_at.isoformat(timespec="seconds"),
            duplicate_lock_key=str(data.duplicate_lock_key or ""),
            created_at_utc=created_at.isoformat(timespec="seconds"),
        )
        self._states[unlock_id] = state
        return state

    def validate_one_shot_unlock(
        self,
        state: Optional[LiveOneShotUnlockState],
        request: LiveOneShotUnlockRequest | Dict[str, Any],
        *,
        now_utc: Optional[datetime] = None,
    ) -> LiveOneShotUnlockResult:
        data = self._coerce_request(request)
        now = now_utc or datetime.now(timezone.utc)
        if state is None:
            return self._blocked("missing_unlock", data, None)

        expired = self._is_expired(state, now)
        if expired:
            state.expired = True
            return self._blocked("unlock_expired", data, state, expired=True)
        if state.consumed:
            return self._blocked("unlock_consumed", data, state, consumed=True)
        if state.duplicate_lock_key and state.duplicate_lock_key in self._duplicate_keys:
            return self._blocked("duplicate_order_lock_reused", data, state, duplicate_locked=True)
        if self._hash_token(data.confirm_token) != state.confirm_token_hash:
            return self._blocked("invalid_confirm_token", data, state)
        if str(data.symbol or "").strip().upper() != state.symbol:
            return self._blocked("symbol_mismatch", data, state)
        if str(data.side or "").strip().lower() != state.side:
            return self._blocked("side_mismatch", data, state)

        amount = _safe_float(data.amount_krw)
        if amount <= 0:
            return self._blocked("invalid_amount", data, state)
        if state.min_order_amount_krw > 0 and amount < state.min_order_amount_krw:
            return self._blocked("amount_below_unlock_min", data, state)
        if state.max_order_amount_krw > 0 and amount > state.max_order_amount_krw:
            return self._blocked("amount_exceeds_unlock_cap", data, state)
        if not _SYMBOL_RE.match(state.symbol):
            return self._blocked("invalid_symbol", data, state)
        if state.side not in {"buy", "sell"}:
            return self._blocked("invalid_side", data, state)

        return LiveOneShotUnlockResult(
            unlock_valid=True,
            locked=False,
            allowed_for_preflight=True,
            blocked_reason="",
            severity="info",
            unlock_id=state.unlock_id,
            consumed=False,
            expired=False,
            duplicate_locked=False,
            max_order_amount_krw=state.max_order_amount_krw,
            submitted=0,
            order_allowed=False,
            real_order=False,
            request_id=str(data.request_id or ""),
        )

    def consume_one_shot_unlock(
        self,
        state: LiveOneShotUnlockState,
        *,
        reason: str = "preflight_contract_consumed",
        now_utc: Optional[datetime] = None,
    ) -> LiveOneShotUnlockState:
        now = now_utc or datetime.now(timezone.utc)
        state.consumed = True
        state.active = False
        state.consumed_at_utc = now.isoformat(timespec="seconds")
        state.consume_reason = str(reason or "")
        if state.duplicate_lock_key:
            self._duplicate_keys.add(state.duplicate_lock_key)
        return state

    def is_duplicate_locked(self, duplicate_lock_key: str) -> bool:
        return str(duplicate_lock_key or "") in self._duplicate_keys

    def log_summary(self, event: str, result: LiveOneShotUnlockResult) -> str:
        return (
            "[AITS][LiveOneShotUnlock] "
            f"event={event} request_id={result.request_id or '-'} "
            f"unlock_id={result.unlock_id or '-'} locked={bool(result.locked)} "
            f"allowed_for_preflight={bool(result.allowed_for_preflight)} "
            f"blocked_reason={result.blocked_reason or '-'} submitted=0 "
            "order_allowed=False real_order=False"
        )

    def _blocked(
        self,
        reason: str,
        data: LiveOneShotUnlockRequest,
        state: Optional[LiveOneShotUnlockState],
        *,
        consumed: bool = False,
        expired: bool = False,
        duplicate_locked: bool = False,
    ) -> LiveOneShotUnlockResult:
        return LiveOneShotUnlockResult(
            unlock_valid=False,
            locked=True,
            allowed_for_preflight=False,
            blocked_reason=str(reason or "unlock_locked"),
            severity="critical" if reason in {"missing_unlock", "unlock_expired"} else "error",
            unlock_id=str(getattr(state, "unlock_id", "") or ""),
            consumed=bool(consumed or getattr(state, "consumed", False)),
            expired=bool(expired or getattr(state, "expired", False)),
            duplicate_locked=bool(duplicate_locked),
            max_order_amount_krw=_safe_float(getattr(state, "max_order_amount_krw", 0.0)),
            submitted=0,
            order_allowed=False,
            real_order=False,
            request_id=str(data.request_id or ""),
        )

    def _make_unlock_id(self, data: LiveOneShotUnlockRequest, created_at: datetime) -> str:
        raw = "|".join(
            [
                str(data.request_id or ""),
                str(data.symbol or ""),
                str(data.side or ""),
                str(data.amount_krw or ""),
                created_at.isoformat(timespec="seconds"),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def _is_expired(self, state: LiveOneShotUnlockState, now: datetime) -> bool:
        expires_at = _parse_dt(state.expires_at_utc)
        return bool(expires_at is not None and now >= expires_at)

    def _coerce_request(self, request: LiveOneShotUnlockRequest | Dict[str, Any]) -> LiveOneShotUnlockRequest:
        if isinstance(request, LiveOneShotUnlockRequest):
            return request
        if isinstance(request, dict):
            fields = LiveOneShotUnlockRequest.__dataclass_fields__
            return LiveOneShotUnlockRequest(**{key: request.get(key) for key in fields if key in request})
        return LiveOneShotUnlockRequest()


def _parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
