from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.aits_state import AIDecisionState
from app.services.ai_engine_provider import (
    build_default_provider_registry,
    get_provider,
)

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
                        "provider_shadow_history_summary": shadow_history_summary,
                        "shadow_signal": self.get_shadow_signal(),
                        **self._local_shadow_meta(provider_shadow_decision),
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
        soft_override_candidate = self._record_soft_override_candidate(decision)

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
                **self._local_shadow_meta(provider_shadow_decision),
                "context": context_data,
            },
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
        except Exception as exc:
            self._safe_log_warning(
                "[AITS][DecisionRouter] shadow_stats_failed | "
                f"error={str(exc)[:160]}"
            )

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

            return (
                f"action={action} | "
                f"conf={conf:.3f} | "
                f"fusion={fusion_action} | "
                f"perf={perf_status} | "
                f"soft={soft_action} | "
                f"eligible={soft_eligible}"
            )
        except Exception:
            return "summary_build_failed"

    def _log_router_summary(self, decision: Any) -> None:
        try:
            raw = getattr(decision, "raw", {}) if hasattr(decision, "raw") else {}
            if not isinstance(raw, dict):
                raw = {}
            summary = self._build_router_summary(decision, raw)
            self._safe_log_info(f"[AITS][RouterSummary] {summary}")

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
                fusion_signal=shadow_signal,
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

            ai_verification_suggestion = self._run_ai_verification_suggestion(
                provider=ai_verification_provider,
                context=ai_verification_context,
                raw=raw,
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

                self._safe_log_info(
                    "[AITS][RouterSummaryAI] "
                    f"ai={_ai_suggestion} | "
                    f"ai_delta={float(_ai_delta):.3f} | "
                    f"ai_reason={_ai_reason} | "
                    f"shadow_delta={float(_shadow_delta):.3f} | "
                    f"shadow_policy={_shadow_policy} | "
                    f"applied=False"
                )
            except Exception:
                pass

            raw_meta = raw.setdefault("meta", {})
            if isinstance(raw_meta, dict):
                raw_meta["ai_verification"] = ai_verification_suggestion
                raw_meta["ai_verification_applied"] = False
                raw_meta["ai_verification_safety"] = "suggestion_only_no_action_change"

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
            }
            self.shadow_history.append(record)
            if len(self.shadow_history) > self.shadow_history_limit:
                self.shadow_history = self.shadow_history[-self.shadow_history_limit :]
            self._save_shadow_history()
        except Exception:
            pass

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
            self.shadow_performance.append(record)
            if len(self.shadow_performance) > self.shadow_performance_limit:
                self.shadow_performance = self.shadow_performance[-self.shadow_performance_limit :]
            self._save_shadow_performance()
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
