from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import Counter
import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:
    requests = None

from app.core.aits_state import (
    ActionItem,
    AITSRuntimeState,
    ExecutionState,
    ExplainabilityState,
    IntelligenceState,
    MarketSnapshot,
    OversightState,
    PortfolioState,
    RegimeState,
    RuntimeMeta,
    SystemState,
)
from app.services.ai_decision_service import AIDecisionService
from app.services.explainability_service import ExplainabilityService
from app.services.portfolio_brain import PortfolioBrain
from app.services.regime_detector import RegimeDetector
from app.services.module_pack_resolver import ModulePackResolver
from app.services.order_service import OrderService
try:
    from app.services.ai_engine_provider import AIEngineProvider
except Exception:
    AIEngineProvider = None
try:
    from app.services.decision_router import DecisionRouter, normalize_provider
except Exception:
    DecisionRouter = None
    normalize_provider = None
from app.core.module_pack_state import (
    DEFAULT_MODULE_PACK_DEFINITIONS,
    DEFAULT_USER_MODULE_PACK_SELECTION,
    UserModulePackSelection,
    ModulePackRuntimeState,
)
try:
    from app.services.order_adapter import AITSOrderAdapter
except Exception:
    AITSOrderAdapter = None
try:
    from app.services.risk_guard import RiskGuard, build_risk_guard_input_from_action
except Exception:
    RiskGuard = None
    build_risk_guard_input_from_action = None


def build_normalized_holdings_snapshot(
    source_groups: list[tuple[str, list[dict]]],
    *,
    normalize_symbol,
    dust_threshold_krw: float = 5000.0,
    managed_holding_min_value_krw: float = 10000.0,
) -> dict:
    """Normalize prioritized holding sources into one runtime target snapshot."""
    merged: dict[str, dict] = {}
    source_conflicts: list[dict] = []
    source_priorities = {
        "live_account": 10,
        "investment_center": 20,
        "portfolio_positions": 30,
        "holdings_rows": 40,
        "managed_pool": 50,
    }

    def number(row: dict, *keys: str) -> float:
        for key in keys:
            try:
                value = float(str(row.get(key) or 0).replace(",", ""))
            except Exception:
                value = 0.0
            if value > 0.0:
                return value
        return 0.0

    def source_time(row: dict) -> tuple[str, float | None, str]:
        raw_value = next((row.get(key) for key in ("updated_at", "snapshot_at", "observed_at", "timestamp", "created_at") if row.get(key) not in (None, "")), None)
        if raw_value in (None, ""):
            return "", None, "unknown"
        try:
            if isinstance(raw_value, (int, float)) or str(raw_value).strip().replace(".", "", 1).isdigit():
                epoch = float(raw_value)
                if epoch > 10_000_000_000:
                    epoch /= 1000.0
                parsed = datetime.fromtimestamp(epoch)
            else:
                parsed = datetime.fromisoformat(str(raw_value).strip().replace("Z", "+00:00")).replace(tzinfo=None)
            age_sec = max(0.0, (datetime.now() - parsed).total_seconds())
            return str(raw_value), age_sec, "fresh" if age_sec <= 300.0 else "stale"
        except Exception:
            return str(raw_value), None, "unknown"

    def close_enough(left: float, right: float) -> bool:
        return bool(left > 0.0 and right > 0.0 and abs(left - right) <= max(1.0, abs(right) * 0.001))

    for source_path, rows in source_groups:
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            symbol = str(normalize_symbol(raw) or "").strip().upper()
            if not symbol or symbol == "KRW":
                continue
            balance = number(raw, "balance")
            locked = number(raw, "locked", "locked_qty")
            qty = max(number(raw, "qty", "quantity", "volume"), balance + locked, balance)
            source_type = str(raw.get("source_type") or raw.get("source") or "").strip().lower()
            if not (qty > 0.0 or raw.get("holding") or raw.get("is_holding") or raw.get("has_position") or source_type in {"live_holding", "external_holding", "holding"}):
                continue
            item = merged.setdefault(symbol, {
                "symbol": symbol,
                "market": symbol,
                "qty": 0.0,
                "available_qty": 0.0,
                "locked_qty": 0.0,
                "avg_buy_price": 0.0,
                "current_price": 0.0,
                "position_value_krw": 0.0,
                "source_paths": [],
                "source_type": "",
                "valuation_source": "unavailable",
                "avg_price_source": "unavailable",
                "current_price_source": "unavailable",
                "valuation_candidates": [],
            })
            if source_path not in item["source_paths"]:
                item["source_paths"].append(source_path)
            if not item["source_type"] and source_type:
                item["source_type"] = source_type
            if item["qty"] <= 0.0 and qty > 0.0:
                item["qty"] = qty
                item["available_qty"] = number(raw, "available_qty", "available", "balance") or qty
                item["locked_qty"] = locked
            avg = number(raw, "avg_buy_price", "avg_price", "avg")
            if item["avg_buy_price"] <= 0.0 and avg > 0.0:
                item["avg_buy_price"] = avg
                item["avg_price_source"] = source_path
            current = number(raw, "current_price", "trade_price", "price")
            if item["current_price"] <= 0.0 and current > 0.0:
                item["current_price"] = current
                item["current_price_source"] = source_path
            value = number(raw, "position_value_krw", "eval_krw", "eval_amount", "value_krw", "position_value")
            candidate_qty = qty or float(item.get("qty") or 0.0)
            derived_from_current = False
            if value <= 0.0 and candidate_qty > 0.0 and current > 0.0:
                value = candidate_qty * current
                derived_from_current = True
            if value > 0.0:
                updated_at, age_sec, freshness = source_time(raw)
                hint = str(raw.get("valuation_source") or "").strip().lower()
                cost_basis = candidate_qty * avg if candidate_qty > 0.0 and avg > 0.0 else 0.0
                if "cost_basis" in hint or close_enough(value, cost_basis):
                    value_kind = "cost_basis"
                elif "current_market" in hint or current > 0.0 or derived_from_current:
                    value_kind = "market_value"
                else:
                    value_kind = "reported_valuation"
                item["valuation_candidates"].append({
                    "source": source_path,
                    "source_priority": int(source_priorities.get(source_path, 90)),
                    "valuation_krw": float(value),
                    "qty": float(candidate_qty),
                    "current_price": float(current),
                    "avg_buy_price": float(avg),
                    "valuation_kind": value_kind,
                    "valuation_source_hint": hint or "-",
                    "updated_at": updated_at,
                    "age_sec": age_sec,
                    "freshness": freshness,
                })
                current_market_value = candidate_qty * current if candidate_qty > 0.0 and current > 0.0 else 0.0
                if value_kind == "cost_basis" and current_market_value > 0.0 and not close_enough(current_market_value, value):
                    item["valuation_candidates"].append({
                        "source": f"{source_path}_qty_times_current_price",
                        "source_priority": int(source_priorities.get(source_path, 90)),
                        "valuation_krw": float(current_market_value),
                        "qty": float(candidate_qty),
                        "current_price": float(current),
                        "avg_buy_price": float(avg),
                        "valuation_kind": "market_value",
                        "valuation_source_hint": "qty_times_current_price",
                        "updated_at": updated_at,
                        "age_sec": age_sec,
                        "freshness": freshness,
                    })
            item["external"] = bool(item.get("external") or source_type == "external_holding")
            item["live_holding"] = bool(item.get("live_holding") or source_path == "live_account" or source_type in {"live_holding", "external_holding", "holding"})
            for key in ("name", "target_weight_pct", "target_weight", "weight_pct", "holding_age"):
                if item.get(key) in (None, "", 0, 0.0) and raw.get(key) not in (None, ""):
                    item[key] = raw.get(key)

    all_holdings: list[dict] = []
    dust_holdings: list[dict] = []
    manageable_holdings: list[dict] = []
    missing_pnl_source: list[str] = []
    for symbol in sorted(merged):
        item = merged[symbol]
        qty = float(item.get("qty") or 0.0)
        candidates = list(item.get("valuation_candidates") or [])
        freshness_rank = {"fresh": 0, "unknown": 1, "stale": 2}
        kind_rank = {"market_value": 0, "reported_valuation": 1, "cost_basis": 2}
        candidates.sort(key=lambda row: (
            kind_rank.get(str(row.get("valuation_kind") or ""), 3),
            freshness_rank.get(str(row.get("freshness") or "unknown"), 1),
            int(row.get("source_priority") or 90),
        ))
        selected = candidates[0] if candidates else {}
        current = float(selected.get("current_price") or item.get("current_price") or 0.0)
        value = float(selected.get("valuation_krw") or 0.0)
        selected_source = str(selected.get("source") or "unavailable")
        selected_kind = str(selected.get("valuation_kind") or "unavailable")
        if current <= 0.0 and qty > 0.0 and value > 0.0:
            current = value / qty
            item["current_price_source"] = f"{selected_source}_valuation_per_qty"
        if value <= 0.0 and qty > 0.0 and current > 0.0:
            value = qty * current
            selected_source = "qty_times_current_price"
            selected_kind = "market_value"
        item["valuation_source"] = selected_source
        item["selected_valuation_source"] = selected_source
        item["selected_valuation_kind"] = selected_kind
        item["selected_valuation_krw"] = value
        item["alternative_valuations"] = [dict(row) for row in candidates[1:]]
        item["dust_by_source"] = [
            str(row.get("source") or "unavailable")
            for row in candidates
            if 0.0 < float(row.get("valuation_krw") or 0.0) < managed_holding_min_value_krw
        ]
        boundary_candidates = [
            row for row in candidates
            if abs(float(row.get("valuation_krw") or 0.0) - managed_holding_min_value_krw) <= 100.0
        ]
        closest_boundary = min(
            boundary_candidates,
            key=lambda row: abs(float(row.get("valuation_krw") or 0.0) - managed_holding_min_value_krw),
            default=None,
        )
        boundary_gap = (
            float(closest_boundary.get("valuation_krw") or 0.0) - managed_holding_min_value_krw
            if isinstance(closest_boundary, dict) else None
        )
        meaningful_alternatives = [
            row for row in candidates[1:]
            if abs(float(row.get("valuation_krw") or 0.0) - value) > max(100.0, abs(value) * 0.05)
            or (float(row.get("valuation_krw") or 0.0) < managed_holding_min_value_krw) != (value < managed_holding_min_value_krw)
        ]
        stale_low_conflict = any(
            str(row.get("freshness") or "") == "stale" and float(row.get("valuation_krw") or 0.0) < value
            for row in meaningful_alternatives
        )
        cost_basis_conflict = any(str(row.get("valuation_kind") or "") == "cost_basis" for row in meaningful_alternatives)
        conflict_reason = (
            "stale_low_valuation_conflict" if stale_low_conflict
            else "cost_basis_valuation_conflict" if cost_basis_conflict
            else "valuation_source_difference" if meaningful_alternatives
            else ""
        )
        item["valuation_source_conflict"] = bool(meaningful_alternatives)
        item["valuation_conflict_reason"] = conflict_reason
        item["stale_low_valuation_conflict"] = stale_low_conflict
        item["threshold_boundary_detected"] = bool(boundary_candidates)
        item["boundary_gap_krw"] = boundary_gap
        if meaningful_alternatives:
            source_conflicts.append({
                "symbol": symbol,
                "selected_valuation_source": selected_source,
                "selected_valuation_krw": value,
                "alternative_valuations": [dict(row) for row in meaningful_alternatives],
                "conflict_reason": conflict_reason,
            })
        avg = float(item.get("avg_buy_price") or 0.0)
        pnl_available = bool(avg > 0.0 and current > 0.0)
        dust = bool(qty > 0.0 and value < managed_holding_min_value_krw)
        manageable = bool(qty > 0.0 and value >= managed_holding_min_value_krw and not dust and (current > 0.0 or value > 0.0))
        item.update({
            "position_value_krw": value,
            "eval_krw": value,
            "value_krw": value,
            "avg_price": avg,
            "current_price": current,
            "price": current,
            "pnl_krw": (current - avg) * qty if pnl_available else None,
            "pnl_pct": ((current - avg) / avg * 100.0) if pnl_available else None,
            "pnl_source": "avg_and_current_price" if pnl_available else "unavailable",
            "dust": dust,
            "dust_holding": dust,
            "is_dust_holding": dust,
            "manageable": manageable,
            "manageable_holding": manageable,
            "protected": manageable,
            "blocker": "" if pnl_available else "pnl_source_missing_for_manageable_holding",
            "dust_threshold_krw": float(dust_threshold_krw),
            "managed_holding_min_value_krw": float(managed_holding_min_value_krw),
            "final_dust": dust,
            "final_manageable": manageable,
        })
        all_holdings.append(item)
        if dust:
            dust_holdings.append(item)
        elif manageable:
            manageable_holdings.append(item)
            if not pnl_available:
                missing_pnl_source.append(symbol)
    return {
        "all_holdings": all_holdings,
        "dust_holdings": dust_holdings,
        "manageable_holdings": manageable_holdings,
        "normalized_all_holding_symbols": [row["symbol"] for row in all_holdings],
        "normalized_dust_holding_symbols": [row["symbol"] for row in dust_holdings],
        "normalized_manageable_holding_symbols": [row["symbol"] for row in manageable_holdings],
        "missing_pnl_source": sorted(missing_pnl_source),
        "source_conflicts": source_conflicts,
    }


class AITSDecisionOutcomeTracker:
    """Persist and evaluate decision outcomes from caller-provided live snapshots."""

    CHECKPOINT_SECONDS = {"outcome_5m": 300, "outcome_15m": 900, "outcome_1h": 3600}
    ACTIONS = {"wait", "hold", "buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}

    def __init__(self, root: Path | str = Path("data") / "ai_decision_training") -> None:
        self.root = Path(root)
        self.state_path = self.root / "outcome_tracking_state.json"

    @staticmethod
    def number(value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def percent_change(cls, before: Any, after: Any) -> Optional[float]:
        before_value = cls.number(before)
        after_value = cls.number(after)
        if before_value is None or after_value is None or before_value <= 0.0:
            return None
        return round((after_value - before_value) / before_value * 100.0, 6)

    def load(self) -> dict:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
            if isinstance(value, dict) and isinstance(value.get("decisions"), dict):
                return value
        except Exception:
            pass
        return {"schema": "aits_decision_outcome_tracking_state.v1", "decisions": {}}

    def save(self, state: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / "outcome_tracking_state.tmp"
        temporary.write_text(json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8")
        temporary.replace(self.state_path)

    def append(self, filename: str, record: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / filename).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def register(self, record: dict, *, now: Optional[float] = None) -> bool:
        decision_id = str(record.get("decision_id") or "")
        action = str(record.get("final_action") or "").lower()
        if not decision_id or action not in self.ACTIONS:
            return False
        state = self.load()
        if decision_id in state["decisions"]:
            return True
        created_at = float(now if now is not None else time.time())
        value = dict(record)
        value.update(
            {
                "schema": "aits_decision_outcome.v1",
                "created_at": created_at,
                "target_checkpoints": list(self.CHECKPOINT_SECONDS),
                "checkpoints": {
                    name: {
                        "checkpoint_name": name,
                        "due_at": created_at + seconds,
                        "evaluated_at": None,
                        "status": "pending",
                    }
                    for name, seconds in self.CHECKPOINT_SECONDS.items()
                },
                "final_outcome": {"status": "pending"},
                "learning_record_ready": False,
            }
        )
        state["decisions"][decision_id] = value
        self.save(state)
        return True

    def link_execution(self, decision_id: str, execution: dict) -> bool:
        if not decision_id:
            return False
        state = self.load()
        record = state["decisions"].get(decision_id)
        if not isinstance(record, dict):
            return False
        record["execution_result"] = dict(execution.get("order_result") or {})
        record["actual_order"] = bool(execution.get("actual_order"))
        record["submitted"] = int(execution.get("submitted") or 0)
        record["position_after"] = execution.get("position_after")
        record["portfolio_after"] = execution.get("portfolio_after")
        self.save(state)
        return True

    @staticmethod
    def classify(record: dict, current: dict) -> tuple[str, float, str]:
        action = str(record.get("final_action") or "wait").lower()
        before = dict(record.get("decision_snapshot") or {})
        price_change = AITSDecisionOutcomeTracker.percent_change(before.get("price"), current.get("price"))
        portfolio_change = AITSDecisionOutcomeTracker.percent_change(
            before.get("portfolio_value_krw"), current.get("portfolio_value_krw")
        )
        observed = price_change if price_change is not None else portfolio_change
        if observed is None:
            return "data_unavailable", 0.0, "실제 가격 또는 자산 평가 source가 없어 결과 평가를 보류했습니다."
        if action in {"wait", "hold"}:
            if observed <= -1.0:
                return "avoided_loss", min(1.0, abs(observed) / 5.0), "대기 판단 이후 하락해 위험 회피 가능성을 기록했습니다."
            if observed >= 2.0:
                return "missed_opportunity", -min(1.0, observed / 8.0), "대기 판단 이후 상승해 기회비용 가능성을 기록했습니다."
            return "good_wait", max(0.1, 1.0 - abs(observed) / 2.0), "대기 판단 이후 큰 방향 변화가 없어 판단 유지가 적절했습니다."
        if action in {"buy", "add"}:
            if observed > 0:
                return "good_buy", min(1.0, observed / 5.0), "진입 판단 이후 가격이 상승했습니다."
            return "bad_buy", max(-1.0, observed / 5.0), "진입 판단 이후 가격이 하락했습니다."
        if action in {"sell", "reduce", "take_profit", "stop_loss"}:
            if observed < 0:
                label = "good_stop_loss" if action == "stop_loss" else ("good_take_profit" if action == "take_profit" else "good_sell")
                return label, min(1.0, abs(observed) / 5.0), "매도 판단 이후 가격이 하락해 회피 또는 실현 효과를 기록했습니다."
            label = "bad_take_profit" if action == "take_profit" else "early_sell"
            return label, -min(1.0, observed / 5.0), "매도 판단 이후 가격이 상승해 조기 매도 가능성을 기록했습니다."
        if action == "rotate":
            candidate_change = AITSDecisionOutcomeTracker.percent_change(
                before.get("candidate_price"), current.get("candidate_price")
            )
            held_change = price_change
            if candidate_change is None or held_change is None:
                return "inconclusive", 0.0, "회전 대상의 상대 성과 source가 충분하지 않아 판단을 보류했습니다."
            gap = candidate_change - held_change
            return ("useful_rotation", min(1.0, gap / 5.0), "회전 후보의 상대 성과가 개선됐습니다.") if gap > 0 else ("bad_rotation", max(-1.0, gap / 5.0), "회전 후보의 상대 성과가 개선되지 않았습니다.")
        return "inconclusive", 0.0, "결과 방향은 확인했지만 분류 근거가 충분하지 않습니다."

    @staticmethod
    def compare_providers(record: dict, *, label: str, score: float) -> dict:
        local_action = str(record.get("local_action") or "")
        external_action = str(record.get("external_action") or "")
        final_source = str(record.get("final_provider_source") or "")
        external_called = bool(record.get("external_called"))
        match = bool(local_action and external_action and local_action == external_action)
        changed = bool(external_called and local_action and external_action and local_action != external_action)
        useful = bool(changed and score > 0.0)
        waste = bool(external_called and (match or (changed and score <= 0.0)))
        order_actions = {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}
        confidence_gap = None
        try:
            confidence_gap = round(float(record.get("external_confidence")) - float(record.get("local_confidence")), 6)
        except (TypeError, ValueError):
            pass
        return {
            "provider_comparison_ready": bool(local_action or external_action),
            "local_external_action_match": match,
            "local_external_disagreed": bool(local_action and external_action and not match),
            "local_external_confidence_gap": confidence_gap,
            "final_provider_source": final_source,
            "final_followed_local": final_source.startswith("local"),
            "final_followed_external": final_source in {"openai", "gemini"},
            "external_called": external_called,
            "external_blocked": bool(record.get("external_blocked")),
            "escalation_reason": str(record.get("escalation_reason") or ""),
            "cost_guard_blocker": str(record.get("cost_guard_blocker") or ""),
            "external_changed_action": changed,
            "external_changed_risk_level": bool(
                local_action in order_actions and external_action not in order_actions
                or local_action not in order_actions and external_action in order_actions
            ),
            "external_call_value_estimate": "useful" if useful else ("possibly_unnecessary" if waste else "inconclusive"),
            "provider_outcome_label": "useful_external_call" if useful else ("unnecessary_external_call" if waste else label),
            "provider_outcome_score": score,
            "external_call_was_useful": useful,
            "external_call_waste_suspected": waste,
            "local_would_have_been_safe": bool(local_action in {"wait", "hold"} and score >= 0.0),
            "local_learning_value": abs(score) if label != "data_unavailable" else 0.0,
            "recommended_future_route": "local_candidate" if local_action in {"wait", "hold"} and score >= 0.0 else "retain_escalation_policy",
        }

    def evaluate_due(self, snapshot_provider, *, now: Optional[float] = None) -> dict:
        evaluated_at = float(now if now is not None else time.time())
        state = self.load()
        events: list[dict] = []
        dirty = False
        for record in list(state["decisions"].values()):
            if not isinstance(record, dict):
                continue
            for checkpoint_name, checkpoint in list((record.get("checkpoints") or {}).items()):
                if not isinstance(checkpoint, dict) or checkpoint.get("status") != "pending":
                    continue
                due_at = float(checkpoint.get("due_at") or evaluated_at + 1)
                if evaluated_at < due_at:
                    continue
                logging.getLogger("aits").info(
                    "[AITS][OutcomeTracker] event=outcome_checkpoint_due decision_id=%s task=%s scope=%s symbol=%s checkpoint=%s due_at=%s action=%s final_provider_source=%s actual_order=%s submitted=%s",
                    record.get("decision_id") or "-", record.get("task") or "-", record.get("scope") or "-",
                    record.get("symbol") or "-", checkpoint_name, due_at, record.get("final_action") or "-",
                    record.get("final_provider_source") or "-", bool(record.get("actual_order")), int(record.get("submitted") or 0),
                )
                current = dict(snapshot_provider(record) or {})
                before = dict(record.get("decision_snapshot") or {})
                label, score, reason_ko = self.classify(record, current)
                status = "skipped" if label == "data_unavailable" else "evaluated"
                late = evaluated_at - due_at > 60.0 and status == "evaluated"
                checkpoint.update(
                    {
                        "evaluated_at": evaluated_at,
                        "status": status,
                        "late_evaluated": late,
                        "price_at_decision": before.get("price"),
                        "price_at_checkpoint": current.get("price"),
                        "price_change_pct": self.percent_change(before.get("price"), current.get("price")),
                        "position_value_at_decision": before.get("position_value_krw"),
                        "position_value_at_checkpoint": current.get("position_value_krw"),
                        "pnl_change_pct": self.percent_change(before.get("position_value_krw"), current.get("position_value_krw")),
                        "portfolio_value_at_decision": before.get("portfolio_value_krw"),
                        "portfolio_value_at_checkpoint": current.get("portfolio_value_krw"),
                        "portfolio_change_pct": self.percent_change(before.get("portfolio_value_krw"), current.get("portfolio_value_krw")),
                        "action_was_executed": bool(record.get("actual_order")),
                        "order_submitted": bool(int(record.get("submitted") or 0) > 0),
                        "order_filled": bool((record.get("execution_result") or {}).get("filled")),
                        "order_side": str((record.get("execution_result") or {}).get("side") or ""),
                        "order_qty": (record.get("execution_result") or {}).get("qty"),
                        "order_krw": (record.get("execution_result") or {}).get("amount_krw"),
                        "outcome_label": label,
                        "outcome_score": score,
                        "outcome_reason_ko": reason_ko,
                        "blocker": "source_data_unavailable" if label == "data_unavailable" else "",
                        "source": current.get("data_source"),
                    }
                )
                comparison = self.compare_providers(record, label=label, score=score)
                safe_for_training = bool(record.get("payload_hash") and record.get("final_action") and label != "data_unavailable")
                candidate_change = self.percent_change(before.get("candidate_price"), current.get("candidate_price"))
                held_change = self.percent_change(before.get("price"), current.get("price"))
                opportunity_gap_change = (
                    round(candidate_change - held_change, 6)
                    if candidate_change is not None and held_change is not None else None
                )
                dataset = {
                    "schema": "aits_decision_outcome.v1",
                    "decision_id": record.get("decision_id"),
                    "created_at": record.get("created_at"),
                    "evaluated_at": evaluated_at,
                    "task": record.get("task"),
                    "scope": record.get("scope"),
                    "symbol": record.get("symbol"),
                    "payload_hash": record.get("payload_hash"),
                    "feature_manifest_hash": record.get("feature_manifest_hash"),
                    "local_decision": {"action": record.get("local_action"), "confidence": record.get("local_confidence")},
                    "external_decision": {"action": record.get("external_action"), "confidence": record.get("external_confidence")},
                    "final_decision": {"provider": record.get("final_provider_source"), "action": record.get("final_action"), "confidence": record.get("final_confidence")},
                    "local_model_id": record.get("local_model_id"),
                    "local_model_prediction": record.get("local_model_prediction") or record.get("local_model_action"),
                    "local_model_confidence": record.get("local_model_confidence"),
                    "model_action_quality_score": record.get("model_action_quality_score"),
                    "model_provider_value_score": record.get("model_provider_value_score"),
                    "local_model_risk_score": record.get("local_model_risk_score"),
                    "local_model_used_for_final": bool(record.get("local_model_used_for_final")),
                    "local_model_not_used_reason": str(record.get("local_model_not_used_reason") or ""),
                    "local_model_live_allowed": bool(record.get("local_model_live_allowed")),
                    "local_model_live_blocker": str(record.get("local_model_live_blocker") or ""),
                    "execution_result": record.get("execution_result"),
                    "checkpoint": checkpoint,
                    "provider_comparison": comparison,
                    "opportunity_cost": {
                        "candidate_at_decision": before.get("candidate_symbol"),
                        "candidate_price_change_pct": candidate_change,
                        "held_symbol_price_change_pct": held_change,
                        "opportunity_gap_change": opportunity_gap_change,
                        "portfolio_opportunity_score": before.get("opportunity_gap"),
                        "missed_move_detected": bool(label == "missed_opportunity"),
                        "avoided_drawdown_detected": bool(label == "avoided_loss"),
                    },
                    "outcome_label": label,
                    "outcome_score": score,
                    "learning_tags": [str(record.get("final_action") or ""), checkpoint_name, label],
                    "data_quality": "acceptable" if safe_for_training else "unavailable",
                    "safe_for_local_training": safe_for_training,
                }
                self.append("outcome_records.jsonl", dataset)
                self.append(
                    "provider_comparison_outcomes.jsonl",
                    {**comparison, "schema": "aits_provider_comparison_outcome.v1", "decision_id": record.get("decision_id"), "checkpoint": checkpoint_name, "evaluated_at": evaluated_at},
                )
                events.append({"record": record, "checkpoint": checkpoint, "checkpoint_name": checkpoint_name, "late": late})
                dirty = True
            checkpoints = [item for item in (record.get("checkpoints") or {}).values() if isinstance(item, dict)]
            if checkpoints and all(item.get("status") != "pending" for item in checkpoints) and (record.get("final_outcome") or {}).get("status") == "pending":
                usable = [item for item in checkpoints if item.get("outcome_label") != "data_unavailable"]
                final_label = usable[-1].get("outcome_label") if usable else "data_unavailable"
                final_score = round(sum(float(item.get("outcome_score") or 0.0) for item in usable) / len(usable), 6) if usable else 0.0
                record["final_outcome"] = {"status": "evaluated" if usable else "skipped", "evaluated_at": evaluated_at, "outcome_label": final_label, "outcome_score": final_score}
                record["learning_record_ready"] = bool(usable and record.get("payload_hash") and record.get("final_action"))
                events.append({"record": record, "finalized": True})
                dirty = True
        if dirty:
            self.save(state)
        pending = sum(
            1 for record in state["decisions"].values() if isinstance(record, dict)
            for checkpoint in (record.get("checkpoints") or {}).values() if isinstance(checkpoint, dict) and checkpoint.get("status") == "pending"
        )
        return {"events": events, "evaluated": sum("checkpoint" in event for event in events), "pending": pending}


class AITSLocalTrainingDatasetCurator:
    """Build a deduplicated, allow-listed LOCAL training dataset from outcome evidence."""

    SCHEMA = "aits_local_training_curated_record.v1"
    DATASET_VERSION = "v1"
    VALID_TASKS = {
        "position_management_decision",
        "portfolio_management_decision",
        "ai_redecision",
        "buy_decision",
        "sell_decision",
        "rotation_decision",
        "promotion_decision",
        "managed_pool_promotion_decision",
    }
    VALID_ACTIONS = AITSDecisionOutcomeTracker.ACTIONS
    ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"}

    def __init__(self, root: Path | str = Path("data") / "ai_decision_training") -> None:
        self.root = Path(root)
        self.outcome_path = self.root / "outcome_records.jsonl"
        self.provider_path = self.root / "provider_comparison_outcomes.jsonl"
        self.state_path = self.root / "outcome_tracking_state.json"
        self.curated_path = self.root / "curated_local_training_records.jsonl"
        self.excluded_path = self.root / "excluded_local_training_records.jsonl"
        self.summary_path = self.root / "curated_local_training_summary.json"

    @staticmethod
    def _stable_hash(value: Any, length: int = 24) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:length]

    @staticmethod
    def _list(value: Any) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item or "").strip()]
        return [str(value)] if str(value or "").strip() else []

    def _read_jsonl(self, path: Path) -> tuple[list[dict], int, int]:
        rows: list[dict] = []
        corrupted = 0
        duplicates = 0
        seen: set[str] = set()
        if not path.exists():
            return rows, corrupted, duplicates
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except Exception:
                    corrupted += 1
                    continue
                if not isinstance(value, dict):
                    corrupted += 1
                    continue
                fingerprint = self._stable_hash(value, 32)
                if fingerprint in seen:
                    duplicates += 1
                    continue
                seen.add(fingerprint)
                rows.append(value)
        return rows, corrupted, duplicates

    def _load_state_decisions(self) -> dict[str, dict]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
            decisions = value.get("decisions") if isinstance(value, dict) else {}
            return {str(key): dict(item) for key, item in (decisions or {}).items() if isinstance(item, dict)}
        except Exception:
            return {}

    @staticmethod
    def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        temporary.replace(path)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _scope_valid(task: str, scope_type: str, scope: str, symbol: str) -> bool:
        if task == "portfolio_management_decision" or scope_type == "portfolio":
            return scope == "PORTFOLIO" and not symbol
        return bool(symbol.startswith("KRW-") and scope in {symbol, ""})

    def _classify_training_gate(self, record: dict, checkpoints: list[dict]) -> dict:
        reasons: list[str] = []
        decision_id = str(record.get("decision_id") or "")
        payload_hash = str(record.get("payload_hash") or "")
        task = str(record.get("task") or "")
        scope_type = str(record.get("scope_type") or "")
        scope = str(record.get("scope") or "")
        symbol = str(record.get("symbol") or "")
        action = str(record.get("final_action") or "").lower()
        provider = str(record.get("final_provider_source") or "")
        payload_grade = str(record.get("payload_quality_grade") or "").upper()
        evaluated = [item for item in checkpoints if item.get("status") == "evaluated"]
        labels = [str(item.get("outcome_label") or "") for item in evaluated]
        sources = [str(item.get("source") or "") for item in evaluated]
        blockers = self._list(record.get("safety_blockers")) + self._list(record.get("risk_blockers"))
        blockers += [str(item.get("blocker")) for item in checkpoints if str(item.get("blocker") or "")]
        blocker_text = ",".join(blockers).lower()

        if not decision_id:
            reasons.append("missing_decision_id")
        if not payload_hash:
            reasons.append("missing_payload_hash")
        if task not in self.VALID_TASKS:
            reasons.append("task_invalid")
        if not self._scope_valid(task, scope_type, scope, symbol):
            reasons.append("task_scope_invalid")
        if action not in self.VALID_ACTIONS:
            reasons.append("action_schema_invalid")
        if not provider:
            reasons.append("provider_context_missing")
        if record.get("provider_context_available") is False:
            reasons.append("provider_context_missing")
        if payload_grade in {"D", "F"}:
            reasons.append("payload_quality_too_low")
        elif not payload_grade:
            reasons.append("payload_quality_missing")
        if not evaluated:
            reasons.append("outcome_not_evaluated")
        if evaluated and all(label in {"", "data_unavailable"} for label in labels):
            reasons.append("data_unavailable")
        if evaluated and all(not source or "unavailable" in source or source == "unknown" for source in sources):
            reasons.append("price_source_unavailable" if symbol else "valuation_source_unavailable")
        if self._list(record.get("missing_critical_features")):
            reasons.append("payload_critical_missing")
        if any(label == "inconclusive" for label in labels) and not any(label not in {"", "inconclusive", "data_unavailable"} for label in labels):
            reasons.append("inconclusive_outcome")
        if "valuation_unit_mismatch" in blocker_text or bool(record.get("valuation_unit_mismatch")):
            reasons.append("valuation_unit_mismatch")
        if bool(record.get("market_data_stale")) or "stale" in blocker_text or any("stale" in source for source in sources):
            reasons.append("stale_market_data")
        provenance_text = " ".join(
            str(record.get(key) or "").lower() for key in ("trigger_reason", "source", "record_source")
        )
        if bool(record.get("manual_action") or record.get("forced_action") or record.get("test_record")) or any(
            token in provenance_text for token in ("manual", "forced", "fixture", "test_record")
        ):
            reasons.append("manual_or_forced_action")
        decision_action = str(record.get("decision_action") or "").lower()
        if decision_action and action and decision_action != action:
            reasons.append("decision_action_mismatch")
        actual_order = record.get("actual_order")
        submitted = int(record.get("submitted") or 0)
        execution = record.get("execution_result") if isinstance(record.get("execution_result"), dict) else {}
        if actual_order is None:
            reasons.append("actual_order_unclear")
        if submitted > 0 and not execution:
            reasons.append("reconciliation_missing")
        if submitted > 0 and not str(execution.get("request_id") or execution.get("status") or ""):
            reasons.append("reconciliation_missing")
        reasons = sorted(set(reasons))
        safe = not reasons
        severity = "none" if safe else ("critical" if any(item in reasons for item in {"manual_or_forced_action", "reconciliation_missing", "valuation_unit_mismatch"}) else "exclude")
        quality = payload_grade if safe and payload_grade in {"A", "B", "C"} else ("F" if "outcome_not_evaluated" in reasons else "D")
        can_be_used_for = {
            "local_action_learning": safe,
            "local_risk_learning": safe or bool(blockers),
            "provider_routing_learning": bool(provider and record.get("local_action")),
            "opportunity_cost_learning": safe and action in {"wait", "hold", "rotate"},
            "wait_hold_learning": safe and action in {"wait", "hold"},
            "buy_sell_learning": safe and action in self.ORDER_ACTIONS - {"rotate"},
            "portfolio_learning": safe and scope_type == "portfolio",
        }
        return {
            "safe_for_local_training": safe,
            "training_gate_status": "passed" if safe else "excluded",
            "training_quality_grade": quality,
            "exclusion_reasons": reasons,
            "exclusion_severity": severity,
            "can_be_used_for": can_be_used_for,
        }

    @staticmethod
    def _classify_action_tags(action: str, label: str, scope_type: str, blockers: list[str]) -> list[str]:
        tags: list[str] = []
        if action in {"wait", "hold"}:
            mapping = {
                "good_wait": "good_wait" if action == "wait" else "good_hold",
                "missed_opportunity": "missed_opportunity",
                "avoided_loss": "avoided_loss",
                "data_unavailable": "data_gap_wait",
            }
            tags.append(mapping.get(label, "bad_wait" if action == "wait" else "bad_hold"))
        elif action in {"buy", "add"}:
            tags.append("good_entry" if label == "good_buy" else ("bad_entry" if label == "bad_buy" else "avoided_bad_buy"))
        elif action in {"sell", "reduce", "take_profit", "stop_loss"}:
            mapping = {
                "good_sell": "good_exit",
                "early_sell": "early_exit",
                "good_take_profit": "good_take_profit",
                "bad_take_profit": "bad_take_profit",
                "good_stop_loss": "good_stop_loss",
                "avoided_loss": "avoided_loss",
            }
            tags.append(mapping.get(label, "late_exit"))
            if any("valuation_unit_mismatch" in blocker for blocker in blockers):
                tags.append("unit_guard_block_correct")
        elif action == "rotate":
            tags.append("good_rotation" if label == "useful_rotation" else ("bad_rotation" if label == "bad_rotation" else "missed_rotation"))
        if scope_type == "portfolio":
            tags.append("good_portfolio_wait" if label == "good_wait" else "bad_portfolio_wait")
        return sorted(set(tags))

    @staticmethod
    def _classify_provider_value(comparison: dict, outcome_score: float) -> dict:
        match = bool(comparison.get("local_external_action_match"))
        changed = bool(comparison.get("external_changed_action"))
        useful = bool(comparison.get("external_call_was_useful"))
        waste = bool(comparison.get("external_call_waste_suspected"))
        external_called = bool(comparison.get("external_called"))
        external_blocked = bool(comparison.get("external_blocked"))
        tags: list[str] = []
        if match:
            tags.append("local_external_agreed")
        elif comparison.get("local_external_disagreed"):
            tags.append("local_external_disagreed")
        if useful:
            tags += ["external_correct", "external_improved_decision"]
        elif waste:
            tags.append("external_unnecessary")
        elif not external_called and not external_blocked and outcome_score >= 0:
            tags += ["local_correct", "local_only_safe"]
        elif external_blocked and outcome_score >= 0:
            tags.append("external_blocked_no_issue")
        elif external_blocked and outcome_score < 0:
            tags.append("external_blocked_possible_opportunity_loss")
        if changed and bool(comparison.get("external_changed_risk_level")):
            tags.append("external_risk_reduced" if outcome_score >= 0 else "external_missed_opportunity")
        label = "useful_external" if useful else ("unnecessary_external" if waste else ("local_sufficient" if outcome_score >= 0 else "route_review"))
        route = str(comparison.get("recommended_future_route") or ("local_candidate" if outcome_score >= 0 else "retain_escalation_policy"))
        return {
            "provider_value_label": label,
            "provider_value_score": outcome_score,
            "provider_learning_tags": sorted(set(tags)),
            "external_call_was_useful": useful,
            "external_call_waste_suspected": waste,
            "recommended_future_provider_route": route,
            "recommended_escalation_policy_adjustment": "review_external_threshold" if waste else "retain_current_policy",
        }

    @staticmethod
    def _classify_opportunity(source: dict) -> dict:
        opportunity = dict(source.get("opportunity_cost") or {})
        candidate_move = AITSDecisionOutcomeTracker.number(opportunity.get("candidate_price_change_pct"))
        held_move = AITSDecisionOutcomeTracker.number(opportunity.get("held_symbol_price_change_pct"))
        portfolio_move = AITSDecisionOutcomeTracker.number(
            (source.get("checkpoint") or {}).get("portfolio_change_pct") if isinstance(source.get("checkpoint"), dict) else None
        )
        missed = bool(opportunity.get("missed_move_detected"))
        avoided = bool(opportunity.get("avoided_drawdown_detected"))
        if candidate_move is None and held_move is None and portfolio_move is None:
            label, score = "data_unavailable_for_opportunity", 0.0
        elif avoided:
            label, score = "avoided_large_drawdown", min(1.0, abs(held_move or portfolio_move or 0.0) / 5.0)
        elif missed:
            move = candidate_move if candidate_move is not None else (held_move or 0.0)
            label, score = ("missed_strong_move" if abs(move) >= 2.0 else "missed_small_move"), -min(1.0, abs(move) / 8.0)
        elif held_move is not None and abs(held_move) < 1.0:
            label, score = "wait_neutral", max(0.1, 1.0 - abs(held_move))
        else:
            label, score = "hold_reasonable", 0.1
        return {
            "opportunity_cost_evaluated": label != "data_unavailable_for_opportunity",
            "candidate_move_pct": candidate_move,
            "held_symbol_move_pct": held_move,
            "portfolio_move_pct": portfolio_move,
            "missed_move_detected": missed,
            "avoided_drawdown_detected": avoided,
            "opportunity_cost_label": label,
            "opportunity_cost_score": score,
            "opportunity_learning_tags": [label],
        }

    def _build_curated_record(self, state: dict, sources: list[dict], provider_rows: list[dict]) -> dict:
        latest = max(sources, key=lambda item: float(item.get("evaluated_at") or 0.0), default={})
        checkpoint_map: dict[str, dict] = {}
        for source in sources:
            checkpoint = dict(source.get("checkpoint") or {})
            name = str(checkpoint.get("checkpoint_name") or "")
            if name:
                checkpoint_map[name] = checkpoint
        if not checkpoint_map:
            checkpoint_map = {str(key): dict(value) for key, value in (state.get("checkpoints") or {}).items() if isinstance(value, dict)}
        checkpoints = list(checkpoint_map.values())
        final = dict(state.get("final_outcome") or {})
        final_label = str(final.get("outcome_label") or latest.get("outcome_label") or "inconclusive")
        final_score = AITSDecisionOutcomeTracker.number(final.get("outcome_score"))
        if final_score is None:
            final_score = AITSDecisionOutcomeTracker.number(latest.get("outcome_score")) or 0.0
        comparison = dict(latest.get("provider_comparison") or {})
        if not comparison and provider_rows:
            comparison = dict(max(provider_rows, key=lambda item: float(item.get("evaluated_at") or 0.0)))
        local = dict(latest.get("local_decision") or {})
        external = dict(latest.get("external_decision") or {})
        final_decision = dict(latest.get("final_decision") or {})
        action = str(state.get("final_action") or final_decision.get("action") or "").lower()
        scope_type = str(state.get("scope_type") or ("portfolio" if str(state.get("scope") or "") == "PORTFOLIO" else "position"))
        blockers = self._list(state.get("risk_blockers")) + self._list(state.get("safety_blockers"))
        blockers += [str(item.get("blocker")) for item in checkpoints if str(item.get("blocker") or "")]
        gate_source = {
            **state,
            "final_action": action,
            "final_provider_source": state.get("final_provider_source") or final_decision.get("provider"),
            "payload_hash": state.get("payload_hash") or latest.get("payload_hash"),
            "payload_quality_grade": state.get("payload_quality_grade"),
            "actual_order": state.get("actual_order", False),
            "submitted": state.get("submitted", 0),
            "execution_result": state.get("execution_result") or latest.get("execution_result") or {},
            "risk_blockers": self._list(state.get("risk_blockers")),
            "safety_blockers": self._list(state.get("safety_blockers")),
        }
        gate = self._classify_training_gate(gate_source, checkpoints)
        action_tags = self._classify_action_tags(action, final_label, scope_type, blockers)
        provider_value = self._classify_provider_value(comparison, final_score)
        opportunity = self._classify_opportunity(latest)
        decision_id = str(state.get("decision_id") or latest.get("decision_id") or "")
        source_ids = sorted(self._stable_hash(source, 20) for source in sources)
        learning_tags = sorted(set(action_tags + provider_value["provider_learning_tags"] + opportunity["opportunity_learning_tags"]))
        learning_label = "excluded" if not gate["safe_for_local_training"] else ("positive" if final_score > 0 else ("negative" if final_score < 0 else "neutral"))
        return {
            "schema": self.SCHEMA,
            "record_id": f"curated-{self._stable_hash(decision_id or source_ids)}",
            "source_decision_id": decision_id,
            "source_outcome_record_id": ",".join(source_ids),
            "created_at": state.get("created_at") or latest.get("created_at"),
            "curated_at": time.time(),
            "session_id": str(state.get("session_id") or ""),
            "task": str(state.get("task") or latest.get("task") or ""),
            "scope_type": scope_type,
            "scope": str(state.get("scope") or latest.get("scope") or ""),
            "symbol": str(state.get("symbol") or latest.get("symbol") or ""),
            "market": str(state.get("symbol") or latest.get("symbol") or ""),
            "timeframe_context": sorted(checkpoint_map),
            "payload_hash": str(state.get("payload_hash") or latest.get("payload_hash") or ""),
            "feature_manifest_hash": state.get("feature_manifest_hash") or latest.get("feature_manifest_hash"),
            "payload_quality_grade": str(state.get("payload_quality_grade") or ""),
            "data_quality_grade": gate["training_quality_grade"],
            "feature_context": dict(state.get("feature_context") or {}),
            "action": action,
            "final_action": action,
            "local_action": str(state.get("local_action") or local.get("action") or ""),
            "external_action": str(state.get("external_action") or external.get("action") or ""),
            "final_provider_source": str(state.get("final_provider_source") or final_decision.get("provider") or ""),
            "local_confidence": state.get("local_confidence", local.get("confidence")),
            "external_confidence": state.get("external_confidence", external.get("confidence")),
            "final_confidence": state.get("final_confidence", final_decision.get("confidence")),
            "local_model_id": str(state.get("local_model_id") or latest.get("local_model_id") or ""),
            "local_model_prediction": str(state.get("local_model_prediction") or state.get("local_model_action") or latest.get("local_model_prediction") or ""),
            "local_model_confidence": state.get("local_model_confidence", latest.get("local_model_confidence")),
            "model_action_quality_score": state.get("model_action_quality_score", latest.get("model_action_quality_score")),
            "model_provider_value_score": state.get("model_provider_value_score", latest.get("model_provider_value_score")),
            "local_model_risk_score": state.get("local_model_risk_score", latest.get("local_model_risk_score")),
            "local_model_used_for_final": bool(state.get("local_model_used_for_final", latest.get("local_model_used_for_final"))),
            "local_model_not_used_reason": str(state.get("local_model_not_used_reason") or latest.get("local_model_not_used_reason") or ""),
            "local_model_live_allowed": bool(state.get("local_model_live_allowed", latest.get("local_model_live_allowed"))),
            "local_model_live_blocker": str(state.get("local_model_live_blocker") or latest.get("local_model_live_blocker") or ""),
            "reason_ko": str(state.get("reason_ko") or ""),
            "provider_route": {
                "final_provider_source": str(state.get("final_provider_source") or final_decision.get("provider") or ""),
                "external_called": bool(state.get("external_called")),
                "external_blocked": bool(state.get("external_blocked")),
            },
            "escalation_reason": str(state.get("escalation_reason") or comparison.get("escalation_reason") or ""),
            "cost_guard_blocker": str(state.get("cost_guard_blocker") or comparison.get("cost_guard_blocker") or ""),
            "risk_blockers": self._list(state.get("risk_blockers")),
            "safety_blockers": self._list(state.get("safety_blockers")) + [item for item in blockers if item not in self._list(state.get("risk_blockers"))],
            "order_submitted": bool(int(state.get("submitted") or 0) > 0),
            "actual_order": bool(state.get("actual_order")),
            "order_side": str((state.get("execution_result") or {}).get("side") or ""),
            "order_result": dict(state.get("execution_result") or latest.get("execution_result") or {}),
            "outcome_checkpoints": checkpoint_map,
            "final_outcome_label": final_label,
            "final_outcome_score": final_score,
            "learning_label": learning_label,
            "learning_tags": learning_tags,
            **gate,
            **provider_value,
            **opportunity,
            "recommended_local_behavior": "learn_from_observed_outcome" if gate["safe_for_local_training"] else "exclude_until_evidence_complete",
            "recommended_future_provider_route": provider_value["recommended_future_provider_route"],
            "notes": "Curated from allow-listed decision and outcome fields; no raw request content retained.",
        }

    def _build_summary(self, records: list[dict], *, source_count: int, corrupted: int, duplicates: int) -> dict:
        safe = [row for row in records if row.get("safe_for_local_training")]
        excluded = [row for row in records if not row.get("safe_for_local_training")]
        def counts(key: str, *, list_value: bool = False) -> dict:
            counter: Counter = Counter()
            for row in records:
                values = row.get(key) if list_value else [row.get(key)]
                for value in values or []:
                    if str(value or ""):
                        counter[str(value)] += 1
            return dict(sorted(counter.items()))
        scores = [float(row.get("final_outcome_score") or 0.0) for row in records]
        grade_values = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
        payload_values = [grade_values.get(str(row.get("payload_quality_grade") or "").upper()) for row in records]
        payload_values = [value for value in payload_values if value is not None]
        comparison_rows = [row for row in records if row.get("local_action") and row.get("external_action")]
        useful_rows = [row for row in records if row.get("provider_route", {}).get("external_called")]
        return {
            "schema": "aits_local_training_curated_summary.v1",
            "dataset_version": self.DATASET_VERSION,
            "total_source_outcome_records": source_count,
            "total_curated_records": len(safe),
            "total_excluded_records": len(excluded),
            "safe_for_training_count": len(safe),
            "excluded_count": len(excluded),
            "by_task": counts("task"),
            "by_action": counts("final_action"),
            "by_provider_source": counts("final_provider_source"),
            "by_outcome_label": counts("final_outcome_label"),
            "by_learning_tag": counts("learning_tags", list_value=True),
            "by_exclusion_reason": counts("exclusion_reasons", list_value=True),
            "avg_payload_quality": round(sum(payload_values) / len(payload_values), 4) if payload_values else None,
            "avg_outcome_score": round(sum(scores) / len(scores), 6) if scores else None,
            "local_external_agreement_rate": round(sum(row.get("local_action") == row.get("external_action") for row in comparison_rows) / len(comparison_rows), 6) if comparison_rows else None,
            "external_call_usefulness_rate": round(sum(bool(row.get("external_call_was_useful")) for row in useful_rows) / len(useful_rows), 6) if useful_rows else None,
            "cost_guard_block_count": sum(bool(row.get("cost_guard_blocker")) for row in records),
            "opportunity_cost_records_count": sum(bool(row.get("opportunity_cost_evaluated")) for row in records),
            "buy_sell_records_count": sum(row.get("final_action") in self.ORDER_ACTIONS - {"rotate"} for row in records),
            "wait_hold_records_count": sum(row.get("final_action") in {"wait", "hold"} for row in records),
            "duplicate_records_detected": duplicates,
            "corrupted_source_records_detected": corrupted,
            "last_curated_at": time.time(),
        }

    def curate(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        logging.getLogger("aits").info("[AITS][LocalTrainingCuration] event=curation_started source=outcome_records actual_order=False submitted=0")
        outcome_rows, outcome_corrupt, outcome_duplicates = self._read_jsonl(self.outcome_path)
        provider_rows, provider_corrupt, provider_duplicates = self._read_jsonl(self.provider_path)
        state_decisions = self._load_state_decisions()
        outcomes_by_decision: dict[str, list[dict]] = {}
        providers_by_decision: dict[str, list[dict]] = {}
        for row in outcome_rows:
            decision_id = str(row.get("decision_id") or "")
            outcomes_by_decision.setdefault(decision_id, []).append(row)
        for row in provider_rows:
            providers_by_decision.setdefault(str(row.get("decision_id") or ""), []).append(row)
        decision_ids = sorted(set(state_decisions) | {key for key in outcomes_by_decision if key})
        records = [
            self._build_curated_record(state_decisions.get(decision_id, {"decision_id": decision_id}), outcomes_by_decision.get(decision_id, []), providers_by_decision.get(decision_id, []))
            for decision_id in decision_ids
        ]
        records.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("record_id") or "")))
        curated = [row for row in records if row.get("safe_for_local_training")]
        excluded = [row for row in records if not row.get("safe_for_local_training")]
        summary = self._build_summary(
            records,
            source_count=len(outcome_rows),
            corrupted=outcome_corrupt + provider_corrupt,
            duplicates=outcome_duplicates + provider_duplicates,
        )
        self._write_jsonl_atomic(self.curated_path, curated)
        self._write_jsonl_atomic(self.excluded_path, excluded)
        self._write_json_atomic(self.summary_path, summary)
        for row in records:
            event = "record_curated" if row.get("safe_for_local_training") else "record_excluded"
            gate_event = "training_gate_passed" if row.get("safe_for_local_training") else "training_gate_failed"
            logging.getLogger("aits").info(
                "[AITS][LocalTrainingCuration] event=%s decision_id=%s task=%s scope=%s symbol=%s safe_for_local_training=%s training_quality_grade=%s exclusion_reasons=%s learning_tags=%s final_outcome_label=%s final_outcome_score=%s actual_order=False submitted=0",
                event, row.get("source_decision_id") or "-", row.get("task") or "-", row.get("scope") or "-", row.get("symbol") or "-",
                bool(row.get("safe_for_local_training")), row.get("training_quality_grade") or "-",
                ",".join(row.get("exclusion_reasons") or []) or "-", ",".join(row.get("learning_tags") or []) or "-",
                row.get("final_outcome_label") or "-", row.get("final_outcome_score"),
            )
            logging.getLogger("aits").info(
                "[AITS][LocalTrainingCuration] event=%s decision_id=%s safe_for_local_training=%s exclusion_reasons=%s actual_order=False submitted=0",
                gate_event, row.get("source_decision_id") or "-", bool(row.get("safe_for_local_training")),
                ",".join(row.get("exclusion_reasons") or []) or "-",
            )
        logging.getLogger("aits").info(
            "[AITS][LocalTrainingCuration] event=curation_summary_written total_source_outcome_records=%s total_curated_records=%s total_excluded_records=%s duplicate_records_detected=%s corrupted_source_records_detected=%s dataset_version=%s actual_order=False submitted=0",
            summary["total_source_outcome_records"], summary["total_curated_records"], summary["total_excluded_records"],
            summary["duplicate_records_detected"], summary["corrupted_source_records_detected"], summary["dataset_version"],
        )
        return summary


class AITSLocalTrainingFeaturePipeline:
    """Convert curated outcome evidence into model-neutral feature records."""

    SCHEMA = "aits_local_training_feature_record.v1"
    DATASET_VERSION = "v1"
    MIN_SPLIT_RECORDS = 20
    VALID_ACTIONS = AITSDecisionOutcomeTracker.ACTIONS
    FEATURE_KEYS = {
        "market_features": (
            "price_change_1m", "price_change_5m", "price_change_15m", "price_change_1h",
            "volume_change", "trade_value", "volatility", "market_data_stale",
        ),
        "indicator_features": ("rsi", "macd", "ma5", "ma20", "ma60", "momentum", "trend_strength"),
        "position_features": (
            "qty", "avg_buy_price", "current_price", "position_value_krw", "pnl_pct", "weight_pct",
            "target_weight_pct", "holding_age", "dust", "manageable",
        ),
        "portfolio_features": (
            "total_asset_krw", "available_krw", "total_budget_krw", "exposure_for_cap",
            "cap_remaining_krw", "position_count", "managed_pool_count", "cash_ratio", "exposure_ratio",
        ),
        "risk_features": (
            "sell_unit_guard_passed", "valuation_unit_mismatch", "risk_blocker_count",
            "safety_blocker_count", "livepreflight_blocker_count", "dust_excluded", "cap_near_limit",
        ),
        "provider_features": (
            "local_confidence", "external_confidence", "confidence_gap", "local_external_agreed",
            "external_called", "external_blocked", "final_provider_source", "escalation_required",
            "cost_guard_blocked",
        ),
        "opportunity_features": (
            "candidate_move_pct", "held_symbol_move_pct", "opportunity_gap_change",
            "missed_move_detected", "avoided_drawdown_detected",
        ),
        "time_features": ("hour_of_day", "day_of_week", "time_since_last_decision", "eta_seconds", "checkpoint_horizon"),
        "data_quality_features": (
            "payload_quality_numeric", "data_quality_numeric", "missing_feature_count",
            "stale_feature_count", "unavailable_feature_count",
        ),
    }

    def __init__(self, root: Path | str = Path("data") / "ai_decision_training") -> None:
        self.root = Path(root)
        self.source_path = self.root / "curated_local_training_records.jsonl"
        self.features_path = self.root / "local_training_features.jsonl"
        self.excluded_path = self.root / "local_training_features_excluded.jsonl"
        self.summary_path = self.root / "local_training_feature_summary.json"

    @staticmethod
    def _stable_hash(value: Any, length: int = 24) -> str:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:length]

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        return AITSDecisionOutcomeTracker.number(value)

    @staticmethod
    def _first(mapping: dict, *keys: str) -> Any:
        for key in keys:
            if key in mapping and mapping.get(key) is not None:
                return mapping.get(key)
        return None

    @classmethod
    def _numeric_first(cls, mapping: dict, *keys: str) -> Optional[float]:
        return cls._number(cls._first(mapping, *keys))

    @staticmethod
    def _bool_or_none(value: Any) -> Optional[bool]:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _grade_numeric(value: Any) -> Optional[float]:
        return {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.3, "F": 0.0}.get(str(value or "").upper())

    @staticmethod
    def _timestamp(value: Any) -> Optional[float]:
        number = AITSDecisionOutcomeTracker.number(value)
        if number is not None:
            return number
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    def _read_jsonl(self) -> tuple[list[dict], int, int]:
        rows: list[dict] = []
        corrupted = 0
        duplicates = 0
        seen: set[str] = set()
        if not self.source_path.exists():
            return rows, corrupted, duplicates
        with self.source_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    corrupted += 1
                    continue
                if not isinstance(row, dict):
                    corrupted += 1
                    continue
                source_id = str(row.get("record_id") or row.get("source_decision_id") or self._stable_hash(row))
                if source_id in seen:
                    duplicates += 1
                    continue
                seen.add(source_id)
                rows.append(row)
        return rows, corrupted, duplicates

    @staticmethod
    def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        temporary.replace(path)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    def _feature_vector(self, row: dict, *, previous_timestamp: Optional[float]) -> dict:
        context = dict(row.get("feature_context") or {})
        market = dict(context.get("market") or {})
        indicators = dict(context.get("indicators") or {})
        position = dict(context.get("position") or {})
        portfolio = dict(context.get("portfolio") or {})
        risk = dict(context.get("risk") or {})
        provider = dict(context.get("provider") or {})
        opportunity = dict(context.get("opportunity") or {})
        quality = dict(context.get("data_quality") or {})
        created_at = self._timestamp(row.get("created_at"))
        created_dt = datetime.fromtimestamp(created_at) if created_at is not None else None
        local_confidence = self._number(row.get("local_confidence"))
        external_confidence = self._number(row.get("external_confidence"))
        total_asset = self._numeric_first(portfolio, "total_asset_krw")
        available = self._numeric_first(portfolio, "available_krw")
        exposure = self._numeric_first(portfolio, "exposure_for_cap")
        cash_ratio = self._numeric_first(portfolio, "cash_ratio")
        exposure_ratio = self._numeric_first(portfolio, "exposure_ratio")
        if cash_ratio is None and total_asset and available is not None:
            cash_ratio = available / total_asset
        if exposure_ratio is None and total_asset and exposure is not None:
            exposure_ratio = exposure / total_asset
        macd_value = indicators.get("macd")
        if isinstance(macd_value, dict):
            macd_value = self._first(macd_value, "macd", "value", "line")
        checkpoints = dict(row.get("outcome_checkpoints") or {})
        evaluated = [name for name, value in checkpoints.items() if isinstance(value, dict) and value.get("status") == "evaluated"]
        return {
            "market_features": {
                "price_change_1m": self._numeric_first(market, "price_change_1m", "change_1m_pct"),
                "price_change_5m": self._numeric_first(market, "price_change_5m", "change_5m_pct"),
                "price_change_15m": self._numeric_first(market, "price_change_15m", "change_15m_pct"),
                "price_change_1h": self._numeric_first(market, "price_change_1h", "change_1h_pct"),
                "volume_change": self._numeric_first(market, "volume_change", "volume_change_pct"),
                "trade_value": self._numeric_first(market, "trade_value", "trade_value_krw", "acc_trade_price_24h"),
                "volatility": self._numeric_first(market, "volatility", "volatility_pct"),
                "market_data_stale": self._bool_or_none(market.get("market_data_stale")),
            },
            "indicator_features": {
                "rsi": self._numeric_first(indicators, "rsi", "RSI"),
                "macd": self._number(macd_value),
                "ma5": self._numeric_first(indicators, "ma5", "MA5"),
                "ma20": self._numeric_first(indicators, "ma20", "MA20"),
                "ma60": self._numeric_first(indicators, "ma60", "MA60"),
                "momentum": self._numeric_first(indicators, "momentum", "momentum_pct"),
                "trend_strength": self._numeric_first(indicators, "trend_strength"),
            },
            "position_features": {
                "qty": self._numeric_first(position, "qty", "quantity"),
                "avg_buy_price": self._numeric_first(position, "avg_buy_price", "average_buy_price"),
                "current_price": self._numeric_first(position, "current_price", "price", "trade_price"),
                "position_value_krw": self._numeric_first(position, "position_value_krw", "selected_valuation_krw", "valuation_krw", "eval_krw"),
                "pnl_pct": self._numeric_first(position, "pnl_pct", "profit_rate"),
                "weight_pct": self._numeric_first(position, "weight_pct", "position_weight_pct"),
                "target_weight_pct": self._numeric_first(position, "target_weight_pct"),
                "holding_age": self._numeric_first(position, "holding_age", "holding_age_seconds"),
                "dust": self._bool_or_none(self._first(position, "dust", "final_dust", "is_dust_holding")),
                "manageable": self._bool_or_none(self._first(position, "manageable", "final_manageable", "manageable_holding")),
            },
            "portfolio_features": {
                "total_asset_krw": total_asset,
                "available_krw": available,
                "total_budget_krw": self._numeric_first(portfolio, "total_budget_krw", "budget_krw"),
                "exposure_for_cap": exposure,
                "cap_remaining_krw": self._numeric_first(portfolio, "cap_remaining_krw"),
                "position_count": self._numeric_first(portfolio, "position_count", "holding_count"),
                "managed_pool_count": self._numeric_first(portfolio, "managed_pool_count"),
                "cash_ratio": cash_ratio,
                "exposure_ratio": exposure_ratio,
            },
            "risk_features": {
                "sell_unit_guard_passed": self._bool_or_none(risk.get("sell_unit_guard_passed")),
                "valuation_unit_mismatch": self._bool_or_none(risk.get("valuation_unit_mismatch")),
                "risk_blocker_count": len(row.get("risk_blockers") or []),
                "safety_blocker_count": len(row.get("safety_blockers") or []),
                "livepreflight_blocker_count": self._numeric_first(risk, "livepreflight_blocker_count"),
                "dust_excluded": self._bool_or_none(risk.get("dust_excluded")),
                "cap_near_limit": self._bool_or_none(risk.get("cap_near_limit")),
            },
            "provider_features": {
                "local_confidence": local_confidence,
                "external_confidence": external_confidence,
                "confidence_gap": (external_confidence - local_confidence) if local_confidence is not None and external_confidence is not None else None,
                "local_external_agreed": self._bool_or_none(provider.get("local_external_agreed")),
                "external_called": bool((row.get("provider_route") or {}).get("external_called")),
                "external_blocked": bool((row.get("provider_route") or {}).get("external_blocked")),
                "final_provider_source": str(row.get("final_provider_source") or "") or None,
                "escalation_required": self._bool_or_none(provider.get("escalation_required")),
                "cost_guard_blocked": bool(row.get("cost_guard_blocker")),
            },
            "opportunity_features": {
                "candidate_move_pct": self._number(row.get("candidate_move_pct")),
                "held_symbol_move_pct": self._number(row.get("held_symbol_move_pct")),
                "opportunity_gap_change": self._numeric_first(opportunity, "opportunity_gap_change", "opportunity_score_gap"),
                "missed_move_detected": self._bool_or_none(row.get("missed_move_detected")),
                "avoided_drawdown_detected": self._bool_or_none(row.get("avoided_drawdown_detected")),
            },
            "time_features": {
                "hour_of_day": created_dt.hour if created_dt else None,
                "day_of_week": created_dt.weekday() if created_dt else None,
                "time_since_last_decision": (created_at - previous_timestamp) if created_at is not None and previous_timestamp is not None else None,
                "eta_seconds": self._number(context.get("eta_seconds")),
                "checkpoint_horizon": evaluated[-1] if evaluated else None,
            },
            "data_quality_features": {
                "payload_quality_numeric": self._grade_numeric(row.get("payload_quality_grade")),
                "data_quality_numeric": self._grade_numeric(row.get("data_quality_grade")),
                "missing_feature_count": self._numeric_first(quality, "missing_feature_count"),
                "stale_feature_count": self._numeric_first(quality, "stale_feature_count"),
                "unavailable_feature_count": self._numeric_first(quality, "unavailable_feature_count"),
            },
        }

    @classmethod
    def _coverage(cls, vector: dict) -> tuple[int, int, dict[str, bool]]:
        available = 0
        total = 0
        groups: dict[str, bool] = {}
        for group, keys in cls.FEATURE_KEYS.items():
            values = dict(vector.get(group) or {})
            group_available = False
            for key in keys:
                total += 1
                if values.get(key) is not None:
                    available += 1
                    group_available = True
            groups[group] = group_available
        return available, total, groups

    @staticmethod
    def _quality_grade(available: int, total: int) -> str:
        ratio = available / total if total else 0.0
        return "A" if ratio >= 0.8 else "B" if ratio >= 0.6 else "C" if ratio >= 0.4 else "D" if ratio >= 0.2 else "F"

    def _build_record(self, row: dict, *, previous_timestamp: Optional[float]) -> dict:
        vector = self._feature_vector(row, previous_timestamp=previous_timestamp)
        available, total, groups = self._coverage(vector)
        action = str(row.get("final_action") or row.get("action") or "").lower()
        outcome_label = str(row.get("final_outcome_label") or "")
        outcome_score = self._number(row.get("final_outcome_score"))
        provider_value_score = self._number(row.get("provider_value_score"))
        opportunity_score = self._number(row.get("opportunity_cost_score"))
        risk_count = len(row.get("risk_blockers") or [])
        safety_count = len(row.get("safety_blockers") or [])
        source_safe = bool(row.get("safe_for_local_training"))
        scope_type = str(row.get("scope_type") or "")
        grade = self._quality_grade(available, total)
        exclusions: list[str] = []
        if not source_safe:
            exclusions.append("curated_source_unsafe")
        if action not in self.VALID_ACTIONS:
            exclusions.append("invalid_action_label")
        if not outcome_label:
            exclusions.append("missing_label")
        if outcome_score is None:
            exclusions.append("missing_outcome_target")
        if grade == "F":
            exclusions.append("feature_quality_too_low")
        if scope_type == "position" and not groups["market_features"]:
            exclusions.append("critical_market_feature_missing")
        if scope_type == "position" and not groups["position_features"]:
            exclusions.append("critical_position_feature_missing")
        if scope_type == "portfolio" and not groups["portfolio_features"]:
            exclusions.append("critical_portfolio_feature_missing")
        if not str(row.get("provider_value_label") or ""):
            exclusions.append("provider_value_missing")
        exclusions = sorted(set(exclusions))
        score = max(-1.0, min(1.0, outcome_score or 0.0))
        risk_adjusted = max(-1.0, min(1.0, score - min(0.5, (risk_count + safety_count) * 0.1)))
        safety_text = " ".join(str(value).lower() for value in (row.get("safety_blockers") or []))
        risk_text = " ".join(str(value).lower() for value in (row.get("risk_blockers") or []))
        provider_features = dict(vector.get("provider_features") or {})
        risk_features = dict(vector.get("risk_features") or {})
        labels = {
            "action_label": action or None,
            "outcome_label": outcome_label or None,
            "recommended_action_label": action or None,
            "learning_label": row.get("learning_label"),
        }
        risk_labels = {
            "unit_guard_block_correct": "valuation_unit_mismatch" in safety_text and not bool(row.get("actual_order")),
            "valuation_mismatch_risk": bool(risk_features.get("valuation_unit_mismatch")) or "valuation_unit_mismatch" in safety_text,
            "cap_limit_risk": "cap" in risk_text or "cap" in safety_text,
            "dust_position_ignore": bool((vector.get("position_features") or {}).get("dust")),
            "safety_blocker_valid": safety_count > 0,
            "order_reconciliation_clean": bool(not row.get("order_submitted") or row.get("order_result")),
            "guard_bypass_detected_false": None,
            "livepreflight_required": action in {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"},
            "riskguard_required": action in {"buy", "add", "sell", "reduce", "rotate", "take_profit", "stop_loss"},
        }
        provider_labels = {
            "provider_value_label": row.get("provider_value_label"),
            "provider_value_score": provider_value_score,
            "local_action": row.get("local_action"),
            "external_action": row.get("external_action"),
            "final_action": action or None,
            "local_external_action_match": provider_features.get("local_external_agreed"),
            "confidence_gap": provider_features.get("confidence_gap"),
            "external_call_was_useful": bool(row.get("external_call_was_useful")),
            "external_call_waste_suspected": bool(row.get("external_call_waste_suspected")),
            "cost_guard_correct": bool(row.get("cost_guard_blocker") and score >= 0),
            "escalation_required_correct": bool(provider_features.get("escalation_required") and score >= 0),
            "recommended_future_provider_route": row.get("recommended_future_provider_route"),
        }
        safe = not exclusions
        outcome_targets = {
            "action_quality_score": score,
            "outcome_score": score,
            "risk_adjusted_score": risk_adjusted,
            "provider_value_score": provider_value_score,
            "opportunity_score": opportunity_score,
            "should_escalate_to_external": bool(provider_features.get("escalation_required")),
            "should_wait": action in {"wait", "hold"},
            "should_block_order": bool(safety_count or risk_count),
            "safe_to_train": safe,
        }
        source_id = str(row.get("record_id") or "")
        return {
            "schema": self.SCHEMA,
            "feature_record_id": f"feature-{self._stable_hash(source_id or row.get('source_decision_id'))}",
            "source_curated_record_id": source_id,
            "source_decision_id": str(row.get("source_decision_id") or ""),
            "created_at": row.get("created_at"),
            "feature_built_at": time.time(),
            "session_id": str(row.get("session_id") or ""),
            "task": str(row.get("task") or ""),
            "scope_type": scope_type,
            "scope": str(row.get("scope") or ""),
            "symbol": str(row.get("symbol") or ""),
            "action": action,
            "final_action": action,
            "provider_source": str(row.get("final_provider_source") or ""),
            "payload_quality_grade": str(row.get("payload_quality_grade") or ""),
            "data_quality_grade": str(row.get("data_quality_grade") or ""),
            "feature_quality_grade": grade,
            "feature_available_count": available,
            "feature_total_count": total,
            "feature_group_availability": groups,
            "feature_vector": vector,
            "labels": labels,
            "risk_labels": risk_labels,
            "provider_value_labels": provider_labels,
            "opportunity_labels": {
                "opportunity_cost_label": row.get("opportunity_cost_label"),
                "opportunity_cost_score": opportunity_score,
                "missed_move_detected": row.get("missed_move_detected"),
                "avoided_drawdown_detected": row.get("avoided_drawdown_detected"),
            },
            "outcome_targets": outcome_targets,
            "split": "unsplit_insufficient_data",
            "safe_for_model_training": safe,
            "exclusion_reasons": exclusions,
            "notes": "Retrospective feature record only; it is not connected to live inference or order generation.",
        }

    def _assign_splits(self, records: list[dict]) -> str:
        safe = [row for row in records if row.get("safe_for_model_training")]
        safe.sort(key=lambda row: (self._timestamp(row.get("created_at")) or 0.0, str(row.get("source_decision_id") or "")))
        if len(safe) < self.MIN_SPLIT_RECORDS:
            for row in safe:
                row["split"] = "unsplit_insufficient_data"
            return "unsplit_insufficient_data"
        train_end = max(1, int(len(safe) * 0.70))
        validation_end = max(train_end + 1, int(len(safe) * 0.85))
        for index, row in enumerate(safe):
            row["split"] = "train" if index < train_end else ("validation" if index < validation_end else "holdout")
        return "time_based_70_15_15"

    def build(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        logging.getLogger("aits").info("[AITS][LocalTrainingFeaturePipeline] event=feature_pipeline_started source=curated_local_training_records actual_order=False submitted=0")
        source_rows, corrupted, duplicates = self._read_jsonl()
        source_rows.sort(key=lambda row: (self._timestamp(row.get("created_at")) or 0.0, str(row.get("record_id") or "")))
        records: list[dict] = []
        previous_by_session: dict[str, float] = {}
        for row in source_rows:
            session_id = str(row.get("session_id") or "")
            previous = previous_by_session.get(session_id)
            record = self._build_record(row, previous_timestamp=previous)
            timestamp = self._timestamp(row.get("created_at"))
            if timestamp is not None:
                previous_by_session[session_id] = timestamp
            records.append(record)
        split_strategy = self._assign_splits(records)
        included = [row for row in records if row.get("safe_for_model_training")]
        excluded = [row for row in records if not row.get("safe_for_model_training")]
        reason_counts = Counter(reason for row in excluded for reason in row.get("exclusion_reasons") or [])
        grade_counts = Counter(str(row.get("feature_quality_grade") or "") for row in records)
        split_counts = Counter(str(row.get("split") or "") for row in records)
        group_counts = Counter(
            group for row in records for group, available in (row.get("feature_group_availability") or {}).items() if available
        )
        summary = {
            "schema": "aits_local_training_feature_summary.v1",
            "dataset_version": self.DATASET_VERSION,
            "source_record_count": len(source_rows),
            "safe_for_model_training_count": len(included),
            "feature_excluded_count": len(excluded),
            "feature_exclusion_reason_counts": dict(sorted(reason_counts.items())),
            "feature_quality_grade_counts": dict(sorted(grade_counts.items())),
            "feature_group_available_counts": dict(sorted(group_counts.items())),
            "duplicate_feature_records_detected": duplicates,
            "corrupted_feature_source_detected": corrupted,
            "split_strategy": split_strategy,
            "train_count": split_counts.get("train", 0),
            "validation_count": split_counts.get("validation", 0),
            "holdout_count": split_counts.get("holdout", 0),
            "unsplit_count": split_counts.get("unsplit_insufficient_data", 0),
            "last_feature_built_at": time.time(),
            "model_training_executed": False,
            "live_inference_connected": False,
        }
        self._write_jsonl_atomic(self.features_path, included)
        self._write_jsonl_atomic(self.excluded_path, excluded)
        self._write_json_atomic(self.summary_path, summary)
        for row in records:
            event = "feature_record_built" if row.get("safe_for_model_training") else "feature_record_excluded"
            gate_event = "feature_quality_gate_passed" if row.get("safe_for_model_training") else "feature_quality_gate_failed"
            logging.getLogger("aits").info(
                "[AITS][LocalTrainingFeaturePipeline] event=%s decision_id=%s task=%s scope=%s feature_quality_grade=%s safe_for_model_training=%s exclusion_reasons=%s split=%s actual_order=False submitted=0",
                event, row.get("source_decision_id") or "-", row.get("task") or "-", row.get("scope") or "-",
                row.get("feature_quality_grade") or "-", bool(row.get("safe_for_model_training")),
                ",".join(row.get("exclusion_reasons") or []) or "-", row.get("split") or "-",
            )
            logging.getLogger("aits").info(
                "[AITS][LocalTrainingFeaturePipeline] event=%s decision_id=%s safe_for_model_training=%s actual_order=False submitted=0",
                gate_event, row.get("source_decision_id") or "-", bool(row.get("safe_for_model_training")),
            )
        logging.getLogger("aits").info(
            "[AITS][LocalTrainingFeaturePipeline] event=feature_summary_written source_record_count=%s safe_for_model_training_count=%s feature_excluded_count=%s split_strategy=%s model_training_executed=false live_inference_connected=false actual_order=False submitted=0",
            len(source_rows), len(included), len(excluded), split_strategy,
        )
        return summary


def _fetch_upbit_price_once(symbol: str) -> tuple[float | None, str]:
    """
    Upbit ticker 1회 조회 (shadow 성과추적 전용)
    return: (price, source)
    """
    try:
        if requests is None:
            return None, "upbit_err_ImportError"
        url = "https://api.upbit.com/v1/ticker"
        params = {"markets": symbol}
        response = requests.get(url, params=params, timeout=1.5)
        if response.status_code != 200:
            return None, f"upbit_http_{response.status_code}"
        data = response.json()
        if not data or not isinstance(data, list):
            return None, "upbit_empty"
        item = data[0] or {}
        price = item.get("trade_price") or item.get("tradePrice")
        if isinstance(price, (int, float)) and price > 0:
            return float(price), "upbit.ticker.trade_price"
        return None, "upbit_no_price"
    except Exception as exc:
        return None, f"upbit_err_{type(exc).__name__}"

# ---------------------------------------------------------------------------
# Cycle result types (Phase 1)
# ---------------------------------------------------------------------------


@dataclass
class CycleMeta:
    cycle_id: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: float = 0.0
    run_mode: str = "ui"
    source: str = "aits_orchestrator"


@dataclass
class CycleStatus:
    ok: bool = True
    status: str = "success"
    phase: str = "completed"
    execution_attempted: bool = False
    execution_completed: bool = False
    degraded_mode: bool = False
    paused: bool = False


@dataclass
class ExecutionRequest:
    actions: List[Any] = field(default_factory=list)
    priority: int = 0
    source: str = "aits"
    decision_trace_id: str = ""
    dry_run: bool = False
    request_summary: str = ""


@dataclass
class CycleExecutionResult:
    submitted_orders: List[str] = field(default_factory=list)
    filled_orders: List[str] = field(default_factory=list)
    rejected_orders: List[str] = field(default_factory=list)
    pending_orders: List[str] = field(default_factory=list)
    execution_errors: List[str] = field(default_factory=list)
    execution_summary: str = ""


@dataclass
class CycleDiagnostics:
    provider_used: str = ""
    fallback_used: bool = False
    provider_latency_ms: float = 0.0
    market_data_latency_ms: float = 0.0
    decision_trace_id: str = ""
    blocked_reason_codes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleResult:
    meta: CycleMeta = field(default_factory=CycleMeta)
    status: CycleStatus = field(default_factory=CycleStatus)
    runtime_state: Optional[AITSRuntimeState] = None
    action_plan: Optional[Any] = None
    execution_request: Optional[ExecutionRequest] = None
    execution_result: CycleExecutionResult = field(default_factory=CycleExecutionResult)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    diagnostics: CycleDiagnostics = field(default_factory=CycleDiagnostics)

    def is_success(self) -> bool:
        return self.status.ok and self.status.status in ("success", "partial")

    def is_blocked(self) -> bool:
        return self.status.status in ("blocked", "paused")

    def has_errors(self) -> bool:
        return len(self.errors) > 0 or len(self.execution_result.execution_errors) > 0

    def summary_text(self) -> str:
        return (
            f"[cycle={self.meta.cycle_id}] status={self.status.status}, "
            f"duration_ms={self.meta.duration_ms:.1f}, warnings={len(self.warnings)}, "
            f"errors={len(self.errors)}"
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AITSOrchestrator:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        app_state: Optional[Any] = None,
        logger: Optional[Any] = None,
        regime_detector: Optional[Any] = None,
        portfolio_brain: Optional[Any] = None,
        ai_decision_service: Optional[Any] = None,
        explainability_service: Optional[Any] = None,
        module_engine: Optional[Any] = None,
        scenario_engine: Optional[Any] = None,
        provider_router: Optional[Any] = None,
        ai_engine_provider: Optional[Any] = None,
        decision_router: Optional[Any] = None,
        execution_adapter: Optional[Any] = None,
        run_mode: str = "ui",
    ) -> None:
        self.config = config if config is not None else {}
        self.app_state = app_state
        self.settings = app_state
        try:
            if not hasattr(self, "strategy"):
                if isinstance(app_state, dict):
                    self.strategy = app_state.get("strategy")
                else:
                    self.strategy = getattr(app_state, "strategy", None)
            if getattr(self, "strategy", None) is None and isinstance(self.config, dict):
                self.strategy = self.config.get("strategy")
        except Exception:
            pass
        self.logger = logger
        self.regime_detector = regime_detector or RegimeDetector(config=self.config, logger=self.logger)
        self.portfolio_brain = portfolio_brain or PortfolioBrain(config=self.config, logger=self.logger)
        self.ai_decision_service = ai_decision_service or AIDecisionService(
            config=self.config, logger=self.logger
        )
        self.explainability_service = explainability_service or ExplainabilityService(
            config=self.config, logger=self.logger
        )
        self.module_engine = module_engine
        self.scenario_engine = scenario_engine
        self.provider_router = provider_router
        self.ai_engine_provider = ai_engine_provider
        self.decision_router = decision_router or (
            DecisionRouter(
                logger=self.logger,
                prefs=self.app_state,
                config=self.config,
                ai_engine_provider=self.ai_engine_provider,
            )
            if DecisionRouter is not None
            else None
        )
        try:
            if self.ai_engine_provider is None and self.decision_router is not None:
                attached_provider = getattr(self.decision_router, "ai_engine_provider", None)
                if attached_provider is not None:
                    self.ai_engine_provider = attached_provider
            if self.ai_engine_provider is None and self.decision_router is not None:
                registry = getattr(self.decision_router, "provider_registry", None)
                if isinstance(registry, dict):
                    self.ai_engine_provider = registry.get("local")
            if self.ai_engine_provider is not None and self.decision_router is not None:
                if getattr(self.decision_router, "ai_engine_provider", None) is None:
                    self.decision_router.ai_engine_provider = self.ai_engine_provider
        except Exception:
            pass
        self._safe_log_info(
            "[AITS][Orchestrator] router_ai_provider_injection | "
            f"attached={getattr(self, 'ai_engine_provider', None) is not None} | "
            f"type={type(getattr(self, 'ai_engine_provider', None)).__name__ if getattr(self, 'ai_engine_provider', None) is not None else 'None'}"
        )
        # AITS v3.6: verifier instances (no forced API)
        try:
            self._verifier_local = getattr(self, "ai_engine_provider", None)
            self._verifier_openai = None
            self._verifier_gemini = None
            _provider_kwargs = {
                "strategy": getattr(self, "strategy", None),
                "settings": getattr(self, "settings", None),
                "config": getattr(self, "config", None),
            }
            try:
                _st = getattr(self, "strategy", None)
                _openai_has_key = False
                _gemini_has_key = False
                if isinstance(_st, dict):
                    _openai_has_key = bool(str(_st.get("ai_openai_api_key") or "").strip())
                    _gemini_has_key = bool(str(_st.get("ai_gemini_api_key") or "").strip())
                elif _st is not None:
                    _openai_has_key = bool(str(getattr(_st, "ai_openai_api_key", "") or "").strip())
                    _gemini_has_key = bool(str(getattr(_st, "ai_gemini_api_key", "") or "").strip())

                self._safe_log_info(
                    "[AITS][Orchestrator] ai_provider_key_injection | "
                    f"strategy_attached={_st is not None} | "
                    f"openai_key_present={_openai_has_key} | "
                    f"gemini_key_present={_gemini_has_key}"
                )
            except Exception:
                pass

            if AIEngineProvider is not None and str(os.getenv("AITS_ENABLE_OPENAI_VERIFIER", "")).strip() == "1":
                try:
                    self._verifier_openai = AIEngineProvider(**_provider_kwargs)
                except Exception:
                    self._verifier_openai = None

            if AIEngineProvider is not None and str(os.getenv("AITS_ENABLE_GEMINI_VERIFIER", "")).strip() == "1":
                try:
                    self._verifier_gemini = AIEngineProvider(**_provider_kwargs)
                except Exception:
                    self._verifier_gemini = None

            self._safe_log_info(
                "[AITS][Orchestrator] verifier_pool_init | "
                f"local={self._verifier_local is not None} | "
                f"openai={self._verifier_openai is not None} | "
                f"gemini={self._verifier_gemini is not None}"
            )
        except Exception:
            pass
        self.execution_adapter = execution_adapter
        self.run_mode = run_mode
        from app.services.execution_bridge import ExecutionBridge

        self.execution_bridge = ExecutionBridge(config=self.config, logger=self.logger)

        self.initialized = False
        self.paused = False
        self.cycle_counter = 0
        self.last_cycle_result: Optional[CycleResult] = None
        self.last_runtime_state: AITSRuntimeState = AITSRuntimeState()
        self.last_action_plan: Optional[Any] = None
        self.last_explainability: Optional[ExplainabilityState] = None
        self.last_error: str = ""
        self.current_user_controls: Dict[str, Any] = {}
        self.last_bridge_result: Optional[Any] = None
        self.last_risk_guard_events: List[Dict[str, Any]] = []
        _oa_cls = AITSOrderAdapter
        if _oa_cls is None:
            from app.services.order_adapter import AITSOrderAdapter as _oa_cls
        self.order_adapter = _oa_cls(
            execution_mode="disabled",
            min_order_krw=5000.0,
            allow_reduce_live=False,
            logger=self.logger,
        )
        self.last_order_adapter_result: Optional[Any] = None
        self.execution_mode: str = "disabled"
        self.risk_guard = RiskGuard() if RiskGuard is not None else None

        self.module_pack_resolver = ModulePackResolver(
            pack_definitions=DEFAULT_MODULE_PACK_DEFINITIONS,
            base_pack_id="ai_default",
            logger=self.logger,
        )
        _mps = DEFAULT_USER_MODULE_PACK_SELECTION
        self.module_pack_selection = UserModulePackSelection(
            active_pack_id=_mps.active_pack_id,
            is_active=_mps.is_active,
            timer_enabled=_mps.timer_enabled,
            duration_minutes=_mps.duration_minutes,
            remaining_seconds=_mps.remaining_seconds,
            activated_at=_mps.activated_at,
            expires_at=_mps.expires_at,
            auto_revert_to_ai_default=_mps.auto_revert_to_ai_default,
            manual_deactivation_allowed=_mps.manual_deactivation_allowed,
            selection_reason=_mps.selection_reason,
            status_text_ko=_mps.status_text_ko,
        )
        self.last_module_pack_runtime: Optional[ModulePackRuntimeState] = None

    def initialize(self) -> bool:
        try:
            state = AITSRuntimeState()
            state.meta.run_mode = self.run_mode
            state.system.initialized = True
            state.system.running = False
            state.system.paused = self.paused
            state.system.active_provider = "local_rule_based"
            state.explainability.current_ai_view = (
                "AITS Phase 1: 초기화되었습니다. 장세·포트폴리오·판단을 연결할 준비가 되었습니다."
            )
            state.oversight.oversight_summary = (
                "시스템이 초기화되었습니다. 사용자는 언제든 판단을 검토하고 일시정지할 수 있습니다."
            )
            self.last_runtime_state = state
            self.last_bridge_result = None
            self.last_risk_guard_events = []
            self.last_order_adapter_result = None
            self.order_adapter.set_execution_mode(self.execution_mode)
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(
                    self.module_pack_selection
                )
            except Exception:
                self.last_module_pack_runtime = None
            self.initialized = True
            self._safe_log_info("AITS orchestrator initialized")
            self._safe_log_info(
                "Module pack runtime initialized: "
                + (
                    (self.last_module_pack_runtime.pack_name_ko or "AI 기본 모드")
                    if self.last_module_pack_runtime is not None
                    else "AI 기본 모드"
                )
            )
            return True
        except Exception:
            return False

    def run_cycle(
        self,
        market_snapshot_override: Optional[Any] = None,
        forced_mode: Optional[str] = None,
        user_override_flags: Optional[Dict[str, Any]] = None,
    ) -> CycleResult:
        started_at = datetime.now()
        try:
            order_service = None
            execution_mode = self.execution_mode
            if execution_mode == "live":
                try:
                    order_service = OrderService()
                except Exception:
                    order_service = None

            self.cycle_counter += 1
            result = CycleResult()
            result.status.phase = "collecting"
            result.meta.cycle_id = self.cycle_counter
            result.meta.started_at = started_at
            result.meta.run_mode = self.run_mode
            result.meta.source = "aits_orchestrator"

            if not self.initialized:
                self.initialize()

            rs = self.last_runtime_state
            rs.meta.cycle_id = self.cycle_counter
            rs.meta.timestamp = started_at
            rs.meta.run_mode = self.run_mode

            rs.system.running = True
            rs.system.paused = self.paused

            if user_override_flags:
                self.current_user_controls.update(user_override_flags)

            self._refresh_module_pack_runtime()

            if self.paused:
                result.status.ok = True
                result.status.status = "paused"
                result.status.phase = "completed"
                result.status.paused = True
                msg = (
                    "거래 사이클이 일시정지되어 있습니다. 재개하면 최신 시장·포트폴리오 "
                    "상태를 다시 평가합니다."
                )
                rs.explainability.current_ai_view = msg
                rs.oversight.oversight_summary = (
                    "현재 일시정지 상태입니다. 재개 전까지 자동 실행은 진행되지 않습니다."
                )
                rs.system.running = False
                result.runtime_state = rs
                result.action_plan = rs.execution.plan
                result.execution_request = ExecutionRequest(
                    actions=[],
                    priority=1,
                    source="aits",
                    decision_trace_id=f"cycle-{self.cycle_counter}",
                    dry_run=True,
                    request_summary=rs.execution.plan.reason_summary or "일시정지 중입니다.",
                )
                result.execution_result.execution_summary = rs.execution.result.execution_summary
                result.diagnostics.provider_used = rs.system.active_provider
                result.diagnostics.decision_trace_id = f"cycle-{self.cycle_counter}"
                self.last_action_plan = rs.execution.plan
                self.last_explainability = rs.explainability
                self.last_runtime_state = rs
                self._update_bridge_result(result)
                try:
                    print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(result.execution_request.actions) if result.execution_request and result.execution_request.actions else 0}")
                    self.last_order_adapter_result = self.order_adapter.execute(
                        self.last_bridge_result, order_service=order_service
                    )
                except Exception as exc:
                    try:
                        if self.logger is not None and hasattr(self.logger, "debug"):
                            self.logger.debug(f"order adapter execute skipped: {exc}")
                    except Exception:
                        pass
                self._update_order_adapter_result()
                finished = datetime.now()
                result.meta.finished_at = finished
                result.meta.duration_ms = (finished - started_at).total_seconds() * 1000.0
                self.last_cycle_result = result
                return result

            self._build_market_state(market_snapshot_override)
            self._build_portfolio_state()
            self._build_intelligence_state(forced_mode)
            self._apply_control_state()
            self._build_execution_state()
            self._build_explainability_state()

            action_plan = rs.execution.plan
            self.last_action_plan = action_plan
            self.last_explainability = rs.explainability
            self.last_runtime_state = rs

            result.runtime_state = rs
            result.action_plan = action_plan
            result.execution_request = ExecutionRequest(
                actions=rs.execution.plan.approved_actions,
                priority=1,
                source="aits",
                decision_trace_id=f"cycle-{self.cycle_counter}",
                dry_run=True,
                request_summary=rs.execution.plan.reason_summary,
            )
            result.execution_result.execution_summary = rs.execution.result.execution_summary
            result.diagnostics.provider_used = rs.system.active_provider
            result.diagnostics.decision_trace_id = f"cycle-{self.cycle_counter}"

            print(f"[AITS][Orchestrator] decision_state | action={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'action', '')} | logic={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'selected_strategy_logic', '')} | symbol={getattr(getattr(getattr(getattr(result, 'runtime_state', None), 'intelligence', None), 'ai_decision', None), 'selected_symbol', '')} | approved={len(action_plan.approved_actions) if action_plan and getattr(action_plan, 'approved_actions', None) else 0} | blocked={len(action_plan.blocked_actions) if action_plan and getattr(action_plan, 'blocked_actions', None) else 0} | actions={len(result.execution_request.actions) if result.execution_request and getattr(result.execution_request, 'actions', None) else 0}")
            self._update_bridge_result(result)
            try:
                print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(result.execution_request.actions) if result.execution_request and result.execution_request.actions else 0}")
                self.last_order_adapter_result = self.order_adapter.execute(
                    self.last_bridge_result, order_service=order_service
                )
            except Exception as exc:
                try:
                    if self.logger is not None and hasattr(self.logger, "debug"):
                        self.logger.debug(f"order adapter execute skipped: {exc}")
                except Exception:
                    pass
            self._update_order_adapter_result()

            self._log_module_pack_effect()

            result.status.phase = "completed"
            result.status.status = "success"
            result.status.ok = True

            finished = datetime.now()
            result.meta.finished_at = finished
            result.meta.duration_ms = (finished - started_at).total_seconds() * 1000.0

            rs.system.running = False
            self.last_cycle_result = result
            return result

        except Exception as exc:
            self.last_error = str(exc)
            err_result = CycleResult()
            err_result.meta.cycle_id = getattr(self, "cycle_counter", 0)
            err_result.meta.started_at = started_at
            err_result.meta.run_mode = self.run_mode
            err_result.status.ok = False
            err_result.status.status = "failed"
            err_result.status.phase = "failed"
            err_result.errors.append(str(exc))
            rs_fail = self.last_runtime_state
            rs_fail.system.last_error = str(exc)
            rs_fail.system.running = False
            err_result.runtime_state = rs_fail
            err_result.execution_request = ExecutionRequest()
            fin = datetime.now()
            err_result.meta.finished_at = fin
            err_result.meta.duration_ms = (fin - started_at).total_seconds() * 1000.0
            self._safe_log_error(f"run_cycle failed: {exc}")
            self.last_cycle_result = err_result
            self._update_bridge_result(err_result)
            try:
                print(f"[AITS][Orchestrator] execute_adapter | mode={self.execution_mode} | actions={len(err_result.execution_request.actions) if err_result.execution_request and err_result.execution_request.actions else 0}")
                self.last_order_adapter_result = self.order_adapter.execute(
                    self.last_bridge_result, order_service=order_service
                )
            except Exception as exc:
                try:
                    if self.logger is not None and hasattr(self.logger, "debug"):
                        self.logger.debug(f"order adapter execute skipped: {exc}")
                except Exception:
                    pass
            self._update_order_adapter_result()
            return err_result

    def get_runtime_state(self) -> AITSRuntimeState:
        return self.last_runtime_state

    def get_last_action_plan(self) -> Optional[Any]:
        return self.last_action_plan

    def get_last_explainability(self) -> Optional[ExplainabilityState]:
        return self.last_explainability

    def get_last_bridge_result(self) -> Optional[Any]:
        return self.last_bridge_result

    def get_last_order_adapter_result(self) -> Optional[Any]:
        return self.last_order_adapter_result

    def get_last_risk_guard_events(self) -> List[Dict[str, Any]]:
        try:
            return list(self.last_risk_guard_events or [])
        except Exception:
            return []

    def set_execution_mode(self, execution_mode: str) -> None:
        self.execution_mode = str(execution_mode or "").strip() or "disabled"
        try:
            self.order_adapter.set_execution_mode(self.execution_mode)
            self.execution_mode = self.order_adapter.execution_mode
        except Exception:
            self.execution_mode = "disabled"
            try:
                self.order_adapter.set_execution_mode("disabled")
            except Exception:
                pass

    def get_execution_mode(self) -> str:
        return self.execution_mode

    def get_module_pack_selection(self) -> UserModulePackSelection:
        return self.module_pack_selection

    def get_last_module_pack_runtime(self) -> Optional[ModulePackRuntimeState]:
        return self.last_module_pack_runtime

    def activate_module_pack(
        self,
        pack_id: str,
        duration_minutes: int = 0,
        reason: str = "",
    ) -> None:
        if not pack_id or not str(pack_id).strip():
            return
        sel = self.module_pack_selection
        now = datetime.now()
        pid = str(pack_id).strip()
        sel.active_pack_id = pid
        sel.is_active = True
        sel.auto_revert_to_ai_default = True
        sel.selection_reason = reason or ""
        if duration_minutes > 0:
            try:
                dm = int(duration_minutes)
            except (TypeError, ValueError):
                dm = 0
            if dm > 0:
                sel.timer_enabled = True
                sel.duration_minutes = dm
                sel.remaining_seconds = dm * 60
                sel.activated_at = now
                sel.expires_at = now + timedelta(minutes=dm)
                sel.status_text_ko = f"모듈팩 활성: {pid} (타이머)"
            else:
                sel.timer_enabled = False
                sel.duration_minutes = 0
                sel.remaining_seconds = 0
                sel.activated_at = now
                sel.expires_at = None
                sel.status_text_ko = f"모듈팩 활성: {pid} / 무기한"
        else:
            sel.timer_enabled = False
            sel.duration_minutes = 0
            sel.remaining_seconds = 0
            sel.activated_at = now
            sel.expires_at = None
            sel.status_text_ko = f"모듈팩 활성: {pid} / 무기한"
        try:
            self.last_module_pack_runtime = self.module_pack_resolver.resolve(
                self.module_pack_selection,
                current_time=datetime.now(),
            )
        except Exception:
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(None)
            except Exception:
                self.last_module_pack_runtime = None
        self._safe_log_info(f"Module pack activation updated: {pid}")

    def request_pause(self, reason: Optional[str] = None) -> None:
        self.paused = True
        rs = self.last_runtime_state
        rs.system.paused = True
        rs.control.pause_logic.pause_requested = True
        rs.control.pause_logic.pause_reason = reason or "user_requested_pause"
        rs.oversight.oversight_summary = (
            "사용자 요청으로 일시정지되었습니다. 재개하면 운영 규칙에 따라 다시 평가합니다."
        )
        self._safe_log_info(f"Pause requested: {rs.control.pause_logic.pause_reason}")

    def request_resume(self) -> None:
        self.paused = False
        rs = self.last_runtime_state
        rs.system.paused = False
        rs.control.pause_logic.pause_requested = False
        rs.control.pause_logic.pause_reason = ""
        self._safe_log_info("Resume requested; pause flags cleared.")

    def update_user_controls(self, **kwargs: Any) -> None:
        try:
            self.current_user_controls.update(kwargs)
            rs = self.last_runtime_state
            if "whitelist" in kwargs and isinstance(kwargs["whitelist"], list):
                rs.control.constraints.whitelist = list(kwargs["whitelist"])
            if "blacklist" in kwargs and isinstance(kwargs["blacklist"], list):
                rs.control.constraints.blacklist = list(kwargs["blacklist"])
            if "selected_modules" in kwargs and isinstance(kwargs["selected_modules"], list):
                mods = list(kwargs["selected_modules"])
                rs.intelligence.modules.selected_modules = mods
                rs.intelligence.modules.active_modules = list(mods)
                rs.intelligence.modules.dominant_module = mods[0] if mods else ""
            if "new_buy_enabled" in kwargs and isinstance(kwargs["new_buy_enabled"], bool):
                rs.control.constraints.new_buy_enabled = kwargs["new_buy_enabled"]
            if "reentry_enabled" in kwargs and isinstance(kwargs["reentry_enabled"], bool):
                rs.control.constraints.reentry_enabled = kwargs["reentry_enabled"]
            if "strategy_mode" in kwargs:
                rs.intelligence.ai_decision.selected_strategy_logic = str(kwargs["strategy_mode"])
            if "risk_mode" in kwargs:
                rs.control.risk.risk_summary = (
                    f"사용자 위험 모드: {kwargs['risk_mode']} (Phase 1 스켈레톤 반영)"
                )
        except Exception:
            pass

    def shutdown(self) -> None:
        self.last_runtime_state.system.running = False
        self._safe_log_info("AITSOrchestrator shutdown.")

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_symbol_list_for_snapshot(self, raw: Any) -> List[str]:
        if not isinstance(raw, (list, tuple)):
            return []
        out: List[str] = []
        seen: set[str] = set()
        for x in raw:
            if not isinstance(x, str):
                continue
            s = x.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= 5:
                break
        return out

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
        except Exception:
            pass

    def _safe_log_error(self, message: str) -> None:
        try:
            if self.logger is not None:
                if hasattr(self.logger, "exception"):
                    self.logger.exception(message)
                elif hasattr(self.logger, "error"):
                    self.logger.error(message)
        except Exception:
            pass

    def _read_ai_provider_for_router(self) -> str:
        try:
            provider = self._extract_direct_provider(getattr(self, "strategy", None))
            if provider:
                return self._normalize_ai_provider_for_router(provider)

            provider = self._extract_strategy_provider(getattr(self, "settings", None))
            if provider:
                return self._normalize_ai_provider_for_router(provider)

            provider = self._extract_strategy_provider(getattr(self, "app_state", None))
            if provider:
                return self._normalize_ai_provider_for_router(provider)

            provider = self._extract_strategy_provider(self.config)
            if provider:
                return self._normalize_ai_provider_for_router(provider)

            provider = self._extract_direct_provider(self.config)
            if provider:
                return self._normalize_ai_provider_for_router(provider)
        except Exception:
            pass
        return "local"

    def _extract_direct_provider(self, root: Any) -> str:
        try:
            if root is None:
                return ""
            if isinstance(root, dict):
                return str(root.get("ai_provider") or "")
            return str(getattr(root, "ai_provider", "") or "")
        except Exception:
            return ""
        return ""

    def _extract_strategy_provider(self, root: Any) -> str:
        try:
            if root is None:
                return ""
            if isinstance(root, dict):
                strategy = root.get("strategy")
            else:
                strategy = getattr(root, "strategy", None)
            provider = self._extract_direct_provider(strategy)
            if provider:
                return provider
            if strategy is not None:
                return ""
            if isinstance(root, dict):
                settings = root.get("settings")
            else:
                settings = getattr(root, "settings", None)
            if settings is not None:
                return self._extract_strategy_provider(settings)
        except Exception:
            return ""
        return ""

    def _normalize_ai_provider_for_router(self, provider: str) -> str:
        if normalize_provider is not None:
            try:
                return normalize_provider(provider)
            except Exception:
                pass
        p = str(provider or "").strip().lower()
        if p in ("gpt", "openai"):
            return "openai"
        if p in ("gemini", "google"):
            return "gemini"
        if p in ("local", "basic"):
            return "local"
        return "local"

    def _log_decision_router_provider_status(self, provider: str) -> None:
        try:
            if self.decision_router is None:
                return
            status = self.decision_router.get_status_summary(provider)
            self._safe_log_info(
                "[AITS][DecisionRouter] provider_status | "
                f"provider={status.get('selected_provider')} | "
                f"ready={status.get('provider_ready')} | "
                f"api_required={status.get('api_required')} | "
                f"reason={status.get('ready_reason')}"
            )
        except Exception:
            pass

    def _build_decision_router_context(
        self,
        regime: Optional[Any] = None,
        portfolio: Optional[Any] = None,
        opportunities: Optional[Any] = None,
        decision: Optional[Any] = None,
    ) -> Dict[str, Any]:
        try:
            positions = getattr(portfolio, "positions", None)
            summary = getattr(portfolio, "summary", None)
            candidates = getattr(opportunities, "candidate_symbols", None) or []
            rule_reason = str(getattr(decision, "ai_summary_for_user", "") or "").strip()
            if not rule_reason:
                rule_reason = str(getattr(decision, "reason", "") or "").strip()
            return {
                "rule_action": str(getattr(decision, "action", "") or ""),
                "original_action": str(getattr(decision, "action", "") or ""),
                "rule_confidence": self._safe_float(
                    getattr(decision, "confidence", 0.0),
                    0.0,
                ),
                "rule_reason": rule_reason,
                "market_regime": str(getattr(regime, "label", "") or ""),
                "positions_count": len(positions) if isinstance(positions, (list, tuple)) else 0,
                "candidate_count": len(candidates) if isinstance(candidates, (list, tuple)) else 0,
                "portfolio_value": self._read_portfolio_value(summary),
                "cycle": int(getattr(self, "cycle_counter", 0) or 0),
            }
        except Exception:
            return {}

    def _read_portfolio_value(self, summary: Optional[Any]) -> float:
        for key in (
            "total_asset_krw",
            "total_value_krw",
            "portfolio_value",
            "evaluation_amount_krw",
            "total_krw",
        ):
            value = self._safe_float(getattr(summary, key, 0.0), 0.0)
            if value > 0.0:
                return value
        return 0.0

    def _update_bridge_result(self, result: CycleResult) -> None:
        try:
            self.last_bridge_result = self.execution_bridge.build_from_cycle_result(result)
            br = self.last_bridge_result
            if br is not None and hasattr(br, "summary_text"):
                self._safe_log_info(br.summary_text())
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"bridge result update skipped: {exc}")
            except Exception:
                pass

    def _update_order_adapter_result(self) -> None:
        try:
            ar = self.last_order_adapter_result
            if ar is not None and hasattr(ar, "summary_text"):
                self._safe_log_info(f"[AITS][OrderAdapter] {ar.summary_text()}")
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"order adapter update skipped: {exc}")
            except Exception:
                pass

    def _refresh_module_pack_runtime(self) -> None:
        try:
            self.last_module_pack_runtime = self.module_pack_resolver.tick(
                self.module_pack_selection,
                current_time=datetime.now(),
            )
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "debug"):
                    self.logger.debug(f"module pack runtime refresh failed: {exc}")
            except Exception:
                pass
            try:
                self.last_module_pack_runtime = self.module_pack_resolver.resolve(None)
            except Exception:
                self.last_module_pack_runtime = None

    def _format_seconds_hhmmss(self, seconds: int) -> str:
        try:
            s = int(seconds)
        except (TypeError, ValueError):
            s = 0
        if s < 0:
            s = 0
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _log_module_pack_effect(self) -> None:
        try:
            rs = getattr(self, "last_runtime_state", None)
            if rs is None:
                return
            intel = getattr(rs, "intelligence", None)
            decision = getattr(intel, "ai_decision", None) if intel else None
            if decision is None:
                return
            logic = (getattr(decision, "selected_strategy_logic", None) or "")
            action = (getattr(decision, "action", None) or "")
            pr = getattr(self, "last_module_pack_runtime", None)
            if pr is None:
                return
            apid = getattr(pr, "active_pack_id", None)
            apid_str = "" if apid is None else str(apid).strip()
            if not apid_str:
                return
            pname = (getattr(pr, "pack_name_ko", None) or "").strip() or apid_str
            override_applied = "override_applied" in logic
            rem_suffix = ""
            if bool(getattr(pr, "timer_enabled", False)):
                try:
                    rem = int(getattr(pr, "remaining_seconds", 0))
                except (TypeError, ValueError):
                    rem = 0
                if rem > 0:
                    rem_suffix = f", remaining={self._format_seconds_hhmmss(rem)}"
            if override_applied:
                msg = (
                    f"[AITS][ModulePack] {pname} applied -> action={action}, override=yes{rem_suffix}"
                )
            else:
                msg = (
                    f"[AITS][ModulePack] {pname} active -> action={action}, override=no{rem_suffix}"
                )
            self._safe_log_info(msg)
        except Exception:
            pass

    def _build_market_state(self, market_snapshot_override: Optional[Any] = None) -> None:
        rs = self.last_runtime_state
        rs.system.active_provider = "local_rule_based"
        snap = rs.market.snapshot
        top_src: Any = None
        vol_src: Any = None
        base: Dict[str, Any] = {
            "btc_price": 0.0,
            "btc_change_pct": 0.0,
            "market_volatility": 0.0,
            "market_breadth": 0.5,
            "snapshot_summary": "기본 시장 스냅샷을 사용합니다.",
        }

        if market_snapshot_override is None:
            data = dict(base)
            data["btc_price"] = self._safe_float(snap.btc_price, 0.0)
            data["btc_change_pct"] = self._safe_float(snap.btc_change_pct, 0.0)
            data["market_volatility"] = self._safe_float(snap.market_volatility, 0.0)
            data["market_breadth"] = self._safe_float(snap.market_breadth, 0.5)
            if (snap.snapshot_summary or "").strip():
                data["snapshot_summary"] = snap.snapshot_summary
            try:
                from app.services.market_feed import (
                    calc_market_breadth,
                    get_tickers,
                    get_top_markets_by_volume,
                )

                blacklist_raw = getattr(getattr(rs.control, "constraints", None), "blacklist", None) or []
                blacklist = {str(x).strip() for x in blacklist_raw if isinstance(x, str) and x.strip()}

                top_rows = get_top_markets_by_volume(
                    limit=20,
                    quote="KRW",
                    exclude_black=blacklist,
                    min_price=10.0,
                )
                if top_rows:
                    volume_leaders = [m for (m, _) in top_rows[:5] if isinstance(m, str) and m.strip()]
                    sorted_by_change = sorted(
                        top_rows,
                        key=lambda x: float(((x[1] or {}).get("signed_change_rate") if isinstance(x[1], dict) else 0.0) or 0.0),
                        reverse=True,
                    )
                    top_gainers = [m for (m, _) in sorted_by_change[:5] if isinstance(m, str) and m.strip()]

                    ticks_map = {
                        m: t for (m, t) in top_rows if isinstance(m, str) and m.strip() and isinstance(t, dict)
                    }
                    breadth, _mean_chg = calc_market_breadth(ticks_map)

                    if volume_leaders:
                        data["volume_leaders"] = volume_leaders
                    if top_gainers:
                        data["top_gainers"] = top_gainers
                    data["market_breadth"] = self._safe_float(breadth, data.get("market_breadth", 0.5))

                    btc = ticks_map.get("KRW-BTC")
                    if btc is None:
                        btc_tick = get_tickers(["KRW-BTC"])
                        btc = btc_tick.get("KRW-BTC") if isinstance(btc_tick, dict) else None
                    if isinstance(btc, dict):
                        data["btc_price"] = self._safe_float(btc.get("trade_price"), data.get("btc_price", 0.0))
                        data["btc_change_pct"] = self._safe_float(
                            btc.get("signed_change_rate"), data.get("btc_change_pct", 0.0)
                        )

                    if not str(data.get("snapshot_summary") or "").strip():
                        data["snapshot_summary"] = "market_feed 기반 시장 스냅샷이 적용되었습니다."
            except Exception:
                pass
            regime = self.regime_detector.detect_from_dict(data)
            snap.btc_price = data["btc_price"]
            snap.btc_change_pct = data["btc_change_pct"]
            snap.market_volatility = data["market_volatility"]
            snap.market_breadth = data["market_breadth"]
            snap.snapshot_summary = data.get("snapshot_summary", base["snapshot_summary"])
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")
        elif isinstance(market_snapshot_override, dict):
            data = {**base, **market_snapshot_override}
            regime = self.regime_detector.detect_from_dict(data)
            snap.btc_price = self._safe_float(data.get("btc_price"), 0.0)
            snap.btc_change_pct = self._safe_float(data.get("btc_change_pct"), 0.0)
            snap.market_volatility = self._safe_float(data.get("market_volatility"), 0.0)
            snap.market_breadth = self._safe_float(data.get("market_breadth"), 0.5)
            snap.snapshot_summary = str(
                data.get("snapshot_summary") or "외부 시장 스냅샷 오버라이드가 적용되었습니다."
            )
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")
        elif isinstance(market_snapshot_override, MarketSnapshot):
            regime = self.regime_detector.detect(market_snapshot_override)
            snap.btc_price = self._safe_float(market_snapshot_override.btc_price, 0.0)
            snap.btc_change_pct = self._safe_float(market_snapshot_override.btc_change_pct, 0.0)
            snap.market_volatility = self._safe_float(market_snapshot_override.market_volatility, 0.0)
            snap.market_breadth = self._safe_float(market_snapshot_override.market_breadth, 0.5)
            ss = (market_snapshot_override.snapshot_summary or "").strip()
            snap.snapshot_summary = ss or "MarketSnapshot 오버라이드가 적용되었습니다."
            top_src = getattr(market_snapshot_override, "top_gainers", None)
            vol_src = getattr(market_snapshot_override, "volume_leaders", None)
        else:
            data = dict(base)
            data["snapshot_summary"] = "지원하지 않는 오버라이드 형식입니다. 기본 스냅샷을 사용합니다."
            regime = self.regime_detector.detect_from_dict(data)
            snap.snapshot_summary = data["snapshot_summary"]
            top_src = data.get("top_gainers")
            vol_src = data.get("volume_leaders")

        try:
            snap.top_gainers = self._normalize_symbol_list_for_snapshot(top_src)
            snap.volume_leaders = self._normalize_symbol_list_for_snapshot(vol_src)
        except Exception:
            snap.top_gainers = []
            snap.volume_leaders = []

        rs.market.regime = regime
        if not (regime.summary_reason or "").strip():
            rs.market.regime.summary_reason = (
                "장세는 규칙 기반 로컬 판별기로 산출되었습니다."
            )
        if not (snap.snapshot_summary or "").strip():
            snap.snapshot_summary = "기본 시장 스냅샷을 사용합니다."

    def _build_portfolio_state(self) -> None:
        rs = self.last_runtime_state
        ps = rs.portfolio
        summ = ps.summary
        positions = ps.positions
        try:
            if summ.position_count is None:
                current_count = 0
            else:
                current_count = int(summ.position_count)
        except (TypeError, ValueError):
            current_count = 0
        if current_count < 0:
            current_count = 0
        if positions and len(positions) > 0:
            summ.position_count = len(positions)
        else:
            summ.position_count = current_count
        acr = self._safe_float(ps.summary.available_cash_ratio, 0.0)
        if acr < 0.0:
            ps.summary.available_cash_ratio = 0.0
        elif acr > 1.0:
            ps.summary.available_cash_ratio = 1.0

    def _build_intelligence_state(self, forced_mode: Optional[str] = None) -> None:
        rs = self.last_runtime_state
        regime = rs.market.regime
        portfolio = rs.portfolio
        opp = rs.intelligence.opportunities
        try:
            sources: List[Any] = []
            flow = getattr(rs.market, "flow", None)
            snap = getattr(rs.market, "snapshot", None)
            sources.extend(list(getattr(flow, "leader_symbols", None) or []))
            sources.extend(list(getattr(snap, "volume_leaders", None) or []))
            sources.extend(list(getattr(snap, "top_gainers", None) or []))

            seen: set[str] = set()
            cleaned: List[str] = []
            for sym in sources:
                if not isinstance(sym, str):
                    continue
                s = sym.strip()
                if not s:
                    continue
                if s in seen:
                    continue
                seen.add(s)
                cleaned.append(s)
                if len(cleaned) >= 5:
                    break
            opp.candidate_symbols = cleaned
        except Exception:
            opp.candidate_symbols = []

        target = self.portfolio_brain.build_target(regime, portfolio)
        try:
            mirrored: List[str] = []
            source_candidates = getattr(opp, "candidate_symbols", None)
            if isinstance(source_candidates, (list, tuple)):
                mirrored = list(source_candidates)
            if target is not None:
                target.candidate_symbols = mirrored
        except Exception:
            if target is not None:
                try:
                    target.candidate_symbols = []
                except Exception:
                    pass

        decision = self.ai_decision_service.decide(
            regime,
            portfolio,
            target,
            pack_runtime=self.last_module_pack_runtime,
        )
        if self.decision_router is not None:
            try:
                provider = self._read_ai_provider_for_router()
                self._log_decision_router_provider_status(provider)
                # AITS Decision Router 31차
                # Pass selected ai_provider into router raw/meta.
                # Safety: metadata only, no action/order change.
                try:
                    _router_raw = getattr(decision, "raw", None)
                    if not isinstance(_router_raw, dict):
                        _router_raw = {}
                        setattr(decision, "raw", _router_raw)

                    if isinstance(_router_raw, dict):
                        _strategy = getattr(self, "strategy", None)
                        _ai_provider = None

                        if isinstance(_strategy, dict):
                            _ai_provider = _strategy.get("ai_provider")
                        else:
                            _ai_provider = getattr(_strategy, "ai_provider", None)

                        _ai_provider = (
                            _ai_provider
                            or getattr(self, "ai_provider", None)
                            or getattr(self, "provider_name", None)
                            or provider
                            or "local"
                        )
                        _dryrun_override = str(
                            os.getenv("AITS_AI_PROVIDER_DRYRUN_OVERRIDE", "") or ""
                        ).strip().lower()
                        if _dryrun_override in ("local", "basic", "openai", "gpt", "gemini"):
                            _original_provider = str(_ai_provider).strip().lower()
                            _ai_provider = "openai" if _dryrun_override == "gpt" else _dryrun_override
                            self._safe_log_info(
                                "[AITS][Orchestrator] router_ai_provider_dryrun_override | "
                                f"original={_original_provider} | override={_ai_provider} | applied=True"
                            )
                        _ai_provider = str(_ai_provider).strip().lower()

                        # AITS v3.6: select verifier by provider (no behavior change)
                        try:
                            _provider_norm = str(_ai_provider).strip().lower()
                            _selected_verifier = getattr(self, "_verifier_local", None)

                            if _provider_norm == "openai" and getattr(self, "_verifier_openai", None) is not None:
                                _selected_verifier = self._verifier_openai
                            elif _provider_norm == "gemini" and getattr(self, "_verifier_gemini", None) is not None:
                                _selected_verifier = self._verifier_gemini

                            if hasattr(self, "decision_router") and self.decision_router is not None:
                                try:
                                    self.decision_router.ai_engine_provider = _selected_verifier
                                except Exception:
                                    pass

                            self._safe_log_info(
                                "[AITS][Orchestrator] verifier_select | "
                                f"provider={_provider_norm} | "
                                f"selected={type(_selected_verifier).__name__ if _selected_verifier else 'None'}"
                            )
                        except Exception:
                            pass

                        _meta = _router_raw.setdefault("meta", {})
                        if isinstance(_meta, dict):
                            _meta["ai_provider"] = _ai_provider
                            _meta.setdefault("strategy", {})
                            if isinstance(_meta.get("strategy"), dict):
                                _meta["strategy"]["ai_provider"] = _ai_provider

                        self._safe_log_info(
                            "[AITS][Orchestrator] router_ai_provider_meta | "
                            f"ai_provider={_ai_provider}"
                        )
                except Exception as exc:
                    try:
                        self._safe_log_info(
                            "[AITS][Orchestrator] router_ai_provider_meta_failed | "
                            f"error={type(exc).__name__}: {exc}"
                        )
                    except Exception:
                        pass
                decision = self.decision_router.route(
                    decision,
                    provider=provider,
                    context=self._build_decision_router_context(
                        regime,
                        portfolio,
                        opp,
                        decision,
                    ),
                )
                self._safe_log_info(
                    "[AITS][DecisionRouter] passthrough | "
                    f"provider={provider} | "
                    f"action={getattr(decision, 'action', '')} | "
                    f"confidence={self._safe_float(getattr(decision, 'confidence', 0.0), 0.0):.3f} | "
                    "source=ai_decision_service"
                )
            except Exception as exc:
                provider = "local"
                try:
                    provider = self._read_ai_provider_for_router()
                except Exception:
                    provider = "local"
                self._safe_log_info(
                    "[AITS][DecisionRouter] route_failed | "
                    f"provider={provider} | error={str(exc)[:160]} | fallback=original_decision"
                )
        rs.portfolio.target = target
        rs.intelligence.ai_decision = decision

        if forced_mode:
            fm = str(forced_mode)
            base_logic = (decision.selected_strategy_logic or "").strip()
            decision.selected_strategy_logic = (
                f"rule_based_phase1 | forced_mode={fm}"
                if not base_logic
                else f"{base_logic} | forced_mode={fm}"
            )

        sm = self.current_user_controls.get("selected_modules")
        if isinstance(sm, list):
            rs.intelligence.modules.selected_modules = list(sm)
            rs.intelligence.modules.active_modules = list(sm)
            rs.intelligence.modules.dominant_module = sm[0] if sm else ""

        if not (opp.selection_summary or "").strip():
            opp.selection_summary = (
                "Phase 1에서는 종목 후보 탐색보다 장세 및 포트폴리오 판단을 우선합니다."
            )

    def _apply_control_state(self) -> None:
        rs = self.last_runtime_state
        rs.system.paused = self.paused
        ctrl = rs.control
        decision = rs.intelligence.ai_decision
        regime = rs.market.regime
        if not ctrl.protection.stage:
            ctrl.protection.stage = "none"
        nb = self.current_user_controls.get("new_buy_enabled")
        if isinstance(nb, bool) and not nb:
            ctrl.constraints.new_buy_enabled = False
        wl = self.current_user_controls.get("whitelist")
        if isinstance(wl, list):
            ctrl.constraints.whitelist = list(wl)
        bl = self.current_user_controls.get("blacklist")
        if isinstance(bl, list):
            ctrl.constraints.blacklist = list(bl)
            ctrl.constraints.blocked_symbols = list(bl)
        ree = self.current_user_controls.get("reentry_enabled")
        if isinstance(ree, bool):
            ctrl.constraints.reentry_enabled = ree

        ctrl.risk.risk_summary = ctrl.risk.risk_summary or (
            "리스크 엔진이 연결되기 전입니다. 계좌·시장 리스크는 기본값으로 유지합니다."
        )
        ctrl.protection.protection_summary = ctrl.protection.protection_summary or (
            "보호 단계는 아직 트리거되지 않았으며, 정책에 따라 단계적으로 강화될 수 있습니다."
        )
        ctrl.constraints.constraint_summary = (
            "사용자·시스템 제약을 반영합니다. 화이트리스트/블랙리스트와 신규 매수 허용 여부를 "
            "우선 적용합니다."
        )
        if isinstance(nb, bool) and not nb:
            ctrl.constraints.constraint_summary += " 신규 매수는 사용자 설정에 의해 제한됩니다."

        lbl = (regime.label or "").strip().lower()
        if decision.action in ("sell", "reduce") and lbl == "bear":
            ctrl.risk.risk_summary = (ctrl.risk.risk_summary or "").strip() + (
                " 약세장 환경에서 손실·노출 축소가 우선입니다."
            )
            ctrl.protection.protection_summary = (ctrl.protection.protection_summary or "").strip() + (
                " 방어적 조정이 반영되었습니다."
            )

        if lbl == "bear" and self._safe_float(regime.confidence, 1.0) < 0.35:
            ctrl.pause_logic.suggested_pause = True
            ctrl.pause_logic.suggested_pause_reason = (
                "약세장과 낮은 장세 신뢰도가 겹쳐 일시정지를 고려할 수 있습니다."
            )

    def _build_execution_state(self) -> None:
        rs = self.last_runtime_state
        plan = rs.execution.plan
        res = rs.execution.result
        decision = rs.intelligence.ai_decision
        self._update_decision_router_shadow_performance()

        plan.approved_actions = []
        plan.blocked_actions = []
        plan.delayed_actions = []
        plan.requires_user_attention = False

        paused = self.paused or rs.control.pause_logic.pause_requested
        new_buy_ok = rs.control.constraints.new_buy_enabled

        if paused:
            plan.execution_mode = "blocked"
            plan.reason_summary = (
                "일시정지 또는 사용자 요청으로 실행이 차단되었습니다. 재개 후 다시 평가합니다."
            )
        elif decision.action == "wait":
            plan.execution_mode = "normal"
            plan.reason_summary = "현재는 신규 행동보다 관망이 우선입니다."
        elif decision.action == "hold":
            plan.execution_mode = "normal"
            plan.reason_summary = "현재 보유 포지션 유지가 우선입니다."
        elif decision.action in ("buy", "sell", "reduce"):
            resolved_symbol = ""
            raw_symbol = getattr(decision, "selected_symbol", "")
            if isinstance(raw_symbol, str):
                rsym = raw_symbol.strip()
                if rsym:
                    resolved_symbol = rsym
            selected_logic = str(getattr(decision, "selected_strategy_logic", "") or "").strip()
            buy_amount_krw = float(getattr(decision, "amount_krw", 0.0) or 0.0)
            if selected_logic in ("sideways_probe_buy_no_positions", "bear_probe_buy_no_positions") and buy_amount_krw <= 0:
                buy_amount_krw = 5000.0
            item = ActionItem(
                symbol=resolved_symbol,
                action_type=decision.action,
                reason=decision.ai_summary_for_user or "",
                amount_krw=buy_amount_krw,
            )
            if decision.action == "buy":
                print(f"[AITS][Orchestrator] execution_buy_amount | logic={selected_logic} | symbol={getattr(decision, 'selected_symbol', '')} | amount_krw={buy_amount_krw}")
            if not new_buy_ok and decision.action == "buy":
                plan.blocked_actions = [item]
                plan.approved_actions = []
                plan.reason_summary = "신규 매수 제한이 활성화되어 매수 실행이 차단되었습니다."
            else:
                plan.approved_actions = [item]
                plan.reason_summary = decision.ai_summary_for_user or "실행 계획이 생성되었습니다."
            plan.execution_mode = "normal"
        else:
            plan.execution_mode = "normal"
            plan.reason_summary = decision.ai_summary_for_user or "실행 계획이 생성되었습니다."

        res.execution_summary = (
            "Phase 1에서는 실제 주문 실행 없이 실행 계획만 생성합니다."
        )
        try:
            router = getattr(self, "decision_router", None)
            if router is not None and str(getattr(self, "execution_mode", "")) == "disabled":
                sig = router.get_shadow_signal()
                act = sig.get("action")
                if len(plan.approved_actions) == 0:
                    candidate_symbol = ""
                    try:
                        candidates = getattr(rs.intelligence.opportunities, "candidate_symbols", None) or []
                        if candidates:
                            candidate_symbol = str(candidates[0] or "").strip()
                    except Exception:
                        candidate_symbol = ""
                    if not candidate_symbol:
                        try:
                            candidates = getattr(rs.intelligence, "candidates", None) or []
                            if candidates:
                                candidate_symbol = str(
                                    getattr(candidates[0], "symbol", "") or ""
                                ).strip()
                        except Exception:
                            candidate_symbol = ""

                    if act in ("buy", "buy_strong") and candidate_symbol:
                        amount = 5000.0
                        if act == "buy_strong":
                            amount = 10000.0
                        plan.approved_actions.append(
                            ActionItem(
                                action_type="buy",
                                symbol=candidate_symbol,
                                amount_krw=amount,
                                priority=1,
                                source_module="decision_router_shadow",
                                source_provider="local",
                                reason=f"DecisionRouter {act} dryrun",
                            )
                        )

                        try:
                            self.logger.info(
                                "[AITS][DecisionRouter] dryrun_candidate_added | "
                                f"type=buy | symbol={candidate_symbol} | "
                                f"amount={amount:.0f} | "
                                f"confidence={self._safe_float(sig.get('confidence', 0.55), 0.55):.3f}"
                            )
                        except Exception:
                            pass
                        self._record_decision_router_shadow_signal(
                            sig,
                            candidate_symbol,
                        )
                    elif act == "reduce":
                        plan.approved_actions.append(
                            ActionItem(
                                action_type="reduce",
                                symbol="*",
                                amount_krw=0.0,
                                priority=1,
                                source_module="decision_router_shadow",
                                source_provider="local",
                                reason="DecisionRouter reduce dryrun",
                            )
                        )

                        try:
                            self.logger.info(
                                "[AITS][DecisionRouter] dryrun_candidate_added | "
                                "type=reduce | percent=30"
                            )
                        except Exception:
                            pass
                        self._record_decision_router_shadow_signal(sig, "*")
                    elif act == "sell_strong":
                        plan.approved_actions.append(
                            ActionItem(
                                action_type="sell",
                                symbol="*",
                                amount_krw=0.0,
                                priority=1,
                                source_module="decision_router_shadow",
                                source_provider="local",
                                reason="DecisionRouter sell dryrun",
                            )
                        )

                        try:
                            self.logger.info(
                                "[AITS][DecisionRouter] dryrun_candidate_added | "
                                "type=sell | percent=100"
                            )
                        except Exception:
                            pass
                        self._record_decision_router_shadow_signal(sig, "*")
        except Exception:
            pass
        self._apply_risk_guard_to_execution_plan(plan)
        self._log_decision_router_dryrun_compare(plan)

    def _apply_risk_guard_to_execution_plan(self, plan: Any) -> None:
        try:
            guard = getattr(self, "risk_guard", None)
            if guard is None or build_risk_guard_input_from_action is None:
                self._record_risk_guard_event(
                    {
                        "event": "unavailable",
                        "reason": "risk_guard_unavailable",
                        "submitted": 0,
                        "order_allowed": False,
                        "real_order": False,
                        "dry_run": True,
                        "execution_mode": str(getattr(self, "execution_mode", "disabled") or "disabled"),
                    }
                )
                return

            approved_raw = list(getattr(plan, "approved_actions", None) or [])
            blocked_raw = list(getattr(plan, "blocked_actions", None) or [])
            if not approved_raw and not blocked_raw:
                self._record_risk_guard_event(
                    {
                        "event": "no_candidate",
                        "reason": "no_execution_candidate",
                        "submitted": 0,
                        "order_allowed": False,
                        "real_order": False,
                        "dry_run": True,
                        "execution_mode": str(getattr(self, "execution_mode", "disabled") or "disabled"),
                    }
                )
                return

            kept_approved = []
            risk_blocked = list(blocked_raw)
            for action in approved_raw:
                result = self._evaluate_risk_guard_action(action, guard, source="approved")
                if bool(getattr(result, "risk_allowed", False)):
                    kept_approved.append(action)
                else:
                    risk_blocked.append(action)

            for action in blocked_raw:
                self._evaluate_risk_guard_action(action, guard, source="blocked")

            plan.approved_actions = kept_approved
            plan.blocked_actions = risk_blocked
        except Exception as exc:
            self._record_risk_guard_event(
                {
                    "event": "failed",
                    "reason": f"exception:{type(exc).__name__}",
                    "submitted": 0,
                    "order_allowed": False,
                    "real_order": False,
                    "dry_run": True,
                    "execution_mode": str(getattr(self, "execution_mode", "disabled") or "disabled"),
                }
            )

    def _evaluate_risk_guard_action(self, action: Any, guard: Any, *, source: str) -> Any:
        context = self._build_risk_guard_context(action)
        rg_input = build_risk_guard_input_from_action(action, context)
        result = guard.evaluate_order_candidate(rg_input)
        result_dict = result.to_dict() if hasattr(result, "to_dict") else {}
        metadata = {
            "risk_guard_checked": True,
            "risk_guard_version": "v1",
            "risk_proof_fixture": str(context.get("proof_fixture") or ""),
            "risk_allowed": bool(result_dict.get("risk_allowed", False)),
            "risk_blocked_reason": str(result_dict.get("blocked_reason") or ""),
            "risk_severity": str(result_dict.get("severity") or ""),
            "risk_requires_confirm": bool(result_dict.get("requires_confirm", False)),
            "risk_checks_summary": [
                {
                    "name": str(check.get("name", "")),
                    "passed": bool(check.get("passed", False)),
                    "reason": str(check.get("reason", "")),
                }
                for check in list(result_dict.get("checks") or [])[:12]
                if isinstance(check, dict)
            ],
            "submitted": 0,
            "order_allowed": False,
            "real_order": False,
            "dry_run": True,
        }
        try:
            setattr(action, "risk_guard", metadata)
        except Exception:
            pass
        self._record_risk_guard_event(
            {
                "event": "evaluate",
                "source": source,
                "request_id": str(context.get("request_id") or ""),
                "proof_mode": bool(context.get("proof_mode", False)),
                "fixture": str(context.get("proof_fixture") or ""),
                "symbol": str(getattr(action, "symbol", "") or ""),
                "side": str(getattr(action, "action_type", "") or ""),
                "risk_allowed": bool(metadata["risk_allowed"]),
                "blocked_reason": metadata["risk_blocked_reason"],
                "severity": metadata["risk_severity"],
                "submitted": 0,
                "order_allowed": False,
                "real_order": False,
                "dry_run": True,
                "execution_mode": str(getattr(self, "execution_mode", "disabled") or "disabled"),
            }
        )
        return result

    def _build_risk_guard_context(self, action: Any) -> Dict[str, Any]:
        rs = self.last_runtime_state
        symbol = str(getattr(action, "symbol", "") or "").strip()
        price = self._read_risk_guard_price_no_fetch(symbol)
        portfolio = getattr(rs, "portfolio", None)
        summary = getattr(portfolio, "summary", None)
        holdings_value = 0.0
        for pos in list(getattr(portfolio, "positions", None) or []):
            try:
                if str(getattr(pos, "symbol", "") or "").strip() != symbol:
                    continue
                qty = self._safe_float(getattr(pos, "qty", 0.0), 0.0)
                cur = self._safe_float(getattr(pos, "current_price", 0.0), 0.0)
                avg = self._safe_float(getattr(pos, "avg_price", 0.0), 0.0)
                holdings_value += qty * (cur if cur > 0 else avg)
            except Exception:
                continue
        cash = self._safe_float(getattr(summary, "cash_balance", 0.0), 0.0)
        portfolio_value = self._safe_float(getattr(summary, "total_equity", 0.0), 0.0)
        proof_fixture = str(getattr(action, "risk_guard_proof_fixture", "") or "").strip()
        proof_request_id = str(getattr(action, "risk_guard_request_id", "") or "").strip()
        return {
            "symbol": symbol,
            "price": price,
            "stale_price": price <= 0.0,
            "cash_available_krw": cash,
            "portfolio_value_krw": portfolio_value,
            "holdings_value_krw": holdings_value,
            "daily_realized_pnl_krw": self._safe_float(getattr(summary, "realized_pnl", 0.0), 0.0),
            "daily_loss_limit_krw": 50_000.0,
            "max_order_amount_krw": 10_000.0,
            "max_position_value_krw": 30_000.0,
            "emergency_stop": bool(self.paused or getattr(getattr(rs, "control", None).pause_logic, "pause_requested", False)),
            "execution_mode": str(getattr(self, "execution_mode", "disabled") or "disabled"),
            "dry_run": True,
            "request_id": proof_request_id
            or f"cycle-{getattr(getattr(rs, 'meta', None), 'cycle_id', 0)}:{symbol or '-'}:{getattr(action, 'action_type', '') or '-'}",
            "proof_mode": bool(getattr(action, "risk_guard_proof_mode", False)),
            "proof_fixture": proof_fixture,
        }

    def _read_risk_guard_price_no_fetch(self, symbol: str) -> float:
        try:
            sym = str(symbol or "").strip()
            if not sym or sym == "*":
                return 0.0
            rs = self.last_runtime_state
            if sym == "KRW-BTC":
                snap = getattr(getattr(rs, "market", None), "snapshot", None)
                price = self._safe_float(getattr(snap, "btc_price", 0.0), 0.0)
                if price > 0.0:
                    return price
            portfolio = getattr(rs, "portfolio", None)
            for pos in list(getattr(portfolio, "positions", None) or []):
                if str(getattr(pos, "symbol", "") or "").strip() != sym:
                    continue
                price = self._safe_float(getattr(pos, "current_price", 0.0), 0.0)
                if price > 0.0:
                    return price
        except Exception:
            return 0.0
        return 0.0

    def _record_risk_guard_event(self, event: Dict[str, Any]) -> None:
        safe = dict(event or {})
        safe["submitted"] = 0
        safe["order_allowed"] = False
        safe["real_order"] = False
        safe["dry_run"] = True
        try:
            events = list(getattr(self, "last_risk_guard_events", None) or [])
            events.append(safe)
            self.last_risk_guard_events = events[-20:]
        except Exception:
            pass
        self._safe_log_info(
            "[AITS][RiskGuardActivePath] "
            f"event={safe.get('event', '')} "
            f"request_id={safe.get('request_id', '-')} "
            f"proof_mode={bool(safe.get('proof_mode', False))} "
            f"fixture={safe.get('fixture', '') or '-'} "
            f"symbol={safe.get('symbol', '-')} "
            f"side={safe.get('side', '-')} "
            f"risk_allowed={bool(safe.get('risk_allowed', False))} "
            f"blocked_reason={safe.get('blocked_reason') or safe.get('reason') or '-'} "
            "submitted=0 order_allowed=False real_order=False dry_run=True "
            f"execution_mode={safe.get('execution_mode', 'disabled')}"
        )

    def _record_decision_router_shadow_signal(self, signal: Dict[str, Any], symbol: str) -> None:
        try:
            router = getattr(self, "decision_router", None)
            if router is None or not hasattr(router, "record_shadow_signal"):
                return
            rs = self.last_runtime_state
            opp = getattr(getattr(rs, "intelligence", None), "opportunities", None)
            candidates = getattr(opp, "candidate_symbols", None) or []
            current_price = self._lookup_shadow_performance_price(symbol)
            if current_price is None:
                self._safe_log_info(
                    "[AITS][DecisionRouter] performance_entry_price_missing | "
                    f"symbol={symbol}"
                )
            else:
                self._safe_log_info(
                    "[AITS][DecisionRouter] performance_entry_price | "
                    f"symbol={symbol} | price={current_price}"
                )
            router.record_shadow_signal(
                signal_action=signal.get("action"),
                signal_confidence=signal.get("confidence", 0.0),
                symbol=symbol,
                market_regime=str(getattr(getattr(rs, "market", None).regime, "label", "") or ""),
                candidate_count=len(candidates) if isinstance(candidates, (list, tuple)) else 0,
                current_price=current_price,
            )
        except Exception:
            pass

    def _log_decision_router_dryrun_compare(self, plan: Any) -> None:
        try:
            router = getattr(self, "decision_router", None)
            if router is None or not hasattr(router, "get_last_soft_override_candidate"):
                return
            soft = router.get_last_soft_override_candidate()

            soft_action = str(soft.get("candidate_action", "none"))
            soft_eligible = bool(soft.get("eligible", False))
            soft_strength = str(soft.get("candidate_strength", "none"))

            dry_actions = []
            try:
                for action_item in list(getattr(plan, "approved_actions", []) or []):
                    action = getattr(action_item, "action", "")
                    if not action:
                        action = getattr(action_item, "action_type", "")
                    dry_actions.append(
                        {
                            "action": action,
                            "symbol": getattr(action_item, "symbol", ""),
                            "amount_krw": getattr(action_item, "amount_krw", 0),
                            "confidence": getattr(action_item, "confidence", 0),
                        }
                    )
            except Exception:
                dry_actions = []

            dry_count = len(dry_actions)
            first_dry_action = dry_actions[0]["action"] if dry_actions else "none"
            first_dry_symbol = dry_actions[0]["symbol"] if dry_actions else ""
            first_dry_amount = dry_actions[0]["amount_krw"] if dry_actions else 0

            matched = False
            if soft_action in ("buy", "buy_strong") and first_dry_action == "buy":
                matched = True
            elif soft_action in ("reduce", "sell", "sell_strong") and first_dry_action in ("reduce", "sell"):
                matched = True
            elif soft_action in ("wait", "none") and dry_count == 0:
                matched = True

            mismatch_reason = "matched"
            if not matched:
                if soft_action in ("wait", "none") and dry_count > 0:
                    mismatch_reason = "unexpected_dryrun_action"
                elif soft_action in ("buy", "buy_strong") and soft_eligible and dry_count == 0:
                    mismatch_reason = "missing_buy_dryrun"
                elif soft_action in ("reduce", "sell", "sell_strong") and soft_eligible and dry_count == 0:
                    mismatch_reason = "missing_sell_dryrun"
                elif soft_action in ("buy", "buy_strong") and dry_count > 0 and first_dry_action != "buy":
                    mismatch_reason = "dryrun_action_mismatch_buy"
                elif (
                    soft_action in ("reduce", "sell", "sell_strong")
                    and dry_count > 0
                    and first_dry_action not in ("reduce", "sell")
                ):
                    mismatch_reason = "dryrun_action_mismatch_sell"
                else:
                    mismatch_reason = "unknown_mismatch"

            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(
                    "[AITS][DecisionRouter] dryrun_compare | "
                    f"soft_action={soft_action} | "
                    f"soft_eligible={soft_eligible} | "
                    f"soft_strength={soft_strength} | "
                    f"dry_count={dry_count} | "
                    f"dry_action={first_dry_action} | "
                    f"dry_symbol={first_dry_symbol} | "
                    f"dry_amount={float(first_dry_amount or 0):.0f} | "
                    f"matched={matched} | "
                    f"mismatch_reason={mismatch_reason}"
                )
            if not matched and self.logger is not None and hasattr(self.logger, "warning"):
                self.logger.warning(
                    "[AITS][DecisionRouter] dryrun_mismatch_warning | "
                    f"soft_action={soft_action} | "
                    f"soft_eligible={soft_eligible} | "
                    f"dry_count={dry_count} | "
                    f"dry_action={first_dry_action} | "
                    f"reason={mismatch_reason}"
                )
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "warning"):
                    self.logger.warning(
                        "[AITS][DecisionRouter] dryrun_compare_failed | "
                        f"error={type(exc).__name__}"
                    )
            except Exception:
                pass

    def _update_decision_router_shadow_performance(self) -> None:
        try:
            router = getattr(self, "decision_router", None)
            if router is None or not hasattr(router, "update_shadow_performance"):
                return
            router.update_shadow_performance(self._lookup_shadow_performance_price)
        except Exception as exc:
            try:
                if self.logger is not None and hasattr(self.logger, "warning"):
                    self.logger.warning(
                        "[AITS][DecisionRouter] performance_update_call_failed | "
                        f"error={str(exc)[:160]}"
                    )
            except Exception:
                pass

    def _lookup_shadow_signal_price(self, symbol: str) -> Optional[float]:
        return self._lookup_shadow_performance_price(symbol)

    def _lookup_shadow_performance_price(self, symbol: str) -> Optional[float]:
        try:
            sym = str(symbol or "").strip()
            if not sym or sym == "*":
                self._log_shadow_performance_price_lookup(sym, None, "not_found")
                return None
            rs = self.last_runtime_state
            if sym == "KRW-BTC":
                snap = getattr(getattr(rs, "market", None), "snapshot", None)
                price = self._safe_float(getattr(snap, "btc_price", 0.0), 0.0)
                if price > 0.0:
                    self._log_shadow_performance_price_lookup(
                        sym,
                        price,
                        "market.snapshot.btc_price",
                    )
                    return price
            intelligence = getattr(rs, "intelligence", None)
            opp = getattr(intelligence, "opportunities", None)
            for item in list(getattr(opp, "top_candidates", None) or []):
                if self._read_shadow_symbol_from_object(item) != sym:
                    continue
                price, source = self._read_shadow_price_with_source(
                    item,
                    "intelligence.opportunities.top_candidates",
                )
                if price is not None:
                    self._log_shadow_performance_price_lookup(sym, price, source)
                    return price
            for item in list(getattr(intelligence, "candidates", None) or []):
                if self._read_shadow_symbol_from_object(item) != sym:
                    continue
                price, source = self._read_shadow_price_with_source(
                    item,
                    "intelligence.candidates",
                )
                if price is not None:
                    self._log_shadow_performance_price_lookup(sym, price, source)
                    return price
            market = getattr(rs, "market", None)
            for container_name in ("prices", "tickers", "market_data"):
                for parent_name, parent in (
                    ("market", market),
                    ("market.snapshot", getattr(market, "snapshot", None)),
                ):
                    container = self._read_shadow_value(parent, container_name)
                    price, source = self._read_shadow_price_from_mapping(
                        container,
                        sym,
                        f"{parent_name}.{container_name}",
                    )
                    if price is not None:
                        self._log_shadow_performance_price_lookup(sym, price, source)
                        return price
            for container_name in ("candidate_prices", "prices", "tickers", "market_data"):
                container = self._read_shadow_value(opp, container_name)
                price, source = self._read_shadow_price_from_mapping(
                    container,
                    sym,
                    f"intelligence.opportunities.{container_name}",
                )
                if price is not None:
                    self._log_shadow_performance_price_lookup(sym, price, source)
                    return price
            portfolio = getattr(rs, "portfolio", None)
            for item in list(getattr(portfolio, "positions", None) or []):
                if self._read_shadow_symbol_from_object(item) != sym:
                    continue
                price, source = self._read_shadow_price_with_source(
                    item,
                    "portfolio.positions",
                    price_keys=("current_price", "price", "last_price", "avg_price"),
                )
                if price is not None:
                    self._log_shadow_performance_price_lookup(sym, price, source)
                    return price
            candidate_symbols = getattr(opp, "candidate_symbols", None)
            if isinstance(candidate_symbols, (list, tuple)) and sym in [str(x).strip() for x in candidate_symbols]:
                price, source = self._read_shadow_price_with_source(
                    opp,
                    "intelligence.opportunities.candidate_symbols.related",
                )
                if price is not None:
                    self._log_shadow_performance_price_lookup(sym, price, source)
                    return price
        except Exception:
            self._log_shadow_performance_price_lookup(str(symbol or "").strip(), None, "not_found")
            return None
        fb_price = None
        fb_src = "not_found"
        try:
            now_sec = int(time.time())
            cache_key = f"_shadow_price_cache_{sym}"
            last = getattr(self, cache_key, None)
            if isinstance(last, dict) and now_sec - int(last.get("ts", 0) or 0) <= 1:
                fb_price = self._safe_float(last.get("price"), 0.0)
                fb_src = str(last.get("source") or "upbit_cached")
                if fb_price <= 0.0:
                    fb_price = None
            else:
                fb_price, fb_src = _fetch_upbit_price_once(sym)
                setattr(
                    self,
                    cache_key,
                    {"ts": now_sec, "price": fb_price, "source": fb_src},
                )
            self._log_shadow_performance_price_lookup(sym, fb_price, fb_src)
            if isinstance(fb_price, (int, float)) and fb_price > 0:
                return float(fb_price)
            return None
        except Exception:
            self._log_shadow_performance_price_lookup(sym, None, "upbit_err_Exception")
            return None
        self._log_shadow_performance_price_lookup(sym, None, "not_found")
        return None

    def _read_shadow_symbol_from_object(self, obj: Any) -> str:
        for key in ("symbol", "ticker", "market", "code"):
            try:
                if isinstance(obj, dict):
                    raw = obj.get(key)
                else:
                    raw = getattr(obj, key, None)
                text = str(raw or "").strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _read_shadow_price_from_object(self, obj: Any) -> Optional[float]:
        price, _source = self._read_shadow_price_with_source(obj, "unknown")
        return price

    def _read_shadow_price_with_source(
        self,
        obj: Any,
        source_prefix: str,
        price_keys: tuple[str, ...] = ("price", "current_price", "last_price", "trade_price", "close"),
    ) -> tuple[Optional[float], str]:
        for key in price_keys:
            try:
                raw = self._read_shadow_value(obj, key)
                price = self._safe_float(raw, 0.0)
                if price > 0.0:
                    return price, f"{source_prefix}.{key}"
            except Exception:
                continue
        return None, "not_found"

    def _read_shadow_price_from_mapping(
        self,
        container: Any,
        symbol: str,
        source_prefix: str,
    ) -> tuple[Optional[float], str]:
        if not isinstance(container, dict):
            return None, "not_found"
        try:
            value = container.get(symbol)
            if value is None:
                return None, "not_found"
            direct = self._safe_float(value, 0.0)
            if direct > 0.0 and not isinstance(value, dict):
                return direct, source_prefix
            price, source = self._read_shadow_price_with_source(value, source_prefix)
            if price is not None:
                return price, source
        except Exception:
            return None, "not_found"
        return None, "not_found"

    def _read_shadow_value(self, obj: Any, key: str) -> Any:
        try:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)
        except Exception:
            return None

    def _log_shadow_performance_price_lookup(
        self,
        symbol: str,
        price: Optional[float],
        source: str,
    ) -> None:
        self._safe_log_info(
            "[AITS][DecisionRouter] performance_price_lookup | "
            f"symbol={symbol} | "
            f"price={price if price is not None else 'None'} | "
            f"source={source or 'not_found'}"
        )

    def _build_explainability_state(self) -> None:
        rs = self.last_runtime_state
        regime = rs.market.regime
        target = rs.portfolio.target
        decision = rs.intelligence.ai_decision
        explain = self.explainability_service.build(regime, target, decision)
        rs.explainability = explain
        self.last_explainability = explain

        ov = rs.oversight
        if not (ov.oversight_summary or "").strip():
            ov.oversight_summary = (
                explain.why_pause_trading or explain.current_ai_view or "사용자 검토가 가능합니다."
            )

        mpr = self.last_module_pack_runtime
        if mpr is not None and (mpr.active_pack_id or "").strip():
            pname = (mpr.pack_name_ko or "").strip() or str(mpr.active_pack_id)
            suffix = f" / 현재 모듈팩: {pname}"
            cur = (ov.oversight_summary or "").strip()
            if suffix.strip() not in cur:
                ov.oversight_summary = (cur + suffix).strip()

        if decision.action == "sell":
            if "sell_review" not in ov.review_required_actions:
                ov.review_required_actions.append("sell_review")

        if decision.action == "buy" and self._safe_float(regime.confidence, 1.0) < 0.35:
            ov.trust_alerts.append(
                "장세 신뢰도가 낮은 상태에서 매수 신호가 있습니다. 주의하세요."
            )
