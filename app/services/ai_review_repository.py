from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable


class AITSDerivedJsonRepository:
    """Atomic derived-data repository with offset indexes and corrupt-line accounting."""

    def __init__(self, path: Path | str, *, id_field: str, schema: str) -> None:
        self.path = Path(path)
        self.id_field = id_field
        self.schema = schema
        self.index_path = self.path.with_suffix(self.path.suffix + ".index.json")

    @staticmethod
    def load_json(path: Path | str, default: Any) -> Any:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            return value
        except (OSError, ValueError, TypeError):
            return default

    @staticmethod
    def atomic_write_json(path: Path | str, value: Any) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def read_jsonl(path: Path | str) -> tuple[list[dict[str, Any]], dict[str, int]]:
        records: list[dict[str, Any]] = []
        stats = {"records": 0, "corrupt": 0, "nul": 0, "partial": 0}
        source = Path(path)
        try:
            with source.open("rb") as handle:
                for raw in handle:
                    if not raw.strip():
                        continue
                    if b"\x00" in raw:
                        stats["corrupt"] += 1
                        stats["nul"] += 1
                        continue
                    try:
                        value = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError, TypeError):
                        stats["corrupt"] += 1
                        if not raw.endswith((b"\n", b"\r")):
                            stats["partial"] += 1
                        continue
                    if not isinstance(value, dict):
                        stats["corrupt"] += 1
                        continue
                    records.append(value)
                    stats["records"] += 1
        except OSError:
            return [], stats
        return records, stats

    def write_records(self, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        latest: dict[str, dict[str, Any]] = {}
        for row in records:
            key = str(row.get(self.id_field) or "")
            if key:
                latest[key] = dict(row)
        ordered = sorted(latest.values(), key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        offsets: list[dict[str, Any]] = []
        try:
            with os.fdopen(fd, "wb") as handle:
                for row in ordered:
                    offset = handle.tell()
                    raw = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                    handle.write(raw)
                    offsets.append({
                        self.id_field: row.get(self.id_field),
                        "offset": offset,
                        "length": len(raw),
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                    })
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
        self.atomic_write_json(self.index_path, {
            "schema": f"{self.schema}.index.v1",
            "record_count": len(offsets),
            "records": offsets,
        })
        return {"record_count": len(offsets), "deduplicated": True, "index_ready": True}

    def read_page(self, *, offset: int = 0, limit: int = 50, newest_first: bool = True) -> list[dict[str, Any]]:
        index = self.load_json(self.index_path, {})
        entries = list(index.get("records") or [])
        if newest_first:
            entries.reverse()
        selected = entries[max(0, offset):max(0, offset) + max(1, min(limit, 200))]
        result: list[dict[str, Any]] = []
        try:
            with self.path.open("rb") as handle:
                for entry in selected:
                    handle.seek(int(entry.get("offset") or 0))
                    raw = handle.read(int(entry.get("length") or 0))
                    if b"\x00" in raw:
                        continue
                    try:
                        value = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError, TypeError):
                        continue
                    if isinstance(value, dict):
                        result.append(value)
        except OSError:
            return []
        return result

    def get(self, record_id: str) -> dict[str, Any]:
        index = self.load_json(self.index_path, {})
        entry = next(
            (row for row in index.get("records") or [] if str(row.get(self.id_field) or "") == str(record_id)),
            None,
        )
        if not entry:
            return {}
        try:
            with self.path.open("rb") as handle:
                handle.seek(int(entry.get("offset") or 0))
                raw = handle.read(int(entry.get("length") or 0))
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeDecodeError, ValueError, TypeError):
            return {}


class AITSAIReviewRepository(AITSDerivedJsonRepository):
    SCHEMA = "aits_ai_review_record.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        super().__init__(Path(data_root) / "ai_review" / "ai_review_records.jsonl", id_field="review_id", schema=self.SCHEMA)
        self.summary_path = self.path.parent / "ai_review_summary.json"
        self.state_path = self.path.parent / "ai_review_state.json"


class AITSLearningJournalRepository(AITSDerivedJsonRepository):
    SCHEMA = "aits_ai_learning_journal_entry.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        super().__init__(Path(data_root) / "learning_journal" / "learning_journal.jsonl", id_field="journal_id", schema=self.SCHEMA)
        self.summary_path = self.path.parent / "learning_journal_summary.json"
        self.patterns_path = self.path.parent / "repeated_patterns.json"
        self.suggestions_path = self.path.parent / "policy_suggestions.jsonl"
        self.suggestion_index_path = self.suggestions_path.with_suffix(self.suggestions_path.suffix + ".index.json")
        self.suggestion_summary_path = self.path.parent / "policy_suggestion_summary.json"
