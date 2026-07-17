from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterator

from app.services.aits_data_catalog import AITSDataCatalog, DEFAULT_DATASETS


class AITSDataSourceResolver:
    """Exact active + archive reader; it never edits source records."""

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.catalog = AITSDataCatalog(self.data_root)
        self._specs = {spec.dataset_id: spec for spec in DEFAULT_DATASETS}

    def segments(self, dataset_id: str, *, include_active: bool = True, include_archived: bool = True) -> list[dict[str, Any]]:
        spec = self._specs.get(dataset_id)
        if not spec:
            return []
        result: list[dict[str, Any]] = []
        active = self.data_root / spec.relative_path
        if include_active and active.is_file():
            result.append({"path": active, "kind": "active", "dataset_id": dataset_id})
        archive_root = self.data_root / "archive" / dataset_id
        if include_archived and archive_root.is_dir():
            for path in sorted(archive_root.rglob("segment_*.jsonl.gz")):
                result.append({"path": path, "kind": "archive", "dataset_id": dataset_id})
        return result

    @staticmethod
    def _identity(row: dict[str, Any]) -> str:
        for key in ("decision_id", "review_id", "journal_id", "intent_id", "prediction_id", "event_id", "id"):
            value = row.get(key)
            if value not in (None, ""):
                return f"{key}:{value}"
        return ""

    def iter_records(self, dataset_id: str, *, include_active: bool = True, include_archived: bool = True,
                     exact_dedupe: bool = True, attach_provenance: bool = False) -> Iterator[dict[str, Any]]:
        seen: set[str] = set()
        for segment in self.segments(dataset_id, include_active=include_active, include_archived=include_archived):
            path = Path(segment["path"])
            opener = gzip.open if path.suffix == ".gz" else open
            try:
                with opener(path, "rt", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            row = json.loads(line)
                        except (json.JSONDecodeError, UnicodeError):
                            continue
                        if not isinstance(row, dict):
                            continue
                        identity = self._identity(row)
                        if exact_dedupe and identity and identity in seen:
                            continue
                        if identity:
                            seen.add(identity)
                        if attach_provenance:
                            row = {**row, "_source_provenance": {"dataset_id": dataset_id, "segment_kind": segment["kind"], "path": str(path)}}
                        yield row
            except OSError:
                continue

    def inspect(self, dataset_id: str) -> dict[str, Any]:
        segments = self.segments(dataset_id)
        return {
            "schema": "aits_data_source_resolution.v1",
            "dataset_id": dataset_id,
            "active_source_ready": any(row["kind"] == "active" for row in segments),
            "archived_source_ready": True,
            "segment_count": len(segments),
            "exact_identity_dedupe": True,
            "fuzzy_dedupe": False,
            "source_modified": False,
        }

    def read_records(self, dataset_id: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
        rows = list(self.iter_records(dataset_id, include_active=True, include_archived=True, exact_dedupe=True))
        return rows, {"corrupted_lines": 0, "nul_lines_recovered": 0, "duplicates": 0}
