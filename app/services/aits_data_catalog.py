from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


CATALOG_SCHEMA = "aits_data_asset_catalog_entry.v1"
POLICY_SCHEMA = "aits_data_governance_policy.v1"


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    display_name_ko: str
    category: str
    relative_path: str
    source_or_derived: str
    schema: str = ""
    backup_required: bool = False
    regeneration_supported: bool = False
    protected: bool = False
    training_use: bool = False
    secret: bool = False


DEFAULT_DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec("candidate_observations", "LOCAL 후보 판단 기록", "immutable_source", "local_engine/local_engine_candidate_observations.jsonl", "source", backup_required=True, training_use=True),
    DatasetSpec("outcomes", "판단 결과 기록", "immutable_source", "ai_decision_training/outcome_records.jsonl", "source", backup_required=True, training_use=True),
    DatasetSpec("provider_comparisons", "교사 AI 비교 기록", "immutable_source", "ai_decision_training/provider_comparison_outcomes.jsonl", "source", backup_required=True, training_use=True),
    DatasetSpec("intent_history", "AI 관찰 계획 이력", "immutable_source", "ai_intent/intent_history.jsonl", "source", backup_required=True, training_use=True),
    DatasetSpec("authority_history", "권한 변경 이력", "immutable_source", "local_engine/local_engine_authority_history.jsonl", "source", backup_required=True),
    DatasetSpec("authority_state", "현재 LOCAL 권한", "critical_state", "local_engine/local_engine_authority_state.json", "state", backup_required=True, protected=True),
    DatasetSpec("capability_matrix", "기능별 학습 상태", "critical_state", "local_engine/local_engine_capability_matrix.json", "state", backup_required=True, protected=True),
    DatasetSpec("active_intents", "현재 AI 관찰 계획", "critical_state", "ai_intent/active_intents.json", "state", backup_required=True, protected=True),
    DatasetSpec("model_registry", "LOCAL 모델 등록부", "critical_state", "local_models/registry.json", "state", backup_required=True, protected=True),
    DatasetSpec("curated_training", "정리된 학습 데이터", "derived_learning", "ai_decision_training/curated_local_training_records.jsonl", "derived", regeneration_supported=True, training_use=True),
    DatasetSpec("training_features", "학습용 특징 데이터", "derived_learning", "ai_decision_training/local_training_features.jsonl", "derived", regeneration_supported=True, training_use=True),
    DatasetSpec("teacher_distillation", "교사 AI 학습 데이터", "derived_learning", "ai_decision_training/local_engine_teacher_distillation_records.jsonl", "derived", regeneration_supported=True, training_use=True),
    DatasetSpec("ai_reviews", "AI 복기", "derived_learning", "ai_review/ai_review_records.jsonl", "derived", regeneration_supported=True, training_use=True),
    DatasetSpec("learning_journal", "학습 일지", "derived_learning", "learning_journal/learning_journal.jsonl", "derived", regeneration_supported=True),
    DatasetSpec("local_models", "LOCAL 모델 파일", "model_artifact", "local_models", "artifact", backup_required=True, protected=True),
    DatasetSpec("runtime_log", "앱 운영 로그", "operational_log", "logs/aits.log", "log"),
    DatasetSpec("runtime_reports", "점검 보고서", "operational_log", "runtime_smoke", "report", regeneration_supported=True),
    DatasetSpec("prefs_secret", "보안 설정", "secret_excluded", "prefs.json", "excluded", protected=True, secret=True),
    DatasetSpec("encrypted_secret", "암호화 키", "secret_excluded", "secret.bin", "excluded", protected=True, secret=True),
    DatasetSpec("api_secrets", "API 인증 정보", "secret_excluded", "secrets.json", "excluded", protected=True, secret=True),
)


def default_governance_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "policy_version": 1,
        "enabled": True,
        "source_auto_delete_enabled": False,
        "source_archive_enabled": True,
        "source_archive_after_days": 90,
        "derived_rebuild_allowed": True,
        "derived_auto_prune_enabled": False,
        "heavy_governance_operations_off_only": True,
        "secret_exclusion_required": True,
        "allow_full_reset": False,
    }


class AITSDataCatalog:
    """Read-only metadata catalog. Persisting a cache is always explicit."""

    def __init__(self, data_root: Path | str = Path("data"), specs: Iterable[DatasetSpec] = DEFAULT_DATASETS) -> None:
        self.data_root = Path(data_root)
        self.specs = tuple(specs)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _record_count(path: Path) -> int | None:
        if path.suffix != ".jsonl":
            return 1 if path.is_file() else None
        with path.open("rb") as handle:
            return sum(1 for line in handle if line.strip())

    def inspect(self, *, deep: bool = False) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for spec in self.specs:
            path = self.data_root / spec.relative_path
            exists = path.exists()
            stat = path.stat() if exists else None
            valid = exists and (path.is_dir() or bool(stat and stat.st_size >= 0))
            entry = {
                **asdict(spec),
                "source_schema": spec.schema,
                "schema": CATALOG_SCHEMA,
                "path": str(path),
                "exists": exists,
                "valid": valid,
                "corrupt": False,
                "read_only": spec.source_or_derived in {"source", "excluded"},
                "record_count": None if spec.secret or not deep or not exists or path.is_dir() else self._record_count(path),
                "size_bytes": int(stat.st_size) if stat and path.is_file() else 0,
                "last_modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else "",
                "checksum": "" if spec.secret or not deep or not exists or path.is_dir() else self._sha256(path),
                "active_segment": exists,
                "archive_segment_count": 0,
                "archived_record_count": 0,
                "last_backup_at": "",
                "retention_policy_ref": "data_governance_policy",
                "blocker": "" if exists else "dataset_not_created_yet",
            }
            entries.append(entry)
        counts = {category: sum(1 for row in entries if row["category"] == category) for category in (
            "immutable_source", "critical_state", "derived_learning", "model_artifact", "operational_log", "secret_excluded"
        )}
        return {
            "schema": "aits_data_catalog_summary.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_count": len(entries),
            "entries": entries,
            "category_counts": counts,
            "corrupt_count": sum(1 for row in entries if row["corrupt"]),
            "deep_scan_performed": deep,
            "source_records_modified": False,
        }

    def write_cache(self, snapshot: dict[str, Any], *, explicit: bool = False) -> Path:
        if not explicit:
            raise PermissionError("catalog_cache_write_requires_explicit_request")
        target = self.data_root / "governance" / "data_catalog.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        return target
