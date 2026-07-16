from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.local_training_dataset_curation import atomic_write_json, read_json_dict


class AITSLocalModelRegistry:
    """Atomic registry for offline LOCAL baseline training runs."""

    REGISTRY_SCHEMA = "aits_local_model_registry.v1"
    LATEST_ATTEMPT_SCHEMA = "aits_local_model_training_attempt.v1"

    def __init__(self, root: Path | str = Path("data") / "local_models") -> None:
        self.root = Path(root)
        self.registry_path = self.root / "registry.json"
        self.latest_path = self.root / "latest_model.json"
        self.latest_attempt_path = self.root / "latest_training_attempt.json"
        self.metrics_status_path = self.root / "latest_training_metrics.json"

    @staticmethod
    def _read_json(path: Path, default: dict) -> dict:
        return read_json_dict(path, default)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        atomic_write_json(path, value)

    def load_registry(self) -> dict:
        return self._read_json(
            self.registry_path,
            {
                "registry_schema": self.REGISTRY_SCHEMA,
                "latest_model_id": "",
                "latest_usable_model_id": "",
                "latest_training_attempt_id": "",
                "latest_usable_multi_head_model_id": "",
                "latest_multi_head_training_attempt_id": "",
                "latest_training_status": "",
                "models": [],
            },
        )

    def load_latest(self) -> dict:
        return self._read_json(self.latest_path, {})

    def load_latest_training_attempt(self) -> dict:
        attempt = self._read_json(self.latest_attempt_path, {})
        if attempt:
            return attempt
        registry = self.load_registry()
        attempt_id = str(registry.get("latest_training_attempt_id") or "")
        if attempt_id:
            return next(
                (
                    dict(item)
                    for item in registry.get("models") or []
                    if isinstance(item, dict) and str(item.get("model_id") or "") == attempt_id
                ),
                {},
            )
        latest = self.load_latest()
        return latest if latest and not latest.get("trained") else {}

    def _artifact_directory(self, entry: dict) -> Path | None:
        raw_path = str(entry.get("artifact_path") or "").strip()
        if not raw_path:
            return None
        artifact_path = Path(raw_path)
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path
        try:
            resolved = artifact_path.resolve()
            resolved.relative_to(self.root.resolve())
        except (OSError, ValueError):
            return None
        return resolved

    @staticmethod
    def _feature_contract_ready(artifact_path: Path) -> bool:
        try:
            feature_manifest = json.loads((artifact_path / "feature_columns.json").read_text(encoding="utf-8"))
            encoding_map = json.loads((artifact_path / "encoding_map.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        feature_columns = feature_manifest.get("feature_columns") if isinstance(feature_manifest, dict) else None
        return bool(isinstance(feature_columns, list) and feature_columns and isinstance(encoding_map, dict))

    def is_usable_model_entry(self, entry: dict) -> bool:
        if not isinstance(entry, dict):
            return False
        if entry.get("trained") is not True or str(entry.get("training_status") or "") != "trained":
            return False
        if not str(entry.get("model_id") or ""):
            return False
        if entry.get("safe_for_live_decision") is not False or entry.get("live_decision_enabled") is not False:
            return False
        if str(entry.get("engine_schema") or "").startswith("aits_local_engine_multi_head"):
            if entry.get("safe_for_live_expansion") is not False:
                return False
        artifact_path = self._artifact_directory(entry)
        return bool(
            artifact_path
            and (artifact_path / "model.pkl").is_file()
            and self._feature_contract_ready(artifact_path)
        )

    def list_usable_models(self, registry: dict | None = None) -> list[dict]:
        source = registry if isinstance(registry, dict) else self.load_registry()
        usable: list[dict] = []
        for item in source.get("models") or []:
            if not self.is_usable_model_entry(item):
                continue
            artifact_path = self._artifact_directory(item)
            usable.append(
                {
                    **dict(item),
                    "model_path": str(artifact_path / "model.pkl"),
                    "feature_schema_compatible": True,
                    "calibration_status": "candidate_only_calibration_may_be_unavailable",
                }
            )
        return sorted(usable, key=lambda item: (float(item.get("created_at") or 0.0), str(item.get("model_id") or "")))

    def resolve_latest_usable_model(self, registry: dict | None = None) -> dict:
        source = registry if isinstance(registry, dict) else self.load_registry()
        usable = self.list_usable_models(source)
        if not usable:
            return {}
        pointer_id = str(source.get("latest_usable_model_id") or source.get("latest_model_id") or "")
        pointed = next((item for item in usable if str(item.get("model_id") or "") == pointer_id), None)
        return dict(pointed or usable[-1])

    def latest_multi_head_candidate(self) -> dict:
        registry = self.load_registry()
        usable = [
            item for item in self.list_usable_models(registry)
            if str(item.get("engine_schema") or "").startswith("aits_local_engine_multi_head")
        ]
        if not usable:
            return {}
        pointer = str(registry.get("latest_usable_multi_head_model_id") or "")
        return dict(next((item for item in usable if str(item.get("model_id") or "") == pointer), usable[-1]))

    def repair_latest_pointers(self) -> dict:
        registry = self.load_registry()
        models = [dict(item) for item in registry.get("models") or [] if isinstance(item, dict)]
        latest_attempt = max(
            models,
            key=lambda item: (float(item.get("created_at") or 0.0), str(item.get("model_id") or "")),
            default={},
        )
        latest_usable = self.resolve_latest_usable_model({**registry, "models": models})
        repaired = {
            "registry_schema": self.REGISTRY_SCHEMA,
            "latest_model_id": str(latest_usable.get("model_id") or ""),
            "latest_usable_model_id": str(latest_usable.get("model_id") or ""),
            "latest_training_attempt_id": str(latest_attempt.get("model_id") or ""),
            "latest_training_status": str(latest_attempt.get("training_status") or ""),
            "latest_usable_multi_head_model_id": str(
                max(
                    (
                        item for item in self.list_usable_models({**registry, "models": models})
                        if str(item.get("engine_schema") or "").startswith("aits_local_engine_multi_head")
                    ),
                    key=lambda item: (float(item.get("created_at") or 0.0), str(item.get("model_id") or "")),
                    default={},
                ).get("model_id") or ""
            ),
            "latest_multi_head_training_attempt_id": str(
                latest_attempt.get("model_id") or ""
            ) if str(latest_attempt.get("engine_schema") or "").startswith("aits_local_engine_multi_head") else str(
                registry.get("latest_multi_head_training_attempt_id") or ""
            ),
            "models": models,
        }
        self._write_json_atomic(self.registry_path, repaired)
        if latest_usable:
            latest_value = {key: value for key, value in latest_usable.items() if key != "model_path"}
            self._write_json_atomic(self.latest_path, latest_value)
        if latest_attempt:
            self._write_json_atomic(
                self.latest_attempt_path,
                {"schema": self.LATEST_ATTEMPT_SCHEMA, **latest_attempt},
            )
        return {
            "latest_training_attempt": latest_attempt,
            "latest_usable_model": latest_usable,
            "usable_model_count": len(self.list_usable_models(repaired)),
        }

    def record_training_run(self, metadata: dict, metrics_status: dict) -> dict:
        value = dict(metadata or {})
        value["safe_for_live_decision"] = False
        value["live_decision_enabled"] = False
        value["safe_for_live_expansion"] = False
        registry = self.load_registry()
        models = [item for item in registry.get("models") or [] if isinstance(item, dict)]
        model_id = str(value.get("model_id") or "")
        models = [item for item in models if str(item.get("model_id") or "") != model_id]
        models.append(value)
        models.sort(key=lambda item: str(item.get("created_at") or ""))
        candidate_registry = {
            "registry_schema": self.REGISTRY_SCHEMA,
            "models": models,
        }
        latest_usable = self.resolve_latest_usable_model(candidate_registry)
        registry = {
            **candidate_registry,
            "latest_model_id": str(latest_usable.get("model_id") or ""),
            "latest_usable_model_id": str(latest_usable.get("model_id") or ""),
            "latest_training_attempt_id": model_id,
            "latest_training_status": str(value.get("training_status") or ""),
            "latest_usable_multi_head_model_id": str(
                latest_usable.get("model_id") or ""
            ) if str(latest_usable.get("engine_schema") or "").startswith("aits_local_engine_multi_head") else str(
                registry.get("latest_usable_multi_head_model_id") or ""
            ),
            "latest_multi_head_training_attempt_id": model_id
            if str(value.get("engine_schema") or "").startswith("aits_local_engine_multi_head")
            else str(registry.get("latest_multi_head_training_attempt_id") or ""),
        }
        self._write_json_atomic(self.registry_path, registry)
        self._write_json_atomic(
            self.latest_attempt_path,
            {"schema": self.LATEST_ATTEMPT_SCHEMA, **value},
        )
        if latest_usable:
            latest_value = {key: item for key, item in latest_usable.items() if key != "model_path"}
            self._write_json_atomic(self.latest_path, latest_value)
        self._write_json_atomic(self.metrics_status_path, dict(metrics_status or {}))
        return value

    def latest_shadow_model(self) -> dict:
        latest = self.latest_model_candidate()
        if not latest:
            return {}
        if not latest.get("safe_for_shadow_evaluation"):
            return {}
        if latest.get("safe_for_live_decision") or latest.get("live_decision_enabled"):
            return {}
        return latest

    def latest_model_candidate(self) -> dict:
        """Return a trained artifact with registry-owned live policy unchanged."""
        return self.resolve_latest_usable_model()


def load_latest_local_model_metadata(root: Path | str = Path("data") / "local_models") -> dict[str, Any]:
    return AITSLocalModelRegistry(root).load_latest()
