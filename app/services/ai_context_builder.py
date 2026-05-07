from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Dict, Optional


CONTEXT_PACK_VERSION = "context_pack_v1"
SENSITIVE_KEY_PARTS = ("key", "secret", "token", "password", "credential")


@dataclass
class AIContextPack:
    market: Dict[str, Any] = field(default_factory=dict)
    portfolio: Dict[str, Any] = field(default_factory=dict)
    opportunity: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    news: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_compact_dict(self) -> Dict[str, Any]:
        # Do not include API keys, secrets, tokens, or credentials in provider input.
        return {
            "version": self.meta.get("version"),
            "market": self.market,
            "portfolio": self.portfolio,
            "opportunity": self.opportunity,
            "risk": self.risk,
            "news": self.news,
            "safety": {
                "suggestion_only": True,
                "applied_to_action": False,
            },
        }


class AIContextBuilder:
    def __init__(self, logger: Optional[Any] = None) -> None:
        self.logger = logger

    def build_context(
        self,
        market_data: Optional[Any] = None,
        portfolio_state: Optional[Any] = None,
        candidates: Optional[Any] = None,
        news_items: Optional[Any] = None,
        runtime_state: Optional[Any] = None,
    ) -> AIContextPack:
        market = self._build_market_context(market_data)
        portfolio = self._build_portfolio_context(portfolio_state)
        opportunity = self._build_opportunity_context(candidates)
        risk = self._build_risk_context(market_data, portfolio_state, runtime_state)
        news = self._build_news_context(news_items)
        meta = self._build_meta_context(runtime_state)

        context_pack = AIContextPack(
            market=market,
            portfolio=portfolio,
            opportunity=opportunity,
            risk=risk,
            news=news,
            meta=meta,
        )

        self._safe_log_info(
            "[AITS][AIContextBuilder] context_built"
            f" | market={self._status_of(market)}"
            f" | portfolio={self._status_of(portfolio)}"
            f" | opportunity={self._status_of(opportunity)}"
            f" | risk={self._status_of(risk)}"
            f" | news={self._status_of(news)}"
        )
        return context_pack

    def _build_market_context(self, market_data: Optional[Any] = None) -> Dict[str, Any]:
        if not market_data:
            return {"status": "empty", "reason": "no_market_data"}
        return {
            "status": "provided",
            "data": self._safe_copy(market_data),
        }

    def _build_portfolio_context(
        self,
        portfolio_state: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not portfolio_state:
            return {"status": "empty", "reason": "no_portfolio_state"}
        return {
            "status": "provided",
            "data": self._safe_copy(portfolio_state),
        }

    def _build_opportunity_context(
        self,
        candidates: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not candidates:
            return {"status": "empty", "reason": "no_candidates"}
        return {
            "status": "provided",
            "data": self._safe_copy(candidates),
        }

    def _build_risk_context(
        self,
        market_data: Optional[Any] = None,
        portfolio_state: Optional[Any] = None,
        runtime_state: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not market_data and not portfolio_state and not runtime_state:
            return {"status": "empty", "reason": "no_risk_inputs"}
        return {
            "status": "provided",
            "market_available": bool(market_data),
            "portfolio_available": bool(portfolio_state),
            "runtime_available": bool(runtime_state),
        }

    def _build_news_context(self, news_items: Optional[Any] = None) -> Dict[str, Any]:
        if not news_items:
            return {"status": "empty", "reason": "no_news_items"}
        return {
            "status": "provided",
            "data": self._safe_copy(news_items),
        }

    def _build_meta_context(self, runtime_state: Optional[Any] = None) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "version": CONTEXT_PACK_VERSION,
            "suggestion_only": True,
            "applied_to_action": False,
        }
        if runtime_state:
            meta["runtime"] = self._safe_copy(runtime_state)
        else:
            meta["runtime"] = {"status": "empty", "reason": "no_runtime_state"}
        return meta

    def _safe_copy(self, value: Any) -> Any:
        if isinstance(value, dict):
            copied: Dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if self._is_sensitive_key(key_text):
                    copied[key_text] = "[redacted]"
                else:
                    copied[key_text] = self._safe_copy(item)
            return copied
        if isinstance(value, list):
            return [self._safe_copy(item) for item in value]
        if isinstance(value, tuple):
            return [self._safe_copy(item) for item in value]
        return value

    def _is_sensitive_key(self, key: str) -> bool:
        key_lower = str(key or "").lower()
        return any(part in key_lower for part in SENSITIVE_KEY_PARTS)

    def _status_of(self, context: Dict[str, Any]) -> str:
        return str(context.get("status") or "unknown")

    def _safe_log_info(self, message: str) -> None:
        try:
            if self.logger is not None and hasattr(self.logger, "info"):
                self.logger.info(message)
                return
            logging.getLogger("aits").info(message)
        except Exception:
            pass


def build_sample_context_pack() -> AIContextPack:
    builder = AIContextBuilder()
    market_data = {"sample": "market"}
    portfolio_state = {"sample": "portfolio"}
    candidates = {"sample": "opportunity"}
    news_items = {"sample": "news"}
    runtime_state = {"sample": "runtime"}
    return builder.build_context(
        market_data=market_data,
        portfolio_state=portfolio_state,
        candidates=candidates,
        news_items=news_items,
        runtime_state=runtime_state,
    )


def build_sample_context_pack() -> AIContextPack:
    market_data = {
        "regime": "risk_on",
        "btc_trend": "up",
        "volatility": "medium",
        "volume_state": "expanding",
    }
    portfolio_state = {
        "cash_ratio": 0.42,
        "positions_count": 3,
        "unrealized_pnl_pct": 1.8,
    }
    candidates = [
        {
            "symbol": "BTC",
            "score": 0.78,
            "reason": "trend_strength",
        }
    ]
    news_items = [
        {
            "title": "Market sentiment improves as volume expands",
            "sentiment": "positive",
        }
    ]
    runtime_state = {
        "provider": "sample",
        "execution_mode": "context_only",
        "ai_status": "offline_sample",
    }

    context_pack = AIContextBuilder().build_context(
        market_data=market_data,
        portfolio_state=portfolio_state,
        candidates=candidates,
        news_items=news_items,
        runtime_state=runtime_state,
    )

    try:
        logging.getLogger("aits").info(
            "[AITS][AIContextBuilder] sample_context_built | ok=True"
        )
    except Exception:
        pass
    return context_pack
