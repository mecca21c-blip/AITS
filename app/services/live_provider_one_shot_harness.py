from __future__ import annotations

import logging

from app.services.ai_context_builder import build_sample_context_pack
from app.services.ai_provider_router import AIProviderRouter
from app.services.ai_state_machine import (
    AIStateMachine,
    format_state_snapshot_for_ui,
)


class LiveProviderOneShotHarness:
    """Shadow-only one-shot provider harness. It never submits orders."""

    def __init__(
        self,
        openai_api_key: str | None = None,
        gemini_api_key: str | None = None,
        openai_model: str = "gpt-5.5-instant",
        gemini_model: str = "gemini-2.5-flash",
        ollama_model: str = "qwen2.5:7b-instruct-q4",
    ) -> None:
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.openai_model = str(openai_model or "gpt-5.5-instant")
        self.gemini_model = str(gemini_model or "gemini-2.5-flash")
        self.ollama_model = str(ollama_model or "qwen2.5:7b-instruct-q4")
        self._log = logging.getLogger("aits")

    def run_one_shot(
        self,
        provider: str,
        context_dict: dict | None = None,
        allow_live: bool = False,
    ) -> dict:
        provider_name = str(provider or "ollama").strip().lower() or "ollama"
        try:
            context = (
                dict(context_dict)
                if isinstance(context_dict, dict)
                else build_sample_context_pack().to_compact_dict()
            )
            dry_run = not bool(allow_live)
            result = AIProviderRouter(
                openai_api_key=self.openai_api_key,
                gemini_api_key=self.gemini_api_key,
                openai_model=self.openai_model,
                gemini_model=self.gemini_model,
                ollama_model=self.ollama_model,
            ).run_shadow_cycle(
                provider_name,
                context,
                dry_run=dry_run,
            )

            shadow_record = result.get("shadow_record") if isinstance(result, dict) else {}
            if not isinstance(shadow_record, dict):
                shadow_record = {}
            symbol = str(
                shadow_record.get("symbol")
                or shadow_record.get("market")
                or context.get("symbol")
                or "KRW-BTC"
            ).strip() or "KRW-BTC"
            snapshot = AIStateMachine().transition(
                symbol=symbol,
                current_state="idle",
                ai_shadow_record=shadow_record,
            )
            state_ui = format_state_snapshot_for_ui(snapshot)
            output = {
                "provider": provider_name,
                "allow_live": bool(allow_live),
                "one_shot": True,
                "shadow_only": True,
                "parsed_valid": bool(result.get("parsed_valid")) if isinstance(result, dict) else False,
                "shadow_record_ready": bool(shadow_record),
                "state_ready": snapshot is not None,
                "state_ui_ready": bool(state_ui),
                "suggestion": str(
                    result.get("suggestion")
                    or shadow_record.get("suggestion")
                    or "skip"
                ),
                "next_action": str(
                    result.get("next_action")
                    or shadow_record.get("next_action")
                    or "wait"
                ),
                "state": str(getattr(snapshot, "state", "") or ""),
                "status_line": str(state_ui.get("status_line") or ""),
                "applied": False,
                "applied_to_action": False,
                "submitted": 0,
                "real_order": False,
            }
            self._log_result(output)
            return output
        except Exception as exc:
            output = {
                "provider": provider_name,
                "allow_live": bool(allow_live),
                "one_shot": True,
                "shadow_only": True,
                "parsed_valid": False,
                "shadow_record_ready": False,
                "state_ready": False,
                "state_ui_ready": False,
                "suggestion": "skip",
                "next_action": "wait",
                "state": "idle",
                "status_line": "",
                "applied": False,
                "applied_to_action": False,
                "submitted": 0,
                "real_order": False,
                "error_type": type(exc).__name__,
            }
            self._log_result(output)
            return output

    def _log_result(self, output: dict) -> None:
        try:
            self._log.info(
                "[AITS][LiveProviderOneShot] one_shot_done | provider=%s | allow_live=%s | parsed_valid=%s | submitted=0",
                output.get("provider"),
                bool(output.get("allow_live")),
                bool(output.get("parsed_valid")),
            )
        except Exception:
            pass


__all__ = ["LiveProviderOneShotHarness"]
