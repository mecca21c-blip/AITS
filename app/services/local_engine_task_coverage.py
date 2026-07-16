from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any

from app.services.local_training_dataset_curation import read_recoverable_jsonl


TASK_COVERAGE_SCHEMA = "aits_local_engine_task_coverage.v1"


class AITSLocalEngineTaskCoverage:
    """Record factual candidate coverage for every provider decision.

    Coverage records are observational only. They never alter provider routing,
    final actions, orders, capability levels, or model registry pointers.
    """

    _lock = threading.Lock()

    def __init__(self, root: Path | str = Path("data") / "local_engine") -> None:
        self.root = Path(root)
        self.path = self.root / "local_engine_task_coverage.jsonl"

    @staticmethod
    def _stable_id(record: dict[str, Any]) -> str:
        identity = {
            "decision_id": str(record.get("decision_id") or ""),
            "payload_hash": str(record.get("payload_hash") or ""),
            "source_task": str(record.get("source_task") or record.get("task") or ""),
            "scope": str(record.get("scope") or ""),
        }
        return "local-coverage-" + hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]

    @staticmethod
    def _validation_blocker(record: dict[str, Any]) -> str:
        if record.get("schema") != TASK_COVERAGE_SCHEMA:
            return "coverage_schema_invalid"
        if not str(record.get("coverage_id") or ""):
            return "coverage_id_missing"
        if not str(record.get("source_task") or ""):
            return "coverage_task_missing"
        if record.get("candidate_only") is not True:
            return "candidate_only_contract_broken"
        if record.get("applied_to_final_action") is not False:
            return "candidate_applied_to_final_action"
        if record.get("fake_candidate") is not False:
            return "fake_candidate_detected"
        return ""

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        value = dict(record or {})
        value.setdefault("schema", TASK_COVERAGE_SCHEMA)
        value.setdefault("created_at", datetime.now().astimezone().isoformat())
        value.setdefault("coverage_id", self._stable_id(value))
        blocker = self._validation_blocker(value)
        if blocker:
            raise ValueError(blocker)
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, default=str) + "\n").encode("utf-8")
        json.loads(payload.decode("utf-8"))
        with self._lock:
            existing, _metrics = read_recoverable_jsonl(self.path)
            if any(str(row.get("coverage_id") or "") == value["coverage_id"] for row in existing):
                return value
            self.root.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        return value

    def read(self) -> tuple[list[dict], dict[str, int]]:
        return read_recoverable_jsonl(self.path)

    def summarize(self) -> dict[str, Any]:
        rows, metrics = self.read()
        unique = {str(row.get("coverage_id") or ""): row for row in rows if row.get("coverage_id")}
        values = list(unique.values())
        eligible = [row for row in values if row.get("local_candidate_eligible")]
        attempted = [row for row in values if row.get("local_candidate_attempted")]
        success = [row for row in values if row.get("local_candidate_available")]
        recorded = [row for row in values if row.get("local_candidate_recorded")]
        by_task: dict[str, Counter] = defaultdict(Counter)
        blockers: dict[str, Counter] = defaultdict(Counter)
        for row in values:
            task = str(row.get("source_task") or row.get("task") or "unknown")
            by_task[task]["total"] += 1
            for field in ("local_candidate_eligible", "local_candidate_attempted", "local_candidate_available", "local_candidate_recorded"):
                if row.get(field):
                    by_task[task][field] += 1
            blocker = str(row.get("candidate_blocker") or "")
            if blocker:
                blockers[task][blocker] += 1
        return {
            "source_exists": self.path.exists(),
            "total_ai_decision_count": len(values),
            "local_candidate_eligible_count": len(eligible),
            "local_candidate_attempt_count": len(attempted),
            "local_candidate_success_count": len(success),
            "local_candidate_recorded_count": len(recorded),
            "local_candidate_coverage_rate": round(len(recorded) / len(eligible), 6) if eligible else 0.0,
            "local_candidate_success_rate": round(len(success) / len(attempted), 6) if attempted else 0.0,
            "coverage_by_task": {key: dict(value) for key, value in sorted(by_task.items())},
            "blocker_counts_by_task": {key: dict(value) for key, value in sorted(blockers.items())},
            "eligible_but_not_attempted_count": sum(
                bool(row.get("local_candidate_eligible")) and not bool(row.get("local_candidate_attempted"))
                for row in values
            ),
            "corrupt_count": int(metrics.get("corrupt_count") or metrics.get("bad_count") or 0),
        }


__all__ = ["AITSLocalEngineTaskCoverage", "TASK_COVERAGE_SCHEMA"]
