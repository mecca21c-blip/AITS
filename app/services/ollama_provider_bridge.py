from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.ai_prompt_builder import AIPromptBuilder
from app.services.ai_response_parser import AIResponseParser


class OllamaProviderBridge:
    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct-q4",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model = str(model or "qwen2.5:7b-instruct-q4")
        self.base_url = str(base_url or "http://127.0.0.1:11434")
        self.timeout = float(timeout or 30.0)
        self.provider = "ollama"

    def run_shadow_cycle(
        self,
        context_dict: dict,
        dry_run: bool = True,
    ) -> dict:
        try:
            context = dict(context_dict or {})
            AIPromptBuilder().build_full_prompt(context)
            if not dry_run:
                return self._not_implemented_result(dry_run=False)

            raw_text = self._build_mock_response()
            parsed = AIResponseParser().parse_json_response(
                raw_text,
                provider=self.provider,
            )
            shadow_record = parsed.to_shadow_record()
            shadow_record_ready = (
                "raw_text" not in shadow_record
                and shadow_record.get("applied") is False
                and shadow_record.get("applied_to_action") is False
            )
            result = {
                "provider": self.provider,
                "model": self.model,
                "dry_run": True,
                "parsed_valid": parsed.valid,
                "shadow_record_ready": shadow_record_ready,
                "suggestion": parsed.suggestion,
                "next_action": parsed.next_action,
                "applied": False,
                "applied_to_action": False,
                "error_type": None,
            }
            self._log_done(
                dry_run=True,
                parsed_valid=parsed.valid,
                suggestion=parsed.suggestion,
            )
            return result
        except Exception as exc:
            result = {
                "provider": self.provider,
                "model": self.model,
                "dry_run": bool(dry_run),
                "parsed_valid": False,
                "shadow_record_ready": False,
                "suggestion": "skip",
                "next_action": "wait",
                "applied": False,
                "applied_to_action": False,
                "error_type": type(exc).__name__,
            }
            self._log_done(
                dry_run=bool(dry_run),
                parsed_valid=False,
                suggestion="skip",
            )
            return result

    def _not_implemented_result(self, dry_run: bool) -> Dict[str, Any]:
        result = {
            "provider": self.provider,
            "model": self.model,
            "dry_run": bool(dry_run),
            "parsed_valid": False,
            "shadow_record_ready": False,
            "suggestion": "skip",
            "next_action": "wait",
            "applied": False,
            "applied_to_action": False,
            "error_type": "not_implemented",
        }
        self._log_done(
            dry_run=bool(dry_run),
            parsed_valid=False,
            suggestion="skip",
        )
        return result

    def _build_mock_response(self) -> str:
        response = {
            "suggestion": "confirm",
            "confidence": 0.72,
            "briefing": "Dry-run Ollama/Qwen shadow cycle completed.",
            "evidence": ["dry_run", "local_provider_skeleton"],
            "next_action": "watch",
            "watch_minutes": 30,
            "exit_plan": {"mode": "shadow_only"},
            "prediction": {"direction": "neutral"},
            "pool_action": {"action": "keep", "reason": "dry_run"},
            "state_transition": {"from": "candidate", "to": "watching"},
            "eta": {"mode": "watch", "remaining_minutes": 30},
            "scenario": {"name": "ollama_dry_run", "label_ko": "Ollama dry run"},
            "price_plan": {"entry": "wait_for_confirmation"},
            "ai_score": {"total": 72},
            "briefing_detail": {"summary": "Mock response only. No action applied."},
        }
        return json.dumps(response, ensure_ascii=False)

    def _log_done(self, dry_run: bool, parsed_valid: bool, suggestion: str) -> None:
        # Do not log prompt bodies, response bodies, keys, secrets, or order data.
        try:
            logging.getLogger("aits").info(
                "[AITS][OllamaProviderBridge] shadow_cycle_done"
                f" | dry_run={bool(dry_run)}"
                f" | parsed_valid={bool(parsed_valid)}"
                f" | suggestion={suggestion}"
            )
        except Exception:
            pass
