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

ROUTER_VERSION = "v1.6"
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
                **self._local_shadow_meta(provider_shadow_decision),
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
            elif action in sell_actions:
                sell_count += 1
                if p10 is not None and p10 < 0.0:
                    sell_win_10m += 1

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
