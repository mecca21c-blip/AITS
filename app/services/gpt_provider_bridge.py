from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.ai_prompt_builder import AIPromptBuilder
from app.services.ai_response_parser import AIResponseParser


class GPTProviderBridge:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.5-instant",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.model = str(model or "gpt-5.5-instant")
        self.timeout = float(timeout or 20.0)
        self.provider = "openai"

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
                raw_text = self._call_openai(prompts)

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
                "[AITS][GPTProviderBridge] shadow_cycle_done"
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
                "[AITS][GPTProviderBridge] shadow_cycle_done"
                f" | dry_run={bool(dry_run)}"
                " | parsed_valid=False"
                " | suggestion=skip"
            )
            return result

    def _build_mock_response(self) -> str:
        response = {
            "suggestion": "confirm",
            "confidence": 0.72,
            "briefing": "Dry-run GPT shadow cycle completed.",
            "evidence": ["dry_run", "context_available"],
            "next_action": "watch",
            "watch_minutes": 30,
            "exit_plan": {"mode": "shadow_only"},
            "prediction": {"direction": "neutral"},
            "pool_action": {"action": "keep", "reason": "dry_run"},
            "state_transition": {"from": "candidate", "to": "watching"},
            "eta": {"mode": "watch", "remaining_minutes": 30},
            "scenario": {"name": "gpt_dry_run", "label_ko": "GPT 모의 실행"},
            "price_plan": {"entry": "wait_for_confirmation"},
            "ai_score": {"total": 72},
            "briefing_detail": {"summary": "Mock response only. No action applied."},
        }
        return json.dumps(response, ensure_ascii=False)

    def _call_openai(self, prompts: Dict[str, str]) -> str:
        # Do not log API keys, prompt bodies, or raw response bodies.
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": prompts.get("system_prompt", "")},
                {"role": "user", "content": prompts.get("user_prompt", "")},
            ],
        )
        return self._extract_response_text(response)

    def _extract_response_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text)

        try:
            choices = getattr(response, "choices", None) or []
            if choices:
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None)
                if content:
                    return str(content)
        except Exception:
            pass
        return str(response or "")

    def _safe_log_info(self, message: str) -> None:
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass
