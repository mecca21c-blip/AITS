# -*- coding: utf-8 -*-
"""
MarketFeed: Upbit 공개 API 기반 시세/거래대금/변동률 폴링 유틸
- 의존: requests (표준 세션), time
- 인증 필요 없음 (잔고/주문은 order_service 담당)
- 스레드 안전: 간단한 Lock과 얕은 캐시(TTL) 적용
- 이벤트 발행(선택): app.core.bus가 있으면 publish 사용

주요 제공 함수
- get_markets(quote="KRW") -> ["KRW-BTC", ...]
- get_tickers(markets=[...]) -> { "KRW-BTC": {...}, ... }
- get_top_markets_by_volume(limit=20, quote="KRW", exclude_black=set(), min_price=10.0)
- get_candle_minute(market, unit=1, count=200) -> list[dict] (최신이 앞)

주의
- 업비트 레이트리밋 고려: 짧은 백오프(backoff) 포함
- 타임아웃: 3s 기본
"""

from __future__ import annotations
import time
import math
import threading
import logging
from typing import Dict, List, Tuple, Optional, Iterable, Set

try:
    import requests
except Exception as e:
    raise RuntimeError("requests 가 필요합니다: pip install requests") from e

# 선택적 이벤트 버스
try:
    import app.core.bus as eventbus  # publish(topic, payload)
except Exception:
    eventbus = None  # 이벤트 발행 생략


_LOG = logging.getLogger(__name__)

_UPBIT_BASE = "https://api.upbit.com"
_DEFAULT_TIMEOUT = 3.0

# 간단 TTL 캐시
class _TTLCache:
    def __init__(self):
        self._d: Dict[str, Tuple[float, object, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str, ttl: float) -> Optional[object]:
        now = time.time()
        with self._lock:
            v = self._d.get(key)
            if not v:
                return None
            ts, data, life = v
            if now - ts > (ttl if ttl is not None else life):
                return None
            return data

    def set(self, key: str, data: object, ttl: float):
        with self._lock:
            self._d[key] = (time.time(), data, ttl)

_CACHE = _TTLCache()
_HTTP = requests.Session()
_HTTP.headers.update({
    "Accept": "application/json",
    "User-Agent": "KMTS/market_feed (requests)"
})

_LOCK = threading.RLock()


def _http_get(path: str, params: dict = None, timeout: float = _DEFAULT_TIMEOUT):
    url = f"{_UPBIT_BASE}{path}"
    try:
        r = _HTTP.get(url, params=params or {}, timeout=timeout)
        if r.status_code == 429:
            # rate limited → 짧은 백오프
            time.sleep(0.25)
            r = _HTTP.get(url, params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"HTTP GET 실패: {path} {params} · {e}")

def get_markets(quote: str = "KRW", ttl: float = 60.0) -> List[str]:
    """
    업비트 지원 마켓 목록. 기본 KRW 마켓만 필터.
    캐시 TTL 기본 60s
    """
    key = f"mkts:{quote}"
    cached = _CACHE.get(key, ttl)
    if cached:
        return cached[:]

    data = _http_get("/v1/market/all", params={"isDetails": "false"})
    mkts = [d["market"] for d in data if isinstance(d, dict) and str(d.get("market", "")).startswith(quote + "-")]
    mkts.sort()
    _CACHE.set(key, mkts, ttl)
    return mkts[:]


def get_markets_with_names(quote: str = "KRW", ttl: float = 60.0) -> List[dict]:
    """
    Watchlist/투자현황용: 한글/영문명을 포함한 마켓 목록 반환.

    반환 예:
      [
        {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        ...
      ]

    - quote: "KRW" / "BTC" 등 마켓 접두사
    - ttl: 캐시 TTL (초)
    """
    key = f"mkts2:{quote}"
    cached = _CACHE.get(key, ttl)
    if cached:
        # 외부에서 수정해도 내부 캐시에 영향 없도록 얕은 복사
        return [dict(row) for row in cached]

    data = _http_get("/v1/market/all", params={"isDetails": "false"})
    rows: List[dict] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        m = str(d.get("market") or "")
        if not m.startswith(quote + "-"):
            continue
        rows.append({
            "market": m,
            "korean_name": str(d.get("korean_name") or ""),
            "english_name": str(d.get("english_name") or ""),
        })

    # 심볼 기준 정렬
    rows.sort(key=lambda r: r["market"])
    _CACHE.set(key, rows, ttl)
    return [dict(row) for row in rows]

def _chunks(seq: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), n):
        yield seq[i: i + n]


def get_tickers(markets: Iterable[str], ttl: float = 1.5) -> Dict[str, dict]:
    """
    다수 심볼의 현재가/24h 거래대금/변동률 가져오기.
    - 업비트는 최대 100개 동시 쿼리 권장 → 50개로 쪼개 호출
    - 반환: { "KRW-BTC": { trade_price, acc_trade_price_24h, signed_change_rate, ... }, ... }
    캐시 TTL 기본 1.5s (초단기)
    """
    mkts = [m for m in markets if m]
    if not mkts:
        return {}

    # 캐시 키는 목록 기반. 너무 길어지지 않게 상위 300심볼까지만 구성
    key = f"ticks:{','.join(mkts[:300])}"
    cached = _CACHE.get(key, ttl)
    if cached:
        return cached.copy()

    out: Dict[str, dict] = {}
    for part in _chunks(mkts, 50):
        q = ",".join(part)
        arr = _http_get("/v1/ticker", params={"markets": q})
        if not isinstance(arr, list):
            continue
        for d in arr:
            try:
                m = d["market"]
                out[m] = {
                    "market": m,
                    "trade_price": float(d.get("trade_price") or 0.0),
                    "acc_trade_price_24h": float(d.get("acc_trade_price_24h") or 0.0),
                    "signed_change_rate": float(d.get("signed_change_rate") or 0.0),
                    "signed_change_price": float(d.get("signed_change_price") or 0.0),
                    "high_price": float(d.get("high_price") or 0.0),
                    "low_price": float(d.get("low_price") or 0.0),
                    "prev_closing_price": float(d.get("prev_closing_price") or 0.0),
                    "acc_trade_volume_24h": float(d.get("acc_trade_volume_24h") or 0.0),
                    "timestamp": int(d.get("timestamp") or 0)
                }
            except Exception:
                # 개별 항목 파싱 실패는 무시
                pass

    _CACHE.set(key, out, ttl)
    return out.copy()


def get_top_markets_by_volume(limit: int = 20,
                              quote: str = "KRW",
                              exclude_black: Optional[Set[str]] = None,
                              min_price: float = 10.0,
                              ttl_markets: float = 60.0,
                              ttl_ticks: float = 1.5) -> List[Tuple[str, dict]]:
    """
    24h 거래대금 상위 마켓 반환
    - limit: 기본 20
    - quote: "KRW" 필터
    - exclude_black: 블랙리스트 제외 (예: {"KRW-XRP"})
    - min_price: 현재가 하한 (너무 저가 토큰 제외용)
    - 반환: [(market, ticker_dict), ...] 거래대금 내림차순
    """
    exclude_black = exclude_black or set()
    mkts = [m for m in get_markets(quote=quote, ttl=ttl_markets) if m not in exclude_black]
    # Python 3.8 미만 호환을 위해 월러스 연산자(:=) 사용 제거
    ticks = get_tickers(mkts, ttl=ttl_ticks)
    rows = []
    for m, d in ticks.items():
        tp = float(d.get("trade_price") or 0.0)
        val24 = float(d.get("acc_trade_price_24h") or 0.0)
        if tp < float(min_price):
            continue
        rows.append((m, d, val24))

    rows.sort(key=lambda x: x[2], reverse=True)
    top = [(m, d) for (m, d, _) in rows[:max(1, int(limit or 20))]]

    # 이벤트 발행(선택)
    if eventbus and hasattr(eventbus, "publish"):
        try:
            eventbus.publish("market.top_updated", {
                "quote": quote,
                "limit": limit,
                "count": len(top),
                "items": [{"market": m, "acc_trade_price_24h": float(d.get("acc_trade_price_24h") or 0.0)} for (m, d) in top]
            })
        except Exception:
            pass
    return top


def get_candle_minute(market: str, unit: int = 1, count: int = 200, ttl: float = 2.5) -> List[dict]:
    """
    분봉 캔들(최신이 앞)
    - unit: 1/3/5/10/15/30/60/240
    - count: 최대 200
    """
    unit = int(unit or 1)
    count = max(1, min(int(count or 200), 200))
    ttl = float(ttl or 2.5)
    key = f"candle:{market}:{unit}:{count}"
    cached = _CACHE.get(key, ttl)
    if cached:
        return cached[:]

    arr = _http_get(f"/v1/candles/minutes/{unit}", params={"market": market, "count": count})
    if not isinstance(arr, list):
        return []
    # 필요한 값만 얕게 축소
    out = []
    for d in arr:
        try:
            out.append({
                "candle_date_time_kst": d.get("candle_date_time_kst"),
                "opening_price": float(d.get("opening_price") or 0.0),
                "high_price": float(d.get("high_price") or 0.0),
                "low_price": float(d.get("low_price") or 0.0),
                "trade_price": float(d.get("trade_price") or 0.0),
                "candle_acc_trade_price": float(d.get("candle_acc_trade_price") or 0.0),
                "candle_acc_trade_volume": float(d.get("candle_acc_trade_volume") or 0.0)
            })
        except Exception:
            pass

    _CACHE.set(key, out, ttl)
    return out[:]


# --------- 고수준 헬퍼 (AI/Runner에서 쓰기 편하도록) ---------

def scan_snapshot_for_ai(quote: str = "KRW",
                         top_n: int = 30,
                         exclude_black: Optional[Set[str]] = None) -> Dict[str, dict]:
    """
    AI 추천용 스냅샷(상위 N개)
    반환: {market: {trade_price, acc_trade_price_24h, signed_change_rate, ...}, ...}
    """
    top = get_top_markets_by_volume(limit=top_n, quote=quote, exclude_black=exclude_black or set())
    return {m: d for (m, d) in top}


def calc_market_breadth(markets_ticks: Dict[str, dict]) -> Tuple[float, float]:
    """
    상승비율(breadth), 평균 등락률(mean_chg) 추정
    """
    if not markets_ticks:
        return 0.0, 0.0
    ups = 0
    s = 0.0
    n = 0
    for m, d in markets_ticks.items():
        r = float(d.get("signed_change_rate") or 0.0)
        if r > 0:
            ups += 1
        s += r
        n += 1
    breadth = (ups / n) if n else 0.0
    mean_chg = (s / n) if n else 0.0
    return float(breadth), float(mean_chg)


def quick_healthcheck() -> dict:
    """
    간단한 헬스체크: KRW 마켓 수/상위 5개 존재 여부
    """
    try:
        mkts = get_markets("KRW")
        top5 = get_top_markets_by_volume(limit=5)
        return {
            "ok": True,
            "markets_krw": len(mkts),
            "top5": [m for (m, _) in top5]
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
