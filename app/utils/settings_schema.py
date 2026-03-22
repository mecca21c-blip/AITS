from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any

class UpbitConfig(BaseModel):
    access_key: str = ""
    secret_key: str = ""

class PollConfig(BaseModel):
    ticker_ms: int = 1500
    topN_refresh_min: int = 30

class UIConfig(BaseModel):
    # 프로그램 로그인/세션 관련 UI 설정
    auto_login: bool = False             # 자동 로그인 사용 여부 (기본: 로그인창 표시)
    restore_last_session: bool = True    # 마지막 세션 복원 여부

    # 로그인 아이디 기억 관련
    saved_id: str = ""                   # 저장된 로그인 아이디(이메일 등)
    remember_id: bool = False            # 아이디 저장 체크 여부

# ---- Strategy schema (defaults only; UI validates ranges) ----
# 사용자 노출: aggressiveness(3단계), order_amount_krw, allow_downscale_order_amount, whitelist, blacklist
# 내부 전용: aggressiveness_level, pos_size_pct, rr_ratio 등 → aggressiveness 프리셋으로 설정
class StrategyConfig(BaseModel):
    # 사용자 선택: 보수적(1) / 중립(5) / 공격적(10) → UI는 3단계만 노출
    aggressiveness: str = "neutral"  # conservative | neutral | aggressive
    aggressiveness_level: int = 5
    strategy_mode: str = "ai"  # avoid|trend_following|ai

    indicators: list[str] = ["bbands", "rsi", "macd"]
    indicators_mode: str = "and"  # and|or|weighted|ai
    indicators_weights: dict[str, float] = {}
    indicators_threshold: float = 0.5  # weighted/ai 임계값 기본
    
    # ✅ 추가: AI 판단 우선 및 논리
    ai_judge_priority: bool = False
    ai_fallback_enabled: bool = True   # AI 추천 없을 때 기술지표(trend_following) fallback → 자연 BUY 가능
    indicator_logic: str = "AND"  # AND|OR

    # ▶ Watchlist 연동: 화이트/블랙
    whitelist: list[str] = []  # ["KRW-BTC", ...]
    blacklist: list[str] = []

    vol_regime: str = "ai"      # low|mid|high|ai
    liquidity: str = "ai"       # low|mid|high|ai
    session: str = "ai"         # asia|europe|us|ai
    
    # ✅ 추가: 시장 환경 필드
    market_volatility: str = "중간 변동성"
    market_liquidity: str = "중간 유동성"
    trading_session: str = "전일"

    pos_size_pct: float = 2.5  # 1종목 최대 투자 비중 (%) - percent 단위로 통일
    rr_ratio: float = 2.0
    daily_loss_limit_pct: float = 3.0
    
    # ✅ 추가: 자금 관리 필드
    max_investment: int = 1_000_000  # 최대투자금
    single_order_amount: int = 100_000  # 1회 주문금액
    order_amount_krw: int = 10000  # 1회 주문금액 (SSOT)
    order_amount_pct: float = 0.2  # 주문 비율 (SSOT)
    allow_downscale_order_amount: bool = False  # 잔고/한도 부족 시 주문금액 자동 축소 허용(최소 5,000원)
    max_invest_cap_krw: int = 0  # 최대 투자금액(상한): 보유 코인 평가합계+이번 주문이 이 금액 초과 시 매수 차단. 0=제한 없음
    
    # 🔷 로테이션 A안: 매도-only, 스코어 기반 (enabled, interval_min, count, min_score_gap)
    rotation: Dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "interval_min": 30, "count": 1, "min_score_gap": 0.05})
    
    # ✅ 추가: 손실/익절 필드
    # 0.0 = AI controls (no fixed TP/SL trigger)
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    exit_mode: str = "ai"  # ai | user | trail (runner: UI 우선, 없으면 여기, 없으면 ai)

    limit_loss_seq_on: bool = False
    limit_loss_seq: int = 3
    limit_win_seq_on: bool = False
    limit_win_seq: int = 5
    cooldown_on: bool = True
    cooldown_sec: int = 30

    # ✅ PATCH: THR 완화 옵션 (기본값 OFF로 기존 동작 유지)
    thr_relax_enabled: bool = False
    thr_relax_pct: float = 1.0
    thr_chase_cap_pct: float = 10.0

    # ✅ 추가: 외부 조건 필드
    macro_news_enabled: bool = False
    exchange_check_enabled: bool = True
    mtf_mix_enabled: bool = False
    cross_asset_enabled: bool = False

    block_on_macro_news: bool = False
    block_on_exchange_events: bool = True
    mtf_mix_on: bool = False
    cross_asset_filter_on: bool = False

    ai_autofill_enabled: bool = False
    daily_reco_schedule: str = "09:00,21:00"
    
    # AI Provider Configuration
    # [위험 지점] 기본값 "local". strategy를 인자 없이 StrategyConfig()로 교체하는 코드 경로에서 이 값으로 덮어쓰여 GPT→LOCAL로 돌아감. 위험 지점 목록: docs/P0_AI_PROVIDER_SSOT_DESIGN_AND_PATCH.md
    ai_provider: str = "local"  # gpt | local | off
    ai_openai_api_key: str = ""
    ai_openai_model: str = "gpt-4o-mini"
    ai_local_url: str = "http://127.0.0.1:11434"   # Ollama base URL (provider=local)
    ai_local_model: str = "qwen2.5"               # Ollama model: llama3.1 | qwen2.5 | mistral
    ai_reco_ttl_sec: int = 60
    ai_fallback_to_local: bool = True

# [ANCHOR: STRATEGY_SETTINGS_START]
# 아래 필드가 없다면 추가 (단일 strategy_id 운용)
class StrategySettings(BaseModel):
    """
    ⚠️ DEPRECATED (하위호환 전용)
    - SSOT는 StrategyConfig(strategy)이다.
    - 이 클래스는 과거 prefs.json/구버전 설정 로드를 위한 '읽기 호환'만 유지한다.
    - 신규 필드 추가/저장/실행 주입은 StrategyConfig에만 한다.
    """
    strategy_id: str = "default"            # 단일 값 운용
    order_amount_krw: int = 6000            # 1회 주문금액 (전략 소속)
    tp_pct: float = 10.0                    # 익절%
    sl_pct: float = 5.0                     # 손절%
    # rr_ratio 제거 - StrategyConfig.rr_ratio 사용
    exit_mode: str = "PARTIAL_TRAIL"        # TP_SL | TRAIL | PARTIAL_TRAIL | PROFIT_VOLUME
    universe_topn: int = 30                 # 상위 N
    universe_window_min: int = 5            # 경신 기준 분
    use_ai_env: bool = True                 # 시황 변수(AI) 사용 여부
# [ANCHOR: STRATEGY_SETTINGS_END]

# === [PATCH S-1] begin: TradeConfig 추가 ===
class TradeConfig(BaseModel):
    safety_buffer_krw: float = 1000.0   # 가용현금에서 항상 빼는 보수적 버퍼
    fee_rate: float = 0.0005            # 0.05%
    slippage: float = 0.001             # 0.10%
# === [PATCH S-1] end ===

# --- 교체: AppSettings 클래스 본문에 한 줄 추가 ---
class AppSettings(BaseModel):
    symbols: List[str] = ["KRW-BTC","KRW-ETH","KRW-XRP"]
    # P0-A: 워치리스트 복원용 — watchlist_symbols가 있으면 symbols보다 우선 사용
    watchlist_symbols: List[str] = []
    auto_top20: bool = True
    max_total_krw: int = 50_000
    order_amount_krw: int = 5_000
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 3.0
    live_trade: bool = False  # ✅ 단일 진실 경로: 루트로 이동
    
    # ✅ P0-UI-WATCHLIST-PERSIST-UISTATE: UI 상태 저장 필드
    ui_state: Dict[str, Any] = Field(default_factory=dict)

    # ▶ 스캔/쿨다운(전역) 기본값
    scan_limit: int = 30
    buy_cooldown_sec: int = 60
    sell_cooldown_sec: int = 10

    upbit: UpbitConfig = UpbitConfig()
    poll: PollConfig = PollConfig()
    ui: UIConfig = UIConfig()
    # [위험 지점] AppSettings() 인자 없이 생성 시 strategy가 기본 인스턴스 → ai_provider=local. docs/P0_AI_PROVIDER_SSOT_DESIGN_AND_PATCH.md
    strategy: StrategyConfig = StrategyConfig()
    trade: TradeConfig = TradeConfig()