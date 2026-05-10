from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


FORBIDDEN_KEY_PARTS = (
    "api_key",
    "key",
    "secret",
    "token",
    "access_key",
    "refresh_token",
    "raw_prompt",
    "prompt",
    "raw_response",
    "full_response",
    "response_text",
    "raw_text",
    "authorization",
    "bearer",
)


class AIRuntimeSnapshotSanitizer:
    """Sanitizes snapshot/export data before persistence preparation."""

    def sanitize(self, value):
        if is_dataclass(value):
            return self.sanitize(asdict(value))
        if isinstance(value, dict):
            sanitized: dict = {}
            for key, item in value.items():
                key_text = str(key or "")
                if self._is_forbidden_key(key_text):
                    continue
                sanitized[key_text] = self.sanitize(item)
            return sanitized
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        return value

    def _is_forbidden_key(self, key: str) -> bool:
        key_lower = str(key or "").strip().lower()
        return any(part in key_lower for part in FORBIDDEN_KEY_PARTS)


def build_sample_sanitized_snapshot() -> dict:
    return AIRuntimeSnapshotSanitizer().sanitize(
        {"api_key": "abc", "safe": 1, "nested": {"raw_response": "x"}}
    )


__all__ = [
    "AIRuntimeSnapshotSanitizer",
    "build_sample_sanitized_snapshot",
]
