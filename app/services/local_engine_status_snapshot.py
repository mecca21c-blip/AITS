from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.services.local_engine_authority_manager import AITSLocalEngineAuthorityManager
from app.services.local_engine_champion_challenger import AITSLocalEngineChampionChallenger
from app.services.local_engine_continuous_learning import AITSLocalEngineContinuousLearning
from app.services.local_model_registry import AITSLocalModelRegistry
from app.services.local_training_dataset_curation import read_json_dict
from app.services.local_engine_level2_evaluator import AITSLocalEngineLevel2Evaluator


LEVEL_NAMES = {0: "외부전용", 1: "학습자", 2: "보조판단", 3: "제한독립", 4: "주판단", 5: "내부운용"}
AUTHORITY_NAMES = {"external_only": "외부 AI 전용", "candidate_only": "후보 판단", "co_pilot": "보조 판단", "task_primary": "일부 작업 우선", "local_primary": "LOCAL 우선", "internal_asset_manager": "내부 운용"}
HEALTH_NAMES = {"stable": "안정", "watch": "관찰 필요", "degraded": "성능 저하", "relearning": "재학습 중", "blocked": "차단됨"}
TASK_NAMES = {
    "position_wait_hold": "보유/대기", "position_buy_add": "매수/추가",
    "position_sell_reduce": "매도/축소", "take_profit_stop_loss": "익절/손절",
    "portfolio_management": "포트폴리오", "rotation": "로테이션",
    "promotion_candidate_selection": "승격 후보 선택", "risk_pre_assessment": "위험 사전평가",
    "eta_redecision": "ETA 재판단", "invalidation_monitoring": "무효화 감시",
    "reason_explanation": "판단 근거 설명",
}


class AITSLocalEngineStatusSnapshot:
    """Small-state snapshot. It never scans JSONL contents on the UI thread."""

    SCHEMA = "aits_local_engine_status_snapshot.v1"

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.local_root = self.data_root / "local_engine"
        self.training_root = self.data_root / "ai_decision_training"
        self.models_root = self.data_root / "local_models"

    @staticmethod
    def _metadata(path: Path, *, record_count: int | None = None, source: bool = False) -> dict[str, Any]:
        try:
            stat = path.stat()
            valid = stat.st_size > 0
            return {
                "name": path.name, "path": str(path), "exists": True,
                "status": "정상" if valid else "비어 있음", "valid": valid,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "size_bytes": stat.st_size, "record_count": record_count,
                "kind": "원본" if source else "파생", "regenerable": not source,
                "blocker": "" if valid else "파일이 비어 있습니다.",
            }
        except OSError:
            return {"name": path.name, "path": str(path), "exists": False, "status": "없음", "valid": False, "modified_at": "", "size_bytes": 0, "record_count": record_count, "kind": "원본" if source else "파생", "regenerable": not source, "blocker": "파일을 찾을 수 없습니다."}

    def build(self, *, provider: str = "", runtime_active: bool = False) -> dict[str, Any]:
        authority_manager = AITSLocalEngineAuthorityManager(self.local_root)
        authority = authority_manager.inspect(persist_initial=False)
        level2 = AITSLocalEngineLevel2Evaluator(
            data_root=self.data_root,
            policy=authority_manager.policy.as_dict(),
        ).evaluate(authority)
        learning = AITSLocalEngineContinuousLearning(self.local_root).inspect()
        models = AITSLocalEngineChampionChallenger().inspect()
        registry = AITSLocalModelRegistry().load_registry()
        champion = AITSLocalModelRegistry().latest_multi_head_candidate()
        attempt = AITSLocalModelRegistry().load_latest_training_attempt()
        challenger = attempt if str(attempt.get("model_id") or "") != str(champion.get("model_id") or "") else {}
        model_comparison = AITSLocalEngineChampionChallenger.compare(champion, challenger) if challenger else {
            "metrics": {}, "comparison_complete": False, "challenger_better": False,
            "activation_performed": False, "user_approval_required": True,
        }
        calibration = read_json_dict(self.models_root / "latest_calibration_summary.json", {})
        curated = read_json_dict(self.training_root / "curated_local_training_summary.json", {})
        features = read_json_dict(self.training_root / "local_training_feature_summary.json", {})
        distillation = read_json_dict(self.training_root / "local_engine_teacher_distillation_summary.json", {})

        task_rows = []
        for key, entry in (authority.get("task_capabilities") or {}).items():
            metrics = dict(entry.get("action_metrics") or {})
            task_rows.append({
                "task_key": key, "task_name": TASK_NAMES.get(key, "기타"),
                "level": int(entry.get("capability_level") or 0),
                "authority": AUTHORITY_NAMES.get(str(entry.get("authority_state") or ""), "확인 필요"),
                "supported_actions": list(entry.get("supported_actions") or []),
                "teacher_samples": int(entry.get("teacher_sample_count") or 0),
                "outcome_samples": int(entry.get("outcome_sample_count") or 0),
                "non_wait_samples": int(entry.get("non_wait_sample_count") or 0),
                "performance": metrics, "health": HEALTH_NAMES.get(str(entry.get("health_status") or ""), "확인 필요"),
                "blocker": str(entry.get("blocker") or ""), "external_ai_required": int(entry.get("capability_level") or 0) < 3,
            })

        counts = {
            "candidate_observations": int(calibration.get("candidate_observation_records_count") or 0),
            "outcome_decisions": int(calibration.get("calibration_source_records_count") or 0),
            "curated_records": int(curated.get("total_curated_records") or 0),
            "excluded_records": int(curated.get("total_excluded_records") or curated.get("excluded_count") or 0),
            "feature_records": int(features.get("safe_for_model_training_count") or features.get("source_record_count") or 0),
            "distillation_records": int(distillation.get("distillation_records_count") or 0),
            "teacher_present": int(distillation.get("teacher_present_count") or 0),
            "teacher_absent": int(distillation.get("teacher_absent_count") or 0),
            "calibration_usable": int(calibration.get("calibration_usable_after_join") or calibration.get("calibration_usable_records_count") or 0),
            "portfolio_teacher": int(distillation.get("portfolio_teacher_record_count") or 0),
        }
        file_specs = [
            (self.local_root / "local_engine_authority_state.json", None, False),
            (self.local_root / "local_engine_authority_history.jsonl", None, False),
            (self.local_root / "local_engine_capability_matrix.json", None, False),
            (self.local_root / "local_engine_health_state.json", None, False),
            (self.local_root / "local_engine_continuous_learning_state.json", None, False),
            (self.local_root / "local_engine_teacher_sync_state.json", None, False),
            (self.local_root / "local_engine_candidate_observations.jsonl", counts["candidate_observations"], True),
            (self.training_root / "outcome_records.jsonl", counts["outcome_decisions"], True),
            (self.training_root / "provider_comparison_outcomes.jsonl", None, True),
            (self.training_root / "curated_local_training_records.jsonl", counts["curated_records"], False),
            (self.training_root / "local_training_features.jsonl", counts["feature_records"], False),
            (self.training_root / "local_engine_teacher_distillation_records.jsonl", counts["distillation_records"], False),
            (self.models_root / "registry.json", len(registry.get("models") or []), False),
            (self.models_root / "latest_model.json", 1, False),
            (self.models_root / "calibration_profile.json", counts["calibration_usable"], False),
            (self.models_root / "latest_calibration_summary.json", 1, False),
        ]
        level = int(authority.get("effective_global_level") or 0)
        health = str(authority.get("health_status") or "")
        authority_code = str(authority.get("global_authority_state") or "")
        snapshot = {
            "schema": self.SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "authority": authority, "learning": learning, "models": models,
            "global_level": int(authority.get("global_level") or 0), "effective_level": level,
            "level_name": LEVEL_NAMES.get(level, "상태 확인 필요"),
            "authority_code": authority_code, "authority_name": AUTHORITY_NAMES.get(authority_code, "상태 확인 필요"),
            "health_code": health, "health_name": HEALTH_NAMES.get(health, "상태 확인 필요"),
            "champion": champion, "challenger": challenger, "model_comparison": model_comparison,
            "task_rows": task_rows,
            "data_counts": counts, "state_files": [
                self._metadata(spec[0], record_count=spec[1], source=spec[2])
                for spec in file_specs
            ],
            "provider": provider, "teacher_sync_required": bool(authority.get("teacher_sync_required")),
            "maintenance_enabled": not runtime_active, "runtime_active": runtime_active,
            "promotion_candidate": authority.get("promotion_candidate"),
            "level2_readiness": level2,
            "rollback_available": bool(authority.get("rollback_available")),
            "raw_jsonl_scanned": False, "low_resource_mode_integrated": True,
        }
        from app.services.local_engine_user_view_model import build_local_engine_user_view_model
        snapshot["user_view"] = build_local_engine_user_view_model(snapshot)
        return snapshot

    @staticmethod
    def recent_history(path: Path | str = Path("data") / "local_engine" / "local_engine_authority_history.jsonl", limit: int = 20) -> list[dict[str, Any]]:
        """Bounded audit view; never returns raw source text."""
        try:
            with Path(path).open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 131_072))
                lines = handle.read(131_072).decode("utf-8", errors="replace").splitlines()[-max(1, limit):]
        except OSError:
            return []
        result = []
        for line in lines:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            result.append({key: row.get(key) for key in ("timestamp", "event", "global_level_before", "global_level_after", "model_id", "reason_codes", "user_approved")})
        return result
