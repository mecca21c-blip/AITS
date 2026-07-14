from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AITSLocalModelRegistry:
    """Atomic registry for offline LOCAL baseline training runs."""

    REGISTRY_SCHEMA = "aits_local_model_registry.v1"

    def __init__(self, root: Path | str = Path("data") / "local_models") -> None:
        self.root = Path(root)
        self.registry_path = self.root / "registry.json"
        self.latest_path = self.root / "latest_model.json"
        self.metrics_status_path = self.root / "latest_training_metrics.json"

    @staticmethod
    def _read_json(path: Path, default: dict) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
            return value if isinstance(value, dict) else default
        except Exception:
            return default

    @staticmethod
    def _write_json_atomic(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    def load_registry(self) -> dict:
        return self._read_json(
            self.registry_path,
            {"registry_schema": self.REGISTRY_SCHEMA, "latest_model_id": "", "models": []},
        )

    def load_latest(self) -> dict:
        return self._read_json(self.latest_path, {})

    def record_training_run(self, metadata: dict, metrics_status: dict) -> dict:
        value = dict(metadata or {})
        value["safe_for_live_decision"] = False
        value["live_decision_enabled"] = False
        registry = self.load_registry()
        models = [item for item in registry.get("models") or [] if isinstance(item, dict)]
        model_id = str(value.get("model_id") or "")
        models = [item for item in models if str(item.get("model_id") or "") != model_id]
        models.append(value)
        models.sort(key=lambda item: str(item.get("created_at") or ""))
        registry = {
            "registry_schema": self.REGISTRY_SCHEMA,
            "latest_model_id": model_id,
            "models": models,
        }
        self._write_json_atomic(self.registry_path, registry)
        self._write_json_atomic(self.latest_path, value)
        self._write_json_atomic(self.metrics_status_path, dict(metrics_status or {}))
        return value

    def latest_shadow_model(self) -> dict:
        latest = self.load_latest()
        if not latest.get("trained"):
            return {}
        if not latest.get("safe_for_shadow_evaluation"):
            return {}
        if latest.get("safe_for_live_decision") or latest.get("live_decision_enabled"):
            return {}
        artifact_path = Path(str(latest.get("artifact_path") or ""))
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path
        try:
            artifact_path.resolve().relative_to(self.root.resolve())
        except (OSError, ValueError):
            return {}
        model_path = artifact_path / "model.pkl"
        if not model_path.exists():
            return {}
        return {**latest, "model_path": str(model_path)}


def load_latest_local_model_metadata(root: Path | str = Path("data") / "local_models") -> dict[str, Any]:
    return AITSLocalModelRegistry(root).load_latest()
