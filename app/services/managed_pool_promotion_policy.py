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
    promotion_min_score: float | None = 60.0
    promotion_min_trade_value_krw: float | None = None
    quality_gate_enabled: bool = True
    fill_to_max: bool = False
    auto_add_enabled: bool = True
    auto_remove_enabled: bool = True
    protect_user_added: bool = True
    protect_holdings_until_liquidated: bool = True
    protect_system_seed_initially: bool = True
    rotation_enabled: bool = True
    rotation_min_score_gap: float | None = 0.0
    rotation_cooldown_sec: int = 3600
    max_rotation_per_cycle: int = 1
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


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _normalized_rotation_score(
    row: dict[str, Any],
    *,
    role: str,
    cfg: ManagedPoolPromotionConfig,
    is_protected: bool = False,
) -> dict[str, Any]:
    """Normalize operating/scanner scores for observe-only rotation comparison."""

    raw_score = _score(row, 0.0)
    change_rate = _float(row.get("change_rate", row.get("change_pct", row.get("signed_change_rate"))), 0.0)
    trade_value = _float(row.get("trade_value", row.get("volume_krw", row.get("acc_trade_price_24h"))), 0.0)
    status = _text(row.get("status") or row.get("state") or row.get("ai_status")).lower()
    stale = bool(row.get("stale") or row.get("market_data_stale") or row.get("ai_stale")) or "stale" in status
    eligible = not bool(row.get("ineligible") or row.get("blocked"))

    score = raw_score
    if change_rate > 0:
        score += min(change_rate * 0.25, 5.0)
    elif change_rate < 0:
        score += max(change_rate * 0.2, -5.0)
    if trade_value > 0:
        score += min(trade_value / 1_000_000_000_000.0, 3.0)
    if status == "dropped":
        score -= 8.0
    elif status == "watching":
        score -= 2.0
    if stale:
        score -= 12.0
    if not eligible:
        score -= 20.0
    if is_protected:
        score = 0.0

    normalized = _clamp_score(score)
    return {
        "role": role,
        "score_source": "scanner_score" if role == "candidate" else "operating_score",
        "raw_score": round(raw_score, 4),
        "normalized_rotation_score": round(normalized, 4),
        "change_rate": round(change_rate, 6),
        "trade_value": round(trade_value, 4),
        "stale": bool(stale),
        "eligible": bool(eligible),
        "protected_excluded": bool(is_protected),
    }


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
    status = _text(row.get("status") or row.get("state") or row.get("trade_status"))
    status_norm = status.lower()
    return bool(
        row.get("manual_hold")
        or row.get("user_trade_hold")
        or row.get("trade_hold")
        or row.get("hold")
        or row.get("locked")
        or status in {"매매보류", "보류"}
        or status_norm in {"trade_hold", "manual_hold", "hold", "paused", "blocked"}
    )


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
    return (
        symbol in holding_symbols
        or bool(row.get("holding"))
        or bool(row.get("holding_display"))
        or bool(row.get("holding_eligible"))
        or status == "holding"
        or qty > 0.0
        or value > 0.0
    )


def _rank(row: dict[str, Any], default: int = 999999) -> int:
    try:
        value = row.get("rank", row.get("priority_rank", row.get("candidate_rank")))
        if value is None:
            return int(default)
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return int(default)


def _added_at_text(row: dict[str, Any]) -> str:
    return _text(row.get("added_at") or row.get("created_at") or row.get("updated_at"))


def _protected_reasons(
    row: dict[str, Any],
    holding_set: set[str],
    cfg: ManagedPoolPromotionConfig,
) -> list[str]:
    reasons: list[str] = []
    if cfg.protect_user_added and _is_user_added(row):
        reasons.append("user_added")
    if cfg.protect_holdings_until_liquidated and _is_holding(row, holding_set):
        reasons.append("holding_until_liquidated")
    if _is_manual_hold(row):
        reasons.append("trade_hold")
    if cfg.protect_system_seed_initially and _is_system_seed(row):
        reasons.append("system_seed")
    return reasons


def _compact_pool_row(row: dict[str, Any], *, reasons: list[str] | None = None) -> dict[str, Any]:
    compact = {
        "symbol": _row_symbol(row),
        "score": _score(row, 0.0),
        "rank": _rank(row),
        "source_type": _source_type(row) or "unknown",
    }
    if reasons is not None:
        compact["reasons"] = list(reasons)
    return compact


def _trim_remove_sort_key(row: dict[str, Any]) -> tuple[float, int, str, str]:
    rank = _rank(row)
    rank_key = -rank if rank < 999999 else 0
    return (_score(row, 0.0), rank_key, _added_at_text(row), _row_symbol(row))


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
        seen.add(symbol)
        out.append(compact)
    out.sort(key=lambda r: (_float(r.get("score"), -1.0), _float(r.get("trade_value"), 0.0), -int(r.get("rank") or 9999)), reverse=True)
    for idx, row in enumerate(out):
        row["rank"] = idx + 1
    return out


def _effective_promotion_min_score(cfg: ManagedPoolPromotionConfig) -> float | None:
    if not bool(cfg.quality_gate_enabled):
        return None
    if cfg.promotion_min_score is None:
        return 60.0
    return float(cfg.promotion_min_score)


def evaluate_candidate_promotion_quality(
    candidate: dict[str, Any],
    config: ManagedPoolPromotionConfig | dict[str, Any] | None = None,
    *,
    existing_symbols: set[str] | None = None,
) -> dict[str, Any]:
    cfg = config if isinstance(config, ManagedPoolPromotionConfig) else ManagedPoolPromotionConfig(**(config or {}))
    symbol = _row_symbol(candidate)
    score = _score(candidate)
    rank = _rank(candidate)
    trade_value = _float(candidate.get("trade_value", candidate.get("volume_krw", candidate.get("acc_trade_price_24h"))), 0.0)
    reasons: list[str] = []
    if not symbol:
        reasons.append("missing_symbol")
    if symbol and symbol in (existing_symbols or set()):
        reasons.append("already_managed")
    min_score = _effective_promotion_min_score(cfg)
    if min_score is not None and score < min_score:
        reasons.append("score_below_min")
    min_trade_value = cfg.promotion_min_trade_value_krw
    if min_trade_value is not None and trade_value < float(min_trade_value):
        reasons.append("trade_value_below_min")
    if bool(cfg.quality_gate_enabled) and reasons:
        reasons.append("candidate_quality_gate_failed")
    return {
        "symbol": symbol,
        "pass": not reasons,
        "reasons": reasons,
        "failed_reason": reasons[0] if reasons else "",
        "score": score,
        "rank": rank,
        "trade_value": trade_value,
        "promotion_min_score": min_score,
        "promotion_min_trade_value_krw": min_trade_value,
    }


def _score_distribution(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [_score(row) for row in candidates if isinstance(row, dict) and _row_symbol(row)]
    if not scores:
        return {"count": 0}
    return {
        "count": len(scores),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "avg": round(sum(scores) / len(scores), 4),
        "gte_60": sum(1 for score in scores if score >= 60.0),
        "lt_60": sum(1 for score in scores if score < 60.0),
    }


def build_managed_pool_quality_rebuild_plan(
    current_rows: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
    holdings: list[dict[str, Any]] | None = None,
    config: ManagedPoolPromotionConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild the non-protected auto-managed subset by quality rank only."""

    cfg = config if isinstance(config, ManagedPoolPromotionConfig) else ManagedPoolPromotionConfig(**(config or {}))
    max_size = max(1, int(cfg.max_managed_pool_size or MAX_MANAGED_POOL_SIZE))
    holding_set = _holding_symbols(holdings)

    rows: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for row in current_rows or []:
        if not isinstance(row, dict):
            continue
        symbol = _row_symbol(row)
        if not symbol or symbol in seen_rows:
            continue
        clean = dict(row)
        clean["symbol"] = symbol
        clean.setdefault("market", symbol)
        rows.append(clean)
        seen_rows.add(symbol)

    protected_keep: list[dict[str, Any]] = []
    rebuild_rows: list[dict[str, Any]] = []
    ignored_rows: list[dict[str, Any]] = []
    for row in rows:
        reasons = _protected_reasons(row, holding_set, cfg)
        if reasons:
            protected_keep.append(_compact_pool_row(row, reasons=reasons))
        elif _is_basic_added(row):
            rebuild_rows.append(row)
        else:
            ignored_rows.append(_compact_pool_row(row, reasons=["non_basic_unprotected"]))

    protected_symbols = {item.get("symbol") for item in protected_keep if item.get("symbol")}
    existing_basic_by_symbol = {_row_symbol(row): row for row in rebuild_rows if _row_symbol(row)}

    candidate_by_symbol: dict[str, dict[str, Any]] = {}
    for row in _sort_candidates(candidates or [], cfg):
        symbol = _row_symbol(row)
        if symbol and symbol not in protected_symbols:
            candidate_by_symbol[symbol] = row

    merged_candidates: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for row in candidate_by_symbol.values():
        symbol = _row_symbol(row)
        if symbol and symbol not in seen_candidates:
            merged_candidates.append(row)
            seen_candidates.add(symbol)
    for symbol, row in existing_basic_by_symbol.items():
        if symbol in protected_symbols or symbol in seen_candidates:
            continue
        merged = _compact_candidate(row, rank=_rank(row))
        merged["source"] = _text(row.get("source") or row.get("source_type") or "basic_added")
        merged["reason"] = _text(row.get("reason") or row.get("reason_summary") or "existing_basic_added_recheck")
        merged_candidates.append(merged)
        seen_candidates.add(symbol)

    merged_candidates = _sort_candidates(merged_candidates, cfg)
    quality_results = [
        evaluate_candidate_promotion_quality(row, cfg, existing_symbols=protected_symbols)
        for row in merged_candidates
    ]
    quality_by_symbol = {item["symbol"]: item for item in quality_results if item.get("symbol")}
    quality_pass_symbols = {item["symbol"] for item in quality_results if item.get("pass") and item.get("symbol")}
    rejected_candidates = [
        {
            "symbol": item.get("symbol", ""),
            "score": item.get("score", 0.0),
            "rank": item.get("rank", 999999),
            "trade_value": item.get("trade_value", 0.0),
            "reasons": item.get("reasons", []),
            "failed_reason": item.get("failed_reason", ""),
        }
        for item in quality_results
        if not item.get("pass")
    ]

    rebuild_slots = max(0, max_size - len(protected_keep))
    selected = [row for row in merged_candidates if row.get("symbol") in quality_pass_symbols][:rebuild_slots]
    selected_symbols = {row.get("symbol") for row in selected if row.get("symbol")}

    planned_keep_basic: list[dict[str, Any]] = []
    planned_add: list[dict[str, Any]] = []
    for row in selected:
        symbol = _row_symbol(row)
        quality = quality_by_symbol.get(symbol, {})
        item = {
            **row,
            "source_type": "basic_added",
            "reason": row.get("reason") or "selected_by_quality_ranked_rebuild",
            "promotion_reason": "quality_ranked_rebuild_keep" if symbol in existing_basic_by_symbol else "quality_ranked_rebuild_add",
            "quality_gate_pass": True,
            "quality_gate_reasons": quality.get("reasons", []),
            "promotion_min_score": quality.get("promotion_min_score"),
            "actual_order": False,
        }
        if symbol in existing_basic_by_symbol:
            planned_keep_basic.append(item)
        else:
            planned_add.append(item)

    planned_remove: list[dict[str, Any]] = []
    for symbol, row in sorted(existing_basic_by_symbol.items(), key=lambda item: _trim_remove_sort_key(item[1])):
        if symbol in selected_symbols:
            continue
        quality = quality_by_symbol.get(symbol, {})
        reason = "quality_ranked_rebuild_not_selected"
        if quality and not quality.get("pass"):
            reason = quality.get("failed_reason") or "quality_gate_failed"
        elif rebuild_slots <= 0:
            reason = "protected_rows_fill_cap"
        planned_remove.append(
            {
                **_compact_pool_row(row),
                "remove_reason": reason,
                "quality_gate_reasons": quality.get("reasons", []) if quality else [],
                "replacement_available": bool(planned_add),
                "actual_order": False,
            }
        )

    after_count_expected = len(protected_keep) + len(planned_keep_basic) + len(planned_add)
    protected_overflow = len(protected_keep) > max_size
    not_filled_reason = ""
    if not protected_overflow and after_count_expected < max_size:
        if not merged_candidates:
            not_filled_reason = "candidate_count_zero"
        elif not quality_pass_symbols:
            not_filled_reason = "quality_gate_no_pass_candidates"
        elif not bool(cfg.fill_to_max):
            not_filled_reason = "max_managed_pool_size_is_cap_not_target"

    protected_violation = bool({item.get("symbol") for item in planned_remove} & protected_symbols)
    return {
        "quality_rebuild_supported": True,
        "config": asdict(cfg),
        "max_managed_pool_size": max_size,
        "promotion_min_score": _effective_promotion_min_score(cfg),
        "promotion_min_trade_value_krw": cfg.promotion_min_trade_value_krw,
        "quality_gate_enabled": bool(cfg.quality_gate_enabled),
        "fill_to_max": bool(cfg.fill_to_max),
        "current_pool_size": len(rows),
        "protected_keep": protected_keep,
        "protected_rows": protected_keep,
        "protected_count": len(protected_keep),
        "rebuild_slots": rebuild_slots,
        "current_basic_added": [_compact_pool_row(row) for row in rebuild_rows],
        "ignored_rows": ignored_rows,
        "candidate_count": len(merged_candidates),
        "candidate_pool": merged_candidates,
        "quality_pass_count": len(quality_pass_symbols),
        "quality_fail_count": len(rejected_candidates),
        "quality_pass_candidates": [row for row in merged_candidates if row.get("symbol") in quality_pass_symbols],
        "quality_fail_candidates": rejected_candidates,
        "rejected_candidates": rejected_candidates,
        "rejection_reasons": sorted({reason for item in rejected_candidates for reason in item.get("reasons", [])}),
        "score_distribution": _score_distribution(merged_candidates),
        "planned_keep_basic": planned_keep_basic,
        "planned_add": planned_add,
        "planned_remove": planned_remove,
        "planned_remove_reasons": sorted({item.get("remove_reason", "") for item in planned_remove if item.get("remove_reason")}),
        "after_count_expected": after_count_expected,
        "pool_size_after": after_count_expected,
        "not_filled_reason": not_filled_reason,
        "protected_overflow": bool(protected_overflow),
        "protected_overflow_reason": "protected_rows_exceed_max" if protected_overflow else "",
        "protected_violation": protected_violation,
        "managed_pool_mutation_performed": False,
        "actual_mutation_performed": False,
        "actual_order": False,
        "rotation_execution": False,
        "order_execution_enabled": False,
    }


def build_managed_pool_promotion_plan(
    current_rows: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
    holdings: list[dict[str, Any]] | None = None,
    config: ManagedPoolPromotionConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config if isinstance(config, ManagedPoolPromotionConfig) else ManagedPoolPromotionConfig(**(config or {}))
    configured_max = int(cfg.max_managed_pool_size if cfg.max_managed_pool_size is not None else MAX_MANAGED_POOL_SIZE)
    max_size = max(1, configured_max)
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
        reasons = _protected_reasons(row, holding_set, cfg)
        if reasons:
            protected_rows.append({"symbol": symbol, "reasons": reasons})
        elif _is_basic_added(row):
            removable_rows.append(row)
        keep.append({"symbol": symbol, "source_type": _source_type(row) or "unknown", "score": _score(row, 0.0)})

    sorted_candidates = _sort_candidates(candidates or [], cfg)
    existing_symbols = {_row_symbol(row) for row in rows}
    quality_results = [
        evaluate_candidate_promotion_quality(row, cfg, existing_symbols=existing_symbols)
        for row in sorted_candidates
    ]
    quality_by_symbol = {item["symbol"]: item for item in quality_results if item.get("symbol")}
    quality_pass_symbols = {item["symbol"] for item in quality_results if item.get("pass") and item.get("symbol")}
    rejected_candidates = [
        {
            "symbol": item.get("symbol", ""),
            "score": item.get("score", 0.0),
            "rank": item.get("rank", 999999),
            "trade_value": item.get("trade_value", 0.0),
            "reasons": item.get("reasons", []),
            "failed_reason": item.get("failed_reason", ""),
        }
        for item in quality_results
        if not item.get("pass")
    ]
    new_candidates = [
        row
        for row in sorted_candidates
        if row["symbol"] not in existing_symbols and row["symbol"] in quality_pass_symbols
    ]

    planned_add: list[dict[str, Any]] = []
    planned_remove: list[dict[str, Any]] = []
    current_size = len(rows)
    if cfg.auto_add_enabled:
        slots = max(0, max_size - current_size)
        for candidate in new_candidates[:slots]:
            quality = quality_by_symbol.get(candidate["symbol"], {})
            planned_add.append(
                {
                    **candidate,
                    "source_type": "basic_added",
                    "reason": candidate.get("reason") or "selected_by_basic_candidate",
                    "promotion_reason": "pool_has_free_slot",
                    "quality_gate_pass": True,
                    "quality_gate_reasons": quality.get("reasons", []),
                    "promotion_min_score": quality.get("promotion_min_score"),
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
                    quality = quality_by_symbol.get(best_new["symbol"], {})
                    planned_add.append(
                        {
                            **best_new,
                            "source_type": "basic_added",
                            "promotion_reason": "replace_lower_basic_added",
                            "quality_gate_pass": True,
                            "quality_gate_reasons": quality.get("reasons", []),
                            "promotion_min_score": quality.get("promotion_min_score"),
                            "actual_order": False,
                        }
                    )

    planned_rotation: list[dict[str, Any]] = []
    rotation_blocker = ""
    rotation_candidates_evaluated = 0
    if cfg.rotation_enabled:
        min_gap = 8.0 if cfg.rotation_min_score_gap is None else float(cfg.rotation_min_score_gap)
        min_promotion_score = _effective_promotion_min_score(cfg)
        rotation_targets = list(removable_rows)
        if not rotation_targets:
            rotation_blocker = "no_non_holding_rotation_target"
        elif not new_candidates:
            rotation_blocker = "no_new_candidate_for_rotation"
        for target in sorted(rotation_targets, key=lambda row: _score(row, 0.0)):
            if len(planned_rotation) >= max(1, int(cfg.max_rotation_per_cycle or 1)):
                break
            old_info = _normalized_rotation_score(target, role="managed", cfg=cfg)
            for candidate in new_candidates:
                rotation_candidates_evaluated += 1
                new_info = _normalized_rotation_score(candidate, role="candidate", cfg=cfg)
                gap = float(new_info["normalized_rotation_score"]) - float(old_info["normalized_rotation_score"])
                if min_promotion_score is not None and float(new_info["normalized_rotation_score"]) < float(min_promotion_score):
                    rotation_blocker = "candidate_below_min_promotion_score"
                    continue
                if gap < min_gap:
                    rotation_blocker = "rotation_candidate_below_margin"
                    continue
                planned_rotation.append(
                    {
                        "rotate_out": _row_symbol(target),
                        "rotate_in": candidate["symbol"],
                        "old_symbol": _row_symbol(target),
                        "new_symbol": candidate["symbol"],
                        "old_operating_score": old_info["raw_score"],
                        "old_rotation_score": old_info["normalized_rotation_score"],
                        "new_scanner_score": new_info["raw_score"],
                        "new_rotation_score": new_info["normalized_rotation_score"],
                        "score_gap": round(gap, 4),
                        "rotate_out_status": _text(target.get("status") or target.get("state")),
                        "rotate_out_source": _source_type(target),
                        "rotate_in_rank": candidate.get("rank"),
                        "min_promotion_score": min_promotion_score,
                        "rotation_margin": min_gap,
                        "cooldown_sec": int(cfg.rotation_cooldown_sec or 0),
                        "old_score_source": old_info["score_source"],
                        "new_score_source": new_info["score_source"],
                        "rotation_allowed": True,
                        "observe_only": True,
                        "managed_pool_mutation": False,
                        "actual_order": False,
                        "order_execution": False,
                        "rotation_execution": False,
                        "reason": "candidate_rotation_score_above_non_holding_managed",
                    }
                )
                break
            if planned_rotation:
                break

    protected_symbols = {item["symbol"] for item in protected_rows}
    protected_violation = any(item.get("symbol") in protected_symbols for item in planned_remove)
    pool_size_after = len(rows) + len(planned_add) - len(planned_remove)
    quality_pass_count = len([item for item in quality_results if item.get("pass")])
    quality_fail_count = len(rejected_candidates)
    remaining_slots = max(0, max_size - len(rows))
    not_filled_reason = ""
    if cfg.auto_add_enabled and remaining_slots > len(planned_add):
        if not sorted_candidates:
            not_filled_reason = "candidate_count_zero"
        elif quality_pass_count <= 0:
            not_filled_reason = "quality_gate_no_pass_candidates"
        elif len(planned_add) < min(remaining_slots, quality_pass_count):
            not_filled_reason = "quality_gate_pass_candidates_not_added"
        elif not bool(cfg.fill_to_max):
            not_filled_reason = "max_managed_pool_size_is_cap_not_target"
    return {
        "policy_supported": True,
        "config": asdict(cfg),
        "max_managed_pool_size": max_size,
        "fill_to_max": bool(cfg.fill_to_max),
        "quality_gate_enabled": bool(cfg.quality_gate_enabled),
        "promotion_min_score": _effective_promotion_min_score(cfg),
        "promotion_min_trade_value_krw": cfg.promotion_min_trade_value_krw,
        "current_pool_size": len(rows),
        "candidate_count": len(sorted_candidates),
        "remaining_slots": remaining_slots,
        "quality_pass_count": quality_pass_count,
        "quality_fail_count": quality_fail_count,
        "candidate_quality_results": quality_results,
        "rejected_candidates": rejected_candidates,
        "rejection_reasons": sorted({reason for item in rejected_candidates for reason in item.get("reasons", [])}),
        "score_distribution": _score_distribution(sorted_candidates),
        "not_filled_reason": not_filled_reason,
        "planned_keep": keep,
        "planned_add": planned_add,
        "planned_remove": planned_remove,
        "protected_rows": protected_rows,
        "planned_rotation": planned_rotation,
        "rotation_logic_detected": bool(cfg.rotation_enabled),
        "rotation_score_source": "normalized_rotation_score",
        "normalized_rotation_score_supported": True,
        "rotation_plan_observe_only": True,
        "rotation_policy_missing": False,
        "rotation_blocker": "" if planned_rotation else rotation_blocker,
        "rotation_candidates_evaluated": rotation_candidates_evaluated,
        "managed_pool_count_mode": "ai_dynamic" if configured_max <= 0 else "user_cap",
        "pool_size_after": pool_size_after,
        "pool_size_after_capped": min(pool_size_after, max_size),
        "protected_violation": protected_violation,
        "order_execution_enabled": bool(cfg.order_execution_enabled),
        "managed_pool_mutation": False,
        "actual_mutation_performed": False,
        "mutation_allowed": False,
    }


def build_managed_pool_trim_plan(
    current_rows: list[dict[str, Any]] | None,
    configured_max_size: int,
    holdings: list[dict[str, Any]] | None = None,
    config: ManagedPoolPromotionConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a protected max-size trim plan without mutating Managed Pool rows."""

    cfg = config if isinstance(config, ManagedPoolPromotionConfig) else ManagedPoolPromotionConfig(**(config or {}))
    max_size = max(1, min(50, int(configured_max_size or cfg.max_managed_pool_size or MAX_MANAGED_POOL_SIZE)))
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
    keep_rows: list[dict[str, Any]] = []
    for row in rows:
        reasons = _protected_reasons(row, holding_set, cfg)
        if reasons:
            protected_rows.append(_compact_pool_row(row, reasons=reasons))
        elif _is_basic_added(row):
            removable_rows.append(row)
        keep_rows.append(_compact_pool_row(row))

    before_count = len(rows)
    excess_count = max(0, before_count - max_size)
    planned_remove_rows = sorted(removable_rows, key=_trim_remove_sort_key)[:excess_count]
    planned_remove: list[dict[str, Any]] = []
    for row in planned_remove_rows:
        planned_remove.append(
            {
                **_compact_pool_row(row),
                "remove_reason": "max_size_apply_low_priority_basic_added",
                "actual_order": False,
            }
        )

    planned_symbols = {item.get("symbol") for item in planned_remove}
    protected_symbols = {item.get("symbol") for item in protected_rows}
    after_count_expected = before_count - len(planned_remove)
    protected_overflow = after_count_expected > max_size
    protected_overflow_reason = ""
    if protected_overflow:
        protected_overflow_reason = "protected_rows_exceed_max_or_not_enough_removable"

    return {
        "trim_supported": True,
        "max_managed_pool_size": max_size,
        "before_count": before_count,
        "trim_required": before_count > max_size,
        "excess_count": excess_count,
        "protected_rows": protected_rows,
        "removable_rows": [_compact_pool_row(row) for row in sorted(removable_rows, key=_trim_remove_sort_key)],
        "planned_keep": keep_rows,
        "planned_remove": planned_remove,
        "actual_remove_count": 0,
        "actual_rotation_count": 0,
        "after_count_expected": after_count_expected,
        "protected_overflow": bool(protected_overflow),
        "protected_overflow_reason": protected_overflow_reason,
        "protected_violation": bool(planned_symbols & protected_symbols),
        "managed_pool_mutation_performed": False,
        "actual_order": False,
        "order_execution_enabled": False,
    }


def build_rotation_intent_payload(
    plan: dict[str, Any] | None,
    *,
    source: str = "managed_pool_promotion_policy",
) -> dict[str, Any]:
    """Normalize planned rotation pairs into an observe-only UX/report payload."""

    planned = []
    if isinstance(plan, dict):
        planned = [item for item in (plan.get("planned_rotation") or []) if isinstance(item, dict)]

    pairs: list[dict[str, Any]] = []
    for item in planned:
        out_symbol = _symbol(item.get("rotate_out") or item.get("rotate_out_symbol"))
        in_symbol = _symbol(item.get("rotate_in") or item.get("rotate_in_symbol"))
        if not out_symbol or not in_symbol:
            continue
        out_score = _float(item.get("old_rotation_score", item.get("holding_score", item.get("rotate_out_score"))), 0.0)
        in_score = _float(item.get("new_rotation_score", item.get("candidate_score", item.get("rotate_in_score"))), 0.0)
        gap = _float(item.get("score_gap"), in_score - out_score)
        reason_text = "신규 후보 점수가 현재 관리종목보다 높음"
        pairs.append(
            {
                "rotate_out_symbol": out_symbol,
                "rotate_out_score": out_score,
                "rotate_out_status": _text(item.get("rotate_out_status") or "교체 검토"),
                "rotate_out_source": _text(item.get("rotate_out_source")),
                "rotate_in_symbol": in_symbol,
                "rotate_in_score": in_score,
                "rotate_in_rank": item.get("rotate_in_rank"),
                "score_gap": round(gap, 4),
                "reason": item.get("reason") or "candidate_score_above_holding",
                "reason_text": reason_text,
                "protection_note": item.get("protection_note") or "교체 검토만 표시, 실제 주문 없음",
                "order_execution": False,
                "actual_order": False,
                "rotation_execution": False,
            }
        )

    no_rotation_reason = ""
    if not pairs:
        no_rotation_reason = "no_rotation_pair_score_gap"

    return {
        "schema": "aits_rotation_intent_v1",
        "rotation_enabled": True,
        "actual_order": False,
        "rotation_execution": False,
        "source": source,
        "pairs": pairs,
        "pair_count": len(pairs),
        "no_rotation_reason": no_rotation_reason,
        "managed_pool_mutation": False,
    }


__all__ = [
    "MAX_MANAGED_POOL_SIZE",
    "ManagedPoolPromotionConfig",
    "evaluate_candidate_promotion_quality",
    "build_managed_pool_quality_rebuild_plan",
    "build_rotation_intent_payload",
    "build_managed_pool_promotion_plan",
    "build_managed_pool_trim_plan",
]
