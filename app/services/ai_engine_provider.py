from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from typing import Any, Dict, Optional
import urllib.error
import urllib.request


AI_VERIFICATION_ALLOWED_SUGGESTIONS = {
    "confirm",
    "override_wait",
    "override_buy",
    "override_reduce",
    "override_sell",
    "reject_signal",
}


def _safe_log_info(message: str) -> None:
    try:
        logging.getLogger("aits").info(message)
    except Exception:
        pass


AI_DECISION_ALLOWED_ACTIONS = {
    "hold",
    "wait",
    "buy",
    "add",
    "sell",
    "reduce",
    "rotate",
    "promote",
    "reject",
    "replace",
    "rotate_review",
    "reduce_and_rotate",
    "take_profit",
    "stop_loss",
}


AI_DECISION_REQUIRED_FIELDS = (
    "action",
    "confidence",
    "reason_ko",
    "eta_seconds",
    "execution_plan",
    "risk_notes",
    "invalidation_conditions",
)


def build_ai_decision_blocker(blockers: Any) -> str:
    if isinstance(blockers, (list, tuple)):
        for item in blockers:
            text = str(item or "").strip()
            if text:
                return text
        return ""
    return str(blockers or "").strip()


def _decision_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _decision_allowed_rotation_symbols(candidates: Any) -> set[str]:
    allowed: set[str] = set()

    def _add(value: Any) -> None:
        symbol = str(value or "").strip().upper()
        if symbol:
            allowed.add(symbol)

    if isinstance(candidates, dict):
        for key in ("rotation_candidates", "scanner_top_candidates", "managed_pool_symbols", "holdings_symbols"):
            values = candidates.get(key)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        _add(item.get("symbol") or item.get("market") or item.get("ticker"))
                    else:
                        _add(item)
        for key in ("rotate_to_symbol", "symbol"):
            _add(candidates.get(key))
    elif isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                _add(item.get("symbol") or item.get("market") or item.get("ticker"))
            else:
                _add(item)
    return allowed


def validate_ai_decision_response(
    response: Optional[Dict[str, Any]],
    *,
    provider: Any = "",
    task: str = "",
    symbol: str = "",
    candidates: Any = None,
) -> Dict[str, Any]:
    """Normalize and validate the final AI decision contract.

    The validator never executes orders. Invalid decisions are converted into a
    non-executable wait decision with an explicit blocker.
    """
    provider_text = str(provider or "").strip().lower() or "unknown"
    task_text = str(task or "").strip() or "ai_decision"
    symbol_text = str(symbol or "").strip().upper()
    _safe_log_info(
        "[AITS][AIDecisionValidator] event=validation_started "
        f"provider={provider_text} task={task_text} symbol={symbol_text or '-'} "
        "actual_order=False submitted=0"
    )

    if not isinstance(response, dict) or not response:
        blocker = "ai_decision_response_missing"
        decision = {
            "schema": "aits_ai_decision_response_v1",
            "action": "wait",
            "confidence": 0.0,
            "reason_ko": "AI 판단 응답이 없어 주문을 보류합니다.",
            "eta_seconds": 300,
            "execution_plan": {},
            "risk_notes": "",
            "invalidation_conditions": [],
            "sell_ratio": 0.0,
            "buy_amount_krw": 0.0,
            "rotate_to_symbol": "",
            "validation_passed": False,
            "validator_result": "failed",
            "validation_blocker": blocker,
            "blocker": blocker,
            "actual_order": False,
            "submitted": 0,
        }
        _safe_log_info(
            "[AITS][AIDecisionValidator] event=validation_failed "
            f"provider={provider_text} task={task_text} symbol={symbol_text or '-'} "
            f"action=wait confidence=0 blocker={blocker} reason=response_missing actual_order=False submitted=0"
        )
        return {"valid": False, "validation_passed": False, "blocker": blocker, "blockers": [blocker], "decision": decision}

    source = dict(response or {})
    blockers: list[str] = []
    execution_plan = source.get("execution_plan")
    if not isinstance(execution_plan, dict):
        execution_plan = {}
        blockers.append("ai_decision_execution_plan_missing")

    action = str(source.get("action") or source.get("decision") or "").strip().lower()
    if action not in AI_DECISION_ALLOWED_ACTIONS:
        blockers.append("ai_decision_action_invalid")
        action = "wait"

    confidence_raw = source.get("confidence")
    confidence = _decision_float(confidence_raw, -1.0)
    if confidence < 0.0 or confidence > 1.0:
        blockers.append("ai_decision_confidence_invalid")
        confidence = max(0.0, min(1.0, _decision_float(confidence_raw, 0.0)))

    reason_ko = str(source.get("reason_ko") or source.get("reason") or "").strip()
    if not reason_ko:
        blockers.append("ai_decision_reason_missing")
        reason_ko = "AI 판단 근거가 비어 있어 주문을 보류합니다."

    eta_raw = source.get("eta_seconds", 300)
    eta_seconds = int(_decision_float(eta_raw, -1.0))
    if eta_seconds < 0:
        blockers.append("ai_decision_eta_invalid")
        eta_seconds = 300

    invalidation_conditions = source.get("invalidation_conditions")
    if invalidation_conditions is None:
        invalidation_conditions = []
    elif isinstance(invalidation_conditions, dict):
        invalidation_conditions = [invalidation_conditions]
    elif not isinstance(invalidation_conditions, list):
        invalidation_conditions = [str(invalidation_conditions)]

    risk_notes = str(source.get("risk_notes") or "")[:1000]
    sell_ratio = _decision_float(source.get("sell_ratio", execution_plan.get("sell_ratio", 0.0)), 0.0)
    buy_amount_krw = _decision_float(source.get("buy_amount_krw", execution_plan.get("buy_amount_krw", 0.0)), 0.0)
    rotate_to_symbol = str(source.get("rotate_to_symbol") or execution_plan.get("rotate_to_symbol") or "").strip().upper()
    replace_symbol = str(
        source.get("replace_symbol")
        or execution_plan.get("replace_symbol")
        or source.get("replace_target_symbol")
        or execution_plan.get("replace_target_symbol")
        or ""
    ).strip().upper()

    if action in {"buy", "add"} and buy_amount_krw <= 0.0:
        blockers.append("ai_decision_buy_amount_missing")
    if action in {"sell", "reduce", "take_profit", "stop_loss"}:
        if sell_ratio <= 0.0:
            blockers.append("ai_decision_sell_ratio_missing")
        elif sell_ratio > 1.0:
            blockers.append("ai_decision_sell_ratio_invalid")
    if action in {"rotate", "reduce_and_rotate"}:
        if not rotate_to_symbol:
            blockers.append("ai_decision_rotate_target_missing")
        else:
            allowed_rotation_symbols = _decision_allowed_rotation_symbols(candidates)
            if allowed_rotation_symbols and rotate_to_symbol not in allowed_rotation_symbols:
                blockers.append("ai_decision_rotate_target_invalid")
    if action == "reduce_and_rotate":
        if sell_ratio <= 0.0:
            blockers.append("rotation_sell_ratio_missing")
        elif sell_ratio > 1.0:
            blockers.append("ai_decision_sell_ratio_invalid")
    if action == "replace" and not replace_symbol:
        blockers.append("rotation_replace_target_missing" if task_text == "rotation_decision" else "promotion_replace_target_missing")

    sell_ratio = max(0.0, min(1.0, sell_ratio))
    buy_amount_krw = max(0.0, buy_amount_krw)
    blocker = build_ai_decision_blocker(blockers)
    valid = not blockers
    if not valid:
        action = "wait"

    decision = dict(source)
    decision.update(
        {
            "schema": "aits_ai_decision_response_v1",
            "action": action,
            "confidence": confidence,
            "reason_ko": reason_ko[:1000],
            "eta_seconds": eta_seconds,
            "execution_plan": execution_plan,
            "risk_notes": risk_notes,
            "invalidation_conditions": invalidation_conditions,
            "sell_ratio": sell_ratio,
            "buy_amount_krw": buy_amount_krw,
            "rotate_to_symbol": rotate_to_symbol,
            "replace_symbol": replace_symbol,
            "validation_passed": bool(valid),
            "validator_result": "passed" if valid else "failed",
            "validation_blocker": blocker,
            "blocker": blocker or str(source.get("blocker") or ""),
            "actual_order": False,
            "submitted": 0,
        }
    )
    _safe_log_info(
        "[AITS][AIDecisionValidator] event=validation_%s provider=%s task=%s symbol=%s "
        "action=%s confidence=%s blocker=%s reason=%s actual_order=False submitted=0"
        % (
            "passed" if valid else "failed",
            provider_text,
            task_text,
            symbol_text or "-",
            action or "-",
            confidence,
            blocker or "-",
            "ok" if valid else blocker or "invalid_schema",
        )
    )
    return {"valid": bool(valid), "validation_passed": bool(valid), "blocker": blocker, "blockers": blockers, "decision": decision}


def normalize_ai_decision_response(response: Optional[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
    return validate_ai_decision_response(response, **kwargs)


@dataclass
class AIEngineDecision:
    action: str = "hold"
    confidence: float = 0.0
    risk: str = "medium"
    reason: str = ""
    engine: str = "local"
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "risk": self.risk,
            "reason": self.reason,
            "engine": self.engine,
            "raw": dict(self.raw or {}),
        }


class AIEngineProvider:
    name: str = "base"
    api_required: bool = False
    ready_reason: str = "Provider not configured"

    def __init__(
        self,
        api_key: str = "",
        settings: Optional[Any] = None,
        strategy: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.settings = settings
        self.strategy = strategy
        self.config = config

    def is_ready(self) -> bool:
        return False

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="AIEngineProvider skeleton fallback",
            engine=self.name,
            raw={"mode": "skeleton", "context": dict(context or {})},
        )

    def _get_config_api_key(self, provider: Any) -> str:
        """
        Return API key from settings first, then env fallback.
        Never log the key value.
        """
        provider = normalize_provider_name(provider)
        resolved_key = ""
        key_method = "missing"

        def _iter_config_roots():
            for obj in (
                getattr(self, "strategy", None),
                getattr(self, "settings", None),
                getattr(self, "config", None),
            ):
                if obj is None:
                    continue
                yield obj
                try:
                    if isinstance(obj, dict):
                        for key in ("strategy", "settings", "config"):
                            child = obj.get(key)
                            if child is not None:
                                yield child
                    else:
                        for key in ("strategy", "settings", "config"):
                            child = getattr(obj, key, None)
                            if child is not None:
                                yield child
                except Exception:
                    pass

        def _read_config_key(obj: Any, names: tuple[str, ...]) -> str:
            try:
                for name in names:
                    if isinstance(obj, dict):
                        key = obj.get(name)
                    else:
                        key = getattr(obj, name, None)
                    if hasattr(key, "get_secret_value"):
                        key = key.get_secret_value()
                    if key:
                        return str(key).strip()
            except Exception:
                pass
            return ""

        if provider == "openai":
            for obj in _iter_config_roots():
                key = _read_config_key(obj, ("ai_openai_api_key", "openai_api_key"))
                if key:
                    resolved_key = key
                    key_method = "settings"
                    break
            if not resolved_key:
                key = os.getenv("OPENAI_API_KEY")
                if key:
                    resolved_key = key
                    key_method = "environment"

        elif provider == "gemini":
            for obj in _iter_config_roots():
                key = _read_config_key(
                    obj,
                    ("ai_gemini_api_key", "gemini_api_key", "google_api_key"),
                )
                if key:
                    resolved_key = key
                    key_method = "settings"
                    break
            if not resolved_key:
                key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if key:
                    resolved_key = key
                    key_method = "environment"
        try:
            _provider_name = normalize_provider_label(provider)

            print(
                "[AITS][AIEngineProvider] key_resolution "
                f"| provider={_provider_name or 'unknown'} "
                f"| resolved={bool(resolved_key)} "
                f"| method={key_method}"
            )
        except Exception:
            pass

        return resolved_key

    def verify_router_decision(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        AITS Decision Router v2.7
        Standard AI verification adapter.

        Safety:
        - Router decision 검증 의견만 반환한다.
        - 주문/action/final decision을 변경하지 않는다.
        - Local/basic은 API 호출하지 않는다.
        - OpenAI/Gemini도 실제 호출 메서드가 명확히 있을 때만 호출한다.
        """
        provider = str(provider or "local").strip().lower()
        context = context or {}

        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"

        try:
            _provider_norm = str(provider or "local").strip().lower()

            _openai_key = self._get_config_api_key("openai")
            _gemini_key = self._get_config_api_key("gemini")

            _openai_ready = bool(_openai_key)
            _gemini_ready = bool(_gemini_key)

            _reason = ""
            if _provider_norm == "openai" and not _openai_ready:
                _reason = "openai_api_key_missing"
            elif _provider_norm == "gemini" and not _gemini_ready:
                _reason = "gemini_api_key_missing"
            elif _provider_norm not in ("openai", "gemini", "local", "basic", "none", ""):
                _reason = f"unsupported_provider:{_provider_norm}"
            else:
                _reason = "ready" if (
                    (_provider_norm == "openai" and _openai_ready)
                    or (_provider_norm == "gemini" and _gemini_ready)
                    or (_provider_norm == "local")
                ) else "not_applicable"

            logging.getLogger("aits").info(
                "[AITS][AIProviderReadiness] "
                f"provider={_provider_norm} | "
                f"openai_ready={_openai_ready} | "
                f"gemini_ready={_gemini_ready} | "
                f"reason={_reason}"
            )
        except Exception:
            pass

        if provider in ("basic", "local", "localprovider", "none", ""):
            try:
                import random

                _force_ai = str(os.getenv("AITS_FORCE_AI_SAMPLE", "0")).lower() in ("1", "true", "yes", "on")

                if _force_ai:
                    _r = random.random()

                    if _r < 0.2:
                        return self._with_ai_result_contract({
                            "suggestion": "confirm",
                            "reason": "local_forced_confirm",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        })

                    if _r < 0.3:
                        return self._with_ai_result_contract({
                            "suggestion": "reject_signal",
                            "reason": "local_forced_reject",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        })
            except Exception:
                pass

            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": "local_provider_no_api_call",
                "risk_note": None,
                "provider": "local",
                "applied": False,
            })

        if provider not in ("openai", "gemini"):
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": f"unsupported_provider:{provider}",
                "provider": provider,
                "applied": False,
            })

        try:
            prompt = self._build_router_verification_prompt(context)
            raw_response = None

            if provider == "openai":
                raw_response = self._call_openai_router_verification(prompt, context)
            elif provider == "gemini":
                raw_response = self._call_gemini_router_verification(prompt, context)

            return self._parse_router_verification_response(
                raw_response=raw_response,
                provider=provider,
            )
        except NotImplementedError as exc:
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": str(exc) or f"{provider}_verifier_not_implemented",
                "provider": provider,
                "applied": False,
            })
        except Exception as exc:
            error_reason = str(exc)[:500]
            if not error_reason:
                error_reason = f"{provider}_verifier_error:{type(exc).__name__}"
            result_reason = error_reason
            if error_reason in (
                "openai_quota_exceeded",
                "openai_api_key_invalid",
                "openai_bad_request",
                "gemini_quota_exceeded",
                "gemini_api_key_invalid",
                "gemini_bad_request",
            ):
                result_reason = f"{error_reason}:error"
            return self._with_ai_result_contract({
                "suggestion": "skip",
                "reason": result_reason,
                "provider": provider,
                "applied": False,
                "error": error_reason,
            })

    def generate_managed_pool_opinion(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Managed Pool opinion-only provider call.

        This path is intentionally separate from Router verification: it asks for
        a display/review opinion and never applies, routes, or executes an order.
        """
        provider = str(provider or "local").strip().lower()
        context = dict(context or {})
        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"
        if provider not in ("openai", "gemini"):
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": f"unsupported_provider:{provider}",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })

        try:
            prompt = self._build_managed_pool_opinion_prompt(context)
            if provider == "openai":
                raw = self._call_openai_managed_pool_opinion(prompt, context)
            else:
                raw = self._call_gemini_managed_pool_opinion(prompt, context)
            parsed = self._parse_managed_pool_opinion_response(raw.get("content"), context)
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": True,
                "response_id": str(raw.get("response_id") or ""),
                "usage_input_tokens": raw.get("usage_input_tokens"),
                "usage_output_tokens": raw.get("usage_output_tokens"),
                "usage_total_tokens": raw.get("usage_total_tokens"),
                "opinion": parsed.get("opinion"),
                "status_label": parsed.get("status_label"),
                "confidence": parsed.get("confidence"),
                "reason": parsed.get("reason"),
                "next_action": parsed.get("next_action"),
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })
        except NotImplementedError as exc:
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": str(exc) or f"{provider}_managed_pool_opinion_not_implemented",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })
        except Exception as exc:
            reason = str(exc)[:500] or f"{provider}_managed_pool_opinion_error:{type(exc).__name__}"
            return self._with_ai_result_contract({
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": reason,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
                "applied": False,
            })

    def generate_position_management_decision(self, *, provider: Any = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ask the selected AI provider for a position-management decision.

        This returns a decision contract only. It never routes or submits orders.
        """
        provider = str(provider or "local").strip().lower()
        context = dict(context or {})
        if provider in ("gpt", "chatgpt"):
            provider = "openai"
        elif provider in ("google", "google_gemini"):
            provider = "gemini"
        try:
            if provider in ("basic", "local", "local_ai", ""):
                parsed = self._build_local_position_management_decision(context)
                validation = validate_ai_decision_response(
                    parsed,
                    provider="local",
                    task=str(context.get("task") or "manage_position_decision"),
                    symbol=str(context.get("symbol") or ""),
                    candidates=context.get("candidates"),
                )
                parsed = dict(validation.get("decision") or {})
                parsed["provider"] = "local"
                parsed["response_confirmed"] = bool(validation.get("validation_passed"))
                parsed["provider_call_attempted"] = False
                parsed["reason"] = parsed.get("reason_ko") or parsed.get("reason") or "LOCAL AI decision"
                return parsed
            if provider not in ("openai", "gemini"):
                return {
                    "schema": "aits_position_management_decision_v1",
                    "provider": provider,
                    "response_confirmed": False,
                    "provider_call_attempted": False,
                    "action": "wait",
                    "confidence": 0.0,
                    "reason_ko": f"지원하지 않는 AI 제공자입니다: {provider}",
                    "eta_seconds": 300,
                    "sell_ratio": 0.0,
                    "buy_amount_krw": 0.0,
                    "blocker": f"unsupported_provider:{provider}",
                    "actual_order": False,
                    "submitted": 0,
                }
            prompt = self._build_position_management_decision_prompt(context)
            if provider == "openai":
                raw = self._call_openai_position_management_decision(prompt, context)
            else:
                raw = self._call_gemini_position_management_decision(prompt, context)
            parsed = self._parse_position_management_decision_response(raw.get("content"), context)
            parsed.update(
                {
                    "schema": "aits_position_management_decision_v1",
                    "provider": provider,
                    "response_confirmed": bool(parsed.get("validation_passed")),
                    "provider_call_attempted": True,
                    "response_id": str(raw.get("response_id") or ""),
                    "usage_input_tokens": raw.get("usage_input_tokens"),
                    "usage_output_tokens": raw.get("usage_output_tokens"),
                    "usage_total_tokens": raw.get("usage_total_tokens"),
                    "actual_order": False,
                    "submitted": 0,
                }
            )
            return parsed
        except NotImplementedError as exc:
            return {
                "schema": "aits_position_management_decision_v1",
                "provider": provider,
                "response_confirmed": False,
                "provider_call_attempted": True,
                "action": "wait",
                "confidence": 0.0,
                "reason_ko": "AI 판단이 필요하지만 제공자 호출이 차단되어 대기합니다.",
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "blocker": str(exc) or f"{provider}_position_decision_not_available",
                "actual_order": False,
                "submitted": 0,
            }
        except Exception as exc:
            return {
                "schema": "aits_position_management_decision_v1",
                "provider": provider,
                "response_confirmed": False,
                "provider_call_attempted": True,
                "action": "wait",
                "confidence": 0.0,
                "reason_ko": "AI 판단 응답을 확인하지 못해 주문을 보류합니다.",
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "blocker": str(exc)[:300] or f"{provider}_position_decision_error:{type(exc).__name__}",
                "actual_order": False,
                "submitted": 0,
            }

    def _build_position_management_decision_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        safe_context = dict(context or {})
        if str(safe_context.get("task") or "").strip() == "ai_redecision":
            return (
                "You are the AITS final AI authority re-evaluating a prior scenario.\n"
                "ETA expiry or invalidation is a request for judgment, never a direct trade action.\n"
                "Compare prior_decision, current_state, and delta_since_prior_decision.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, sell_ratio, buy_amount_krw, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
                "Allowed action values: hold, wait, sell, reduce, add, buy, rotate, stop_loss, take_profit.\n"
                "If evidence is incomplete, choose wait or hold with a new ETA and explicit invalidation conditions.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        if str(safe_context.get("task") or "").strip() == "rotation_decision":
            return (
                "You are the AITS final AI decision authority for managed-pool rotation.\n"
                "BASIC has collected rotation score evidence only. normalized_rotation_score is a trigger, not action.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, replace_symbol, rotate_to_symbol, sell_ratio, buy_amount_krw, risk_notes, invalidation_conditions.\n"
                "Allowed action values: rotate, wait, hold, replace, reduce_and_rotate, reject.\n"
                "Protected, user-added, live holding, or external holding rows must not be removed by simple replacement.\n"
                "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        if str(safe_context.get("task") or "").strip() == "managed_pool_promotion_decision":
            return (
                "You are the AITS final AI decision authority for managed-pool promotion.\n"
                "BASIC has collected candidate and portfolio data only. Decide whether the candidate should enter the Managed Pool.\n"
                "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
                "execution_plan, replace_symbol, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
                "Allowed action values: promote, reject, wait, replace, rotate_review, hold.\n"
                "Do not decide from scanner score alone. Use market context, current pool, holdings protection, cap, and alternatives together.\n"
                "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
                "Context JSON:\n"
                + json.dumps(safe_context, ensure_ascii=False, default=str)
            )
        return (
            "You are the AITS final AI decision authority for live position management.\n"
            "BASIC has collected data only. Decide action; do not claim execution.\n"
            "Return only compact JSON with keys: action, confidence, reason_ko, eta_seconds, "
            "sell_ratio, buy_amount_krw, rotate_to_symbol, risk_notes, invalidation_conditions.\n"
            "Allowed action values: hold, wait, sell, reduce, add, buy, rotate, stop_loss, take_profit.\n"
            "Use pnl, RSI, MACD, volume, volatility, portfolio cap, alternatives, and risk context together; "
            "do not decide from pnl threshold alone.\n"
            "If data is insufficient, choose wait or hold with eta_seconds and reason_ko.\n"
            "Context JSON:\n"
            + json.dumps(safe_context, ensure_ascii=False, default=str)
        )

    def _call_openai_position_management_decision(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("openai_live_call_disabled")
        api_key = self._get_config_api_key("openai")
        if not api_key:
            raise NotImplementedError("openai_api_key_missing")
        model = os.getenv("AITS_OPENAI_POSITION_DECISION_MODEL", os.getenv("AITS_OPENAI_VERIFY_MODEL", "gpt-4o-mini"))
        payload = {
            "model": model,
            "temperature": 0.1,
            "max_tokens": 420,
            "messages": [
                {"role": "system", "content": "Return only JSON. You are an AI portfolio decision engine. Do not execute trades."},
                {"role": "user", "content": prompt},
            ],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        usage = data.get("usage") or {}
        return {
            "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "response_id": data.get("id") or "",
            "usage_input_tokens": usage.get("prompt_tokens"),
            "usage_output_tokens": usage.get("completion_tokens"),
            "usage_total_tokens": usage.get("total_tokens"),
        }

    def _call_gemini_position_management_decision(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("gemini_live_call_disabled")
        api_key = self._get_config_api_key("gemini")
        if not api_key:
            raise NotImplementedError("gemini_api_key_missing")
        model = os.getenv("AITS_GEMINI_POSITION_DECISION_MODEL", os.getenv("AITS_GEMINI_VERIFY_MODEL", "gemini-2.0-flash"))
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 420},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = ((candidates[0].get("content") or {}).get("parts") or [])
            content = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        usage = data.get("usageMetadata") or {}
        return {
            "content": content,
            "response_id": str(data.get("responseId") or ""),
            "usage_input_tokens": usage.get("promptTokenCount"),
            "usage_output_tokens": usage.get("candidatesTokenCount"),
            "usage_total_tokens": usage.get("totalTokenCount"),
        }

    def _parse_position_management_decision_response(self, raw_response: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = dict(context or {})
        text = str(raw_response or "").strip()
        parsed: Dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(text[start:end + 1])
                    except Exception:
                        parsed = {}
        allowed = AI_DECISION_ALLOWED_ACTIONS
        action = str(parsed.get("action") or parsed.get("decision") or "").strip().lower()
        if action not in allowed:
            action = "wait"
        try:
            confidence = float(parsed.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        try:
            eta_seconds = int(float(parsed.get("eta_seconds") or 300))
        except Exception:
            eta_seconds = 300
        try:
            sell_ratio = float(parsed.get("sell_ratio") or 0.0)
        except Exception:
            sell_ratio = 0.0
        sell_ratio = max(0.0, min(1.0, sell_ratio))
        try:
            buy_amount_krw = float(parsed.get("buy_amount_krw") or 0.0)
        except Exception:
            buy_amount_krw = 0.0
        reason_ko = str(parsed.get("reason_ko") or parsed.get("reason") or "").strip()
        if not reason_ko:
            reason_ko = "AI 판단 근거가 비어 있어 실행하지 않고 대기합니다."
            action = "wait"
        raw_decision = {
            "action": action,
            "confidence": confidence,
            "reason_ko": reason_ko[:800],
            "eta_seconds": eta_seconds,
            "sell_ratio": sell_ratio,
            "buy_amount_krw": max(0.0, buy_amount_krw),
            "rotate_to_symbol": str(parsed.get("rotate_to_symbol") or "").strip().upper(),
            "replace_symbol": str(parsed.get("replace_symbol") or parsed.get("replace_target_symbol") or "").strip().upper(),
            "execution_plan": parsed.get("execution_plan") if isinstance(parsed.get("execution_plan"), dict) else {},
            "risk_notes": str(parsed.get("risk_notes") or "")[:800],
            "invalidation_conditions": parsed.get("invalidation_conditions") or [],
            "blocker": "",
        }
        validation = validate_ai_decision_response(
            raw_decision,
            provider=str(context.get("provider") or ""),
            task=str(context.get("task") or "manage_position_decision"),
            symbol=str(context.get("symbol") or ""),
            candidates=context.get("candidates"),
        )
        return dict(validation.get("decision") or raw_decision)

    def _build_local_position_management_decision(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        context = dict(context or {})
        symbol = str(context.get("symbol") or "").strip().upper()
        task = str(context.get("task") or "").strip()
        if task == "rotation_decision":
            rotation_candidate = context.get("rotation_candidate") if isinstance(context.get("rotation_candidate"), dict) else {}
            old_position = context.get("old_position") if isinstance(context.get("old_position"), dict) else {}
            new_candidate = context.get("new_candidate") if isinstance(context.get("new_candidate"), dict) else {}
            old_symbol = str(rotation_candidate.get("old_symbol") or old_position.get("symbol") or symbol or "").strip().upper()
            new_symbol = str(rotation_candidate.get("new_symbol") or new_candidate.get("symbol") or "").strip().upper()
            gap = _clamp_float(rotation_candidate.get("score_gap"), lo=-100.0, hi=100.0, default=0.0)
            new_score = _clamp_float(
                rotation_candidate.get("new_score") or new_candidate.get("scanner_score") or new_candidate.get("basic_score"),
                lo=0.0,
                hi=100.0,
                default=0.0,
            )
            source_type = str(old_position.get("source_type") or "").strip()
            old_protected = bool(old_position.get("protected") or old_position.get("managed_protected"))
            old_holding = bool(old_position.get("holding"))
            execution_plan: Dict[str, Any] = {
                "replace_symbol": old_symbol,
                "rotate_to_symbol": new_symbol,
                "rotation_execution": False,
                "execution_pending": False,
            }
            action = "wait"
            confidence = 0.52
            reason = "로테이션 후보는 추가 관찰 후 다시 판단합니다."
            if old_holding or old_protected or source_type in {"user_added", "live_holding", "external_holding"}:
                action = "wait"
                confidence = 0.62
                execution_plan["replace_symbol"] = ""
                reason = "보유/보호 종목은 단순 로테이션 교체 대상에서 제외합니다."
            elif old_symbol and new_symbol and gap >= 8.0 and new_score >= 65.0:
                action = "replace"
                confidence = min(0.90, 0.64 + min(gap, 25.0) / 100.0)
                reason = f"{new_symbol} 후보가 {old_symbol}보다 우위라 관리종목 교체 검토를 승인합니다."
            elif old_symbol and new_symbol and gap >= 5.0:
                action = "wait"
                confidence = 0.57
                reason = f"{new_symbol} 후보가 우위지만 교체 확정 전 추가 관찰이 필요합니다."
            else:
                action = "reject"
                confidence = 0.60
                execution_plan["replace_symbol"] = ""
                reason = "로테이션 점수 격차가 충분하지 않아 교체하지 않습니다."
            return {
                "schema": "aits_position_management_decision_v1",
                "task": task,
                "provider": "local",
                "action": action,
                "confidence": round(float(confidence), 4),
                "reason_ko": reason,
                "eta_seconds": 600,
                "execution_plan": execution_plan,
                "replace_symbol": execution_plan.get("replace_symbol", ""),
                "rotate_to_symbol": execution_plan.get("rotate_to_symbol", ""),
                "sell_ratio": _clamp_float(execution_plan.get("sell_ratio"), lo=0.0, hi=1.0, default=0.0),
                "buy_amount_krw": 0.0,
                "risk_notes": "LOCAL rotation gate decision; no order submit in this stage.",
                "invalidation_conditions": [
                    "rotation_score_gap_reverses",
                    "protected_or_holding_status_changes",
                    "market_data_stale",
                ],
                "actual_order": False,
                "submitted": 0,
            }
        if task == "managed_pool_promotion_decision":
            candidate = context.get("candidate") if isinstance(context.get("candidate"), dict) else {}
            constraints = context.get("constraints") if isinstance(context.get("constraints"), dict) else {}
            comparison = context.get("comparison") if isinstance(context.get("comparison"), dict) else {}
            symbol = str(candidate.get("symbol") or symbol or "").strip().upper()
            score = _clamp_float(
                candidate.get("scanner_score") or candidate.get("basic_score"),
                lo=0.0,
                hi=100.0,
                default=0.0,
            )
            trade_value = _clamp_float(candidate.get("trade_value"), lo=0.0, hi=10**15, default=0.0)
            current_count = int(_clamp_float((context.get("current_managed_pool") or {}).get("count"), 0.0))
            max_count = int(_clamp_float((context.get("current_managed_pool") or {}).get("max_count"), 0.0))
            has_free_slot = max_count <= 0 or current_count < max_count
            replace_symbol = str(comparison.get("weakest_non_holding_symbol") or "").strip().upper()
            action = "wait"
            confidence = 0.48
            execution_plan: Dict[str, Any] = {}
            reason = f"{symbol or '候補'} 관리종목 편입은 추가 시장 확인을 기다립니다."
            if score >= 70.0 and (trade_value > 0.0 or candidate.get("market_reason")):
                if has_free_slot:
                    action = "promote"
                    confidence = 0.66
                    reason = f"{symbol} 후보는 점수와 시장 근거가 충분해 관리종목 편입을 승인합니다."
                elif replace_symbol:
                    action = "replace"
                    confidence = 0.61
                    execution_plan["replace_symbol"] = replace_symbol
                    reason = f"{symbol} 후보는 기존 비보유 관리종목보다 우위라 교체 검토를 승인합니다."
                else:
                    reason = f"{symbol} 후보는 매력적이지만 최대 관리종목수 여유가 없어 대기합니다."
            elif score < 60.0:
                action = "reject"
                confidence = 0.58
                reason = f"{symbol} 후보는 현재 점수와 시장 근거가 부족해 편입하지 않습니다."
            return {
                "schema": "aits_position_management_decision_v1",
                "action": action,
                "confidence": confidence,
                "reason_ko": reason,
                "eta_seconds": 300,
                "sell_ratio": 0.0,
                "buy_amount_krw": 0.0,
                "rotate_to_symbol": "",
                "replace_symbol": execution_plan.get("replace_symbol", ""),
                "execution_plan": execution_plan,
                "risk_notes": "LOCAL AI promotion decision; Basic candidate score is trigger data only.",
                "invalidation_conditions": [],
                "blocker": "",
                "actual_order": False,
                "submitted": 0,
            }
        if task == "ai_redecision":
            current_state = context.get("current_state") if isinstance(context.get("current_state"), dict) else {}
            context = dict(context)
            context["position"] = current_state.get("position") if isinstance(current_state.get("position"), dict) else {}
            context["market"] = current_state.get("market") if isinstance(current_state.get("market"), dict) else {}
            context["indicators"] = current_state.get("indicators") if isinstance(current_state.get("indicators"), dict) else {}
            context["portfolio"] = current_state.get("portfolio") if isinstance(current_state.get("portfolio"), dict) else {}
            context["requested_decision"] = {
                "trigger": str(context.get("trigger_reason") or "ai_redecision"),
                "allowed_actions": list((context.get("requested_decision") or {}).get("allowed_actions") or []),
            }
        trigger = str((context.get("requested_decision") or {}).get("trigger") or context.get("trigger") or "").strip()
        position = context.get("position") if isinstance(context.get("position"), dict) else {}
        market = context.get("market") if isinstance(context.get("market"), dict) else {}
        indicators = context.get("indicators") if isinstance(context.get("indicators"), dict) else {}
        pnl_pct = _clamp_float(position.get("pnl_pct"), lo=-1000.0, hi=1000.0, default=0.0)
        rsi = _clamp_float(indicators.get("RSI") or indicators.get("rsi"), lo=0.0, hi=100.0, default=0.0)
        trend_strength = _clamp_float(indicators.get("trend_strength"), lo=-100.0, hi=100.0, default=0.0)
        volume_change = _clamp_float(market.get("volume_change"), lo=-1000.0, hi=1000.0, default=0.0)
        action = "wait"
        confidence = 0.45
        eta_seconds = 600
        reason = (
            f"{symbol or '보유종목'}은 {trigger or '관리'} 조건으로 AI 판단이 요청됐지만, "
            "LOCAL AI는 추가 시장 확증을 기다리도록 판단했습니다."
        )
        if trigger in {"take_profit", "strong_take_profit"} and rsi >= 70.0 and volume_change < 0.0 and trend_strength < 0.0:
            action = "reduce"
            confidence = 0.62
            eta_seconds = 0
            reason = f"{symbol} 수익 구간에서 RSI 과열, 거래량 둔화, 추세 약화가 함께 보여 일부 익절이 적절합니다."
        elif trigger in {"stop_loss", "emergency_stop_loss"} and trend_strength < -30.0:
            action = "stop_loss"
            confidence = 0.64 if pnl_pct <= -20.0 else 0.58
            eta_seconds = 0
            reason = f"{symbol} 손실 구간에서 하락 추세가 강해 손절 검토가 필요합니다."
        return {
            "schema": "aits_position_management_decision_v1",
            "action": action,
            "confidence": confidence,
            "reason_ko": reason,
            "eta_seconds": eta_seconds,
            "sell_ratio": 1.0 if trigger == "emergency_stop_loss" and action == "stop_loss" else (0.5 if action in {"reduce", "sell", "stop_loss", "take_profit"} else 0.0),
            "buy_amount_krw": 0.0,
            "rotate_to_symbol": "",
            "execution_plan": {},
            "risk_notes": "LOCAL AI decision; no direct threshold execution.",
            "invalidation_conditions": [],
            "blocker": "",
            "actual_order": False,
            "submitted": 0,
        }

    def _build_managed_pool_opinion_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        context = dict(context or {})
        safe_context = {
            "schema": context.get("schema") or "managed_pool_ai_opinion_request_v1",
            "symbol": context.get("symbol"),
            "display_name": context.get("display_name"),
            "aits_score": context.get("aits_score"),
            "status": context.get("status"),
            "status_reason": context.get("status_reason"),
            "managed_source": context.get("managed_source"),
            "candidate_reason": context.get("candidate_reason"),
            "recent_move": context.get("recent_move"),
            "safety_constraints": context.get("safety_constraints"),
        }
        return (
            "You are generating an AITS Managed Pool operation opinion for display only.\n"
            "This is NOT router verification and NOT an order approval request.\n"
            "Never ask to buy, sell, cancel, retry, or execute an order.\n"
            "Return only compact JSON with keys: opinion, status_label, confidence, reason, next_action.\n"
            "Allowed opinion values: watch, buy_wait, rotate_review, sell_review, data_insufficient.\n"
            "Allowed Korean status_label values: 관망, 매수대기, 교체검토, 매도검토, 데이터부족.\n"
            "The reason must be user-facing market/managed-pool rationale, not an execution-block reason.\n"
            "The next_action must be review-only and must include no order execution.\n"
            "Context JSON:\n"
            + json.dumps(safe_context, ensure_ascii=False, default=str)
        )

    def _call_openai_managed_pool_opinion(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("openai_live_call_disabled")
        api_key = self._get_config_api_key("openai")
        if not api_key:
            raise NotImplementedError("openai_api_key_missing")
        model = os.getenv("AITS_OPENAI_OPINION_MODEL", os.getenv("AITS_OPENAI_VERIFY_MODEL", "gpt-4o-mini"))
        payload = {
            "model": model,
            "temperature": 0.2,
            "max_tokens": 260,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON. You write Korean Managed Pool review opinions. Never execute trades.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            _safe_log_info("[AITS][ManagedPoolOpinionOpenAI] step=before_request")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage") or {}
            return {
                "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "response_id": data.get("id") or "",
                "usage_input_tokens": usage.get("prompt_tokens"),
                "usage_output_tokens": usage.get("completion_tokens"),
                "usage_total_tokens": usage.get("total_tokens"),
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800].lower()
            if exc.code == 429 or "quota" in body or "rate limit" in body or "insufficient_quota" in body:
                raise RuntimeError("openai_quota_exceeded")
            if exc.code in (401, 403) or "invalid api key" in body or "incorrect api key" in body:
                raise RuntimeError("openai_api_key_invalid")
            if exc.code == 400:
                raise RuntimeError("openai_bad_request")
            raise

    def _call_gemini_managed_pool_opinion(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        if not (real_call_enabled and one_shot_enabled):
            raise NotImplementedError("gemini_live_call_disabled")
        api_key = self._get_config_api_key("gemini")
        if not api_key:
            raise NotImplementedError("gemini_api_key_missing")
        model = os.getenv("AITS_GEMINI_OPINION_MODEL", os.getenv("AITS_GEMINI_VERIFY_MODEL", "gemini-1.5-flash"))
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 260},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            _safe_log_info("[AITS][ManagedPoolOpinionGemini] step=before_request")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = ""
            candidates = data.get("candidates") or []
            if candidates:
                parts = ((candidates[0].get("content") or {}).get("parts") or [])
                content = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
            usage = data.get("usageMetadata") or {}
            return {
                "content": content,
                "response_id": str(data.get("responseId") or ""),
                "usage_input_tokens": usage.get("promptTokenCount"),
                "usage_output_tokens": usage.get("candidatesTokenCount"),
                "usage_total_tokens": usage.get("totalTokenCount"),
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800].lower()
            if exc.code == 429 or "quota" in body or "rate limit" in body:
                raise RuntimeError("gemini_quota_exceeded")
            if exc.code in (401, 403) or "api key not valid" in body or "invalid api key" in body:
                raise RuntimeError("gemini_api_key_invalid")
            if exc.code == 400:
                raise RuntimeError("gemini_bad_request")
            raise

    def _parse_managed_pool_opinion_response(self, raw_response: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        text = str(raw_response or "").strip()
        parsed: Dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(text[start:end + 1])
                    except Exception:
                        parsed = {}
        opinion_raw = str(parsed.get("opinion") or parsed.get("recommendation") or parsed.get("status") or "").strip().lower()
        status_raw = str(parsed.get("status_label") or "").strip()
        status_map = {
            "watch": ("watch", "관망"),
            "hold": ("watch", "관망"),
            "관망": ("watch", "관망"),
            "buy_wait": ("buy_wait", "매수대기"),
            "buy": ("buy_wait", "매수대기"),
            "매수대기": ("buy_wait", "매수대기"),
            "rotate_review": ("rotate_review", "교체검토"),
            "rotation": ("rotate_review", "교체검토"),
            "교체검토": ("rotate_review", "교체검토"),
            "sell_review": ("sell_review", "매도검토"),
            "sell": ("sell_review", "매도검토"),
            "매도검토": ("sell_review", "매도검토"),
            "data_insufficient": ("data_insufficient", "데이터부족"),
            "insufficient": ("data_insufficient", "데이터부족"),
            "데이터부족": ("data_insufficient", "데이터부족"),
        }
        opinion, status_label = status_map.get(opinion_raw) or status_map.get(status_raw) or ("data_insufficient", "데이터부족")
        try:
            confidence = float(parsed.get("confidence"))
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        reason = str(parsed.get("reason") or parsed.get("rationale") or "").strip()
        if not reason or reason.lower() in {"execution not allowed", "order execution not allowed"}:
            reason = "관리종목 운용 의견 생성을 위한 근거가 제한적입니다. 추가 데이터 확인 후 참고만 합니다."
        next_action = str(parsed.get("next_action") or "").strip()
        if not next_action:
            next_action = "운용 의견 참고만 수행; 주문 실행 없음"
        return {
            "opinion": opinion,
            "status_label": status_label,
            "confidence": confidence,
            "reason": reason[:500],
            "next_action": next_action[:300],
        }

    def _with_ai_result_contract(self, result: Dict[str, Any]) -> Dict[str, Any]:
        result["suggestion_only"] = True
        result["applied_to_action"] = False
        try:
            print(
                "[AITS][AIEngineProvider] ai_result_contract "
                "| suggestion_only=True | applied_to_action=False"
            )
        except Exception:
            pass
        return result

    def _build_router_verification_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """
        Build compact prompt for Router verification.

        Token policy:
        - RouterSummary 수준의 compact context만 사용한다.
        - 장문 시장 데이터/캔들 원본/전체 로그는 포함하지 않는다.
        """
        context = context or {}
        allowed = ", ".join(sorted(AI_VERIFICATION_ALLOWED_SUGGESTIONS))
        lines = [
            "You are a safety verifier for an AI trading decision router.",
            "Return only a compact JSON object.",
            "Do not place orders.",
            "Do not execute trades.",
            "Do not assume authority over final action.",
            f"Allowed suggestion values: {allowed}",
            "",
            "Context:",
        ]

        for key in (
            "router_version",
            "final_action",
            "final_confidence",
            "fusion_signal",
            "performance_boost",
            "soft_override_candidate",
            "dryrun_compare",
            "mismatch_reason",
            "market_regime",
            "candidate_count",
            "positions_count",
            "symbol",
            "execution_allowed",
            "safety_note",
        ):
            if key in context:
                lines.append(f"- {key}: {context.get(key)}")

        lines.extend(
            [
                "",
                "Return JSON format:",
                '{"suggestion":"confirm","reason":"short reason","risk_note":"short risk note"}',
            ]
        )
        return "\n".join(lines)

    def _call_openai_router_verification(self, prompt: str, context: Dict[str, Any]) -> Any:
        """
        OpenAI router verification call.

        Safety:
        - 기존 OpenAI 호출 메서드가 명확히 있을 때만 위임한다.
        - 없으면 NotImplementedError로 안전하게 skip 처리된다.
        - 여기서 신규 SDK/키 로딩/설정 변경을 하지 않는다.
        """
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        api_call_enabled = real_call_enabled and one_shot_enabled
        if api_call_enabled:
            gate_reason = "enabled"
        elif real_call_enabled:
            gate_reason = "missing_one_shot"
        else:
            gate_reason = "dryrun_mode"
        _safe_log_info(
            "[AITS][AIEngineProvider] api_call_entry "
            f"| provider=openai | enabled={api_call_enabled} | reason={gate_reason}"
        )
        if not api_call_enabled:
            raise NotImplementedError("openai_live_call_disabled")

        api_key = self._get_config_api_key("openai")
        if not api_key:
            raise NotImplementedError("openai_api_key_missing")

        model = os.getenv("AITS_OPENAI_VERIFY_MODEL", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"

        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": 120,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON. You are a trading router verifier. Never execute trades.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            _safe_log_info("[AITS][OpenAIHTTP] step=before_request")
            with urllib.request.urlopen(req, timeout=20) as resp:
                response_text = resp.read().decode("utf-8")
                _safe_log_info(f"[AITS][OpenAIHTTP] status={resp.status}")
                _safe_log_info(
                    "[AITS][OpenAIHTTP] body="
                    + str(response_text)[:300].replace("\n", " ").replace("\r", " ")
                )
                data = json.loads(response_text)
            _raw_preview = str(data).replace("\n", " ").replace("\r", " ")[:500]
            logging.getLogger("aits").info(
                "[AITS][OpenAIRaw] "
                f"preview={_raw_preview}"
            )
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800]
            body_lower = body.lower()

            reason = f"openai_http_error:{exc.code}"

            if exc.code == 429 or "quota" in body_lower or "rate limit" in body_lower or "too many requests" in body_lower or "insufficient_quota" in body_lower:
                reason = "openai_quota_exceeded"
            elif exc.code in (401, 403) or "invalid api key" in body_lower or "incorrect api key" in body_lower:
                reason = "openai_api_key_invalid"
            elif exc.code == 400:
                reason = "openai_bad_request"

            _safe_log_info(f"[AITS][OpenAIHTTP] status={exc.code}")
            _safe_log_info(
                "[AITS][OpenAIHTTP] body="
                + str(body)[:300].replace("\n", " ").replace("\r", " ")
            )
            _safe_log_info(
                "[AITS][OpenAIHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            _safe_log_info(
                "[AITS][OpenAIHTTP] classified_error | "
                f"code={exc.code} | reason={reason}"
            )
            raise RuntimeError(reason)
        except Exception as exc:
            _safe_log_info(
                "[AITS][OpenAIHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            raise
        finally:
            os.environ["AITS_AI_VERIFY_LIVE_ONCE"] = "0"

    def _call_gemini_router_verification(self, prompt: str, context: Dict[str, Any]) -> Any:
        """
        Gemini router verification call.

        Safety:
        - 기존 Gemini 호출 메서드가 명확히 있을 때만 위임한다.
        - 없으면 NotImplementedError로 안전하게 skip 처리된다.
        - 여기서 신규 SDK/키 로딩/설정 변경을 하지 않는다.
        """
        real_call_enabled = str(os.getenv("AITS_ENABLE_REAL_AI_CALL", "")).strip() == "1"
        one_shot_enabled = str(os.getenv("AITS_REAL_AI_ONE_SHOT", "")).strip() == "1"
        api_call_enabled = real_call_enabled and one_shot_enabled
        if api_call_enabled:
            gate_reason = "enabled"
        elif real_call_enabled:
            gate_reason = "missing_one_shot"
        else:
            gate_reason = "dryrun_mode"
        _safe_log_info(
            "[AITS][AIEngineProvider] api_call_entry "
            f"| provider=gemini | enabled={api_call_enabled} | reason={gate_reason}"
        )
        if not api_call_enabled:
            raise NotImplementedError("gemini_live_call_disabled")

        api_key = self._get_config_api_key("gemini")
        if not api_key:
            raise NotImplementedError("gemini_api_key_missing")

        model = os.getenv("AITS_GEMINI_VERIFY_MODEL", "gemini-2.0-flash")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Return only JSON. You are a trading router verifier. "
                                "Never execute trades.\n\n" + prompt
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 120,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            _safe_log_info("[AITS][GeminiHTTP] step=before_request")
            with urllib.request.urlopen(req, timeout=20) as resp:
                response_text = resp.read().decode("utf-8")
                _safe_log_info(f"[AITS][GeminiHTTP] status={resp.status}")
                _safe_log_info(
                    "[AITS][GeminiHTTP] body="
                    + str(response_text)[:300].replace("\n", " ").replace("\r", " ")
                )
                data = json.loads(response_text)
            _raw_preview = str(data).replace("\n", " ").replace("\r", " ")[:500]
            logging.getLogger("aits").info(
                "[AITS][GeminiRaw] "
                f"preview={_raw_preview}"
            )
            return (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:800]
            body_lower = body.lower()

            reason = f"gemini_http_error:{exc.code}"

            if exc.code == 429 or "quota" in body_lower or "rate limit" in body_lower or "too many requests" in body_lower:
                reason = "gemini_quota_exceeded"
            elif exc.code in (401, 403) or "api key not valid" in body_lower or "api_key_invalid" in body_lower:
                reason = "gemini_api_key_invalid"
            elif exc.code == 400:
                reason = "gemini_bad_request"

            _safe_log_info(f"[AITS][GeminiHTTP] status={exc.code}")
            _safe_log_info(
                "[AITS][GeminiHTTP] body="
                + str(body)[:300].replace("\n", " ").replace("\r", " ")
            )
            _safe_log_info(
                "[AITS][GeminiHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            _safe_log_info(
                "[AITS][GeminiHTTP] classified_error | "
                f"code={exc.code} | reason={reason}"
            )
            raise RuntimeError(reason)
        except Exception as exc:
            _safe_log_info(
                "[AITS][GeminiHTTP] error "
                f"type={type(exc).__name__} | "
                f"msg={str(exc)[:200]}"
            )
            raise
        finally:
            os.environ["AITS_AI_VERIFY_LIVE_ONCE"] = "0"

    def _parse_router_verification_response(self, *, raw_response: Any = None, provider: Any = None) -> Dict[str, Any]:
        """
        Parse AI verifier response into standard suggestion dict.
        """
        import json

        provider = str(provider or "unknown").strip().lower()

        if isinstance(raw_response, dict):
            parsed = raw_response
        else:
            text = str(raw_response or "").strip()
            if not text:
                return self._with_ai_result_contract({
                    "suggestion": "skip",
                    "reason": "empty_response",
                    "provider": provider,
                    "applied": False,
                })
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = {
                    "suggestion": "confirm",
                    "reason": "non_json_response_default_confirm",
                    "risk_note": text[:500],
                }

        suggestion = str(parsed.get("suggestion") or parsed.get("decision") or "confirm").strip().lower()
        if suggestion not in AI_VERIFICATION_ALLOWED_SUGGESTIONS:
            suggestion = "confirm"

        return self._with_ai_result_contract({
            "suggestion": suggestion,
            "reason": str(parsed.get("reason") or parsed.get("summary") or "provider_response")[:500],
            "risk_note": str(parsed.get("risk_note") or parsed.get("note") or "")[:500],
            "provider": provider,
            "applied": False,
            "raw_response": parsed,
        })

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "api_required": self.api_required,
            "ready": self.is_ready(),
            "ready_reason": self.get_ready_reason(),
        }

    def get_ready_reason(self) -> str:
        return self.ready_reason


class LocalProvider(AIEngineProvider):
    name = "local"
    api_required = False

    def is_ready(self) -> bool:
        return True

    def get_ready_reason(self) -> str:
        return "Local Engine ready"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        raw_context = dict(context or {})
        rule_action = str(
            raw_context.get("rule_action")
            or raw_context.get("original_action")
            or ""
        ).strip().lower()
        if rule_action == "watch":
            normalized_rule_action = "wait"
        else:
            normalized_rule_action = rule_action
        rule_confidence = _clamp_float(
            raw_context.get("rule_confidence"),
            lo=0.0,
            hi=1.0,
            default=0.50,
        )
        market_regime = str(raw_context.get("market_regime") or "").strip().lower()
        candidate_count = _safe_int(raw_context.get("candidate_count"), 0)
        positions_count = _safe_int(raw_context.get("positions_count"), 0)
        shadow_action = "hold"
        shadow_rule = "hold_wait"
        risk = "medium"
        confidence = _clamp_float(rule_confidence, lo=0.45, hi=0.60, default=0.50)
        reason = (
            "Local shadow HOLD: "
            f"conditions not strong enough, regime={market_regime or 'unknown'}, "
            f"candidates={candidate_count}"
        )
        buy_regimes = ("sideways", "bull", "alt", "neutral")
        sell_regimes = ("bear", "crash", "risk_off")
        if (
            positions_count == 0
            and candidate_count >= 3
            and market_regime in buy_regimes
            and normalized_rule_action in ("wait", "hold", "buy")
            and rule_confidence >= 0.50
        ):
            shadow_action = "buy"
            shadow_rule = "buy_candidate"
            confidence = min(0.70, max(0.55, rule_confidence))
            risk = "medium" if market_regime in buy_regimes else "high"
            reason = (
                "Local shadow BUY candidate: "
                f"no positions, candidates={candidate_count}, "
                f"regime={market_regime}, rule={rule_action or 'unknown'}"
            )
        elif (
            positions_count > 0
            and market_regime in sell_regimes
            and normalized_rule_action in ("sell", "reduce", "hold", "wait")
            and rule_confidence >= 0.45
        ):
            shadow_action = "sell"
            shadow_rule = "sell_candidate"
            confidence = min(0.70, max(0.55, rule_confidence))
            risk = "high"
            reason = (
                "Local shadow SELL candidate: "
                f"positions={positions_count}, regime={market_regime}, "
                f"rule={rule_action or 'unknown'}"
            )
        elif normalized_rule_action in ("wait", "watch"):
            shadow_action = "wait"
            reason = (
                "Local shadow WAIT: "
                f"conditions not strong enough, regime={market_regime or 'unknown'}, "
                f"candidates={candidate_count}"
            )
        risk_hint = _build_local_risk_hint(
            shadow_action=shadow_action,
            market_regime=market_regime,
            candidate_count=candidate_count,
        )
        shadow_summary = _trim_text(
            "Local shadow: "
            f"rule={rule_action or 'unknown'}, "
            f"regime={market_regime or 'unknown'}, "
            f"candidates={candidate_count}, "
            f"positions={positions_count}, "
            f"conf={confidence:.2f}",
            160,
        )
        return AIEngineDecision(
            action=shadow_action,
            confidence=confidence,
            risk=risk,
            reason=reason,
            engine="local",
            raw={
                "mode": "rule_shadow_v1",
                "has_context": bool(raw_context),
                "rule_action": rule_action,
                "rule_confidence": rule_confidence,
                "rule_reason": str(raw_context.get("rule_reason") or ""),
                "market_regime": market_regime,
                "positions_count": positions_count,
                "candidate_count": candidate_count,
                "portfolio_value": raw_context.get("portfolio_value"),
                "cycle": raw_context.get("cycle"),
                "shadow_rule": shadow_rule,
                "execution_allowed": False,
                "note": "shadow only; final decision unchanged",
                "shadow_summary": shadow_summary,
                "risk_hint": risk_hint,
            },
        )


class OpenAIProvider(AIEngineProvider):
    name = "openai"
    api_required = True

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def get_ready_reason(self) -> str:
        if self.is_ready():
            return "OpenAI API key configured"
        return "OpenAI API key missing"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="OpenAIProvider shadow only; API call disabled",
            engine="openai",
            raw={"mode": "shadow_provider", "api_call": "disabled"},
        )


class GeminiProvider(AIEngineProvider):
    name = "gemini"
    api_required = True

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def get_ready_reason(self) -> str:
        if self.is_ready():
            return "Gemini API key configured"
        return "Gemini API key missing"

    def decide(self, context: Optional[Dict[str, Any]] = None) -> AIEngineDecision:
        return AIEngineDecision(
            action="hold",
            confidence=0.0,
            risk="medium",
            reason="GeminiProvider shadow only; API call disabled",
            engine="gemini",
            raw={"mode": "shadow_provider", "api_call": "disabled"},
        )


def normalize_provider_name(provider_name: Any) -> str:
    provider_norm = str(provider_name or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    if provider_norm in ("local", "basic"):
        return "local"
    return "local"


def normalize_provider_label(provider_name: Any) -> str:
    provider_norm = str(provider_name or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    return "basic"


def _clamp_float(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    try:
        if value is None:
            result = default
        else:
            result = float(value)
    except (TypeError, ValueError):
        result = default
    if result < lo:
        return lo
    if result > hi:
        return hi
    return result


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_local_risk_hint(
    *,
    shadow_action: str,
    market_regime: str,
    candidate_count: int,
) -> str:
    action = str(shadow_action or "").strip().lower()
    if action == "buy":
        return "buy_candidate_shadow"
    if action == "sell":
        return "sell_candidate_shadow"
    regime = str(market_regime or "").strip().lower()
    if regime in ("bear", "crash", "risk_off", "risk-off"):
        return "defensive"
    if candidate_count >= 5:
        return "watchlist_active"
    return "neutral"


def _trim_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _read_value(root: Any, key: str) -> str:
    try:
        if root is None:
            return ""
        if isinstance(root, dict):
            value = root.get(key)
        else:
            value = getattr(root, key, "")
        return str(value or "").strip()
    except Exception:
        return ""


def _iter_roots(*roots: Any):
    seen = set()
    stack = [root for root in roots if root is not None]
    while stack:
        root = stack.pop(0)
        ident = id(root)
        if ident in seen:
            continue
        seen.add(ident)
        yield root
        try:
            if isinstance(root, dict):
                children = [root.get(key) for key in ("strategy", "settings", "prefs", "config")]
            else:
                children = [getattr(root, key, None) for key in ("strategy", "settings", "prefs", "config")]
            stack.extend(child for child in children if child is not None)
        except Exception:
            continue


def _find_api_key(
    candidates: tuple[str, ...],
    *roots: Any,
    env_keys: tuple[str, ...] = (),
    provider: Any = None,
) -> str:
    resolved_key = ""
    key_method = "missing"
    for root in _iter_roots(*roots):
        for key in candidates:
            value = _read_value(root, key)
            if value:
                resolved_key = value
                key_method = "settings"
                break
        if resolved_key:
            break
    if not resolved_key:
        for env_key in env_keys:
            value = (os.getenv(env_key) or "").strip()
            if value:
                resolved_key = value
                key_method = "environment"
                break
    try:
        _provider_name = normalize_provider_label(provider)

        print(
            "[AITS][AIEngineProvider] key_resolution "
            f"| provider={_provider_name or 'unknown'} "
            f"| resolved={bool(resolved_key)} "
            f"| method={key_method}"
        )
    except Exception:
        pass
    return resolved_key


def build_default_provider_registry(
    settings: Optional[Any] = None,
    prefs: Optional[Any] = None,
    config: Optional[Any] = None,
) -> Dict[str, AIEngineProvider]:
    openai_api_key = _find_api_key(
        ("ai_openai_api_key", "openai_api_key", "gpt_api_key"),
        settings,
        prefs,
        config,
        env_keys=("OPENAI_API_KEY",),
        provider="openai",
    )
    gemini_api_key = _find_api_key(
        (
            "ai_gemini_api_key",
            "gemini_api_key",
            "google_api_key",
            "google_gemini_api_key",
        ),
        settings,
        prefs,
        config,
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        provider="gemini",
    )
    return {
        "local": LocalProvider(),
        "openai": OpenAIProvider(api_key=openai_api_key),
        "gemini": GeminiProvider(api_key=gemini_api_key),
    }


def get_provider(
    registry: Optional[Dict[str, AIEngineProvider]], provider_name: Any
) -> AIEngineProvider:
    try:
        provider_key = normalize_provider_name(provider_name)
        provider_label = normalize_provider_label(provider_name or provider_key)
        try:
            print(
                "[AITS][AIEngineProvider] provider_selected "
                f"| provider={provider_label}"
            )
        except Exception:
            pass
        providers = registry or {}
        provider = providers.get(provider_key) or providers.get("local")
        if provider is not None:
            return provider
    except Exception:
        pass
    return LocalProvider()
