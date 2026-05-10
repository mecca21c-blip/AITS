from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata() -> dict:
    return {
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "real_order": False,
        "submitted": 0,
        "research_mode": True,
    }


@dataclass
class AIRuntimeIncident:
    incident_id: str
    provider: str
    session_id: str
    incident_type: str
    severity: str
    title: str
    description: str
    detected_at: str
    active: bool
    acknowledged: bool
    metadata: dict = field(default_factory=_metadata)


def build_runtime_incident(
    provider: str,
    session_id: str,
    incident_type: str,
    severity: str,
    title: str,
    description: str,
    metadata: dict | None = None,
) -> AIRuntimeIncident:
    safe_metadata = _metadata()
    if isinstance(metadata, dict):
        safe_metadata.update(_sanitize_metadata(metadata))
    return AIRuntimeIncident(
        incident_id=f"incident-{uuid4().hex}",
        provider=str(provider or "unknown"),
        session_id=str(session_id or ""),
        incident_type=str(incident_type or "runtime_incident"),
        severity=str(severity or "warning"),
        title=str(title or incident_type or "Runtime incident"),
        description=str(description or ""),
        detected_at=_now(),
        active=True,
        acknowledged=False,
        metadata=safe_metadata,
    )


def _sanitize_metadata(metadata: dict) -> dict:
    forbidden = ("key", "secret", "token", "raw", "prompt", "response")
    clean: dict = {}
    for key, value in metadata.items():
        key_text = str(key or "")
        if any(part in key_text.lower() for part in forbidden):
            continue
        clean[key_text] = value
    return clean


def build_sample_runtime_incident() -> AIRuntimeIncident:
    return build_runtime_incident(
        provider="mock",
        session_id="sample-runtime-session",
        incident_type="anomaly_detected",
        severity="warning",
        title="Anomaly detected",
        description="mock anomaly incident for runtime diagnostics",
    )


__all__ = [
    "AIRuntimeIncident",
    "build_runtime_incident",
    "build_sample_runtime_incident",
]
