from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any, Iterable

from app.services.aits_orchestrator import (
    AITSLocalTrainingDatasetCurator as _LegacyDatasetCurator,
)


SOURCE_FILES = {
    "outcome_records.jsonl",
    "provider_comparison_outcomes.jsonl",
    "outcome_tracking_state.json",
}

DERIVED_FILES = {
    "curated_local_training_records.jsonl",
    "excluded_local_training_records.jsonl",
    "curated_local_training_summary.json",
    "local_training_features.jsonl",
    "local_training_features_excluded.jsonl",
    "local_training_feature_summary.json",
    "registry.json",
    "latest_model.json",
    "latest_training_metrics.json",
    "calibration_profile.json",
    "calibration_history.jsonl",
    "latest_calibration_summary.json",
}


TASK_REQUIRED_FEATURES = {
    "position": (
        "position.qty",
        "position.current_price",
        "position.position_value_krw",
        "position.pnl_pct",
        "portfolio.total_asset_krw",
        "risk.valuation_unit_mismatch",
    ),
    "portfolio": (
        "portfolio.total_asset_krw",
        "portfolio.available_krw",
        "portfolio.exposure_for_cap",
        "portfolio.cap_remaining_krw",
        "portfolio.position_count",
    ),
    "candidate": (
        "opportunity.opportunity_gap_change",
        "portfolio.total_asset_krw",
        "portfolio.available_krw",
    ),
}


def _task_contract_kind(task: str, scope_type: str) -> str:
    if task == "portfolio_management_decision" or scope_type == "portfolio":
        return "portfolio"
    if task in {
        "buy_decision",
        "rotation_decision",
        "promotion_decision",
        "managed_pool_promotion_decision",
    }:
        return "candidate"
    return "position"


def _nested_present(source: dict, path: str) -> bool:
    value: Any = source
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return value is not None and value != ""


def build_training_eligibility_provenance(
    *,
    task: str,
    scope_type: str,
    scope: str,
    symbol: str,
    provider_source: str,
    final_action: str,
    feature_context: dict,
    payload_quality: dict,
    decision_contract_schema: str = "aits_ai_decision.v1",
    payload_snapshot_schema: str = "aits_ai_decision_payload.v1",
) -> dict:
    """Build a factual precheck; it does not replace the offline training gate."""
    kind = _task_contract_kind(task, scope_type)
    required = list(TASK_REQUIRED_FEATURES[kind])
    present = [path for path in required if _nested_present(feature_context, path)]
    missing = [path for path in required if path not in present]
    evidence_summary = {}
    for group in ("market", "indicators", "position", "portfolio", "risk", "provider", "opportunity"):
        values = feature_context.get(group) if isinstance(feature_context.get(group), dict) else {}
        evidence_summary[group] = sum(value is not None and value != "" for value in values.values())
    blockers = []
    if not task:
        blockers.append("task_missing")
    if not scope:
        blockers.append("scope_missing")
    if not provider_source:
        blockers.append("provider_source_missing")
    if not final_action:
        blockers.append("final_action_missing")
    if not str(payload_quality.get("payload_quality_grade") or ""):
        blockers.append("payload_quality_missing")
    if missing:
        blockers.append("task_specific_required_fields_missing")
    return {
        "decision_task": task,
        "decision_scope": scope,
        "provider_source": provider_source,
        "teacher_source": provider_source if provider_source in {"openai", "gemini"} else "",
        "final_action": final_action,
        "decision_contract_schema": decision_contract_schema,
        "payload_snapshot_schema": payload_snapshot_schema,
        "payload_quality": {
            key: payload_quality.get(key)
            for key in (
                "payload_quality_grade",
                "feature_manifest_hash",
                "payload_required_feature_count",
                "payload_available_feature_count",
                "payload_missing_feature_count",
                "payload_unavailable_feature_count",
            )
        },
        "required_fields_present": present,
        "evidence_summary": evidence_summary,
        "task_specific_required_fields": required,
        "missing_fields": missing,
        "training_eligibility_precheck": {
            "status": "eligible" if not blockers else "ineligible",
            "eligible": not blockers,
            "blockers": blockers,
            "contract_kind": kind,
        },
    }


def _json_bytes(value: Any, *, indent: int | None = None) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=indent,
        default=str,
    ).encode("utf-8")


def atomic_write_bytes(path: Path, payload: bytes, *, validate_json: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    temporary = path.with_name(f".{path.name}.{token}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if validate_json:
        json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def atomic_write_json(path: Path, value: dict) -> None:
    atomic_write_bytes(path, _json_bytes(value, indent=2), validate_json=True)


def atomic_write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    payload = b"".join(_json_bytes(row) + b"\n" for row in rows)
    for line in payload.splitlines():
        if line.strip():
            json.loads(line.decode("utf-8"))
    atomic_write_bytes(path, payload)


def read_json_dict(path: Path, default: dict | None = None) -> dict:
    fallback = dict(default or {})
    if not path.exists() or path.stat().st_size == 0:
        return fallback
    try:
        payload = path.read_bytes()
        if b"\x00" in payload:
            return fallback
        value = json.loads(payload.decode("utf-8"))
        return value if isinstance(value, dict) else fallback
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return fallback


def read_recoverable_jsonl(path: Path) -> tuple[list[dict], dict[str, int]]:
    rows: list[dict] = []
    seen: set[str] = set()
    metrics = {
        "corrupted_lines": 0,
        "nul_lines_recovered": 0,
        "duplicates": 0,
    }
    if not path.exists():
        return rows, metrics
    for raw_line in path.read_bytes().splitlines():
        if not raw_line.strip(b"\x00 \t\r\n"):
            continue
        had_nul = b"\x00" in raw_line
        cleaned = raw_line.replace(b"\x00", b"").strip()
        try:
            value = json.loads(cleaned.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            metrics["corrupted_lines"] += 1
            continue
        if not isinstance(value, dict):
            metrics["corrupted_lines"] += 1
            continue
        if had_nul:
            metrics["nul_lines_recovered"] += 1
        fingerprint = hashlib.sha256(
            _json_bytes(value)
        ).hexdigest()
        if fingerprint in seen:
            metrics["duplicates"] += 1
            continue
        seen.add(fingerprint)
        rows.append(value)
    return rows, metrics


def inspect_data_file(path: Path, *, source: bool) -> dict:
    result = {
        "path": str(path),
        "name": path.name,
        "category": "source" if source else "derived",
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "nul_bytes": 0,
        "valid": False,
        "empty": False,
        "recoverable": False,
        "blocker": "missing",
    }
    if not path.exists():
        return result
    payload = path.read_bytes()
    result["nul_bytes"] = payload.count(b"\x00")
    if not payload:
        result.update({"empty": True, "blocker": "empty"})
        return result
    if path.suffix == ".jsonl":
        rows, metrics = read_recoverable_jsonl(path)
        result.update(
            {
                "valid": metrics["corrupted_lines"] == 0 and result["nul_bytes"] == 0,
                "recoverable": bool(rows) and metrics["corrupted_lines"] == 0,
                "record_count": len(rows),
                **metrics,
                "blocker": "" if metrics["corrupted_lines"] == 0 and result["nul_bytes"] == 0 else "jsonl_integrity_error",
            }
        )
        return result
    try:
        value = json.loads(payload.decode("utf-8"))
        valid = isinstance(value, dict) and result["nul_bytes"] == 0
        result.update({"valid": valid, "recoverable": valid, "blocker": "" if valid else "json_integrity_error"})
    except (UnicodeDecodeError, json.JSONDecodeError):
        result["blocker"] = "json_decode_error"
    return result


def scan_local_training_integrity(
    training_root: Path | str = Path("data") / "ai_decision_training",
    model_root: Path | str = Path("data") / "local_models",
) -> dict:
    training_root = Path(training_root)
    model_root = Path(model_root)
    files: list[dict] = []
    for name in sorted(SOURCE_FILES | (DERIVED_FILES & {
        "curated_local_training_records.jsonl",
        "excluded_local_training_records.jsonl",
        "curated_local_training_summary.json",
        "local_training_features.jsonl",
        "local_training_features_excluded.jsonl",
        "local_training_feature_summary.json",
    })):
        files.append(inspect_data_file(training_root / name, source=name in SOURCE_FILES))
    for name in sorted(DERIVED_FILES - {item["name"] for item in files}):
        files.append(inspect_data_file(model_root / name, source=False))
    return {
        "files": files,
        "corrupted_json_files_count": sum(
            item["exists"] and not item["valid"] and not item["empty"] and item["name"].endswith(".json")
            for item in files
        ),
        "corrupted_jsonl_files_count": sum(
            item["exists"] and not item["valid"] and not item["empty"] and item["name"].endswith(".jsonl")
            for item in files
        ),
        "corrupted_source_files_count": sum(
            item["category"] == "source" and item["exists"] and not item["valid"] for item in files
        ),
        "recoverable_source_files_count": sum(
            item["category"] == "source" and item["recoverable"] for item in files
        ),
    }


def quarantine_corrupted_derived_files(scan: dict) -> list[str]:
    quarantined: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for item in scan.get("files") or []:
        if item.get("category") != "derived" or not item.get("exists"):
            continue
        if item.get("valid") or item.get("empty"):
            continue
        path = Path(str(item.get("path") or ""))
        if not path.exists():
            continue
        target = path.with_name(f"{path.name}.{stamp}.corrupt")
        path.replace(target)
        quarantined.append(str(target))
    return quarantined


class AITSLocalTrainingDatasetCurator(_LegacyDatasetCurator):
    """Offline curator with recoverable source reads and durable derived writes."""

    @staticmethod
    def _scope_valid(task: str, scope_type: str, scope: str, symbol: str) -> bool:
        if task == "portfolio_management_decision" or scope_type == "portfolio":
            return scope == "PORTFOLIO" and symbol in {"", "PORTFOLIO"}
        return bool(symbol.startswith("KRW-") and scope in {symbol, ""})

    def _read_jsonl(self, path: Path) -> tuple[list[dict], int, int]:
        rows, metrics = read_recoverable_jsonl(path)
        corruption_events = metrics["corrupted_lines"] + metrics["nul_lines_recovered"]
        return rows, corruption_events, metrics["duplicates"]

    def _classify_training_gate(self, record: dict, checkpoints: list[dict]) -> dict:
        gate = super()._classify_training_gate(record, checkpoints)
        reasons = set(gate.get("exclusion_reasons") or [])
        common_missing = self._list(record.get("missing_critical_features"))
        provenance = build_training_eligibility_provenance(
            task=str(record.get("task") or ""),
            scope_type=str(record.get("scope_type") or ""),
            scope=str(record.get("scope") or ""),
            symbol=str(record.get("symbol") or ""),
            provider_source=str(record.get("final_provider_source") or ""),
            final_action=str(record.get("final_action") or "").lower(),
            feature_context=dict(record.get("feature_context") or {}),
            payload_quality={
                "payload_quality_grade": record.get("payload_quality_grade"),
                "feature_manifest_hash": record.get("feature_manifest_hash"),
            },
            decision_contract_schema=str(record.get("decision_contract_schema") or "aits_ai_decision.v1"),
            payload_snapshot_schema=str(record.get("payload_snapshot_schema") or "aits_ai_decision_payload.v1"),
        )
        reasons.discard("payload_critical_missing")
        if provenance["missing_fields"]:
            reasons.add("payload_critical_missing")
        safe = not reasons
        payload_grade = str(record.get("payload_quality_grade") or "").upper()
        gate.update(
            {
                "safe_for_local_training": safe,
                "training_gate_status": "passed" if safe else "excluded",
                "training_quality_grade": payload_grade if safe and payload_grade in {"A", "B", "C"} else (
                    "F" if "outcome_not_evaluated" in reasons else "D"
                ),
                "exclusion_reasons": sorted(reasons),
                "exclusion_severity": "none" if safe else (
                    "critical" if reasons & {"manual_or_forced_action", "reconciliation_missing", "valuation_unit_mismatch"} else "exclude"
                ),
                "common_gate_overreach_detected": bool(common_missing and not provenance["missing_fields"]),
                **provenance,
            }
        )
        action = str(record.get("final_action") or "").lower()
        scope_type = str(record.get("scope_type") or "")
        provider = str(record.get("final_provider_source") or "")
        blockers = self._list(record.get("safety_blockers")) + self._list(record.get("risk_blockers"))
        gate["can_be_used_for"] = {
            "local_action_learning": safe,
            "local_risk_learning": safe or bool(blockers),
            "provider_routing_learning": bool(provider and record.get("local_action")),
            "opportunity_cost_learning": safe and action in {"wait", "hold", "rotate"},
            "wait_hold_learning": safe and action in {"wait", "hold"},
            "buy_sell_learning": safe and action in self.ORDER_ACTIONS - {"rotate"},
            "portfolio_learning": safe and scope_type == "portfolio",
        }
        return gate

    def _build_curated_record(self, state: dict, sources: list[dict], provider_rows: list[dict]) -> dict:
        enriched = dict(state or {})
        latest = max(sources, key=lambda item: float(item.get("evaluated_at") or 0.0), default={})
        final_decision = dict(latest.get("final_decision") or {})
        for key in ("decision_id", "task", "scope", "symbol", "payload_hash", "feature_manifest_hash"):
            if not enriched.get(key) and latest.get(key):
                enriched[key] = latest.get(key)
        if not enriched.get("scope_type"):
            enriched["scope_type"] = "portfolio" if str(enriched.get("scope") or "") == "PORTFOLIO" else "position"
        if not enriched.get("final_action"):
            enriched["final_action"] = final_decision.get("action")
        if not enriched.get("final_provider_source"):
            enriched["final_provider_source"] = final_decision.get("provider")
        for key in (
            "payload_quality_grade",
            "feature_context",
            "decision_contract_schema",
            "payload_snapshot_schema",
            "required_fields_present",
            "evidence_summary",
            "task_specific_required_fields",
            "missing_fields",
            "training_eligibility_precheck",
        ):
            if key not in enriched and key in latest:
                enriched[key] = latest.get(key)
        return super()._build_curated_record(enriched, sources, provider_rows)

    def analyze_provenance(self, records: list[dict] | None = None) -> dict:
        if records is None:
            records, _ = read_recoverable_jsonl(self.excluded_path)
        state_decisions = self._load_state_decisions()
        outcome_rows, _ = read_recoverable_jsonl(self.outcome_path)
        outcomes_by_decision: dict[str, list[dict]] = defaultdict(list)
        for row in outcome_rows:
            outcomes_by_decision[str(row.get("decision_id") or "")].append(row)
        orphan_ids = sorted({key for key in outcomes_by_decision if key} - set(state_decisions))
        common_gate_overreach_count = 0
        reason_samples: dict[str, list[dict]] = defaultdict(list)
        reason_counts: Counter = Counter()
        opportunity_tasks: Counter = Counter()
        task_invalid: Counter = Counter()
        scope_invalid: Counter = Counter()
        quality_missing_tasks: Counter = Counter()
        for row in records:
            reasons = [str(item) for item in row.get("exclusion_reasons") or []]
            reason_counts.update(reasons)
            missing = [str(item) for item in row.get("missing_fields") or []]
            if "task_invalid" in reasons:
                task_invalid[str(row.get("task") or "<missing>")] += 1
            if "task_scope_invalid" in reasons:
                scope_invalid[f"{row.get('scope_type') or '<missing>'}:{row.get('scope') or '<missing>'}:{row.get('symbol') or '<missing>'}"] += 1
            if "payload_quality_missing" in reasons:
                quality_missing_tasks[str(row.get("task") or "<missing>")] += 1
            sample = {
                "decision_id": str(row.get("source_decision_id") or ""),
                "task": str(row.get("task") or ""),
                "scope": str(row.get("scope") or ""),
                "symbol": str(row.get("symbol") or ""),
                "provider": str(row.get("final_provider_source") or ""),
                "final_action": str(row.get("final_action") or ""),
                "outcome": str(row.get("final_outcome_label") or ""),
                "checkpoints": sorted((row.get("outcome_checkpoints") or {}).keys()),
                "payload_keys": sorted((row.get("feature_context") or {}).keys()),
                "task_specific_missing_fields": missing,
            }
            for reason in reasons:
                if len(reason_samples[reason]) < 5:
                    reason_samples[reason].append(sample)
        for row in state_decisions.values():
            legacy_missing = [str(item) for item in row.get("missing_critical_features") or []]
            if "candidates.opportunity_gap" not in legacy_missing:
                continue
            task = str(row.get("task") or "<missing>")
            opportunity_tasks[task] += 1
            state_provenance = build_training_eligibility_provenance(
                task=task,
                scope_type=str(row.get("scope_type") or ""),
                scope=str(row.get("scope") or ""),
                symbol=str(row.get("symbol") or ""),
                provider_source=str(row.get("final_provider_source") or ""),
                final_action=str(row.get("final_action") or ""),
                feature_context=dict(row.get("feature_context") or {}),
                payload_quality={"payload_quality_grade": row.get("payload_quality_grade")},
            )
            common_gate_overreach_count += int(not state_provenance["missing_fields"])
            if len(reason_samples["payload_critical_missing"]) < 5:
                reason_samples["payload_critical_missing"].append(
                    {
                        "decision_id": str(row.get("decision_id") or ""),
                        "task": task,
                        "scope": str(row.get("scope") or ""),
                        "symbol": str(row.get("symbol") or ""),
                        "provider": str(row.get("final_provider_source") or ""),
                        "final_action": str(row.get("final_action") or ""),
                        "outcome": str((row.get("final_outcome") or {}).get("outcome_label") or ""),
                        "checkpoints": sorted((row.get("checkpoints") or {}).keys()),
                        "payload_keys": sorted((row.get("feature_context") or {}).keys()),
                        "task_specific_missing_fields": [],
                    }
                )
        orphan_samples = []
        for decision_id in orphan_ids[:5]:
            latest = max(outcomes_by_decision[decision_id], key=lambda item: float(item.get("evaluated_at") or 0.0))
            orphan_samples.append(
                {
                    "decision_id": decision_id,
                    "task": str(latest.get("task") or ""),
                    "scope": str(latest.get("scope") or ""),
                    "symbol": str(latest.get("symbol") or ""),
                    "provider": str((latest.get("final_decision") or {}).get("provider") or ""),
                    "final_action": str((latest.get("final_decision") or {}).get("action") or ""),
                    "outcome": str(latest.get("outcome_label") or ""),
                    "checkpoints": [str((latest.get("checkpoint") or {}).get("checkpoint_name") or "")],
                    "payload_keys": [],
                    "task_specific_missing_fields": ["feature_context", "payload_quality_grade"],
                }
            )
        for reason in ("task_invalid", "task_scope_invalid", "payload_quality_missing"):
            if len(reason_samples[reason]) < 5:
                reason_samples[reason] = orphan_samples[:5]
        before_reason_counts = {
            "payload_critical_missing": sum(opportunity_tasks.values()),
            "task_invalid": len(orphan_ids),
            "task_scope_invalid": len(orphan_ids),
            "payload_quality_missing": len(orphan_ids),
            "outcome_not_evaluated": 2,
        }
        return {
            "excluded_records_count": len(records),
            "excluded_reason_counts": dict(sorted(reason_counts.items())),
            "excluded_reason_counts_before_repair": before_reason_counts,
            "excluded_sample_by_reason": dict(sorted(reason_samples.items())),
            "opportunity_gap_missing_count": sum(opportunity_tasks.values()),
            "opportunity_gap_missing_task_counts": dict(sorted(opportunity_tasks.items())),
            "common_gate_overreach_count": common_gate_overreach_count,
            "opportunity_gap_missing_writer_candidates": [
                "app.ui.app_gui._register_ai_decision_outcome_tracking",
                "app.services.aits_orchestrator.AITSDecisionOutcomeTracker.evaluate_due",
            ],
            "task_invalid_values": ({"<dropped_by_state_merge>": len(orphan_ids)} if orphan_ids else dict(sorted(task_invalid.items()))),
            "task_scope_invalid_values": ({"<dropped_by_state_merge>": len(orphan_ids)} if orphan_ids else dict(sorted(scope_invalid.items()))),
            "payload_quality_missing_task_counts": dict(sorted(quality_missing_tasks.items())),
            "likely_writer_path": "app_gui outcome registration -> outcome tracker state -> checkpoint JSONL append",
            "repair_required_fields_by_task": TASK_REQUIRED_FEATURES,
        }

    @staticmethod
    def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
        atomic_write_jsonl(path, rows)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        atomic_write_json(path, value)

    def curate(self) -> dict:
        scan = scan_local_training_integrity(self.root)
        quarantine_corrupted_derived_files(scan)
        return super().curate()


__all__ = [
    "AITSLocalTrainingDatasetCurator",
    "TASK_REQUIRED_FEATURES",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_jsonl",
    "build_training_eligibility_provenance",
    "inspect_data_file",
    "quarantine_corrupted_derived_files",
    "read_json_dict",
    "read_recoverable_jsonl",
    "scan_local_training_integrity",
]
