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
            "confidence": 0.55,
            "briefing": (
                "현재 후보는 단기 변동성은 있지만 거래대금과 추세 확인이 아직 부족합니다. "
                "무리한 진입보다 관찰을 유지하며 추가 확인이 필요합니다."
            ),
            "evidence": [
                "거래대금이 진입 기준을 충분히 넘지 못함",
                "단기 추세가 명확한 상승 전환으로 확인되지 않음",
                "리스크 대비 기대수익이 아직 충분하지 않음",
            ],
            "next_action": "watch",
            "watch_minutes": 30,
            "exit_plan": {
                "mode": "watch_only",
                "reason": "즉시 진입 조건 부족",
            },
            "prediction": {
                "direction": "sideways",
                "confidence": 0.55,
            },
            "pool_action": {
                "action": "watch",
                "reason": "관찰 가치는 있으나 즉시 진입 조건은 부족",
            },
            "state_transition": {
                "from": "candidate",
                "to": "watching",
            },
            "eta": {
                "mode": "watch",
                "remaining_minutes": 30,
                "reason": "거래대금과 추세 재확인 필요",
            },
            "scenario": {
                "name": "sideways_watch",
                "label_ko": "횡보 관찰형",
                "confidence": 0.55,
            },
            "price_plan": {
                "entry_zone": "-",
                "target_price": "-",
                "risk_price": "-",
                "reward_risk_ratio": "-",
            },
            "ai_score": {
                "total": 55,
                "trend": 12,
                "volume": 10,
                "risk": 13,
                "momentum": 10,
                "sentiment": 10,
            },
            "briefing_detail": {
                "summary": "관찰 유지",
                "risk_factor": "거래대금 부족",
                "opportunity_factor": "추세 전환 가능성 확인 필요",
                "market_context": "시장 평균 대비 강한 신호는 아직 제한적",
            },
        }

        parsed = AIResponseParser().parse_json_response(
            json.dumps(mock_response, ensure_ascii=False),
            provider=provider_name,
        )
        shadow_record = parsed.to_shadow_record()
        shadow_record["watch_minutes"] = parsed.watch_minutes
        shadow_record["exit_plan"] = dict(parsed.exit_plan or {})
        shadow_record["state_transition"] = dict(parsed.state_transition or {})
        shadow_record["price_plan"] = dict(parsed.price_plan or {})
        shadow_record["ai_score"] = dict(parsed.ai_score or {})
        shadow_record["briefing_detail"] = dict(parsed.briefing_detail or {})
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
            "shadow_record": shadow_record,
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
