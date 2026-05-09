from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any, Dict, List, Optional


ALLOWED_SUGGESTIONS = {"confirm", "reject", "skip"}
ALLOWED_NEXT_ACTIONS = {"buy", "sell", "hold", "wait", "watch", "reduce", "remove"}
ALLOWED_POOL_ACTIONS = {"keep", "remove", "watch", "promote", "demote"}


@dataclass
class AIParsedResponse:
    provider: str = "unknown"
    suggestion: str = "skip"
    confidence: float = 0.0
    briefing: str = ""
    evidence: List[Any] = field(default_factory=list)
    next_action: str = "wait"
    watch_minutes: int = 0
    exit_plan: Dict[str, Any] = field(default_factory=dict)
    prediction: Dict[str, Any] = field(default_factory=dict)
    pool_action: Dict[str, Any] = field(default_factory=dict)
    state_transition: Dict[str, Any] = field(default_factory=dict)
    eta: Dict[str, Any] = field(default_factory=dict)
    scenario: Dict[str, Any] = field(default_factory=dict)
    price_plan: Dict[str, Any] = field(default_factory=dict)
    ai_score: Dict[str, Any] = field(default_factory=dict)
    briefing_detail: Dict[str, Any] = field(default_factory=dict)
    valid: bool = False
    raw_text: str = ""
    error: Optional[str] = None
    suggestion_only: bool = True
    applied_to_action: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_shadow_record(self) -> Dict[str, Any]:
        record = {
            "provider": self.provider,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "next_action": self.next_action,
            "briefing": self.briefing,
            "evidence": list(self.evidence or []),
            "scenario": dict(self.scenario or {}),
            "eta": dict(self.eta or {}),
            "prediction": dict(self.prediction or {}),
            "pool_action": dict(self.pool_action or {}),
            "valid": self.valid,
            "suggestion_only": True,
            "applied_to_action": False,
            "applied": False,
        }
        if self.metadata:
            record["metadata"] = {
                key: value
                for key, value in self.metadata.items()
                if key not in {"raw_text", "prompt", "response"}
            }
        try:
            logging.getLogger("aits").info(
                "[AITS][AIResponseParser] shadow_record_built"
                f" | provider={self.provider}"
                f" | suggestion={self.suggestion}"
                " | applied=False"
            )
        except Exception:
            pass
        return record


class AIResponseParser:
    def parse_json_response(
        self,
        raw_text: str,
        provider: str = "unknown",
    ) -> AIParsedResponse:
        provider_name = str(provider or "unknown")
        raw = str(raw_text or "")
        recovery_result = None
        parse_text = raw

        try:
            from app.services.ai_response_recovery import AIResponseRecovery

            recovery_result = AIResponseRecovery().recover_json_text(raw)
            if recovery_result.raw_valid or recovery_result.recovered:
                parse_text = recovery_result.recovered_text
        except Exception:
            recovery_result = None

        try:
            payload = json.loads(parse_text)
            if not isinstance(payload, dict):
                raise ValueError("AI response JSON root is not an object")
        except Exception as exc:
            parsed = self._fallback_parse_failure(
                provider=provider_name,
                raw_text=raw,
                error=self._build_error(type(exc).__name__, recovery_result),
            )
            parsed.metadata = self._build_recovery_metadata(recovery_result)
            self._log_parsed(parsed)
            return parsed

        suggestion = self._normalize_choice(
            payload.get("suggestion"),
            allowed=ALLOWED_SUGGESTIONS,
            fallback="skip",
        )
        next_action = self._normalize_choice(
            payload.get("next_action"),
            allowed=ALLOWED_NEXT_ACTIONS,
            fallback="wait",
        )
        pool_action = self._normalize_pool_action(payload.get("pool_action"))

        parsed = AIParsedResponse(
            provider=provider_name,
            suggestion=suggestion,
            confidence=self._clamp_confidence(payload.get("confidence")),
            briefing=str(payload.get("briefing") or payload.get("summary") or ""),
            evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
            next_action=next_action,
            watch_minutes=self._safe_int(payload.get("watch_minutes")),
            exit_plan=self._safe_dict(payload.get("exit_plan"), {}),
            prediction=self._safe_dict(payload.get("prediction"), {}),
            pool_action=pool_action,
            state_transition=self._safe_dict(payload.get("state_transition"), {}),
            eta=self._safe_dict(payload.get("eta"), self._fallback_eta("invalid_eta")),
            scenario=self._safe_dict(payload.get("scenario"), self._fallback_scenario()),
            price_plan=self._safe_dict(payload.get("price_plan"), {}),
            ai_score=self._safe_dict(payload.get("ai_score"), {}),
            briefing_detail=self._safe_dict(payload.get("briefing_detail"), {}),
            valid=True,
            raw_text=raw,
            error=None,
            suggestion_only=True,
            applied_to_action=False,
            metadata=self._build_recovery_metadata(recovery_result),
        )
        self._log_parsed(parsed)
        return parsed

    def _fallback_parse_failure(
        self,
        provider: str,
        raw_text: str,
        error: str,
    ) -> AIParsedResponse:
        return AIParsedResponse(
            provider=provider,
            suggestion="skip",
            confidence=0.0,
            briefing="AI response parse failed",
            evidence=[],
            next_action="wait",
            watch_minutes=0,
            exit_plan={},
            prediction={},
            pool_action={"action": "watch", "reason": "parse_failed"},
            state_transition={},
            eta=self._fallback_eta("parse_failed"),
            scenario=self._fallback_scenario(),
            price_plan={},
            ai_score={},
            briefing_detail={},
            valid=False,
            raw_text=raw_text,
            error=error,
            suggestion_only=True,
            applied_to_action=False,
            metadata={},
        )

    def _normalize_choice(self, value: Any, allowed: set[str], fallback: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in allowed:
            return normalized
        return fallback

    def _normalize_pool_action(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {"action": "watch", "reason": "missing_pool_action"}
        pool_action = dict(value)
        pool_action["action"] = self._normalize_choice(
            pool_action.get("action"),
            allowed=ALLOWED_POOL_ACTIONS,
            fallback="watch",
        )
        return pool_action

    def _safe_dict(self, value: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        return dict(fallback)

    def _fallback_eta(self, reason: str) -> Dict[str, Any]:
        return {
            "mode": "watch",
            "remaining_minutes": 0,
            "reason": reason,
        }

    def _fallback_scenario(self) -> Dict[str, Any]:
        return {
            "name": "unknown",
            "label_ko": "unknown",
        }

    def _build_recovery_metadata(self, recovery_result: Any) -> Dict[str, Any]:
        return {
            "recovery_used": bool(getattr(recovery_result, "recovered", False)),
            "raw_valid": bool(getattr(recovery_result, "raw_valid", False)),
            "recovery_error_type": getattr(recovery_result, "error_type", None),
            "shadow_only": True,
            "suggestion_only": True,
            "applied": False,
            "applied_to_action": False,
            "real_order": False,
            "submitted": 0,
        }

    def _build_error(self, error: str, recovery_result: Any) -> str:
        recovery_error = getattr(recovery_result, "error_type", None)
        if recovery_error:
            return f"{error}:{recovery_error}"
        return str(error or "parse_error")

    def _clamp_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        if confidence < 0.0:
            return 0.0
        if confidence > 1.0:
            return 1.0
        return confidence

    def _safe_int(self, value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        if parsed < 0:
            return 0
        return parsed

    def _log_parsed(self, parsed: AIParsedResponse) -> None:
        # Do not log keys, secrets, tokens, credentials, or the raw full response.
        try:
            logging.getLogger("aits").info(
                "[AITS][AIResponseParser] response_parsed"
                f" | provider={parsed.provider}"
                f" | valid={parsed.valid}"
                f" | suggestion={parsed.suggestion}"
                f" | next_action={parsed.next_action}"
                f" | scenario={parsed.scenario.get('name')}"
                f" | pool_action={parsed.pool_action.get('action')}"
                f" | recovery_used={parsed.metadata.get('recovery_used')}"
            )
        except Exception:
            pass


def build_sample_ai_pipeline_result() -> Dict[str, Any]:
    from app.services.ai_context_builder import build_sample_context_pack
    from app.services.ai_prompt_builder import AIPromptBuilder

    context_pack = build_sample_context_pack()
    context_dict = context_pack.to_compact_dict()
    prompts = AIPromptBuilder().build_full_prompt(context_dict)

    mock_response = {
        "suggestion": "confirm",
        "confidence": 0.71,
        "briefing": "Sample managed candidate remains actionable with controlled risk.",
        "evidence": ["sample_context_available", "risk_controls_present"],
        "next_action": "watch",
        "watch_minutes": 15,
        "pool_action": {
            "action": "keep",
            "reason": "sample_candidate_still_valid",
        },
        "state_transition": {
            "from": "candidate",
            "to": "watching",
        },
        "eta": {
            "mode": "watch",
            "remaining_minutes": 15,
            "reason": "sample_follow_up_window",
        },
        "scenario": {
            "name": "base_watch",
            "label_ko": "watch",
        },
        "price_plan": {
            "entry": "wait_for_confirmation",
            "invalid_if": "risk_expands",
        },
        "ai_score": {
            "total": 71,
            "risk": 62,
            "opportunity": 74,
        },
        "briefing_detail": {
            "summary": "Sample pipeline validates context, prompt, and parser flow.",
            "risk_note": "No action is applied.",
        },
    }

    parsed = AIResponseParser().parse_json_response(
        json.dumps(mock_response, ensure_ascii=False),
        provider="sample",
    )
    shadow_record = parsed.to_shadow_record()
    result = {
        "context_version": context_dict.get("version"),
        "system_prompt_ok": "JSON ONLY" in prompts.get("system_prompt", ""),
        "user_prompt_ok": "MARKET:" in prompts.get("user_prompt", "")
        and "Return JSON ONLY" in prompts.get("user_prompt", ""),
        "parsed_valid": parsed.valid,
        "suggestion": parsed.suggestion,
        "next_action": parsed.next_action,
        "scenario": parsed.scenario.get("name"),
        "applied_to_action": parsed.applied_to_action,
        "shadow_record_ok": "raw_text" not in shadow_record
        and shadow_record.get("applied") is False,
    }

    try:
        logging.getLogger("aits").info(
            "[AITS][AIPipeline] sample_pipeline_built"
            f" | parsed_valid={parsed.valid}"
            f" | suggestion={parsed.suggestion}"
            f" | next_action={parsed.next_action}"
        )
    except Exception:
        pass
    return result
