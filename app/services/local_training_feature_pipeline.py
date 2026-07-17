from __future__ import annotations

from pathlib import Path

from app.services.aits_orchestrator import (
    AITSLocalTrainingFeaturePipeline as _LegacyFeaturePipeline,
)
from app.services.local_training_dataset_curation import (
    atomic_write_json,
    atomic_write_jsonl,
    quarantine_corrupted_derived_files,
    read_governed_dataset,
    read_recoverable_jsonl,
    scan_local_training_integrity,
)


class AITSLocalTrainingFeaturePipeline(_LegacyFeaturePipeline):
    """Offline feature builder with durable derived writes."""

    def _read_jsonl(self) -> tuple[list[dict], int, int]:
        if self.source_path.name == "curated_local_training_records.jsonl":
            rows, metrics = read_governed_dataset("curated_training", self.source_path.parents[1])
        else:
            rows, metrics = read_recoverable_jsonl(self.source_path)
        corruption_events = metrics["corrupted_lines"] + metrics["nul_lines_recovered"]
        return rows, corruption_events, metrics["duplicates"]

    @staticmethod
    def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
        atomic_write_jsonl(path, rows)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        atomic_write_json(path, value)

    def build(self) -> dict:
        scan = scan_local_training_integrity(self.root)
        quarantine_corrupted_derived_files(scan)
        return super().build()


__all__ = ["AITSLocalTrainingFeaturePipeline"]
