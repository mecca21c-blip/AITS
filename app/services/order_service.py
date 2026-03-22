# ⚠️ 봉인 선언: 역할 변경/이동/삭제/리팩터링 금지
# - 현 단계에서는 안정화 우선
# - 구조 변경은 v-next에서만 수행
# - 이 파일의 역할/위치/구조는 변경하지 말 것

from __future__ import annotations
import time, hmac, hashlib, requests, logging, traceback
import uuid, jwt, json, urllib.parse, os
from urllib.parse import urlencode
from typing import Any, Dict
from decimal import Decimal, ROUND_DOWN

from app.guards.order_guard import can_buy, can_sell  # (다른 곳에서 참조할 수 있어 유지)
from app.db.trades_db import log_trade, last_order_ts_by_market
from app.services.upbit import get_tickers
from app.utils.trade_reason_format import format_trade_reason, format_trade_reason_fallback

def _notify_trade_recorded():
    """매매기록 저장 후 UI(매매기록 탭) 새로고침용 이벤트 발행."""
    try:
        import app.core.bus as eventbus
        eventbus.publish("trades.recorded", {})
        # P0-C: BUS 로그는 bus.py에서 게이트 처리됨 (KMTS_DEBUG_BUS=1일 때만)
    except Exception:
        pass


def _notify_strategy_last_event(message: str):
    """전략 탭 '최근 이벤트' 표시용 이벤트 발행 (ORDER-BLOCK/BUY/SELL)."""
    try:
        import app.core.bus as eventbus
        eventbus.publish("strategy.last_event", {"message": (message or "")[:120]})
    except Exception:
        pass


def _ai_meta_for_log(settings: Any) -> Dict[str, Any]:
    """v5.4 FINAL: 매매기록용 4컬럼. ai_reco.get_last_decision() 단일 진실만 사용, 화이트리스트 밖이면 unknown."""
    out = {}
    try:
        from app.services import ai_reco
        dec = ai_reco.get_last_decision()
        am = (dec.get("ai_mode") or "").strip().lower()
        out["selected_mode"] = am or "local"
        out["selected_engine"] = (dec.get("selected_engine") or "").strip()
        out["actual_engine"] = (dec.get("actual_engine") or "").strip()
        out["reason_code"] = (dec.get("reason") or "").strip()
        if out["reason_code"] not in ("ok", "ai_hold", "inflight", "timeout", "auth_401", "http_429", "ssl", "no_key", "fallback", "unknown", "map_error"):
            out["reason_code"] = "unknown"
        if out["actual_engine"] and out["reason_code"] == "unknown" and dec.get("detail"):
            out["reason_tooltip_extra"] = f"unexpected actual_engine={dec.get('detail', '')[:40]} (sanitized)"
    except Exception:
        out["actual_engine"] = "unknown"
        out["reason_code"] = "unknown"
    return out

# [SELL-BLOCK] reason=dust 로그 10분당 1회 per symbol (스팸 방지)
_SELL_DUST_BLOCK_LAST_LOG: Dict[str, float] = {}
_SELL_DUST_BLOCK_COOLDOWN_SEC = 600.0

# ---- module-level helpers (레거시 호환 alias 포함) ----
def coin_from_market(m: str) -> str:
    """'KRW-BTC' -> 'BTC'"""
    try:
        return (m or "").split("-")[1].strip().upper()
    except Exception:
        return ""

def _coin_from_market(m: str) -> str:  # alias for legacy
    return coin_from_market(m)

def floor8(x: float) -> str:
    """volume는 최대 8자리 소수. 항상 내림 처리."""
    q = (Decimal(str(x))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    s = format(q, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s

def _available_coin(self, coin: str) -> float:  # alias for legacy callers
    return available_coin_via_accounts(self, coin)

def available_coin_via_accounts(svc, coin: str) -> float:
    """
    /v1/accounts 로부터 (balance - locked) 가용수량 계산
    예외/실패 시 0.0
    """
    try:
        rows = svc.fetch_accounts()
    except Exception:
        return 0.0
    for a in rows or []:
        if (a.get("currency") or "").upper() == (coin or "").upper():
            bal = float(a.get("balance") or 0)
            lck = float(a.get("locked")  or 0)
            return max(bal - lck, 0.0)
    return 0.0

log = logging.getLogger(__name__)
API_HOST = "https://api.upbit.com"


def _safe(v, d=None):
    """로그/설정용: 인자 1개면 예외를 안전한 문자열로, 2개면 value-or-default."""
    if d is not None:
        return v if (v is not None and v != "") else d
    try:
        return str(v)
    except Exception:
        try:
            return repr(v)
        except Exception:
            return "<unprintable>"

# OrderService 모듈 import 스탬프
import os
import inspect

# Holding bypass 1회용 플래그
_BYPASS_HOLDING_USED = False

# 잔고 조회 실패 시 fallback: (ts, balance, locked)
_LAST_KRW_CACHE = (0.0, 0.0, 0.0)
_KRW_CACHE_TTL = 120.0  # 2분
# available=0 로그용: (balance, locked, safety_buf)
_LAST_KRW_LOG_INFO = (0.0, 0.0, 1000.0)

# PyInstaller(onedir/onefile)에서는 모듈이 아카이브에서 로드되어
# __file__ 경로가 실제 파일로 존재하지 않을 수 있음(getmtime -> FileNotFoundError 방지).
_file = globals().get("__file__", None)
_mtime = "NA"
try:
    if _file and isinstance(_file, str) and os.path.exists(_file):
        _mtime = os.path.getmtime(_file)
except Exception:
    _mtime = "NA"
log.info(f"[ORDER-SVC-IMPORT] file={_file or 'NA'} mtime={_mtime} pid={os.getpid()}")

class OrderService:
    def __init__(self):
        self._last_order_ts = 0.0
        self._running = False
        self._trading_enabled = True  # P0-BLOCK: Stop 시 False로 설정, 주문 가드에서 사용
        self._panic = False
        self._settings = None  # UI에서 init_prefs 후 주입받음
        self._strategy: Dict[str, Any] = {}  # 최신 strategy 스냅샷(dict)

        self._base = "https://api.upbit.com"
        self.access_key: str | None = None
        self.secret_key: str | None = None
        self._simulate: bool = True
        # 먼지 포지션(추정 체결금액 < 5000원) 쿨다운: market -> until_epoch
        self._dust_cooldown: dict[str, float] = {}
        # === [PATCH-S1] begin: side cooldown fields ===
        self._side_cooldown = {"BUY": {}, "SELL": {}}  # market -> until_epoch
        # === [PATCH-S1] end ===
        # 🔷 [ROTATION] BUY 실패 원인 추적 (rotation 기능용)
        self._last_buy_fail_reason = None
        # SELL 실패 원인 추적 (SL/rotation 상세 로그용)
        self._last_sell_fail_reason = None
        self._last_sell_fail_detail = ""
        self._last_sell_fail_source = "manual"

    # --- [D1] 삽입: 먼지(dust) 판단 + 가용수량 조회 헬퍼 --------------------
    def _is_dust(self, market: str, qty: float) -> bool:
        """
        qty * last_price * (1 - fee - slippage) < 5,000원이면 먼지로 간주
        """
        try:
            price = self.fetch_last_price(market)
            if not price or price <= 0 or qty <= 0:
                return True
            fee = float(getattr(getattr(self._settings, "trade", None), "fee_rate", 0.0005) or 0.0005)
            slp = float(getattr(getattr(self._settings, "trade", None), "slippage", 0.001) or 0.001)
            proceeds = qty * float(price) * (1.0 - fee - slp)
            return proceeds < 5000.0
        except Exception:
            return True

    def _available_qty(self, market: str) -> float:
        """
        보유(balance) - 주문중(locked) 기준의 현재 가용수량
        """
        try:
            cur = market.split("-", 1)[1].upper()
            accts = self.fetch_accounts() or []
            a = next((x for x in accts if (x.get("currency") or "").upper() == cur), None)
            if not a:
                return 0.0
            bal = float(a.get("balance") or 0.0)
            lck = float(a.get("locked") or 0.0)
            return max(0.0, bal - lck)
        except Exception:
            return 0.0

    def _set_last_sell_fail(self, reason: str | None, detail: str = "", source: str = "manual") -> None:
        try:
            self._last_sell_fail_reason = reason
            self._last_sell_fail_detail = str(detail or "")
            self._last_sell_fail_source = str(source or "manual")
        except Exception:
            pass

    def get_last_sell_fail_info(self) -> dict:
        return {
            "reason": getattr(self, "_last_sell_fail_reason", None),
            "detail": getattr(self, "_last_sell_fail_detail", ""),
            "source": getattr(self, "_last_sell_fail_source", "manual"),
        }
    # -----------------------------------------------------------------------

    def _final_guard(self, side: str, market: str, amount: float | None = None, qty: float | None = None, simulate: bool | None = None, panic_mode: bool = False) -> tuple[bool, str, dict]:
        """
        주문 전송 직전 최종 게이트
        반환: (ok: bool, reason: str, detail: dict)
        panic_mode=True 이면 wl_miss 등 guard 통과(전량매도 보장).
        """
        try:
            import time
            detail = {}
            wl = []  # 기본값 설정으로 스코프 안전화
            
            # 1) simulate/live_trade 체크 (SSOT: settings.live_trade)
            try:
                live_trade = bool(getattr(self._settings, "live_trade", False))
            except Exception:
                live_trade = False
            simulate = not live_trade

            detail['simulate'] = bool(simulate)
            detail['live_trade'] = bool(live_trade)

            # 전량매도(PANIC): guard 우회하여 반드시 주문 시도
            if panic_mode:
                log.info("[FINAL-GUARD] bypass=1 reason=panic market=%s", market)
                return True, 'all_ok', detail
            
            # P0-BLOCK: trading_enabled 가드 (Stop 시 주문 차단)
            if not getattr(self, "_trading_enabled", True):
                log.info("[ORDER-FINAL] allow=False simulate=%s reason=trading_disabled", simulate)
                return False, 'trading_disabled', detail
            
            # 2) 화이트/블랙리스트 체크
            wl_ok = bl_ok = True
            try:
                stg = getattr(self._settings, 'strategy', {}) or {}
                if hasattr(stg, 'model_dump'):
                    stg = stg.model_dump()
                
                wl = list(stg.get('whitelist') or [])
                bl = set(s.upper() for s in (stg.get('blacklist') or []))
                
                if wl:
                    wl_set = set(s.strip().upper() for s in wl if s and str(s).strip())
                    wl_ok = market.upper() in wl_set
                if bl:
                    bl_ok = market.upper() not in bl
                    
                detail['wl'] = 'Y' if wl_ok else 'N'
                detail['bl'] = 'Y' if bl_ok else 'N'
            except Exception:
                wl_ok = bl_ok = True
                detail['wl'] = 'Y'
                detail['bl'] = 'Y'
            
            # 3) 쿨다운 체크
            cd_rem = 0.0
            try:
                cd_key = side.upper()
                if cd_key in self._side_cooldown:
                    left = max(0.0, (self._side_cooldown[cd_key].get(market, 0.0) or 0.0) - time.monotonic())
                    cd_rem = left
                detail['cd_rem'] = cd_rem
            except Exception:
                cd_rem = 0.0
                detail['cd_rem'] = 0.0
            
            # 4) 일손실제한 체크 (있으면)
            dll_ok = 'Y'
            try:
                if self._settings and hasattr(self._settings, 'strategy'):
                    stg = self._settings.strategy
                    if hasattr(stg, 'model_dump'):
                        stg = stg.model_dump()
                    dll_limit = float(stg.get('daily_loss_limit_pct', 0) or 0)
                    if dll_limit > 0:
                        # TODO: 실제 일손실 계산 (현재는 항상 OK로 처리)
                        dll_ok = 'Y'
                detail['dll_ok'] = dll_ok
            except Exception:
                dll_ok = 'Y'
                detail['dll_ok'] = 'Y'
            
            # 5) 최소 주문금액 체크
            min_ok = 'Y'
            min_amount = 5000.0  # 업비트 기준
            try:
                if side.upper() == 'BUY' and amount is not None:
                    min_ok = 'Y' if amount >= min_amount else 'N'
                elif side.upper() == 'SELL' and qty is not None:
                    # SELL은 가치 체크 (가격 * 수량)
                    price = self.fetch_last_price(market)
                    if price and price > 0:
                        value = qty * price
                        min_ok = 'Y' if value >= min_amount else 'N'
                detail['min_ok'] = min_ok
            except Exception:
                min_ok = 'Y'
                detail['min_ok'] = 'Y'
            
            # 6) 최종 판정 (우선순위: BL > WL-miss > simulate block > cooldown > dll > min_amount > other)
            if not bl_ok:
                return False, 'blacklist', detail
            if wl and not wl_ok:
                return False, 'wl_miss', detail
            if simulate:
                return False, 'simulate', detail
            if cd_rem > 0:
                return False, 'cooldown', detail
            if dll_ok == 'N':
                return False, 'daily_loss_limit', detail
            if min_ok == 'N':
                return False, 'min_amount', detail
            
            return True, 'all_ok', detail
            
        except Exception as e:
            # 예외 시 안전 차단
            return False, f'exception_{str(e)[:20]}', {'error': str(e)[:50]}

    # -----------------------------------------------------------------------

    # [추가] 실행기 기본기: RUNNING 플래그와 로그
    def run(self):
        import logging
        self._running = True
        logging.getLogger(__name__).info("OrderService RUNNING (loop not implemented)")

    def stop(self):
        import logging
        self._running = False
        logging.getLogger(__name__).info("OrderService STOPPED")

    def set_trading_enabled(self, enabled: bool) -> None:
        """
        P0-BLOCK: 거래 활성화/비활성화 설정
        enabled=False 시 주문 가드에서 allow=False 처리
        """
        try:
            self._trading_enabled = bool(enabled)
            self._running = bool(enabled)
            log.info("[TRADE-EN] enabled=%s", self._trading_enabled)
        except Exception:
            try:
                log.info("[TRADE-EN] enabled=%s", enabled)
            except Exception:
                pass

    def is_running(self) -> bool:
        return bool(getattr(self, "_running", False))
    
    # [추가] 내부 로그 헬퍼(누락 시 대비)
    def _log_info(self, msg: str):
        import logging
        logging.getLogger(__name__).info(msg)

    # ----- settings injection -----
    def set_settings(self, settings):
        """
        런타임용 전략 스냅샷을 보관하고, 공격성 프리셋을 파생 파라미터에 반영한다.
        """
        from copy import deepcopy
        import inspect

        # 런타임 시그니처 덤프 (1회만)
        if not hasattr(self, '_rt_dumped'):
            self._rt_dumped = True
            svc_id = id(self)
            self_type = type(self).__name__
            module_file = __file__
            func_file = self.buy_market.__code__.co_filename
            func_line = self.buy_market.__code__.co_firstlineno
            sig = str(inspect.signature(self.buy_market))
            log.info(f"[BUYMARK-RT-BOOT] svc_id={svc_id} self_type={self_type} module_file={module_file} func_file={func_file} func_line={func_line} sig={sig}")

        # ✅ SSOT: ALWAYS use the settings passed by caller (runner/UI)
        self._settings = settings
        
        # [추가] Upbit 키/실거래 플래그 주입
        try:
            # ✅ 키 읽기 직전에는 무조건 self._settings 사용
            settings = self._settings
            
            # 우선순위: upbit.access_key/secret_key (공통설정 저장 방식)
            up = getattr(settings, "upbit", {}) or {}
            if hasattr(up, "model_dump"):
                up = up.model_dump()
            
            access_key = up.get("access_key")
            secret_key = up.get("secret_key")
            
            # 폴백: upbit_access_key/upbit_secret_key (기존 방식)
            if not access_key:
                access_key = getattr(settings, "upbit_access_key", None)
            if not secret_key:
                secret_key = getattr(settings, "upbit_secret_key", None)
            
            # ✅ 키 읽기 경로 로그 + SSOT 분기 진단
            settings_id = id(settings)
            order_service_id = id(self)
            self._log_info(f"[ORDER] upbit key read: primary=settings.upbit.access_key, fallback=settings.upbit_access_key")
            self._log_info(f"[ORDER] access_key found={bool(access_key)} secret_key_found={bool(secret_key)} settings_id={settings_id} order_service_id={order_service_id}")
            
            self.access_key = (access_key or "").strip()
            self.secret_key = (secret_key or "").strip()
            
            # ✅ 키 미설정 판단 조건 로그
            access_empty = not self.access_key or len(self.access_key) == 0
            secret_empty = not self.secret_key or len(self.secret_key) == 0
            log.info(f"[ORDER] key status: access_key_empty={access_empty} secret_key_empty={secret_empty} simulate={self._simulate}")
        except Exception:
            # 안전 폴백(키 미설정 시 None 유지)
            self.access_key = self.access_key or None
            self.secret_key = self.secret_key or None

        # 실거래 여부(시뮬 모드 반전) - 루트에서 읽기
        try:
            settings = self._settings  # ✅ SSOT: 항상 self._settings 사용
            live = bool(getattr(settings, "live_trade", False))
            self._simulate = (not live)
            # ✅ live_trade 로그
            log.info(f"[ORDER] live_trade={live} → _simulate={self._simulate}")
        except Exception:
            pass
        
        # strategy 스냅샷 보관
        stg = getattr(settings, "strategy", {}) or {}
        # dict 보장
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()
        self._strategy = deepcopy(stg)

        def stg_get(k, d=None):
            try:
                return self._strategy.get(k, d)
            except Exception:
                return d
        self.stg = stg_get  # 외부에서 self.stg("key", default)로 안전 접근

        # 전략 모드 우선순위: avoid면 신규 진입 차단 플래그
        self._avoid_entries = (self.stg("strategy_mode", "ai") == "avoid")

        # 공격성 프리셋(수익 극대화/리스크 균형)
        lv = int(self.stg("aggressiveness_level", 5))

        # clamp 유틸
        def _clamp(v, lo, hi): return max(lo, min(hi, v))

        def _normalize_pct_with_log(key: str, v: object, default: float, source: str) -> float:
            """percent SSOT 정규화.
            - 모든 값을 percent로 취급, ratio 변환 완전 제거
            - invalid/None: default로 회복 + [UNIT-FIX] 로그
            """
            raw = v
            try:
                x = float(raw)
            except Exception:
                log.warning("[UNIT-FIX] key=%s raw=%r source=%s invalid -> default %.3f%%", key, raw, source, float(default))
                return float(default)
            # ✅ P0-UNIT: 모든 값을 percent로 취급, ratio 변환 제거
            log.info("[UNIT-FIX] key=%s raw=%r source=%s treated_as_percent -> %.3f%%", key, raw, source, float(x))
            return float(x)

        # aggressiveness 프리셋 (percent SSOT)
        pos = _clamp(0.5 + 0.5 * (lv - 1), 0.0, 5.0)
        rr = 1.2 + 0.2 * (lv - 1)
        dll = _clamp(1.0 + 0.5 * (lv - 1), 0.0, 20.0)
        cd = max(10, 60 - 5 * (lv - 1))

        # ※ setdefault → 강제 주입으로 변경 (aggressiveness_level 보장)
        manual = bool(self._strategy.get("_manual_tuning", False))
        if not manual:
            # ✅ 사용자 커밋값 우선: 값이 없거나(키 없음/None/<=0)일 때만 프리셋으로 채움
            try:
                cur_pos = self._strategy.get("pos_size_pct", None)
                cur_pos_f = float(cur_pos) if cur_pos not in (None, "") else None
            except Exception:
                cur_pos_f = None
            if (cur_pos_f is None) or (cur_pos_f <= 0):
                self._strategy["pos_size_pct"] = float(pos)

            try:
                cur_dll = self._strategy.get("daily_loss_limit_pct", None)
                cur_dll_f = float(cur_dll) if cur_dll not in (None, "") else None
            except Exception:
                cur_dll_f = None
            if (cur_dll_f is None) or (cur_dll_f <= 0):
                self._strategy["daily_loss_limit_pct"] = float(dll)

            if self._strategy.get("rr_ratio") in (None, ""):
                self._strategy["rr_ratio"] = rr
            if self._strategy.get("cooldown_on", True) and (self._strategy.get("cooldown_sec") in (None, "")):
                self._strategy["cooldown_sec"] = cd

        # ✅ SSOT 강제: self._strategy에는 percent만 남긴다(혼재는 여기서 1회 보정)
        try:
            self._strategy["pos_size_pct"] = _normalize_pct_with_log(
                "pos_size_pct",
                self._strategy.get("pos_size_pct", None),
                default=2.5,
                source="OrderService.set_settings",
            )
            self._strategy["daily_loss_limit_pct"] = _normalize_pct_with_log(
                "daily_loss_limit_pct",
                self._strategy.get("daily_loss_limit_pct", None),
                default=3.0,
                source="OrderService.set_settings",
            )
        except Exception:
            pass

        # 핵심 파라미터 1줄 로그
        try:
            _pos_pct = float(self._strategy.get('pos_size_pct', 0.0) or 0.0)
        except Exception:
            _pos_pct = 0.0
        try:
            _dll_pct = float(self._strategy.get('daily_loss_limit_pct', 0.0) or 0.0)
        except Exception:
            _dll_pct = 0.0
        self._log_info(f"[전략 주입] mode={self._strategy.get('strategy_mode')} lv={lv} "
                    f"pos={_pos_pct:.3f}% rr={self._strategy.get('rr_ratio')} "
                    f"cd={self._strategy.get('cooldown_sec')}s dll={_dll_pct:.3f}%")

        # ✅ 로그 증거 안정화(한글 인코딩 깨짐 대비): ASCII 보조 로그
        self._log_info(f"[STRAT-INJECT] mode={self._strategy.get('strategy_mode')} lv={lv} "
                    f"pos={_pos_pct:.3f}% rr={self._strategy.get('rr_ratio')} "
                    f"cd={self._strategy.get('cooldown_sec')}s dll={_dll_pct:.3f}%")
        return True

    def stg(self, key: str, default=None):
        """strategy dict에서 안전하게 꺼내기"""
        try:
            return (self._strategy or {}).get(key, default)
        except Exception:
            return default

    # ----- JWT / 요청 공통 -----
    def _jwt_encode(self, payload: dict) -> str:
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _auth_headers(self, params: dict) -> dict:
        """
        Upbit JWT: query_hash = SHA512(urlencode(sorted(params))); query_hash_alg='SHA512'
        """
        if not (self.access_key and self.secret_key):
            raise RuntimeError("Upbit API 키가 설정되지 않았습니다. 설정 탭에서 저장 후 다시 시도하세요.")

        items = sorted((k, str(v)) for k, v in (params or {}).items())
        query_string = urllib.parse.urlencode(items)

        m = hashlib.sha512(); m.update(query_string.encode("utf-8"))
        qh = m.hexdigest()

        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
            "query_hash": qh,
            "query_hash_alg": "SHA512",
        }
        token = self._jwt_encode(payload)
        return {"Authorization": f"Bearer {token}"}

    def _post_signed(self, url: str, params: dict, timeout: int = 10):
        """
        Upbit는 쿼리 파라미터 기준으로 JWT를 검증한다. 반드시 params= 로 보내야 함.
        """
        headers = self._auth_headers(params)
        return requests.post(url, params=params, headers=headers, timeout=timeout)

    def fetch_accounts(self):
        """
        Upbit /v1/accounts 호출. (JWT 필요)
        """
        h = self._auth_headers({})
        from app.services.upbit import get_accounts
        return get_accounts(h)

    def fetch_last_price(self, market: str):
        """단일 마켓 현재가. price_service.get_current_price 사용. 실패 시 None, 로그 [PRICE-FETCH]."""
        try:
            from app.services.price_service import get_current_price
            px = get_current_price(market, force=False)
            if px is not None and float(px) > 0:
                return float(px)
            logging.debug("[PRICE-FETCH] ok=0 market=%s err=no_price", market)
            return None
        except Exception as e:
            logging.warning("[PRICE-FETCH] ok=0 market=%s err=%s", market, str(e)[:80])
            return None

    def _compute_invested_krw(self) -> float:
        """보유 포지션 평가금액 합계(KRW 제외 코인만). 현재가*수량 기준. 리스크 cap 비교용."""
        try:
            accts = self.fetch_accounts() or []
            total = 0.0
            for a in accts:
                cur = (a.get("currency") or "").strip().upper()
                if not cur or cur == "KRW":
                    continue
                bal = float(a.get("balance") or 0.0)
                if bal <= 0:
                    continue
                market = f"KRW-{cur}"
                px = self.fetch_last_price(market)
                if px is not None and px > 0:
                    total += bal * px
            return total
        except Exception:
            return 0.0

    # ----- 내부 유틸 -----
    def _respect_rate_limit(self, resp: requests.Response):
        """
        Remaining-Req 헤더를 파싱하여 여유가 적으면 짧게 슬립.
        예: 'group=default; min=1799; sec=29'
        - sec(초 단위 잔여 요청 수)가 1 이하이면 0.2~0.5초 대기
        """
        try:
            rem = resp.headers.get("Remaining-Req", "")
            parts = dict(x.split("=") for x in rem.replace(" ", "").split(";") if "=" in x)
            sec_left = int(parts.get("sec", "5"))
            if sec_left <= 1:
                time.sleep(0.35)
        except Exception:
            pass

    def _request_with_retry(self, method, url, *, params=None, json=None, headers=None, timeout=10, max_retries=2):
        import random
        last = None
        for i in range(max_retries + 1):
            try:
                r = requests.request(method, url, params=params, json=json, headers=headers, timeout=timeout)
                self._respect_rate_limit(r)
                if r.status_code < 500:
                    return r
                last = r
            except Exception:
                last = None
            time.sleep(0.4 * (2 ** i) + random.random() * 0.2)
        if last is not None:
            return last
        raise RuntimeError("request failed after retries")

    def _simulate(self, side: str, market: str, krw_amt_or_vol: float):
        log.info("[SIMULATE] %s %s %s", side, market, krw_amt_or_vol)

    # ----- guards -----
    def _can_order(self) -> bool:
        if self._panic:
            log.warning("PANIC STOP 상태 — 주문 차단")
            return False
        now = time.time()
        if now - self._last_order_ts < 1.0:  # 최소 1초 간격
            log.warning("주문 쿨다운 중")
            return False
        self._last_order_ts = now
        return True

    # === [PATCH O-1] begin: trade cfg + available KRW helpers ===
    def _get_trade_cfg(self):
        trade = getattr(self._settings, "trade", None)
        fee = float(getattr(trade, "fee_rate", 0.0005) or 0.0005)
        slp = float(getattr(trade, "slippage", 0.001) or 0.001)
        buf = float(getattr(trade, "safety_buffer_krw", 1000.0) or 1000.0)
        return fee, slp, buf

    def _compute_available_krw(self) -> float:
        """
        available = KRW balance - KRW locked - 내부 예약금 - safety_buffer
        조회 실패/None/예외/KRW 미포함 시: 마지막 정상잔고 캐시 사용 (TTL 2분)
        """
        global _LAST_KRW_CACHE, _LAST_KRW_LOG_INFO
        try:
            rows = self.fetch_accounts()
        except Exception:
            rows = None
        krw_balance, krw_locked = 0.0, 0.0
        krw_found = False
        for a in rows or []:
            if (a.get("currency") or "").upper() == "KRW":
                krw_balance = float(a.get("balance") or 0.0)
                krw_locked  = float(a.get("locked")  or 0.0)
                _LAST_KRW_CACHE = (time.time(), krw_balance, krw_locked)
                krw_found = True
                break
        if not krw_found:
            # 조회 실패 또는 빈 응답 또는 KRW 미포함: 캐시 fallback
            cached_ts, cached_bal, cached_lck = _LAST_KRW_CACHE
            if cached_ts > 0 and (time.time() - cached_ts) < _KRW_CACHE_TTL:
                krw_balance, krw_locked = cached_bal, cached_lck
        reserved = float(getattr(self, "_reserved_krw", 0.0) or 0.0)
        _, _, safety_buf = self._get_trade_cfg()
        globals()["_LAST_KRW_LOG_INFO"] = (krw_balance, krw_locked, safety_buf)
        return max(0.0, krw_balance - krw_locked - reserved - safety_buf)
    # === [PATCH O-1] end ===

    # ----- 가격 지정 매수 (원문 보존 + 정리) -----
    # (runner나 다른 모듈에서 호출 중일 수 있어 API 유지)
    def buy_price(self, market: str, krw_amount: float, simulate=True, reason: str = "", strategy_id: str = "default", strategy_info: str | None = None) -> bool:
        """
        지정가 매수처럼 금액 지정 입력을 받지만, Upbit price-주문(원화) 모델에 맞춰
        한도 내 5,000원 배수로만 주문.
        """
        if not self._can_order():
            return False
        if self._settings is None:
            raise RuntimeError("설정 미주입: set_settings 먼저 호출")

        # SSOT: 실거래 여부는 settings.live_trade로 확정하고, runner의 simulate 인자 혼선을 무시
        try:
            _live_trade = bool(getattr(self._settings, "live_trade", False))
        except Exception:
            _live_trade = False
        simulate = not _live_trade

        # stg 변수 정의 - dict로 통일
        stg = getattr(self._settings, "strategy", {}) or {}
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()

        # 계정/총자산
        try:
            rows = self.fetch_accounts()
        except Exception:
            rows = []
        krw_balance, krw_locked, coins = 0.0, 0.0, []
        for a in rows or []:
            cur = (a.get("currency") or "").upper()
            if cur == "KRW":
                krw_balance = float(a.get("balance") or 0)
                krw_locked  = float(a.get("locked")  or 0)
            else:
                coins.append((cur, float(a.get("balance") or 0.0), float(a.get("locked") or 0.0), float(a.get("avg_buy_price") or 0.0)))

        total_asset = krw_balance
        try:
            prices = {}
            mkts = [f"KRW-{c}" for c,_,_,_ in coins]
            if mkts:
                for i in range(0, len(mkts), 50):
                    for t in (get_tickers(mkts[i:i+50]) or []):
                        prices[t.get("market")] = float(t.get("trade_price") or 0.0)
            for c, bal, lck, avg in coins:
                px = prices.get(f"KRW-{c}", 0.0) or avg
                total_asset += (bal + lck) * px
        except Exception:
            for c, bal, lck, avg in coins:
                total_asset += (bal + lck) * avg

        available_krw = self._compute_available_krw()

        try:
            max_total = float(getattr(self._settings, "max_total_krw", 50_000))
        except Exception:
            max_total = 50_000.0
        orderable_krw = available_krw
        remaining_cap = max(0.0, float(max_total) - (float(total_asset) - float(orderable_krw)))
        if remaining_cap == float("inf"):
            remaining_cap = orderable_krw

        # 포지션 비중 적용: available_krw * position_pct/100
        pos_pct = float(_safe(stg.get("pos_size_pct", 2.5), 2.5))  # percent 단위
        position_limit = available_krw * pos_pct / 100.0

        # 요청금액: SSOT 그대로 사용. 다운스케일 금지.
        try:
            req_amt = int(float(krw_amount or 0))
        except (TypeError, ValueError):
            req_amt = 0
        MIN_ORDER_KRW = 5000
        
        # hard_cap 계산: pos_size_pct가 최소 주문금액을 막지 않게 보호
        hard_cap_candidate = min(available_krw, remaining_cap, position_limit) if remaining_cap != float("inf") else min(available_krw, position_limit)
        hard_cap_bypass_reason = None
        
        if hard_cap_candidate < MIN_ORDER_KRW:
            if req_amt >= MIN_ORDER_KRW:
                # 테스트/소액 계좌 보호: pos_size_pct 우회, 최소 주문금액 보호
                hard_cap = min(available_krw, req_amt)
                hard_cap_bypass_reason = "pos_size_pct_bypassed_for_min_order"
                logging.info(
                    "[BUY-CAP-ADJUST] reason=%s symbol=%s available=%.0f position_limit=%.0f order_amount=%d final_cap=%.0f",
                    hard_cap_bypass_reason, market, available_krw, position_limit, req_amt, hard_cap
                )
            else:
                # order_amount_krw 자체가 최소 주문금액 미만이면 기존대로 BLOCK
                hard_cap = hard_cap_candidate
        else:
            hard_cap = hard_cap_candidate
        
        # 정책 2: 다운스케일 옵션 확인
        allow_downscale = False
        try:
            stg = getattr(self._settings, "strategy", {}) or {}
            if hasattr(stg, "model_dump"):
                stg = stg.model_dump()
            allow_downscale = bool(stg.get("allow_downscale_order_amount", False))
        except Exception:
            allow_downscale = False
        
        if req_amt < MIN_ORDER_KRW:
            _notify_strategy_last_event(f"ORDER-BLOCK reason=req_under_min symbol={market}")
            logging.warning(
                "[ORDER-BLOCK] reason=req_under_min symbol=%s amount=%s simulate=%s live_trade=%s",
                market, req_amt, simulate, not getattr(self._settings, "live_trade", False)
            )
            return False
        if hard_cap < MIN_ORDER_KRW and req_amt < MIN_ORDER_KRW:
            # hard_cap < 5000이고 req_amt도 < 5000인 경우만 BLOCK
            _notify_strategy_last_event(f"ORDER-BLOCK reason=cap_under_min symbol={market} hard_cap={hard_cap:.0f}")
            logging.warning(
                "[ORDER-BLOCK] reason=cap_under_min symbol=%s req=%s hard_cap=%.0f simulate=%s live_trade=%s",
                market, req_amt, hard_cap, simulate, not getattr(self._settings, "live_trade", False)
            )
            return False
        
        # req > hard_cap: 자동 축소는 allow_downscale_order_amount ON일 때만
        final_req = req_amt
        if req_amt > hard_cap:
            if allow_downscale and hard_cap >= MIN_ORDER_KRW:
                final_req = int(hard_cap)
                logging.info(
                    "[CAP-DOWN] req=%s hard_cap=%s final=%s applied=1 reason=cap_downscale",
                    req_amt, hard_cap, final_req,
                )
                logging.info(
                    "[BUY-DOWNSCALE] enabled=1 req=%s available=%s final=%s reason=req_exceeds_cap_downscale",
                    int(req_amt), int(hard_cap), final_req,
                )
            else:
                logging.info(
                    "[CAP-DOWN] req=%s hard_cap=%s final=%s applied=0 reason=req_exceeds_cap_or_downscale_off",
                    req_amt, hard_cap, req_amt,
                )
                logging.info(
                    "[BUY-DOWNSCALE] enabled=%s req=%s available=%s final=%s reason=req_exceeds_cap_block",
                    "1" if allow_downscale else "0",
                    int(req_amt),
                    int(hard_cap),
                    int(req_amt),
                )
                _notify_strategy_last_event(
                    f"ORDER-BLOCK reason=req_exceeds_cap symbol={market} req={req_amt} hard_cap={hard_cap:.0f}"
                )
                logging.warning(
                    "[ORDER-BLOCK] reason=req_exceeds_cap symbol=%s req=%s hard_cap=%.0f simulate=%s live_trade=%s downscale=0",
                    market, req_amt, hard_cap, simulate, not getattr(self._settings, "live_trade", False),
                )
                return False

        # final_req 사용 (다운스케일된 경우 반영)
        req_amt = final_req

        # 현재가(로그용)
        price = None
        try:
            t = get_tickers([market])[0]
            price = float(t.get("trade_price") or 0)
        except Exception:
            pass

        # 주문 함수 진입 로그 (항상 출력)
        logging.info(
            "[BUY-READY] %s amt=%s entry=buy_price simulate=%s live_trade=%s",
            market, krw_amount, simulate, _live_trade
        )

        # 시뮬 (SSOT simulate)
        if simulate:
            # FINAL-GUARD 체크 (시뮬에서도 로그를 위해 호출)
            ok, reason, detail = self._final_guard('BUY', market, amount=req_amt, simulate=simulate)
            vol = (float(req_amt) / price) if (price and price > 0) else 0.0
            vol_str = (Decimal(str(vol))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            rsn_short, rsn_tip = format_trade_reason_fallback(reason or "simulate")
            ai_meta = _ai_meta_for_log(self._settings)
            extra = ai_meta.pop("reason_tooltip_extra", "")
            if extra:
                rsn_tip = (rsn_tip or "") + "\n" + extra
            log_trade(time.time(), market, "BUY", price, float(vol_str), float(req_amt), reason or "simulate", strategy_id=strategy_id, strategy_info=(strategy_info or reason), reason_short=rsn_short, reason_tooltip=rsn_tip, **ai_meta)
            _notify_trade_recorded()
            _notify_strategy_last_event(f"BUY(SIM) {market} {req_amt}원")
            logging.info("BUY(SIM) %s %s원 -> vol~%s (reason=%s)", market, req_amt, vol_str, reason)
            return True

        # FINAL-GUARD 체크 (SSOT simulate 전달)
        ok, reason, detail = self._final_guard('BUY', market, amount=req_amt, simulate=simulate)

        logging.info(
            "[BUY-READY] symbol=%s simulate=%s live_trade=%s amt=%d avail=%.0f cap=%.0f ak_len=%d",
            market,
            simulate,
            not simulate,
            req_amt,
            available_krw,
            remaining_cap if remaining_cap != float('inf') else -1,
            len(self._side_cooldown.get("BUY", {}))
        )

        url = f"{API_HOST}/v1/orders"
        body = {"market": market, "side": "bid", "ord_type": "price", "price": str(req_amt)}
        params_dict = dict(sorted(body.items()))
        headers = self._auth_headers(params_dict)
        r = self._request_with_retry("POST", url, params=params_dict, headers=headers, timeout=10, max_retries=2)
        logging.info("BUY %s %s -> %s", market, req_amt, r.text)

        ok, uuid_ = False, None
        try:
            js = r.json()
            ok = (r.status_code // 100 == 2) and bool(js.get("uuid"))
            uuid_ = js.get("uuid")
        except Exception:
            ok = False
        if not ok:
            logging.warning("BUY 실패: 응답=%s", getattr(r, "text", ""))
            return False

        try:
            cd = float(getattr(self._settings, "buy_cooldown_sec", None) or self.stg("buy_cooldown_sec", 60))
            self._side_cooldown["BUY"][market] = time.monotonic() + cd
        except Exception:
            pass

        vol_est = (float(req_amt) / price) if (price and price > 0) else 0.0
        rsn_short, rsn_tip = format_trade_reason_fallback(reason or f"LIVE uuid={uuid_}")
        ai_meta = _ai_meta_for_log(self._settings)
        extra = ai_meta.pop("reason_tooltip_extra", "")
        if extra:
            rsn_tip = (rsn_tip or "") + "\n" + extra
        log_trade(time.time(), market, "BUY", price, float(vol_est), float(req_amt), reason or f"LIVE uuid={uuid_}", strategy_id=strategy_id, strategy_info=(strategy_info or reason), reason_short=rsn_short, reason_tooltip=rsn_tip, **ai_meta)
        _notify_trade_recorded()
        _notify_strategy_last_event(f"BUY {market} {req_amt}원 success uuid={uuid_}")
        return True

    # ----- 시장가 매도(볼륨 지정) -----
    def sell_market(self, market: str, qty: float, simulate=True, reason: str = "", strategy_id: str = "default", strategy_info: str | None = None, price_hint: float | None = None, meta: Dict[str, Any] | None = None) -> tuple[bool, str | None]:
        """
        시장가 매도(수량 지정). 반환: (ok, block_reason). ok=False일 때 block_reason으로 차단 사유 전달.
        - price_hint: runner가 넘긴 현재가; fetch_last_price 실패 시 이 값으로 est_krw/가드 판단
        - 청산가치 5,000 미만(먼지)은 스킵
        - locked 제외한 가용수량만 매도
        """
        # SSOT: 실거래 여부는 settings.live_trade로 확정
        try:
            _live_trade = bool(getattr(self._settings, "live_trade", False))
        except Exception:
            _live_trade = False
        simulate = not _live_trade
        meta_keys = list(meta.keys()) if (meta and isinstance(meta, dict)) else []
        sell_source = str((meta or {}).get("source") or "manual") if isinstance(meta, dict) else "manual"
        panic_mode = bool(meta and isinstance(meta, dict) and meta.get("panic") is True)
        panic_mode = panic_mode or ("PANIC" in (reason or "").upper() or "전량" in str(reason or ""))
        panic_mode = panic_mode or bool(getattr(self, "_panic", False))
        logging.info("[SELL-ENTRY] market=%s qty=%s reason=%s meta_keys=%s panic=%d simulate=%s price_hint=%s", market, qty, (reason or "")[:40], meta_keys, 1 if panic_mode else 0, simulate, price_hint)

        # stg 변수 정의 - dict로 통일
        stg = getattr(self._settings, "strategy", {}) or {}
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()
        
        logging.info("[SELL-READY] %s qty=%s entry=sell_market simulate=%s price_hint=%s", market, qty, simulate, price_hint)

        # 최신 가격: fetch 실패 시 runner가 넘긴 price_hint 사용 (SELL-BLOCK price_or_qty_invalid 방지). 실패 시 1회 재시도.
        price = None
        try:
            price = self.fetch_last_price(market)
        except Exception:
            price = None
        if not price or price <= 0:
            price = float(price_hint) if price_hint is not None and float(price_hint) > 0 else None
        if not price or price <= 0:
            try:
                price = self.fetch_last_price(market)
            except Exception:
                price = None
        if not price or price <= 0:
            price = float(price_hint) if price_hint is not None and float(price_hint) > 0 else None

        price_for_log = float(price) if (price is not None and float(price) > 0) else 0.0
        est_krw = (float(qty) * price_for_log) if (price_for_log > 0 and qty) else 0.0

        # 가격/수량 기본 체크 (qty<=0 시 reason=qty_unavailable, balance/locked/avail 로그)
        if not qty or qty <= 0:
            block_reason = "qty_unavailable"
            balance, locked, avail = 0.0, 0.0, 0.0
            try:
                cur = market.split("-", 1)[1].upper()
                for a in (self.fetch_accounts() or []):
                    if (a.get("currency") or "").upper() == cur:
                        balance = float(a.get("balance") or 0.0)
                        locked = float(a.get("locked") or 0.0)
                        avail = max(0.0, balance - locked)
                        break
            except Exception:
                pass
            _notify_strategy_last_event(f"SELL-BLOCK reason={block_reason} symbol={market}")
            logging.warning(
                "[SELL-BLOCK] reason=%s market=%s qty=%s balance=%s locked=%s avail=%s",
                block_reason, market, qty, balance, locked, avail
            )
            self._set_last_sell_fail(block_reason, f"balance={balance} locked={locked} avail={avail}", sell_source)
            return (False, block_reason)
        if not price or price <= 0:
            if panic_mode:
                logging.info("[PANIC-SELL] price_missing bypass=1 symbol=%s qty=%s price_hint=%s", market, qty, price_hint)
            else:
                block_reason = "price_fetch_failed"
                detail = f"price={price} qty={qty} price_hint={price_hint}"
                _notify_strategy_last_event(f"SELL-BLOCK reason={block_reason} symbol={market}")
                logging.warning(
                    "[SELL-BLOCK] reason=%s symbol=%s qty=%s est_krw=%.0f live_trade=%s simulate=%s detail=%s",
                    block_reason, market, qty, est_krw, not simulate, simulate, detail
                )
                self._set_last_sell_fail(block_reason, detail, sell_source)
                return (False, block_reason)

        # 먼지(dust) 가드 (panic_mode면 최소주문·dust 체크 우회)
        if not panic_mode and self._is_dust(market, float(qty)):
            now_ts = time.time()
            last = _SELL_DUST_BLOCK_LAST_LOG.get(market, 0.0)
            if (now_ts - last) >= _SELL_DUST_BLOCK_COOLDOWN_SEC:
                _SELL_DUST_BLOCK_LAST_LOG[market] = now_ts
                _notify_strategy_last_event(f"SELL-BLOCK reason=dust symbol={market} est_krw={est_krw:.0f}")
                logging.warning(
                    "[SELL-BLOCK] reason=dust symbol=%s qty=%s est_krw=%.0f live_trade=%s simulate=%s detail=est_krw<5000 (10min throttle)",
                    market, qty, est_krw, not simulate, simulate
                )
            self._set_last_sell_fail("dust", f"est_krw={est_krw:.0f}<5000", sell_source)
            return (False, "dust")

        # 가용 수량 확인(locked 제외)
        avail = self._available_qty(market)
        if avail <= 0:
            detail = f"available_qty={avail} requested_qty={qty}"
            _notify_strategy_last_event(f"SELL-BLOCK reason=available_qty_zero symbol={market}")
            logging.warning(
                "[SELL-BLOCK] reason=available_qty_zero symbol=%s qty=%s est_krw=%.0f live_trade=%s simulate=%s detail=%s",
                market, qty, est_krw, not simulate, simulate, detail
            )
            self._set_last_sell_fail("available_qty_zero", detail, sell_source)
            return (False, "available_qty_zero")

        # 과다 주문 보호
        qty = float(min(float(qty), avail))

        # 시뮬 (SSOT simulate)
        if simulate:
            # FINAL-GUARD 체크 (시뮬에서도 로그를 위해 호출)
            ok, reason, detail = self._final_guard('SELL', market, qty=qty, simulate=True, panic_mode=panic_mode)
            qty_str = f"qty={qty}" if 'qty' in detail else ""
            log_fields = f"side=SELL symbol={market} live_trade={detail.get('live_trade', False)} simulate={detail.get('simulate', True)} {qty_str} wl={detail.get('wl', 'N')} bl={detail.get('bl', 'N')} cd_rem={detail.get('cd_rem', 0):.0f} dll_ok={detail.get('dll_ok', 'Y')} min_ok={detail.get('min_ok', 'Y')}"
            
            if ok:
                logging.info(f"[FINAL-GUARD] PASS {log_fields}")
            else:
                _notify_strategy_last_event(f"SELL-BLOCK reason=guard_fail symbol={market} detail={reason}")
                logging.info(
                    "[SELL-BLOCK] reason=guard_fail symbol=%s qty=%s est_krw=%.0f live_trade=%s simulate=%s detail=%s",
                    market, qty, qty * price_for_log, False, True, reason
                )
                self._set_last_sell_fail("guard_fail", str(reason), sell_source)
                return (False, "guard_fail")
            
            val_eff = qty * price_for_log
            logging.info("SELL(SIM) %s qty~%s @~%s ≈ %s원 (reason=%s)",
                        market,
                        f"{qty:.8f}".rstrip('0').rstrip('.'),
                        f"{price_for_log:,.0f}",
                        f"{val_eff:,.0f}",
                        reason or "simulate")
            return (True, None)

        # 실제 주문 전송
        url = f"{API_HOST}/v1/orders"
        body = {"market": market, "side": "ask", "ord_type": "market", "volume": str(qty)}
        params_dict = dict(sorted(body.items()))
        headers = self._auth_headers(params_dict)

        logging.info("[SELL-READY] %s qty=%s (~%s원)", market, f"{qty:.8f}".rstrip('0').rstrip('.'),
                    f"{qty*price_for_log:,.0f}")

        # FINAL-GUARD 체크 (실거래에서 simulate=False 전달)
        ok, reason, detail = self._final_guard('SELL', market, qty=qty, simulate=False, panic_mode=panic_mode)
        qty_str = f"qty={qty}" if 'qty' in detail else ""
        log_fields = f"side=SELL symbol={market} live_trade={detail.get('live_trade', False)} simulate={detail.get('simulate', True)} {qty_str} wl={detail.get('wl', 'N')} bl={detail.get('bl', 'N')} cd_rem={detail.get('cd_rem', 0):.0f} dll_ok={detail.get('dll_ok', 'Y')} min_ok={detail.get('min_ok', 'Y')}"
        
        if ok:
            logging.info(f"[FINAL-GUARD] PASS {log_fields}")
        else:
            guard_reason = str(reason or "unknown_guard")
            est_sell_krw = float(qty) * float(price_for_log or 0.0)
            can_force_sell = (qty > 0 and avail > 0 and est_sell_krw >= 5000.0 and sell_source in ("stop_loss", "rotation", "manual"))
            if can_force_sell and guard_reason in ("wl_miss", "blacklist", "cooldown"):
                logging.warning(
                    "[SELL-GUARD-BYPASS] symbol=%s source=%s reason=%s qty=%s avail=%s est_krw=%.0f",
                    market, sell_source, guard_reason, qty, avail, est_sell_krw
                )
            else:
                _notify_strategy_last_event(f"SELL-BLOCK reason=guard_fail symbol={market} detail={guard_reason}")
                logging.info(
                    "[SELL-BLOCK] reason=guard_fail symbol=%s qty=%s est_krw=%.0f live_trade=%s simulate=%s detail=%s",
                    market, qty, qty * price_for_log, not simulate, simulate, guard_reason
                )
                self._set_last_sell_fail("guard_fail", guard_reason, sell_source)
                return (False, "guard_fail")

        # 실제 주문 전송 (예외/실패 시 무조건 api_failed로 통일)
        url = f"{API_HOST}/v1/orders"
        body = {"market": market, "side": "ask", "ord_type": "market", "volume": str(qty)}
        params_dict = dict(sorted(body.items()))
        try:
            headers = self._auth_headers(params_dict)
            r = self._request_with_retry("POST", url, params=params_dict, headers=headers, timeout=10, max_retries=2)
        except Exception as e:
            _notify_strategy_last_event(f"SELL-BLOCK reason=api_failed symbol={market}")
            logging.warning(
                "[SELL-BLOCK] reason=api_failed status=request_err err=%s body_hint=N/A market=%s qty=%s",
                _safe(e)[:80], market, qty
            )
            self._set_last_sell_fail("api_failed", _safe(e)[:80], sell_source)
            return (False, "api_failed")
        logging.info("SELL %s qty=%s -> %s", market, f"{qty:.8f}".rstrip('0').rstrip('.'), r.text)

        # 성공여부 판단(참고: 일부 종목은 부분체결/대기로 올 수 있음)
        try:
            js = r.json()
            ok = (r.status_code // 100 == 2) and bool(js.get("uuid"))
        except Exception:
            ok = False
        if not ok:
            status = getattr(r, "status_code", 0)
            body_raw = getattr(r, "text", "") or ""
            body_hint = (body_raw[:120] if body_raw else "N/A")
            err = ""
            try:
                js = r.json()
                err = str(js.get("error", {}).get("message", js.get("message", "")) or "")[:80]
            except Exception:
                err = body_hint[:80] if body_hint else "N/A"
            _notify_strategy_last_event(f"SELL-BLOCK reason=api_failed symbol={market}")
            logging.warning(
                "[SELL-BLOCK] reason=api_failed status=%s err=%s body_hint=%s market=%s qty=%s",
                status, err, body_hint, market, qty
            )
            self._set_last_sell_fail("api_failed", f"status={status} err={err}", sell_source)
            return (False, "api_failed")
        try:
            # 최신가 기준 대략 체결가치 추정
            vol = float(qty)
            krw = float(vol * price_for_log) if price_for_log else 0.0
            explain = (meta or {}).get("explain") if isinstance(meta, dict) else None
            explain = explain if isinstance(explain, dict) else None
            if explain:
                rsn_short, rsn_tip = format_trade_reason(explain)
            else:
                rsn_short, rsn_tip = format_trade_reason_fallback(reason or "LIVE ok")
            ai_meta = _ai_meta_for_log(self._settings)
            extra = ai_meta.pop("reason_tooltip_extra", "")
            if extra:
                rsn_tip = (rsn_tip or "") + "\n" + extra
            log_trade(time.time(), market, "SELL", price_for_log or 0.0, vol, -krw, reason or f"LIVE ok", strategy_id=strategy_id, strategy_info=(strategy_info or reason), reason_short=rsn_short, reason_tooltip=rsn_tip, **ai_meta)
            _notify_trade_recorded()
            _notify_strategy_last_event(f"SELL {market} qty={qty} est_krw={krw:.0f} success")
        except Exception:
            pass
        self._set_last_sell_fail(None, "", sell_source)
        return (True, None)

    # ----- 단일 엔트리포인트: try_buy -----
    def _resolve_order_amount_krw(self) -> int | None:
        """
        주문 금액 결정 SSOT 함수
        - order_amount_krw가 5000 이상이면 그 값이 최종값
        - order_amount_krw가 없거나 5000 미만이면 available_krw * order_amount_pct/100 사용
        - 5000 미만이면 None 반환 (주문 스킵)
        """
        try:
            # 가용자산 조회
            available_krw = self._compute_available_krw()
            
            # 설정 스냅샷 - dict로 통일
            stg = getattr(self._settings, "strategy", {}) or {}
            if hasattr(stg, "model_dump"):
                stg = stg.model_dump()
            if not isinstance(stg, dict):
                try:
                    stg = dict(stg)
                except Exception:
                    stg = {}

            # 1) order_amount_krw 우선 (숫자칸 최종값) - dict.get만 사용
            order_amount_krw = int(stg.get("order_amount_krw", 0) or 0)
            order_amount_pct = float(stg.get("order_amount_pct", 0.0) or 0.0)

            # pct가 0.2처럼 분수(=20%)로 들어오면 %로 보정
            if 0.0 < order_amount_pct <= 1.0:
                order_amount_pct = order_amount_pct * 100.0

            # 설정 진단 로그
            has_krw = ("order_amount_krw" in stg) and (stg.get("order_amount_krw") is not None)
            has_pct = ("order_amount_pct" in stg) and (stg.get("order_amount_pct") is not None)
            source_path = f"strategy.{type(stg).__name__}"
            log.info(f"[SETTINGS-DUMP] has_order_amount_krw={has_krw} value={order_amount_krw} has_pct={has_pct} value={order_amount_pct} source_path={source_path}")
            
            log.info(f"[ORDER-AMOUNT-DEBUG] available={available_krw} input_krw={order_amount_krw} input_pct={order_amount_pct}")
            
            if order_amount_krw >= 5000:
                return order_amount_krw
            
            # 2) order_amount_pct로 계산 (슬라이더 보조)
            # 기본값은 20% (분수 저장/퍼센트 저장 모두 허용)
            order_amount_pct = float(stg.get("order_amount_pct", 20.0) or 20.0)
            if 0.0 < order_amount_pct <= 1.0:
                order_amount_pct = order_amount_pct * 100.0
            calc_amount = int(available_krw * order_amount_pct / 100.0)

            # 3) 최소주문금액 체크
            if calc_amount < 5000:
                return None  # 주문 스킵 신호
                
            return calc_amount
            
        except Exception as e:
            log.error(f"[ORDER-AMOUNT] 금액 산정 중 오류: {e}")
            return None

    def try_buy(self, symbol: str, krw_amount: float, reason: str = "", meta: dict = None) -> bool:
        """
        단일 엔트리포인트: BUY 결정 후 최종 주문 실행
        - simulate/live_trade 판단 (SSOT)
        - wl/bl 체크 (강제 정책)
        - 최소주문금액/잔고 확인
        - 이미 보유 여부 확인
        """
        global _BYPASS_HOLDING_USED
        
        if meta is None:
            meta = {}
        order_source = (meta.get("order_source") or "ai").lower()
        if order_source not in ("user", "ai"):
            order_source = "ai"
        log.info("[TRY_BUY-IN] market=%s krw_amount=%s source=%s", symbol, krw_amount, order_source)
        
        # SSOT: simulate/live_trade 최종 결정 - 무조건 settings.live_trade 사용
        try:
            _live_trade = bool(getattr(self._settings, "live_trade", False))
        except Exception:
            _live_trade = False
        simulate = not _live_trade
        
        # SSOT: settings 스냅샷 확정 - dict로 통일
        stg = getattr(self._settings, "strategy", {}) or {}
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()
        allow_downscale_order = bool(stg.get("allow_downscale_order_amount", False))
        
        # 실거래 1회 제한 가드 (테스트용)
        once_guard = os.environ.get("KMTS_LIVE_TRADE_ONCE", "0") == "1"
        if _live_trade and once_guard:
            if not hasattr(self, "_live_trade_once_used"):
                self._live_trade_once_used = False
        
        # 🔷 [ROTATION] BUY 실패 원인 추적 초기화
        self._last_buy_fail_reason = None
        
        # 기본값 설정
        allow = True
        final_reason = reason or "ready"
        final_reason_ui = None  # insufficient_balance 시 UX용 메시지
        
        # WL/BL 강제 정책 (simple_momo와 동일)
        wl = set(s.upper() for s in (stg.get("whitelist") or []))
        bl = set(s.upper() for s in (stg.get("blacklist") or []))
        wl_on = symbol.upper() in wl
        bl_on = symbol.upper() in bl
        
        if bl_on:
            allow = False
            final_reason = "blacklist"
            self._last_buy_fail_reason = "other"
        elif wl and not wl_on:
            allow = False
            final_reason = "not_in_whitelist"
            self._last_buy_fail_reason = "other"
        
        # 주문 금액 SSOT: Runner에서 전달한 krw_amount 우선 (5000 이상일 때만), 없으면 설정에서 산정
        MIN_ORDER_KRW = 5000.0
        final_krw_amount = None
        if krw_amount is not None:
            try:
                amt = int(float(krw_amount))
                if amt >= MIN_ORDER_KRW:
                    final_krw_amount = amt
            except (TypeError, ValueError):
                pass
        if final_krw_amount is None:
            final_krw_amount = self._resolve_order_amount_krw()
        if final_krw_amount is None:
            msg = f"ORDER-BLOCK reason=order_amount_failed symbol={symbol}"
            log.warning(
                "[ORDER-BLOCK] reason=order_amount_failed symbol=%s amount=NA simulate=%s live_trade=%s",
                symbol, simulate, _live_trade
            )
            _notify_strategy_last_event(msg)
            return False
            
        available_krw = self._compute_available_krw()
        input_krw = stg.get("order_amount_krw", 0)
        input_pct = stg.get("order_amount_pct", 0.0)
        min_ok = final_krw_amount >= MIN_ORDER_KRW
        # 🔷 [CASH-CHECK] 주문 생성 직전 현금 체크 로그
        log.info("[CASH-CHECK] avail=%.0f need=%.0f 부족=%s symbol=%s", 
                 available_krw, final_krw_amount, "YES" if available_krw < final_krw_amount else "NO", symbol)
        if available_krw == 0.0:
            bal, lck, buf = globals().get("_LAST_KRW_LOG_INFO", (0.0, 0.0, 1000.0))
            log.info(f"[ORDER-AMOUNT] available=0.0 KRW 잔고 {bal:.0f}원 (safety_buffer {buf:.0f}원 차감 → 가용 0원) input_krw={input_krw} pct={input_pct} final={final_krw_amount} min_ok={min_ok} simulate={simulate}")
        else:
            log.info(f"[ORDER-AMOUNT] available={available_krw} input_krw={input_krw} pct={input_pct} final={final_krw_amount} min_ok={min_ok} simulate={simulate}")
        
        if final_krw_amount < MIN_ORDER_KRW:
            msg = f"ORDER-BLOCK reason=min_amount symbol={symbol} amount={final_krw_amount:.0f}"
            log.warning(
                "[ORDER-BLOCK] reason=min_amount symbol=%s amount=%.0f min=%.0f simulate=%s live_trade=%s",
                symbol, final_krw_amount, MIN_ORDER_KRW, simulate, _live_trade
            )
            self._last_buy_fail_reason = "other"
            _notify_strategy_last_event(msg)
            return False
        
        # 최대 투자금액(상한) 가드: BUY만, cap>0일 때 (보유 평가합계 + 이번 주문) > cap 이면 차단
        cap_krw = int(stg.get("max_invest_cap_krw", 0) or 0)
        if cap_krw > 0:
            invested = self._compute_invested_krw()
            if invested + float(final_krw_amount) > cap_krw:
                self._last_buy_fail_reason = "max_invest_cap_exceeded"
                msg = f"ORDER-BLOCK reason=max_invest_cap_exceeded symbol={symbol} (최대 투자금액 초과로 매수 차단)"
                _notify_strategy_last_event("ORDER-BLOCK reason=max_invest_cap_exceeded (최대 투자금액 초과로 매수 차단)")
                log.warning(
                    "[ORDER-BLOCK] reason=max_invest_cap_exceeded symbol=%s invested=%.0f order=%.0f cap=%.0f",
                    symbol, invested, float(final_krw_amount), cap_krw
                )
                return False
        
        # 잔고 확인 (simulate가 아닐 때만)
        if not simulate:
            try:
                rows = self.fetch_accounts()
                krw_balance = 0.0
                krw_found = False
                for a in (rows or []):
                    if (a.get("currency") or "").upper() == "KRW":
                        krw_balance = float(a.get("balance") or 0.0)
                        krw_found = True
                        break
                if not krw_found:
                    allow = False
                    final_reason = "balance_unavailable"
                    self._last_buy_fail_reason = "other"
                elif krw_balance < final_krw_amount:
                    try:
                        _, _, safety_buf = self._get_trade_cfg()
                    except Exception:
                        safety_buf = 1000.0
                    max_spend = min(float(krw_balance), float(available_krw))
                    adj = int(max_spend)
                    req_i = int(final_krw_amount)
                    if allow_downscale_order and adj >= MIN_ORDER_KRW:
                        log.info(
                            "[BUY-DOWNSCALE] enabled=1 req=%s available=%s final=%s reason=insufficient_balance_downscale",
                            req_i, int(available_krw), adj,
                        )
                        final_krw_amount = adj
                        allow = True
                        final_reason = reason or "ready"
                        final_reason_ui = None
                        self._last_buy_fail_reason = None
                        log.info(
                            "[CASH-CHECK] avail=%.0f need=%.0f 부족=NO action=BUY_DOWNSCALE symbol=%s",
                            available_krw, float(final_krw_amount), symbol,
                        )
                    else:
                        allow = False
                        final_reason = f"insufficient_balance_{krw_balance}"
                        final_reason_ui = (
                            f"KRW 잔고 {krw_balance:.0f}원 (safety_buffer {safety_buf:.0f}원 차감) "
                            f"→ 요청 {final_krw_amount:.0f}원 부족"
                        )
                        self._last_buy_fail_reason = "insufficient_krw"
                        log.info(
                            "[BUY-DOWNSCALE] enabled=0 req=%s available=%s final=%s reason=insufficient_balance_block",
                            req_i, int(available_krw), adj,
                        )
                        log.info(
                            "[CASH-CHECK] avail=%.0f need=%.0f 부족=YES action=BUY_SKIP symbol=%s",
                            krw_balance, final_krw_amount, symbol,
                        )
            except Exception:
                allow = False
                final_reason = "balance_check_failed"
                self._last_buy_fail_reason = "other"
        
        # 이미 보유 여부 확인
        coin = coin_from_market(symbol)
        if coin:
            try:
                current_balance = available_coin_via_accounts(self, coin)
                if current_balance > 0:
                    # DUST HOLDING IGNORE (KRW)
                    MIN_HOLDING_KRW = 5000  # <= 5천원 미만은 '먼지'로 보고 보유 차단에서 제외
                    
                    # Calculate KRW value of holding
                    try:
                        # Get current price to calculate KRW value
                        from app.services.price_service import get_current_price
                        current_price = get_current_price(symbol)
                        holding_krw = float(current_balance) * float(current_price)
                    except Exception:
                        holding_krw = 0.0
                    
                    # If dust holding, treat as not holding
                    if holding_krw < MIN_HOLDING_KRW:
                        log.info("[HOLDING-DUST] sym=%s holding_qty=%.8f krw=%.2f < %d -> treat as NOT holding",
                                 symbol, current_balance, holding_krw, MIN_HOLDING_KRW)
                        current_balance = 0  # 먼지 보유는 0으로 처리
                    
                    # Holding bypass 1회용 스위치
                    global _BYPASS_HOLDING_USED
                    bypass = (os.getenv("KMTS_BYPASS_HOLDING", "0") == "1") and (not _BYPASS_HOLDING_USED)
                    if bypass:
                        _BYPASS_HOLDING_USED = True
                        log.warning(f"[HOLDING-BYPASS] applied once: market={symbol} holding_check_skipped=True balance={current_balance}")
                        current_balance = 0  # 우회: 보유량 0으로 처리
                    
                    if current_balance > 0:
                        # 실계좌 1회 재검증: 가짜 보유로 차단 방지 (STOP/START 직후, API 지연 등)
                        recheck_balance = available_coin_via_accounts(self, coin)
                        recheck_krw = 0.0
                        try:
                            from app.services.price_service import get_current_price
                            recheck_price = get_current_price(symbol)
                            recheck_krw = float(recheck_balance) * float(recheck_price or 0)
                        except Exception:
                            pass
                        if recheck_balance <= 0 or recheck_krw < MIN_HOLDING_KRW:
                            log.info("[HOLDING-REVERIFY] sym=%s first=%.8f recheck=%.8f krw=%.2f -> treat as NOT holding",
                                     symbol, current_balance, recheck_balance, recheck_krw)
                            current_balance = 0  # 재검증: 미보유로 처리
                    
                    if current_balance > 0:
                        # 조건부 허용(추가매수): A) 쿨다운 300초 경과 B) 먼지(상단 처리) C) allow_downscale
                        SCALE_IN_COOLDOWN_SEC = 300
                        scale_in_allowed = False
                        scale_in_detail = ""
                        try:
                            last_ts = last_order_ts_by_market(symbol)
                            if last_ts is None or (time.time() - last_ts) >= SCALE_IN_COOLDOWN_SEC:
                                scale_in_allowed = True
                                scale_in_detail = "cooldown_passed"
                        except Exception:
                            pass
                        if not scale_in_allowed:
                            allow_downscale = bool(stg.get("allow_downscale_order_amount", False))
                            if allow_downscale:
                                scale_in_allowed = True
                                scale_in_detail = "allow_downscale"
                        if scale_in_allowed:
                            final_reason = f"scale_in_allowed detail={scale_in_detail}" if scale_in_detail else "scale_in_allowed"
                        else:
                            allow = False
                            final_reason = f"already_holding_{current_balance}"
                            if self._last_buy_fail_reason is None:
                                self._last_buy_fail_reason = "other"
            except Exception:
                pass
        
        # 실거래 1회 제한 체크 (다른 검증 후 최종 단계에서)
        if _live_trade and once_guard and self._live_trade_once_used:
            allow = False
            final_reason = "live_trade_once_used"
        
        # 최종 로그 (2줄만 유지)
        # 런타임 덤프 로그
        log.warning(
            f"[HOLDING-BYPASS-RT] env={os.getenv('KMTS_BYPASS_HOLDING','0')} "
            f"used={globals().get('_BYPASS_HOLDING_USED','<NA>')} "
            f"reason_pre={final_reason}"
        )
        
        bypass = (os.getenv("KMTS_BYPASS_HOLDING", "0") == "1") and (not _BYPASS_HOLDING_USED)
        
        if bypass and isinstance(final_reason, str) and ("already_holding" in final_reason):
            _BYPASS_HOLDING_USED = True
            log.warning(f"[HOLDING-BYPASS] applied once at ORDER-FINAL: symbol={symbol} reason_before={final_reason}")
            allow = True
            final_reason = "holding_bypass_once"
        
        log.info("[ORDER-FINAL] symbol=%s allow=%s simulate=%s reason=%s wl_on=%s bl_on=%s amount=%s",
                symbol, allow, simulate, final_reason, wl_on, bl_on, final_krw_amount)
        
        if not allow:
            # 🔷 [ROTATION] 실패 원인 기록 (현금 부족이 아니면 "other")
            if self._last_buy_fail_reason is None:
                self._last_buy_fail_reason = "other"
            msg = f"ORDER-BLOCK {final_reason_ui} symbol={symbol}" if final_reason_ui else f"ORDER-BLOCK reason={final_reason} symbol={symbol}"
            log.warning(
                "[ORDER-BLOCK] reason=%s symbol=%s amount=%.0f simulate=%s live_trade=%s",
                final_reason, symbol, final_krw_amount, simulate, _live_trade
            )
            _notify_strategy_last_event(msg)
            return False
        
        # 주문 실행
        if allow:
            # 실제 주문 실행
            try:
                # 호출 직전 로그
                log.info(
                    f"[TRY_BUY_CALL] market={symbol} krw={final_krw_amount} simulate={not _live_trade} "
                    f"reason={final_reason!s} has_meta={meta is not None} "
                    f"kwargs_keys=NA"  # try_buy는 **kwargs 없음
                )
                
                # simulate 뒤집힘 추적 로그
                log.warning(
                    f"[SIM-FLOW] try_buy simulate_in={not _live_trade} -> calling buy_market simulate_out={not _live_trade} "
                    f"live_trade={_live_trade} self_simulate={getattr(self, '_simulate', None)}"
                )
                
                # ✅ SIM-FLOW LOG: try_buy에서 buy_market 호출 직전
                log.warning(f"[SIM-FLOW] TRY_BUY simulate_in={not _live_trade} self_simulate={getattr(self,'_simulate',None)} market={symbol} krw={final_krw_amount}")
                
                success = self.buy_market(symbol, final_krw_amount, simulate=not _live_trade, reason=final_reason, meta=meta)
                if success:
                    log.info("[ORDER] BUY symbol=%s amount=%s simulate=%s success", symbol, final_krw_amount, not _live_trade)
                    # 🔷 [ROTATION] 성공 시 실패 원인 초기화
                    self._last_buy_fail_reason = None
                # 실거래 1회 제한: 실주문 성공 시점에만 카운트
                if _live_trade and once_guard and success is True:
                    self._live_trade_once_used = True
                
                return success
            except TypeError as e:
                log.error(f"[TRY_BUY_TYPEERROR] {e}")
                raise
            except Exception as e:
                log.error("[ORDER-EXEC] 실패: %s", _safe(e))
                log.debug("[ORDER-EXEC] traceback:\n%s", traceback.format_exc())
                _notify_strategy_last_event(f"ORDER-BLOCK reason=order_exec_failed symbol={symbol} error={_safe(e)[:40]}")
                log.warning(
                    "[ORDER-BLOCK] reason=order_exec_failed symbol=%s amount=%.0f simulate=%s live_trade=%s error=%s",
                    symbol, final_krw_amount, simulate, _live_trade, _safe(e)
                )
                return False
        else:
            return False

    def get_last_buy_fail_reason(self) -> str | None:
        """🔷 [ROTATION] BUY 실패 원인 반환 (rotation 기능용)"""
        return getattr(self, "_last_buy_fail_reason", None)

    # ----- 시장가 매수(원화 지정) -----
    def buy_market(self, market: str, krw_amt: float, simulate=True, reason: str = "", strategy_id: str = "default", strategy_info: str | None = None, meta=None, **kwargs) -> bool:
        """
        시장가 매수(원화 지정).
        - 가용KRW/최대투자금 한도 내에서 5,000원 배수로 주문
        - 수수료/슬리피지는 가용KRW 산출(안전버퍼)과 체결 시점에서 처리
        """
        log.info("[BUY_MARKET-IN] market=%s krw_amount=%s", market, krw_amt)
        # 런타임 안전장치: meta 파라미터 로깅
        try:
            if meta is not None:
                if isinstance(meta, dict):
                    meta_keys = list(meta.keys())[:5]  # 최대 5개 키만 표시
                    log.info(f"[ORDER-EXEC] buy_market meta=<dict keys={meta_keys}>")
                else:
                    log.info(f"[ORDER-EXEC] buy_market meta_type={type(meta).__name__}")
        except Exception:
            log.info("[ORDER-EXEC] buy_market meta_logging_failed")
        
        # 진입 로그 추가
        has_meta = meta is not None
        log.info(f"[ORDER-EXEC] buy_market ENTRY symbol={market} amount={krw_amt} simulate={simulate} meta={has_meta}")
        
        # ✅ SIM-FLOW LOG: buy_market 함수 진입 직후
        log.warning(f"[SIM-FLOW] BUY_MARKET simulate_arg={simulate} self_simulate={getattr(self,'_simulate',None)} market={market} krw={krw_amt}")
        
        # 실호출/시뮬 분기 확정 로그
        log.warning(f"[UPBIT-CALL-GATE] simulate_arg={simulate} self_simulate={getattr(self,'_simulate',None)} will_call_upbit={not simulate}")
            
        # SSOT: 실거래 여부는 settings.live_trade로 확정하고, runner의 simulate 인자 혼선을 무시
        # ✅ PATCH: simulate 파라미터 우선 - settings 덮어쓰기 방지
        try:
            _live_trade = bool(getattr(self._settings, "live_trade", False))
        except Exception:
            _live_trade = False
        # simulate = not _live_trade  # ❌ REMOVED: 파라미터 simulate를 덮어쓰지 않음

        # 주문 함수 진입 로그 (DEBUG 플래그일 때만)
        if os.environ.get("KMTS_DEBUG_BUY_READY", "0") == "1":
            logging.info(
                "[BUY-READY] %s amt=%s entry=buy_market simulate=%s live_trade=%s",
                market, krw_amt, simulate, _live_trade
            )
        
        # stg 변수 정의 - dict로 통일
        stg = getattr(self._settings, "strategy", {}) or {}
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()
        
        # 주문 실행 직전 설정값 스냅샷 (DEBUG 플래그일 때만)
        if os.environ.get("KMTS_DEBUG_ORDER_READY", "0") == "1":
            try:
                symbol = market  # Upbit market format
                # 주문 허용 여부 판단 (간단히)
                allow = True
                reason = "ready"
                
                # WL/BL 체크
                wl = set(s.upper() for s in (stg.get("whitelist") or []))
                bl = set(s.upper() for s in (stg.get("blacklist") or []))
                wl_on = symbol.upper() in wl
                bl_on = symbol.upper() in bl
                
                if bl_on:
                    allow = False
                    reason = "blacklist"
                elif wl and not wl_on:
                    allow = False
                    reason = "not_in_whitelist"
                
                # 핵심 설정값
                pos = stg.get("pos_size_pct", "N/A")
                rr = stg.get("rr_ratio", "N/A")
                dll = stg.get("daily_loss_limit_pct", "N/A")
                
                logging.info("[ORDER-READY] symbol=%s allow=%s pos=%s rr=%s dll=%s wl_on=%s bl_on=%s reason=%s",
                            symbol, allow, pos, rr, dll, wl_on, bl_on, reason)
            except Exception:
                # 로그 실패해도 주문 진행 방지 금지
                pass
        
        # === side-cooldown 체크 (성공 후에만 갱신, monotonic) ===
        try:
            cd = float(getattr(self._settings, "buy_cooldown_sec", None) or self.stg("buy_cooldown_sec", 60))
            now = time.monotonic()
            left = max(0.0, (self._side_cooldown["BUY"].get(market, 0.0) or 0.0) - now)
            if left > 0:
                logging.info("[BUY-SKIP] %s side-cooldown %.1fs left", market, left)
                return False
        except Exception:
            pass

        if not self._can_order():
            return False
        if self._settings is None:
            raise RuntimeError("설정 미주입: set_settings 먼저 호출")

        # 계정 자산 스냅샷
        try:
            rows = self.fetch_accounts()
        except Exception:
            rows = []
        krw_balance, krw_locked, coins = 0.0, 0.0, []
        for a in (rows or []):
            cur = (a.get("currency") or "").upper()
            if cur == "KRW":
                krw_balance = float(a.get("balance") or 0.0)
                krw_locked  = float(a.get("locked")  or 0.0)
            else:
                coins.append((cur, float(a.get("balance") or 0.0),
                                float(a.get("locked")  or 0.0),
                                float(a.get("avg_buy_price") or 0.0)))

        # 총자산 계산(시세 실패시 평단 사용)
        total_asset = krw_balance
        try:
            prices = {}
            mkts = [f"KRW-{c}" for c,_,_,_ in coins]
            if mkts:
                for i in range(0, len(mkts), 50):
                    for t in (get_tickers(mkts[i:i+50]) or []):
                        prices[t.get("market")] = float(t.get("trade_price") or 0.0)
            for c, bal, lck, avg in coins:
                px = prices.get(f"KRW-{c}", 0.0) or avg
                total_asset += (bal + lck) * px
        except Exception:
            for c, bal, lck, avg in coins:
                total_asset += (bal + lck) * avg

        # 가용KRW/남은 한도 (SSOT: meta.max_cap_krw 우선, 없으면 settings)
        available_krw = self._compute_available_krw()
        try:
            if meta and isinstance(meta, dict) and meta.get("max_cap_krw") is not None:
                max_total = float(meta["max_cap_krw"])
            else:
                max_total = float(getattr(self._settings, "max_total_krw", 50_000))
        except Exception:
            max_total = 50_000.0
        orderable_krw = available_krw
        remaining_cap = max(0.0, float(max_total) - (float(total_asset) - float(orderable_krw)))
        if remaining_cap == float("inf"):
            remaining_cap = orderable_krw

        # 포지션 비중 적용: available_krw * position_pct/100
        pos_pct = float(_safe(stg.get("pos_size_pct", 2.5), 2.5))  # percent 단위
        position_limit = available_krw * pos_pct / 100.0

        MIN_ORDER_KRW = 5000.0
        # SSOT 금액 고정: 사용자/AI 결정 금액 그대로 사용. 다운스케일 금지.
        try:
            req = int(float(krw_amt))
        except (TypeError, ValueError):
            req = 0
        
        # hard_cap 계산: pos_size_pct가 최소 주문금액을 막지 않게 보호
        hard_cap_candidate = min(available_krw, remaining_cap, position_limit) if remaining_cap != float("inf") else min(available_krw, position_limit)
        hard_cap_bypass_reason = None
        
        if hard_cap_candidate < MIN_ORDER_KRW:
            if req >= MIN_ORDER_KRW:
                # 테스트/소액 계좌 보호: pos_size_pct 우회, 최소 주문금액 보호
                hard_cap = min(available_krw, req)
                hard_cap_bypass_reason = "pos_size_pct_bypassed_for_min_order"
            else:
                # order_amount_krw 자체가 최소 주문금액 미만이면 기존대로 BLOCK
                hard_cap = hard_cap_candidate
        else:
            hard_cap = hard_cap_candidate
        
        rem_cap_log = remaining_cap if remaining_cap != float("inf") else -1

        log.info(
            "[BUY_CAP] market=%s req=%s available=%.0f position_limit=%.0f remaining_cap=%s hard_cap=%.0f%s",
            market, req, available_krw, position_limit, rem_cap_log, hard_cap,
            f" bypass_reason={hard_cap_bypass_reason}" if hard_cap_bypass_reason else ""
        )
        if hard_cap_bypass_reason:
            log.info(
                "[BUY-CAP-ADJUST] reason=%s symbol=%s available=%.0f position_limit=%.0f order_amount=%d final_cap=%.0f",
                hard_cap_bypass_reason, market, available_krw, position_limit, req, hard_cap
            )

        # 정책 2: 다운스케일 옵션 확인
        allow_downscale = False
        try:
            stg = getattr(self._settings, "strategy", {}) or {}
            if hasattr(stg, "model_dump"):
                stg = stg.model_dump()
            allow_downscale = bool(stg.get("allow_downscale_order_amount", False))
        except Exception:
            allow_downscale = False
        
        if req < MIN_ORDER_KRW:
            _notify_strategy_last_event(f"ORDER-BLOCK reason=req_under_min symbol={market}")
            log.warning(
                "[ORDER-BLOCK] reason=req_under_min symbol=%s amount=%s simulate=%s live_trade=%s",
                market, req, simulate, not simulate
            )
            return False
        if hard_cap < MIN_ORDER_KRW and req < MIN_ORDER_KRW:
            # hard_cap < 5000이고 req도 < 5000인 경우만 BLOCK
            _notify_strategy_last_event(f"ORDER-BLOCK reason=cap_under_min symbol={market} hard_cap={hard_cap:.0f}")
            log.warning(
                "[ORDER-BLOCK] reason=cap_under_min symbol=%s req=%s hard_cap=%.0f simulate=%s live_trade=%s",
                market, req, hard_cap, simulate, not simulate
            )
            return False
        
        # req > hard_cap: 자동 축소는 allow_downscale_order_amount ON일 때만
        final_req = req
        if req > hard_cap:
            if allow_downscale and hard_cap >= MIN_ORDER_KRW:
                final_req = int(hard_cap)
                log.info(
                    "[CAP-DOWN] req=%s hard_cap=%s final=%s applied=1 reason=cap_downscale",
                    req, hard_cap, final_req,
                )
                log.info(
                    "[BUY-DOWNSCALE] enabled=1 req=%s available=%s final=%s reason=req_exceeds_cap_downscale",
                    int(req), int(hard_cap), final_req,
                )
            else:
                log.info(
                    "[CAP-DOWN] req=%s hard_cap=%s final=%s applied=0 reason=req_exceeds_cap_or_downscale_off",
                    req, hard_cap, req,
                )
                log.info(
                    "[BUY-DOWNSCALE] enabled=%s req=%s available=%s final=%s reason=req_exceeds_cap_block",
                    "1" if allow_downscale else "0",
                    int(req),
                    int(hard_cap),
                    int(req),
                )
                _notify_strategy_last_event(
                    f"ORDER-BLOCK reason=req_exceeds_cap symbol={market} req={req} hard_cap={hard_cap:.0f}"
                )
                log.warning(
                    "[ORDER-BLOCK] reason=req_exceeds_cap symbol=%s req=%s hard_cap=%.0f simulate=%s live_trade=%s downscale=0",
                    market, req, hard_cap, simulate, not simulate,
                )
                return False

        # final_req 사용 (다운스케일된 경우 반영)
        req = final_req

        # 현재가(로그용)
        price = None
        try:
            t = get_tickers([market])[0]
            price = float(t.get("trade_price") or 0) or None
        except Exception:
            pass

        # 시뮬 (SSOT simulate)
        if simulate:
            # FINAL-GUARD 체크 (시뮬에서도 로그를 위해 호출)
            ok, reason, detail = self._final_guard('BUY', market, amount=req, simulate=simulate)
            amt_str = f"amt={req}" if 'amt' in detail else ""
            log_fields = f"side=BUY symbol={market} live_trade={detail.get('live_trade', False)} simulate={detail.get('simulate', True)} {amt_str} wl={detail.get('wl', 'N')} bl={detail.get('bl', 'N')} cd_rem={detail.get('cd_rem', 0):.0f} dll_ok={detail.get('dll_ok', 'Y')} min_ok={detail.get('min_ok', 'Y')}"
            
            if ok:
                logging.info(f"[FINAL-GUARD] PASS {log_fields}")
            else:
                logging.info(f"[FINAL-GUARD] FAIL reason={reason} {log_fields}")
            
            vol = (float(req) / price) if (price and price > 0) else 0.0
            vol_q = (Decimal(str(vol))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            explain = (meta or {}).get("explain") if meta and isinstance(meta, dict) else None
            if explain and isinstance(explain, dict):
                rsn_short, rsn_tip = format_trade_reason(explain)
            else:
                rsn_short, rsn_tip = format_trade_reason_fallback(reason or "simulate")
            ai_meta = _ai_meta_for_log(self._settings)
            extra = ai_meta.pop("reason_tooltip_extra", "")
            if extra:
                rsn_tip = (rsn_tip or "") + "\n" + extra
            log_trade(time.time(), market, "BUY", price, float(vol_q), float(req), reason or "simulate", strategy_id=strategy_id, strategy_info=(strategy_info or reason), reason_short=rsn_short, reason_tooltip=rsn_tip, **ai_meta)
            _notify_trade_recorded()
            _notify_strategy_last_event(f"BUY(SIM) {market} {req}원")
            logging.info("BUY(SIM) %s %s원 -> vol~%s (reason=%s)", market, req, vol_q, reason)
            log.info(f"[UPBIT_RESULT] status=SIMULATED market={market} krw={krw_amt} reason={reason}")
            return True

        # 주문 직전 스냅샷
        logging.info(
            "[BUY-READY] %s amt=%s avail=%.0f cap=%.0f simulate=%s live_trade=%s",
            market, req, available_krw,
            remaining_cap if remaining_cap != float('inf') else -1,
            simulate, (not simulate)
        )

        # FINAL-GUARD 체크 (SSOT simulate 전달)
        ok, reason, detail = self._final_guard('BUY', market, amount=req, simulate=simulate)
        amt_str = f"amt={req}" if 'amt' in detail else ""
        log_fields = f"side=BUY symbol={market} live_trade={detail.get('live_trade', False)} simulate={detail.get('simulate', True)} {amt_str} wl={detail.get('wl', 'N')} bl={detail.get('bl', 'N')} cd_rem={detail.get('cd_rem', 0):.0f} dll_ok={detail.get('dll_ok', 'Y')} min_ok={detail.get('min_ok', 'Y')}"
        
        if ok:
            logging.info(f"[FINAL-GUARD] PASS {log_fields}")
        else:
            logging.info(f"[FINAL-GUARD] FAIL reason={reason} {log_fields}")
            return False

        # 실거래 전송
        url = f"{API_HOST}/v1/orders"
        body = {"market": market, "side": "bid", "ord_type": "price", "price": str(req)}
        params_dict = dict(sorted(body.items()))
        headers = self._auth_headers(params_dict)
        r = self._request_with_retry("POST", url, params=params_dict, headers=headers, timeout=10, max_retries=2)
        logging.info("BUY %s %s -> %s", market, req, r.text)

        ok, uuid_ = False, None
        try:
            js = r.json()
            ok = (r.status_code // 100 == 2) and bool(js.get("uuid"))
            uuid_ = js.get("uuid")
        except Exception:
            ok = False
        
        # Upbit 결과 1줄 요약
        if ok:
            _notify_strategy_last_event(f"BUY {market} {req}원 success uuid={uuid_}")
            log.info(f"[UPBIT_RESULT] ok=True market={market} uuid={uuid_}")
            log.info(f"[ORDER-EXEC] buy_market SUCCESS symbol={market} uuid={uuid_}")
        else:
            error_msg = getattr(r, "text", "Unknown error")
            log.error(f"[UPBIT_RESULT] ok=False market={market} err={error_msg}")
            log.error(f"[ORDER-EXEC] buy_market FAILED symbol={market} error='{error_msg}'")
            
        if not ok:
            logging.warning("BUY 실패: 응답=%s", getattr(r, "text", ""))
            return False

        # 성공 후에만 side-cooldown 시작
        try:
            cd = float(getattr(self._settings, "buy_cooldown_sec", None) or self.stg("buy_cooldown_sec", 60))
            self._side_cooldown["BUY"][market] = time.monotonic() + cd
        except Exception:
            pass

        vol_est = (float(req) / price) if (price and price > 0) else 0.0
        explain = (meta or {}).get("explain") if meta and isinstance(meta, dict) else None
        if explain and isinstance(explain, dict):
            rsn_short, rsn_tip = format_trade_reason(explain)
        else:
            rsn_short, rsn_tip = format_trade_reason_fallback(reason or f"LIVE uuid={uuid_}")
        ai_meta = _ai_meta_for_log(self._settings)
        extra = ai_meta.pop("reason_tooltip_extra", "")
        if extra:
            rsn_tip = (rsn_tip or "") + "\n" + extra
        log_trade(time.time(), market, "BUY", price, float(vol_est), float(req), reason or f"LIVE uuid={uuid_}", strategy_id=strategy_id, strategy_info=(strategy_info or reason), reason_short=rsn_short, reason_tooltip=rsn_tip, **ai_meta)
        _notify_trade_recorded()
        return True

    # ----- panic -----
    def panic_stop(self):
        self._panic = True
        log.warning("PANIC STOP 발동 — 신규 주문 차단")

    def reset_panic(self):
        self._panic = False
        log.info("PANIC 해제")

# 싱글턴 인스턴스 (기존 모듈들이 import 하므로 유지)
svc_order = OrderService()

# 런타임 시그니처 덤프 (싱글턴 생성 직후)
try:
    if not getattr(svc_order, "_rt_dumped_boot", False):
        setattr(svc_order, "_rt_dumped_boot", True)
        fn = getattr(svc_order, "buy_market", None)
        if fn and hasattr(fn, "__code__"):
            log.info(
                f"[BUYMARK-RT-BOOT] svc_id={id(svc_order)} type={type(svc_order).__name__} "
                f"module_file={os.path.abspath(__file__)} "
                f"func_file={fn.__code__.co_filename} func_line={fn.__code__.co_firstlineno} "
                f"sig={inspect.signature(fn)}"
            )
        else:
            log.info(
                f"[BUYMARK-RT-BOOT] svc_id={id(svc_order)} type={type(svc_order).__name__} "
                f"module_file={os.path.abspath(__file__)} buy_market=NONE"
            )
except Exception as e:
    log.exception(f"[BUYMARK-RT-BOOT] dump failed: {e}")

# --- module-level exports for UI runner ---------------------------------
def start_strategy(settings):
    """
    UI에서 import하는 표준 실행 엔트리.
    - 최신 설정 주입 후 실행 러너를 '여러 후보 경로'에서 자동 탐색해 위임
    - 러너가 없으면 svc_order.run() 또는 running 플래그만 세팅
    - 실행 직전/직후 전략 요약 2줄을 INFO + 버스 이벤트로 알림
    """
    try:
        import importlib, logging
        svc_order.set_settings(settings)

        # --- 실행 전 요약 2줄 ---
        bus = None  # [FIX] 반드시 사전 정의
        try:
            import app.core.bus as eventbus
            bus = eventbus            # [FIX] 성공 시에도 bus에 바인딩
        except Exception:
            bus = None

        def _safe(v, d=""):
            return v if (v is not None and v != "") else d

        # ★ 주입 완료된 런타임 전략 스냅샷 우선 사용
        try:
            stg = getattr(svc_order, "_strategy", None)
            if not isinstance(stg, dict):
                stg = getattr(settings, "strategy", {}) or {}
                if hasattr(stg, "model_dump"):
                    stg = stg.model_dump()
        except Exception:
            stg = {}

        # 핵심 파라미터 수집
        strategy_id = str(_safe(stg.get("strategy_id", "default")))
        inds        = [i.upper() for i in (stg.get("indicators") or [])]
        pos         = float(_safe(stg.get("pos_size_pct", 2.5), 2.5))  # percent 단위로 읽기
        rr          = float(_safe(stg.get("rr_ratio", 2.0), 2.0))
        cd          = int(float(_safe(stg.get("cooldown_sec", 30), 30)))
        dll         = float(_safe(stg.get("daily_loss_limit_pct", 3.0), 3.0))  # percent 단위로 읽기
        aggr        = _safe(stg.get("aggressiveness_level", 5))
        mode        = _safe(stg.get("strategy_mode", "ai"))
        combine     = _safe(stg.get("indicators_mode", "and")).upper()
        # ✅ P2-1-③: 시장환경 SSOT 키 우선, 레짐 키는 보조 표기만
        market_vol = _safe(stg.get("market_volatility", "중간 변동성"))
        market_liq = _safe(stg.get("market_liquidity", "중간 유동성"))
        trading_sess = _safe(stg.get("trading_session", "전일"))
        
        # 레짐 필드는 보조 표기만 (디버그용)
        regime = _safe(stg.get("vol_regime", "ai"))
        liq = _safe(stg.get("liquidity", "ai"))
        session = _safe(stg.get("session", "ai"))
        
        wl          = stg.get("whitelist") or []
        bl          = stg.get("blacklist") or []

        # line1/line2 생성 (전략정보 상자 & 매매 사유에 동일하게 사용)
        line1 = (
            f"id={strategy_id} · mode={mode} · aggr={aggr} · "
            f"pos={pos:.1f}% · rr={rr} · cd={cd}s · dll={dll:.1f}%"
        )
        line2 = (
            f"inds={inds if inds else ['-']} · combine={combine} · "
            f"mVol={market_vol} mLiq={market_liq} tSess={trading_sess} · "
            f"(rLiq={liq} rSess={session}) · WL {len(wl)} / BL {len(bl)}"
        )

        logging.getLogger(__name__).info(line1)
        logging.getLogger(__name__).info(line2)
        if bus and hasattr(bus, "publish"):
            try:
                bus.publish("strategy_summary_updated", {"line1": line1, "line2": line2, "strategy_id": strategy_id})
            except Exception:
                pass

        # 실행 러너 후보(상위→하위 우선순위)
        candidates = [
            ("app.strategy.runner", "start_strategy"),
            ("app.services.strategy_runner", "start_strategy"),
            ("app.runtime.ai_only_runtime", "start_strategy"),
            ("app.services.ai_only_engine", "start"),
            ("app.main", "start_strategy"),
        ]

        for mod_name, fn_name in candidates:
            try:
                mod = importlib.import_module(mod_name)
                fn  = getattr(mod, fn_name, None)
                if callable(fn):
                    fn(settings)
                    try:
                        svc_order._running = True
                    except Exception:
                        pass
                    logging.getLogger(__name__).info(f"[start_strategy] delegated to {mod_name}.{fn_name}")
                    # --- 실행 직후에도 요약 한 번 더(러너가 파라미터 재가공했을 수 있음) ---
                    try:
                        if bus and hasattr(bus, "publish"):
                            bus.publish("strategy_summary_updated", {"line1": line1, "line2": line2})
                    except Exception:
                        pass
                    return True
            except Exception as _e:
                logging.getLogger(__name__).debug(f"[start_strategy] candidate miss {mod_name}.{fn_name}: {_e}")

        runner = getattr(svc_order, "run", None) or getattr(svc_order, "start", None)
        if callable(runner):
            runner()
        else:
            try:
                svc_order._running = True
            except Exception:
                pass
        logging.getLogger(__name__).info("[start_strategy] 설정 주입 완료 (no runner)")
        return True

    except Exception as e:
        logging.getLogger(__name__).error(f"[start_strategy] 실패: {e}")
        return False

def stop_strategy():
    """
    UI에서 import하는 표준 정지 엔트리.
    - 실행 러너를 '여러 후보 경로'에서 자동 탐색해 정지 위임
    - 러너가 없으면 svc_order.stop() 또는 running 플래그 해제
    """
    try:
        import importlib

        candidates = [
            ("app.strategy.runner", "stop_strategy"),  # ← 추가: 실제 러너
            ("app.services.strategy_runner", "stop_strategy"),
            ("app.runtime.ai_only_runtime", "stop_strategy"),
            ("app.services.ai_only_engine", "stop"),
            ("app.main", "stop_strategy"),
        ]

        for mod_name, fn_name in candidates:
            try:
                mod = importlib.import_module(mod_name)
                fn  = getattr(mod, fn_name, None)
                if callable(fn):
                    fn()
                    try:
                        svc_order._running = False
                    except Exception:
                        pass
                    logging.getLogger(__name__).info(
                        f"[stop_strategy] delegated to {mod_name}.{fn_name}"
                    )
                    return True
            except Exception as _e:
                logging.getLogger(__name__).debug(
                    f"[stop_strategy] candidate miss {mod_name}.{fn_name}: {_e}"
                )

        # 모든 후보 실패 → 최소 호환
        stopper = getattr(svc_order, "stop", None) or getattr(svc_order, "shutdown", None)
        if callable(stopper):
            stopper()
        else:
            try:
                svc_order._running = False
            except Exception:
                pass
        logging.getLogger(__name__).info("[stop_strategy] 요청 수신 (no runner)")
        return True

    except Exception as e:
        logging.getLogger(__name__).error(f"[stop_strategy] 실패: {e}")
        return False

    def get_last_buy_fail_reason(self) -> str | None:
        """🔷 [ROTATION] BUY 실패 원인 반환 (rotation 기능용)"""
        return getattr(self, "_last_buy_fail_reason", None)
# ------------------------------------------------------------------------
