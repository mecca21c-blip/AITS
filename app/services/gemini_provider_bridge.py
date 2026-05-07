from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.ai_prompt_builder import AIPromptBuilder
from app.services.ai_response_parser import AIResponseParser


class GeminiProviderBridge:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.model = str(model or "gemini-2.5-flash")
        self.timeout = float(timeout or 20.0)
        self.provider = "gemini"

    def run_shadow_cycle(
        self,
        context_dict: dict,
        dry_run: bool = True,
    ) -> dict:
        try:
            context = dict(context_dict or {})
            prompts = AIPromptBuilder().build_full_prompt(context)
            if dry_run:
                raw_text = self._build_mock_response()
            else:
                raw_text = self._call_gemini(prompts)

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
                "dry_run": bool(dry_run),
                "parsed_valid": parsed.valid,
                "shadow_record_ready": shadow_record_ready,
                "suggestion": parsed.suggestion,
                "next_action": parsed.next_action,
                "applied": False,
                "applied_to_action": False,
            }
            self._safe_log_info(
                "[AITS][GeminiProviderBridge] shadow_cycle_done"
                f" | dry_run={bool(dry_run)}"
                f" | parsed_valid={parsed.valid}"
                f" | suggestion={parsed.suggestion}"
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
            self._safe_log_info(
                "[AITS][GeminiProviderBridge] shadow_cycle_done"
                f" | dry_run={bool(dry_run)}"
                " | parsed_valid=False"
                " | suggestion=skip"
            )
            return result

    def _build_mock_response(self) -> str:
        response = {
            "suggestion": "confirm",
            "confidence": 0.72,
            "briefing": "Dry-run Gemini shadow cycle completed.",
            "evidence": ["dry_run", "context_available"],
            "next_action": "watch",
            "watch_minutes": 30,
            "exit_plan": {"mode": "shadow_only"},
            "prediction": {"direction": "neutral"},
            "pool_action": {"action": "keep", "reason": "dry_run"},
            "state_transition": {"from": "candidate", "to": "watching"},
            "eta": {"mode": "watch", "remaining_minutes": 30},
            "scenario": {"name": "gemini_dry_run", "label_ko": "Gemini dry run"},
            "price_plan": {"entry": "wait_for_confirmation"},
            "ai_score": {"total": 72},
            "briefing_detail": {"summary": "Mock response only. No action applied."},
        }
        return json.dumps(response, ensure_ascii=False)

    def _call_gemini(self, prompts: Dict[str, str]) -> str:
        # Do not log API keys, prompt bodies, or raw response bodies.
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        prompt = "\n\n".join(
            [
                prompts.get("system_prompt", ""),
                prompts.get("user_prompt", ""),
            ]
        )
        response = model.generate_content(
            prompt,
            request_options={"timeout": self.timeout},
        )
        return self._extract_response_text(response)

    def _extract_response_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if text:
            return str(text)

        try:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None) or []
                if parts:
                    part_text = getattr(parts[0], "text", None)
                    if part_text:
                        return str(part_text)
        except Exception:
            pass
        return str(response or "")

    def _safe_log_info(self, message: str) -> None:
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass
