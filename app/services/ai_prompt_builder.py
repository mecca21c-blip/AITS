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
        state_context_text = self.build_state_context_block(
            context.get("current_state") or context.get("state_context"),
            context.get("recent_history") or context.get("state_history"),
        )
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
                state_context_text,
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

    def build_state_context_block(
        self,
        current_state: dict | None,
        recent_history: list[dict] | None,
    ) -> str:
        current = current_state if isinstance(current_state, dict) else {}
        history = recent_history if isinstance(recent_history, list) else []
        history_items = [item for item in history if isinstance(item, dict)][:5]

        lines = ["[STATE CONTEXT]", "Current State:"]
        if current:
            lines.extend(
                [
                    f"- state: {str(current.get('state') or 'idle').strip()}",
                    f"- scenario: {str(current.get('scenario') or '-').strip()}",
                    f"- eta: {self._format_state_eta(current)}",
                ]
            )
        else:
            lines.append("- No active state")

        lines.extend(["", "Recent State History:"])
        if history_items:
            for idx, item in enumerate(history_items, start=1):
                previous_state = str(
                    item.get("previous_state") or item.get("from") or "idle"
                ).strip()
                state = str(item.get("state") or item.get("to") or "idle").strip()
                lines.append(f"{idx}. {previous_state} -> {state}")
        else:
            lines.append("No recent state history")

        lines.extend(
            [
                "",
                "Important:",
                "- Maintain continuity of reasoning.",
                "- Avoid unnecessary state oscillation.",
                "- Respect previous observations.",
                "- Keep suggestion-only mode.",
                "- Do not trigger direct trading.",
                "- Keep applied_to_action false.",
                "- Return JSON ONLY.",
            ]
        )
        self._safe_log_info(
            "[AITS][PromptBuilder] state_context_prompt_built"
            f" | history_count={len(history_items)}"
        )
        return "\n".join(lines)

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

    def _format_state_eta(self, current_state: dict) -> str:
        eta_text = str(current_state.get("eta_text") or "").strip()
        if eta_text:
            return eta_text
        try:
            minutes = int(float(current_state.get("eta_minutes") or 0))
        except Exception:
            minutes = 0
        if minutes <= 0:
            return "-"
        if minutes >= 10080:
            return "long_watch"
        if minutes >= 1440:
            days = minutes // 1440
            hours = (minutes % 1440) // 60
            return f"{days}d {hours}h"
        if minutes >= 60:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
        return f"{minutes}m"

    def _safe_log_info(self, message: str) -> None:
        try:
            logging.getLogger("aits").info(message)
        except Exception:
            pass


def build_sample_state_aware_prompt_result() -> dict:
    try:
        from app.services.ai_context_builder import build_sample_context_pack
        from app.services.ai_state_machine import build_sample_state_pipeline_result

        context = build_sample_context_pack().to_compact_dict()
        state_pipeline = build_sample_state_pipeline_result()
        current_state = dict(state_pipeline.get("ui") or {})
        if not current_state:
            current_state = {
                "state": state_pipeline.get("state") or "idle",
                "scenario": state_pipeline.get("scenario") or "",
                "eta_minutes": state_pipeline.get("eta_minutes") or 0,
            }
        recent_history = [
            {"previous_state": "idle", "state": "watching"},
            {"previous_state": "watching", "state": "entry_wait"},
            {"previous_state": "entry_wait", "state": current_state.get("state") or "watching"},
        ]
        context["current_state"] = current_state
        context["recent_history"] = recent_history

        prompt = AIPromptBuilder().build_full_prompt(context)
        system_prompt = str(prompt.get("system_prompt") or "")
        user_prompt = str(prompt.get("user_prompt") or "")
        return {
            "system_prompt_ok": bool(system_prompt),
            "user_prompt_ok": bool(user_prompt),
            "state_context_included": "[STATE CONTEXT]" in user_prompt,
            "history_included": "Recent State History:" in user_prompt,
            "json_only": "Return JSON ONLY." in system_prompt and "Return JSON ONLY." in user_prompt,
        }
    except Exception:
        return {
            "system_prompt_ok": False,
            "user_prompt_ok": False,
            "state_context_included": False,
            "history_included": False,
            "json_only": False,
        }


def build_state_context_block(
    current_state: dict | None,
    recent_history: list[dict] | None,
) -> str:
    return AIPromptBuilder().build_state_context_block(current_state, recent_history)


__all__ = [
    "AIPromptBuilder",
    "build_sample_state_aware_prompt_result",
    "build_state_context_block",
]
