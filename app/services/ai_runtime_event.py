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
class AIRuntimeEvent:
    event_id: str
    session_id: str
    provider: str
    symbol: str
    event_type: str
    severity: str
    title: str
    message: str
    timestamp: str
    source: str
    metadata: dict = field(default_factory=_metadata)


def build_runtime_event(
    session_id: str,
    provider: str,
    symbol: str,
    event_type: str,
    severity: str = "info",
    title: str = "",
    message: str = "",
    source: str = "runtime",
    metadata: dict | None = None,
) -> AIRuntimeEvent:
    safe_metadata = _metadata()
    if isinstance(metadata, dict):
        safe_metadata.update(_sanitize_metadata(metadata))
    return AIRuntimeEvent(
        event_id=f"evt-{uuid4().hex}",
        session_id=str(session_id or ""),
        provider=str(provider or "unknown"),
        symbol=str(symbol or "KRW-BTC"),
        event_type=str(event_type or "runtime_event"),
        severity=str(severity or "info"),
        title=str(title or event_type or "Runtime event"),
        message=str(message or ""),
        timestamp=_now(),
        source=str(source or "runtime"),
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


def build_sample_runtime_event() -> AIRuntimeEvent:
    return build_runtime_event(
        session_id="sample-runtime-session",
        provider="mock",
        symbol="KRW-BTC",
        event_type="one_shot_completed",
        severity="info",
        title="One-shot completed",
        message="mock one-shot completed in research mode",
        source="sample",
    )


__all__ = [
    "AIRuntimeEvent",
    "build_runtime_event",
    "build_sample_runtime_event",
]
