from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


FORBIDDEN_KEY_PARTS = ("api_key", "secret", "token", "raw_response", "full_response", "raw_text")


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
        "memory_only": True,
    }


@dataclass
class AIRuntimeMemoryItem:
    session_id: str
    key: str
    value: dict
    updated_at: str
    metadata: dict = field(default_factory=_metadata)


class AIRuntimeMemory:
    """Session-scoped memory for sanitized runtime context only."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, AIRuntimeMemoryItem]] = {}

    def set_item(
        self,
        session_id: str,
        key: str,
        value: dict,
    ) -> AIRuntimeMemoryItem | None:
        safe_key = str(key or "").strip()
        if not safe_key or self._is_forbidden_key(safe_key):
            return None
        item = AIRuntimeMemoryItem(
            session_id=str(session_id or ""),
            key=safe_key,
            value=self._sanitize_value(value),
            updated_at=_now(),
            metadata=_metadata(),
        )
        self._items.setdefault(item.session_id, {})[safe_key] = item
        return item

    def get_item(self, session_id: str, key: str) -> AIRuntimeMemoryItem | None:
        return self._items.get(str(session_id or ""), {}).get(str(key or ""))

    def list_items(self, session_id: str) -> list[AIRuntimeMemoryItem]:
        return list(self._items.get(str(session_id or ""), {}).values())

    def clear_session(self, session_id: str) -> None:
        self._items.pop(str(session_id or ""), None)

    def build_summary(self) -> dict:
        total_items = sum(len(items) for items in self._items.values())
        keys: dict[str, int] = {}
        for items in self._items.values():
            for key in items:
                keys[key] = keys.get(key, 0) + 1
        return {
            "total_sessions": len(self._items),
            "total_items": total_items,
            "keys": keys,
            "shadow_only": True,
            "real_order": False,
            "submitted": 0,
            "research_mode": True,
        }

    def _sanitize_value(self, value: Any) -> dict:
        if not isinstance(value, dict):
            return {"value": value}
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key or "")
            if self._is_forbidden_key(key_text):
                continue
            if isinstance(item, dict):
                sanitized[key_text] = self._sanitize_value(item)
            elif isinstance(item, list):
                sanitized[key_text] = [
                    self._sanitize_value(entry) if isinstance(entry, dict) else entry
                    for entry in item
                ]
            else:
                sanitized[key_text] = item
        return sanitized

    def _is_forbidden_key(self, key: str) -> bool:
        key_lower = str(key or "").strip().lower()
        return any(part in key_lower for part in FORBIDDEN_KEY_PARTS)


def build_sample_runtime_memory_summary() -> dict:
    memory = AIRuntimeMemory()
    memory.set_item("sample-runtime-session", "last_quality_score", {"score": 0.82})
    return memory.build_summary()


__all__ = [
    "AIRuntimeMemory",
    "AIRuntimeMemoryItem",
    "build_sample_runtime_memory_summary",
]
