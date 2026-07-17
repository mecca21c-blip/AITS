from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.ai_review_repository import AITSDerivedJsonRepository


POLICY_SCHEMA = "aits_effective_policy.v1"
ORDER_ACTIONS = {"buy", "add", "sell", "reduce", "take_profit", "stop_loss", "rotate"}
ALL_ACTIONS = {
    "wait", "hold", *ORDER_ACTIONS,
    "promote", "reject", "replace", "reduce_and_rotate", "rotate_review",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _positive_numbers(*values: Any) -> list[float]:
    result: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            result.append(number)
    return result


class AITSEffectivePolicyResolver:
    """Resolve existing policy SSOT inputs into a conservative immutable snapshot.

    This service describes permitted decision space. It never selects an action,
    creates an order, or expands LOCAL_ENGINE authority.
    """

    schema = POLICY_SCHEMA

    @staticmethod
    def canonical_hash(value: Mapping[str, Any]) -> str:
        presentation_only = {
            "global_policy_style", "global_preset_name", "asset_policy_style", "asset_preset_name",
            "effective_policy_style", "effective_preset_name", "max_weight_pct",
            "asset_override_active", "applied_to_router",
        }
        body = {
            key: item for key, item in dict(value).items()
            if key not in {"policy_id", "policy_hash", "created_at", "preview_only", "applied_to_runtime"} | presentation_only
        }
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def resolve(
        cls,
        *,
        global_policy: Mapping[str, Any] | None = None,
        asset_policy: Mapping[str, Any] | None = None,
        preset: Mapping[str, Any] | None = None,
        user_overrides: Mapping[str, Any] | None = None,
        authority: Mapping[str, Any] | None = None,
        execution_mode: str = "",
        preferred_provider: str = "",
        basic_config: Mapping[str, Any] | None = None,
        managed_pool_rows: list[Mapping[str, Any]] | None = None,
        scope_type: str = "position",
        scope: str = "",
        symbol: str = "",
        preview_only: bool = False,
        created_at: str = "",
    ) -> dict[str, Any]:
        global_policy = _dict(global_policy)
        asset_policy = _dict(asset_policy)
        preset = _dict(preset)
        overrides = _dict(user_overrides)
        authority = _dict(authority)
        basic_config = _dict(basic_config)
        symbol = str(symbol or asset_policy.get("symbol") or "").strip().upper()

        global_ai = _dict(global_policy.get("ai_policy"))
        global_risk = _dict(global_ai.get("risk_budget"))
        asset_risk = _dict(asset_policy.get("risk_budget"))
        override_risk = _dict(overrides.get("risk_budget"))
        conflicts: list[dict[str, Any]] = []

        def conservative_min(name: str, *values: Any) -> float:
            numbers = _positive_numbers(*values)
            if len(set(numbers)) > 1:
                conflicts.append({"field": name, "resolution": "minimum_selected", "values": numbers})
            return min(numbers) if numbers else 0.0

        def conservative_max(name: str, *values: Any) -> float:
            numbers = _positive_numbers(*values)
            if len(set(numbers)) > 1:
                conflicts.append({"field": name, "resolution": "maximum_selected", "values": numbers})
            return max(numbers) if numbers else 0.0

        global_allowed = {str(v).lower() for v in _list(global_policy.get("allowed_actions")) if str(v).lower() in ALL_ACTIONS}
        asset_allowed = {str(v).lower() for v in _list(asset_policy.get("allowed_actions")) if str(v).lower() in ALL_ACTIONS}
        override_allowed = {str(v).lower() for v in _list(overrides.get("allowed_actions")) if str(v).lower() in ALL_ACTIONS}
        explicit_allowed = [values for values in (global_allowed, asset_allowed, override_allowed) if values]
        allowed = set.intersection(*explicit_allowed) if explicit_allowed else set(ALL_ACTIONS)
        restricted = {
            str(v).lower()
            for source in (global_policy, asset_policy, overrides)
            for v in _list(source.get("restricted_actions"))
            if str(v).lower() in ALL_ACTIONS
        }
        allowed -= restricted
        confirmation = {
            str(v).lower()
            for source in (global_policy, asset_policy, overrides)
            for v in _list(source.get("confirmation_required_actions"))
            if str(v).lower() in ALL_ACTIONS
        }

        try:
            local_level = int(authority.get("effective_level", authority.get("effective_global_level", authority.get("global_level", 1))))
        except (TypeError, ValueError):
            local_level = 1
        authority_state = str(authority.get("authority_state") or authority.get("global_authority_state") or authority.get("authority") or "candidate_only")
        if local_level <= 2 or authority_state in {"external_only", "candidate_only", "co_pilot"}:
            confirmation.update(ORDER_ACTIONS)

        eta_global = _dict(global_policy.get("eta_bounds"))
        eta_asset = _dict(asset_policy.get("eta_bounds"))
        min_eta = max([0, *[int(v) for v in _positive_numbers(eta_global.get("minimum_seconds"), eta_asset.get("minimum_seconds"), overrides.get("eta_min_seconds"))]])
        max_eta_values = [int(v) for v in _positive_numbers(eta_global.get("maximum_seconds"), eta_asset.get("maximum_seconds"), overrides.get("eta_max_seconds"))]
        max_eta = min(max_eta_values) if max_eta_values else 86400
        if min_eta > max_eta:
            conflicts.append({"field": "eta_bounds", "resolution": "blocked", "minimum": min_eta, "maximum": max_eta})

        snapshot: dict[str, Any] = {
            "schema": POLICY_SCHEMA,
            "policy_version": 1,
            "created_at": created_at or str(global_policy.get("updated_at") or asset_policy.get("updated_at") or _utc_now()),
            "scope_type": str(scope_type or "position"),
            "scope": str(scope or symbol or "GLOBAL"),
            "symbol": symbol,
            "global_policy_snapshot_id": str(global_policy.get("snapshot_id") or global_policy.get("policy_id") or ""),
            "asset_policy_snapshot_id": str(asset_policy.get("snapshot_id") or asset_policy.get("policy_id") or ""),
            "preset_id": str(asset_policy.get("preset_name") or global_policy.get("preset_name") or preset.get("preset_id") or ""),
            "user_override_ids": list(overrides.get("override_ids") or []),
            "authority_state_id": str(authority.get("state_id") or authority.get("updated_at") or ""),
            "execution_mode": str(execution_mode or ""),
            "source_priority": ["safety_constraints", "global_policy", "asset_policy", "preset", "user_override", "local_authority", "provider_cost_guard"],
            "conflict_resolution_log": conflicts,
            "operating_style": str(asset_policy.get("policy_style") or global_policy.get("policy_style") or preset.get("operating_style") or "balanced"),
            "risk_preference": asset_policy.get("risk_level", global_policy.get("risk_level", 50)),
            "observation_bias": asset_policy.get("observation_bias", global_policy.get("observation_bias", "balanced")),
            "wait_preference": asset_policy.get("wait_preference", global_policy.get("wait_preference", 50)),
            "autonomy_level": asset_policy.get("autonomy_level", global_policy.get("autonomy_level", 0)),
            "turnover_preference": asset_policy.get("turnover_preference", global_policy.get("turnover_preference", "balanced")),
            "holding_horizon": asset_policy.get("holding_horizon", global_policy.get("holding_horizon", "adaptive")),
            "teacher_confirmation_preference": asset_policy.get("teacher_confirmation_preference", global_policy.get("teacher_confirmation_preference", "required_when_uncertain")),
            "max_asset_weight": conservative_min("max_asset_weight", asset_policy.get("max_weight_pct"), asset_risk.get("max_asset_weight"), global_risk.get("max_asset_weight"), override_risk.get("max_asset_weight")),
            "max_total_exposure": conservative_min("max_total_exposure", global_risk.get("max_total_exposure"), asset_risk.get("max_total_exposure"), override_risk.get("max_total_exposure")),
            "max_order_krw": conservative_min("max_order_krw", global_risk.get("max_order_krw") or global_risk.get("max_entry_krw"), asset_risk.get("max_order_krw"), override_risk.get("max_order_krw")),
            "cash_reserve": conservative_max("cash_reserve", global_risk.get("cash_reserve") or global_risk.get("reserve_cash_krw"), asset_risk.get("cash_reserve"), override_risk.get("cash_reserve")),
            "concentration_limit": conservative_min("concentration_limit", global_risk.get("concentration_limit"), asset_risk.get("concentration_limit"), override_risk.get("concentration_limit")),
            "portfolio_cap": conservative_min("portfolio_cap", global_risk.get("total_budget_krw"), asset_risk.get("portfolio_cap"), override_risk.get("portfolio_cap")),
            "add_position_allowed": bool(global_policy.get("add_position_allowed", True) and asset_policy.get("add_position_allowed", True) and overrides.get("add_position_allowed", True)),
            "reduce_position_allowed": bool(global_policy.get("reduce_position_allowed", True) and asset_policy.get("reduce_position_allowed", True) and overrides.get("reduce_position_allowed", True)),
            "rotation_allowed": bool(global_policy.get("rotation_allowed", True) and asset_policy.get("rotation_allowed", True) and overrides.get("rotation_allowed", True)),
            "preferred_provider": str(preferred_provider or global_policy.get("preferred_provider") or ""),
            "external_confirmation_required": bool(confirmation or global_policy.get("external_confirmation_required", False)),
            "teacher_sampling_policy": deepcopy(global_policy.get("teacher_sampling_policy") or {}),
            "cost_guard_policy_ref": str(global_policy.get("cost_guard_policy_ref") or "strategy.ai_provider"),
            "local_authority_level": local_level,
            "task_action_authority": deepcopy(authority.get("task_action_authority") or {}),
            "allowed_actions": sorted(allowed),
            "restricted_actions": sorted(restricted),
            "confirmation_required_actions": sorted(confirmation),
            "unsupported_actions": sorted(ALL_ACTIONS - allowed - restricted),
            "abstain_on_policy_conflict": True,
            "required_watch_points": list(asset_policy.get("required_watch_points") or global_policy.get("required_watch_points") or []),
            "required_invalidation_types": list(asset_policy.get("required_invalidation_types") or global_policy.get("required_invalidation_types") or []),
            "eta_bounds": {"minimum_seconds": min_eta, "maximum_seconds": max_eta},
            "reason_required": True,
            "evidence_required": bool(global_policy.get("evidence_required", True)),
            "expected_scenario_required": bool(global_policy.get("expected_scenario_required", True)),
            "policy_valid": min_eta <= max_eta,
            "policy_conflicts": [row.get("field") for row in conflicts],
            "blocker": "effective_policy_conflict" if min_eta > max_eta else "",
            "direct_order_authority": False,
            "managed_pool_count": len(managed_pool_rows or []),
            "basic_config_present": bool(basic_config),
            "preview_only": bool(preview_only),
            "applied_to_runtime": not bool(preview_only),
            "applied_to_order": False,
        }
        snapshot["policy_hash"] = cls.canonical_hash(snapshot)
        snapshot["policy_id"] = f"policy-{snapshot['policy_hash'][:16]}"
        return snapshot

    @staticmethod
    def immutable(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
        return MappingProxyType(deepcopy(dict(snapshot)))


class AITSEffectivePolicySnapshotRepository:
    """Persist only derived immutable runtime snapshots; policy source SSOT is untouched."""

    def __init__(self, root: Path | str = "data/ai_policy") -> None:
        self.root = Path(root)
        self.runtime_path = self.root / "effective_policy_runtime_snapshot.json"
        self.history_path = self.root / "effective_policy_snapshots.jsonl"

    def inspect(self) -> dict[str, Any]:
        value = AITSDerivedJsonRepository.load_json(self.runtime_path, {})
        return value if isinstance(value, dict) else {}

    def persist(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        value = deepcopy(dict(snapshot))
        if value.get("schema") != POLICY_SCHEMA or not value.get("policy_hash"):
            return {"written": False, "blocker": "effective_policy_snapshot_invalid"}
        current = self.inspect()
        if str(current.get("policy_id") or "") == str(value.get("policy_id") or ""):
            return {"written": False, "deduplicated": True, "policy_id": value.get("policy_id")}
        AITSDerivedJsonRepository.atomic_write_json(self.runtime_path, value)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"written": True, "deduplicated": False, "policy_id": value.get("policy_id")}
