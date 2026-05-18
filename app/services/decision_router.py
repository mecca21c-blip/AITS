from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.aits_state import AIDecisionState
from app.services.ai_engine_provider import (
    build_default_provider_registry,
    get_provider,
)
from app.services.ai_provider_comparison_stats import AIProviderComparisonStats

ROUTER_VERSION = "v2.6"
AI_VERIFICATION_SUGGESTIONS = {
    "confirm",
    "override_wait",
    "override_buy",
    "override_reduce",
    "override_sell",
    "reject_signal",
}
ROUTER_MODE = "shadow_provider"

# FastSample mode log guard (process-level)
_AITS_FAST_SAMPLE_MODE_LOGGED = False


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
        history_path: Optional[Any] = None,
        performance_path: Optional[Any] = None,
        ai_engine_provider=None,
        ai_verifier=None,
    ) -> None:
        self.logger = logger
        self.provider_registry = provider_registry or build_default_provider_registry(
            settings=settings,
            prefs=prefs,
            config=config,
        )
        self.router_version = ROUTER_VERSION
        self.mode = str(mode or ROUTER_MODE).strip() or ROUTER_MODE
        self.shadow_history_limit = 20
        self.shadow_history_path = self._resolve_shadow_history_path(history_path)
        self.shadow_history = self._load_shadow_history()
        self.shadow_performance_limit = 50
        self.performance_path = self._resolve_shadow_performance_path(
            performance_path,
            history_path,
        )
        self.shadow_performance = self._load_shadow_performance()
        # AITS Decision Router v2.8
        # Optional AI verifier/provider injection.
        # Safety: stored only; no forced API call, no action change.
        try:
            if ai_verifier is not None and not hasattr(self, "ai_verifier"):
                self.ai_verifier = ai_verifier
            if ai_engine_provider is not None and not hasattr(self, "ai_engine_provider"):
                self.ai_engine_provider = ai_engine_provider
        except Exception:
            pass
        self._safe_log_info(
            f"[AITS][DecisionRouter] initialized | version={ROUTER_VERSION} | mode={self.mode}"
        )

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
        shadow_history_summary = self._get_shadow_history_summary()
        self._last_fusion_action = ""
        self._last_ai_micro_apply_delta = 0.0
        self._last_ai_micro_apply_reason = "not_applied"
        if self.mode == "shadow_provider":
            provider_obj = get_provider(self.provider_registry, engine)
            try:
                provider_shadow_decision = provider_obj.decide(context_data)
                shadow_raw = dict(getattr(provider_shadow_decision, "raw", {}) or {})
                final_action = str(getattr(decision, "action", "") or "")
                final_confidence = self._safe_float(
                    getattr(decision, "confidence", 0.0),
                    0.0,
                )
                self._record_shadow_history(
                    provider=engine,
                    shadow_decision=provider_shadow_decision,
                    final_action=final_action,
                    final_confidence=final_confidence,
                )
                shadow_history_summary = self._get_shadow_history_summary()
                shadow_signal = self.get_shadow_signal()
                self._safe_log_info(
                    "[AITS][DecisionRouter] provider_shadow | "
                    f"provider={engine} | "
                    f"shadow_action={getattr(provider_shadow_decision, 'action', '')} | "
                    f"shadow_conf={self._safe_float(getattr(provider_shadow_decision, 'confidence', 0.0), 0.0):.3f} | "
                    f"shadow_rule={shadow_raw.get('shadow_rule', '')} | "
                    f"execution_allowed={shadow_raw.get('execution_allowed', False)} | "
                    f"history_count={shadow_history_summary.get('count', 0)} | "
                    f"history_bias={shadow_history_summary.get('consistency', 'mixed')} | "
                    f"history_buy={shadow_history_summary.get('buy', 0)} | "
                    f"history_sell={shadow_history_summary.get('sell', 0)} | "
                    f"history_persisted={getattr(self, 'shadow_history_persisted', False)} | "
                    f"rule_action={shadow_raw.get('rule_action', '')} | "
                    f"regime={shadow_raw.get('market_regime', '')} | "
                    f"candidates={shadow_raw.get('candidate_count', 0)} | "
                    f"positions={shadow_raw.get('positions_count', 0)} | "
                    f"risk_hint={shadow_raw.get('risk_hint', '')} | "
                    "final=passthrough"
                )
                self._safe_log_info(
                    "[AITS][DecisionRouter] final_action_contract | "
                    "final=passthrough | ai_applied=False"
                )
                self._safe_log_info(
                    "[AITS][DecisionRouter] fusion_signal | "
                    f"history_bias={shadow_signal.get('history_bias', 'mixed')} | "
                    f"regime={shadow_signal.get('market_regime', '')} | "
                    f"fusion_action={shadow_signal.get('fusion_action', 'wait')} | "
                    f"score={self._safe_float(shadow_signal.get('fusion_score'), 0.0):.3f} | "
                    f"applied={bool(shadow_signal.get('fusion_applied', False))}"
                )
                self._last_fusion_action = str(shadow_signal.get("fusion_action") or "")
                if shadow_signal.get("action") != "none":
                    shadow_conf = self._safe_float(shadow_signal.get("confidence"), 0.0)
                    self._safe_log_info(
                        "[AITS][DecisionRouter] shadow_signal | "
                        f"action={shadow_signal.get('action')} | "
                        f"base_conf={self._safe_float(shadow_signal.get('base_confidence'), shadow_conf):.3f} | "
                        f"adjusted_conf={shadow_conf:.3f} | "
                        f"multiplier={self._safe_float(shadow_signal.get('confidence_multiplier'), 1.0):.3f} | "
                        f"adjust_reason={shadow_signal.get('confidence_adjust_reason') or 'unknown'} | "
                        f"sample_count={self._safe_int(shadow_signal.get('performance_sample_count'), 0)} | "
                        f"winrate10={self._safe_float(shadow_signal.get('performance_winrate_10m'), 0.0):.1f} | "
                        f"avg10={self._safe_float(shadow_signal.get('performance_avg_p10m'), 0.0):.2f} | "
                        f"reason={shadow_signal.get('reason')}"
                    )
            except Exception as exc:
                provider_shadow_error = str(exc)[:160]
                self._safe_log_info(
                    "[AITS][DecisionRouter] provider_shadow_failed | "
                    f"provider={engine} | error={provider_shadow_error} | fallback=passthrough"
                )
        self._log_shadow_performance_stats()
        if decision is None:
            fallback_raw = {
                "original_action": None,
                "original_confidence": None,
                "original_reason": None,
                "selected_provider": engine,
                "router_version": ROUTER_VERSION,
                "router_mode": self.mode,
                "provider_status": provider_status,
                "provider_shadow_decision": self._decision_to_dict(provider_shadow_decision),
                "provider_shadow_error": provider_shadow_error,
                "provider_shadow_history_summary": shadow_history_summary,
                "shadow_signal": self.get_shadow_signal(),
                **self._local_shadow_meta(provider_shadow_decision),
            }
            ai_shadow_for_router = self._resolve_ai_shadow_for_router(context_data)
            self._last_resolved_ai_shadow_for_router = (
                dict(ai_shadow_for_router) if isinstance(ai_shadow_for_router, dict) else {}
            )
            self._attach_ai_shadow_meta(fallback_raw, ai_shadow_for_router)
            self._store_ai_shadow_in_shadow_history(
                (fallback_raw.get("meta") or {}).get("ai_shadow")
                if isinstance(fallback_raw.get("meta"), dict)
                else None
            )
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
                    raw=fallback_raw,
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
        performance_boost = self._apply_performance_soft_boost(decision, confidence)
        confidence = self._safe_float(
            performance_boost.get("adjusted_conf"),
            confidence,
        )
        fusion_override = self._apply_fusion_performance_override(decision)
        confidence = self._safe_float(
            fusion_override.get("final_conf"),
            confidence,
        )
        _micro_confidence_meta = {
            "micro_confidence_delta": 0.0,
            "micro_confidence_applied": False,
            "micro_confidence_reason": "not_applied",
            "micro_confidence_new_conf": confidence,
            "micro_confidence_test_mode": False,
        }
        try:
            _apply_delta = self._safe_float(
                getattr(self, "_last_ai_micro_apply_delta", 0.0),
                0.0,
            )
            _apply_reason = str(
                getattr(self, "_last_ai_micro_apply_reason", "not_applied")
                or "not_applied"
            )
            _micro_test_on = bool(getattr(self, "_last_ai_micro_apply_test_mode", False))
            if _apply_delta > 0.01:
                _apply_delta = 0.01
            elif _apply_delta < -0.01:
                _apply_delta = -0.01
            _micro_preview_conf = confidence
            if _micro_test_on and _apply_delta != 0.0:
                _micro_preview_conf = self._clamp(confidence + _apply_delta, 0.0, 1.0)
            _confirm_threshold = self._safe_float(
                getattr(self, "_last_ai_micro_confirm_threshold", 0.60),
                0.60,
            )
            _reject_threshold = self._safe_float(
                getattr(self, "_last_ai_micro_reject_threshold", 0.60),
                0.60,
            )
            try:
                _micro_confidence_meta["micro_confidence_delta"] = float(_apply_delta or 0.0)
                _micro_confidence_meta["micro_confidence_applied"] = bool(
                    _micro_test_on and _apply_delta != 0.0
                )
                _micro_confidence_meta["micro_confidence_reason"] = str(_apply_reason or "not_applied")
                _micro_confidence_meta["micro_confidence_new_conf"] = float(_micro_preview_conf or 0.0)
                _micro_confidence_meta["micro_confidence_test_mode"] = bool(_micro_test_on)
            except Exception:
                pass
            self._safe_log_info(
                "[AITS][AIMicroApply] "
                f"delta={_apply_delta:.4f} | "
                f"reason={_apply_reason} | "
                f"new_conf={_micro_preview_conf:.4f} | "
                f"applied={_micro_test_on and _apply_delta != 0.0} | "
                f"test_mode={_micro_test_on} | "
                f"confirm_th={_confirm_threshold:.2f} | "
                f"reject_th={_reject_threshold:.2f}"
            )
        except Exception:
            pass
        soft_override_candidate = self._record_soft_override_candidate(decision)

        try:
            _micro_delta = float(_micro_confidence_meta.get("micro_confidence_delta") or 0.0)
            _micro_applied = bool(_micro_confidence_meta.get("micro_confidence_applied"))

            if _micro_applied and _micro_delta != 0.0:
                _raw_conf = float(confidence or 0.0)
                _safe_delta = max(-0.01, min(0.01, _micro_delta))
                _new_conf = self._clamp(_raw_conf + _safe_delta, 0.0, 1.0)

                confidence = _new_conf
                try:
                    setattr(decision, "confidence", _new_conf)
                except Exception:
                    pass
                _micro_confidence_meta["micro_confidence_new_conf"] = _new_conf
                self._last_micro_confidence_applied = True
                self._last_micro_confidence_delta = _safe_delta

                self._safe_log_info(
                    "[AITS][AIMicroFinalApply] "
                    f"delta={_safe_delta:.4f} | "
                    f"before={_raw_conf:.4f} | "
                    f"after={_new_conf:.4f} | "
                    f"applied=True"
                )
            else:
                _raw_conf = float(confidence or 0.0)
                self._last_micro_confidence_applied = False
                self._last_micro_confidence_delta = 0.0
                self._safe_log_info(
                    "[AITS][AIMicroFinalApply] "
                    f"delta=0.0000 | "
                    f"before={_raw_conf:.4f} | "
                    f"after={_raw_conf:.4f} | "
                    f"applied=False"
                )
        except Exception:
            pass

        raw_context_data = dict(context_data)
        if "ai_shadow" in raw_context_data:
            raw_context_data.pop("ai_shadow", None)

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
                "provider_shadow_history_summary": shadow_history_summary,
                "shadow_signal": self.get_shadow_signal(),
                "performance_boost": performance_boost,
                "fusion_override": fusion_override,
                "soft_override_candidate": soft_override_candidate,
                "micro_confidence": _micro_confidence_meta,
                **self._local_shadow_meta(provider_shadow_decision),
                "context": raw_context_data,
            },
        )
        ai_shadow_for_router = self._resolve_ai_shadow_for_router(context_data)
        self._last_resolved_ai_shadow_for_router = (
            dict(ai_shadow_for_router) if isinstance(ai_shadow_for_router, dict) else {}
        )
        self._attach_ai_shadow_meta(routed_result.raw, ai_shadow_for_router)
        self._store_ai_shadow_in_shadow_history(
            (routed_result.raw.get("meta") or {}).get("ai_shadow")
            if isinstance(routed_result.raw.get("meta"), dict)
            else None
        )
        self._attach_router_result(decision, routed_result)
        self._log_router_summary(decision)
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

    def get_shadow_signal(self) -> Dict[str, Any]:
        try:
            hist = list(getattr(self, "shadow_history", []))
            if len(hist) < 3:
                return self._apply_regime_bias_fusion(
                    {"action": "none", "confidence": 0.0, "reason": "history_lt_3"}
                )

            recent3 = hist[-3:]
            recent5 = hist[-5:] if len(hist) >= 5 else hist

            buy3 = sum(1 for row in recent3 if row.get("shadow_action") == "buy")
            sell3 = sum(1 for row in recent3 if row.get("shadow_action") == "sell")

            buy5 = sum(1 for row in recent5 if row.get("shadow_action") == "buy")
            sell5 = sum(1 for row in recent5 if row.get("shadow_action") == "sell")

            def avg_conf(rows: list[Dict[str, Any]]) -> float:
                if not rows:
                    return 0.0
                return round(
                    sum(float(row.get("shadow_confidence", 0.0)) for row in rows)
                    / len(rows),
                    3,
                )

            signal = {"action": "none", "confidence": 0.0, "reason": "no_signal"}
            if buy5 >= 5:
                signal = self._build_adjusted_shadow_signal(
                    action="buy_strong",
                    base_confidence=avg_conf(recent5),
                    reason="shadow_buy_5_confirmed",
                )
            elif sell5 >= 5:
                signal = self._build_adjusted_shadow_signal(
                    action="sell_strong",
                    base_confidence=avg_conf(recent5),
                    reason="shadow_sell_5_confirmed",
                )
            elif buy3 >= 3:
                signal = self._build_adjusted_shadow_signal(
                    action="buy",
                    base_confidence=avg_conf(recent3),
                    reason="shadow_buy_3_confirmed",
                )
            elif sell3 >= 3:
                signal = self._build_adjusted_shadow_signal(
                    action="reduce",
                    base_confidence=avg_conf(recent3),
                    reason="shadow_sell_3_confirmed",
                )

            return self._apply_regime_bias_fusion(signal)
        except Exception:
            return {"action": "none", "confidence": 0.0, "reason": "signal_error"}

    def get_regime_bias_signal(self, history_bias: Any, market_regime: Any) -> Dict[str, Any]:
        bias = str(history_bias or "").strip().lower() or "mixed"
        regime = str(market_regime or "").strip().lower() or "unknown"
        rules = {
            ("buy_bias", "bull"): ("buy_strong", 1.00),
            ("buy_bias", "sideways"): ("buy", 0.80),
            ("buy_bias", "neutral"): ("buy", 0.75),
            ("buy_bias", "alt"): ("buy", 0.72),
            ("buy_bias", "bear"): ("wait", 0.35),
            ("buy_bias", "crash"): ("wait", 0.10),
            ("buy_bias", "risk_off"): ("wait", 0.20),
            ("sell_bias", "bear"): ("sell_strong", 1.00),
            ("sell_bias", "crash"): ("sell_strong", 1.00),
            ("sell_bias", "risk_off"): ("sell_strong", 0.95),
            ("sell_bias", "sideways"): ("reduce", 0.70),
            ("sell_bias", "neutral"): ("reduce", 0.65),
            ("sell_bias", "bull"): ("wait", 0.30),
            ("sell_bias", "alt"): ("wait", 0.35),
            ("neutral_wait", "bull"): ("buy", 0.55),
            ("neutral_wait", "sideways"): ("wait", 0.50),
            ("neutral_wait", "neutral"): ("wait", 0.50),
            ("neutral_wait", "bear"): ("wait", 0.45),
            ("neutral_wait", "crash"): ("reduce", 0.60),
        }
        action, score = rules.get((bias, regime), ("wait", 0.50))
        return {
            "action": action,
            "score": self._clamp(score, 0.0, 1.0),
            "reason": f"history_bias={bias}, regime={regime}",
        }

    def _apply_regime_bias_fusion(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        try:
            fused = dict(signal or {})
            history_summary = self._get_shadow_history_summary()
            history_bias = str(history_summary.get("consistency") or "mixed")
            market_regime = self._latest_shadow_market_regime()
            fusion = self.get_regime_bias_signal(history_bias, market_regime)
            fusion_action = str(fusion.get("action") or "wait")
            fusion_score = self._safe_float(fusion.get("score"), 0.0)
            applied = fusion_score >= 0.85

            if applied:
                adjusted = self._build_adjusted_shadow_signal(
                    action=fusion_action,
                    base_confidence=fusion_score,
                    reason=str(fusion.get("reason") or "regime_bias_fusion"),
                )
                adjusted.update(
                    {
                        "fusion_action": fusion_action,
                        "fusion_score": round(fusion_score, 3),
                        "fusion_reason": str(fusion.get("reason") or ""),
                        "fusion_applied": True,
                        "history_bias": history_bias,
                        "market_regime": market_regime,
                        "pre_fusion_action": str(fused.get("action") or "none"),
                        "pre_fusion_confidence": self._safe_float(fused.get("confidence"), 0.0),
                    }
                )
                return adjusted

            fused.update(
                {
                    "fusion_action": fusion_action,
                    "fusion_score": round(fusion_score, 3),
                    "fusion_reason": str(fusion.get("reason") or ""),
                    "fusion_applied": False,
                    "history_bias": history_bias,
                    "market_regime": market_regime,
                }
            )
            return fused
        except Exception:
            fallback = dict(signal or {})
            fallback.update(
                {
                    "fusion_action": "wait",
                    "fusion_score": 0.0,
                    "fusion_reason": "fusion_error",
                    "fusion_applied": False,
                    "history_bias": "mixed",
                    "market_regime": "",
                }
            )
            return fallback

    def get_shadow_confidence_adjustment(self, action: str) -> Dict[str, Any]:
        try:
            action_norm = str(action or "").strip().lower()
            if action_norm in ("buy", "buy_strong"):
                action_set = {"buy", "buy_strong"}
                win_when_positive = True
            elif action_norm in ("reduce", "sell", "sell_strong"):
                action_set = {"reduce", "sell", "sell_strong"}
                win_when_positive = False
            else:
                return {
                    "multiplier": 1.0,
                    "reason": "unsupported_action",
                    "sample_count": 0,
                    "winrate_10m": 0.0,
                    "avg_p10m": 0.0,
                }

            p10_values = []
            wins = 0
            for row in list(getattr(self, "shadow_performance", []) or []):
                if not isinstance(row, dict):
                    continue
                signal_action = str(row.get("signal_action") or "").strip().lower()
                if signal_action not in action_set:
                    continue
                p10 = self._optional_float(row.get("p10m"))
                if p10 is None:
                    continue
                p10_values.append(p10)
                if (win_when_positive and p10 > 0.0) or ((not win_when_positive) and p10 < 0.0):
                    wins += 1

            sample_count = len(p10_values)
            avg_p10m = self._average_or_zero(p10_values)
            winrate = self._safe_pct(wins, sample_count)
            if sample_count < 5:
                multiplier = 1.0
                reason = "insufficient_performance"
            elif winrate >= 70.0 and avg_p10m > 0.0:
                multiplier = 1.10
                reason = "performance_boost"
            elif winrate >= 60.0:
                multiplier = 1.05
                reason = "performance_mild_boost"
            elif winrate <= 40.0:
                multiplier = 0.90
                reason = "performance_penalty"
            else:
                multiplier = 1.0
                reason = "performance_neutral"

            return {
                "multiplier": self._clamp(multiplier, 0.80, 1.20),
                "reason": reason,
                "sample_count": sample_count,
                "winrate_10m": winrate,
                "avg_p10m": avg_p10m,
            }
        except Exception:
            return {
                "multiplier": 1.0,
                "reason": "adjustment_error",
                "sample_count": 0,
                "winrate_10m": 0.0,
                "avg_p10m": 0.0,
            }

    def _build_adjusted_shadow_signal(
        self,
        *,
        action: str,
        base_confidence: Any,
        reason: str,
    ) -> Dict[str, Any]:
        base_conf = round(self._clamp(base_confidence, 0.0, 1.0), 3)
        adj = self.get_shadow_confidence_adjustment(action)
        multiplier = self._safe_float(adj.get("multiplier"), 1.0)
        final_conf = round(self._clamp(base_conf * multiplier, 0.0, 1.0), 3)
        return {
            "action": action,
            "confidence": final_conf,
            "base_confidence": base_conf,
            "confidence_multiplier": multiplier,
            "confidence_adjust_reason": str(adj.get("reason") or ""),
            "performance_sample_count": self._safe_int(adj.get("sample_count"), 0),
            "performance_winrate_10m": self._safe_float(adj.get("winrate_10m"), 0.0),
            "performance_avg_p10m": self._safe_float(adj.get("avg_p10m"), 0.0),
            "reason": reason,
        }

    def _safe_pct(self, n: Any, d: Any) -> float:
        try:
            denominator = float(d)
            if denominator <= 0.0:
                return 0.0
            return round((float(n) / denominator) * 100.0, 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    def get_shadow_performance_summary(self) -> Dict[str, Any]:
        rows = list(getattr(self, "shadow_performance", []) or [])
        buy_actions = {"buy", "buy_strong"}
        sell_actions = {"reduce", "sell", "sell_strong"}
        buy_count = 0
        sell_count = 0
        buy_win_10m = 0
        sell_win_10m = 0
        p10_values = []
        p30_values = []
        p60_values = []
        p10_sample_count = 0
        p10_win_count = 0

        for row in rows:
            if not isinstance(row, dict):
                continue
            action = str(row.get("signal_action") or "").strip().lower()
            p10 = self._optional_float(row.get("p10m"))
            p30 = self._optional_float(row.get("p30m"))
            p60 = self._optional_float(row.get("p60m"))

            if action in buy_actions:
                buy_count += 1
                if p10 is not None and p10 > 0.0:
                    buy_win_10m += 1
                    p10_win_count += 1
                if p10 is not None:
                    p10_sample_count += 1
            elif action in sell_actions:
                sell_count += 1
                if p10 is not None and p10 < 0.0:
                    sell_win_10m += 1
                    p10_win_count += 1
                if p10 is not None:
                    p10_sample_count += 1

            if p10 is not None:
                p10_values.append(p10)
            if p30 is not None:
                p30_values.append(p30)
            if p60 is not None:
                p60_values.append(p60)

        return {
            "count_total": len(rows),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_win_10m": buy_win_10m,
            "sell_win_10m": sell_win_10m,
            "buy_winrate_10m": self._safe_pct(buy_win_10m, buy_count),
            "sell_winrate_10m": self._safe_pct(sell_win_10m, sell_count),
            "sample_count_10m": p10_sample_count,
            "winrate_10m": self._safe_pct(p10_win_count, p10_sample_count),
            "avg_p10m": self._average_or_zero(p10_values),
            "avg_p30m": self._average_or_zero(p30_values),
            "avg_p60m": self._average_or_zero(p60_values),
        }

    def _log_shadow_performance_stats(self) -> None:
        try:
            stats = self.get_shadow_performance_summary()
            if self._safe_int(stats.get("count_total"), 0) < 3:
                return
            self._safe_log_info(
                "[AITS][DecisionRouter] shadow_stats | "
                f"count={stats.get('count_total', 0)} | "
                f"buy={stats.get('buy_count', 0)} | "
                f"sell={stats.get('sell_count', 0)} | "
                f"buy_win10={self._safe_float(stats.get('buy_winrate_10m'), 0.0):.1f}% | "
                f"sell_win10={self._safe_float(stats.get('sell_winrate_10m'), 0.0):.1f}% | "
                f"avg10={self._safe_float(stats.get('avg_p10m'), 0.0):.2f} | "
                f"avg30={self._safe_float(stats.get('avg_p30m'), 0.0):.2f} | "
                f"avg60={self._safe_float(stats.get('avg_p60m'), 0.0):.2f}"
            )
            try:
                shadow_performance = list(getattr(self, "shadow_performance", []) or [])
                _ai_rows = [
                    x for x in shadow_performance
                    if isinstance(x, dict) and "ai_suggestion" in x
                ]

                _ai_count = len(_ai_rows)
                _ai_confirm = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "confirm")
                _ai_skip = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "skip")
                _ai_reject = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "reject_signal")
                _ai_override = sum(
                    1 for x in _ai_rows
                    if str(x.get("ai_suggestion") or "").lower().startswith("override_")
                )
                _ai_applied = sum(1 for x in _ai_rows if bool(x.get("ai_applied")))

                _delta_values = []
                for x in _ai_rows:
                    try:
                        _delta_values.append(float(x.get("ai_shadow_delta") or 0.0))
                    except Exception:
                        pass

                _avg_delta = (sum(_delta_values) / len(_delta_values)) if _delta_values else 0.0

                # AIShadowStats is logged after shadow_performance append/save.
                try:
                    _perf_rows = [
                        x for x in shadow_performance
                        if isinstance(x, dict) and "ai_suggestion" in x
                    ]

                    def _is_win(row):
                        try:
                            vals = [
                                row.get("p10m") or row.get("p10m_proxy"),
                                row.get("p30m") or row.get("p30m_proxy"),
                                row.get("p60m") or row.get("p60m_proxy"),
                            ]
                            vals = [v for v in vals if isinstance(v, (int, float))]
                            if not vals:
                                return None
                            return (sum(vals) / len(vals)) > 0
                        except Exception:
                            return None

                    _confirm_rows = [r for r in _perf_rows if str(r.get("ai_suggestion")) == "confirm"]
                    _reject_rows = [r for r in _perf_rows if str(r.get("ai_suggestion")) == "reject_signal"]

                    def _calc_winrate(rows):
                        wins = 0
                        total = 0
                        for r in rows:
                            w = _is_win(r)
                            if w is None:
                                continue
                            total += 1
                            if w:
                                wins += 1
                        return (wins / total) if total > 0 else 0.0, total

                    _confirm_wr, _confirm_n = _calc_winrate(_confirm_rows)
                    _reject_wr, _reject_n = _calc_winrate(_reject_rows)

                    _avg_delta_effect = 0.0
                    _delta_effect_samples = 0

                    for r in _perf_rows:
                        try:
                            d = float(r.get("ai_shadow_delta") or 0.0)
                            w = _is_win(r)
                            if w is None:
                                continue
                            _delta_effect_samples += 1
                            _avg_delta_effect += d if w else -d
                        except Exception:
                            pass

                    if _delta_effect_samples > 0:
                        _avg_delta_effect /= _delta_effect_samples

                    # AIShadowPerformance is logged after shadow_performance append/save.

                    try:
                        # 기본값
                        _ai_micro_delta = 0.0
                        _ai_micro_reason = "no_effect"

                        # 최소 샘플 조건
                        if _delta_effect_samples >= 10:
                            # confirm 성과가 충분히 좋을 때
                            if _confirm_wr >= 0.6:
                                _ai_micro_delta = min(0.01, 0.01 * _confirm_wr)
                                _ai_micro_reason = "confirm_boost"

                            # reject 성과가 충분히 좋을 때 (리스크 감소)
                            elif _reject_wr >= 0.6:
                                _ai_micro_delta = -min(0.01, 0.01 * _reject_wr)
                                _ai_micro_reason = "reject_penalty"

                        try:
                            _base_conf = 0.0
                            _base_obj = locals().get("base", {})
                            if isinstance(_base_obj, dict):
                                _base_conf = float(_base_obj.get("confidence", 0.0) or 0.0)
                        except Exception:
                            _base_conf = 0.0

                        # 기존 confidence는 건드리지 않고 별도 변수로만 계산
                        _ai_adjusted_conf = _base_conf + _ai_micro_delta

                        # 로그만 남김 (실제 반영 X)
                        self._safe_log_info(
                            "[AITS][AIMicroAdjust] "
                            f"delta={_ai_micro_delta:.4f} | "
                            f"reason={_ai_micro_reason} | "
                            f"base_conf={_base_conf:.4f} | "
                            f"shadow_conf={_ai_adjusted_conf:.4f} | "
                            f"applied=False"
                        )

                        try:
                            import os

                            _apply_delta = 0.0
                            _apply_reason = "not_applied"
                            _micro_test_on = str(os.getenv("AITS_MICRO_APPLY_TEST", "0")).lower() in ("1", "true", "yes", "on")

                            _min_samples = 10
                            _confirm_threshold = 0.60
                            _reject_threshold = 0.60

                            if _micro_test_on:
                                _confirm_threshold = 0.25
                                _reject_threshold = 0.50

                            # 최소 샘플 조건 + 유의미한 성과
                            if _delta_effect_samples >= _min_samples:
                                if _confirm_wr >= _confirm_threshold:
                                    _apply_delta = min(0.01, 0.01 * _confirm_wr)
                                    _apply_reason = "confirm_apply"

                                elif _reject_wr >= _reject_threshold:
                                    _apply_delta = -min(0.01, 0.01 * _reject_wr)
                                    _apply_reason = "reject_apply"

                            self._last_ai_micro_apply_delta = _apply_delta
                            self._last_ai_micro_apply_reason = _apply_reason
                            self._last_ai_micro_apply_test_mode = _micro_test_on
                            self._last_ai_micro_confirm_threshold = _confirm_threshold
                            self._last_ai_micro_reject_threshold = _reject_threshold

                        except Exception:
                            pass

                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] shadow_stats_failed | "
                f"error={str(exc)[:160]}"
            )

    def _log_ai_shadow_stats_after_save(self) -> None:
        try:
            shadow_performance = list(getattr(self, "shadow_performance", []) or [])
            _ai_rows = [
                x for x in shadow_performance
                if isinstance(x, dict) and "ai_suggestion" in x
            ]

            _ai_count = len(_ai_rows)
            _ai_confirm = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "confirm")
            _ai_skip = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "skip")
            _ai_reject = sum(1 for x in _ai_rows if str(x.get("ai_suggestion") or "").lower() == "reject_signal")
            _ai_override = sum(
                1 for x in _ai_rows
                if str(x.get("ai_suggestion") or "").lower().startswith("override_")
            )
            _ai_applied = sum(1 for x in _ai_rows if bool(x.get("ai_applied")))

            _delta_values = []
            for x in _ai_rows:
                try:
                    _delta_values.append(float(x.get("ai_shadow_delta") or 0.0))
                except Exception:
                    pass

            _avg_delta = (sum(_delta_values) / len(_delta_values)) if _delta_values else 0.0

            self._safe_log_info(
                "[AITS][AIShadowStats] "
                f"count={_ai_count} | "
                f"confirm={_ai_confirm} | "
                f"skip={_ai_skip} | "
                f"reject={_ai_reject} | "
                f"override={_ai_override} | "
                f"avg_delta={_avg_delta:.3f} | "
                f"applied={_ai_applied}"
            )
        except Exception:
            pass

        try:
            shadow_performance = list(getattr(self, "shadow_performance", []) or [])
            _perf_rows = [
                x for x in shadow_performance
                if isinstance(x, dict) and "ai_suggestion" in x
            ]

            def _is_win(row):
                try:
                    vals = [
                        row.get("p10m") or row.get("p10m_proxy"),
                        row.get("p30m") or row.get("p30m_proxy"),
                        row.get("p60m") or row.get("p60m_proxy"),
                    ]
                    vals = [v for v in vals if isinstance(v, (int, float))]
                    if not vals:
                        return None
                    return (sum(vals) / len(vals)) > 0
                except Exception:
                    return None

            _confirm_rows = [r for r in _perf_rows if str(r.get("ai_suggestion")) == "confirm"]
            _reject_rows = [r for r in _perf_rows if str(r.get("ai_suggestion")) == "reject_signal"]

            def _calc_winrate(rows):
                wins = 0
                total = 0
                for r in rows:
                    w = _is_win(r)
                    if w is None:
                        continue
                    total += 1
                    if w:
                        wins += 1
                return (wins / total) if total > 0 else 0.0, total

            _confirm_wr, _confirm_n = _calc_winrate(_confirm_rows)
            _reject_wr, _reject_n = _calc_winrate(_reject_rows)

            _avg_delta_effect = 0.0
            _delta_effect_samples = 0

            for r in _perf_rows:
                try:
                    d = float(r.get("ai_shadow_delta") or 0.0)
                    w = _is_win(r)
                    if w is None:
                        continue
                    _delta_effect_samples += 1
                    _avg_delta_effect += d if w else -d
                except Exception:
                    pass

            if _delta_effect_samples > 0:
                _avg_delta_effect /= _delta_effect_samples

            self._safe_log_info(
                "[AITS][AIShadowPerformance] "
                f"confirm_wr={_confirm_wr:.3f} | "
                f"confirm_n={_confirm_n} | "
                f"reject_wr={_reject_wr:.3f} | "
                f"reject_n={_reject_n} | "
                f"avg_delta_effect={_avg_delta_effect:.3f} | "
                f"sample={_delta_effect_samples}"
            )
        except Exception:
            pass

    def _average_or_zero(self, values: Any) -> float:
        try:
            nums = [float(value) for value in values if value is not None]
            if not nums:
                return 0.0
            return round(sum(nums) / len(nums), 2)
        except Exception:
            return 0.0

    def _calc_performance_boost(self, perf_summary: dict) -> dict:
        """
        p10m 기반 간단 보정값 산출
        return:
          {
            "multiplier": float,
            "reason": str,
            "sample_count": int,
            "winrate": float,
            "avg_p10m": float
          }
        """
        try:
            min_sample_required = 3
            count = int(
                perf_summary.get("count", None)
                if perf_summary.get("count", None) is not None
                else perf_summary.get("sample_count_10m", 0)
                or 0
            )
            winrate = float(perf_summary.get("winrate_10m", 0.0) or 0.0)
            avg10 = float(perf_summary.get("avg_p10m", 0.0) or 0.0)
            sample_ready = count >= min_sample_required

            if not sample_ready:
                return {
                    "multiplier": 1.0,
                    "reason": "perf_observe_insufficient_sample",
                    "status": "observe",
                    "sample_count": count,
                    "sample_ready": False,
                    "min_sample_required": min_sample_required,
                    "winrate": winrate,
                    "avg_p10m": avg10,
                }

            if winrate >= 70 and avg10 > 0:
                multiplier = 1.08
                reason = "perf_strong_positive"
            elif winrate >= 60:
                multiplier = 1.04
                reason = "perf_positive"
            elif winrate <= 40:
                multiplier = 0.92
                reason = "perf_negative"
            else:
                multiplier = 1.0
                reason = "perf_neutral"

            multiplier = max(0.85, min(1.15, multiplier))
            if multiplier > 1.0:
                status = "active_boost"
            elif multiplier < 1.0:
                status = "active_penalty"
            else:
                status = "active_neutral"
            return {
                "multiplier": multiplier,
                "reason": reason,
                "status": status,
                "sample_count": count,
                "sample_ready": True,
                "min_sample_required": min_sample_required,
                "winrate": winrate,
                "avg_p10m": avg10,
            }
        except Exception:
            return {
                "multiplier": 1.0,
                "reason": "perf_error",
                "status": "observe",
                "sample_count": 0,
                "sample_ready": False,
                "min_sample_required": 3,
                "winrate": 0.0,
                "avg_p10m": 0.0,
            }

    def _apply_performance_soft_boost(
        self,
        decision: Any,
        final_confidence: Any,
    ) -> Dict[str, Any]:
        try:
            perf_summary = getattr(self, "_shadow_performance_summary", None)
            if perf_summary is None:
                perf_summary = self.get_shadow_performance_summary()
            boost = self._calc_performance_boost(perf_summary)

            base_conf = self._safe_float(final_confidence, 0.0)
            adjusted_conf = max(
                0.0,
                min(1.0, base_conf * self._safe_float(boost.get("multiplier"), 1.0)),
            )
            result = {
                "status": str(boost.get("status") or "observe"),
                "sample_ready": bool(boost.get("sample_ready", False)),
                "min_sample_required": self._safe_int(boost.get("min_sample_required"), 3),
                "base_conf": base_conf,
                "adjusted_conf": adjusted_conf,
                "multiplier": self._safe_float(boost.get("multiplier"), 1.0),
                "reason": str(boost.get("reason") or ""),
                "sample_count": self._safe_int(boost.get("sample_count"), 0),
                "winrate10": self._safe_float(boost.get("winrate"), 0.0),
                "avg10": self._safe_float(boost.get("avg_p10m"), 0.0),
            }

            self._safe_log_info(
                "[AITS][DecisionRouter] performance_boost | "
                f"status={result['status']} | "
                f"sample_ready={result['sample_ready']} | "
                f"min_sample={result['min_sample_required']} | "
                f"base_conf={base_conf:.3f} | adjusted_conf={adjusted_conf:.3f} | "
                f"multiplier={result['multiplier']:.3f} | reason={result['reason']} | "
                f"sample_count={result['sample_count']} | "
                f"winrate10={result['winrate10']:.1f} | avg10={result['avg10']:.2f}"
            )
            try:
                setattr(decision, "confidence", adjusted_conf)
                raw = getattr(decision, "raw", None)
                if not isinstance(raw, dict):
                    raw = {}
                    setattr(decision, "raw", raw)
                raw["performance_boost"] = result
            except Exception:
                pass
            return result
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] performance_boost_failed | "
                f"error={type(exc).__name__}"
            )
            return {
                "base_conf": self._safe_float(final_confidence, 0.0),
                "adjusted_conf": self._safe_float(final_confidence, 0.0),
                "multiplier": 1.0,
                "reason": "perf_error",
                "status": "observe",
                "sample_ready": False,
                "min_sample_required": 3,
                "sample_count": 0,
                "winrate10": 0.0,
                "avg10": 0.0,
            }

    def _calc_fusion_performance_adjustment(
        self,
        fusion_action: str,
        boost_info: dict,
    ) -> dict:
        """
        fusion + performance 기반 추가 보정 (confidence만)
        return:
          {
            "multiplier": float,
            "reason": str
          }
        """
        try:
            status = boost_info.get("status")
            sample_ready = bool(boost_info.get("sample_ready", False))
            action = str(fusion_action or "").strip().lower()

            if not sample_ready:
                return {"multiplier": 1.0, "reason": "fusion_perf_insufficient"}

            if action in ("buy", "buy_strong"):
                if status == "active_boost":
                    return {"multiplier": 1.05, "reason": "fusion_buy_boost"}
                if status == "active_penalty":
                    return {"multiplier": 0.95, "reason": "fusion_buy_penalty"}

            if action in ("sell", "sell_strong", "reduce"):
                if status == "active_boost":
                    return {"multiplier": 1.05, "reason": "fusion_sell_boost"}
                if status == "active_penalty":
                    return {"multiplier": 0.95, "reason": "fusion_sell_penalty"}

            return {"multiplier": 1.0, "reason": "fusion_neutral"}
        except Exception:
            return {"multiplier": 1.0, "reason": "fusion_error"}

    def _apply_fusion_performance_override(self, decision: Any) -> Dict[str, Any]:
        try:
            fusion_action = str(getattr(self, "_last_fusion_action", "") or "")
            raw = getattr(decision, "raw", None)
            if not isinstance(raw, dict):
                raw = {}
                setattr(decision, "raw", raw)
            boost_info = raw.get("performance_boost", {})
            if not isinstance(boost_info, dict):
                boost_info = {}

            fusion_adj = self._calc_fusion_performance_adjustment(
                fusion_action,
                boost_info,
            )
            base_conf = self._safe_float(getattr(decision, "confidence", 0.0), 0.0)
            multiplier = self._safe_float(fusion_adj.get("multiplier"), 1.0)
            final_conf = max(0.0, min(1.0, base_conf * multiplier))
            result = {
                "fusion_action": fusion_action,
                "base_conf": base_conf,
                "final_conf": final_conf,
                "multiplier": multiplier,
                "reason": str(fusion_adj.get("reason") or ""),
            }

            self._safe_log_info(
                "[AITS][DecisionRouter] fusion_override | "
                f"fusion_action={fusion_action} | "
                f"base_conf={base_conf:.3f} | final_conf={final_conf:.3f} | "
                f"multiplier={multiplier:.3f} | "
                f"reason={result['reason']}"
            )
            setattr(decision, "confidence", final_conf)
            raw["fusion_override"] = result
            return result
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] fusion_override_failed | "
                f"error={type(exc).__name__}"
            )
            base_conf = self._safe_float(getattr(decision, "confidence", 0.0), 0.0)
            return {
                "fusion_action": "",
                "base_conf": base_conf,
                "final_conf": base_conf,
                "multiplier": 1.0,
                "reason": "fusion_error",
            }

    def get_soft_override_candidate(
        self,
        fusion_action: str,
        performance_status: str,
        final_confidence: float,
    ) -> dict:
        """
        실제 action은 변경하지 않고, Router가 추천하는 soft override 후보만 반환한다.
        return:
        {
            "candidate_action": "buy" | "buy_strong" | "reduce" | "sell_strong" | "wait" | "none",
            "candidate_strength": "none" | "weak" | "medium" | "strong",
            "reason": str,
            "eligible": bool
        }
        """
        try:
            action = str(fusion_action or "").strip().lower()
            status = str(performance_status or "").strip().lower()
            conf = self._safe_float(final_confidence, 0.0)

            if status == "active_boost":
                if action == "buy_strong" and conf >= 0.60:
                    return {
                        "candidate_action": "buy_strong",
                        "candidate_strength": "strong",
                        "reason": "active_boost_buy_strong",
                        "eligible": True,
                    }
                if action == "buy" and conf >= 0.55:
                    return {
                        "candidate_action": "buy",
                        "candidate_strength": "medium",
                        "reason": "active_boost_buy",
                        "eligible": True,
                    }
                if action in ("reduce", "sell_strong") and conf >= 0.55:
                    return {
                        "candidate_action": action,
                        "candidate_strength": "medium",
                        "reason": "active_boost_defensive",
                        "eligible": True,
                    }

            if status == "active_neutral":
                if action in ("buy", "buy_strong", "reduce", "sell_strong") and conf >= 0.65:
                    return {
                        "candidate_action": action,
                        "candidate_strength": "weak",
                        "reason": "active_neutral_high_confidence",
                        "eligible": True,
                    }

            if status == "active_penalty":
                return {
                    "candidate_action": "wait",
                    "candidate_strength": "weak",
                    "reason": "performance_penalty_blocks_override",
                    "eligible": False,
                }

            if status == "observe":
                return {
                    "candidate_action": "none",
                    "candidate_strength": "none",
                    "reason": "observe_mode_no_override",
                    "eligible": False,
                }

            return {
                "candidate_action": "none",
                "candidate_strength": "none",
                "reason": "no_candidate",
                "eligible": False,
            }
        except Exception:
            return {
                "candidate_action": "none",
                "candidate_strength": "none",
                "reason": "candidate_error",
                "eligible": False,
            }

    def _record_soft_override_candidate(self, decision: Any) -> Dict[str, Any]:
        try:
            raw = getattr(decision, "raw", None)
            if not isinstance(raw, dict):
                raw = {}
                setattr(decision, "raw", raw)
            boost_info = raw.get("performance_boost", {})
            if not isinstance(boost_info, dict):
                boost_info = {}
            fusion_info = raw.get("fusion_override", {})
            if not isinstance(fusion_info, dict):
                fusion_info = {}

            fusion_action = (
                fusion_info.get("fusion_action")
                or getattr(self, "_last_fusion_action", None)
                or ""
            )
            performance_status = str(boost_info.get("status") or "unknown")
            final_confidence = self._safe_float(getattr(decision, "confidence", 0.0), 0.0)
            candidate = self.get_soft_override_candidate(
                fusion_action=fusion_action,
                performance_status=performance_status,
                final_confidence=final_confidence,
            )
            candidate["fusion_action"] = str(fusion_action or "")
            candidate["performance_status"] = performance_status
            candidate["final_confidence"] = final_confidence
            self._safe_log_info(
                "[AITS][DecisionRouter] soft_override_candidate | "
                f"candidate_action={candidate.get('candidate_action')} | "
                f"strength={candidate.get('candidate_strength')} | "
                f"eligible={candidate.get('eligible')} | "
                f"fusion_action={fusion_action} | "
                f"performance_status={performance_status} | "
                f"final_conf={final_confidence:.3f} | "
                f"reason={candidate.get('reason')}"
            )
            self._last_soft_override_candidate = dict(candidate)
            raw["soft_override_candidate"] = candidate
            return candidate
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] soft_override_candidate_failed | "
                f"error={type(exc).__name__}"
            )
            return {
                "candidate_action": "none",
                "candidate_strength": "none",
                "reason": "candidate_error",
                "eligible": False,
            }

    def get_last_soft_override_candidate(self) -> dict:
        """
        마지막 soft_override_candidate 반환.
        없으면 안전한 none dict 반환.
        """
        try:
            candidate = getattr(self, "_last_soft_override_candidate", None)
            if isinstance(candidate, dict):
                return dict(candidate)
        except Exception:
            pass

        return {
            "candidate_action": "none",
            "candidate_strength": "none",
            "eligible": False,
            "reason": "no_soft_candidate",
        }

    def _build_ai_verification_context(
        self,
        *,
        final_action=None,
        final_confidence=None,
        fusion_signal=None,
        performance_boost=None,
        soft_override_candidate=None,
        dryrun_compare=None,
        mismatch_reason=None,
        market_regime=None,
        candidate_count=None,
        positions_count=None,
        symbol=None,
        execution_allowed=None,
    ):
        """
        Decision Router v2.6
        Compact AI verification context.

        Safety:
        - 관측/검증용 payload만 생성한다.
        - action/final decision/order에는 절대 관여하지 않는다.
        - 토큰 절약을 위해 RouterSummary 수준의 핵심값만 담는다.
        """
        try:
            perf = performance_boost if isinstance(performance_boost, dict) else {}
            fusion = fusion_signal if isinstance(fusion_signal, dict) else {}
            soft = soft_override_candidate if isinstance(soft_override_candidate, dict) else {}

            return {
                "final_action": final_action or "none",
                "final_confidence": round(float(final_confidence or 0.0), 3),
                "fusion_action": fusion.get("fusion_action", "none"),
                "performance_status": perf.get("status", "unknown"),
                "performance_multiplier": perf.get("multiplier", 1.0),
                "soft_candidate": soft.get("candidate_action", "none"),
                "soft_eligible": soft.get("eligible", False),
                "router_version": ROUTER_VERSION,
            }

            context = {
                "router_version": ROUTER_VERSION,
                "final_action": final_action,
                "final_confidence": final_confidence,
                "fusion_signal": fusion_signal,
                "performance_boost": performance_boost,
                "soft_override_candidate": soft_override_candidate,
                "dryrun_compare": dryrun_compare,
                "mismatch_reason": mismatch_reason,
                "market_regime": market_regime,
                "candidate_count": candidate_count,
                "positions_count": positions_count,
                "symbol": symbol,
                "execution_allowed": execution_allowed,
                "allowed_suggestions": sorted(AI_VERIFICATION_SUGGESTIONS),
                "safety_note": "verification_only_no_action_change",
            }
            return {k: v for k, v in context.items() if v is not None}
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][AIVerification] context_build_failed | "
                f"error={type(exc).__name__}: {exc}"
            )
            return {
                "router_version": ROUTER_VERSION,
                "safety_note": "verification_only_no_action_change",
                "context_error": type(exc).__name__,
            }

    def _run_ai_verification_shadow(self, provider: str, context: dict) -> dict:
        """
        AI verification layer 1.
        This stage never calls provider APIs; it only returns provider-specific shadow metadata.
        """
        provider = str(provider or "local").lower().strip()
        context = context if isinstance(context, dict) else {}

        base = {
            "called": False,
            "provider": provider or "local",
            "suggestion": "skip",
            "reason": "not_called",
            "context": context,
            "applied": False,
            "observe_only_weight_delta": 0.0,
            "observe_only_weight_reason": "verification_shadow_no_api_call",
            "observe_only_weight_applied": False,
            "shadow_confidence_delta": 0.0,
            "shadow_confidence_policy": "verification_shadow_no_action_effect",
            "shadow_confidence_applied": False,
        }

        if provider in ("local", "basic", "none", ""):
            base.update(
                {
                    "provider": "local",
                    "suggestion": "skip",
                    "reason": "local_provider_no_api_call",
                    "observe_only_weight_reason": "ai_local_skip_no_api_call",
                    "shadow_confidence_policy": "local_skip_no_shadow_effect",
                }
            )
            return base

        if provider in ("openai", "gpt"):
            base.update(
                {
                    "provider": "openai",
                    "suggestion": "pending_api_integration",
                    "reason": "openai_shadow_verification_not_called_yet",
                }
            )
            return base

        if provider in ("gemini", "google"):
            base.update(
                {
                    "provider": "gemini",
                    "suggestion": "pending_api_integration",
                    "reason": "gemini_shadow_verification_not_called_yet",
                }
            )
            return base

        base.update(
            {
                "provider": provider,
                "suggestion": "skip",
                "reason": "unknown_provider",
            }
        )
        return base

    def _resolve_ai_verification_provider(self, raw=None):
        """
        Decision Router v2.6
        Resolve selected AI provider safely.

        Safety:
        - provider 판별만 한다.
        - 외부 API 호출은 여기서 하지 않는다.
        """
        provider = None

        try:
            if isinstance(raw, dict):
                provider = raw.get("selected_provider") or raw.get("provider") or provider
                meta = raw.get("meta") or raw.get("metadata") or {}
                strategy = raw.get("strategy") or {}

                if isinstance(meta, dict):
                    meta_strategy = meta.get("strategy") or {}
                    if isinstance(meta_strategy, dict):
                        provider = meta_strategy.get("ai_provider") or provider
                    provider = meta.get("ai_provider") or provider

                if isinstance(strategy, dict):
                    provider = strategy.get("ai_provider") or provider
        except Exception:
            provider = provider

        try:
            provider = provider or getattr(self, "ai_provider", None)
            provider = provider or getattr(self, "provider_name", None)
            provider = provider or getattr(self, "_ai_provider", None)
            provider = provider or getattr(self, "_provider_name", None)
        except Exception:
            provider = provider

        try:
            raw_meta_provider = None
            raw_strategy_provider = None
            raw_meta_strategy_provider = None

            if isinstance(raw, dict):
                _meta = raw.get("meta") or raw.get("metadata") or {}
                _strategy = raw.get("strategy") or {}

                if isinstance(_meta, dict):
                    raw_meta_provider = _meta.get("ai_provider")
                    _meta_strategy = _meta.get("strategy") or {}
                    if isinstance(_meta_strategy, dict):
                        raw_meta_strategy_provider = _meta_strategy.get("ai_provider")

                if isinstance(_strategy, dict):
                    raw_strategy_provider = _strategy.get("ai_provider")

            self._safe_log_info(
                "[AITS][AIVerification] provider_source | "
                f"raw_meta={raw_meta_provider} | "
                f"raw_meta_strategy={raw_meta_strategy_provider} | "
                f"raw_strategy={raw_strategy_provider} | "
                f"self_ai_provider={getattr(self, 'ai_provider', None)} | "
                f"self_provider_name={getattr(self, 'provider_name', None)}"
            )
        except Exception:
            pass

        provider = str(provider or "local").strip().lower()

        if provider in ("gpt", "openai", "chatgpt"):
            return "openai"
        if provider in ("gemini", "google", "google_gemini"):
            return "gemini"
        if provider in ("basic", "local", "localprovider", "none", ""):
            return "local"

        return provider

    def _run_ai_verification_suggestion(self, *, provider=None, context=None, raw=None):
        """
        Decision Router v2.6
        AI verification suggestion layer.

        Safety:
        - 이 메서드는 final action을 절대 바꾸지 않는다.
        - openai/gemini 실제 호출은 adapter가 있으면 시도하고, 없으면 unavailable로 기록한다.
        - local/basic이면 API 호출하지 않는다.
        - 반환값은 raw/meta 기록용 suggestion dict다.
        """
        provider = str(provider or "local").strip().lower()
        context = context or {}

        try:
            self._safe_log_info(
                "[AITS][AIVerification] provider_route | "
                f"provider={provider} | phase=enter | applied=False"
            )
        except Exception:
            pass

        base = {
            "enabled": True,
            "provider": provider,
            "mode": "verification_only",
            "applied": False,
            "suggestion": "skip",
            "reason": "not_called",
            "context": context,
        }

        if provider in ("local", "basic", "none", ""):
            base.update(
                {
                    "suggestion": "skip",
                    "reason": "local_provider_no_api_call",
                }
            )
            try:
                import os
                import random

                _force_ai_sample = str(os.getenv("AITS_FORCE_AI_SAMPLE", "0")).lower() in ("1", "true", "yes", "on")

                if _force_ai_sample:
                    _r = random.random()

                    if _r < 0.20:
                        base["suggestion"] = "confirm"
                        base["reason"] = "local_forced_confirm"
                        base["risk_note"] = None
                    elif _r < 0.30:
                        base["suggestion"] = "reject_signal"
                        base["reason"] = "local_forced_reject"
                        base["risk_note"] = None

                    self._safe_log_info(
                        "[AITS][AIVerification] force_ai_sample | "
                        f"provider=local | "
                        f"suggestion={base.get('suggestion')} | "
                        f"reason={base.get('reason')} | "
                        f"applied=False"
                    )
            except Exception:
                pass
            self._safe_log_info(
                "[AITS][AIVerification] skipped | "
                f"provider={provider} | reason=local_provider_no_api_call"
            )
            try:
                base["observe_only_weight_delta"] = 0.0
                base["observe_only_weight_reason"] = "ai_local_skip_no_api_call"
                base["observe_only_weight_applied"] = False

                self._safe_log_info(
                    "[AITS][AIVerificationWeight] "
                    f"provider={provider} | "
                    f"suggestion={base.get('suggestion')} | "
                    f"delta=0.000 | "
                    f"reason=ai_local_skip_no_api_call | "
                    f"applied=False"
                )
            except Exception:
                pass
            try:
                base["shadow_confidence_delta"] = 0.0
                base["shadow_confidence_policy"] = "local_skip_no_shadow_effect"
                base["shadow_confidence_applied"] = False

                self._safe_log_info(
                    "[AITS][AIVerificationShadowDelta] "
                    f"provider=local | "
                    f"suggestion=skip | "
                    f"delta=0.000 | "
                    f"policy=local_skip_no_shadow_effect | "
                    f"applied=False"
                )
            except Exception:
                pass
            return base

        if provider not in ("openai", "gemini"):
            base.update(
                {
                    "suggestion": "skip",
                    "reason": f"unsupported_provider:{provider}",
                }
            )
            self._safe_log_info(
                "[AITS][AIVerification] skipped | "
                f"provider={provider} | reason=unsupported_provider"
            )
            return base

        try:
            self._safe_log_info(
                "[AITS][AIVerification] provider_route | "
                f"provider={provider} | phase=verifier_lookup | applied=False"
            )
        except Exception:
            pass

        try:
            verifier = (
                getattr(self, "ai_verifier", None)
                or getattr(self, "_ai_verifier", None)
                or getattr(self, "ai_engine_provider", None)
                or getattr(self, "_ai_engine_provider", None)
                or getattr(self, "provider", None)
                or getattr(self, "_provider", None)
            )

            try:
                self._safe_log_info(
                    "[AITS][AIVerification] verifier_resolved | "
                    f"provider={provider} | attached={verifier is not None} | "
                    f"type={type(verifier).__name__ if verifier is not None else 'None'}"
                )
            except Exception:
                pass

            try:
                _verifier_type = type(verifier).__name__ if verifier is not None else "None"
                if provider in ("openai", "gemini") and _verifier_type == "LocalProvider":
                    base.update(
                        {
                            "suggestion": "skip",
                            "reason": f"verifier_not_implemented:{provider}:local_provider_attached",
                            "verifier_type": _verifier_type,
                        }
                    )
                    self._safe_log_info(
                        "[AITS][AIVerification] verifier_type_blocked | "
                        f"provider={provider} | verifier_type={_verifier_type} | applied=False"
                    )
                    return base
            except Exception:
                pass

            if verifier is None:
                base.update(
                    {
                        "suggestion": "skip",
                        "reason": "verifier_not_attached",
                    }
                )
                self._safe_log_info(
                    "[AITS][AIVerification] unavailable | "
                    f"provider={provider} | reason=verifier_not_attached"
                )
                return base

            result = None

            if hasattr(verifier, "verify_router_decision"):
                result = verifier.verify_router_decision(provider=provider, context=context)
            elif hasattr(verifier, "verify_decision"):
                result = verifier.verify_decision(provider=provider, context=context)
            elif hasattr(verifier, "ask"):
                result = verifier.ask(context)
            else:
                base.update(
                    {
                        "suggestion": "skip",
                        "reason": "verifier_method_not_found",
                    }
                )
                self._safe_log_info(
                    "[AITS][AIVerification] unavailable | "
                    f"provider={provider} | reason=verifier_method_not_found"
                )
                return base

            parsed = result if isinstance(result, dict) else {"raw_response": str(result)}
            suggestion = str(parsed.get("suggestion") or parsed.get("decision") or "confirm").strip().lower()

            if suggestion not in AI_VERIFICATION_SUGGESTIONS:
                suggestion = "confirm"

            base.update(
                {
                    "suggestion": suggestion,
                    "reason": parsed.get("reason") or parsed.get("summary") or "provider_response",
                    "raw_response": parsed,
                }
            )

            try:
                _original_suggestion = str(base.get("suggestion") or "").lower()
                _reason = str(base.get("reason") or "").lower()

                if _original_suggestion == "confirm" and any(
                    x in _reason
                    for x in (
                        "verifier_not_implemented",
                        "error",
                        "api_key_missing",
                        "empty_response",
                    )
                ):
                    base["suggestion"] = "skip"

                    self._safe_log_info(
                        "[AITS][AIVerification] suggestion_corrected | "
                        f"original=confirm | corrected=skip | reason={_reason} | applied=False"
                    )
            except Exception:
                pass

            try:
                _suggestion = str(base.get("suggestion") or "skip").strip().lower()
                _weight_delta = 0.0
                _weight_reason = "neutral"

                if _suggestion == "confirm":
                    _weight_delta = 0.03
                    _weight_reason = "ai_confirm_small_boost"
                elif _suggestion == "reject_signal":
                    _weight_delta = -0.08
                    _weight_reason = "ai_reject_signal_penalty"
                elif _suggestion == "override_wait":
                    _weight_delta = -0.05
                    _weight_reason = "ai_override_wait_penalty"
                elif _suggestion == "override_buy":
                    _weight_delta = 0.05
                    _weight_reason = "ai_override_buy_observe"
                elif _suggestion == "override_reduce":
                    _weight_delta = -0.04
                    _weight_reason = "ai_override_reduce_observe"
                elif _suggestion == "override_sell":
                    _weight_delta = -0.07
                    _weight_reason = "ai_override_sell_observe"
                else:
                    _weight_delta = 0.0
                    _weight_reason = "ai_skip_or_unknown"

                try:
                    _api_reason = str(base.get("reason") or "").strip()
                    _api_reason_lower = _api_reason.lower()

                    if _suggestion == "skip" and any(x in _api_reason_lower for x in (
                        "quota_exceeded",
                        "api_key_missing",
                        "api_key_invalid",
                        "bad_request",
                        "http_error",
                        "live_call_disabled",
                        "verifier_not_implemented",
                        "verifier_error",
                        "unsupported_provider",
                        "empty_response",
                    )):
                        _weight_reason = _api_reason
                except Exception:
                    pass

                base["observe_only_weight_delta"] = _weight_delta
                base["observe_only_weight_reason"] = _weight_reason
                base["observe_only_weight_applied"] = False

                self._safe_log_info(
                    "[AITS][AIVerificationWeight] "
                    f"provider={provider} | "
                    f"suggestion={_suggestion} | "
                    f"delta={_weight_delta:.3f} | "
                    f"reason={_weight_reason} | "
                    f"applied=False"
                )

                try:
                    _suggestion = str(base.get("suggestion") or "skip").strip().lower()
                    _reason = str(base.get("reason") or "").strip().lower()

                    _shadow_delta = 0.0
                    _shadow_policy = "neutral"

                    if _suggestion == "confirm":
                        _shadow_delta = 0.02
                        _shadow_policy = "confirm_small_shadow_boost"
                    elif _suggestion == "reject_signal":
                        _shadow_delta = -0.04
                        _shadow_policy = "reject_signal_shadow_penalty"
                    elif _suggestion == "override_wait":
                        _shadow_delta = -0.03
                        _shadow_policy = "override_wait_shadow_penalty"
                    elif _suggestion == "override_buy":
                        _shadow_delta = 0.00
                        _shadow_policy = "override_buy_blocked_observe_only"
                    elif _suggestion == "override_reduce":
                        _shadow_delta = -0.02
                        _shadow_policy = "override_reduce_shadow_penalty"
                    elif _suggestion == "override_sell":
                        _shadow_delta = -0.04
                        _shadow_policy = "override_sell_shadow_penalty"
                    elif _suggestion == "skip":
                        _shadow_delta = 0.00
                        _shadow_policy = "skip_no_shadow_effect"
                    else:
                        _shadow_delta = 0.00
                        _shadow_policy = "unknown_suggestion_no_shadow_effect"

                    # API/infra failure must never affect confidence.
                    if any(x in _reason for x in (
                        "api_key_missing",
                        "api_key_invalid",
                        "quota_exceeded",
                        "bad_request",
                        "http_error",
                        "live_call_disabled",
                        "verifier_not_implemented",
                        "verifier_error",
                        "unsupported_provider",
                        "empty_response",
                        "local_provider_no_api_call",
                    )):
                        _shadow_delta = 0.00
                        _shadow_policy = "infra_failure_no_shadow_effect"

                    base["shadow_confidence_delta"] = _shadow_delta
                    base["shadow_confidence_policy"] = _shadow_policy
                    base["shadow_confidence_applied"] = False

                    self._safe_log_info(
                        "[AITS][AIVerificationShadowDelta] "
                        f"provider={provider} | "
                        f"suggestion={_suggestion} | "
                        f"delta={_shadow_delta:.3f} | "
                        f"policy={_shadow_policy} | "
                        f"applied=False"
                    )
                except Exception:
                    pass
            except Exception:
                pass

            self._safe_log_info(
                "[AITS][AIVerification] suggestion | "
                f"provider={provider} | suggestion={base.get('suggestion')} | applied=False"
            )
            try:
                _raw_preview = ""
                _raw_obj = base.get("raw_response")
                if isinstance(_raw_obj, dict):
                    _raw_preview = str(
                        {
                            "suggestion": _raw_obj.get("suggestion"),
                            "reason": _raw_obj.get("reason") or _raw_obj.get("summary"),
                            "risk_note": _raw_obj.get("risk_note") or _raw_obj.get("note"),
                        }
                    )
                else:
                    _raw_preview = str(_raw_obj or "")

                _raw_preview = _raw_preview.replace("\n", " ").replace("\r", " ")[:300]
                _reason_preview = str(base.get("reason") or "").replace("\n", " ").replace("\r", " ")[:300]
                _error_preview = str(base.get("error") or "").replace("\n", " ").replace("\r", " ")[:500]
                _risk_preview = ""
                if isinstance(base.get("raw_response"), dict):
                    _risk_preview = str(
                        base["raw_response"].get("risk_note")
                        or base["raw_response"].get("note")
                        or ""
                    ).replace("\n", " ").replace("\r", " ")[:300]

                self._safe_log_info(
                    "[AITS][AIVerificationDetail] "
                    f"provider={provider} | "
                    f"suggestion={base.get('suggestion')} | "
                    f"reason={_reason_preview} | "
                    f"risk_note={_risk_preview} | "
                    f"error={_error_preview} | "
                    f"raw_preview={_raw_preview} | "
                    f"applied=False"
                )
            except Exception:
                pass
            return base

        except Exception as exc:
            base.update(
                {
                    "suggestion": "skip",
                    "reason": f"verification_error:{type(exc).__name__}",
                    "error": str(exc),
                }
            )
            self._safe_log_warning(
                "[AITS][AIVerification] failed | "
                f"provider={provider} | error={type(exc).__name__}: {exc}"
            )
            return base

    def _build_router_summary(self, decision: Any, raw: dict) -> str:
        try:
            action = getattr(decision, "action", "none")
            conf = float(getattr(decision, "confidence", 0.0))

            perf = raw.get("performance_boost", {}) if raw else {}
            perf_status = perf.get("status", "unknown")

            fusion = raw.get("fusion_override", {}) if raw else {}
            fusion_action = fusion.get("fusion_action", "none")

            soft = raw.get("soft_override_candidate", {}) if raw else {}
            soft_action = soft.get("candidate_action", "none")
            soft_eligible = soft.get("eligible", False)
            ai_stats = self._get_ai_suggestion_history_stats()
            ai_shadow = self._resolve_ai_shadow_for_summary(raw)
            ai_shadow_present = bool(ai_shadow)
            ai_shadow_fields = self._extract_ai_shadow_summary_fields(ai_shadow)
            provider_stats = self._build_ai_provider_stats_summary()

            return (
                f"action={action} | "
                f"conf={conf:.3f} | "
                f"fusion={fusion_action} | "
                f"perf={perf_status} | "
                f"soft={soft_action} | "
                f"eligible={soft_eligible} | "
                f"ai_t={ai_stats.get('total_count', 0)} | "
                f"ai_c={ai_stats.get('confirm_count', 0)} | "
                f"ai_s={ai_stats.get('skip_count', 0)} | "
                f"ai_r={ai_stats.get('reject_count', 0)} | "
                f"ai_shadow={ai_shadow_present} | "
                f"ai_state={ai_shadow_fields.get('ai_state')} | "
                f"ai_action={ai_shadow_fields.get('ai_action')} | "
                f"ai_scenario={ai_shadow_fields.get('ai_scenario')} | "
                f"ai_eta={ai_shadow_fields.get('ai_eta')} | "
                f"ai_stats_total={provider_stats.get('total')} | "
                f"ai_stats={provider_stats.get('compact')} | "
                "ai_applied=False | "
                "ai_a=0"
            )
        except Exception:
            return "summary_build_failed"

    def _log_router_summary(self, decision: Any) -> None:
        try:
            raw = getattr(decision, "raw", {}) if hasattr(decision, "raw") else {}
            if not isinstance(raw, dict):
                raw = {}
            if not raw:
                try:
                    router_result = getattr(decision, "decision_router_result", None)
                    raw = dict(getattr(router_result, "raw", {}) or {})
                except Exception:
                    raw = {}
            else:
                try:
                    router_result = getattr(decision, "decision_router_result", None)
                    router_raw = dict(getattr(router_result, "raw", {}) or {})
                    router_shadow = self._resolve_ai_shadow_for_summary(router_raw)
                    raw_shadow = self._resolve_ai_shadow_for_summary(raw)
                    if router_shadow and not raw_shadow:
                        raw = dict(raw)
                        raw_meta = raw.setdefault("meta", {})
                        if not isinstance(raw_meta, dict):
                            raw_meta = {}
                            raw["meta"] = raw_meta
                        raw_meta["ai_shadow"] = router_shadow
                except Exception:
                    pass
            summary_ai_shadow = self._resolve_ai_shadow_for_summary(raw)
            if summary_ai_shadow:
                try:
                    raw = dict(raw)
                    raw_meta = raw.setdefault("meta", {})
                    if not isinstance(raw_meta, dict):
                        raw_meta = {}
                        raw["meta"] = raw_meta
                    raw_meta["ai_shadow"] = summary_ai_shadow
                except Exception:
                    pass
            summary = self._build_router_summary(decision, raw)
            self._safe_log_info(f"[AITS][RouterSummary] {summary}")
            try:
                provider_stats = self._build_ai_provider_stats_summary()
                self._safe_log_info(
                    "[AITS][DecisionRouter] ai_provider_stats_summary | "
                    f"total={provider_stats.get('total')} | "
                    f"providers={provider_stats.get('provider_count')}"
                )
                ai_shadow = summary_ai_shadow or self._resolve_ai_shadow_for_summary(raw)
                ai_shadow_fields = self._extract_ai_shadow_summary_fields(ai_shadow)
                found = bool(ai_shadow)
                self._safe_log_info(
                    "[AITS][DecisionRouter] ai_shadow_summary_resolved | "
                    f"found={found} | "
                    f"ai_state={ai_shadow_fields.get('ai_state')} | "
                    f"ai_action={ai_shadow_fields.get('ai_action')}"
                )
                self._safe_log_info(
                    "[AITS][RouterSummary] "
                    f"ai_state={ai_shadow_fields.get('ai_state')} | "
                    f"ai_action={ai_shadow_fields.get('ai_action')} | "
                    "ai_applied=False"
                )
            except Exception:
                pass

            ai_verification_provider = self._resolve_ai_verification_provider(raw)
            performance_boost = raw.get("performance_boost", {})
            fusion_override = raw.get("fusion_override", {})
            soft_override_candidate = raw.get("soft_override_candidate", {})
            shadow_signal = raw.get("shadow_signal", {})
            context_data = raw.get("context", {})
            if not isinstance(context_data, dict):
                context_data = {}

            ai_verification_context = self._build_ai_verification_context(
                final_action=getattr(decision, "action", None),
                final_confidence=self._safe_float(getattr(decision, "confidence", 0.0), 0.0),
                fusion_signal=fusion_override,
                performance_boost=performance_boost,
                soft_override_candidate=soft_override_candidate,
                market_regime=(
                    raw.get("provider_shadow_market_regime")
                    or context_data.get("market_regime")
                    or shadow_signal.get("market_regime")
                    if isinstance(shadow_signal, dict)
                    else raw.get("provider_shadow_market_regime")
                ),
                candidate_count=raw.get("provider_shadow_candidate_count") or context_data.get("candidate_count"),
                positions_count=raw.get("provider_shadow_positions_count") or context_data.get("positions_count"),
                symbol=getattr(decision, "selected_symbol", None) or raw.get("symbol"),
                execution_allowed=raw.get("provider_shadow_execution_allowed"),
            )

            ai_verification_suggestion = self._run_ai_verification_shadow(
                ai_verification_provider,
                ai_verification_context,
            )
            self._safe_log_info(
                "[AITS][AIVerification] "
                f"provider={ai_verification_suggestion.get('provider')} | "
                f"called={ai_verification_suggestion.get('called')} | "
                f"suggestion={ai_verification_suggestion.get('suggestion')} | "
                f"reason={ai_verification_suggestion.get('reason')}"
            )
            self._safe_log_info(
                "[AITS][DecisionRouter] ai_suggestion_received | "
                "suggestion_only=True | applied_to_action=False"
            )
            try:
                self._last_ai_verification_suggestion = ai_verification_suggestion
            except Exception:
                pass

            try:
                _ai_summary = locals().get("ai_verification_suggestion", None)

                if isinstance(_ai_summary, dict):
                    _ai_suggestion = str(_ai_summary.get("suggestion") or "none")
                    _ai_delta = _ai_summary.get("observe_only_weight_delta", 0.0)
                    _ai_reason = str(
                        _ai_summary.get("observe_only_weight_reason")
                        or _ai_summary.get("reason")
                        or ""
                    )
                    _shadow_delta = _ai_summary.get("shadow_confidence_delta", 0.0)
                    _shadow_policy = str(
                        _ai_summary.get("shadow_confidence_policy")
                        or "not_recorded"
                    )
                else:
                    _ai_suggestion = "none"
                    _ai_delta = 0.0
                    _ai_reason = "not_recorded_yet"
                    _shadow_delta = 0.0
                    _shadow_policy = "not_recorded"

                try:
                    _apply_delta = self._safe_float(
                        getattr(
                            self,
                            "_last_micro_confidence_delta",
                            getattr(self, "_last_ai_micro_apply_delta", 0.0),
                        ),
                        0.0,
                    )
                    _micro_applied = bool(getattr(self, "_last_micro_confidence_applied", False))
                except Exception:
                    _apply_delta = 0.0
                    _micro_applied = False

                self._safe_log_info(
                    "[AITS][RouterSummaryAI] "
                    f"ai={_ai_suggestion} | "
                    f"ai_delta={float(_ai_delta):.3f} | "
                    f"ai_reason={_ai_reason} | "
                    f"shadow_delta={float(_shadow_delta):.3f} | "
                    f"shadow_policy={_shadow_policy} | "
                    f"micro_delta={_apply_delta:.4f} | "
                    f"micro_applied={_micro_applied} | "
                    f"applied=False"
                )
            except Exception:
                pass

            raw_meta = raw.setdefault("meta", {})
            if isinstance(raw_meta, dict):
                ai_suggestion_summary = {
                    "provider": ai_verification_suggestion.get("provider"),
                    "suggestion": ai_verification_suggestion.get("suggestion"),
                    "delta": ai_verification_suggestion.get("observe_only_weight_delta", 0.0),
                    "applied": False,
                }
                raw_meta["ai_suggestion"] = ai_suggestion_summary
                raw_meta["ai_verification_context"] = ai_verification_context
                raw_meta["ai_verification"] = ai_verification_suggestion
                raw_meta["ai_verification_applied"] = False
                raw_meta["ai_verification_safety"] = "suggestion_only_no_action_change"
                self._safe_log_info(
                    "[AITS][DecisionRouter] ai_suggestion_stored | "
                    "stored=True | applied=False"
                )
                history_stored = self._store_ai_suggestion_in_shadow_history(
                    raw_meta.get("ai_suggestion")
                )
                self._safe_log_info(
                    "[AITS][DecisionRouter] ai_suggestion_history | "
                    f"stored={history_stored} | applied=False"
                )
                stats = self._get_ai_suggestion_history_stats()
                try:
                    import os

                    stats_verbose = str(os.getenv("AITS_AI_STATS_VERBOSE", "1")).strip() != "0"
                except Exception:
                    stats_verbose = True
                if stats_verbose:
                    self._safe_log_info(
                        "[AITS][DecisionRouter] ai_suggestion_stats | "
                        f"window={stats.get('window', 100)} | "
                        f"total={stats.get('total_count', 0)} | "
                        f"confirm={stats.get('confirm_count', 0)} | "
                        f"reject={stats.get('reject_count', 0)} | "
                        f"skip={stats.get('skip_count', 0)} | "
                        f"openai={stats.get('openai_count', 0)} | "
                        f"gemini={stats.get('gemini_count', 0)} | "
                        f"basic={stats.get('basic_count', 0)} | "
                        f"openai_confirm={stats.get('openai_confirm', 0)} | "
                        f"openai_reject={stats.get('openai_reject', 0)} | "
                        f"openai_skip={stats.get('openai_skip', 0)} | "
                        f"gemini_confirm={stats.get('gemini_confirm', 0)} | "
                        f"gemini_reject={stats.get('gemini_reject', 0)} | "
                        f"gemini_skip={stats.get('gemini_skip', 0)} | "
                        f"basic_confirm={stats.get('basic_confirm', 0)} | "
                        f"basic_reject={stats.get('basic_reject', 0)} | "
                        f"basic_skip={stats.get('basic_skip', 0)} | "
                        "applied=False"
                    )
                    self._safe_log_info(
                        "[AITS][DecisionRouter] ai_suggestion_stats_compact | "
                        f"window={stats.get('window', 100)} | "
                        f"total={stats.get('total_count', 0)} | "
                        f"confirm={stats.get('confirm_count', 0)} | "
                        f"reject={stats.get('reject_count', 0)} | "
                        f"skip={stats.get('skip_count', 0)} | "
                        "applied=0"
                    )

            self._safe_log_info(
                "[AITS][AIVerification] recorded | "
                f"provider={ai_verification_suggestion.get('provider')} | "
                f"suggestion={ai_verification_suggestion.get('suggestion')} | "
                f"applied={ai_verification_suggestion.get('applied')}"
            )
        except Exception:
            self._safe_log_warning("[AITS][RouterSummary] failed")

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

    def _build_sample_ai_shadow_for_router(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "suggestion": "confirm",
            "confidence": 0.72,
            "next_action": "watch",
            "scenario": {"label_ko": "횡보 관찰형", "name": "sideways_watch"},
            "eta": {
                "remaining_minutes": 30,
                "reason": "거래대금과 추세 재확인 필요",
            },
            "pool_action": {"action": "watch", "reason": "관찰 가치 있음"},
            "valid": True,
            "suggestion_only": True,
            "applied_to_action": False,
            "applied": False,
        }

    def _resolve_ai_shadow_for_router(self, context_data: Dict[str, Any]) -> dict | None:
        try:
            if isinstance(context_data, dict) and isinstance(context_data.get("ai_shadow"), dict):
                return context_data.get("ai_shadow")
            enabled = str(os.getenv("AITS_INJECT_SAMPLE_AI_SHADOW", "") or "").strip() == "1"
            if not enabled:
                return None
            self._safe_log_info(
                "[AITS][DecisionRouter] sample_ai_shadow_injected | "
                "enabled=True | applied=False"
            )
            return self._build_sample_ai_shadow_for_router()
        except Exception:
            return None

    def _attach_ai_shadow_meta(self, raw: dict, ai_shadow: dict | None) -> bool:
        attached = False
        try:
            if not isinstance(raw, dict) or not isinstance(ai_shadow, dict):
                return False
            allowed_fields = {
                "provider",
                "suggestion",
                "confidence",
                "next_action",
                "briefing",
                "evidence",
                "scenario",
                "eta",
                "prediction",
                "pool_action",
                "valid",
                "suggestion_only",
                "applied_to_action",
                "applied",
            }
            clean_shadow = {
                key: ai_shadow.get(key)
                for key in allowed_fields
                if key in ai_shadow
            }
            clean_shadow["suggestion_only"] = True
            clean_shadow["applied_to_action"] = False
            clean_shadow["applied"] = False

            meta = raw.setdefault("meta", {})
            if not isinstance(meta, dict):
                meta = {}
                raw["meta"] = meta
            meta["ai_shadow"] = clean_shadow
            attached = True
            return True
        except Exception:
            return False
        finally:
            self._safe_log_info(
                "[AITS][DecisionRouter] ai_shadow_attached | "
                f"attached={bool(attached)} | applied=False"
            )

    def _extract_ai_shadow_summary_fields(self, ai_shadow: dict) -> Dict[str, Any]:
        try:
            shadow = ai_shadow if isinstance(ai_shadow, dict) else {}
            scenario = shadow.get("scenario") if isinstance(shadow.get("scenario"), dict) else {}
            eta = shadow.get("eta") if isinstance(shadow.get("eta"), dict) else {}

            scenario_label = str(scenario.get("label_ko") or "").strip()
            scenario_name = str(scenario.get("name") or "").strip()
            next_action = str(shadow.get("next_action") or "").strip()
            suggestion = str(shadow.get("suggestion") or "").strip()

            ai_state = scenario_label or scenario_name or next_action or "-"
            ai_action = next_action or suggestion or "-"
            ai_scenario = scenario_label or scenario_name or "-"
            ai_eta = eta.get("remaining_minutes")
            if ai_eta in (None, ""):
                ai_eta = "-"

            return {
                "ai_state": ai_state,
                "ai_action": ai_action,
                "ai_scenario": ai_scenario,
                "ai_eta": ai_eta,
                "ai_applied": False,
            }
        except Exception:
            return {
                "ai_state": "-",
                "ai_action": "-",
                "ai_scenario": "-",
                "ai_eta": "-",
                "ai_applied": False,
            }

    def _resolve_ai_shadow_for_summary(self, raw: dict | None = None) -> Dict[str, Any]:
        try:
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                if isinstance(meta, dict) and isinstance(meta.get("ai_shadow"), dict):
                    return meta.get("ai_shadow") or {}

            resolved = getattr(self, "_last_resolved_ai_shadow_for_router", None)
            if isinstance(resolved, dict) and resolved:
                return resolved

            history = getattr(self, "shadow_history", None)
            if isinstance(history, list) and history:
                latest = history[-1]
                if isinstance(latest, dict) and isinstance(latest.get("ai_shadow"), dict):
                    return latest.get("ai_shadow") or {}
        except Exception:
            pass
        return {}

    def _build_ai_provider_stats_summary(self) -> Dict[str, Any]:
        try:
            history = getattr(self, "shadow_history", None)
            records = list(history) if isinstance(history, list) else []
            stats = AIProviderComparisonStats().build_stats(records)
            providers = stats.get("providers") if isinstance(stats, dict) else {}
            if not isinstance(providers, dict):
                providers = {}
            parts = []
            for provider in sorted(providers):
                bucket = providers.get(provider) or {}
                if not isinstance(bucket, dict):
                    continue
                parts.append(
                    f"{provider}:"
                    f"t{int(bucket.get('total') or 0)}/"
                    f"c{int(bucket.get('confirm') or 0)}/"
                    f"s{int(bucket.get('skip') or 0)}/"
                    f"w{int(bucket.get('watch') or 0)}/"
                    f"a{int(bucket.get('applied_count') or 0)}"
                )
            return {
                "total": int(stats.get("total") or 0) if isinstance(stats, dict) else 0,
                "provider_count": len(providers),
                "compact": " | ".join(parts) if parts else "-",
            }
        except Exception:
            return {
                "total": 0,
                "provider_count": 0,
                "compact": "-",
            }

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

    def _safe_log_warning(self, message: str) -> None:
        try:
            if self.logger is not None:
                if hasattr(self.logger, "warning"):
                    self.logger.warning(message)
                elif hasattr(self.logger, "info"):
                    self.logger.info(message)
        except Exception:
            pass

    def _resolve_shadow_history_path(self, history_path: Optional[Any] = None) -> Path:
        try:
            if history_path:
                return Path(history_path)
            root = Path(__file__).resolve().parents[2]
            return root / "data" / "shadow_history.json"
        except Exception:
            return Path("data") / "shadow_history.json"

    def _load_shadow_history(self) -> list[Dict[str, Any]]:
        try:
            path = Path(getattr(self, "shadow_history_path", Path("data") / "shadow_history.json"))
            if not path.exists():
                self._safe_log_info("[AITS][DecisionRouter] shadow_history_loaded | count=0")
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self._safe_log_info("[AITS][DecisionRouter] shadow_history_loaded | count=0")
                return []
            rows = [row for row in data if isinstance(row, dict)]
            rows = rows[-self.shadow_history_limit :]
            self._safe_log_info(
                f"[AITS][DecisionRouter] shadow_history_loaded | count={len(rows)}"
            )
            return rows
        except Exception:
            self._safe_log_info("[AITS][DecisionRouter] shadow_history_loaded | count=0")
            return []

    def _resolve_shadow_performance_path(
        self,
        performance_path: Optional[Any] = None,
        history_path: Optional[Any] = None,
    ) -> Path:
        try:
            if performance_path:
                return Path(performance_path)
            if history_path:
                return Path(history_path).parent / "shadow_performance.json"
            root = Path(__file__).resolve().parents[2]
            return root / "data" / "shadow_performance.json"
        except Exception:
            return Path("data") / "shadow_performance.json"

    def _load_shadow_performance(self) -> list[Dict[str, Any]]:
        try:
            path = Path(getattr(self, "performance_path", Path("data") / "shadow_performance.json"))
            if not path.exists():
                self._safe_log_info("[AITS][DecisionRouter] shadow_performance_loaded | count=0")
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self._safe_log_info("[AITS][DecisionRouter] shadow_performance_loaded | count=0")
                return []
            rows = [row for row in data if isinstance(row, dict)]
            rows = rows[-self.shadow_performance_limit :]
            self._safe_log_info(
                f"[AITS][DecisionRouter] shadow_performance_loaded | count={len(rows)}"
            )
            return rows
        except Exception:
            self._safe_log_info("[AITS][DecisionRouter] shadow_performance_loaded | count=0")
            return []

    def _save_shadow_performance(self) -> None:
        try:
            path = Path(getattr(self, "performance_path", Path("data") / "shadow_performance.json"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    list(getattr(self, "shadow_performance", []) or []),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] shadow_performance_save_failed | "
                f"reason={str(exc)[:160]}"
            )

    def _save_shadow_history(self) -> None:
        try:
            path = Path(getattr(self, "shadow_history_path", Path("data") / "shadow_history.json"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    list(getattr(self, "shadow_history", []) or []),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            self.shadow_history_persisted = True
        except Exception as exc:
            self.shadow_history_persisted = False
            self._safe_log_warning(
                "[AITS][DecisionRouter] shadow_history_save_failed | "
                f"error={str(exc)[:160]}"
            )

    def _record_shadow_history(
        self,
        *,
        provider: str,
        shadow_decision: Optional[Any],
        final_action: str,
        final_confidence: float,
    ) -> None:
        try:
            if shadow_decision is None:
                return
            raw = dict(getattr(shadow_decision, "raw", {}) or {})
            raw_meta = raw.get("meta", {})
            if not isinstance(raw_meta, dict):
                raw_meta = {}
            ai_shadow_for_history = self._sanitize_ai_shadow_history_fields(
                raw_meta.get("ai_shadow")
            )
            record = {
                "timestamp": self._now_iso(),
                "provider": str(provider or ""),
                "shadow_action": str(getattr(shadow_decision, "action", "") or ""),
                "shadow_confidence": self._safe_float(
                    getattr(shadow_decision, "confidence", 0.0),
                    0.0,
                ),
                "shadow_rule": str(raw.get("shadow_rule") or ""),
                "risk_hint": str(raw.get("risk_hint") or ""),
                "rule_action": str(raw.get("rule_action") or ""),
                "market_regime": str(raw.get("market_regime") or ""),
                "candidate_count": self._safe_int(raw.get("candidate_count"), 0),
                "positions_count": self._safe_int(raw.get("positions_count"), 0),
                "final_action": str(final_action or ""),
                "final_confidence": self._safe_float(final_confidence, 0.0),
                "execution_allowed": bool(raw.get("execution_allowed", False)),
                "ai_suggestion": raw_meta.get("ai_suggestion"),
            }
            if ai_shadow_for_history:
                record["ai_shadow"] = ai_shadow_for_history
            self.shadow_history.append(record)
            if len(self.shadow_history) > self.shadow_history_limit:
                self.shadow_history = self.shadow_history[-self.shadow_history_limit :]
            self._save_shadow_history()
            self._safe_log_info(
                "[AITS][DecisionRouter] ai_shadow_history | "
                f"stored={bool(ai_shadow_for_history)} | applied=False"
            )
        except Exception:
            pass

    def _sanitize_ai_shadow_history_fields(self, ai_shadow: Any) -> Dict[str, Any]:
        try:
            if not isinstance(ai_shadow, dict):
                return {}
            allowed_fields = {
                "provider",
                "suggestion",
                "confidence",
                "next_action",
                "scenario",
                "eta",
                "pool_action",
                "valid",
            }
            clean_shadow = {
                key: ai_shadow.get(key)
                for key in allowed_fields
                if key in ai_shadow
            }
            clean_shadow["applied"] = False
            clean_shadow["applied_to_action"] = False
            return clean_shadow
        except Exception:
            return {}

    def _store_ai_shadow_in_shadow_history(self, ai_shadow: Any) -> bool:
        stored = False
        try:
            clean_shadow = self._sanitize_ai_shadow_history_fields(ai_shadow)
            if not clean_shadow:
                return False
            history = getattr(self, "shadow_history", None)
            if not isinstance(history, list):
                history = []
                self.shadow_history = history
            if history:
                latest = history[-1]
            else:
                latest = {
                    "timestamp": self._now_iso(),
                    "ai_applied": False,
                    "submitted": 0,
                }
                history.append(latest)
            if not isinstance(latest, dict):
                return False
            latest["ai_shadow"] = clean_shadow
            self._save_shadow_history()
            stored = True
            return True
        except Exception:
            return False
        finally:
            self._safe_log_info(
                "[AITS][DecisionRouter] ai_shadow_history | "
                f"stored={bool(stored)} | applied=False"
            )

    def _store_ai_suggestion_in_shadow_history(self, ai_suggestion: Any) -> bool:
        try:
            if not isinstance(ai_suggestion, dict):
                return False
            history = getattr(self, "shadow_history", None)
            if not history:
                return False
            latest = history[-1]
            if not isinstance(latest, dict):
                return False
            latest["ai_suggestion"] = ai_suggestion
            self._save_shadow_history()
            return True
        except Exception:
            return False

    def _get_ai_suggestion_history_stats(self) -> Dict[str, int]:
        stats = {
            "window": 100,
            "total_count": 0,
            "confirm_count": 0,
            "reject_count": 0,
            "skip_count": 0,
            "openai_count": 0,
            "gemini_count": 0,
            "basic_count": 0,
            "openai_confirm": 0,
            "openai_reject": 0,
            "openai_skip": 0,
            "gemini_confirm": 0,
            "gemini_reject": 0,
            "gemini_skip": 0,
            "basic_confirm": 0,
            "basic_reject": 0,
            "basic_skip": 0,
        }
        try:
            records = list(getattr(self, "shadow_history", []) or [])
            recent_records = records[-100:]
            for row in recent_records:
                if not isinstance(row, dict):
                    continue
                ai_suggestion = row.get("ai_suggestion")
                if isinstance(ai_suggestion, dict):
                    suggestion = str(ai_suggestion.get("suggestion") or "").strip().lower()
                    provider = str(ai_suggestion.get("provider") or "").strip().lower()
                else:
                    suggestion = str(ai_suggestion or "").strip().lower()
                    provider = ""
                if not suggestion:
                    continue
                stats["total_count"] += 1
                if provider in ("openai", "gpt", "chatgpt"):
                    provider_bucket = "openai"
                    stats["openai_count"] += 1
                elif provider in ("gemini", "google", "google_gemini"):
                    provider_bucket = "gemini"
                    stats["gemini_count"] += 1
                else:
                    provider_bucket = "basic"
                    stats["basic_count"] += 1
                if suggestion == "confirm":
                    stats["confirm_count"] += 1
                    stats[f"{provider_bucket}_confirm"] += 1
                elif suggestion == "reject_signal":
                    stats["reject_count"] += 1
                    stats[f"{provider_bucket}_reject"] += 1
                elif suggestion == "skip":
                    stats["skip_count"] += 1
                    stats[f"{provider_bucket}_skip"] += 1
            return stats
        except Exception:
            return stats

    def record_shadow_signal(
        self,
        *,
        signal_action: Any,
        signal_confidence: Any,
        symbol: Any,
        market_regime: Any,
        candidate_count: Any,
        current_price: Optional[Any] = None,
    ) -> None:
        try:
            base = {}
            try:
                base = getattr(self, "_last_ai_verification_suggestion", {}) or {}
                if not isinstance(base, dict):
                    base = {}
            except Exception:
                base = {}
            record = {
                "timestamp": self._now_iso(),
                "signal_action": str(signal_action or ""),
                "signal_confidence": self._safe_float(signal_confidence, 0.0),
                "symbol": str(symbol or ""),
                "market_regime": str(market_regime or ""),
                "candidate_count": self._safe_int(candidate_count, 0),
                "entry_price": self._optional_float(current_price),
                "checked": False,
                "p10m": None,
                "p30m": None,
                "p60m": None,
                "ai_suggestion": str(base.get("suggestion") or "skip"),
                "ai_reason": str(base.get("reason") or ""),
                "ai_shadow_delta": float(base.get("shadow_confidence_delta") or 0.0),
                "ai_shadow_policy": str(base.get("shadow_confidence_policy") or ""),
                "ai_applied": False,
            }
            try:
                # === FAST SAMPLE (dev/test only) ===
                import os
                _fast_sample_on = str(os.getenv("AITS_SHADOW_FAST_SAMPLE", "0")).lower() in ("1", "true", "yes", "on")

                try:
                    global _AITS_FAST_SAMPLE_MODE_LOGGED
                    if not _AITS_FAST_SAMPLE_MODE_LOGGED:
                        self._safe_log_info(
                            "[AITS][ShadowFastSample] "
                            f"mode={'on' if _fast_sample_on else 'off'}"
                        )
                        _AITS_FAST_SAMPLE_MODE_LOGGED = True
                except Exception:
                    pass

                if not _fast_sample_on:
                    # fast sample 비활성화 시 proxy 생성 안 함
                    pass
                else:
                    # p10m/p30m/p60m이 없는 경우, 즉시 평가 가능한 proxy 생성
                    if record.get("p10m") is None and record.get("p30m") is None and record.get("p60m") is None:
                        import random

                        # 신호 방향에 따라 약한 편향 부여
                        _act = str(record.get("signal_action") or "")
                        _base = 0.0

                        if _act == "buy":
                            _base = 0.01
                        elif _act == "sell":
                            _base = -0.01

                        # 노이즈 추가 (±0.02 범위)
                        _n1 = _base + random.uniform(-0.02, 0.02)
                        _n2 = _base + random.uniform(-0.02, 0.02)
                        _n3 = _base + random.uniform(-0.02, 0.02)

                        # proxy 필드로만 저장 (기존 pXX 필드는 건드리지 않음)
                        record["p10m_proxy"] = round(_n1, 4)
                        record["p30m_proxy"] = round(_n2, 4)
                        record["p60m_proxy"] = round(_n3, 4)
                        record["eval_source"] = "proxy"

                        self._safe_log_info(
                            "[AITS][ShadowFastSample] "
                            f"proxy_applied=True | act={_act} | "
                            f"p10m_proxy={record['p10m_proxy']} | "
                            f"p30m_proxy={record['p30m_proxy']} | "
                            f"p60m_proxy={record['p60m_proxy']}"
                        )
            except Exception:
                pass
            self.shadow_performance.append(record)
            if len(self.shadow_performance) > self.shadow_performance_limit:
                self.shadow_performance = self.shadow_performance[-self.shadow_performance_limit :]
            self._save_shadow_performance()
            self._log_ai_shadow_stats_after_save()
            self._safe_log_info(
                "[AITS][DecisionRouter] performance_signal_recorded | "
                f"action={record['signal_action']} | symbol={record['symbol']}"
            )
        except Exception:
            pass

    def update_shadow_performance(self, price_lookup_func: Any) -> None:
        try:
            if price_lookup_func is None:
                self._safe_log_info("[AITS][DecisionRouter] performance_update_start | pending=0")
                return
            now = datetime.now(timezone.utc)
            updated = False
            rows = list(getattr(self, "shadow_performance", []) or [])
            pending = [row for row in rows if not bool(row.get("checked", False))]
            self._safe_log_info(
                "[AITS][DecisionRouter] performance_update_start | "
                f"pending={len(pending)}"
            )
            for row in rows:
                try:
                    if bool(row.get("checked", False)):
                        continue
                    symbol = str(row.get("symbol") or "").strip()
                    if not symbol or symbol == "*":
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_update_skipped | "
                            "reason=missing_symbol"
                        )
                        continue
                    entry_price = self._optional_float(row.get("entry_price"))
                    if entry_price is None or entry_price <= 0.0:
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_update_skipped | "
                            f"symbol={symbol} | reason=missing_entry_price"
                        )
                        continue
                    ts_raw = str(row.get("timestamp") or "")
                    try:
                        ts = datetime.fromisoformat(ts_raw)
                    except Exception:
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_update_skipped | "
                            f"symbol={symbol} | reason=bad_timestamp"
                        )
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    elapsed_sec = (now - ts).total_seconds()
                    try:
                        now_price = self._optional_float(price_lookup_func(symbol))
                    except Exception:
                        now_price = None
                    self._safe_log_info(
                        "[AITS][DecisionRouter] performance_price | "
                        f"symbol={symbol} | price={now_price if now_price is not None else 'None'}"
                    )
                    if now_price is None or now_price <= 0.0:
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_update_skipped | "
                            f"symbol={symbol} | reason=missing_current_price"
                        )
                        continue
                    if elapsed_sec < 600.0:
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_update_waiting | "
                            f"symbol={symbol} | elapsed_sec={int(elapsed_sec)}"
                        )
                        continue
                    elapsed_min = elapsed_sec / 60.0
                    pnl = round(((now_price - entry_price) / entry_price) * 100.0, 4)
                    if elapsed_min >= 10.0 and row.get("p10m") is None:
                        row["p10m"] = pnl
                        updated = True
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_updated | "
                            f"symbol={symbol} | field=p10m | value={pnl:.2f}"
                        )
                    if elapsed_min >= 30.0 and row.get("p30m") is None:
                        row["p30m"] = pnl
                        updated = True
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_updated | "
                            f"symbol={symbol} | field=p30m | value={pnl:.2f}"
                        )
                    if elapsed_min >= 60.0 and row.get("p60m") is None:
                        row["p60m"] = pnl
                        row["checked"] = True
                        updated = True
                        self._safe_log_info(
                            "[AITS][DecisionRouter] performance_updated | "
                            f"symbol={symbol} | field=p60m | value={pnl:.2f}"
                        )
                except Exception:
                    continue
            if updated:
                self._save_shadow_performance()
        except Exception:
            pass

    def _get_shadow_history_summary(self) -> Dict[str, Any]:
        try:
            rows = list(getattr(self, "shadow_history", None) or [])
            count = len(rows)
            counts = {"buy": 0, "sell": 0, "hold": 0, "wait": 0}
            total_confidence = 0.0
            for row in rows:
                action = str(row.get("shadow_action") or "").lower()
                if action in counts:
                    counts[action] += 1
                total_confidence += self._safe_float(row.get("shadow_confidence"), 0.0)
            last_action = str(rows[-1].get("shadow_action") or "") if rows else ""
            avg_confidence = (total_confidence / count) if count > 0 else 0.0
            consistency = "mixed"
            if count >= 3:
                buy_ratio = counts["buy"] / count
                sell_ratio = counts["sell"] / count
                neutral_ratio = (counts["hold"] + counts["wait"]) / count
                if buy_ratio >= 0.60:
                    consistency = "buy_bias"
                elif sell_ratio >= 0.60:
                    consistency = "sell_bias"
                elif neutral_ratio >= 0.60:
                    consistency = "neutral_wait"
            return {
                "count": count,
                "buy": counts["buy"],
                "sell": counts["sell"],
                "hold": counts["hold"],
                "wait": counts["wait"],
                "last_action": last_action,
                "consistency": consistency,
                "avg_confidence": round(avg_confidence, 4),
            }
        except Exception:
            return {
                "count": 0,
                "buy": 0,
                "sell": 0,
                "hold": 0,
                "wait": 0,
                "last_action": "",
                "consistency": "mixed",
                "avg_confidence": 0.0,
            }

    def _latest_shadow_market_regime(self) -> str:
        try:
            for row in reversed(list(getattr(self, "shadow_history", None) or [])):
                if not isinstance(row, dict):
                    continue
                regime = str(row.get("market_regime") or "").strip().lower()
                if regime:
                    return regime
        except Exception:
            pass
        return ""

    def _local_shadow_meta(self, decision: Optional[Any]) -> Dict[str, Any]:
        try:
            if decision is None or str(getattr(decision, "engine", "") or "") != "local":
                return {}
            raw = dict(getattr(decision, "raw", {}) or {})
            return {
                "local_shadow_rule_action": raw.get("rule_action"),
                "local_shadow_reason": str(getattr(decision, "reason", "") or ""),
                "local_shadow_confidence": self._safe_float(
                    getattr(decision, "confidence", 0.0),
                    0.0,
                ),
                "provider_shadow_summary": raw.get("shadow_summary"),
                "provider_shadow_risk_hint": raw.get("risk_hint"),
                "provider_shadow_rule_action": raw.get("rule_action"),
                "provider_shadow_market_regime": raw.get("market_regime"),
                "provider_shadow_candidate_count": raw.get("candidate_count"),
                "provider_shadow_positions_count": raw.get("positions_count"),
                "provider_shadow_rule": raw.get("shadow_rule"),
                "provider_shadow_execution_allowed": raw.get("execution_allowed"),
            }
        except Exception:
            return {}

    def _trim_log_text(self, value: Any, limit: int = 120) -> str:
        text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
        if len(text) <= limit:
            return text
        return text[:limit]

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

    def _optional_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            result = float(value)
            return result
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
