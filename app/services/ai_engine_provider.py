from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, Optional


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
