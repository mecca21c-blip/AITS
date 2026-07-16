from __future__ import annotations

from typing import Any


class AITSLocalEngineReasonComposer:
    """Compose Korean explanations only from structured, present evidence."""

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def compose(
        self,
        *,
        action: str,
        feature_context: dict,
        confidence: float | None,
        risk: dict,
        escalation: dict,
        eta: dict,
        invalidation_conditions: list[dict],
    ) -> dict:
        market = dict(feature_context.get("market") or {})
        indicators = dict(feature_context.get("indicators") or {})
        position = dict(feature_context.get("position") or {})
        portfolio = dict(feature_context.get("portfolio") or {})
        evidence: list[dict] = []
        clauses: list[str] = []

        pnl = self._number(position.get("pnl_pct"))
        if pnl is not None:
            evidence.append({"feature": "position.pnl_pct", "value": pnl})
            clauses.append(f"현재 손익률은 {pnl:.2f}%입니다")
        momentum = self._number(indicators.get("momentum"))
        if momentum is not None:
            evidence.append({"feature": "indicators.momentum", "value": momentum})
            clauses.append(f"단기 모멘텀은 {momentum:.2f}입니다")
        volatility = self._number(market.get("volatility"))
        if volatility is not None:
            evidence.append({"feature": "market.volatility", "value": volatility})
            clauses.append(f"관측 변동성은 {volatility:.2f}입니다")
        cap_remaining = self._number(portfolio.get("cap_remaining_krw"))
        if cap_remaining is not None:
            evidence.append({"feature": "portfolio.cap_remaining_krw", "value": cap_remaining})
            clauses.append(f"포트폴리오 한도 잔여액은 {cap_remaining:,.0f}원입니다")
        ma5 = self._number(indicators.get("ma5"))
        ma20 = self._number(indicators.get("ma20"))
        if ma5 is not None and ma20 is not None:
            evidence.append({"feature": "indicators.ma5", "value": ma5})
            evidence.append({"feature": "indicators.ma20", "value": ma20})
            relation = "상회" if ma5 >= ma20 else "하회"
            clauses.append(f"단기 이동평균이 중기 이동평균을 {relation}합니다")

        risk_level = str(risk.get("risk_level") or "unknown")
        risk_factors = list(risk.get("risk_factors") or [])
        if risk_factors:
            clauses.append(f"위험 근거로 {', '.join(risk_factors[:2])}가 확인됩니다")
        if not clauses:
            clauses.append("사용 가능한 구조화 근거가 제한적입니다")

        action_copy = {
            "wait": "대기",
            "hold": "보유",
            "buy": "매수 검토",
            "add": "추가 매수 검토",
            "sell": "매도 검토",
            "reduce": "비중 축소 검토",
            "take_profit": "익절 검토",
            "stop_loss": "손절 검토",
            "rotate": "교체 검토",
        }.get(action, action)
        eta_seconds = eta.get("eta_seconds")
        conclusion = f"따라서 LOCAL_ENGINE은 {action_copy} 후보를 제안합니다"
        if eta_seconds:
            conclusion += f". {int(eta_seconds)}초 후 재판단합니다"
        if escalation.get("escalation_required"):
            conclusion += ". 외부 AI 확인이 필요합니다"

        reason = ". ".join(clauses[:3]) + ". " + conclusion + "."
        return {
            "reason_ko": reason,
            "evidence_summary": evidence,
            "risk_summary_ko": f"위험 수준은 {risk_level}이며 RiskGuard와 LivePreflight 검증이 필요합니다.",
            "wait_reason_type": "evidence_limited" if not evidence else "structured_feature_evidence",
            "reason_template_id": "local_engine_structured_reason.v1",
            "evidence_reference_valid": bool(evidence),
            "unsupported_evidence_reference_count": 0,
            "invalidation_reference_count": len(invalidation_conditions),
            "confidence_reference": confidence,
        }
