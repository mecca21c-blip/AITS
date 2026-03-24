from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ModuleDefinition:
    module_id: str
    module_name_ko: str
    category: str
    role: str
    description_ko: str
    short_description_ko: str = ""
    info_text_ko: str = ""
    recommended_for_ko: str = ""
    caution_text_ko: str = ""
    suitable_regimes: List[str] = field(default_factory=list)
    risk_profile: str = "medium"
    default_params: Dict[str, Any] = field(default_factory=dict)
    enabled_by_default: bool = True


@dataclass
class ModulePackDefinition:
    pack_id: str
    pack_name_ko: str
    description_ko: str
    short_description_ko: str = ""
    info_text_ko: str = ""
    recommended_for_ko: str = ""
    caution_text_ko: str = ""
    included_modules: List[str] = field(default_factory=list)
    preferred_modules: List[str] = field(default_factory=list)
    suppressed_modules: List[str] = field(default_factory=list)
    risk_bias_override: str = "none"
    asset_scope_override: str = "all"
    buy_bias_delta: float = 0.0
    wait_bias_delta: float = 0.0
    reduce_bias_delta: float = 0.0
    sell_bias_delta: float = 0.0
    exit_strictness_delta: float = 0.0
    suitable_regimes: List[str] = field(default_factory=list)
    enabled_by_default: bool = True


@dataclass
class UserModulePackSelection:
    active_pack_id: Optional[str] = None
    is_active: bool = False
    timer_enabled: bool = False
    duration_minutes: int = 0
    remaining_seconds: int = 0
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    auto_revert_to_ai_default: bool = True
    manual_deactivation_allowed: bool = True
    selection_reason: str = ""
    status_text_ko: str = "AI 기본 모드"

    def has_active_timer(self) -> bool:
        return self.is_active and self.timer_enabled and self.remaining_seconds > 0

    def is_expired(self) -> bool:
        return self.timer_enabled and self.remaining_seconds <= 0

    def is_ai_default_mode(self) -> bool:
        return (not self.is_active) or (not self.active_pack_id)

    def summary_text_ko(self) -> str:
        if self.is_ai_default_mode():
            return "AI 기본 모드"
        if self.timer_enabled:
            return f"모듈팩 활성: {self.active_pack_id} / 남은 시간 {self.remaining_seconds}초"
        return f"모듈팩 활성: {self.active_pack_id} / 무기한"


@dataclass
class ModulePackRuntimeState:
    active_pack_id: Optional[str] = None
    pack_name_ko: str = "AI 기본 모드"
    effective_preferred_modules: List[str] = field(default_factory=list)
    effective_suppressed_modules: List[str] = field(default_factory=list)
    effective_risk_bias: str = "none"
    effective_asset_scope: str = "all"
    effective_buy_bias_delta: float = 0.0
    effective_wait_bias_delta: float = 0.0
    effective_reduce_bias_delta: float = 0.0
    effective_sell_bias_delta: float = 0.0
    effective_exit_strictness_delta: float = 0.0
    timer_enabled: bool = False
    remaining_seconds: int = 0
    expired: bool = False
    runtime_summary_ko: str = "AI 기본 모드로 동작 중입니다."


DEFAULT_MODULE_DEFINITIONS: List[ModuleDefinition] = [
    ModuleDefinition(
        module_id="volatility_breakout",
        module_name_ko="변동성 돌파",
        category="entry",
        role="추세 시작 구간 진입",
        description_ko="변동성 확대 구간에서 가격 돌파를 감지해 추세 초입 진입을 시도합니다.",
        short_description_ko="변동성 확대 시 돌파 진입",
        info_text_ko="박스권 상단 돌파와 변동성 증가를 함께 확인해 허위 신호를 줄이는 방식입니다.",
        recommended_for_ko="강세장 초입이나 추세 전환이 강하게 나타나는 시점에 적합합니다.",
        caution_text_ko="횡보장에서 잦은 가짜 돌파가 발생할 수 있어 손절 기준을 엄격히 두어야 합니다.",
        suitable_regimes=["bull", "sideways"],
        risk_profile="high",
        default_params={"lookback": 20, "breakout_threshold": 1.2, "confirm_volume": True},
    ),
    ModuleDefinition(
        module_id="rsi_bollinger_reversal",
        module_name_ko="RSI + 볼린저 역추세",
        category="entry",
        role="과매수·과매도 반전 진입",
        description_ko="RSI와 볼린저 밴드를 결합해 과도한 치우침 이후 되돌림 진입을 노립니다.",
        short_description_ko="과열 구간 반전 포착",
        info_text_ko="RSI 극단값과 밴드 이탈 후 재진입 조건을 함께 확인해 반전 가능성을 높입니다.",
        recommended_for_ko="횡보장이나 단기 과열 이후 평균회귀가 자주 나타나는 구간에 적합합니다.",
        caution_text_ko="강한 추세장에서는 역추세 진입이 연속 손실로 이어질 수 있어 비중을 줄여야 합니다.",
        suitable_regimes=["sideways"],
        risk_profile="medium",
        default_params={"rsi_period": 14, "rsi_low": 30, "rsi_high": 70, "bb_period": 20},
    ),
    ModuleDefinition(
        module_id="ma_cross",
        module_name_ko="이동평균선 크로스",
        category="trend",
        role="중기 추세 추종",
        description_ko="단기·중기 이동평균선 교차를 기반으로 방향 전환과 추세 지속을 판단합니다.",
        short_description_ko="평균선 교차 추세 판단",
        info_text_ko="골든크로스·데드크로스를 핵심 신호로 사용하며 추가 필터로 노이즈를 줄입니다.",
        recommended_for_ko="완만한 상승·하락 추세가 이어지는 장세에 적합합니다.",
        caution_text_ko="급변 구간에서는 신호가 늦게 발생할 수 있어 진입 타이밍이 불리할 수 있습니다.",
        suitable_regimes=["bull", "bear", "sideways"],
        risk_profile="medium",
        default_params={"fast_period": 20, "slow_period": 60, "confirm_bars": 2},
    ),
    ModuleDefinition(
        module_id="macd_trend_strength",
        module_name_ko="MACD 추세 강도",
        category="trend",
        role="추세 강도 필터링",
        description_ko="MACD 라인과 시그널의 거리, 히스토그램 변화를 이용해 추세 강도를 평가합니다.",
        short_description_ko="MACD 기반 추세 강도 확인",
        info_text_ko="단순 교차보다 모멘텀 확장 여부를 함께 반영해 신호 신뢰도를 높입니다.",
        recommended_for_ko="추세 추종 전략에서 진입 신호의 품질을 높이고 싶을 때 적합합니다.",
        caution_text_ko="저변동 횡보 구간에서는 유의미한 강도 차이가 작아 과해석 위험이 있습니다.",
        suitable_regimes=["bull", "bear"],
        risk_profile="medium",
        default_params={"fast": 12, "slow": 26, "signal": 9, "strength_threshold": 0.0},
    ),
    ModuleDefinition(
        module_id="vwap_volume_trend",
        module_name_ko="거래량 반영 평균가(VWAP)",
        category="confirmation",
        role="거래량 기반 추세 확인",
        description_ko="VWAP 대비 가격 위치와 거래량 변화를 함께 보며 추세 신호를 보강합니다.",
        short_description_ko="VWAP과 거래량으로 추세 확인",
        info_text_ko="기관 평균 체결가 개념을 활용해 가격이 유리한 방향인지 확인하는 보조 모듈입니다.",
        recommended_for_ko="거래량이 충분한 메이저 자산에서 신호 품질을 높이고자 할 때 적합합니다.",
        caution_text_ko="거래량이 적은 자산에서는 VWAP 의미가 약해져 필터 성능이 저하될 수 있습니다.",
        suitable_regimes=["bull", "sideways", "bear"],
        risk_profile="low",
        default_params={"session": "day", "volume_spike_ratio": 1.5},
    ),
    ModuleDefinition(
        module_id="trailing_stop_exit",
        module_name_ko="트레일링 스톱 & 손절",
        category="exit",
        role="수익 보호와 손실 제한을 위한 청산 모듈",
        description_ko="가격 상승 시 손절선을 따라 올리고, 하락 시 손실을 제한하도록 자동 청산 기준을 제공합니다.",
        short_description_ko="수익 보호·손실 제한 청산",
        info_text_ko="변동성 기반 추적 손절과 고정 손절을 함께 사용해 급락 위험을 완화합니다.",
        recommended_for_ko="모든 장세에서 리스크 관리를 우선하고 싶은 운용에 적합합니다.",
        caution_text_ko="손절 폭이 지나치게 좁으면 정상 변동에도 조기 청산이 반복될 수 있습니다.",
        suitable_regimes=["bull", "sideways", "bear"],
        risk_profile="low",
        default_params={"trailing_pct": 3.0, "hard_stop_pct": 5.0, "take_profit_pct": 12.0},
    ),
]


DEFAULT_MODULE_PACK_DEFINITIONS: List[ModulePackDefinition] = [
    ModulePackDefinition(
        pack_id="ai_default",
        pack_name_ko="AI 기본 모드",
        description_ko="AI가 전체 모듈을 유연하게 조합해 장세에 맞춰 판단하는 기본 운용 모드입니다.",
        short_description_ko="기본 자동 판단 모드",
        info_text_ko="특정 모듈 편향 없이 시장 상태와 포트폴리오 맥락을 함께 고려합니다.",
        recommended_for_ko="별도 선호가 없거나 초기 운영 단계에서 기본값으로 사용하기 좋습니다.",
        caution_text_ko="시장 급변 시에는 사용자 제약과 리스크 설정을 함께 점검하는 것이 안전합니다.",
        included_modules=[],
        preferred_modules=[],
        suppressed_modules=[],
        risk_bias_override="none",
        asset_scope_override="all",
        buy_bias_delta=0.0,
        wait_bias_delta=0.0,
        reduce_bias_delta=0.0,
        sell_bias_delta=0.0,
        exit_strictness_delta=0.0,
        suitable_regimes=["bull", "sideways", "bear"],
    ),
    ModulePackDefinition(
        pack_id="trend_pack",
        pack_name_ko="추세 추종 팩",
        description_ko="추세 지속 구간에서 진입·보유를 강화하고 역추세 신호 비중을 낮춘 팩입니다.",
        short_description_ko="추세 중심 운용",
        info_text_ko="이동평균선과 MACD 기반 추세 강도 신호를 우선 반영하도록 구성됩니다.",
        recommended_for_ko="강세장 또는 방향성이 분명한 하락 추세 대응에 적합합니다.",
        caution_text_ko="횡보장에서는 신호 품질이 저하될 수 있어 대기 비중을 함께 관리해야 합니다.",
        included_modules=["ma_cross", "macd_trend_strength", "trailing_stop_exit"],
        preferred_modules=["ma_cross", "macd_trend_strength"],
        suppressed_modules=["rsi_bollinger_reversal"],
        risk_bias_override="offensive",
        asset_scope_override="all",
        buy_bias_delta=0.20,
        wait_bias_delta=-0.10,
        reduce_bias_delta=-0.05,
        sell_bias_delta=-0.05,
        exit_strictness_delta=0.10,
        suitable_regimes=["bull", "bear"],
    ),
    ModulePackDefinition(
        pack_id="reversal_pack",
        pack_name_ko="횡보 반등 팩",
        description_ko="과매도·과매수 반전 신호를 중심으로 짧은 구간 회복을 노리는 팩입니다.",
        short_description_ko="평균회귀 중심 운용",
        info_text_ko="RSI와 볼린저 밴드 기반 반전 조건을 우선 반영해 보수적으로 접근합니다.",
        recommended_for_ko="방향성이 약한 횡보장이나 단기 과열/과매도 구간에 적합합니다.",
        caution_text_ko="강한 추세장에서는 역추세 손실이 커질 수 있어 진입 강도를 낮춰야 합니다.",
        included_modules=["rsi_bollinger_reversal", "trailing_stop_exit"],
        preferred_modules=["rsi_bollinger_reversal"],
        suppressed_modules=["volatility_breakout", "macd_trend_strength"],
        risk_bias_override="neutral",
        asset_scope_override="major_only",
        buy_bias_delta=0.05,
        wait_bias_delta=0.10,
        reduce_bias_delta=0.05,
        sell_bias_delta=0.00,
        exit_strictness_delta=0.15,
        suitable_regimes=["sideways"],
    ),
    ModulePackDefinition(
        pack_id="defensive_pack",
        pack_name_ko="방어형 팩",
        description_ko="현금 방어와 손실 제한을 우선해 변동성 확대 구간을 보수적으로 대응하는 팩입니다.",
        short_description_ko="방어 우선 운용",
        info_text_ko="청산·리스크 관리 모듈 비중을 높이고 공격적 진입 모듈 비중을 낮춥니다.",
        recommended_for_ko="약세장 또는 장세 신뢰도가 낮아 보수적 대응이 필요한 구간에 적합합니다.",
        caution_text_ko="강한 상승 초입에서는 기회비용이 발생할 수 있어 해제 타이밍 점검이 필요합니다.",
        included_modules=["ma_cross", "trailing_stop_exit"],
        preferred_modules=["trailing_stop_exit"],
        suppressed_modules=["volatility_breakout"],
        risk_bias_override="defensive",
        asset_scope_override="major_only",
        buy_bias_delta=-0.25,
        wait_bias_delta=0.20,
        reduce_bias_delta=0.15,
        sell_bias_delta=0.10,
        exit_strictness_delta=0.25,
        suitable_regimes=["bear", "sideways"],
    ),
    ModulePackDefinition(
        pack_id="volume_pack",
        pack_name_ko="거래량/VWAP 팩",
        description_ko="거래량과 VWAP 기반 확인 신호를 강화해 체결 품질과 추세 신뢰도를 높이는 팩입니다.",
        short_description_ko="거래량 확인 강화 운용",
        info_text_ko="VWAP 괴리와 거래량 급증 여부를 함께 반영해 무리한 추격 진입을 줄입니다.",
        recommended_for_ko="유동성이 높은 시장에서 신호 검증 단계를 강화하고 싶을 때 적합합니다.",
        caution_text_ko="저유동성 자산에서는 거래량 왜곡으로 신호가 불안정할 수 있습니다.",
        included_modules=["vwap_volume_trend", "ma_cross", "trailing_stop_exit"],
        preferred_modules=["vwap_volume_trend"],
        suppressed_modules=["rsi_bollinger_reversal"],
        risk_bias_override="neutral",
        asset_scope_override="major_only",
        buy_bias_delta=0.10,
        wait_bias_delta=0.05,
        reduce_bias_delta=0.05,
        sell_bias_delta=0.00,
        exit_strictness_delta=0.10,
        suitable_regimes=["bull", "sideways"],
    ),
]


DEFAULT_USER_MODULE_PACK_SELECTION = UserModulePackSelection(
    active_pack_id=None,
    is_active=False,
    timer_enabled=False,
    duration_minutes=0,
    remaining_seconds=0,
    activated_at=None,
    expires_at=None,
    auto_revert_to_ai_default=True,
    manual_deactivation_allowed=True,
    selection_reason="",
    status_text_ko="AI 기본 모드",
)
