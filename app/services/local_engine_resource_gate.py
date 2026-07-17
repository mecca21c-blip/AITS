from __future__ import annotations

from pathlib import Path
from typing import Any


class AITSLocalEngineResourceGate:
    """Deployment/resource suitability gate for future elevated LOCAL authority."""

    SCHEMA = "aits_local_engine_resource_gate.v1"

    @staticmethod
    def evaluate(model: dict[str, Any], *, policy: dict[str, Any], latency_ms: float | None = None,
                 peak_memory_mb: float | None = None) -> dict[str, Any]:
        limits = dict(policy.get("deployment_resource_thresholds") or {})
        raw_path = Path(str(model.get("artifact_path") or "")) if model.get("artifact_path") else None
        size = 0
        if raw_path and raw_path.exists():
            try:
                size = sum(path.stat().st_size for path in raw_path.rglob("*") if path.is_file())
            except OSError:
                size = 0
        size_mb = size / (1024 * 1024)
        cpu_only = not bool(model.get("gpu_required"))
        external_runtime = bool(model.get("external_runtime_required"))
        package_compatible = bool(model) and bool(model.get("feature_schema_compatible", True))
        blockers: list[str] = []
        if not model:
            blockers.append("usable_model_missing")
        if not cpu_only:
            blockers.append("gpu_required")
        if external_runtime:
            blockers.append("external_runtime_required")
        if size_mb > float(limits.get("maximum_artifact_size_mb") or 512.0):
            blockers.append("artifact_size_limit_exceeded")
        if latency_ms is not None and latency_ms > float(limits.get("maximum_inference_latency_ms") or 500.0):
            blockers.append("inference_latency_limit_exceeded")
        if peak_memory_mb is not None and peak_memory_mb > float(limits.get("maximum_peak_memory_mb") or 1024.0):
            blockers.append("peak_memory_limit_exceeded")
        if not package_compatible:
            blockers.append("package_or_schema_incompatible")
        return {
            "schema": AITSLocalEngineResourceGate.SCHEMA,
            "artifact_size_mb": round(size_mb, 4), "inference_latency_ms": latency_ms,
            "peak_memory_mb": peak_memory_mb, "cpu_only_supported": cpu_only,
            "gpu_required": not cpu_only, "external_runtime_required": external_runtime,
            "package_compatible": package_compatible, "schema_compatible": package_compatible,
            "resource_health_status": "ready" if not blockers else "blocked",
            "low_resource_compatible": not blockers, "blockers": blockers,
        }
