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

ROUTER_VERSION = "v1.2"
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
                if shadow_signal.get("action") != "none":
                    self._safe_log_info(
                        "[AITS][DecisionRouter] shadow_signal | "
                        f"action={shadow_signal.get('action')} | "
                        f"confidence={self._safe_float(shadow_signal.get('confidence'), 0.0):.3f} | "
                        f"reason={shadow_signal.get('reason')}"
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
                return {"action": "none", "confidence": 0.0, "reason": "history_lt_3"}

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

            if buy5 >= 5:
                return {
                    "action": "buy_strong",
                    "confidence": avg_conf(recent5),
                    "reason": "shadow_buy_5_confirmed",
                }

            if sell5 >= 5:
                return {
                    "action": "sell_strong",
                    "confidence": avg_conf(recent5),
                    "reason": "shadow_sell_5_confirmed",
                }

            if buy3 >= 3:
                return {
                    "action": "buy",
                    "confidence": avg_conf(recent3),
                    "reason": "shadow_buy_3_confirmed",
                }

            if sell3 >= 3:
                return {
                    "action": "reduce",
                    "confidence": avg_conf(recent3),
                    "reason": "shadow_sell_3_confirmed",
                }

            return {"action": "none", "confidence": 0.0, "reason": "no_signal"}
        except Exception:
            return {"action": "none", "confidence": 0.0, "reason": "signal_error"}

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

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
