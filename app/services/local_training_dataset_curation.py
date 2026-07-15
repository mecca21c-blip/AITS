from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
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
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_jsonl",
    "inspect_data_file",
    "quarantine_corrupted_derived_files",
    "read_json_dict",
    "read_recoverable_jsonl",
    "scan_local_training_integrity",
]
