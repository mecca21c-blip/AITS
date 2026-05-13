from __future__ import annotations

import json

from app.services.ollama_prompt_profile import OllamaPromptProfileBuilder


class OllamaStructuredPromptBuilder:
    """Builds profile-based JSON-only prompts for local Ollama shadow inference."""

    def build_prompt(self, context_dict: dict | None = None, profile: str = "compact") -> str:
        prompt_profile = OllamaPromptProfileBuilder().get_profile(profile)
        context = dict(context_dict or {}) if isinstance(context_dict, dict) else {}
        safe_context = {
            "symbol": str(context.get("symbol") or context.get("market") or "KRW-BTC"),
            "state": str(context.get("state") or "unknown"),
            "mode": "shadow_only",
            "submitted": 0,
            "real_order": False,
        }
        schema = self._schema_for_profile(prompt_profile.name)
        prompt = "\n".join(
            [
                "JSON ONLY. Return one JSON object. No markdown. No code fence. No explanation.",
                "Allowed suggestion: confirm, reject, skip.",
                "Allowed next_action: buy, sell, hold, wait, watch, reduce, remove.",
                "Safety constants: suggestion_only=true, applied=false, applied_to_action=false, submitted=0, real_order=false.",
                "Required fields: " + ", ".join(schema.keys()) + ".",
                "Schema:",
                json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
                "Context:",
                json.dumps(safe_context, ensure_ascii=False, separators=(",", ":")),
            ]
        )
        return prompt[: prompt_profile.max_chars]

    def _schema_for_profile(self, profile: str) -> dict:
        safety = {
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "submitted": 0,
            "real_order": False,
        }
        if profile == "speed_test":
            return {
                "suggestion": "skip",
                "confidence": 0.0,
                "next_action": "wait",
                **safety,
            }
        if profile == "ultra_compact":
            return {
                "suggestion": "skip",
                "confidence": 0.0,
                "next_action": "wait",
                "briefing": "short summary",
                "evidence": ["reason"],
                "scenario": {"name": "local_shadow"},
                "eta": {"remaining_minutes": 30},
                **safety,
            }
        if profile == "compact":
            return {
                "suggestion": "skip",
                "confidence": 0.0,
                "briefing": "short summary",
                "evidence": ["reason"],
                "next_action": "wait",
                "watch_minutes": 30,
                "pool_action": {"action": "keep"},
                "scenario": {"name": "local_shadow"},
                "eta": {"remaining_minutes": 30},
                **safety,
            }
        return {
            "suggestion": "skip",
            "confidence": 0.0,
            "briefing": "short summary",
            "evidence": ["reason"],
            "next_action": "wait",
            "watch_minutes": 30,
            "exit_plan": {"mode": "shadow_only"},
            "prediction": {"direction": "neutral"},
            "pool_action": {"action": "keep", "reason": "shadow_only"},
            "state_transition": {"from": "unknown", "to": "watching"},
            "eta": {"mode": "watch", "remaining_minutes": 30},
            "scenario": {"name": "local_shadow", "label_ko": "local observation"},
            "price_plan": {"entry": "wait"},
            "ai_score": {"total": 0},
            "briefing_detail": {"summary": "shadow-only local inference"},
            **safety,
        }


def build_sample_ollama_structured_prompt() -> str:
    return OllamaStructuredPromptBuilder().build_prompt({"symbol": "KRW-BTC"})


__all__ = [
    "OllamaStructuredPromptBuilder",
    "build_sample_ollama_structured_prompt",
]
