from __future__ import annotations

import logging

from app.services.ai_state_machine import AIStateSnapshot


class AIStateRepository:
    """In-memory AI state persistence skeleton. It does not execute orders."""

    def __init__(self) -> None:
        self._state_map: dict[str, AIStateSnapshot] = {}
        self._log = logging.getLogger("aits")

    def set_state(self, snapshot: AIStateSnapshot) -> None:
        symbol = str(getattr(snapshot, "symbol", "") or "").strip()
        if not symbol:
            return
        self._ensure_safe_metadata(snapshot)
        self._state_map[symbol] = snapshot
        self._log.info(
            "[AITS][AIStateRepo] state_saved | symbol=%s | state=%s",
            symbol,
            str(getattr(snapshot, "state", "") or ""),
        )

    def get_state(self, symbol: str) -> AIStateSnapshot | None:
        key = str(symbol or "").strip()
        if not key:
            return None
        return self._state_map.get(key)

    def remove_state(self, symbol: str) -> None:
        key = str(symbol or "").strip()
        if not key:
            return
        self._state_map.pop(key, None)
        self._log.info(
            "[AITS][AIStateRepo] state_removed | symbol=%s",
            key,
        )

    def clear(self) -> None:
        self._state_map.clear()

    def list_states(self) -> list[AIStateSnapshot]:
        return list(self._state_map.values())

    def build_state_summary(self) -> dict:
        summary: dict[str, int] = {"total": len(self._state_map)}
        for snapshot in self._state_map.values():
            state = str(getattr(snapshot, "state", "") or "idle").strip().lower()
            if not state:
                state = "idle"
            summary[state] = int(summary.get(state, 0)) + 1
        self._log.info(
            "[AITS][AIStateRepo] state_summary_built | total=%s",
            summary["total"],
        )
        return summary

    def _ensure_safe_metadata(self, snapshot: AIStateSnapshot) -> None:
        metadata = getattr(snapshot, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                snapshot.metadata = metadata
            except Exception:
                return
        metadata["suggestion_only"] = True
        metadata["applied_to_action"] = False


__all__ = ["AIStateRepository"]
