from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

from app.services.ai_review_repository import AITSDerivedJsonRepository


class AITSAIIntentRepository:
    """Derived, atomic canonical Intent repository; source records are untouched."""

    def __init__(self, root: Path | str = "data/ai_intent") -> None:
        self.root = Path(root)
        self.active_path = self.root / "active_intents.json"
        self.history_path = self.root / "intent_history.jsonl"
        self.summary_path = self.root / "intent_summary.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def scope_key(intent: dict[str, Any]) -> str:
        return "|".join((str(intent.get("task") or ""), str(intent.get("scope") or ""), str(intent.get("symbol") or "")))

    def inspect(self) -> dict[str, Any]:
        active = AITSDerivedJsonRepository.load_json(self.active_path, {})
        summary = AITSDerivedJsonRepository.load_json(self.summary_path, {})
        return {
            "schema": "aits_ai_intent_repository_snapshot.v1",
            "active_intents": dict(active.get("active_intents") or {}) if isinstance(active, dict) else {},
            "summary": summary if isinstance(summary, dict) else {},
            "persistence_performed": False,
        }

    def find_active(self, *, task: str = "", scope: str = "", symbol: str = "") -> dict[str, Any]:
        snapshot = self.inspect()
        rows = list((snapshot.get("active_intents") or {}).values())
        task, scope, symbol = str(task or ""), str(scope or ""), str(symbol or "").upper()
        matches = [
            dict(row) for row in rows if isinstance(row, dict)
            and (not task or str(row.get("task") or "") == task)
            and (not scope or str(row.get("scope") or "") == scope)
            and (not symbol or str(row.get("symbol") or "").upper() == symbol)
        ]
        if not matches and symbol:
            matches = [dict(row) for row in rows if isinstance(row, dict) and str(row.get("symbol") or "").upper() == symbol]
        return max(matches, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), default={})

    def _append_history(self, event: dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _load_active_for_write(self) -> dict[str, Any]:
        if not self.active_path.exists():
            return {}
        try:
            raw = self.active_path.read_bytes()
            if b"\x00" in raw:
                raise ValueError("nul_byte_detected")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("active_intent_root_invalid")
            return value
        except (OSError, UnicodeDecodeError, ValueError, TypeError):
            quarantine = self.active_path.with_suffix(self.active_path.suffix + f".corrupt.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
            try:
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(self.active_path), str(quarantine))
            except OSError:
                pass
            return {}

    def upsert_active(self, intent: dict[str, Any], *, event_type: str = "intent_activated") -> dict[str, Any]:
        state = self._load_active_for_write()
        active = dict(state.get("active_intents") or {}) if isinstance(state, dict) else {}
        key = self.scope_key(intent)
        previous = active.get(key) if isinstance(active.get(key), dict) else {}
        if previous and str(previous.get("intent_id")) == str(intent.get("intent_id")) and int(previous.get("revision") or 0) >= int(intent.get("revision") or 0):
            return {"written": False, "deduplicated": True, "intent": previous}
        active[key] = dict(intent)
        AITSDerivedJsonRepository.atomic_write_json(self.active_path, {
            "schema": "aits_ai_active_intents.v1", "updated_at": self._now(), "active_intents": active,
        })
        event = {
            "schema": "aits_ai_intent_history_event.v1", "event": event_type,
            "created_at": self._now(), "intent_id": intent.get("intent_id"),
            "decision_id": intent.get("decision_id"), "revision": intent.get("revision"),
            "previous_intent_id": previous.get("intent_id"), "status": intent.get("status"),
            "task": intent.get("task"), "scope": intent.get("scope"), "symbol": intent.get("symbol"),
        }
        self._append_history(event)
        AITSDerivedJsonRepository.atomic_write_json(self.summary_path, {
            "schema": "aits_ai_intent_summary.v1", "updated_at": self._now(),
            "active_count": len(active), "last_event": event,
        })
        return {"written": True, "deduplicated": False, "intent": dict(intent)}

    def transition(self, intent_id: str, status: str, *, reason: str = "") -> dict[str, Any]:
        state = self._load_active_for_write()
        active = dict(state.get("active_intents") or {}) if isinstance(state, dict) else {}
        matched_key = next((key for key, row in active.items() if str((row or {}).get("intent_id")) == str(intent_id)), "")
        if not matched_key:
            return {"written": False, "blocker": "intent_not_found"}
        intent = dict(active[matched_key])
        intent.update({"status": status, "updated_at": self._now(), "lifecycle_reason": str(reason or "")})
        terminal = status in {"satisfied", "invalidated", "expired", "completed", "cancelled", "blocked", "inconclusive"}
        if terminal:
            active.pop(matched_key, None)
        else:
            active[matched_key] = intent
        AITSDerivedJsonRepository.atomic_write_json(self.active_path, {
            "schema": "aits_ai_active_intents.v1", "updated_at": self._now(), "active_intents": active,
        })
        self._append_history({
            "schema": "aits_ai_intent_history_event.v1", "event": f"intent_{status}",
            "created_at": self._now(), "intent_id": intent_id, "decision_id": intent.get("decision_id"),
            "revision": intent.get("revision"), "status": status, "reason": str(reason or ""),
            "task": intent.get("task"), "scope": intent.get("scope"), "symbol": intent.get("symbol"),
        })
        return {"written": True, "intent": intent}
