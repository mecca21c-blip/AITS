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


class RuntimeResourceConfig(BaseModel):
    """Stable deployment defaults for laptops and integrated graphics."""

    low_resource_mode_enabled: bool = True
    ultra_safe_startup_enabled: bool = True
    chart_render_on_startup: bool = False
    disable_chart_rendering_in_low_resource: bool = True
    chart_render_manual_only: bool = True
    chart_refresh_min_interval_sec: float = 20.0
    candle_chart_initial_delay_sec: float = 60.0
    chart_render_after_on_stable_sec: float = 60.0
    max_chart_candles: int = 80
    enable_chart_subplots_in_low_resource: bool = False
    ui_log_max_lines: int = 500
    ui_log_flush_interval_sec: float = 2.0
    table_refresh_min_interval_sec: float = 5.0
    status_refresh_min_interval_sec: float = 1.5
    market_refresh_batch_size: int = 10
    indicator_compute_batch_size: int = 4
    startup_stage_delay_ms: int = 300
    ai_startup_delay_sec: float = 15.0
    scheduler_startup_delay_sec: float = 20.0
    resource_health_interval_sec: float = 30.0
    learning_pipeline_auto_run_enabled: bool = False
    local_model_training_auto_run_on_live: bool = False
    calibration_auto_run_on_live: bool = False
    curation_auto_run_on_live: bool = False
    feature_pipeline_auto_run_on_live: bool = False
    on_startup_total_timeout_sec: float = 30.0
    on_startup_stage_timeout_sec: float = 10.0
    on_click_fast_return_warning_ms: int = 300


class DataGovernancePolicyConfig(BaseModel):
    """Single settings SSOT for retention, archive, backup, and recovery."""

    policy_version: int = 1
    enabled: bool = True
    last_updated_at: str = ""
    last_updated_by: str = "system_default"
    total_data_limit_mb: int = 10_240
    warning_threshold_pct: int = 80
    critical_threshold_pct: int = 95
    minimum_free_disk_mb: int = 2_048
    behavior_on_warning: str = "notify_and_plan_archive"
    behavior_on_critical: str = "block_noncritical_heavy_work"
    source_auto_delete_enabled: bool = False
    source_archive_enabled: bool = True
    source_archive_after_days: int = 90
    source_archive_chunk_policy: str = "monthly"
    source_permanent_delete_requires_backup: bool = True
    source_permanent_delete_requires_explicit_confirmation: bool = True
    derived_retention_days: int = 365
    derived_rebuild_allowed: bool = True
    derived_auto_prune_enabled: bool = False
    derived_prune_requires_offline: bool = True
    summary_retention_days: int = 730
    log_retention_days: int = 30
    log_max_total_mb: int = 512
    keep_latest_failure_logs: bool = True
    pinned_log_protection: bool = True
    runtime_report_keep_count: int = 30
    runtime_failure_report_keep_count: int = 20
    keep_champion: bool = True
    keep_previous_champion: bool = True
    keep_active_challenger: bool = True
    keep_usable_model_count: int = 5
    keep_failed_attempt_metadata: bool = True
    unused_model_retention_days: int = 180
    backup_enabled: bool = True
    backup_directory: str = "data/backups"
    essential_backup_keep_count: int = 5
    learning_backup_keep_count: int = 3
    full_backup_keep_count: int = 2
    backup_compression: str = "zip_deflated"
    backup_encryption_supported: bool = False
    secret_exclusion_required: bool = True
    archived_source_training_enabled: bool = True
    historical_replay_enabled: bool = True
    training_date_range: Dict[str, str] = Field(default_factory=dict)
    excluded_dataset_ids: List[str] = Field(default_factory=list)
    included_dataset_ids: List[str] = Field(default_factory=list)
    user_training_overrides: Dict[str, Any] = Field(default_factory=dict)
    minimum_review_reliability: str = "medium"
    heavy_governance_operations_off_only: bool = True
    allow_manual_archive: bool = True
    allow_manual_backup: bool = True
    allow_manual_restore: bool = True
    allow_derived_regeneration: bool = True
    allow_derived_reset: bool = True
    allow_full_reset: bool = False


class ReleaseOperationsConfig(BaseModel):
    release_channel: str = "release_candidate"
    low_resource_release_profile: bool = True
    automatic_network_update_enabled: bool = False
    update_requires_user_approval: bool = True
    update_requires_offline: bool = True
    preserve_user_data_on_uninstall: bool = True
    support_bundle_secret_exclusion: bool = True
    optional_backup_encryption_enabled: bool = False

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
    per_order_hard_cap_krw: int = 12_000  # live one-shot per-order hard cap
    total_guarded_window_cap_krw: int = 20_000  # guarded-window total cap
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
    ai_provider: str = "local"  # openai | gemini | local/basic
    ai_openai_api_key: str = ""
    ai_gemini_api_key: str = ""
    ai_openai_model: str = "gpt-4o-mini"
    ai_gemini_model: str = "gemini-2.5-flash"
    ai_local_url: str = "http://127.0.0.1:11434"   # Ollama base URL (provider=local)
    ai_local_model: str = "qwen2.5"               # Ollama model: llama3.1 | qwen2.5 | mistral
    ai_local_confidence_threshold: float = 0.72
    local_ollama_developer_only: bool = True
    local_ollama_auto_generate_enabled: bool = False
    local_ollama_auto_generate_on_live_enabled: bool = False
    ai_external_request_cooldown_seconds: int = 15
    ai_external_duplicate_payload_cooldown_seconds: int = 600
    ai_external_max_calls_per_hour: int = 60
    ai_external_max_calls_per_day: int = 500
    ai_external_max_live_order_calls_per_hour: int = 20
    ai_external_max_tokens_estimate_per_call: int = 1200
    ai_external_daily_estimated_cost_limit: float = 5.0
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
    runtime_resource: RuntimeResourceConfig = RuntimeResourceConfig()
    data_governance_policy: DataGovernancePolicyConfig = DataGovernancePolicyConfig()
    release_operations: ReleaseOperationsConfig = ReleaseOperationsConfig()
    # [위험 지점] AppSettings() 인자 없이 생성 시 strategy가 기본 인스턴스 → ai_provider=local. docs/P0_AI_PROVIDER_SSOT_DESIGN_AND_PATCH.md
    strategy: StrategyConfig = StrategyConfig()
    trade: TradeConfig = TradeConfig()
