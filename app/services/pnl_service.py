from __future__ import annotations
import time, logging
from typing import Dict, Any, List, Optional
from math import floor

log = logging.getLogger(__name__)

MIN_ORDER_KRW = 5000

# -----------------------------------------------------
# [KMTS] 공통 포지션 / PnL / 먼지판정 헬퍼
# -----------------------------------------------------

def calc_unrealized_pnl(avg_cost: float, current_price: float, qty: float) -> float:
    """
    미실현 손익(%) 계산: (현재가-평단)/평단*100
    예외 또는 잘못된 입력시 0 반환
    """
    try:
        if avg_cost <= 0 or qty <= 0 or current_price <= 0:
            return 0.0
        return (current_price - avg_cost) / avg_cost * 100.0
    except Exception:
        return 0.0


def est_position_value(current_price: float, qty: float) -> float:
    """
    현재 포지션 평가금액(원)
    """
    try:
        return max(float(current_price or 0.0) * float(qty or 0.0), 0.0)
    except Exception:
        return 0.0


def is_dust_position(current_price: float, qty: float, min_krw: int = MIN_ORDER_KRW) -> bool:
    """
    추정금액 < 최소주문금액이면 먼지 포지션으로 간주
    """
    try:
        val = est_position_value(current_price, qty)
        return val < float(min_krw)
    except Exception:
        return False


def dust_reason_str(market: str, current_price: float, qty: float, min_krw: int = MIN_ORDER_KRW) -> str:
    """
    로그/알림용 문구
    """
    try:
        est = est_position_value(current_price, qty)
        return f"{market} 추정금액 {floor(est)}원 < {min_krw}원 → 먼지 포지션"
    except Exception:
        return f"{market} 먼지 포지션 (계산오류)"


def evaluate_positions(pos_list: List[Dict[str, Any]], price_by_market: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    포지션 목록 + 현재가 맵(by market) → 평가금액, 손익률, 먼지 여부 계산 후 리턴
    """
    out = []
    for p in pos_list or []:
        m = p.get("market")
        qty = float(p.get("qty") or 0)
        avg = float(p.get("avg_cost") or 0)
        px  = None
        try:
            px = price_by_market.get(m, {}).get("trade_price")
            if not isinstance(px, (float, int)):
                px = None
        except Exception:
            px = None

        est_val = est_position_value(px or 0.0, qty)
        pnl_pct = calc_unrealized_pnl(avg, px or 0.0, qty)
        is_dust = is_dust_position(px or 0.0, qty)

        out.append({
            "market": m,
            "qty": qty,
            "avg_cost": avg,
            "current_price": px,
            "est_value": est_val,
            "unrealized_pnl_pct": pnl_pct,
            "is_dust": is_dust,
        })
    return out


# -----------------------------------------------------
# 테스트용 스텁 (runner나 UI에서 간단 확인 가능)
# -----------------------------------------------------
if __name__ == "__main__":
    # 예시 데이터
    dummy_positions = [
        {"market": "KRW-ETH", "qty": 0.001, "avg_cost": 3700000},
        {"market": "KRW-XRP", "qty": 10, "avg_cost": 700},
    ]
    dummy_prices = {
        "KRW-ETH": {"trade_price": 3800000},
        "KRW-XRP": {"trade_price": 720},
    }
    results = evaluate_positions(dummy_positions, dummy_prices)
    for r in results:
        log.info(r)
