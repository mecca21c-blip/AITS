from __future__ import annotations

from typing import Any, Dict, List, Optional


DecisionDict = Dict[str, Any]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _safe_str(v: Any, default: str = "") -> str:
    try:
        if v is None:
            return default
        return str(v)
    except Exception:
        return default


def _normalize_symbol(row: Dict[str, Any]) -> str:
    return _safe_str(
        row.get("symbol")
        or row.get("market")
        or row.get("ticker")
        or row.get("code")
        or "",
        ""
    )


def _extract_change_pct(row: Dict[str, Any]) -> float:
    # 허용 키 후보
    # - change_pct
    # - change_rate_pct
    # - signed_change_rate_pct
    # - rate
    #
    # 중요:
    # 1) *_pct 라는 이름이면 기본적으로 "이미 퍼센트값"으로 간주한다.
    #    예: 0.7 -> 0.7%
    # 2) rate 계열은 비율값(0.007 = 0.7%)일 가능성이 높으므로
    #    작은 값이면 *100 보정한다.
    # 3) signed_change_rate_pct 가 실제로 퍼센트가 아닌 비율로 들어오는 경우도 있어
    #    값이 매우 작으면 보정한다.
    if "change_pct" in row:
        return _safe_float(row.get("change_pct"), 0.0)

    if "change_rate_pct" in row:
        return _safe_float(row.get("change_rate_pct"), 0.0)

    if "signed_change_rate_pct" in row:
        v = _safe_float(row.get("signed_change_rate_pct"), 0.0)
        if -0.2 <= v <= 0.2:
            return v * 100.0
        return v

    v = _safe_float(row.get("rate"), 0.0)
    if -0.2 <= v <= 0.2:
        return v * 100.0
    return v


def _extract_volume_score_base(row: Dict[str, Any]) -> float:
    # 거래대금/거래량 계열 키를 최대한 유연하게 받음
    # 큰 값일수록 좋다.
    candidates = [
        row.get("volume_krw"),
        row.get("acc_trade_price_24h"),
        row.get("acc_trade_price"),
        row.get("trade_value"),
        row.get("volume"),
        row.get("acc_trade_volume_24h"),
    ]
    best = 0.0
    for v in candidates:
        fv = _safe_float(v, 0.0)
        if fv > best:
            best = fv
    return best


def _extract_position_symbol(pos: Dict[str, Any]) -> str:
    return _safe_str(
        pos.get("symbol")
        or pos.get("market")
        or pos.get("ticker")
        or pos.get("code")
        or "",
        ""
    )


def _extract_position_pnl_pct(pos: Dict[str, Any]) -> float:
    # 허용 키 후보
    raw = (
        pos.get("pnl_pct")
        if "pnl_pct" in pos else
        pos.get("profit_pct")
        if "profit_pct" in pos else
        pos.get("return_pct")
        if "return_pct" in pos else
        pos.get("unrealized_pnl_pct")
    )
    v = _safe_float(raw, 0.0)
    if -1.0 <= v <= 1.0:
        v *= 100.0
    return v


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _normalize_ui_score_to_internal(v: Any, default: float) -> float:
    try:
        fv = float(v)
        if fv < 0:
            return 0.0
        if fv > 100:
            fv = 100.0
        return fv / 100.0
    except Exception:
        return default


def _extract_trade_value_base(row: Dict[str, Any]) -> float:
    candidates = [
        row.get("trade_value"),
        row.get("volume_krw"),
        row.get("acc_trade_price_24h"),
        row.get("acc_trade_price"),
    ]
    best = 0.0
    for v in candidates:
        fv = _safe_float(v, 0.0)
        if fv > best:
            best = fv
    return best


def _regime_from_market(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "regime": "neutral",
            "confidence": 0.35,
            "reason": "시장 데이터 부족"
        }

    changes = [_extract_change_pct(r) for r in rows]
    pos_ratio = sum(1 for x in changes if x > 0.0) / max(len(changes), 1)
    neg_ratio = sum(1 for x in changes if x < 0.0) / max(len(changes), 1)
    avg_change = _mean(changes)

    sorted_changes = sorted(changes, reverse=True)
    top_n = min(5, len(sorted_changes))
    leader_avg = _mean(sorted_changes[:top_n]) if top_n > 0 else 0.0

    # regime 판단은 너무 공격적이지 않게 보수적으로
    if pos_ratio >= 0.62 and avg_change >= 0.35 and leader_avg >= 1.0:
        return {
            "regime": "bull",
            "confidence": min(0.90, 0.55 + pos_ratio * 0.2 + min(leader_avg, 3.0) * 0.06),
            "reason": "상승 종목 비중 우세 + 상위 주도 종목 강세"
        }

    if neg_ratio >= 0.62 and avg_change <= -0.35:
        return {
            "regime": "bear",
            "confidence": min(0.90, 0.55 + neg_ratio * 0.2 + min(abs(avg_change), 3.0) * 0.06),
            "reason": "하락 종목 비중 우세 + 평균 수익률 약세"
        }

    return {
        "regime": "neutral",
        "confidence": 0.50 + min(abs(avg_change), 1.0) * 0.05,
        "reason": "혼조 구간 / 방향성 불충분"
    }


def _score_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    vol_bases = [_extract_volume_score_base(r) for r in rows]
    max_vol = max(vol_bases) if vol_bases else 0.0
    if max_vol <= 0.0:
        max_vol = 1.0

    scored: List[Dict[str, Any]] = []
    for row in rows:
        symbol = _normalize_symbol(row)
        if not symbol:
            continue

        chg = _extract_change_pct(row)
        vol = _extract_volume_score_base(row)
        vol_norm = min(1.0, vol / max_vol)

        # 너무 %기반만 되지 않게, 변화율 + 거래 활성도 혼합
        # 음수 종목은 진입 후보에서 자연스럽게 밀리게 함
        momentum = max(-3.0, min(5.0, chg))
        momentum_norm = (momentum + 3.0) / 8.0  # -3 ~ +5 -> 0 ~ 1

        score = momentum_norm * 0.62 + vol_norm * 0.38

        scored.append({
            "symbol": symbol,
            "change_pct": round(chg, 4),
            "volume_base": vol,
            "volume_norm": round(vol_norm, 4),
            "score": round(score, 4),
        })

    scored.sort(key=lambda x: (x["score"], x["change_pct"], x["volume_base"]), reverse=True)
    return scored


def _find_best_holding(positions: List[Dict[str, Any]], candidate_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not positions:
        return None

    enriched: List[Dict[str, Any]] = []
    for pos in positions:
        symbol = _extract_position_symbol(pos)
        pnl_pct = _extract_position_pnl_pct(pos)
        c = candidate_map.get(symbol)
        market_score = c["score"] if c else 0.0
        change_pct = c["change_pct"] if c else 0.0
        enriched.append({
            "symbol": symbol,
            "pnl_pct": round(pnl_pct, 4),
            "market_score": round(market_score, 4),
            "change_pct": round(change_pct, 4),
        })

    enriched.sort(key=lambda x: (x["market_score"], x["pnl_pct"], x["change_pct"]), reverse=True)
    return enriched[0] if enriched else None


def _find_worst_holding(positions: List[Dict[str, Any]], candidate_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not positions:
        return None

    enriched: List[Dict[str, Any]] = []
    for pos in positions:
        symbol = _extract_position_symbol(pos)
        pnl_pct = _extract_position_pnl_pct(pos)
        c = candidate_map.get(symbol)
        market_score = c["score"] if c else 0.0
        change_pct = c["change_pct"] if c else 0.0
        enriched.append({
            "symbol": symbol,
            "pnl_pct": round(pnl_pct, 4),
            "market_score": round(market_score, 4),
            "change_pct": round(change_pct, 4),
        })

    enriched.sort(key=lambda x: (x["market_score"], x["pnl_pct"], x["change_pct"]))
    return enriched[0] if enriched else None


def build_basic_decision(
    market_rows: List[Dict[str, Any]],
    positions: Optional[List[Dict[str, Any]]] = None,
    max_positions: int = 3,
    config: Optional[Dict[str, Any]] = None,
) -> DecisionDict:
    """
    규칙 기반 기본 매매 엔진.
    반환 구조는 AI 응답과 유사한 dict 형식을 유지한다.

    Parameters
    ----------
    market_rows : list[dict]
        시장 후보 데이터.
        각 row는 최소한 symbol/market/ticker 중 하나와
        change_pct 계열 또는 거래량 계열 키를 포함하는 것이 좋다.

    positions : list[dict] | None
        현재 보유 포지션 정보.
        각 pos는 symbol/market/ticker 와 pnl_pct 계열 키를 선택적으로 가질 수 있다.

    max_positions : int
        최대 보유 개수 기준. max_positions 미만이면 ENTER 여지,
        꽉 차 있으면 ROTATE/HOLD/STAY 중심으로 판단.

    config : dict | None
        UI 등에서 전달하는 Basic 설정. 일부 키(max_positions, min_trade_value_krw 등)가
        있으면 해당 값이 우선 적용된다.

    Returns
    -------
    dict
        {
          "decision": "STAY|ENTER|HOLD|ROTATE",
          "reason": "...",
          "next_action": "...",
          "rotation": {
            "needed": bool,
            ...
          }
        }
    """
    positions = positions or []

    config = config or {}

    cfg_max_positions = int(_safe_float(config.get("max_positions"), max_positions))
    if cfg_max_positions <= 0:
        cfg_max_positions = max_positions if max_positions > 0 else 3

    min_trade_value_krw = _safe_float(config.get("min_trade_value_krw"), 0.0)
    avoid_bear_market = bool(config.get("avoid_bear_market", True))

    entry_score_threshold = _normalize_ui_score_to_internal(
        config.get("entry_score_threshold"),
        0.64,
    )
    exit_score_threshold = _normalize_ui_score_to_internal(
        config.get("exit_score_threshold"),
        0.45,
    )

    max_concurrent_buys = int(_safe_float(config.get("max_concurrent_buys"), 1))
    if max_concurrent_buys <= 0:
        max_concurrent_buys = 1

    max_positions = cfg_max_positions

    filtered_market_rows: List[Dict[str, Any]] = []
    for row in market_rows or []:
        if not isinstance(row, dict):
            continue
        if min_trade_value_krw > 0:
            trade_value = _extract_trade_value_base(row)
            if trade_value < min_trade_value_krw:
                continue
        filtered_market_rows.append(row)

    regime_info = _regime_from_market(filtered_market_rows)
    regime = regime_info["regime"]

    candidates = _score_candidates(filtered_market_rows)
    candidate_map = {c["symbol"]: c for c in candidates}
    top = candidates[0] if candidates else None

    best_holding = _find_best_holding(positions, candidate_map)
    worst_holding = _find_worst_holding(positions, candidate_map)

    holding_symbols = {_extract_position_symbol(p) for p in positions if _extract_position_symbol(p)}
    free_slots = max(0, max_positions - len(positions))

    # ===== 데이터 부족 =====
    if not candidates:
        return {
            "decision": "STAY",
            "reason": "후보 데이터 부족 또는 거래대금 필터 조건 미충족으로 관망",
            "next_action": "시장 데이터 수집 대기",
            "rotation": {
                "needed": False
            }
        }

    top_symbol = top["symbol"]
    top_score = _safe_float(top["score"])
    top_change = _safe_float(top["change_pct"])

    # 자연스러운 진입 억제를 위한 기준
    enter_threshold = entry_score_threshold
    if regime == "neutral":
        enter_threshold = max(enter_threshold, 0.72)
    elif regime == "bear":
        enter_threshold = max(enter_threshold, 0.86)

    rotate_gap_threshold = 0.18 if regime == "bull" else 0.24 if regime == "neutral" else 0.32

    # ===== 보유 없음 =====
    if not positions:
        if regime == "bear" and avoid_bear_market:
            return {
                "decision": "STAY",
                "reason": "하락장 회피 설정 활성 + 신규 진입 보류",
                "next_action": "관망 유지",
                "rotation": {
                    "needed": False
                }
            }

        if top_score >= enter_threshold and top_change > 0:
            return {
                "decision": "ENTER",
                "reason": f"{'상승 흐름' if regime == 'bull' else '중립장 내 선도 후보'} + 거래 활성도 우수 + 후보 우위",
                "next_action": (
                    f"{top_symbol} 소액 진입"
                    if max_concurrent_buys == 1
                    else f"{top_symbol} 소액 진입 (동시 매수 제한 {max_concurrent_buys})"
                ),
                "rotation": {
                    "needed": False
                }
            }

        return {
            "decision": "STAY",
            "reason": "진입 확신이 부족하여 관망",
            "next_action": "후보 모니터링 지속",
            "rotation": {
                "needed": False
            }
        }

    # ===== 보유 있음 / 최고 후보가 이미 보유 종목인 경우 =====
    if top_symbol in holding_symbols:
        if regime == "bear":
            return {
                "decision": "HOLD",
                "reason": "하락장이나 기존 보유 종목 중 상대 우위 유지",
                "next_action": f"{top_symbol} 방어적 보유 유지",
                "rotation": {
                    "needed": False
                }
            }

        return {
            "decision": "HOLD",
            "reason": "기존 보유 종목이 여전히 상위 후보",
            "next_action": f"{top_symbol} 보유 유지",
            "rotation": {
                "needed": False
            }
        }

    # ===== 자리 여유가 있으면 신규 진입 고려 =====
    if free_slots > 0:
        if regime != "bear" and top_score >= enter_threshold and top_change > 0:
            return {
                "decision": "ENTER",
                "reason": "보유 여유 슬롯 존재 + 신규 후보 우위",
                "next_action": (
                    f"{top_symbol} 분할 진입"
                    if max_concurrent_buys == 1
                    else f"{top_symbol} 분할 진입 (동시 매수 제한 {max_concurrent_buys})"
                ),
                "rotation": {
                    "needed": False
                }
            }

        return {
            "decision": "HOLD",
            "reason": "기존 보유 유지가 우선이며 신규 진입 확신 부족",
            "next_action": "보유 종목 추적 지속",
            "rotation": {
                "needed": False
            }
        }

    # ===== 자리 없음 -> rotation 검토 =====
    if worst_holding:
        worst_symbol = worst_holding["symbol"]
        worst_score = _safe_float(worst_holding["market_score"])
        worst_pnl = _safe_float(worst_holding["pnl_pct"])
        gap = top_score - worst_score

        # 단순 손실만으로 교체하지 않고,
        # '후보 우위 + 기존 약세'가 같이 보여야 rotation
        if (
            regime != "bear"
            and top_change > 0
            and gap >= rotate_gap_threshold
            and (worst_pnl < -0.8 or worst_score < exit_score_threshold)
        ):
            return {
                "decision": "ROTATE",
                "reason": "상위 후보가 기존 약한 보유 종목 대비 명확한 우위",
                "next_action": f"{worst_symbol} 비중 축소 후 {top_symbol} 교체 진입 검토",
                "rotation": {
                    "needed": True,
                    "out_symbol": worst_symbol,
                    "in_symbol": top_symbol,
                    "score_gap": round(gap, 4)
                }
            }

    # ===== 기본값 =====
    if regime == "bear":
        return {
            "decision": "HOLD",
            "reason": "하락장 우세로 보유 방어 및 관망",
            "next_action": "신규 공격 진입 자제",
            "rotation": {
                "needed": False
            }
        }

    best_symbol = best_holding["symbol"] if best_holding else positions[0].get("symbol", "보유종목")
    return {
        "decision": "HOLD",
        "reason": "교체 우위가 충분하지 않아 기존 포지션 유지",
        "next_action": f"{best_symbol} 중심으로 보유 유지",
        "rotation": {
            "needed": False
        }
    }


__all__ = [
    "build_basic_decision",
]
