from __future__ import annotations

import json
import logging
from typing import Any, Dict


class AIPromptBuilder:
    def build_system_prompt(self) -> str:
        return "\n".join(
            [
                "You are the AI reasoning layer for AITS AI Trading Operating System.",
                "Operate in suggestion-only mode.",
                "Do not place trades or trigger direct trading.",
                "Return JSON ONLY.",
                "Use conservative risk awareness.",
                "Use opportunity cost awareness.",
                "Required JSON fields: suggestion, confidence, briefing, evidence, next_action, watch_minutes, exit_plan, prediction, pool_action, state_transition, eta, scenario, price_plan, ai_score, briefing_detail.",
                "Allowed suggestion values: confirm, reject, skip.",
                "Allowed next_action values: buy, sell, hold, wait, watch, reduce, remove.",
                "Allowed pool_action.action values: keep, remove, watch, promote, demote.",
                "Keep applied_to_action false.",
            ]
        )

    def build_user_prompt(self, context_dict: Dict[str, Any]) -> str:
        # Do not include API keys, secrets, tokens, or credentials in prompt input.
        context = dict(context_dict or {})
        prompt = "\n".join(
            [
                "Build a trading operation suggestion from this compact context.",
                "Return a UI-ready analysis for AITS managed candidate and detail panel.",
                "",
                "MARKET:",
                self._to_json_block(context.get("market")),
                "",
                "PORTFOLIO:",
                self._to_json_block(context.get("portfolio")),
                "",
                "OPPORTUNITY:",
                self._to_json_block(context.get("opportunity")),
                "",
                "RISK:",
                self._to_json_block(context.get("risk")),
                "",
                "NEWS:",
                self._to_json_block(context.get("news")),
                "",
                "Return JSON ONLY.",
                "Example:",
                "{",
                '  "suggestion": "confirm",',
                '  "confidence": 0.71,',
                '  "briefing": "...",',
                '  "evidence": ["..."],',
                '  "next_action": "watch",',
                '  "watch_minutes": 30,',
                '  "exit_plan": {},',
                '  "prediction": {},',
                '  "pool_action": {"action": "keep"},',
                '  "state_transition": {"current": "watching", "next": "entry_ready"},',
                '  "eta": {"mode": "watch", "remaining_minutes": 20},',
                '  "scenario": {"name": "sideways_watch", "label_ko": "횡보 관찰형"},',
                '  "price_plan": {"target_price": 3511270},',
                '  "ai_score": {"total": 62},',
                '  "briefing_detail": {"summary": "ok"}',
                "}",
            ]
        )
        return prompt

    def build_full_prompt(self, context_dict: Dict[str, Any]) -> Dict[str, str]:
        context = dict(context_dict or {})
        prompt = {
            "system_prompt": self.build_system_prompt(),
            "user_prompt": self.build_user_prompt(context),
        }
        self._safe_log_info(
            "[AITS][AIPromptBuilder] prompt_built"
            f" | context_version={context.get('version')}"
        )
        return prompt

    def _to_json_block(self, value: Any) -> str:
        return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)

    def _safe_log_info(self, message: str) -> None:
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass
