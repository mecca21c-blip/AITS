# -*- coding: utf-8 -*-
"""Managed Pool promotion/rotation policy.

Pure planning only. This module must not mutate UI rows, call providers, or
touch order/execution services.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MAX_MANAGED_POOL_SIZE = 10
PROTECTED_SYSTEM_SEED_SYMBOLS = {"KRW-BTC", "KRW-ETH", "KRW-XRP"}


@dataclass(frozen=True)
class ManagedPoolPromotionConfig:
    max_managed_pool_size: int = MAX_MANAGED_POOL_SIZE
    promotion_min_score: float | None = None
    auto_add_enabled: bool = True
    auto_remove_enabled: bool = True
    protect_user_added: bool = True
    protect_holdings_until_liquidated: bool = True
    protect_system_seed_initially: bool = True
    rotation_enabled: bool = True
    rotation_min_score_gap: float | None = 0.0
    order_execution_enabled: bool = False


def _text(value: Any) -> str:
    return str(value or "").strip()


def _symbol(value: Any) -> str:
    raw = _text(value).upper()
    if not raw:
        return ""
    return raw if "-" in raw else f"KRW-{raw}"


def _row_symbol(row: dict[str, Any]) -> str:
    return _symbol(row.get("symbol") or row.get("market") or row.get("code") or row.get("ticker"))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _score(row: dict[str, Any], default: float = -1.0) -> float:
    return _float(row.get("score", row.get("ai_score")), default)


def _source_type(row: dict[str, Any]) -> str:
    return _text(row.get("source_type") or row.get("source")).lower()


def _is_user_added(row: dict[str, Any]) -> bool:
    source_type = _source_type(row)
    return source_type in {"user_added", "user", "manual", "manual_added"} or _text(row.get("source")).upper() == "USER"


def _is_basic_added(row: dict[str, Any]) -> bool:
    source_type = _source_type(row)
    return source_type in {"basic_added", "basic", "auto", "auto_added"}


def _is_system_seed(row: dict[str, Any]) -> bool:
    source_type = _source_type(row)
    symbol = _row_symbol(row)
    return source_type in {"system_seed", "system_default", "seed"} or symbol in PROTECTED_SYSTEM_SEED_SYMBOLS


def _is_manual_hold(row: dict[str, Any]) -> bool:
    return bool(row.get("manual_hold") or row.get("user_trade_hold") or row.get("locked"))


def _holding_symbols(holdings: list[dict[str, Any]] | None) -> set[str]:
    symbols: set[str] = set()
    for row in holdings or []:
        if not isinstance(row, dict):
            continue
        symbol = _row_symbol(row)
        qty = _float(row.get("qty", row.get("quantity", row.get("balance"))), 0.0)
        value = _float(row.get("value_krw", row.get("holding_value", row.get("amount_krw"))), 0.0)
        if symbol and (qty > 0.0 or value > 0.0 or row.get("holding") is True):
            symbols.add(symbol)
    return symbols


def _is_holding(row: dict[str, Any], holding_symbols: set[str]) -> bool:
    symbol = _row_symbol(row)
    status = _text(row.get("status")).lower()
    qty = _float(row.get("qty", row.get("quantity", row.get("balance"))), 0.0)
    value = _float(row.get("value_krw", row.get("holding_value", row.get("amount_krw"))), 0.0)
    return symbol in holding_symbols or bool(row.get("holding")) or status == "holding" or qty > 0.0 or value > 0.0


def _compact_candidate(row: dict[str, Any], *, rank: int) -> dict[str, Any]:
    symbol = _row_symbol(row)
    return {
        "symbol": symbol,
        "rank": int(row.get("rank") or rank),
        "score": _score(row),
        "reason": _text(row.get("reason") or row.get("reason_summary")),
        "source": _text(row.get("source") or row.get("source_type") or "basic"),
        "change_rate": _float(row.get("change_rate", row.get("change_pct", row.get("signed_change_rate"))), 0.0),
        "trade_value": _float(row.get("trade_value", row.get("volume_krw", row.get("acc_trade_price_24h"))), 0.0),
    }


def _sort_candidates(candidates: list[dict[str, Any]], config: ManagedPoolPromotionConfig) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, row in enumerate(candidates or []):
        if not isinstance(row, dict):
            continue
        compact = _compact_candidate(row, rank=idx + 1)
        symbol = compact["symbol"]
        if not symbol or symbol in seen:
            continue
        if config.promotion_min_score is not None and compact["score"] < float(config.promotion_min_score):
            continue
        seen.add(symbol)
        out.append(compact)
    out.sort(key=lambda r: (_float(r.get("score"), -1.0), _float(r.get("trade_value"), 0.0), -int(r.get("rank") or 9999)), reverse=True)
    for idx, row in enumerate(out):
        row["rank"] = idx + 1
    return out


def build_managed_pool_promotion_plan(
    current_rows: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
    holdings: list[dict[str, Any]] | None = None,
    config: ManagedPoolPromotionConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config if isinstance(config, ManagedPoolPromotionConfig) else ManagedPoolPromotionConfig(**(config or {}))
    max_size = max(1, int(cfg.max_managed_pool_size or MAX_MANAGED_POOL_SIZE))
    holding_set = _holding_symbols(holdings)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in current_rows or []:
        if not isinstance(row, dict):
            continue
        symbol = _row_symbol(row)
        if not symbol or symbol in seen:
            continue
        clean = dict(row)
        clean["symbol"] = symbol
        clean.setdefault("market", symbol)
        rows.append(clean)
        seen.add(symbol)

    protected_rows: list[dict[str, Any]] = []
    removable_rows: list[dict[str, Any]] = []
    keep: list[dict[str, Any]] = []
    for row in rows:
        symbol = _row_symbol(row)
        reasons: list[str] = []
        if cfg.protect_user_added and _is_user_added(row):
            reasons.append("user_added")
        if cfg.protect_holdings_until_liquidated and _is_holding(row, holding_set):
            reasons.append("holding_until_liquidated")
        if _is_manual_hold(row):
            reasons.append("manual_hold")
        if cfg.protect_system_seed_initially and _is_system_seed(row):
            reasons.append("system_seed")
        if reasons:
            protected_rows.append({"symbol": symbol, "reasons": reasons})
        elif _is_basic_added(row):
            removable_rows.append(row)
        keep.append({"symbol": symbol, "source_type": _source_type(row) or "unknown", "score": _score(row, 0.0)})

    sorted_candidates = _sort_candidates(candidates or [], cfg)
    existing_symbols = {_row_symbol(row) for row in rows}
    new_candidates = [row for row in sorted_candidates if row["symbol"] not in existing_symbols]

    planned_add: list[dict[str, Any]] = []
    planned_remove: list[dict[str, Any]] = []
    current_size = len(rows)
    if cfg.auto_add_enabled:
        slots = max(0, max_size - current_size)
        for candidate in new_candidates[:slots]:
            planned_add.append(
                {
                    **candidate,
                    "source_type": "basic_added",
                    "reason": candidate.get("reason") or "selected_by_basic_candidate",
                    "promotion_reason": "pool_has_free_slot",
                    "actual_order": False,
                }
            )

    if cfg.auto_remove_enabled:
        projected_size = current_size + len(planned_add)
        removable_sorted = sorted(removable_rows, key=lambda row: (_score(row, -1.0), _float(row.get("trade_value"), 0.0)))
        for row in removable_sorted:
            if projected_size <= max_size:
                break
            symbol = _row_symbol(row)
            planned_remove.append(
                {
                    "symbol": symbol,
                    "score": _score(row, 0.0),
                    "source_type": _source_type(row),
                    "remove_reason": "pool_size_over_max_low_rank_basic_added",
                    "actual_order": False,
                }
            )
            projected_size -= 1

        if current_size >= max_size and new_candidates and removable_sorted:
            weakest = removable_sorted[0]
            best_new = new_candidates[0]
            if _score(best_new) > _score(weakest):
                weak_symbol = _row_symbol(weakest)
                if not any(item.get("symbol") == weak_symbol for item in planned_remove):
                    planned_remove.append(
                        {
                            "symbol": weak_symbol,
                            "score": _score(weakest, 0.0),
                            "source_type": _source_type(weakest),
                            "remove_reason": "higher_rank_candidate_replacement",
                            "replacement_symbol": best_new["symbol"],
                            "replacement_score": best_new["score"],
                            "actual_order": False,
                        }
                    )
                can_add_replacement = (current_size + 1 - len(planned_remove)) <= max_size
                if not planned_add and can_add_replacement:
                    planned_add.append(
                        {
                            **best_new,
                            "source_type": "basic_added",
                            "promotion_reason": "replace_lower_basic_added",
                            "actual_order": False,
                        }
                    )

    planned_rotation: list[dict[str, Any]] = []
    if cfg.rotation_enabled and new_candidates:
        holding_rows = [row for row in rows if _is_holding(row, holding_set)]
        for holding in sorted(holding_rows, key=lambda row: _score(row, 0.0)):
            candidate = new_candidates[0]
            gap = _score(candidate) - _score(holding, 0.0)
            min_gap = 0.0 if cfg.rotation_min_score_gap is None else float(cfg.rotation_min_score_gap)
            if gap > min_gap:
                planned_rotation.append(
                    {
                        "rotate_out": _row_symbol(holding),
                        "rotate_in": candidate["symbol"],
                        "holding_score": _score(holding, 0.0),
                        "candidate_score": candidate["score"],
                        "score_gap": round(gap, 4),
                        "sell_candidate": True,
                        "buy_candidate": True,
                        "actual_order": False,
                        "reason": "candidate_score_above_holding",
                    }
                )
                break

    protected_symbols = {item["symbol"] for item in protected_rows}
    protected_violation = any(item.get("symbol") in protected_symbols for item in planned_remove)
    pool_size_after = len(rows) + len(planned_add) - len(planned_remove)
    return {
        "policy_supported": True,
        "config": asdict(cfg),
        "max_managed_pool_size": max_size,
        "current_pool_size": len(rows),
        "candidate_count": len(sorted_candidates),
        "planned_keep": keep,
        "planned_add": planned_add,
        "planned_remove": planned_remove,
        "protected_rows": protected_rows,
        "planned_rotation": planned_rotation,
        "pool_size_after": pool_size_after,
        "pool_size_after_capped": min(pool_size_after, max_size),
        "protected_violation": protected_violation,
        "order_execution_enabled": bool(cfg.order_execution_enabled),
        "actual_mutation_performed": False,
        "mutation_allowed": False,
    }


__all__ = [
    "MAX_MANAGED_POOL_SIZE",
    "ManagedPoolPromotionConfig",
    "build_managed_pool_promotion_plan",
]
