from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.aits_state import AIDecisionState
from app.services.ai_engine_provider import (
    build_default_provider_registry,
    get_provider,
)

ROUTER_VERSION = "v0.5"
ROUTER_MODE = "shadow_provider"


@dataclass
class DecisionRouterResult:
    action: str
    symbol: Optional[str]
    confidence: float
    risk: str
    reason: str
    engine: str
    source: str
    amount_krw: float
    timestamp: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_action(action: str) -> str:
    action_norm = str(action or "").strip().lower()
    mapping = {
        "buy": "buy",
        "sell": "sell",
        "reduce": "reduce",
        "hold": "hold",
        "wait": "wait",
        "watch": "wait",
    }
    return mapping.get(action_norm, "hold")


def normalize_provider(provider: str) -> str:
    provider_norm = str(provider or "").strip().lower()
    if provider_norm in ("gpt", "openai"):
        return "openai"
    if provider_norm in ("gemini", "google"):
        return "gemini"
    if provider_norm in ("local", "basic"):
        return "local"
    return "local"


class DecisionRouter:
    def __init__(
        self,
        logger: Optional[Any] = None,
        provider_registry: Optional[Dict[str, Any]] = None,
        settings: Optional[Any] = None,
        prefs: Optional[Any] = None,
        config: Optional[Any] = None,
        mode: str = ROUTER_MODE,
    ) -> None:
        self.logger = logger
        self.provider_registry = provider_registry or build_default_provider_registry(
            settings=settings,
            prefs=prefs,
            config=config,
        )
        self.router_version = ROUTER_VERSION
        self.mode = str(mode or ROUTER_MODE).strip() or ROUTER_MODE

    def route(
        self,
        decision: Optional[Any],
        *,
        provider: str = "local",
        context: Optional[Dict[str, Any]] = None,
    ) -> AIDecisionState:
        engine = normalize_provider(provider)
        context_data = dict(context or {})
        provider_status = self.get_status_summary(engine)
        provider_shadow_decision = None
        provider_shadow_error = ""
        if self.mode == "shadow_provider":
            provider_obj = get_provider(self.provider_registry, engine)
            try:
                provider_shadow_decision = provider_obj.decide(context_data)
                self._safe_log_info(
                    "[AITS][DecisionRouter] provider_shadow | "
                    f"provider={engine} | "
                    f"action={getattr(provider_shadow_decision, 'action', '')} | "
                    f"confidence={self._safe_float(getattr(provider_shadow_decision, 'confidence', 0.0), 0.0):.3f} | "
                    "final=passthrough"
                )
            except Exception as exc:
                provider_shadow_error = str(exc)[:160]
                self._safe_log_info(
                    "[AITS][DecisionRouter] provider_shadow_failed | "
                    f"provider={engine} | error={provider_shadow_error} | fallback=passthrough"
                )
        if decision is None:
            routed = AIDecisionState(
                action="hold",
                action_bias="neutral",
                confidence=0.0,
                selected_strategy_logic="decision_router_null_fallback",
                ai_summary_for_user="DecisionRouter: reason missing",
                ai_warning_for_user="DecisionRouter received no decision; fallback hold was used.",
            )
            self._attach_router_result(
                routed,
                DecisionRouterResult(
                    action="hold",
                    symbol=None,
                    confidence=0.0,
                    risk="medium",
                    reason="DecisionRouter: reason missing",
                    engine=engine,
                    source="ai_decision_service",
                    amount_krw=0.0,
                    timestamp=self._now_iso(),
                    raw={
                        "original_action": None,
                        "original_confidence": None,
                        "original_reason": None,
                        "selected_provider": engine,
                        "router_version": ROUTER_VERSION,
                        "router_mode": self.mode,
                        "provider_status": provider_status,
                        "provider_shadow_decision": self._decision_to_dict(provider_shadow_decision),
                        "provider_shadow_error": provider_shadow_error,
                    },
                ),
            )
            return routed

        raw_action = getattr(decision, "action", "")
        raw_confidence = getattr(decision, "confidence", 0.0)
        raw_reason = getattr(decision, "ai_summary_for_user", "")
        if not raw_reason:
            raw_reason = getattr(decision, "reason", "")

        action = normalize_action(raw_action)
        confidence = self._clamp(raw_confidence, 0.0, 1.0)
        reason = str(raw_reason or "DecisionRouter: reason missing")
        symbol = str(getattr(decision, "selected_symbol", "") or "").strip() or None
        amount_krw = self._safe_float(getattr(decision, "amount_krw", 0.0), 0.0)
        risk = str(getattr(decision, "risk", "") or "medium").strip().lower() or "medium"

        routed_result = DecisionRouterResult(
            action=action,
            symbol=symbol,
            confidence=confidence,
            risk=risk,
            reason=reason,
            engine=engine,
            source="ai_decision_service",
            amount_krw=amount_krw,
            timestamp=self._now_iso(),
            raw={
                "original_action": raw_action,
                "original_confidence": raw_confidence,
                "original_reason": raw_reason,
                "selected_provider": engine,
                "router_version": ROUTER_VERSION,
                "router_mode": self.mode,
                "provider_status": provider_status,
                "provider_shadow_decision": self._decision_to_dict(provider_shadow_decision),
                "provider_shadow_error": provider_shadow_error,
                "context": context_data,
            },
        )
        self._attach_router_result(decision, routed_result)
        return decision

    def get_status_summary(self, provider: str) -> Dict[str, Any]:
        selected_provider = normalize_provider(provider)
        provider_obj = get_provider(self.provider_registry, selected_provider)
        provider_status = provider_obj.get_status()
        return {
            "router_version": ROUTER_VERSION,
            "mode": self.mode,
            "selected_provider": selected_provider,
            "provider_ready": bool(provider_status.get("ready", False)),
            "api_required": bool(provider_status.get("api_required", False)),
            "provider_name": str(provider_status.get("name") or selected_provider),
            "ready_reason": str(provider_status.get("ready_reason") or ""),
        }

    def _attach_router_result(
        self, decision: AIDecisionState, result: DecisionRouterResult
    ) -> None:
        try:
            setattr(decision, "decision_router_result", result)
            setattr(decision, "decision_router_raw", result.to_dict())
            setattr(decision, "source_provider", result.engine)
            setattr(decision, "source_module", "decision_router")
            if not hasattr(decision, "amount_krw"):
                setattr(decision, "amount_krw", result.amount_krw)
        except Exception:
            pass

    def _normalize_provider(self, provider: str) -> str:
        return normalize_provider(provider)

    def _decision_to_dict(self, decision: Optional[Any]) -> Dict[str, Any]:
        if decision is None:
            return {}
        try:
            if hasattr(decision, "to_dict"):
                return dict(decision.to_dict())
        except Exception:
            pass
        return {
            "action": str(getattr(decision, "action", "") or ""),
            "confidence": self._safe_float(getattr(decision, "confidence", 0.0), 0.0),
            "risk": str(getattr(decision, "risk", "") or ""),
            "reason": str(getattr(decision, "reason", "") or ""),
            "engine": str(getattr(decision, "engine", "") or ""),
            "raw": dict(getattr(decision, "raw", {}) or {}),
        }

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
        except Exception:
            pass

    def _clamp(self, value: Any, low: float, high: float) -> float:
        val = self._safe_float(value, low)
        if val < low:
            return low
        if val > high:
            return high
        return val

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
