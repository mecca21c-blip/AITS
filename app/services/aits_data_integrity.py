from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AITSDataIntegrityService:
    """Read-only integrity checks. Source corruption is reported, never rewritten."""

    def inspect_file(self, path: Path | str, *, source: bool = False, deep: bool = False) -> dict[str, Any]:
        target = Path(path)
        result = {
            "schema": "aits_data_integrity_result.v1", "path": str(target), "exists": target.exists(),
            "status": "healthy" if target.exists() else "warning", "nul_bytes": False,
            "partial_last_line": False, "parse_errors": 0, "source": source,
            "source_auto_rewritten": False, "quarantine_available": not source,
        }
        if not target.is_file() or not deep:
            return result
        data = target.read_bytes()
        result["nul_bytes"] = b"\x00" in data
        if target.suffix == ".jsonl":
            result["partial_last_line"] = bool(data and not data.endswith(b"\n"))
            for line in data.splitlines():
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except (json.JSONDecodeError, UnicodeError):
                    result["parse_errors"] += 1
        elif target.suffix == ".json":
            try:
                json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeError):
                result["parse_errors"] += 1
        if result["nul_bytes"] or result["parse_errors"]:
            result["status"] = "corrupt_source" if source else "corrupt_derived"
        elif result["partial_last_line"]:
            result["status"] = "recoverable"
        return result

    @staticmethod
    def recovery_plan(result: dict[str, Any]) -> dict[str, Any]:
        source = bool(result.get("source"))
        return {
            "schema": "aits_data_recovery_plan.v1", "status": result.get("status"),
            "recommended_action": "restore_from_verified_backup" if source else "quarantine_and_regenerate",
            "automatic_rewrite_allowed": False, "user_approval_required": True,
            "critical_state_recovery_ready": True, "orphan_model_detection_ready": True,
            "operation_executed": False,
        }
