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

    def __init__(self, api_key: str = "") -> None:
        self.api_key = str(api_key or "").strip()

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

            _openai_key = os.getenv("OPENAI_API_KEY")
            _gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

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
                        return {
                            "suggestion": "confirm",
                            "reason": "local_forced_confirm",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        }

                    if _r < 0.3:
                        return {
                            "suggestion": "reject_signal",
                            "reason": "local_forced_reject",
                            "risk_note": None,
                            "provider": "local",
                            "applied": False,
                        }
            except Exception:
                pass

            return {
                "suggestion": "skip",
                "reason": "local_provider_no_api_call",
                "risk_note": None,
                "provider": "local",
                "applied": False,
            }

        if provider not in ("openai", "gemini"):
            return {
                "suggestion": "skip",
                "reason": f"unsupported_provider:{provider}",
                "provider": provider,
                "applied": False,
            }

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
            return {
                "suggestion": "skip",
                "reason": str(exc) or f"{provider}_verifier_not_implemented",
                "provider": provider,
                "applied": False,
            }
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
            return {
                "suggestion": "skip",
                "reason": result_reason,
                "provider": provider,
                "applied": False,
                "error": error_reason,
            }

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
        if str(os.getenv("AITS_AI_VERIFY_LIVE_ONCE", "")).strip() != "1":
            raise NotImplementedError("openai_live_call_disabled")

        api_key = os.getenv("OPENAI_API_KEY")
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
        if str(os.getenv("AITS_AI_VERIFY_LIVE_ONCE", "")).strip() != "1":
            raise NotImplementedError("gemini_live_call_disabled")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
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
                return {
                    "suggestion": "skip",
                    "reason": "empty_response",
                    "provider": provider,
                    "applied": False,
                }
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

        return {
            "suggestion": suggestion,
            "reason": str(parsed.get("reason") or parsed.get("summary") or "provider_response")[:500],
            "risk_note": str(parsed.get("risk_note") or parsed.get("note") or "")[:500],
            "provider": provider,
            "applied": False,
            "raw_response": parsed,
        }

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
) -> str:
    for root in _iter_roots(*roots):
        for key in candidates:
            value = _read_value(root, key)
            if value:
                return value
    for env_key in env_keys:
        value = (os.getenv(env_key) or "").strip()
        if value:
            return value
    return ""


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
        providers = registry or {}
        provider = providers.get(provider_key) or providers.get("local")
        if provider is not None:
            return provider
    except Exception:
        pass
    return LocalProvider()
