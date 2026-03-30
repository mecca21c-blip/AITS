from __future__ import annotations
import os, json, base64, secrets
from typing import Tuple
from cryptography.fernet import Fernet
from app.utils.settings_schema import AppSettings, UIConfig, PollConfig, StrategyConfig

_SECRET_FILE = None
_PREFS_FILE = None
_DEFAULTS_FILE = None

# 중복 저장 방지 전역 변수
_last_save_time = 0.0
_last_save_payload = ""
_save_inflight = False
# P0-C: UI 상태 저장 throttle (5초)
_last_ui_state_save_time = 0.0

def _get_prefs_path() -> str:
    """현재 사용 중인 prefs 파일 경로 반환 (진단용)"""
    _ensure_inited()
    return _PREFS_FILE or "unknown"

def _ensure_inited() -> None:
    """
    ✅ Store Lock 하드닝:
    - init_prefs()가 어떤 이유로든 선행되지 않으면(초기화 순서 꼬임),
      암호키/설정 파일 경로가 None 상태가 되어 복호화가 실패하고
      결과적으로 업비트 키가 ""로 로드 → 다음 저장에서 빈값으로 덮어쓰기 발생한다.
    - 이를 방지하기 위해, 미초기화 시 현재 작업 디렉토리 기준 root/data로 자동 초기화한다.
      (KMTS는 보통 프로젝트 루트에서 실행하므로 이 경로가 안정적이다)
    """
    global _SECRET_FILE, _PREFS_FILE, _DEFAULTS_FILE
    if _SECRET_FILE and _PREFS_FILE and _DEFAULTS_FILE:
        return

    try:
        root_dir = os.getcwd()
        data_dir = os.path.join(root_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        _SECRET_FILE = os.path.join(data_dir, "secret.bin")
        _PREFS_FILE = os.path.join(data_dir, "prefs.json")
        _DEFAULTS_FILE = os.path.join(root_dir, "configs", "app.yaml")

        if not os.path.exists(_SECRET_FILE):
            key = Fernet.generate_key()
            with open(_SECRET_FILE, "wb") as f:
                f.write(key)
    except Exception:
        # 최후 폴백: 이후 decrypt/encrypt가 실패해도 예외로 앱이 죽지 않게 한다.
        pass

def init_prefs(root_dir: str, data_dir: str) -> None:
    global _SECRET_FILE, _PREFS_FILE, _DEFAULTS_FILE
    os.makedirs(data_dir, exist_ok=True)
    _SECRET_FILE = os.path.join(data_dir, "secret.bin")      # 로컬 전용 암호 키
    _PREFS_FILE  = os.path.join(data_dir, "prefs.json")      # 설정 저장소(키는 암호화)
    _DEFAULTS_FILE = os.path.join(root_dir, "configs", "app.yaml")
    if not os.path.exists(_SECRET_FILE):
        # 고유 키 생성 (로컬 파일만으로 복호화 가능)
        key = Fernet.generate_key()
        with open(_SECRET_FILE, "wb") as f: f.write(key)

def _fernet() -> Fernet:
    _ensure_inited()
    with open(_SECRET_FILE, "rb") as f:
        key = f.read()
    return Fernet(key)

def _load_defaults() -> AppSettings:
    # YAML 파싱 없이도 최소 구동되도록, 실패하면 하드코딩 기본값 사용
    try:
        import yaml
        with open(_DEFAULTS_FILE, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        raw = {}
    return AppSettings(**raw)

# --- I/O & Logging helpers (추가) -------------------------------------------

def _log_error(msg: str) -> None:
    try:
        import logging
        logging.getLogger(__name__).error(msg)
    except Exception:
        print(f"[prefs] ERROR: {msg}")

def _log_info(msg: str) -> None:
    try:
        import logging
        logging.getLogger(__name__).info(msg)
    except Exception:
        print(f"[prefs] INFO: {msg}")

_SENSITIVE_PATHS = [
    ("upbit", "access_key"),
    ("upbit", "secret_key"),
]


def _merge_env_secrets(data: dict) -> dict:
    """prefs 로드 후 UPBIT / OpenAI 키를 환경 변수로 보강(저장소에 키 없이 동작)."""
    if not isinstance(data, dict):
        return data
    try:
        up = dict(data.get("upbit") or {})
        env_ak = (os.getenv("UPBIT_ACCESS_KEY") or "").strip()
        env_sk = (os.getenv("UPBIT_SECRET_KEY") or "").strip()
        if env_ak:
            up["access_key"] = env_ak
        if env_sk:
            up["secret_key"] = env_sk
        data["upbit"] = up
        st = dict(data.get("strategy") or {})
        env_oai = (os.getenv("OPENAI_API_KEY") or "").strip()
        if env_oai:
            st["ai_openai_api_key"] = env_oai
        data["strategy"] = st
    except Exception:
        pass
    return data

def _safe_decrypt(val: str) -> str:
    # "enc:<token>" 형태(표준 Fernet token) 우선 복호화
    try:
        if isinstance(val, str) and val.startswith("enc:"):
            token = val[4:].encode("utf-8")
            f = _fernet()

            # ✅ 1) 표준(권장): enc:<fernet_token>
            try:
                return f.decrypt(token).decode("utf-8")
            except Exception:
                pass

            # ✅ 2) 레거시 폴백: enc:<b64(fernet_token)>
            try:
                token2 = base64.urlsafe_b64decode(token)
                return f.decrypt(token2).decode("utf-8")
            except Exception:
                return ""
    except Exception:
        return ""
    return val

def _safe_encrypt(val: str) -> str:
    try:
        if isinstance(val, str) and val and not val.startswith("enc:"):
            f = _fernet()
            token = f.encrypt(val.encode("utf-8"))
            # ✅ Fernet.encrypt() 결과 자체가 urlsafe-base64 토큰이므로 "재인코딩" 금지
            return "enc:" + token.decode("utf-8")
    except Exception:
        # 암호화 실패 시 원문 저장(로컬 전용 파일이므로 실사용 가능)
        return val
    return val

def _read_prefs_json() -> dict:
    _ensure_inited()
    """
    prefs.json 로드 + 민감키 복호화 + defaults 보강
    """
    path = _PREFS_FILE or "unknown"
    exists = bool(path != "unknown" and os.path.exists(path))
    try:
        if not _PREFS_FILE or not exists:
            # 파일 없으면 기본값 반환
            defaults = _load_defaults().model_dump()
            ak_len = len(defaults.get("upbit", {}).get("access_key", "").strip())
            sk_len = len(defaults.get("upbit", {}).get("secret_key", "").strip())
            _log_info(f"[PREFS-PATH] path={path} exists={exists} loaded=defaults")
            _log_info(f"[KEY-PERSIST] load: sources=[defaults] final_source=defaults ak_len={ak_len} sk_len={sk_len}")
            return _merge_env_secrets(defaults)
        with open(_PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        # 민감키 복호화
        ak_len = sk_len = 0
        for sect, key in _SENSITIVE_PATHS:
            try:
                if sect in data and key in data[sect]:
                    data[sect][key] = _safe_decrypt(data[sect][key])
                    if key == "access_key":
                        ak_len = len(data[sect][key].strip()) if data[sect][key] else 0
                    elif key == "secret_key":
                        sk_len = len(data[sect][key].strip()) if data[sect][key] else 0
            except Exception:
                pass
        _log_info(f"[PREFS-PATH] path={path} exists=True loaded=prefs.json")
        _log_info(f"[KEY-PERSIST] load: sources=[prefs.json] final_source=prefs.json ak_len={ak_len} sk_len={sk_len}")
        return _merge_env_secrets(data)
    except Exception as e:
        _log_error(f"[PREFS-PATH] path={path} exists={exists} loaded=error error={e!s}")
        _log_error(f"[KEY-PERSIST] load: sources=[error] final_source=error ak_len=0 sk_len=0 error={e}")
        _log_error(f"_read_prefs_json 실패: {e}")
        return _merge_env_secrets(_load_defaults().model_dump())

# [ANCHOR: UTILS_HELPERS_START]
def get_active_strategy_id(prefs) -> str:
    """단일 전략 운용: 저장된 전략 ID가 없으면 'default'."""
    try:
        sid = prefs.get("strategy", {}).get("strategy_id") \
              or prefs.get("strategy_settings", {}).get("strategy_id")
        return sid or "default"
    except Exception:
        return "default"

def get_setting(prefs, key: str, strategy_id: str | None = None, default=None):
    """
    설정 통합 조회. 전략 설정 > 공통 설정 > default 순으로 반환.
    """
    if strategy_id is None:
        strategy_id = get_active_strategy_id(prefs)

    # 전략 섹션 우선
    s = prefs.get("strategy") or prefs.get("strategy_settings") or {}
    if key in s:
        return s.get(key, default)

    # 공통 섹션 (global/common)
    g = prefs.get("global") or prefs.get("common") or {}
    if key in g:
        return g.get(key, default)

    return default

def build_strategy_info_line(prefs) -> str:
    """
    ✅ SSOT(StrategyConfig) 기반 1줄 요약 문자열 생성기.
    - 레거시(style/aggressiveness/combine/ind_bb/...)를 더 이상 사용하지 않는다.
    - 기존 외부 호출 시그니처는 유지한다(하위호환).
    """
    try:
        # 아래에 정의된 SSOT 요약기를 사용(중복 정의/레거시 토큰 생성 제거)
        return _build_strategy_info_line_ssot(prefs)
    except Exception:
        return "strategy=—"
# [ANCHOR: UTILS_HELPERS_END]

def _write_prefs_json(payload: dict) -> bool:
    _ensure_inited()
    """
    prefs.json 저장(민감키 암호화 후 기록, 그 외는 평문)
    """
    try:
        if not _PREFS_FILE:
            raise RuntimeError("_PREFS_FILE is None (init_prefs 누락/경로 초기화 실패)")

        # 중복 저장 방지 가드
        import time
        current_time = time.monotonic()
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # 전역 저장 상태 확인
        global _last_save_time, _last_save_payload, _save_inflight
        
        # 저장 중 재진인 방지
        if _save_inflight:
            return True
        
        # 0.5초 이내 동일 payload 저장 방지
        if (_last_save_time > 0 and 
            current_time - _last_save_time < 0.5 and 
            payload_str == _last_save_payload):
            return True
        
        # 저장 상태 설정
        _save_inflight = True
        _last_save_time = current_time
        _last_save_payload = payload_str

        data = json.loads(json.dumps(payload))  # deepcopy
        # 민감키 암호화
        ak_len = sk_len = 0
        for sect, key in _SENSITIVE_PATHS:
            try:
                if sect in data and key in data[sect]:
                    raw_val = data[sect][key]
                    data[sect][key] = _safe_encrypt(data[sect][key])
                    if key == "access_key":
                        ak_len = len(raw_val.strip()) if raw_val else 0
                    elif key == "secret_key":
                        sk_len = len(raw_val.strip()) if raw_val else 0
            except Exception:
                pass
        os.makedirs(os.path.dirname(_PREFS_FILE), exist_ok=True)
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        _log_info(f"[KEY-PERSIST] save: path={_PREFS_FILE} ak_len={ak_len} sk_len={sk_len} result=ok")
        try:
            _log_info(f"[PREFS] saved -> {_PREFS_FILE}")
        except Exception:
            pass

        return True
    except Exception as e:
        _log_error(f"[KEY-PERSIST] save: path={_PREFS_FILE} ak_len={ak_len} sk_len={sk_len} result=fail error={e}")
        _log_error(f"_write_prefs_json 실패: {e}")
        return False
    finally:
        # 저장 상태 해제
        _save_inflight = False

def load_settings():
    _ensure_inited()
    """
    저장된 prefs.json을 로드하고, Strategy 기본값을 병합하여 누락 키를 채운다.
    """
    from .settings_schema import AppSettings, StrategyConfig
    data = _read_prefs_json()  # 기존 구현 사용
    
    # --- normalize legacy prefs (keep backward compatibility) ---
    try:
        strat = (data or {}).get("strategy") or {}
        indicators = strat.get("indicators", None)

        # legacy: "rsi,bb,macd,ma" -> ["rsi","bb","macd","ma"]
        if isinstance(indicators, str):
            norm = [x.strip() for x in indicators.split(",") if x.strip()]
            strat["indicators"] = norm
            data["strategy"] = strat

        # legacy: None -> []
        if indicators is None:
            strat["indicators"] = strat.get("indicators") or []
            data["strategy"] = strat
            
        # normalize: indicator_logic 대문자 → 소문자
        indicator_logic = strat.get("indicator_logic", None)
        if isinstance(indicator_logic, str):
            strat["indicator_logic"] = indicator_logic.lower()
            data["strategy"] = strat
            
        # normalize: mode None 방지
        strategy_mode = strat.get("strategy_mode", None)
        if strategy_mode is None:
            strat["strategy_mode"] = "ai"
            data["strategy"] = strat
            
        # normalize: 레거시 order_amount 필드 정리 (strategy.order_amount -> strategy.single_order_amount)
        legacy_order_amount = strat.get("order_amount", None)
        if legacy_order_amount is not None:
            # 새로운 필드로 이관
            if strat.get("single_order_amount") is None:
                strat["single_order_amount"] = legacy_order_amount
            # 레거시 필드 삭제
            del strat["order_amount"]
            data["strategy"] = strat
            
        # normalize: 레거시 시장환경 필드 정리
        # volatility -> market_volatility, liquidity -> market_liquidity, session -> trading_session
        legacy_volatility = strat.get("volatility", None)
        if legacy_volatility is not None:
            if strat.get("market_volatility") is None:
                strat["market_volatility"] = legacy_volatility
            del strat["volatility"]
            data["strategy"] = strat
            
        legacy_liquidity = strat.get("liquidity", None)
        if legacy_liquidity is not None and strat.get("market_liquidity") is None:
            # ⚠️ legacy "liquidity"는 2가지 의미가 섞여 있을 수 있음
            #   (A) 시장환경(한글/설명형) → market_liquidity
            #   (B) 레짐(low/mid/high/ai) → StrategyConfig.liquidity(레짐)
            try:
                regime_vals = {"low", "mid", "high", "ai"}
                val = legacy_liquidity
                val_str = val.strip().lower() if isinstance(val, str) else ""
                is_regime = val_str in regime_vals

                # 한글/설명형(예: "높음", "보통", "유동성 높음")은 market_liquidity로 이관
                is_market_text = isinstance(val, str) and (("유동성" in val) or (val_str not in regime_vals))
                if (not is_regime) and is_market_text:
                    strat["market_liquidity"] = legacy_liquidity
                    # 레짐 키 오염 방지: 시장환경이었다면 legacy liquidity는 제거
                    del strat["liquidity"]
                    data["strategy"] = strat
            except Exception:
                # 실패 시에는 기존 값을 건드리지 않는다(로드 안전성)
                pass
            
        legacy_session = strat.get("session", None)
        if legacy_session is not None:
            if strat.get("trading_session") is None:
                strat["trading_session"] = legacy_session
            del strat["session"]
            data["strategy"] = strat
            
    except Exception:
        # never block loading due to normalization
        pass
    # --- /normalize ---
    
    settings = AppSettings(**(data or {}))
    
    # live_trade 로그 (루트) - throttled
    live_trade_loaded = bool(getattr(settings, "live_trade", False))
    from app.utils.logging_kmt import log_throttled, is_debug_mode
    if is_debug_mode():
        _log_info(f"[PREFS] live_trade loaded={live_trade_loaded} from root config")
    else:
        log_throttled(_log_info, "prefs_live_trade", f"[PREFS] live_trade loaded={live_trade_loaded} from root config", interval_sec=5)
    
    # P0-C: UI-STATE 로그 throttle (10초) - 로드 시에도 빈도 제한
    ui_state_keys = list(settings.ui_state.keys()) if hasattr(settings, 'ui_state') else 'NO_UI_STATE'
    if is_debug_mode():
        _log_info(f"[UI-STATE] keys={ui_state_keys}")
    else:
        log_throttled(_log_info, "ui_state_keys", f"[UI-STATE] keys={ui_state_keys}", interval_sec=10)
    
    # 병합: strategy 누락키 채우기 (타입을 StrategyConfig로 유지)
    base = StrategyConfig().model_dump()

    cur_raw = getattr(settings, "strategy", {}) or {}
    if hasattr(cur_raw, "model_dump"):
        cur = cur_raw.model_dump()
    elif isinstance(cur_raw, dict):
        cur = dict(cur_raw)
    else:
        cur = {}

    base.update(cur)

    # 마이그레이션: AI 추천 없을 때 기술지표 fallback → 자연 BUY 가능 (기존 저장값 False였으면 True로)
    if base.get("ai_fallback_enabled") is False:
        base["ai_fallback_enabled"] = True

    try:
        settings.strategy = StrategyConfig(**base)
    except Exception:
        # 최후 폴백: 최소한 dict라도 들어가게
        settings.strategy = base

    return settings

# === 전략 스냅샷 1줄 요약 생성기(실제 매매 reason/전략정보 표시용) ==========================
def _build_strategy_info_line_ssot(settings) -> str:
    """
    현재 settings 내 전략 파라미터를 1줄로 요약한다(SSOT: StrategyConfig).
    - 전략설정 탭의 '전략정보' 표시와 매매기록(reason)에 동일 문자열 사용
    - save_settings()가 이미 line1/line2를 만들고 있으므로, 포맷 호환 유지
    """
    try:
        # settings 는 AppSettings(pydantic) 또는 dict 일 수 있음 → dict 로 정규화
        if hasattr(settings, "model_dump"):
            payload = settings.model_dump()
        elif isinstance(settings, dict):
            payload = settings
        else:
            payload = getattr(settings, "__dict__", {}) or {}

        s = payload.get("strategy", {}) or {}
        inds = [i.upper() for i in (s.get("indicators") or [])]

        # line1과 line2 규칙은 save_settings()의 이벤트 포맷과 맞춘다
        def _safe(v, d=""):
            return v if (v is not None and v != "") else d

        # line1
        try:
            pos_pct = float(_safe(s.get("pos_size_pct", 2.5)))
            pos_pct_str = f"{pos_pct:.2f}%"
        except Exception:
            pos_pct_str = "—"

        line1 = (
            f"mode={_safe(s.get('strategy_mode','ai'))} · "
            f"aggr={_safe(s.get('aggressiveness_level',5))} · "
            f"pos={pos_pct_str} · "
            f"rr={_safe(s.get('rr_ratio',2.0))} · "
            f"cd={_safe(s.get('cooldown_sec',30))}s · "
            f"dll={float(_safe(s.get('daily_loss_limit_pct',3.0))):.2f}%"
        )

        # line2
        wl = s.get("whitelist") or []
        bl = s.get("blacklist") or []
        line2 = (
            f"inds={inds if inds else ['-']} · "
            f"combine={_safe(s.get('indicators_mode','and')).upper()} · "
            f"regime={_safe(s.get('vol_regime','ai'))} · liq={_safe(s.get('liquidity','ai'))} · "
            f"session={_safe(s.get('session','ai'))} · WL {len(wl)} / BL {len(bl)}"
        )

        # 1줄 결합 (전략정보 박스/거래 reason에서 동일 사용)
        return f"{line1} · {line2}"
    except Exception:
        # 실패 시라도 빈 문자열 대신 최소 안전값
        return "strategy=—"
# ===========================================================================================

def save_settings(settings):
    _ensure_inited()
    """
    strategy를 dict로 직렬화해 저장(호환성 유지) + 저장 직후 요약 이벤트 발행
    """
    try:
        import time
        payload = settings.model_dump() if hasattr(settings, "model_dump") else settings.__dict__

        # UI 섹션 보정(누락 키 기본값 채움)
        ui = payload.get("ui") or {}
        if hasattr(ui, "model_dump"):
            ui = ui.model_dump()

        # 자동로그인 / 세션 복원
        ui.setdefault("auto_login", False)
        ui.setdefault("restore_last_session", False)

        # 로그인 아이디 기억 기능
        ui.setdefault("saved_id", "")
        ui.setdefault("remember_id", False)

        payload["ui"] = ui
        
        # P0-C: UI 상태 저장 throttle (10초) - UI 상태가 포함된 경우에만 적용
        global _last_ui_state_save_time
        current_time = time.monotonic()
        ui_state = payload.get("ui_state") or {}
        has_ui_state = bool(ui_state)
        
        if has_ui_state and _last_ui_state_save_time > 0:
            elapsed = current_time - _last_ui_state_save_time
            if elapsed < 10.0:
                # UI 상태 저장은 throttle로 스킵 (로그 없음, 저장만 스킵)
                return True  # 저장 스킵
        
        if has_ui_state:
            _last_ui_state_save_time = current_time
            # P0-C: 저장 후에만 로그 1줄 출력
            ui_state_keys = list(ui_state.keys()) if ui_state else []
            _log_info(f"[UI-STATE] saved keys={ui_state_keys}")

        # strategy를 dict로 고정 직렬화
        stg = getattr(settings, "strategy", {}) or {}
        if hasattr(stg, "model_dump"):
            stg = stg.model_dump()
        
        # ✅ indicators를 항상 list[str]로 강제 변환 (Pydantic 경고 방지)
        indicators = stg.get("indicators", [])
        if isinstance(indicators, str):
            indicators = indicators.split(',') if indicators else []
        elif not isinstance(indicators, list):
            indicators = []
        stg["indicators"] = [str(i).strip() for i in indicators if i and str(i).strip()]
        
        payload["strategy"] = stg

        _resolved = _PREFS_FILE or "unknown"
        _exists = os.path.exists(_resolved) if _resolved != "unknown" else False
        try:
            _cwd = os.getcwd()
        except Exception:
            _cwd = "unknown"
        _log_info(f"[PREFS-PATH] resolved={_resolved} exists={_exists} cwd={_cwd}")
        ok = _write_prefs_json(payload)
        if not ok:
            raise RuntimeError("prefs.json 저장 실패")

        # ---- 저장 직후 UI 요약 갱신(버스 이벤트) ----
        try:
            from app.core import bus  # publish(topic, data)
            def _safe(v, d=""): 
                return v if (v is not None and v != "") else d
            s = payload.get("strategy", {}) or {}
            inds = [i.upper() for i in (s.get("indicators") or [])]
            line1 = (
                f"mode={_safe(s.get('strategy_mode','ai'))} · "
                f"aggr={_safe(s.get('aggressiveness_level',5))} · "
                f"pos={float(_safe(s.get('pos_size_pct',2.5))):.2f}% · "
                f"rr={_safe(s.get('rr_ratio',2.0))} · "
                f"cd={_safe(s.get('cooldown_sec',30))}s · "
                f"dll={float(_safe(s.get('daily_loss_limit_pct',3.0))):.2f}%"
            )
            wl = s.get("whitelist") or []
            bl = s.get("blacklist") or []
            line2 = (
                f"inds={inds if inds else ['-']} · "
                f"combine={_safe(s.get('indicators_mode','and')).upper()} · "
                f"regime={_safe(s.get('vol_regime','ai'))} · liq={_safe(s.get('liquidity','ai'))} · "
                f"session={_safe(s.get('session','ai'))} · WL {len(wl)} / BL {len(bl)}"
            )
            bus.publish("strategy_summary_updated", {"line1": line1, "line2": line2})
        except Exception:
            pass

        return True
    except Exception as e:
        _log_error(f"설정 저장 실패: {e}")
        return False

# strategy 내 GPT 키/모델: 공란으로 덮어쓸 수 있는 필드이지만, 기존 값이 있으면 빈 값으로 덮어쓰지 않음(LOCAL 저장 시 보존)
_USER_CLEARABLE_STRATEGY_KEYS = frozenset({"ai_openai_api_key", "ai_openai_model"})


def _deep_merge_dict(dst: dict, src: dict) -> dict:
    """
    dict 재귀 병합(merge):
    - src의 값이 dict이면 dst의 dict와 재귀 병합
    - 그 외 타입은 src로 overwrite
    - ai_openai_api_key / ai_openai_model: src가 빈 문자열이면 기존 dst가 비어있을 때만 빈 문자열로 설정.
      (기존에 값이 있으면 유지 → GPT→LOCAL 저장 시 GPT 키 삭제 방지)
    - 그 외 str: non-empty wins (src가 빈 문자열이면 dst 유지)
    """
    if dst is None:
        dst = {}
    if src is None:
        return dst
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            dst[k] = _deep_merge_dict(dst.get(k, {}), v)
        else:
            if isinstance(v, str) and v.strip() == "":
                if k in _USER_CLEARABLE_STRATEGY_KEYS:
                    # 기존 값이 있으면 빈 문자열로 덮어쓰지 않음 (LOCAL 저장 시 GPT 키 보존)
                    if isinstance(dst.get(k), str) and (dst.get(k) or "").strip() != "":
                        _log_info(f"[KEY-MERGE] key={k} src_empty -> keep dst non-empty (len={len((dst.get(k) or '').strip())})")
                        continue
                    dst[k] = ""
                elif isinstance(dst.get(k), str) and dst.get(k).strip() != "":
                    _log_info(f"[KEY-MERGE] key={k} src_empty -> keep dst non-empty (len={len(dst[k].strip())})")
                    continue
                else:
                    dst[k] = v
            else:
                dst[k] = v
    return dst

def save_settings_patch(patch: dict, base_settings=None):
    """
    ✅ 단일 저장소 고정(merge/patch):
    - 전체 덮어쓰기(save_settings) 대신, 필요한 섹션만 patch로 병합 후 저장한다.
    - base_settings가 있으면 그 값을 기준으로, 없으면 디스크(prefs.json) 기준으로 병합한다.
    - 반환: 병합/저장된 AppSettings
    """
    from .settings_schema import AppSettings
    try:
        if base_settings is not None:
            if hasattr(base_settings, "model_dump"):
                base_payload = base_settings.model_dump()
            else:
                base_payload = getattr(base_settings, "__dict__", {}) or {}
        else:
            base_payload = _read_prefs_json() or {}

        # LOCAL 저장 시: GPT 키/모델은 절대 삭제하지 않음. 디스크 → base_payload 순으로 채움.
        patch_copy = dict(patch or {})
        st = patch_copy.get("strategy") or {}
        if isinstance(st, dict) and (st.get("ai_provider") or "").strip().lower() == "local":
            disk_raw = _read_prefs_json() or {}
            base_st = (disk_raw.get("strategy") or {}) if isinstance(disk_raw.get("strategy"), dict) else {}
            base_st = dict(base_st) if base_st else {}
            base_from_memory = (base_payload.get("strategy") or {}) if isinstance(base_payload.get("strategy"), dict) else {}
            if isinstance(base_from_memory, dict):
                base_from_memory = dict(base_from_memory)
            else:
                base_from_memory = {}
            need_key = not (st.get("ai_openai_api_key") or "").strip()
            need_model = not (st.get("ai_openai_model") or "").strip()
            if need_key or need_model:
                st = dict(st)
                # 1) 디스크 base_st에서 채우고, 없으면 2) 메모리 base_payload에서 채움
                if need_key:
                    val = (base_st.get("ai_openai_api_key") or "").strip() or (base_from_memory.get("ai_openai_api_key") or "").strip()
                    if val:
                        st["ai_openai_api_key"] = val
                if need_model:
                    val = (base_st.get("ai_openai_model") or "").strip() or (base_from_memory.get("ai_openai_model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
                    if val:
                        st["ai_openai_model"] = val
                patch_copy["strategy"] = st
            # 병합 base: 디스크에 strategy가 있으면 디스크 기준(키 보존), 없으면 기존 base_payload 유지
            if base_st and isinstance(base_payload.get("strategy"), dict):
                base_payload = dict(base_payload)
                base_payload["strategy"] = dict(base_st)
                # 디스크 base에 키가 없었으면 메모리에서 채워 넣어서 덮어쓰기 방지
                for key in ("ai_openai_api_key", "ai_openai_model"):
                    if not (base_payload["strategy"].get(key) or "").strip() and (base_from_memory.get(key) or "").strip():
                        base_payload["strategy"][key] = (base_from_memory.get(key) or "").strip() or ("gpt-4o-mini" if key == "ai_openai_model" else "")

        merged = _deep_merge_dict(dict(base_payload), patch_copy)
        
        # ✅ live_trade 저장 로그 (루트)
        live_trade_saved = merged.get("live_trade", False)
        _log_info(f"[PREFS] live_trade saved={live_trade_saved} in root config")
        
        s_new = AppSettings(**merged)

        # 저장(기존 이벤트/암호화/직렬화 로직 재사용)
        ok = save_settings(s_new)
        if not ok:
            return None
        return s_new
    except Exception as e:
        _log_error(f"save_settings_patch 실패: {e}")
        return None


def build_strategy_snapshot_hash(strategy) -> str:
    """
    ✅ P3: Saved 전략 스냅샷 해시 생성기
    - 동일 전략은 항상 동일 해시를 보장
    - dict/pydantic 모델 모두 지원
    """
    import json
    import hashlib
    
    try:
        # dict 정규화
        if hasattr(strategy, 'model_dump'):
            strategy_dict = strategy.model_dump()
        elif hasattr(strategy, 'dict'):
            strategy_dict = strategy.dict()
        elif not isinstance(strategy, dict):
            strategy_dict = vars(strategy)
        else:
            strategy_dict = strategy
        
        # 포함 필드만 추출
        fields = [
            'strategy_mode', 'aggressiveness_level', 'pos_size_pct', 
            'rr_ratio', 'cooldown_sec', 'daily_loss_limit_pct',
            'indicators', 'whitelist', 'blacklist'
        ]
        
        filtered = {}
        for field in fields:
            if field in strategy_dict:
                filtered[field] = strategy_dict[field]
        
        # 정렬된 JSON 직렬화 → SHA256
        json_str = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
        hash_full = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        
        # 앞 8자리만 반환
        return hash_full[:8]
        
    except Exception:
        return "00000000"


