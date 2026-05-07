from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.ai_context_builder import build_sample_context_pack
from app.services.ai_prompt_builder import AIPromptBuilder
from app.services.ai_response_parser import AIResponseParser


class AIProviderMockBridge:
    def run_mock_cycle(self, provider: str = "mock") -> Dict[str, Any]:
        provider_name = str(provider or "mock")
        context = build_sample_context_pack()
        context_dict = context.to_compact_dict()
        prompts = AIPromptBuilder().build_full_prompt(context_dict)

        # Mock-only response. Do not log raw prompts, raw responses, keys, or secrets.
        mock_response = {
            "suggestion": "confirm",
            "confidence": 0.72,
            "briefing": "Mock provider suggests continued observation.",
            "evidence": ["context_pack_ready", "mock_provider_cycle"],
            "next_action": "watch",
            "watch_minutes": 30,
            "exit_plan": {
                "mode": "risk_limit",
                "reason": "exit if mock risk expands",
            },
            "prediction": {
                "direction": "neutral_up",
                "confidence": 0.61,
            },
            "pool_action": {
                "action": "keep",
                "reason": "candidate remains valid in mock cycle",
            },
            "state_transition": {
                "from": "candidate",
                "to": "watching",
            },
            "eta": {
                "mode": "watch",
                "remaining_minutes": 30,
                "reason": "mock follow-up window",
            },
            "scenario": {
                "name": "mock_watch",
                "label_ko": "모의 관찰",
            },
            "price_plan": {
                "entry": "wait_for_confirmation",
                "stop": "risk_limit",
                "target": "mock_resistance",
            },
            "ai_score": {
                "total": 72,
                "risk": 64,
                "opportunity": 75,
            },
            "briefing_detail": {
                "summary": "Mock bridge validates context to shadow record flow.",
                "risk_note": "No action is applied.",
            },
        }

        parsed = AIResponseParser().parse_json_response(
            json.dumps(mock_response, ensure_ascii=False),
            provider=provider_name,
        )
        shadow_record = parsed.to_shadow_record()
        shadow_record_ready = (
            "raw_text" not in shadow_record
            and shadow_record.get("applied") is False
            and bool(shadow_record.get("provider"))
        )
        result = {
            "provider": provider_name,
            "context_version": context_dict.get("version"),
            "prompt_ready": "JSON ONLY" in prompts.get("system_prompt", "")
            and "MARKET:" in prompts.get("user_prompt", ""),
            "parsed_valid": parsed.valid,
            "shadow_record_ready": shadow_record_ready,
            "suggestion": parsed.suggestion,
            "next_action": parsed.next_action,
            "scenario": parsed.scenario.get("name"),
            "applied": shadow_record.get("applied") is True,
        }

        self._safe_log_info(
            "[AITS][AIProviderMockBridge] mock_cycle_done"
            f" | provider={provider_name}"
            f" | parsed_valid={parsed.valid}"
            f" | shadow_record_ready={shadow_record_ready}"
        )
        return result

    def _safe_log_info(self, message: str) -> None:
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass
