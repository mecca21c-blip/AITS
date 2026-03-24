from __future__ import annotations
import logging
from typing import Optional

# eventbus 임포트 추가
import app.core.bus as eventbus

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QSpinBox, QSizePolicy, QTextEdit, QVBoxLayout, QWidget, QDoubleSpinBox,
    QListWidget, QRadioButton, QButtonGroup, QMessageBox, QToolButton, QDialog, QSplitter
)
from PySide6.QtCore import Qt, QTimer, QSettings

# 도움말 텍스트 정의
HELP_TEXTS = {
    "전략 요약": """
전략 요약은 현재 설정된 모든 매매 전략을 한눈에 보여주는 기능입니다.

【무엇인가요?】
현재 설정된 모든 매매 전략 파라미터를 실시간으로 요약하여 보여주는 대시보드입니다.

【오늘 어떻게 사용하나요?】
1. AI 추천 시스템으로 최적 전략을 받습니다
2. 매매 적극성 슬라이더로 오늘의 성향을 조정합니다
3. 전략 요약창에서 모든 설정이 올바르게 반영되었는지 확인합니다
4. 설정이 만족스러우면 '전략 저장' 버튼으로 저장합니다

【주의사항/팁】
• 전략 요약은 실시간으로 업데이트되므로 설정 변경 즉시 확인 가능합니다
• 손익비와 리스크 관리 수치가 적절한지 반드시 확인하세요
• AI 추천과 내 설정이 다를 경우, 전략 요약을 통해 차이점을 파악할 수 있습니다
• 복잡한 설정도 한눈에 파악하여 실수를 방지할 수 있습니다
""",
    "기술적 지표": """
기술적 지표는 차트 패턴과 수학적 지표를 활용하여 매매 신호를 생성하는 기능입니다.

【무엇인가요?】
RSI, 볼린저밴드, MACD 등 다양한 기술적 지표를 조합하여 매매 진입/청산 시점을 판단하는 시스템입니다.

【오늘 어떻게 사용하나요?】
1. 사용할 지표를 체크하여 조합합니다 (AND/OR 논리 선택)
2. AI 판단 우선 옵션으로 AI 분석을 가중시킬 수 있습니다
3. 논리 목록에서 지표별 조건을 세부적으로 설정합니다
4. 전략 요약에서 지표 조합이 올바르게 반영되었는지 확인합니다

【주의사항/팁】
• 지표가 너무 많으면 신호가 희소해지고, 너무 적으면 잦은 매매가 발생할 수 있습니다
• 과최적화를 피하기 위해 주요 지표 2-3개 조합을 권장합니다
• AI 판단 우선 시에는 AI 분석이 지표 신호보다 우선 적용됩니다
• 시장 상황에 따라 지표 효과가 달라질 수 있으니 주기적인 재검토가 필요합니다

【지표별 설명】
• RSI: 상대강도지수로, 70 이상이면 과매수, 30 이하이면 과매도 상태를 의미합니다
• 볼린저밴드: 변동성 기반 밴드로, 가격이 상단 밴드를 이탈하면 강세, 하단을 이탈하면 약세 신호입니다
• MACD: 추세 전환 지표로, 시그널선과의 교차에서 매매 신호가 발생합니다
• 이평선: 주가 평균으로, 단기/장기 이평선 교차에서 추세 변화를 판단합니다
• ATR: 평균 진폭으로, 시장의 변동성 크기를 나타내는 지표입니다
• Stochastic: 모멘텀 지표로, 80 이상 과매수, 20 이하 과매도 구간을 나타냅니다

【논리 옵션】
• 현재는 AND/OR 논리만 지원됩니다. AND는 모든 조건 충족 시, OR는 하나의 조건만 충족해도 신호가 발생합니다
""",
    "AI 추천 시스템": """
AI 추천 시스템은 현재 시장 상황을 분석하여 최적의 전략을 추천하는 기능입니다.

【무엇인가요?】
실시간 시장 데이터를 분석하여 현재 상황에 가장 적합한 매매 전략을 자동으로 제안하는 시스템입니다.

【오늘 어떻게 사용하나요?】
1. 'AI 추천 새로고침' 버튼을 클릭하여 최신 시장 분석을 받습니다
2. AI가 제안한 전략 내용과 근거를 확인합니다
3. 'AI 추천 적용하기' 버튼으로 제안된 설정을 한 번에 적용합니다
4. 전략 요약에서 AI 추천이 올바르게 반영되었는지 확인합니다

【주의사항/팁】
• AI 추천은 현재 시장 상황을 기반으로 하므로 실시간 업데이트가 중요합니다
• 추천된 전략은 참고용이며, 투자자의 성향에 맞게 조정할 수 있습니다
• 시장 변동이 크거나 특수한 상황에서는 AI 추천을 여러 번 확인하세요
• AI 추천과 내 판단이 다를 경우, 전략 요약을 통해 비교 분석 후 결정하세요
""",
    "매매 적극성": """
매매 적극성은 오늘의 매매 성향을 한 번에 조정하는 핵심 컨트롤입니다.

【무엇인가요?】
1-10단계 슬라이더로 오늘의 매매 공격성을 설정하고, 관련된 모든 리스크 관리 항목을 자동으로 조정하는 통합 컨트롤입니다.

【오늘 어떻게 사용하나요?】
1. 슬라이더를 움직여 오늘의 매매 성향을 결정합니다 (1=보수적, 10=공격적)
2. 연동된 리스크 관리 항목들이 자동으로 조정되는 것을 확인합니다
3. 전략 요약에서 전체적인 설정 균형을 확인합니다
4. 만족스러운 설정이면 '전략 저장'으로 저장합니다

【주의사항/팁】
• 슬라이더 조정 시 포지션 비중, 손익비, 쿨다운, 일손실제한이 함께 변경됩니다
• 초보자는 3-5단계로 시작하여 점진적으로 높이는 것을 권장합니다
• 시장 변동성이 클 때는 낮은 단계, 안정적일 때는 높은 단계를 고려하세요
• 개인 투자 성향과 시장 상황을 고려하여 최적의 지점을 찾으세요

■ 포지션 비중(중요)
- '포지션 비중'은 한 종목에 내 전체 자산 중 최대 얼마까지 투입할지를 의미합니다.
  예) 총자산 1,000,000원, 포지션 비중 2.5% → 1종목 최대 25,000원까지만 매수
  예) 총자산 1,000,000원, 포지션 비중 25%  → 1종목 최대 250,000원까지 매수
- 자동매매 안정성을 위해 '분산 투자'를 원하면 2.5%~5% 범위를 권장합니다.
- 화면마다 숫자가 다르게 보이면(2.5% vs 25%) 단위(비율/퍼센트) 혼재 오류일 수 있으니, 표시/저장 단위를 통일합니다.
""",
    "전략 모드": """
전략 모드는 매매의 기본적인 접근 방식을 결정하는 설정입니다.

• 추세 추종: 주가의 추세 방향에 따라 매매하는 전략
  - 상승 추세일 때 매수, 하락 추세일 때 매도
  - 안정적이지만 큰 수익은 기대하기 어려움

• 변동성 돌파: 가격 변동이 클 때 진입하는 전략
  - 특정 가격대를 돌파할 때 매매 신호 발생
  - 큰 수익 가능성 있지만 위험도 높음

• 역추세 매매: 주가 방향과 반대로 매매하는 전략
  - 과매수/과매도 구간에서 반대 포지션 취함
  - 높은 수익률 가능성 but 전문가용

시장 상황과 투자자 성향에 맞는 모드를 선택하세요.
""",
    "시장 환경 변수": """
시장 환경 변수는 현재 시장의 특성을 정의하는 중요한 설정입니다.

• 변동성: 시장의 움직임이 얼마나 큰지 설정
  - 낮음: 안정적인 시장, 작은 가격 변동
  - 보통: 일반적인 시장 상황
  - 높음: 큰 가격 변동이 있는 시장

• 유동성: 거래가 얼마나 활발한지 설정
  - 낮음: 거래량 적은 종목, 대형주 위주
  - 보통: 일반적인 거래량
  - 높음: 거래량 많은 종목, 소형주 포함

• 세션: 주요 거래 시간대 설정
  - 아시아: 한국, 일본 등 아시아 시장
  - 유럽: 런던, 프랑크푸르트 등
  - 미국: 뉴욕, 나스닥 등

이 설정들은 전략의 민감도와 타이밍에 큰 영향을 줍니다.
""",
    "리스크 관리": """
리스크 관리는 투자 자금을 보호하고 안정적인 수익을 추구하는 핵심 기능입니다.

• 포지션 비중: 총 자금 대비 투자 비중
  - 10%: 매우 보수적, 안정성 우선
  - 30%: 일반적인 수준
  - 50%: 적극적, 높은 수익 추구

• 손익비: 수익과 손실의 목표 비율
  - 1:1.5: 손실 1당 수익 1.5 목표
  - 1:2: 일반적인 수준
  - 1:3: 공격적, 높은 수익률 목표

• 일손실제한: 하루 최대 손실 한도
  - 자금의 1-5% 내에서 설정 권장
  - 이 한도 도달 시 자동 매매 중단

• 쿨다운: 연속 매매 방지 대기 시간
  - 5분: 빈번한 매매 가능
  - 30분: 일반적인 설정
  - 60분: 신중한 매매

리스크 관리는 장기 투자 성공의 핵심입니다.
""",
    "심리·행동 제어": """
심리·행동 제어는 투자자의 감정적 판단을 막고 논리적 매매를 돕는 기능입니다.

• 자동 매매: 감정적 판단 제거
  - 설정된 조건에 따라 자동으로 매매
  - 공포와 탐욕에서 벗어난 의사결정

• 손절 강제: 손실 확정 지연 방지
  - 설정된 손실률 도달 시 자동 매도
  - '더 오르면...' 하는 생각을 차단

• 익절 자동: 탐욕으로 인한 수익 날림 방지
  - 목표 수익률 도달 시 자동 매도
  - '더 오르면...' 하는 욕심 제어

• 과매수/과매도 알림: 극단적 시장 상황 경고
  - 비이성적인 매매 유도 상황 알림
  - 냉정한 판단 유도

성공적인 투자는 감정 통제에서 시작됩니다.
""",
    "외부/고급 조건": """
외부/고급 조건은 기본적인 기술적 분석 외에 추가적인 매매 신호를 설정하는 기능입니다.

• 거래량 급증: 특정 시점의 거래량 폭발
  - 기관 매매나 뉴스 기반 매매 신호
  - 가격 변동 전 선행 지표 활용

• 뉴스 연동: 주요 경제 뉴스 기반 매매
  - 금리, 환율, 정책 발표 시 반응
  - 기본적 분석과 기술적 분석 결합

• 기관 매매 추적: 대형 자금 움직임 분석
  - 외국인, 기관 순매수/매도 동향
  - 스마트 머니의 흐름 따르기

• 시간대별 패턴: 특정 시간대의 매매 성향
  - 장초/장마감, 요일별 특성 반영
  - 시간 기반 통계적 우위 확보

이 조건들을 통해 기본 전략을 보강하고 수익률을 높일 수 있습니다.
""",
    "관심 종목": """
관심 종목은 매매 대상으로 등록된 종목들을 관리하는 기능입니다.

• 종목 추가/삭제: 관심 있는 종목 등록
  - 코드 검색으로 쉽게 추가
  - 섹터별로 그룹화 가능

• 실시간 시세: 등록된 종목의 현재가격 확인
  - 1초 단위 실시간 업데이트
  - 등락률과 거래량 표시

• 알림 설정: 중요한 가격 변동 시 알림
  - 목표가 도달 시 알림
  - 급등락 발생 시 알림

• 성과 분석: 종목별 수익률 추적
  - 매매 기록 자동 저장
  - 수익률과 승률 통계 제공

관심 종목 관리는 체계적인 투자의 시작입니다.
""",
    "지표 설정": """
지표 설정은 기술적 분석에 사용할 보조지표들을 선택하는 기능입니다.

• 이동평균선: 추세 방향 판단
  - 5일, 20일, 60일 등 다양한 기간
  - 골든크로스 매매 신호 활용

• RSI: 과매수/과매도 상태 판단
  - 70 이상: 과매수, 매도 고려
  - 30 이하: 과매도, 매수 고려

• MACD: 추세 전환 신호 포착
  - 시그널선과 MACD선 교차점 활용
  - 추세의 강약까지 파악 가능

• 볼린저밴드: 가격 변동성 분석
  - 상단선 돌파: 과매수 신호
  - 하단선 이탈: 과매도 신호

• 스토캐스틱: 단기 매매 타이밍
  - %K와 %D 교차로 매매 신호
  - 단기 수익률 극대화에 유용

여러 지표를 조합하여 신뢰도 높은 매매를 할 수 있습니다.
""",
    "주문/위험 한도": """
주문/위험 한도는 실제 매매 실행 시 적용될 금액과 위험 관리 설정입니다.

• 최대 투자금: 총 투자 가능한 금액
  - 계좌 잔고의 일부만 사용 권장
  - 비상자금은 항상 확보

• 1회 주문금액: 한 번에 투자하는 금액
  - 분할 매매 시 평균 단가 유리
  - 리스크 분산 효과

• 손절률: 손실 확정 기준
  - -5%: 보수적, 빠른 손절
  - -10%: 일반적인 수준
  - -15%: 공격적, 더 기다려보기

• 익절률: 수익 실현 기준
  - +5%: 소액 빈번한 수익
  - +10%: 일반적인 목표
  - +20%: 큰 수익 추구

이 설정들은 실제 매매 시 자동으로 적용됩니다.
"""
}

# AI 매매 성향 3단계 → 내부 파라미터 프리셋 (사용자 숫자 입력 제거, AI 내부 전용)
AGGRESSIVENESS_PRESETS = {
    "conservative": {"aggressiveness_level": 2, "pos_size_pct": 1.5, "rr_ratio": 1.8, "daily_loss_limit_pct": 2.0, "cooldown_sec": 45},
    "neutral":      {"aggressiveness_level": 5, "pos_size_pct": 2.5, "rr_ratio": 2.0, "daily_loss_limit_pct": 3.0, "cooldown_sec": 30},
    "aggressive":   {"aggressiveness_level": 9, "pos_size_pct": 5.0, "rr_ratio": 3.0, "daily_loss_limit_pct": 5.0, "cooldown_sec": 10},
}

class StrategyTab(QWidget):
    """전략설정 탭 - 리디자인: AI 주도, 사용자는 실행/성향/종목/주문금액만 결정."""

    def __init__(self, owner, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("strategyTabRoot")
        self._owner = owner
        self._log = logging.getLogger("app.ui.strategy_tab")
        
        self._ai_master_enabled = False
        self._applying_ai = False
        self._manual_rr_override = False
        self._manual_dll_override = False
        self._applying_aggr_preset = False
        self._is_dirty = False

        # 🔷 UI Splitter 상태(좌우/상하) 저장/복원
        self._strategy_vsplitter = None
        self._strategy_top_hsplitter = None
        self._splitter_state_timer = QTimer(self)
        self._splitter_state_timer.setSingleShot(True)

        self._draft_strategy = {
            'pos_size_pct': 2.5, 'rr_ratio': 2.0, 'cooldown_sec': 30,
            'daily_loss_limit_pct': 3.0, 'aggressiveness_level': 5,
            'strategy_mode': 'ai', 'indicators': ['bbands', 'rsi', 'macd'],
            'whitelist': [], 'blacklist': []
        }
        self._last_event_message = ""
        
        self._init_widgets()
        
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ✅ 상하 모든 박스를 사용자가 조절 가능하게: Vertical QSplitter
        vs = QSplitter(Qt.Vertical)
        vs.setChildrenCollapsible(False)
        vs.setHandleWidth(6)
        vs.setObjectName("strategyVSplitter")
        self._strategy_vsplitter = vs

        # 🔷 상단: 실행 상태 카드 (높이 조절 가능)
        g_run = self._build_run_status_card()
        vs.addWidget(g_run)

        # ✅ 2열 상단: AI 매매 성향(좌) + 주문 설정(우) — 좌우 조절 가능: Horizontal QSplitter
        hs = QSplitter(Qt.Horizontal)
        hs.setChildrenCollapsible(False)
        hs.setHandleWidth(8)
        hs.setObjectName("strategyTopHSplitter")
        self._strategy_top_hsplitter = hs

        g_aggr = self._build_aggressiveness_section()
        g_order = self._build_order_section()
        g_aggr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        g_order.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        hs.addWidget(g_aggr)
        hs.addWidget(g_order)

        # 상단 2열을 세로 Splitter에 넣어 "상하 높이"도 조절되게 함
        vs.addWidget(hs)

        # 🔷 종목 제어 / 사전 점검도 상하 조절 가능
        sym_section = self._build_symbol_section()
        vs.addWidget(sym_section)

        preflight_section = self._build_preflight_section()
        vs.addWidget(preflight_section)

        root.addWidget(vs)

        # 진단 로그(1회): splitter 구성 확인
        try:
            self._log.info(
                "[LAYOUT-DBG] strategy splitters ready vs=%s hs=%s",
                bool(self._strategy_vsplitter), bool(self._strategy_top_hsplitter)
            )
        except Exception:
            pass

        # 🔷 Splitter 상태 복원 + 변경 시 저장(throttle)
        self._restore_strategy_splitter_state()
        try:
            self._splitter_state_timer.timeout.connect(self._save_strategy_splitter_state)
            self._strategy_vsplitter.splitterMoved.connect(lambda *_: self._splitter_state_timer.start(250))
            self._strategy_top_hsplitter.splitterMoved.connect(lambda *_: self._splitter_state_timer.start(250))
        except Exception as e:
            self._log.debug("[SPLITTER] hook failed: %s", e)
        
        # 저장 버튼
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.lbl_dirty_state = QLabel("✅ 저장됨")
        self.lbl_dirty_state.setStyleSheet("QLabel { color: #666; font-size: 11px; padding: 4px; }")
        btn_row.addWidget(self.lbl_dirty_state)
        self.btn_save_apply = QPushButton("전략 저장")
        self._save_btn_base_text = "전략 저장"
        self.btn_save_apply.setStyleSheet("QPushButton { font-weight: bold; padding: 10px 20px; background: #007bff; color: white; }")
        self.btn_save_apply.setMinimumWidth(120)
        self.btn_save_apply.clicked.connect(self._on_save_apply)
        btn_row.addWidget(self.btn_save_apply)
        self.btn_sell_test = QPushButton("매도 테스트")
        self.btn_sell_test.setToolTip("실제 주문 없이 현재 보유 종목의 매도 조건만 평가합니다.")
        self.btn_sell_test.setMaximumWidth(100)
        self.btn_sell_test.clicked.connect(self._on_sell_test_clicked)
        btn_row.addWidget(self.btn_sell_test)
        root.addLayout(btn_row)
        # 전략설정 탭 전용 로컬 QSS (상단 여백/패딩 축소, 전역 QSS 미변경)
        self.setStyleSheet(
            "QWidget#strategyTabRoot QGroupBox { margin-top: 6px; padding-top: 8px; }\n"
            "QWidget#strategyTabRoot QLabel { margin: 0px; padding: 0px; }\n"
        )
        
        self._connect_signals()
        self._update_run_status_card()
        self._update_summary()
        self._sync_initial_watchlist()
        self._update_dirty_indicator()
        self._load_order_and_downscale_from_settings()

        try:
            eventbus.subscribe("ai.reco.strategy_suggested", self._on_ai_strategy_suggested)
            eventbus.subscribe("runner.strategy.injected", self._on_runner_strategy_injected)
            eventbus.subscribe("strategy.last_event", self._on_strategy_last_event)
            eventbus.subscribe("external.trade.detected", self._on_external_trade_detected)
            eventbus.subscribe("rotation.fired", self._on_rotation_fired)
        except Exception:
            pass
        self._rotation_last_ts = 0.0
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._update_rotation_timer_label)
        self._rotation_timer.start(1000)
    
    def showEvent(self, event):
        """전략설정 탭 표시 시 1회 레이아웃 로그 (2열 구성 검증). 무거운 작업 금지."""
        super().showEvent(event)
        self._log.info("[TAB] enter name=Strategy")
        QTimer.singleShot(0, self._log_strat_ui_layout)
    
    def _log_strat_ui_layout(self):
        """UI 구성 직후 1회: [STRAT-UI] layout=2col_top(aggr+order) 2col_lists(wl+bl) ok size=(w,h)"""
        try:
            w, h = self.size().width(), self.size().height()
            self._log.info("[STRAT-UI] layout=2col_top(aggr+order) 2col_lists(wl+bl) ok size=(%d,%d)", w, h)
        except Exception:
            pass
    
    def _on_runner_strategy_injected(self, payload):
        """Runner가 전략 주입 시 이벤트 수신 → 실사용 전략 UI 갱신."""
        self._update_active_strategy_ui(payload)

    def _on_strategy_last_event(self, payload):
        """ORDER-BLOCK/BUY/SELL 이벤트 수신 → 실행 상태 카드만 갱신 (최근 AI 판단은 투자현황탭에서 처리)."""
        try:
            msg = (payload or {}).get("message", "") if isinstance(payload, dict) else ""
            if msg:
                self._last_event_message = str(msg)[:120]
            self._update_run_status_card()
        except Exception:
            pass

    def _on_rotation_enabled_changed(self, checked):
        """로테이션 체크박스 변경: OFF→ON 시 타이머 리셋, OFF 시 마지막 로테이션 표시 초기화(과거 세션 잔재 제거)."""
        try:
            self._mark_dirty()
            if checked:
                import time
                self._rotation_last_ts = time.time()
                self._update_rotation_timer_label()
            else:
                if hasattr(self, "lbl_rotation_last"):
                    self.lbl_rotation_last.setText("")
        except Exception:
            pass

    def _on_rotation_fired(self, payload):
        """로테이션 발동 시 기준 시각 갱신 + 마지막 로테이션/결과 상태 표시."""
        try:
            if not isinstance(payload, dict):
                return
            p = payload.get("advice") if isinstance(payload.get("advice"), dict) else payload
            ts = p.get("ts")
            if ts is not None:
                self._rotation_last_ts = float(ts)
            import time
            t = time.localtime(float(ts)) if ts else time.localtime()
            hms = "%02d:%02d:%02d" % (t.tm_hour, t.tm_min, t.tm_sec)
            line = "마지막 로테이션: %s" % hms
            ok_count = p.get("ok_count")
            fail_count = p.get("fail_count")
            out_list = p.get("out_list") or []
            if ok_count is not None and fail_count is not None:
                line += " (성공 %d / 실패 %d)" % (ok_count, fail_count)
            else:
                line += " (대상 없음)" if not out_list else ""
            if out_list:
                parts = []
                for item in out_list[:10]:
                    if isinstance(item, dict):
                        market = item.get("market", "")
                        ok = item.get("ok", False)
                        reason = (item.get("reason") or "")[:20]
                        parts.append("[%s %s]" % (market, "OK" if ok else "FAIL:" + (reason or "—")))
                    else:
                        parts.append("[%s]" % str(item))
                line += " " + " ".join(parts)
                if len(out_list) > 10:
                    line += " ..."
            elif ok_count is not None and fail_count is not None and ok_count == 0 and fail_count == 0:
                line += " [대상 없음]"
            if hasattr(self, "lbl_rotation_last"):
                self._log.info("[ROT-UI] update_last_rotation line=%s", line[:120] if line else "")
                self.lbl_rotation_last.setText(line)
            self._update_rotation_timer_label()
        except Exception:
            pass

    def _update_rotation_timer_label(self):
        """1초마다: 로테이션 사용 시 다음 발동까지 남은 시간 mm:ss 표시."""
        try:
            if not hasattr(self, "lbl_rotation_timer") or not hasattr(self, "chk_rotation_enabled"):
                return
            if not self.chk_rotation_enabled.isChecked():
                self.lbl_rotation_timer.setText("다음 로테이션: OFF")
                return
            interval_min = getattr(self, "spn_rotation_interval", None)
            interval_sec = (int(interval_min.value()) if interval_min else 30) * 60
            last_ts = getattr(self, "_rotation_last_ts", 0.0) or 0.0
            import time
            now = time.time()
            if last_ts <= 0:
                self.lbl_rotation_timer.setText("다음 로테이션: —")
                return
            remaining = max(0, int(interval_sec - (now - last_ts)))
            m, s = remaining // 60, remaining % 60
            self.lbl_rotation_timer.setText("다음 로테이션: %d:%02d" % (m, s))
        except Exception:
            pass
    
    def _update_active_strategy_ui(self, data):
        """실사용 전략(ACTIVE STRATEGY) UI 갱신 → 통합 '현재 적용 전략'에 한 줄 반영."""
        try:
            if not hasattr(self, "lbl_active_strategy"):
                self._last_active_line = (data or {}).get("order_amount_krw") if isinstance(data, dict) else None
                return
            if not data or not isinstance(data, dict):
                self.lbl_active_strategy.setText("아직 실행된 전략이 없습니다.")
                self._last_active_line = None
                return
            oa = int(data.get("order_amount_krw", 0) or 0)
            pos = float(data.get("pos_size_pct", 0) or 0)
            rr = float(data.get("rr", 0) or data.get("rr_ratio", 0) or 0)
            cd = int(data.get("cooldown_sec", 0) or 0)
            dll = float(data.get("daily_loss_limit_pct", 0) or 0)
            line1 = f"주문금액: {oa:,}원 | 포지션: {pos}%"
            line2 = f"RR: {rr} | 쿨다운: {cd}초 | 일일손실: {dll}%"
            self.lbl_active_strategy.setText("[ACTIVE STRATEGY]\n" + line1 + "\n" + line2)
            self._last_active_line = line1 + " | " + line2
            self._log.info("[AI-UI] active strategy updated %s", data)
        except Exception as e:
            self.lbl_active_strategy.setText("아직 실행된 전략이 없습니다.")
            self._last_active_line = None
            self._log.debug("[AI-UI] active strategy update failed: %s", e)
    
    def _update_ai_strategy_snapshot(self):
        """AI 전략 스냅샷(읽기 전용) 갱신. 리디자인 후 해당 위젯 없으면 스킵."""
        try:
            if not hasattr(self, "lbl_ai_snapshot"):
                return
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            if not main_window:
                self.lbl_ai_snapshot.setText("아직 AI 전략이 적용되지 않았습니다.")
                self._last_ai_line = None
                return

            settings = main_window._get_settings_cached()
            stg = getattr(settings, "strategy", None) if settings else None
            show = stg and (getattr(self, "_ai_strategy_applied", False) or getattr(self, "_last_ai_strategy", None))
            if not show or not stg:
                self.lbl_ai_snapshot.setText("아직 AI 전략이 적용되지 않았습니다.")
                self._last_ai_line = None
                return

            # ✅ 적용값(SSOT)
            oa = int(getattr(stg, "order_amount_krw", 10000) or 10000)
            pos = float(getattr(stg, "pos_size_pct", 2.5) or 2.5)
            rr = float(getattr(stg, "rr_ratio", 2.0) or 2.0)
            cd = int(getattr(stg, "cooldown_sec", 30) or 30)
            dll = float(getattr(stg, "daily_loss_limit_pct", 3.0) or 3.0)

            lines = [
                "[APPLIED / SSOT]",
                f"주문금액: {oa:,}원",
                f"포지션 크기: {pos}%",
                f"손익비(RR): {rr}",
                f"쿨다운: {cd}초",
                f"일일 손실 제한: {dll}%",
            ]

            # ✅ 편집중(드래프트) 프리뷰: 저장 전에도 즉시 사용자에게 "현재 조정값"을 보여준다
            if getattr(self, "_is_dirty", False) and isinstance(getattr(self, "_draft_strategy", None), dict):
                doa = int(self._draft_strategy.get("order_amount_krw", oa) or oa)
                dpos = float(self._draft_strategy.get("pos_size_pct", pos) or pos)
                drr = float(self._draft_strategy.get("rr_ratio", rr) or rr)
                dcd = int(self._draft_strategy.get("cooldown_sec", cd) or cd)
                ddll = float(self._draft_strategy.get("daily_loss_limit_pct", dll) or dll)
                lines += [
                    "",
                    "[PREVIEW / EDITING]",
                    f"주문금액: {doa:,}원",
                    f"포지션 크기: {dpos}%",
                    f"손익비(RR): {drr}",
                    f"쿨다운: {dcd}초",
                    f"일일 손실 제한: {ddll}%",
                ]

            # (있을 때) confidence/reason 추가 표시
            last = getattr(self, "_last_ai_strategy", None) or {}
            if last.get("confidence") is not None:
                lines.append(f"AI 신뢰도: {float(last.get('confidence', 0)):.2f}")
            if last.get("reason"):
                lines.append(f"사유: {str(last.get('reason', ''))[:80]}")

            self.lbl_ai_snapshot.setText("\n".join(lines))
            self._last_ai_line = f"주문금액: {oa:,}원 | 포지션: {pos}% | RR: {rr} | 쿨다운: {cd}초 | 일일손실: {dll}%"
            self._log.info(
                "[AI-UI] snapshot updated order_amount_krw=%s pos_size_pct=%s rr=%s cooldown_sec=%s daily_loss_limit_pct=%s dirty=%s",
                oa, pos, rr, cd, dll, getattr(self, "_is_dirty", False)
            )
        except Exception as e:
            self.lbl_ai_snapshot.setText("아직 AI 전략이 적용되지 않았습니다.")
            self._last_ai_line = None
            self._log.debug("[AI-UI] snapshot update failed: %s", e)
    
    def _on_user_override(self, reason=""):
        """사용자 수동 변경 감지 시 모두AI 해제"""
        if self._applying_ai:  # AI 적용 중이면 무시
            return
            
        if self._ai_master_enabled:
            self._ai_master_enabled = False
            # 버튼을 주황색으로 변경
            self.btn_all_ai.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; background: #ff6b35; color: white; border: none; border-radius: 3px; }")
            
            # 사용자 피드백
            if hasattr(self, 'info_label'):
                self.info_label.setText(f"사용자 설정 변경 감지 → 모두AI 해제 ({reason})")
            
            self._log.info(f"모두AI 해제: 사용자 개입 감지 ({reason})")
    
    def _load_watchlist(self):
        """워치리스트 로드"""
        try:
            # ✅ main window 캐시 getter 사용
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            
            if main_window:
                settings = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                settings = load_settings()
            
            whitelist = getattr(settings.strategy, 'whitelist', [])
            blacklist = getattr(settings.strategy, 'blacklist', [])
            
            # UI 반영
            self._whitelist = whitelist
            self._blacklist = blacklist
            self._update_watchlist_ui()
            
        except Exception as e:
            self.log.error(f"[CONFIG] load watchlist failed: {e}")
    
    def _sync_initial_watchlist(self):
        """초기 워치리스트 동기화: prefs에서 로드하여 UI에 반영"""
        try:
            # ✅ main window 캐시 getter 사용
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            
            if main_window:
                settings = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                settings = load_settings()
            
            whitelist = getattr(settings.strategy, 'whitelist', [])
            blacklist = getattr(settings.strategy, 'blacklist', [])
            
            # 워치리스트 요약 UI에 반영
            self._apply_watchlist_view(whitelist, blacklist, reason="initial_prefs_sync")
            
            self._log.info(f"초기 워치리스트 동기화 완료: WL={len(whitelist)}, BL={len(blacklist)}")
            
        except Exception as e:
            self._log.error(f"초기 워치리스트 동기화 실패: {e}")
    
    def _show_help(self, title: str, body: str):
        """도움말 팝업 표시"""
        QMessageBox.information(self, f"{title} 도움말", body.strip())
        # 인포 배너에도 메시지 표시
        if hasattr(self, 'info_label'):
            self.info_label.setText(f"도움말: {title}을 확인했습니다.")
    
    def _make_info_btn(self, title: str, body: str) -> QToolButton:
        """도움말 버튼 생성"""
        btn = QToolButton()
        btn.setText("ⓘ")
        btn.setAutoRaise(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(18, 18)
        btn.setToolTip("도움말 보기")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(lambda: self._show_help(title, body))
        return btn
    
    def _create_section_header_with_title(self, title: str) -> QHBoxLayout:
        """섹션 제목과 도움말 버튼이 있는 헤더 생성"""
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title_label)
        
        if title in HELP_TEXTS:
            info_btn = self._make_info_btn(title, HELP_TEXTS[title])
            header.addWidget(info_btn)
        
        header.addStretch(1)
        return header
    
    def _create_standard_section_header(self, title: str) -> QWidget:
        """표준 섹션 헤더 위젯 생성 (제목 + ⓘ)"""
        header_widget = QWidget()
        header_widget.setFixedHeight(28)  # 고정 높이로 모든 섹션 통일
        header_widget.setStyleSheet("QWidget { border-bottom: 1px solid #e0e0e0; background: #f8f9fa; }")
        
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        layout.addWidget(title_label)
        
        if title in HELP_TEXTS:
            info_btn = self._make_info_btn(title, HELP_TEXTS[title])
            layout.addWidget(info_btn)
        
        layout.addStretch(1)
        return header_widget
    
    def _init_widgets(self):
        """리디자인: 최소 위젯만 초기화 (실행 상태/요약은 _build_run_status_card 등에서 생성)."""
        self._ai_strategy_applied = False
        self._last_ai_line = None
        self._last_active_line = None
        self.info_label = QLabel("전략 설정이 준비되었습니다.")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("QLabel { color: #00c896; font-size: 12px; padding: 8px; background: #f0f8f0; border-radius: 3px; }")
        self.lbl_strat_summary = QLabel("")  # 호환용, run status 카드가 대체
    
    def _build_run_status_card(self):
        """상단: 실행 상태 · 오늘 전략 요약 카드 (표준 포맷)."""
        g = QGroupBox("실행 상태 · 오늘 전략 요약")
        g.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #0078d4; }")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay = QVBoxLayout(g)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(2)
        self.lbl_run_status = QLabel(
            "[STOPPED] 모의매매\n"
            "KRW 잔고: —\n"
            "오늘 전략: — | 1회 주문: — | 스냅샷: —\n"
            "마지막 AI 판단: —"
        )
        self.lbl_run_status.setWordWrap(True)
        self.lbl_run_status.setStyleSheet("QLabel { font-size: 13px; padding: 8px; background: #f8f9fa; border-radius: 4px; }")
        lay.addWidget(self.lbl_run_status)
        self.lbl_beginner_hint = QLabel("AI가 매수/매도 판단을 수행합니다. 사용자는 성향·주문금액·허용/차단 종목만 선택하세요.")
        self.lbl_beginner_hint.setStyleSheet("QLabel { color: #555; font-size: 11px; padding: 4px 6px; margin: 0px; }")
        self.lbl_beginner_hint.setWordWrap(True)
        self.lbl_beginner_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(self.lbl_beginner_hint)
        return g
    
    def _build_aggressiveness_section(self):
        """섹션 1: AI 매매 성향 (3단계, 표준 설명)."""
        g = QGroupBox("AI 매매 성향")
        g.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #0078d4; }")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay = QVBoxLayout(g)
        lay.setContentsMargins(8, 16, 8, 6)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignTop)

        row = QHBoxLayout()
        row.setSpacing(0)  # ✅ 버튼 사이 여백 제거 → 3등분 정확히 맞춤

        # ✅ 라디오 버튼 → 버튼형 토글(로직 호환: isChecked/setChecked 유지)
        self.radio_aggr_conservative = QPushButton("보수적")
        self.radio_aggr_conservative.setCheckable(True)
        self.radio_aggr_conservative.setToolTip("신호가 강할 때만 진입, 손실 회피 우선")
        self.radio_aggr_conservative.setObjectName("aggrConservative")

        self.radio_aggr_neutral = QPushButton("중립")
        self.radio_aggr_neutral.setCheckable(True)
        self.radio_aggr_neutral.setToolTip("균형 잡힌 진입과 회전")
        self.radio_aggr_neutral.setObjectName("aggrNeutral")

        self.radio_aggr_aggressive = QPushButton("공격적")
        self.radio_aggr_aggressive.setCheckable(True)
        self.radio_aggr_aggressive.setToolTip("빠른 진입과 적극적 회전")
        self.radio_aggr_aggressive.setObjectName("aggrAggressive")

        # 버튼 높이/확장 정책(가독성 + 균일 폭)
        for b in (self.radio_aggr_conservative, self.radio_aggr_neutral, self.radio_aggr_aggressive):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(36)
            # ✅ 가로 Expanding → 박스 폭을 3등분
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 🔷 기본 상태는 그레이스케일
        self.radio_aggr_conservative.setStyleSheet(
            "QPushButton#aggrConservative{background:#f2f2f2;color:#666;border:1px solid #ddd;border-radius:6px;font-weight:700;}"
            "QPushButton#aggrConservative:hover{background:#e6e6e6;}"
            "QPushButton#aggrConservative:checked{background:#1e5bd8;color:#ffffff;border:1px solid #1e5bd8;}"
        )
        self.radio_aggr_neutral.setStyleSheet(
            "QPushButton#aggrNeutral{background:#f2f2f2;color:#666;border:1px solid #ddd;border-radius:6px;font-weight:700;}"
            "QPushButton#aggrNeutral:hover{background:#e6e6e6;}"
            "QPushButton#aggrNeutral:checked{background:#2e7d32;color:#ffffff;border:1px solid #2e7d32;}"
        )
        self.radio_aggr_aggressive.setStyleSheet(
            "QPushButton#aggrAggressive{background:#f2f2f2;color:#666;border:1px solid #ddd;border-radius:6px;font-weight:700;}"
            "QPushButton#aggrAggressive:hover{background:#e6e6e6;}"
            "QPushButton#aggrAggressive:checked{background:#d32f2f;color:#ffffff;border:1px solid #d32f2f;}"
        )

        # ✅ 기존 로직 유지: QButtonGroup으로 단일 선택 보장
        self.radio_aggr_neutral.setChecked(True)
        self._aggr_radio_group = QButtonGroup(self)
        self._aggr_radio_group.setExclusive(True)
        self._aggr_radio_group.addButton(self.radio_aggr_conservative)
        self._aggr_radio_group.addButton(self.radio_aggr_neutral)
        self._aggr_radio_group.addButton(self.radio_aggr_aggressive)

        # 🔷 버튼 stretch를 동일하게 1:1:1
        row.addWidget(self.radio_aggr_conservative, 1)
        row.addWidget(self.radio_aggr_neutral, 1)
        row.addWidget(self.radio_aggr_aggressive, 1)
        lay.addLayout(row)

        # 🔷 로테이션: 기회비용 창출 매도-only (주기 | 교체수 | 다음/마지막 로테이션, 왼쪽 플로우)
        self.chk_rotation_enabled = QCheckBox("로테이션 사용")
        self.chk_rotation_enabled.setChecked(False)
        self.chk_rotation_enabled.setToolTip("정체된 종목을 정리해 현금(기회비용)을 만듭니다. 점수 낮은 순·정체 오래된 순으로 전량 매도만 수행.")
        lay.addWidget(self.chk_rotation_enabled)
        row_rot = QHBoxLayout()
        row_rot.addWidget(QLabel("주기:"))
        self.spn_rotation_interval = QSpinBox()
        self.spn_rotation_interval.setRange(1, 240)
        self.spn_rotation_interval.setValue(30)
        self.spn_rotation_interval.setSuffix(" 분")
        row_rot.addWidget(self.spn_rotation_interval)
        row_rot.addWidget(QLabel("|"))
        row_rot.addWidget(QLabel("교체 수:"))
        self.spn_rotation_count = QSpinBox()
        self.spn_rotation_count.setRange(1, 10)
        self.spn_rotation_count.setValue(1)
        self.spn_rotation_count.setSuffix(" 개")
        row_rot.addWidget(self.spn_rotation_count)
        row_rot.addWidget(QLabel("|"))
        self.lbl_rotation_timer = QLabel("다음 로테이션: OFF")
        self.lbl_rotation_timer.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        row_rot.addWidget(self.lbl_rotation_timer)
        lay.addLayout(row_rot)
        self.lbl_rotation_last = QLabel("")
        self.lbl_rotation_last.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        lay.addWidget(self.lbl_rotation_last)

        desc = QLabel(
            "AI가 시장 상황에 따라 진입 빈도와 회전 속도를 자동 조절합니다.\n"
            "보수적: 신호가 강할 때만 진입 | 중립: 균형 | 공격적: 빠른 진입·회전"
        )
        desc.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(desc)
        return g

    def _build_order_section(self):
        """섹션 2: 주문 설정 (표준 라벨·설명)."""
        g = QGroupBox("주문 설정")  # ✅ 다른 박스들과 동일하게 GroupBox 타이틀 사용
        g.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #0078d4; }")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        main_layout = QVBoxLayout(g)
        # 폼 레이아웃 (실제 화면에 붙는 lay)
        lay = QFormLayout()
        lay.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        lay.setLabelAlignment(Qt.AlignLeft)
        lay.setHorizontalSpacing(10)
        # 한 줄: 1회 주문금액 | 최대 투자금액 | 보유자산 전체 기준
        row_order = QWidget()
        row_layout = QHBoxLayout(row_order)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(QLabel("1회 주문금액(원)"))
        self.spn_order_amount = QSpinBox()
        self.spn_order_amount.setRange(5000, 100_000_000)
        self.spn_order_amount.setValue(10_000)
        self.spn_order_amount.setSingleStep(1000)
        self.spn_order_amount.setGroupSeparatorShown(True)
        self.spn_order_amount.setMinimumWidth(140)
        self.spn_order_amount.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        row_layout.addWidget(self.spn_order_amount)
        row_layout.addWidget(QLabel(" | "))
        row_layout.addWidget(QLabel("최대 투자금액(원)"))
        self.spn_max_invest_cap = QSpinBox()
        self.spn_max_invest_cap.setRange(0, 100_000_000)
        self.spn_max_invest_cap.setValue(0)
        self.spn_max_invest_cap.setSingleStep(10000)
        self.spn_max_invest_cap.setGroupSeparatorShown(True)
        self.spn_max_invest_cap.setSpecialValueText("제한 없음")
        self.spn_max_invest_cap.setMinimumWidth(140)
        self.spn_max_invest_cap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.spn_max_invest_cap.setToolTip("총 보유 평가금액(노출)이 이 금액을 넘으면 추가 매수를 차단합니다. (0=제한 없음)")
        row_layout.addWidget(self.spn_max_invest_cap)
        lay.addRow("", row_order)
        self.chk_allow_downscale = QCheckBox("잔고 부족 시 주문금액 자동 축소 허용")
        self.chk_allow_downscale.setChecked(False)
        lay.addRow("", self.chk_allow_downscale)
        self.lbl_downscale_desc = QLabel("설정한 금액 그대로만 주문 시도합니다. 잔고/한도 부족 시 주문하지 않습니다.")
        self.lbl_downscale_desc.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        self.lbl_downscale_desc.setWordWrap(True)
        lay.addRow("", self.lbl_downscale_desc)

        # ✅ 익절/손절(%) — 0이면 AI 판단(고정값 금지), >0이면 사용자 안전장치(최우선)
        self.spn_stop_loss_pct = QDoubleSpinBox()
        self.spn_stop_loss_pct.setRange(0.0, 50.0)
        self.spn_stop_loss_pct.setDecimals(2)
        self.spn_stop_loss_pct.setSingleStep(0.1)
        self.spn_stop_loss_pct.setSuffix("%")
        self.spn_stop_loss_pct.setValue(0.0)
        self.spn_stop_loss_pct.setToolTip("0% = AI 판단 / 0보다 크면 사용자 값 우선 적용")

        self.spn_take_profit_pct = QDoubleSpinBox()
        self.spn_take_profit_pct.setRange(0.0, 100.0)
        self.spn_take_profit_pct.setDecimals(2)
        self.spn_take_profit_pct.setSingleStep(0.1)
        self.spn_take_profit_pct.setSuffix("%")
        self.spn_take_profit_pct.setValue(0.0)
        self.spn_take_profit_pct.setToolTip("0% = AI 판단 / 0보다 크면 사용자 값 우선 적용")

        # 손절/익절 한 줄 2열: 각각 라벨 + 입력 + 상태, 중간에 | 구분
        self.lbl_stop_mode = QLabel("")
        self.lbl_stop_mode.setStyleSheet("color: #0078d4; font-size: 10px;")
        self.lbl_tp_mode = QLabel("")
        self.lbl_tp_mode.setStyleSheet("color: #0078d4; font-size: 10px;")
        
        hbox_tp_sl = QHBoxLayout()
        # 손절: 라벨 + 입력 + 상태
        hbox_sl = QHBoxLayout()
        hbox_sl.addWidget(QLabel("손절(%)"))
        hbox_sl.addWidget(self.spn_stop_loss_pct)
        hbox_sl.addSpacing(10)
        hbox_sl.addWidget(self.lbl_stop_mode)
        hbox_tp_sl.addLayout(hbox_sl)
        
        # 구분자 |
        lbl_separator = QLabel("|")
        lbl_separator.setStyleSheet("color: #999; font-size: 12px; padding: 0 8px;")
        hbox_tp_sl.addWidget(lbl_separator)
        
        # 익절: 라벨 + 입력 + 상태
        hbox_tp = QHBoxLayout()
        hbox_tp.addWidget(QLabel("익절(%)"))
        hbox_tp.addWidget(self.spn_take_profit_pct)
        hbox_tp.addSpacing(10)
        hbox_tp.addWidget(self.lbl_tp_mode)
        hbox_tp_sl.addLayout(hbox_tp)
        
        lay.addRow("", hbox_tp_sl)
        main_layout.addLayout(lay)

        self.spn_stop_loss_pct.valueChanged.connect(self._update_tp_sl_status)
        self.spn_take_profit_pct.valueChanged.connect(self._update_tp_sl_status)
        self._update_tp_sl_status()

        def _on_downscale_toggled():
            if self.chk_allow_downscale.isChecked():
                self.lbl_downscale_desc.setText("잔고/한도 범위 내에서 금액을 자동 축소하여 주문합니다. (최소 5,000원)")
            else:
                self.lbl_downscale_desc.setText("설정한 금액 그대로만 주문 시도합니다. 잔고/한도 부족 시 주문하지 않습니다.")
        self.chk_allow_downscale.toggled.connect(_on_downscale_toggled)
        return g

    def _build_symbol_section(self):
        """섹션 3: 종목 제어 – 허용(Allowlist)(좌), 차단(Blacklist)(우) 2열."""
        g = QGroupBox("종목 제어")
        g.setToolTip("고급: allowlist로 후보를 제한하고, whitelist로 우선순위를 조정할 수 있습니다.")
        g.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #0078d4; }")
        g.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QHBoxLayout(g)
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 4, 0)
        row_wl = QHBoxLayout()
        row_wl.addWidget(QLabel("허용 종목(Allowlist)"))
        self.btn_wl_manage = QPushButton("관리")
        self.btn_wl_manage.setMaximumWidth(80)
        row_wl.addWidget(self.btn_wl_manage)
        row_wl.addStretch()
        left_lay.addLayout(row_wl)
        self.lst_whitelist = QListWidget()
        self.lst_whitelist.setMinimumHeight(100)
        self.lst_whitelist.setMaximumHeight(140)
        self.lst_whitelist.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_lay.addWidget(self.lst_whitelist)
        wl_desc = QLabel(
            "화이트리스트: '허용'이 아니라 '우선순위'입니다. 조건이 맞을 때 먼저 고려합니다."
        )
        wl_desc.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        wl_desc.setWordWrap(True)
        left_lay.addWidget(wl_desc)
        left_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(left_w)
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(4, 0, 0, 0)
        row_bl = QHBoxLayout()
        row_bl.addWidget(QLabel("차단 종목(Blacklist)"))
        self.btn_bl_manage = QPushButton("관리")
        self.btn_bl_manage.setMaximumWidth(80)
        row_bl.addWidget(self.btn_bl_manage)
        row_bl.addStretch()
        right_lay.addLayout(row_bl)
        self.lst_blacklist = QListWidget()
        self.lst_blacklist.setMinimumHeight(100)
        self.lst_blacklist.setMaximumHeight(140)
        self.lst_blacklist.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_lay.addWidget(self.lst_blacklist)
        bl_desc = QLabel("해당 종목은 절대 매매하지 않습니다.")
        bl_desc.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        bl_desc.setWordWrap(True)
        right_lay.addWidget(bl_desc)
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(right_w)
        self._watchlist_manage_dialog = None
        self.btn_wl_manage.clicked.connect(lambda: self._open_watchlist_manage("whitelist"))
        self.btn_bl_manage.clicked.connect(lambda: self._open_watchlist_manage("blacklist"))
        return g

    def _build_preflight_section(self):
        """섹션 4: 사전 점검 결과 (표준 포맷)."""
        g = QGroupBox("사전 점검 결과")
        g.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #0078d4; }")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        lay = QVBoxLayout(g)
        self.lbl_preflight = QLabel("실행 버튼 위에서 확인됩니다.")
        self.lbl_preflight.setWordWrap(True)
        self.lbl_preflight.setFixedHeight(130)
        self.lbl_preflight.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lbl_preflight.setStyleSheet(
            "QLabel { font-size: 12px; padding: 6px; background: #f8f9fa; border-radius: 4px; }"
        )
        lay.addWidget(self.lbl_preflight)
        return g

    def _on_sell_test_clicked(self):
        """매도 테스트(드라이런): 실제 주문 없이 현재 보유/매도 조건만 5줄로 표시."""
        try:
            # P0-[2]: Holdings SSOT 사용
            from app.services.holdings_service import fetch_live_holdings
            from app.strategy.runner import (
                get_last_sell_attempt_ts, get_last_sell_block_reason_counter,
                get_last_sell_elig_decision, get_last_sell_elig_top_reason,
            )
            import time
            
            holdings_data = fetch_live_holdings(force=True)
            items = holdings_data.get("items", [])
            pos_n = len(items)
            ts = get_last_sell_attempt_ts()
            if ts and ts > 0:
                age_min = int((time.time() - ts) / 60)
                attempt_str = f"{age_min}분 전 시도"
            else:
                attempt_str = "아직 없음"
            counter = get_last_sell_block_reason_counter() or {}
            top_block = (sorted(counter.items(), key=lambda x: -x[1])[:1] or [("—", 0)])[0]
            top_block_str = f"{top_block[0]} ({top_block[1]}회)"
            decision = get_last_sell_elig_decision()
            reason = (get_last_sell_elig_top_reason() or "—")[:60]
            msg = (
                f"1. 현재 보유: {pos_n}종목\n"
                f"2. 최근 매도 시도: {attempt_str}\n"
                f"3. 매도 차단 Top: {top_block_str}\n"
                f"4. 최근 판단: {decision}\n"
                f"5. 이유: {reason}\n\n"
                "※ 실제 주문 없음. TP/SL/트레일 조건만 평가된 상태입니다."
            )
            QMessageBox.information(self, "매도 테스트(드라이런)", msg)
        except Exception as e:
            self._log.debug("sell test: %s", e)
            QMessageBox.information(self, "매도 테스트", "상태를 불러오지 못했습니다.")

    def _open_watchlist_manage(self, kind: str):
        """종목 제어 '관리' 클릭 시 리스트 관리 다이얼로그(추가/삭제) 열기."""
        try:
            if hasattr(self, "_on_manage_watchlist"):
                self._on_manage_watchlist()
            elif kind == "whitelist" and hasattr(self, "lst_whitelist"):
                self.lst_whitelist.setFocus()
            elif kind == "blacklist" and hasattr(self, "lst_blacklist"):
                self.lst_blacklist.setFocus()
        except Exception as e:
            self._log.debug("watchlist manage open: %s", e)

    def _update_run_status_card(self):
        """실행 상태 · 오늘 전략 요약 카드 갱신 (표준 포맷)."""
        try:
            from app.strategy.runner import _RUNNING, _SESSION_SNAPSHOT_SYMBOLS
            main = self.parent()
            while main and not hasattr(main, "_get_settings_cached"):
                main = main.parent()
            live = False
            avail = 0.0
            aggr_display = "중립"
            order_krw = 0
            snapshot_n = 0
            line2 = "KRW 잔고: —"
            if main and hasattr(main, "_get_settings_cached"):
                s = main._get_settings_cached()
                live = bool(getattr(s, "live_trade", False))
                stg = getattr(s, "strategy", None)
                if stg:
                    aggr = getattr(stg, "aggressiveness", "neutral") or "neutral"
                    aggr_display = {"conservative": "보수적", "neutral": "중립", "aggressive": "공격적"}.get(aggr, "중립")
                    order_krw = int(getattr(stg, "order_amount_krw", 0) or 0)
                try:
                    from app.services.order_service import OrderService, _LAST_KRW_LOG_INFO
                    svc = OrderService()
                    svc.set_settings(s)
                    avail = svc._compute_available_krw()
                    if avail == 0.0:
                        bal, lck, buf = _LAST_KRW_LOG_INFO
                        line2 = f"KRW 잔고: {bal:,.0f}원 (safety buffer {buf:,.0f}원 차감 → 가용 0원)"
                    else:
                        line2 = f"KRW 잔고: {avail:,.0f}원"
                except Exception:
                    line2 = "KRW 잔고: —"
                if _SESSION_SNAPSHOT_SYMBOLS is not None:
                    snapshot_n = len(_SESSION_SNAPSHOT_SYMBOLS)
            status = "RUNNING ●" if _RUNNING else "STOPPED"
            mode = "실매매" if live else "모의매매"
            line1 = f"[{status}] {mode}"
            line3 = f"오늘 전략: {aggr_display} | 1회 주문: {order_krw:,}원 | 스냅샷: {snapshot_n}종목"
            last = (self._last_event_message or "—").strip()[:80]
            line4 = f"마지막 AI 판단: {last}"
            # SELL 상태 카드: 보유 N개 | 최근 매도시도 | 매도 차단 Top
            try:
                # P0-[2]: Holdings SSOT 사용
                from app.services.holdings_service import fetch_live_holdings
                from app.strategy.runner import get_last_sell_attempt_ts, get_last_sell_block_reason_counter, get_last_exit_source
                holdings_data = fetch_live_holdings(force=False)
                pos_n = len(holdings_data.get("items", [])) if holdings_data.get("ok") else 0
                ts = get_last_sell_attempt_ts()
                import time
                if ts and ts > 0:
                    age_min = int((time.time() - ts) / 60)
                    sell_attempt_str = f"{age_min}분전" if age_min < 60 else "1시간+"
                else:
                    sell_attempt_str = "없음"
                counter = get_last_sell_block_reason_counter() or {}
                top_block = (sorted(counter.items(), key=lambda x: -x[1])[:1] or [("—", 0)])[0][0]
                exit_src = get_last_exit_source()
                exit_hint = f" | ⚠ exit_source={exit_src}" if exit_src in ("ai_missing", "ai_no_threshold") else ""
                line5 = f"보유종목 {pos_n}개 | 최근 매도시도: {sell_attempt_str} | 매도 차단Top: {top_block}{exit_hint}"
            except Exception:
                line5 = "보유종목 — | 최근 매도시도: — | 매도 차단Top: —"
            self.lbl_run_status.setText(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}")
        except Exception as e:
            self._log.debug("run status update: %s", e)

    def _load_order_and_downscale_from_settings(self):
        """1회 주문금액·다운스케일 옵션 초기값 로드."""
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, "_get_settings_cached"):
                main_window = main_window.parent()
            if not main_window:
                return
            settings = main_window._get_settings_cached()
            if not settings or not hasattr(settings, "strategy"):
                return
            stg = settings.strategy
            if hasattr(self, "chk_allow_downscale"):
                self.chk_allow_downscale.setChecked(bool(getattr(stg, "allow_downscale_order_amount", False)))
                if hasattr(self, "lbl_downscale_desc"):
                    if getattr(stg, "allow_downscale_order_amount", False):
                        self.lbl_downscale_desc.setText("잔고/한도 범위 내에서 금액을 자동 축소하여 주문합니다. (최소 5,000원)")
                    else:
                        self.lbl_downscale_desc.setText("설정한 금액 그대로만 주문 시도합니다. 잔고/한도 부족 시 주문하지 않습니다.")
            if hasattr(self, "spn_order_amount"):
                self.spn_order_amount.setValue(int(getattr(stg, "order_amount_krw", 10000) or 10000))
            if hasattr(self, "spn_max_invest_cap"):
                self.spn_max_invest_cap.setValue(int(getattr(stg, "max_invest_cap_krw", 0) or 0))
            aggr = getattr(stg, "aggressiveness", "neutral") or "neutral"
            if aggr == "conservative" and hasattr(self, "radio_aggr_conservative"):
                self.radio_aggr_conservative.setChecked(True)
            elif aggr == "aggressive" and hasattr(self, "radio_aggr_aggressive"):
                self.radio_aggr_aggressive.setChecked(True)
            else:
                if hasattr(self, "radio_aggr_neutral"):
                    self.radio_aggr_neutral.setChecked(True)
            # 🔷 로테이션 A안 설정 로드
            rot = getattr(stg, "rotation", None) or (stg.get("rotation") if isinstance(stg, dict) else None) or {}
            if hasattr(self, "chk_rotation_enabled"):
                self.chk_rotation_enabled.setChecked(bool(rot.get("enabled", False)))
            if hasattr(self, "spn_rotation_interval"):
                self.spn_rotation_interval.setValue(int(rot.get("interval_min", 30)))
            if hasattr(self, "spn_rotation_count"):
                self.spn_rotation_count.setValue(int(rot.get("count", 1)))
        except Exception as e:
            self._log.debug("load order/downscale: %s", e)

    def _on_external_trade_detected(self, payload):
        """외부 거래 감지 시 UI 알림 (최근 AI 판단은 투자현황탭에서 처리)."""
        try:
            # 외부 거래 감지 이벤트는 투자현황탭에서 처리됨
            pass
        except Exception:
            pass

    def _update_preflight_display(self):
        """사전 점검 결과 표시 (메인 윈도우 _preflight_check 호출)."""
        try:
            if not hasattr(self, "lbl_preflight"):
                return
            main = self._owner or self.parent()
            while main and not hasattr(main, "_preflight_check"):
                main = main.parent() if hasattr(main, "parent") else None
            if main:
                ok, msg = main._preflight_check()
                self.lbl_preflight.setText(msg)
                if not ok:
                    self.lbl_preflight.setStyleSheet("QLabel { font-size: 12px; padding: 6px; background: #fff3cd; color: #856404; border-radius: 4px; }")
                else:
                    self.lbl_preflight.setStyleSheet("QLabel { font-size: 12px; padding: 6px; background: #f8f9fa; border-radius: 4px; }")
            else:
                self.lbl_preflight.setText("사전 점검: 실행 버튼 위에서 확인됩니다.")
        except Exception as e:
            self._log.debug("preflight display: %s", e)

    def showEvent(self, event):
        """탭 표시 시 사전 점검·실행 상태 갱신."""
        super().showEvent(event)
        self._update_preflight_display()
        self._update_run_status_card()
    
    def _build_left_column(self):
        """Build left column with main controls"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(6)  # Reduced spacing
        left_layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
        
        # Strategy Mode
        mode_group = QGroupBox("")  # 제목 완전히 제거
        mode_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)
        
        # 표준 섹션: AI 매매 성향
        header = self._create_standard_section_header("AI 매매 성향")
        mode_layout.addWidget(header)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        radio_row = QHBoxLayout()
        self.radio_avoid = QRadioButton("보수적")
        self.radio_avoid.setToolTip("신호가 강할 때만 진입, 회전 느림")
        self.radio_trend = QRadioButton("중립")
        self.radio_trend.setToolTip("균형 잡힌 진입/회전")
        self.radio_ai = QRadioButton("공격적")
        self.radio_ai.setToolTip("진입 빠름, 회전 적극적")
        self.radio_ai.setChecked(True)
        radio_row.addWidget(self.radio_avoid)
        radio_row.addWidget(self.radio_trend)
        radio_row.addWidget(self.radio_ai)
        radio_row.addStretch()
        content_layout.addLayout(radio_row)
        mode_help = QLabel("AI가 진입/청산 타이밍을 주도합니다. 사용자는 성향만 선택하세요.")
        mode_help.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        mode_help.setWordWrap(True)
        content_layout.addWidget(mode_help)
        mode_layout.addWidget(content_widget)
        left_layout.addWidget(mode_group)
        
        # Order/Risk Limits
        risk_group = QGroupBox("")  # 제목 완전히 제거
        risk_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        risk_main_layout = QVBoxLayout(risk_group)
        risk_main_layout.setContentsMargins(0, 0, 0, 0)
        risk_main_layout.setSpacing(0)
        
        header = self._create_standard_section_header("주문 설정")
        risk_main_layout.addWidget(header)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        left_risk_widget = QWidget()
        left_risk_layout = QFormLayout(left_risk_widget)
        left_risk_layout.setSpacing(6)
        self.spn_max_invest = QSpinBox()
        self.spn_max_invest.setRange(1000, 100_000_000)
        self.spn_max_invest.setSingleStep(10_000)
        try:
            total_asset = self._get_total_asset()
            if total_asset > 0:
                self.spn_max_invest.setValue(int(total_asset))
            else:
                self.spn_max_invest.setValue(1_000_000)
        except Exception:
            self.spn_max_invest.setValue(1_000_000)
        self.spn_max_invest.setGroupSeparatorShown(True)
        self.spn_max_invest.valueChanged.connect(self._on_max_invest_changed)
        left_risk_layout.addRow("최대 투자금\\", self.spn_max_invest)
        # 한 줄: 1회 주문금액 | 최대 투자금액 | 보유자산 전체 기준 (0폭 방지: minWidth + SizePolicy)
        row_order = QWidget()
        row_order_layout = QHBoxLayout(row_order)
        row_order_layout.setContentsMargins(0, 0, 0, 0)
        row_order_layout.setSpacing(8)
        row_order_layout.addWidget(QLabel("1회 주문금액(원)"))
        self.spn_order_amount = QSpinBox()
        self.spn_order_amount.setRange(1000, 100_000_000)
        self.spn_order_amount.setValue(10_000)
        self.spn_order_amount.setSingleStep(1000)
        self.spn_order_amount.setGroupSeparatorShown(True)
        self.spn_order_amount.setMinimumWidth(140)
        self.spn_order_amount.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        row_order_layout.addWidget(self.spn_order_amount)
        row_order_layout.addWidget(QLabel(" | "))
        row_order_layout.addWidget(QLabel("최대 투자금액(원)"))
        self.spn_max_invest_cap = QSpinBox()
        self.spn_max_invest_cap.setRange(0, 100_000_000)
        self.spn_max_invest_cap.setValue(0)
        self.spn_max_invest_cap.setSingleStep(10000)
        self.spn_max_invest_cap.setGroupSeparatorShown(True)
        self.spn_max_invest_cap.setSpecialValueText("제한 없음")
        self.spn_max_invest_cap.setMinimumWidth(140)
        self.spn_max_invest_cap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.spn_max_invest_cap.setToolTip("총 보유 평가금액(노출)이 이 금액을 넘으면 추가 매수를 차단합니다. (0=제한 없음)")
        row_order_layout.addWidget(self.spn_max_invest_cap)
        row_order_layout.addStretch(1)
        left_risk_layout.addRow("", row_order)
        self.chk_allow_downscale = QCheckBox("잔고 부족 시 주문금액 자동 축소 허용")
        self.chk_allow_downscale.setChecked(False)
        self.chk_allow_downscale.setToolTip(
            "OFF: 설정한 금액 그대로만 주문 시도. 잔고/한도 부족 시 주문하지 않습니다.\n"
            "ON: 잔고 범위 내에서 금액을 자동 조정해 주문합니다."
        )
        left_risk_layout.addRow("", self.chk_allow_downscale)
        content_layout.addWidget(left_risk_widget)
        
        # 고급 모드 펼치기(▶): exit_mode + 손절/익절
        self._advanced_visible = False
        self.btn_advanced_toggle = QPushButton("고급 모드 펼치기(▶)")
        self.btn_advanced_toggle.setCheckable(True)
        self.btn_advanced_toggle.setChecked(False)
        self.btn_advanced_toggle.toggled.connect(self._on_advanced_toggle_clicked)
        content_layout.addWidget(self.btn_advanced_toggle)
        self.frm_advanced = QFrame()
        self.frm_advanced.setFrameShape(QFrame.StyledPanel)
        adv_layout = QFormLayout(self.frm_advanced)
        adv_layout.setSpacing(6)
        self.cmb_exit_mode = QComboBox()
        self.cmb_exit_mode.addItems(["ai", "user", "trail"])
        self.cmb_exit_mode.setCurrentText("ai")
        self.cmb_exit_mode.setToolTip("ai: AI 주도 청산 | user: 수동 | trail: 트레일링")
        adv_layout.addRow("청산 모드(exit_mode)", self.cmb_exit_mode)
        self.spn_stop_loss = QDoubleSpinBox()
        self.spn_stop_loss.setRange(0.0, 20.0)  # 0.0 허용 (AI 판단)
        self.spn_stop_loss.setSuffix("%")
        self.spn_stop_loss.setValue(0.0)
        self.lbl_stop_loss_status = QLabel("")  # 초기값은 _update_tp_sl_status()에서 설정
        self.lbl_stop_loss_status.setStyleSheet("color: #666; font-size: 10px;")
        hbox_sl = QHBoxLayout()
        hbox_sl.addWidget(self.spn_stop_loss)
        hbox_sl.addWidget(self.lbl_stop_loss_status)
        hbox_sl.addStretch()
        adv_layout.addRow("손절", hbox_sl)
        self.spn_stop_loss.valueChanged.connect(self._update_tp_sl_status)
        
        self.spn_take_profit = QDoubleSpinBox()
        self.spn_take_profit.setRange(0.0, 20.0)  # 0.0 허용 (AI 판단)
        self.spn_take_profit.setSuffix("%")
        self.spn_take_profit.setValue(0.0)
        self.lbl_take_profit_status = QLabel("")  # 초기값은 _update_tp_sl_status()에서 설정
        self.lbl_take_profit_status.setStyleSheet("color: #666; font-size: 10px;")
        hbox_tp = QHBoxLayout()
        hbox_tp.addWidget(self.spn_take_profit)
        hbox_tp.addWidget(self.lbl_take_profit_status)
        hbox_tp.addStretch()
        adv_layout.addRow("익절", hbox_tp)
        self.spn_take_profit.valueChanged.connect(self._update_tp_sl_status)
        # 초기 상태 갱신 (값이 이미 설정된 경우)
        self._update_tp_sl_status()
        self.frm_advanced.setVisible(False)
        content_layout.addWidget(self.frm_advanced)
        
        risk_main_layout.addWidget(content_widget)
        
        left_layout.addWidget(risk_group)
        
        # Technical Indicators
        inds_group = QGroupBox("")  # 제목 완전히 제거
        inds_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        inds_layout = QVBoxLayout(inds_group)
        inds_layout.setContentsMargins(0, 0, 0, 0)
        inds_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가 (인포박스 포함)
        header = self._create_standard_section_header("기술적 지표")
        inds_layout.addWidget(header)
        inds_content_widget = QWidget()
        inds_content_layout = QVBoxLayout(inds_content_widget)
        inds_content_layout.setContentsMargins(8, 8, 8, 8)
        inds_content_layout.setSpacing(6)
        
        # Indicator checkboxes in single row
        inds_row = QHBoxLayout()
        inds_row.setSpacing(8)
        
        self.chk_rsi = QCheckBox("RSI")
        self.chk_rsi.setChecked(True)
        inds_row.addWidget(self.chk_rsi)
        
        self.chk_bb = QCheckBox("Bollinger Bands")
        self.chk_bb.setChecked(True)
        inds_row.addWidget(self.chk_bb)
        
        self.chk_macd = QCheckBox("MACD")
        self.chk_macd.setChecked(True)
        inds_row.addWidget(self.chk_macd)
        
        self.chk_ma = QCheckBox("이평")
        self.chk_ma.setChecked(True)
        inds_row.addWidget(self.chk_ma)
        
        self.chk_atr = QCheckBox("ATR")
        self.chk_atr.setChecked(False)
        inds_row.addWidget(self.chk_atr)
        
        self.chk_stoch = QCheckBox("Stochastic")
        self.chk_stoch.setChecked(False)
        inds_row.addWidget(self.chk_stoch)
        
        inds_row.addStretch()  # Push checkboxes to left
        inds_content_layout.addLayout(inds_row)
        
        # Logic options
        logic_layout = QHBoxLayout()
        logic_layout.setSpacing(6)
        self.cmb_logic = QComboBox()
        self.cmb_logic.addItems(["AND", "OR"])
        self.cmb_logic.setCurrentText("AND")
        logic_layout.addWidget(QLabel("논리:"))
        logic_layout.addWidget(self.cmb_logic)
        
        # AI 판단 우선을 논리와 같은 줄로 이동
        self.chk_ai_judge = QCheckBox("AI 판단 우선")
        logic_layout.addWidget(self.chk_ai_judge)
        logic_layout.addStretch()
        
        inds_content_layout.addLayout(logic_layout)
        inds_layout.addWidget(inds_content_widget)
        left_layout.addWidget(inds_group)
        
        # External/Advanced Conditions
        ext_group = QGroupBox("")  # 제목 완전히 제거
        ext_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        ext_layout = QVBoxLayout(ext_group)
        ext_layout.setContentsMargins(0, 0, 0, 0)
        ext_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("외부/고급 조건")
        ext_layout.addWidget(header)
        # 내용 영역
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Checkboxes in single row
        ext_row = QHBoxLayout()
        ext_row.setSpacing(8)
        
        self.chk_macro_news = QCheckBox("매크로 뉴스 차단")
        self.chk_macro_news.setChecked(False)
        ext_row.addWidget(self.chk_macro_news)
        
        self.chk_exchange_check = QCheckBox("거래소 점검 차단")
        self.chk_exchange_check.setChecked(True)
        ext_row.addWidget(self.chk_exchange_check)
        
        self.chk_mtf_mix = QCheckBox("MTF 믹스")
        self.chk_mtf_mix.setChecked(False)
        ext_row.addWidget(self.chk_mtf_mix)
        
        self.chk_cross_asset = QCheckBox("크로스자산 필터")
        self.chk_cross_asset.setChecked(False)
        ext_row.addWidget(self.chk_cross_asset)
        
        ext_row.addStretch()  # Push checkboxes to left
        content_layout.addLayout(ext_row)
        
        ext_layout.addWidget(content_widget)
        
        left_layout.addWidget(ext_group)
        
        # AI Auto Recommendation
        ai_group = QGroupBox("")  # 제목 완전히 제거
        ai_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("AI 자동 추천")
        ai_layout.addWidget(header)
        # 내용 영역
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Buttons row
        ai_top = QHBoxLayout()
        ai_top.setSpacing(6)
        ai_top.addStretch()
        
        self.btn_ai_refresh = QPushButton("새로고침")
        self.btn_ai_refresh.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; }")
        ai_top.addWidget(self.btn_ai_refresh)
        
        self.btn_ai_apply = QPushButton("적용하기")
        self.btn_ai_apply.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; background: #28a745; color: white; }")
        self.btn_ai_apply.setEnabled(False)  # Disabled until recommendation is generated
        ai_top.addWidget(self.btn_ai_apply)
        
        content_layout.addLayout(ai_top)
        
        # AI recommendation display
        self.txt_ai_reason = QTextEdit()
        self.txt_ai_reason.setMinimumHeight(120)
        self.txt_ai_reason.setMaximumHeight(150)
        self.txt_ai_reason.setReadOnly(True)
        self.txt_ai_reason.setPlaceholderText("AI가 시장 상황을 분석하여 전략 설정을 추천합니다...")
        content_layout.addWidget(self.txt_ai_reason)
        
        ai_layout.addWidget(content_widget)
        
        left_layout.addWidget(ai_group)
        left_layout.addStretch()
        
        return left_widget
    
    def _build_right_column(self):
        """Build right column with environment + risk + watchlist"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(6)  # Reduced spacing
        right_layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
        
        # Market Environment
        market_group = QGroupBox("")  # 제목 완전히 제거
        market_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        market_layout = QVBoxLayout(market_group)
        market_layout.setContentsMargins(0, 0, 0, 0)
        market_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("시장 환경 변수")
        market_layout.addWidget(header)
        # 내용 영역
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Volatility
        content_layout.addWidget(QLabel("변동성:"))
        self.cmb_volatility = QComboBox()
        self.cmb_volatility.addItems(["낮음", "보통", "높음"])
        self.cmb_volatility.setCurrentText("보통")
        content_layout.addWidget(self.cmb_volatility)
        
        # Liquidity
        content_layout.addWidget(QLabel("유동성:"))
        self.cmb_liquidity = QComboBox()
        self.cmb_liquidity.addItems(["낮음", "보통", "높음"])
        self.cmb_liquidity.setCurrentText("보통")
        content_layout.addWidget(self.cmb_liquidity)
        
        # Session
        content_layout.addWidget(QLabel("세션:"))
        self.cmb_session = QComboBox()
        self.cmb_session.addItems(["아시아", "유럽", "미국"])
        self.cmb_session.setCurrentText("아시아")
        content_layout.addWidget(self.cmb_session)
        
        content_layout.addStretch()  # Push items to left
        
        market_layout.addWidget(content_widget)
        
        right_layout.addWidget(market_group)
        
        # Risk Management
        risk_group = QGroupBox("")  # 제목 완전히 제거
        risk_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        risk_layout = QVBoxLayout(risk_group)
        risk_layout.setContentsMargins(0, 0, 0, 0)
        risk_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("리스크 관리")
        risk_layout.addWidget(header)
        # 내용 영역
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Position size
        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(6)
        pos_layout.addWidget(QLabel("포지션 비중(1종목 최대)"))
        self.sld_pos_size = QSlider(Qt.Horizontal)
        self.sld_pos_size.setRange(1, 100)  # 1% ~ 100%로 수정
        self.sld_pos_size.setValue(2.5)  # 기본값 2.5%로 수정
        self.lbl_pos_size = QLabel("2.5%")
        pos_layout.addWidget(self.sld_pos_size)
        pos_layout.addWidget(self.lbl_pos_size)
        content_layout.addLayout(pos_layout)
        
        # 포지션 비중 설명
        pos_desc = QLabel("(주문가능 KRW 기준)")
        pos_desc.setStyleSheet("QLabel { font-size: 10px; color: #666; margin-left: 6px; }")
        content_layout.addWidget(pos_desc)
        
        # Risk/Reward ratio
        rr_layout = QHBoxLayout()
        rr_layout.setSpacing(6)
        rr_layout.addWidget(QLabel("손익비(RR)"))
        self.sld_rr_ratio = QSlider(Qt.Horizontal)
        self.sld_rr_ratio.setRange(10, 50)
        self.sld_rr_ratio.setValue(22)
        self.lbl_rr_ratio = QLabel("2.2")
        rr_layout.addWidget(self.sld_rr_ratio)
        rr_layout.addWidget(self.lbl_rr_ratio)
        content_layout.addLayout(rr_layout)
        
        # Daily loss limit
        loss_layout = QHBoxLayout()
        loss_layout.setSpacing(6)
        loss_layout.addWidget(QLabel("일일 손실 한도(%)"))
        self.sld_daily_loss = QSlider(Qt.Horizontal)
        self.sld_daily_loss.setRange(5, 100)
        self.sld_daily_loss.setValue(35)
        self.lbl_daily_loss = QLabel("3.5%")
        loss_layout.addWidget(self.sld_daily_loss)
        loss_layout.addWidget(self.lbl_daily_loss)
        content_layout.addLayout(loss_layout)
        
        risk_layout.addWidget(content_widget)
        
        right_layout.addWidget(risk_group)
        
        # Psychology & Behavior Control
        psych_group = QGroupBox("")  # 제목 완전히 제거
        psych_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        psych_layout = QVBoxLayout(psych_group)
        psych_layout.setContentsMargins(0, 0, 0, 0)
        psych_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("심리·행동 제어")
        psych_layout.addWidget(header)
        # 내용 영역
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Consecutive loss limit
        content_layout.addWidget(QLabel("연속 손실 제한:"))
        self.spn_consec_loss = QSpinBox()
        self.spn_consec_loss.setRange(1, 10)
        self.spn_consec_loss.setValue(3)
        self.spn_consec_loss.setSuffix("회")
        content_layout.addWidget(self.spn_consec_loss)
        
        # Consecutive win limit
        content_layout.addWidget(QLabel("연속 승리 제한:"))
        self.spn_consec_win = QSpinBox()
        self.spn_consec_win.setRange(1, 10)
        self.spn_consec_win.setValue(5)
        self.spn_consec_win.setSuffix("회")
        content_layout.addWidget(self.spn_consec_win)
        
        # Cooldown wait
        content_layout.addWidget(QLabel("쿨다운(초):"))
        self.spn_behavior_cooldown = QSpinBox()
        self.spn_behavior_cooldown.setRange(60, 3600)
        self.spn_behavior_cooldown.setValue(300)
        self.spn_behavior_cooldown.setSuffix("초")
        content_layout.addWidget(self.spn_behavior_cooldown)
        
        content_layout.addStretch()  # Push items to left
        
        psych_layout.addWidget(content_widget)
        
        right_layout.addWidget(psych_group)
        
        # Watchlist Summary
        watchlist_group = QGroupBox("")  # 제목 완전히 제거
        watchlist_group.setStyleSheet("QGroupBox { border: 1px solid #0078d4; }")
        watchlist_layout = QVBoxLayout(watchlist_group)
        watchlist_layout.setContentsMargins(0, 0, 0, 0)
        watchlist_layout.setSpacing(0)
        
        # 표준 섹션 헤더 추가
        header = self._create_standard_section_header("Watchlist 요약")
        watchlist_layout.addWidget(header)
        
        # 내용 영역
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # White list
        white_layout = QVBoxLayout()
        white_layout.setSpacing(6)
        white_layout.addWidget(QLabel("화이트 리스트"))
        self.lst_whitelist = QListWidget()
        self.lst_whitelist.setMinimumHeight(180)
        self.lst_whitelist.setMaximumHeight(200)
        self.lst_whitelist.setMinimumWidth(250)  # 심볼창 너비 더 확대
        # 셀 크기 조정 가능하도록 설정
        self.lst_whitelist.setResizeMode(QListWidget.Adjust)
        self.lst_whitelist.setUniformItemSizes(False)  # 각 항목 크기 다르게 허용
        # 컬럼 너비 자동 조정 활성화
        self.lst_whitelist.setFont(self.font())  # 현재 폰트 설정
        white_layout.addWidget(self.lst_whitelist)
        content_layout.addLayout(white_layout)
        
        # Black list
        black_layout = QVBoxLayout()
        black_layout.setSpacing(6)
        black_layout.addWidget(QLabel("블랙 리스트"))
        self.lst_blacklist = QListWidget()
        self.lst_blacklist.setMinimumHeight(180)
        self.lst_blacklist.setMaximumHeight(200)
        self.lst_blacklist.setMinimumWidth(250)  # 심볼창 너비 더 확대
        # 셀 크기 조정 가능하도록 설정
        self.lst_blacklist.setResizeMode(QListWidget.Adjust)
        self.lst_blacklist.setUniformItemSizes(False)  # 각 항목 크기 다르게 허용
        # 컬럼 너비 자동 조정 활성화
        self.lst_blacklist.setFont(self.font())  # 현재 폰트 설정
        black_layout.addWidget(self.lst_blacklist)
        content_layout.addLayout(black_layout)
        
        # Manage button
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.addStretch()
        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)
        
        watchlist_layout.addWidget(content_widget)
        
        right_layout.addWidget(watchlist_group)
        
        # Info Box and Save Button container
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(6)
        
        # Info Box (moved here)
        bottom_layout.addWidget(self.info_label)
        bottom_layout.addStretch()
        
        # Strategy Save Button
        bottom_layout.addWidget(self.lbl_dirty_state)
        self.btn_save_apply = QPushButton("전략 저장")
        self._save_btn_base_text = "전략 저장"  # ✅ P2-5: 원래 텍스트 저장
        self.btn_save_apply.setStyleSheet("QPushButton { font-weight: bold; padding: 10px 20px; background: #007bff; color: white; }")
        self.btn_save_apply.setMinimumWidth(120)
        bottom_layout.addWidget(self.btn_save_apply)
        
        right_layout.addWidget(bottom_container)
        
        right_layout.addStretch()
        # Save button
        self.btn_save_apply.clicked.connect(self._on_save_apply)
        
        return right_widget
    
    def _connect_signals(self):
        """리디자인: AI 성향·주문·워치리스트·저장만 연결."""
        if hasattr(self, "radio_aggr_conservative"):
            self.radio_aggr_conservative.toggled.connect(self._on_aggr_radio_changed)
        if hasattr(self, "radio_aggr_neutral"):
            self.radio_aggr_neutral.toggled.connect(self._on_aggr_radio_changed)
        if hasattr(self, "radio_aggr_aggressive"):
            self.radio_aggr_aggressive.toggled.connect(self._on_aggr_radio_changed)
        if hasattr(self, "spn_order_amount"):
            self.spn_order_amount.valueChanged.connect(self._mark_dirty)
            if hasattr(self, "spn_max_invest_cap"):
                self.spn_max_invest_cap.valueChanged.connect(self._mark_dirty)
            if hasattr(self, "chk_allow_downscale"):
                self.chk_allow_downscale.toggled.connect(self._mark_dirty)
        if hasattr(self, "chk_rotation_enabled"):
            self.chk_rotation_enabled.toggled.connect(self._on_rotation_enabled_changed)
        if hasattr(self, "spn_rotation_interval"):
            self.spn_rotation_interval.valueChanged.connect(self._mark_dirty)
        if hasattr(self, "spn_rotation_count"):
            self.spn_rotation_count.valueChanged.connect(self._mark_dirty)
        try:
            eventbus.subscribe("watchlist.apply.visible_symbols", self._on_watchlist_applied)
            eventbus.subscribe("watchlist.wb.changed", self._on_watchlist_wb_changed)
        except Exception as e:
            self._log.error("watchlist subscribe: %s", e)

    def _on_aggr_radio_changed(self):
        """AI 매매 성향 라디오 변경 시 Dirty 표시."""
        self._mark_dirty()

    def _update_tp_sl_status(self):
        """익절/손절 값 변경 시 판단 주체 상태 표시 갱신"""

        # 주문설정(표준 UI): 손절/익절 각각 분리 표시
        if hasattr(self, "spn_stop_loss_pct") and hasattr(self, "lbl_stop_mode"):
            sl = float(self.spn_stop_loss_pct.value() or 0.0)
            if sl <= 0.0:
                self.lbl_stop_mode.setText("→ AI 판단 모드")
                self.lbl_stop_mode.setStyleSheet("color: #0078d4; font-size: 10px;")
            else:
                self.lbl_stop_mode.setText("→ 사용자 지정값 적용")
                self.lbl_stop_mode.setStyleSheet("color: #666; font-size: 10px;")

        if hasattr(self, "spn_take_profit_pct") and hasattr(self, "lbl_tp_mode"):
            tp = float(self.spn_take_profit_pct.value() or 0.0)
            if tp <= 0.0:
                self.lbl_tp_mode.setText("→ AI 판단 모드")
                self.lbl_tp_mode.setStyleSheet("color: #0078d4; font-size: 10px;")
            else:
                self.lbl_tp_mode.setText("→ 사용자 지정값 적용")
                self.lbl_tp_mode.setStyleSheet("color: #666; font-size: 10px;")

        # 고급 모드 UI(하위호환): 상태 라벨만 유지
        if hasattr(self, "spn_stop_loss") and hasattr(self, "lbl_stop_loss_status"):
            sl_val = self.spn_stop_loss.value()
            if sl_val <= 0.0:
                self.lbl_stop_loss_status.setText("AI 판단 중")
                self.lbl_stop_loss_status.setStyleSheet("color: #0078d4; font-size: 10px;")
            else:
                self.lbl_stop_loss_status.setText("사용자 고정값 사용")
                self.lbl_stop_loss_status.setStyleSheet("color: #666; font-size: 10px;")

        if hasattr(self, "spn_take_profit") and hasattr(self, "lbl_take_profit_status"):
            tp_val = self.spn_take_profit.value()
            if tp_val <= 0.0:
                self.lbl_take_profit_status.setText("AI 판단 중")
                self.lbl_take_profit_status.setStyleSheet("color: #0078d4; font-size: 10px;")
            else:
                self.lbl_take_profit_status.setText("사용자 고정값 사용")
                self.lbl_take_profit_status.setStyleSheet("color: #666; font-size: 10px;")
    
    def _mark_dirty(self):
        """변경 시 Dirty 표시."""
        self._is_dirty = True
        self._update_dirty_indicator()
    
    def _on_watchlist_applied(self, payload):
        """워치리스트 탭에서 '반영' 버튼 클릭 시 호출됨 - Draft-only 모드"""
        try:
            self._log.info("[WATCHLIST] APPLIED_RX payload=%s", payload)
            
            # payload에서 whitelist/blacklist 추출 (하위호환 지원)
            whitelist = payload.get("whitelist", [])
            blacklist = payload.get("blacklist", [])
            
            # 타입 방어: list가 아닌 경우 list로 캐스팅
            if not isinstance(whitelist, list):
                whitelist = list(whitelist) if whitelist else []
            if not isinstance(blacklist, list):
                blacklist = list(blacklist) if blacklist else []
            
            # ✅ P1 SSOT FINAL: Draft-only 모드 - self._draft_strategy만 갱신
            if not hasattr(self, '_draft_strategy'):
                self._draft_strategy = {}
            
            self._draft_strategy['whitelist'] = whitelist
            self._draft_strategy['blacklist'] = blacklist
            self._log.info("[WATCHLIST] DRAFT_UPDATE_FROM_EVENT whitelist=%d blacklist=%d", len(whitelist), len(blacklist))
            
            # UI에 즉시 반영 (덮어쓰기)
            self._apply_watchlist_view(whitelist, blacklist, reason="applied_event")
            
            # Dirty 상태 설정
            self._is_dirty = True
            self._update_dirty_indicator()
            self._log.info("[WATCHLIST] DIRTY_SET reason=watchlist_applied_event")
            
            # 성공 메시지 및 로그 (임시 반영 톤 유지)
            self._log.info(f"[STRATEGY] watchlist applied to draft wl={len(whitelist)} bl={len(blacklist)}")
            self._info(f"⚠️ 워치리스트 변경이 임시 반영되었습니다. 저장/적용을 눌러 확정하세요. (화이트: {len(whitelist)}, 블랙: {len(blacklist)})")
            
        except Exception as e:
            self._log.error(f"Error handling watchlist apply: {e}")
            self._info("⚠️ 워치리스트 반영 중 오류가 발생했습니다.")
    
    def _on_watchlist_wb_changed(self, payload):
        """✅ SSOT: 워치리스트 체크 변경 시 즉시 덮어쓰기로 반영"""
        try:
            whitelist = payload.get("whitelist", [])
            blacklist = payload.get("blacklist", [])
            
            # ✅ 수신 로그: 전체 리스트 확인
            self._log.info(f"[STRATEGY] wb.changed received wl={len(whitelist)} bl={len(blacklist)} whitelist={whitelist} blacklist={blacklist} from {payload.get('source', 'unknown')}")
            
            # ✅ 리스트 위젯에 100% 덮어쓰기 (append/merge 금지)
            self._apply_watchlist_view(whitelist, blacklist, reason="wb_changed")
            
        except Exception as e:
            self._log.error(f"Error handling watchlist wb changed: {e}")
    
    def _apply_watchlist_view(self, whitelist, blacklist, reason=""):
        """✅ SSOT: 리스트 위젯에 항상 덮어쓰기 (append/merge 금지)"""
        try:
            # 화이트리스트: clear() 후 add()로 완전 덮어쓰기
            self.lst_whitelist.clear()
            for symbol in (whitelist or []):
                self.lst_whitelist.addItem(symbol)
            
            # 블랙리스트: clear() 후 add()로 완전 덮어쓰기
            self.lst_blacklist.clear()
            for symbol in (blacklist or []):
                self.lst_blacklist.addItem(symbol)
                
            wl_n = len(whitelist or [])
            wl_sample = list(whitelist or [])[:20]
            self._log.info(
                "[STRAT-WL] allowed_n=%d symbols=%s source=%s",
                wl_n,
                wl_sample,
                reason or "-",
            )
            self._log.debug(f"[STRATEGY] view overwritten: wl={len(whitelist or [])} bl={len(blacklist or [])} reason={reason}")
            
        except Exception as e:
            self._log.error(f"Error applying watchlist view: {e}")
    
    def _on_aggr_changed(self, value):
        """매매 적극성 변경 시 실시간 수치 표시 + 리스크 값 자동 조정 (단방향 연동)"""
        # ✅ 저장 중에는 자동 저장 방지
        if hasattr(self, '_saving_strategy') and self._saving_strategy:
            return
            
        try:
            lv = int(value)
            # 포지션 비중을 percent 단위로 계산
            pos = max(1.0, 1.0 + 1.5 * (lv - 1))  # 1% ~ 25% 범위
            rr = 1.2 + 0.2 * (lv - 1)
            cd = max(30, 600 - 50 * (lv - 1))
            dl = max(0.5, 2.5 - 0.2 * (lv - 1))  # percent 단위
            
            # 실시간 수치 표시 라벨 업데이트
            self.lbl_aggr_values.setText(f"포지션 비중(1종목 최대): {pos:.1f}% | 손익비(RR): {rr:.1f} | 쿨다운: {cd}초 | 일일 손실 한도(%): {dl:.1f}%")
            
            # 볼륨→리스크 단방향 연동: 리스크 슬라이더 값 자동 조정
            if hasattr(self, 'sld_pos_size'):
                self.sld_pos_size.blockSignals(True)
                self.sld_pos_size.setValue(int(pos))  # percent 값으로 직접 설정
                self.sld_pos_size.blockSignals(False)
                self.lbl_pos_size.setText(f"{pos:.1f}%")
                self._log.info(f"[POS] source=aggr pos={pos:.1f} path=draft.pos_size_pct")
            
            # ✅ P0-7: 프리셋 연동 (rr_ratio & daily_loss_limit_pct)
            preset_table = {1: (1.2, 2.5), 3: (1.6, 3.0), 5: (2.0, 3.5), 7: (2.4, 4.0), 9: (2.8, 4.5), 10: (3.0, 5.0)}
            # 가장 가까운 키로 스냅
            nearest_level = min(preset_table.keys(), key=lambda k: abs(k - lv))
            preset_rr, preset_dll = preset_table[nearest_level]
            
            self._applying_aggr_preset = True
            try:
                # RR 연동 (override가 아닐 경우만)
                if not self._manual_rr_override and hasattr(self, 'sld_rr_ratio'):
                    self.sld_rr_ratio.blockSignals(True)
                    self.sld_rr_ratio.setValue(int(preset_rr * 10))
                    self.sld_rr_ratio.blockSignals(False)
                    self.lbl_rr_ratio.setText(f"{preset_rr:.1f}")
                    self._draft_strategy['rr_ratio'] = preset_rr
                    self._log.info(f"[RR] source=aggr_preset rr={preset_rr:.1f} path=draft.rr_ratio")
                
                # DLL 연동 (override가 아닐 경우만)
                if not self._manual_dll_override:
                    self._set_daily_loss_pct(preset_dll, reason="aggr_preset")
            finally:
                self._applying_aggr_preset = False
            
            # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태)
            self._draft_strategy['pos_size_pct'] = pos
            self._draft_strategy['rr_ratio'] = rr
            self._draft_strategy['cooldown_sec'] = cd
            self._draft_strategy['aggressiveness_level'] = lv
            
            # ✅ P0-SYNC-DLL-LAST: DLL은 helper로 동기화 (Draft 직접 수정 금지)
            self._set_daily_loss_pct(dl, reason="aggr_manual")
            
            # ✅ P2-5: Dirty 상태 설정
            self._is_dirty = True
            self._update_dirty_indicator()

            # ✅ 즉시 표시 갱신(저장/적용 전이라도 "편집중 프리뷰"를 보여줌)
            try:
                self._update_ai_strategy_snapshot()
            except Exception:
                pass
            
            # 볼륨→심리행동제어 쿨다운 연동 (단일화: 심리행동제어 쿨다운이 정답)
            if hasattr(self, 'spn_behavior_cooldown'):
                self.spn_behavior_cooldown.blockSignals(True)
                self.spn_behavior_cooldown.setValue(cd)  # 심리행동제어 쿨다운으로 설정
                self.spn_behavior_cooldown.blockSignals(False)
                self._log.info(f"[CD] source=aggr cd={cd} path=settings.strategy.cooldown_sec")
            
            # 수치 조정 시 AI 버튼을 주황색으로 변경
            self.btn_all_ai.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; background: #ff6b35; color: white; border: none; border-radius: 3px; }")
            
            # 디바운스를 통한 UI 표시만 변경 (전략요약 갱신 금지)
            if hasattr(self, '_aggr_update_timer'):
                self._aggr_update_timer.stop()
            
            from PySide6.QtCore import QTimer
            if not hasattr(self, '_aggr_update_timer'):
                self._aggr_update_timer = QTimer()
                self._aggr_update_timer.setSingleShot(True)
                # self._aggr_update_timer.timeout.connect(lambda: self._update_summary("aggr_changed"))
            
            self._aggr_update_timer.start(300)
            
        except Exception as e:
            self._log.error(f"Error in aggressiveness change: {e}")
    
    def _on_all_ai_clicked(self):
        """모두 AI 버튼 클릭 시 처리"""
        # 모두AI 상태 토글
        self._ai_master_enabled = not self._ai_master_enabled
        
        if self._ai_master_enabled:
            # 활성화: 버튼을 초록색으로 변경
            self.btn_all_ai.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; background: #28a745; color: white; border: none; border-radius: 3px; }")
            
            # AI 자동 통제 활성화 로직 (추후 구현)
            if hasattr(self, 'info_label'):
                self.info_label.setText("AI 자동 통제가 활성화되었습니다. AI가 실시간으로 전략을 조정합니다.")
            
            self._log.info("All AI mode activated")

            # ✅ All AI ON 시점에 avoid 고착 방지(최소 수정)
            try:
                cur_mode = self._get_strategy_mode_from_ui()
                if cur_mode == "avoid":
                    self._set_strategy_mode_ui("trend_following", reason="all_ai_on")
                    self._log.warning("[AI-MASTER] avoid -> trend_following (auto) source=all_ai_on")
                    self._is_dirty = True
                    self._update_dirty_indicator()
                    # 자동 커밋(저장)
                    try:
                        self._on_save_apply()
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            # 비활성화: 버튼을 주황색으로 변경
            self.btn_all_ai.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; background: #ff6b35; color: white; border: none; border-radius: 3px; }")
            
            if hasattr(self, 'info_label'):
                self.info_label.setText("AI 자동 통제가 비활성화되었습니다.")
            
            self._log.info("All AI mode deactivated")

    def _get_strategy_mode_from_ui(self) -> str:
        """리디자인: 전략 모드는 항상 AI 판단."""
        return "ai"

    def _set_strategy_mode_ui(self, mode: str, *, reason: str = "") -> None:
        """SSOT 문자열(strategy_mode)을 UI 라디오에 반영"""
        try:
            m = str(mode or "").strip().lower()
            if m == "avoid" and hasattr(self, "radio_avoid"):
                self.radio_avoid.setChecked(True)
            elif m in ("trend_following", "trend", "momentum") and hasattr(self, "radio_trend"):
                self.radio_trend.setChecked(True)
            else:
                if hasattr(self, "radio_ai"):
                    self.radio_ai.setChecked(True)
            self._log.info(f"[STRATEGY-MODE] ui_set mode={m} reason={reason}")
        except Exception:
            pass

    def _normalize_pct_value(self, v: object, default: float) -> float:
        """percent SSOT 정규화: 0~1로 들어오면 *100 교정."""
        try:
            x = float(v)
        except Exception:
            return float(default)
        # 0.03 같은 ratio로 들어오면 percent로 교정
        if 0.0 < x <= 1.0:
            return x * 100.0
        return x

    def _on_ai_strategy_suggested(self, payload: dict) -> None:
        """ai.reco.strategy_suggested 수신 시(All AI ON인 경우) suggested를 UI+SSOT에 반영"""
        try:
            if not getattr(self, "_ai_master_enabled", False):
                return
            if not isinstance(payload, dict):
                return
            if isinstance(payload.get("strategy"), dict):
                self._last_ai_strategy = payload["strategy"]

            suggested = payload.get("suggested")
            if not isinstance(suggested, dict):
                self._log.info("[AI-STRAT] suggested missing -> skip")
                return

            # 실거래 안전 가드(클램프)
            mode = str(suggested.get("strategy_mode") or "ai").strip().lower()
            if mode not in ("avoid", "trend_following", "ai"):
                mode = "ai"

            aggr = int(suggested.get("aggressiveness_level") or 5)
            aggr = max(1, min(10, aggr))

            pos_pct = self._normalize_pct_value(suggested.get("pos_size_pct"), default=2.5)
            pos_pct = max(0.5, min(25.0, float(pos_pct)))

            dll_pct = self._normalize_pct_value(suggested.get("daily_loss_limit_pct"), default=3.0)
            dll_pct = max(0.5, min(10.0, float(dll_pct)))

            rr = float(suggested.get("rr_ratio") or 2.0)
            rr = max(0.5, min(5.0, rr))

            cd = int(suggested.get("cooldown_sec") or 30)
            cd = max(10, min(3600, cd))

            ind_mode = str(suggested.get("indicators_mode") or "and").strip().lower()
            if ind_mode not in ("and", "or", "weighted", "ai"):
                ind_mode = "and"

            self._set_strategy_mode_ui(mode, reason="ai_strategy_suggested")

            # 리디자인 UI: sld_aggr 없으면 성향 3단계만 반영 후 저장
            if not hasattr(self, "sld_aggr"):
                aggr_key = "conservative" if aggr <= 2 else ("aggressive" if aggr >= 8 else "neutral")
                if hasattr(self, "radio_aggr_conservative"):
                    self.radio_aggr_conservative.setChecked(aggr_key == "conservative")
                if hasattr(self, "radio_aggr_neutral"):
                    self.radio_aggr_neutral.setChecked(aggr_key == "neutral")
                if hasattr(self, "radio_aggr_aggressive"):
                    self.radio_aggr_aggressive.setChecked(aggr_key == "aggressive")
                oa = int(suggested.get("order_amount_krw") or suggested.get("single_order_amount") or 10000)
                if hasattr(self, "spn_order_amount") and 5000 <= oa <= 100_000_000:
                    self.spn_order_amount.setValue(oa)
                self._is_dirty = True
                self._update_dirty_indicator()
                try:
                    self._on_save_apply()
                except Exception:
                    pass
                return

            try:
                self.sld_aggr.blockSignals(True)
                self.sld_aggr.setValue(int(aggr))
                self.sld_aggr.blockSignals(False)
            except Exception:
                pass

            try:
                self.sld_pos_size.blockSignals(True)
                self.sld_pos_size.setValue(int(pos_pct))
                self.sld_pos_size.blockSignals(False)
                self.lbl_pos_size.setText(f"{pos_pct:.1f}%")
            except Exception:
                pass

            try:
                self.sld_rr_ratio.blockSignals(True)
                self.sld_rr_ratio.setValue(int(rr * 10))
                self.sld_rr_ratio.blockSignals(False)
                self.lbl_rr_ratio.setText(f"{rr:.1f}")
                self._draft_strategy['rr_ratio'] = rr
            except Exception:
                pass

            try:
                self._set_daily_loss_pct(float(dll_pct), reason="ai_strategy_suggested")
            except Exception:
                pass

            try:
                if hasattr(self, 'spn_behavior_cooldown'):
                    self.spn_behavior_cooldown.setValue(int(cd))
            except Exception:
                pass

            # indicators_mode는 UI 로직과 연동(표준 enum 커밋을 위해 draft에 보관)
            try:
                self._draft_strategy['indicators_mode'] = ind_mode
            except Exception:
                pass

            self._log.info(
                "[AI-STRAT] applied mode=%s aggr=%d pos=%.2f dll=%.2f rr=%.2f cd=%d ind_mode=%s",
                mode,
                aggr,
                pos_pct,
                dll_pct,
                rr,
                cd,
                ind_mode,
            )

            # Dirty + 자동 커밋
            self._is_dirty = True
            self._update_dirty_indicator()
            try:
                self._on_save_apply()
            except Exception:
                pass

        except Exception as e:
            self._log.exception(f"[AI-STRAT] apply error: {e}")
    
    def _on_pos_size_changed(self, value):
        """리스크 관리 변경 시 (리디자인 UI에서는 위젯 없음)"""
        if not hasattr(self, "lbl_pos_size"):
            return
        if hasattr(self, '_saving_strategy') and self._saving_strategy:
            return
        self.lbl_pos_size.setText(f"{value}%")  # 이미 % 값이므로 그대로 표시
        self._log.info(f"[POS] source=risk pos={value:.1f} path=draft.pos_size_pct")
        # 볼륨 슬라이더는 변경하지 않음 (단방향 연동)
        self._log.debug(f"[RISK] pos_size changed: {value}%")
        # self._update_summary("risk_changed")  # 전략요약 갱신 금지
        
        # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태)
        self._draft_strategy['pos_size_pct'] = float(value)
        
        # ✅ P2-5: Dirty 상태 설정
        self._is_dirty = True
        self._update_dirty_indicator()
    
    def _on_rr_ratio_changed(self, value):
        """리스크 관리 변경 시 (리디자인 UI에서는 위젯 없음)"""
        if not hasattr(self, "lbl_rr_ratio"):
            return
        if hasattr(self, '_saving_strategy') and self._saving_strategy:
            return
        if getattr(self, '_applying_aggr_preset', False):
            return
        self.lbl_rr_ratio.setText(f"{value/10:.1f}")
        self._log.info(f"[RR] source=risk rr={value/10.0:.1f} path=draft.rr_ratio")
        # 볼륨 슬라이더는 변경하지 않음 (단방향 연동)
        # self._update_summary("risk_changed")  # 전략요약 갱신 금지
        
        # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태)
        self._draft_strategy['rr_ratio'] = value / 10.0
        
        # ✅ P0-7: 수동 오버라이드 플래그 설정
        self._manual_rr_override = True
        
        # ✅ P2-5: Dirty 상태 설정
        self._is_dirty = True
        self._update_dirty_indicator()

        # ✅ 즉시 표시 갱신(저장 전 프리뷰 반영)
        try:
            self._update_ai_strategy_snapshot()
        except Exception:
            pass
    
    def _on_reset_preset(self):
        """✅ P0-7: 프리셋 초기화 버튼 (리디자인 UI에서는 호출되지 않음)"""
        try:
            self._manual_rr_override = False
            self._manual_dll_override = False
            if hasattr(self, 'sld_aggr'):
                current_aggr = self.sld_aggr.value()
                self._on_aggr_changed(current_aggr)
            
            self._info("리스크 프리셋 자동 연동이 다시 활성화되었습니다.")
            self._log.info("[PRESET] override flags reset, auto-linkage restored")
            
        except Exception as e:
            self._log.error(f"[PRESET] reset error: {e}")
            self._info("프리셋 초기화 중 오류가 발생했습니다.")
    
    def _set_daily_loss_pct(self, dl: float, *, update_draft=True, update_ui=True, reason=""):
        """✅ P0-SYNC-DLL-ONEFIX: DLL 동기화 전용 helper"""
        try:
            # Draft 업데이트
            if update_draft:
                self._draft_strategy['daily_loss_limit_pct'] = dl
                self._log.info(f"[DLL] source={reason} dll={dl:.1f} path=draft.daily_loss_limit_pct")
            
            # UI 동기화
            if update_ui:
                # 리스크관리 위젯
                if hasattr(self, 'spn_daily_loss'):
                    self.spn_daily_loss.blockSignals(True)
                    self.spn_daily_loss.setValue(int(dl * 10))  # 0.1% 단위
                    self.spn_daily_loss.blockSignals(False)
                
                # 리스크관리 라벨
                if hasattr(self, 'lbl_daily_loss'):
                    self.lbl_daily_loss.setText(f"{dl:.1f}%")
                
                self._log.info(f"[DLL] source={reason} ui_sync={dl:.1f}")
        except Exception as e:
            self._log.error(f"[DLL] sync error: {e}")
    
    def _on_daily_loss_changed(self, value):
        """리스크 관리 변경 시 (리디자인 UI에서는 위젯 없음)"""
        if not hasattr(self, "lbl_daily_loss"):
            return
        if hasattr(self, '_saving_strategy') and self._saving_strategy:
            return
        if getattr(self, '_applying_aggr_preset', False):
            return
        self.lbl_daily_loss.setText(f"{value/10:.1f}%")
        self._log.info(f"[DLL] source=risk dll={value/10.0:.1f} path=draft.daily_loss_limit_pct")
        # 볼륨 슬라이더는 변경하지 않음 (단방향 연동)
        # self._update_summary("risk_changed")  # 전략요약 갱신 금지
        
        # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태)
        self._draft_strategy['daily_loss_limit_pct'] = value / 10.0
        
        # ✅ P0-7: 수동 오버라이드 플래그 설정
        self._manual_dll_override = True
        
        # ✅ P2-5: Dirty 상태 설정
        self._is_dirty = True
        self._update_dirty_indicator()
    
    def _on_behavior_cooldown_changed(self, value):
        """심리행동제어 쿨다운 변경 시 로그 기록"""
        self._log.info(f"[CD] source=psych sec={value} path=draft.cooldown_sec")
        # self._update_summary("psychology_changed")  # 전략요약 갱신 금지
        
        # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태)
        self._draft_strategy['cooldown_sec'] = value
        
        # ✅ P2-5: Dirty 상태 설정
        self._is_dirty = True
        self._update_dirty_indicator()
    
    def _on_max_invest_changed(self, value):
        """최대투자금 변경 시 상한 체크"""
        try:
            # 포트폴리오 탭에서 보유자산 정보 가져오기
            available_balance = self._get_available_balance()
            
            if available_balance > 0 and value > available_balance:
                # 상한 초과 시 자동 조정
                self.spn_max_invest.blockSignals(True)
                self.spn_max_invest.setValue(int(available_balance))
                self.spn_max_invest.blockSignals(False)
                
                self._info("보유자산을 초과할 수 없습니다")
                self._log.info(f"최대투자금 상한 적용: {value:,} → {int(available_balance):,}")
        except Exception as e:
            self._log.error(f"최대투자금 상한 체크 오류: {e}")
    
    def _on_advanced_toggle_clicked(self, checked: bool):
        """고급 모드 펼치기/접기: exit_mode, 손절/익절 표시."""
        try:
            self._advanced_visible = bool(checked)
            if hasattr(self, "frm_advanced"):
                self.frm_advanced.setVisible(self._advanced_visible)
            if hasattr(self, "btn_advanced_toggle"):
                self.btn_advanced_toggle.setText("고급 모드 접기(▼)" if self._advanced_visible else "고급 모드 펼치기(▶)")
        except Exception as e:
            self._log.debug("advanced toggle: %s", e)
    
    def _get_total_asset(self):
        """총자산(KRW 평가액) 가져오기"""
        try:
            # 포트폴리오 탭에서 총자산 정보 가져오기
            if hasattr(self._owner, 'portfolio_tab') and self._owner.portfolio_tab:
                portfolio_tab = self._owner.portfolio_tab
                
                # 총자산 라벨에서 추출
                if hasattr(portfolio_tab, 'lbl_total_asset') and portfolio_tab.lbl_total_asset:
                    text = portfolio_tab.lbl_total_asset.text()
                    # "총자산: 41,507 KRW" 형식에서 숫자 추출
                    import re
                    match = re.search(r'([\d,]+)', text)
                    if match:
                        return int(match.group(1).replace(',', ''))
            
            # API 직접 호출로 fallback
            from app.services.order_service import svc_order
            accounts = svc_order.fetch_accounts()
            total_krw = 0.0
            for acc in accounts:
                if acc.get('currency') == 'KRW':
                    bal = float(acc.get('balance') or 0)
                    total_krw += bal
            
            return int(total_krw) if total_krw > 0 else 0
                    
        except Exception as e:
            self._log.debug(f"총자산 조회 실패: {e}")
            return 0
    
    def _get_available_balance(self):
        """주문가능 KRW 잔액 가져오기"""
        try:
            # 포트폴리오 탭에서 현재 보유자산 정보 가져오기
            if hasattr(self._owner, 'portfolio_tab') and self._owner.portfolio_tab:
                portfolio_tab = self._owner.portfolio_tab
                
                # 라벨에서 주문가능 금액 추출
                if hasattr(portfolio_tab, 'lbl_available') and portfolio_tab.lbl_available:
                    text = portfolio_tab.lbl_available.text()
                    # "주문가능: 41,507 KRW" 형식에서 숫자 추출
                    import re
                    match = re.search(r'([\d,]+)', text)
                    if match:
                        return int(match.group(1).replace(',', ''))
                
                # 보유 KRW로 fallback
                if hasattr(portfolio_tab, 'lbl_krw_balance') and portfolio_tab.lbl_krw_balance:
                    text = portfolio_tab.lbl_krw_balance.text()
                    match = re.search(r'([\d,]+)', text)
                    if match:
                        return int(match.group(1).replace(',', ''))
            
            # API 직접 호출으로 fallback
            from app.services.order_service import svc_order
            accounts = svc_order.fetch_accounts()
            for acc in accounts:
                if acc.get('currency') == 'KRW':
                    bal = float(acc.get('balance') or 0)
                    locked = float(acc.get('locked') or 0)
                    return max(0.0, bal - locked)
                    
        except Exception as e:
            self._log.debug(f"주문가능 잔액 조회 실패: {e}")
        
        return 0
    
    def _generate_ai_recommendation(self):
        """Generate AI recommendation based on market analysis"""
        try:
            import time
            self._log.info("[AI-RECO] generate start button_click=manual")
            
            current_hour = time.localtime().tm_hour
            
            # Market condition analysis
            if 9 <= current_hour <= 11:
                market_condition = "오전 강세 구간"
                volatility = "보통"
                liquidity = "보통"
                session = "아시아"
                aggr = 7
                reason = "오전 강세 시간대로 적극적 매수 기회"
            elif 14 <= current_hour <= 16:
                market_condition = "오후 변동성 구간"
                volatility = "높음"
                liquidity = "보통"
                session = "유럽"
                aggr = 4
                reason = "오후 변동성으로 보수적 접근 필요"
            else:
                market_condition = "일반 시장 상황"
                volatility = "낮음"
                liquidity = "보통"
                session = "미국"
                aggr = 5
                reason = "안정적인 중립적 접근"
            
            # Compute recommendation payload
            pos_size = max(1.0, 1.0 + 1.5 * (aggr - 1))  # percent 단위: 1% ~ 25% 범위
            rr_ratio = 1.2 + 0.2 * (aggr - 1)
            cooldown_sec = max(30, 600 - 50 * (aggr - 1))  # 매매 적극성과 동일한 공식 사용
            daily_loss_limit_pct = max(0.5, 2.5 - 0.2 * (aggr - 1))  # percent 단위
            
            # Enhanced recommendation with market analysis
            reco_summary = f"🤖 AI 시장 분석 및 추천:\n\n"
            reco_summary += f"📊 시장 상황: {market_condition}\n"
            reco_summary += f"📈 변동성: {volatility} | 💰 유동성: {liquidity}\n"
            reco_summary += f"⏰ 거래 세션: {session}\n\n"
            reco_summary += f"🎯 추천 설정:\n"
            reco_summary += f"• 공격성: {aggr}/10\n"
            reco_summary += f"• 포지션 비중(1종목 최대): {pos_size:.1f}%\n"
            reco_summary += f"• 손익비(RR): {rr_ratio:.1f}배\n"
            reco_summary += f"• 쿨다운: {cooldown_sec}초\n"
            reco_summary += f"• 일일 손실 한도(%): {daily_loss_limit_pct:.1f}%\n\n"
            reco_summary += f"💡 추천 이유: {reason}\n"
            
            # Add behavioral advice
            if aggr >= 7:
                reco_summary += f"\n⚠️ 주의: 높은 공격성은 빠른 손실을 유발할 수 있습니다."
            elif aggr <= 3:
                reco_summary += f"\n💡 팁: 보수적 설정으로 안정적인 수익을 목표로 합니다."
            
            # Display recommendation
            self.txt_ai_reason.setText(reco_summary)
            self.btn_ai_apply.setEnabled(True)  # Enable apply button
            
            # Store recommendation for later application
            # ✅ P2-1-②: 레거시 키(volatility/liquidity/session) 저장 금지
            # - UI 적용용 임시 payload는 SSOT 키만 사용
            self._pending_ai_recommendation = {
                "aggressiveness_level": aggr,
                "pos_size_pct": pos_size,
                "rr_ratio": rr_ratio,
                "cooldown_sec": cooldown_sec,
                "daily_loss_limit_pct": daily_loss_limit_pct,
                "market_volatility": volatility,
                "market_liquidity": liquidity,
                "trading_session": session,
                "reason": reason,
            }
            
            self._info("AI 시장 분석이 완료되었습니다. 추천을 확인 후 적용하세요.")
            self._log.info("[AI-RECO] generate complete recommendation_stored=true")
            
        except Exception as e:
            self._info(f"AI 추천 준비 중 오류: {e}")
            self._log.exception(f"[AI-RECO-UI] error: {e}")
    
    def _apply_ai_recommendation(self):
        """Apply the generated AI recommendation to actual strategy"""
        try:
            if not hasattr(self, '_pending_ai_recommendation'):
                self._info("적용할 AI 추천이 없습니다. 먼저 새로고침을 눌러주세요.")
                self._log.warning("[AI-RECO] apply fail reason=no_pending_recommendation")
                return
                
            self._log.info("[AI-RECO] apply start pending_exists=true")
            reco = self._pending_ai_recommendation
            self._applying_ai = True
                
            reco = self._pending_ai_recommendation
            
            # ✅ P0-SYNC-DLL-ONEFIX: AI 추천 DLL이 있으면 override를 먼저 설정 (aggr 세팅 이전)
            reco_dll = reco.get("daily_loss_limit_pct", None)
            if reco_dll is not None:
                self._manual_dll_override = True  # AI 추천값은 override로 간주
            
            # 리디자인 UI: sld_aggr 없으면 성향 3단계 + 주문금액만 반영 후 저장
            if not hasattr(self, "sld_aggr"):
                aggr = int(reco.get("aggressiveness_level", 5))
                aggr_key = "conservative" if aggr <= 2 else ("aggressive" if aggr >= 8 else "neutral")
                if hasattr(self, "radio_aggr_conservative"):
                    self.radio_aggr_conservative.setChecked(aggr_key == "conservative")
                if hasattr(self, "radio_aggr_neutral"):
                    self.radio_aggr_neutral.setChecked(aggr_key == "neutral")
                if hasattr(self, "radio_aggr_aggressive"):
                    self.radio_aggr_aggressive.setChecked(aggr_key == "aggressive")
                oa = int(reco.get("order_amount_krw") or reco.get("single_order_amount") or 10000)
                if hasattr(self, "spn_order_amount") and 5000 <= oa <= 100_000_000:
                    self.spn_order_amount.setValue(oa)
                self._is_dirty = True
                self._update_dirty_indicator()
                try:
                    self._on_save_apply()
                except Exception:
                    pass
                self._applying_ai = False
                return
            
            # Apply changes to UI (모든 항목 명시적 적용)
            self.sld_aggr.setValue(reco["aggressiveness_level"])
            aggr = reco["aggressiveness_level"]
            pos = max(1.0, 1.0 + 1.5 * (aggr - 1))  # percent 단위: 1% ~ 25% 범위
            rr = 1.2 + 0.2 * (aggr - 1)
            cd = max(30, 600 - 50 * (aggr - 1))
            
            # ✅ P0-SYNC-1: AI 추천 DLL 우선 사용
            if reco_dll is not None:
                dl = reco_dll
            else:
                dl = max(0.5, 2.5 - 0.2 * (aggr - 1))  # 프리셋 fallback
            
            # 리스크 관리 영역에 일관된 값 적용
            if hasattr(self, 'sld_pos_size'):
                self.sld_pos_size.blockSignals(True)
                self.sld_pos_size.setValue(int(pos))  # percent 값으로 직접 설정
                self.sld_pos_size.blockSignals(False)
                self.lbl_pos_size.setText(f"{pos:.1f}%")
                self._log.info(f"[POS] source=ai_apply pos={pos:.1f} path=draft.pos_size_pct")
                
            if hasattr(self, 'sld_rr_ratio'):
                self.sld_rr_ratio.blockSignals(True)
                self.sld_rr_ratio.setValue(int(rr * 10))
                self.sld_rr_ratio.blockSignals(False)
                self.lbl_rr_ratio.setText(f"{rr:.1f}")
                self._log.info(f"[RR] source=ai_apply rr={rr:.1f} path=draft.rr_ratio")
                
            # ✅ P0-SYNC-DLL-ONEFIX: AI 추천 DLL은 helper로 동기화
            if reco_dll is not None:
                self._set_daily_loss_pct(dl, reason="ai_reco_apply")
            
            # 매매 적극성 표시 라벨 업데이트
            self.lbl_aggr_values.setText(f"포지션 비중(1종목 최대): {pos:.1f}% | 손익비(RR): {rr:.1f} | 쿨다운: {cd}초 | 일일 손실 한도(%): {dl:.1f}%")
            
            # 쿨다운 설정 (단일화: 심리행동제어 쿨다운이 정답)
            if hasattr(self, 'spn_behavior_cooldown'):
                self.spn_behavior_cooldown.setValue(reco["cooldown_sec"])
                self._log.info(f"[CD] source=ai_apply cd={reco['cooldown_sec']} path=draft.cooldown_sec")
            
            # 최대투자금 및 1회주문금액 (pos_size 기반 계산)
            if hasattr(self, 'spn_max_invest'):
                # 총자산의 pos_size 비율로 최대투자금 설정
                total_asset = self._get_total_asset()
                if total_asset > 0:
                    max_invest = int(total_asset * pos / 100)  # percent를 ratio로 변환
                    self.spn_max_invest.setValue(max_invest)
            
            if hasattr(self, 'spn_order_amount'):
                # 1회주문금액은 총자산의 1% 또는 최소 1만원
                total_asset = self._get_total_asset()
                if total_asset > 0:
                    order_amount = max(10_000, int(total_asset * 0.01))
                    self.spn_order_amount.setValue(order_amount)
            
            # Update market environment
            # ✅ P2-1-②: SSOT 키 우선(market_volatility/market_liquidity/trading_session)
            # (하위호환) 혹시 남아있을 수 있는 레거시 키(volatility/liquidity/session)도 폴백으로만 허용
            try:
                v_txt = reco.get("market_volatility", None)
                if v_txt is None:
                    v_txt = reco.get("volatility", "보통")
                self.cmb_volatility.setCurrentText(v_txt)
            except:
                pass

            try:
                l_txt = reco.get("market_liquidity", None)
                if l_txt is None:
                    l_txt = reco.get("liquidity", "보통")
                self.cmb_liquidity.setCurrentText(l_txt)
            except:
                pass

            try:
                s_txt = reco.get("trading_session", None)
                if s_txt is None:
                    s_txt = reco.get("session", "아시아")
                self.cmb_session.setCurrentText(s_txt)
            except:
                pass
            
            # 손절/익절 설정 (AI 추천 기반)
            # 규칙: 사용자가 이미 값(>0)을 넣었으면 절대 덮어쓰지 않음. 0(=AI)일 때만 반영.
            ai_sl = float(reco.get("daily_loss_limit_pct", 0.0) or 0.0)
            ai_tp = float((reco.get("rr_ratio", 0.0) or 0.0) * 2.0)

            if hasattr(self, "spn_stop_loss_pct"):
                if float(self.spn_stop_loss_pct.value() or 0.0) <= 0.0:
                    self.spn_stop_loss_pct.setValue(ai_sl)
            if hasattr(self, "spn_take_profit_pct"):
                if float(self.spn_take_profit_pct.value() or 0.0) <= 0.0:
                    self.spn_take_profit_pct.setValue(ai_tp)

            # 고급 모드 하위호환도 동일 가드
            if hasattr(self, "spn_stop_loss"):
                if float(self.spn_stop_loss.value() or 0.0) <= 0.0:
                    self.spn_stop_loss.setValue(ai_sl)
            if hasattr(self, "spn_take_profit"):
                if float(self.spn_take_profit.value() or 0.0) <= 0.0:
                    self.spn_take_profit.setValue(ai_tp)

            if hasattr(self, "_update_tp_sl_status"):
                self._update_tp_sl_status()
            
            # 기술적 지표 (기본값 유지 - AI 추천에 없음)
            if hasattr(self, 'chk_rsi'):
                self.chk_rsi.setChecked(True)
            if hasattr(self, 'chk_bb'):
                self.chk_bb.setChecked(True)
            if hasattr(self, 'chk_macd'):
                self.chk_macd.setChecked(False)
            if hasattr(self, 'chk_ma'):
                self.chk_ma.setChecked(False)
            if hasattr(self, 'chk_atr'):
                self.chk_atr.setChecked(False)
            if hasattr(self, 'chk_stoch'):
                self.chk_stoch.setChecked(False)
            
            # 논리 설정 (기본값 유지 - AI 추천에 없음)
            if hasattr(self, 'cmb_logic'):
                self.cmb_logic.setCurrentText("AND")
            if hasattr(self, 'chk_ai_judge'):
                self.chk_ai_judge.setChecked(False)
            
            # 외부 조건 (기본값 유지 - AI 추천에 없음)
            if hasattr(self, 'chk_macro_news'):
                self.chk_macro_news.setChecked(False)
            if hasattr(self, 'chk_exchange_check'):
                self.chk_exchange_check.setChecked(True)
            if hasattr(self, 'chk_mtf_mix'):
                self.chk_mtf_mix.setChecked(False)
            if hasattr(self, 'chk_cross_asset'):
                self.chk_cross_asset.setChecked(False)
            
            # UI 표시만 변경 (전략요약 갱신 금지)
            # self._update_summary("ai_recommendation")
            
            # ✅ P2-2: Draft 상태 업데이트 (UI 편집 중 상태) - 최종 통합
            self._draft_strategy['pos_size_pct'] = pos
            self._draft_strategy['rr_ratio'] = rr
            self._draft_strategy['cooldown_sec'] = reco["cooldown_sec"]
            self._draft_strategy['daily_loss_limit_pct'] = dl
            self._draft_strategy['aggressiveness_level'] = aggr

            # ✅ P0-AI-SSOT-BRIDGE: settings.strategy에 AI 전략 5필드 직접 overwrite (중간 가공 금지)
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            if main_window:
                settings = main_window._get_settings_cached()
                if settings and getattr(settings, 'strategy', None):
                    strategy_ssot = getattr(self, '_last_ai_strategy', None)
                    if not isinstance(strategy_ssot, dict):
                        strategy_ssot = {
                            "order_amount_krw": int(getattr(settings.strategy, "order_amount_krw", 10000) or 10000),
                            "pos_size_pct": float(reco.get("pos_size_pct", pos)),
                            "rr_ratio": float(reco.get("rr_ratio", rr)),
                            "cooldown_sec": int(reco.get("cooldown_sec", reco["cooldown_sec"])),
                            "daily_loss_limit_pct": float(reco.get("daily_loss_limit_pct", dl)),
                        }
                    for key in ("order_amount_krw", "pos_size_pct", "rr_ratio", "cooldown_sec", "daily_loss_limit_pct"):
                        if key in strategy_ssot and strategy_ssot[key] is not None:
                            v = strategy_ssot[key]
                            if key == "order_amount_krw":
                                setattr(settings.strategy, key, max(1000, int(v)))
                            elif key == "pos_size_pct":
                                setattr(settings.strategy, key, max(0.5, min(25.0, float(v))))
                            elif key == "rr_ratio":
                                setattr(settings.strategy, key, max(0.5, min(5.0, float(v))))
                            elif key == "cooldown_sec":
                                setattr(settings.strategy, key, max(10, min(3600, int(v))))
                            elif key == "daily_loss_limit_pct":
                                setattr(settings.strategy, key, max(0.5, min(10.0, float(v))))
                    try:
                        from app.utils.prefs import save_settings
                        save_settings(settings)
                        self._log.info("[AI-RECO] applied to settings.strategy")
                        self._ai_strategy_applied = True
                        self._update_ai_strategy_snapshot()
                    except Exception as e:
                        self._log.warning("[AI-RECO] applied to settings.strategy save failed: %s", e)
            
            # Clear recommendation and disable apply button
            self.txt_ai_reason.clear()
            self.btn_ai_apply.setEnabled(False)
            delattr(self, '_pending_ai_recommendation')
            
            # ✅ AI 추천 적용 후 즉시 캐시 갱신 트리거
            try:
                # AI 추천 적용 이벤트 발행으로 runner 캐시 강제 갱신
                import app.core.bus as eventbus
                eventbus.publish("ai.reco.refresh", {})
                self._log.warning("[AI-RECO][PUB] topic=ai.reco.refresh source=config_tabs:_apply_ai_recommendation")
                self._log.info("[AI-RECO] apply_commit trigger_cache_refresh=true")
                self._log.info("[AI-RECO] apply_commit published ai.reco.refresh")
            except Exception as e:
                self._log.warning(f"[AI-RECO] cache refresh trigger failed: {e}")
            
            self._info("AI 추천이 성공적으로 적용되었습니다.")
            
            # ✅ P2-5: Dirty 상태 설정
            self._is_dirty = True
            self._update_dirty_indicator()
            
        except Exception as e:
            self._info(f"AI 추천 적용 중 오류: {e}")
            self._log.exception(f"[AI-RECO-APPLY] error: {e}")
        finally:
            # AI 적용 플래그 해제
            self._applying_ai = False
    
    def sync_ui_to_settings(self, settings):
        """실행 직전: 전략 탭 UI 상태를 settings에 반영(저장 없이). allow_downscale 등이 Run 시점에 적용되도록."""
        try:
            if not hasattr(settings, "strategy") or not settings.strategy:
                from app.utils.settings_schema import StrategyConfig
                # [위험 지점] StrategyConfig() → ai_provider=기본값(local). GPT 선택 상태가 여기서 초기화됨. docs/P0_AI_PROVIDER_SSOT_DESIGN_AND_PATCH.md
                # 기존 strategy 없음(또는 falsy) → ai_provider 읽을 소스 없음.
                settings.strategy = StrategyConfig()
            stg = settings.strategy
            if (hasattr(self, "radio_avoid") and self.radio_avoid.isChecked()) or (hasattr(self, "radio_aggr_conservative") and self.radio_aggr_conservative.isChecked()):
                aggr_key = "conservative"
            elif (hasattr(self, "radio_ai") and self.radio_ai.isChecked()) or (hasattr(self, "radio_aggr_aggressive") and self.radio_aggr_aggressive.isChecked()):
                aggr_key = "aggressive"
            else:
                aggr_key = "neutral"
            preset = AGGRESSIVENESS_PRESETS.get(aggr_key, AGGRESSIVENESS_PRESETS["neutral"])
            stg.aggressiveness = aggr_key
            stg.aggressiveness_level = preset["aggressiveness_level"]
            stg.pos_size_pct = preset["pos_size_pct"]
            stg.rr_ratio = preset["rr_ratio"]
            stg.daily_loss_limit_pct = preset["daily_loss_limit_pct"]
            stg.cooldown_sec = preset["cooldown_sec"]
            if hasattr(self, "spn_order_amount"):
                stg.order_amount_krw = self.spn_order_amount.value()
                stg.single_order_amount = self.spn_order_amount.value()
            if hasattr(self, "spn_max_invest_cap"):
                stg.max_invest_cap_krw = int(self.spn_max_invest_cap.value())
            if hasattr(self, "chk_allow_downscale"):
                stg.allow_downscale_order_amount = self.chk_allow_downscale.isChecked()
            if hasattr(self, "cmb_exit_mode"):
                stg.exit_mode = str(self.cmb_exit_mode.currentText() or "ai")
            if hasattr(self, "spn_stop_loss"):
                stg.stop_loss_pct = float(self.spn_stop_loss.value())
            if hasattr(self, "spn_take_profit"):
                stg.take_profit_pct = float(self.spn_take_profit.value())
            if hasattr(self, "lst_whitelist") and hasattr(self, "lst_blacklist"):
                def _n(s):
                    s = str(s).strip().upper()
                    if not s: return ""
                    return s if s.startswith("KRW-") else (f"KRW-{s.split('-')[-1]}" if "-" in s else f"KRW-{s}")
                wl = [x for x in (_n(self.lst_whitelist.item(i).text()) for i in range(self.lst_whitelist.count())) if x]
                bl = [x for x in (_n(self.lst_blacklist.item(i).text()) for i in range(self.lst_blacklist.count())) if x]
                stg.whitelist = wl
                stg.blacklist = bl
            if hasattr(self, "chk_rotation_enabled") and hasattr(self, "spn_rotation_interval") and hasattr(self, "spn_rotation_count"):
                stg.rotation = {"enabled": self.chk_rotation_enabled.isChecked(), "interval_min": self.spn_rotation_interval.value(), "count": self.spn_rotation_count.value()}
            self._log.debug("[STRATEGY] sync_ui_to_settings: order_amount=%s allow_downscale=%s", getattr(stg, "order_amount_krw", 0), getattr(stg, "allow_downscale_order_amount", False))
        except Exception as e:
            self._log.debug("sync_ui_to_settings: %s", e)

    def _commit_strategy_from_ui(self):
        """리디자인: 사용자 설정 4가지만 커밋 - aggressiveness(3단계), order_amount, downscale, whitelist/blacklist."""
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, "_get_settings_cached"):
                main_window = main_window.parent()
            if main_window:
                settings = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                settings = load_settings()
            if not hasattr(settings, "strategy") or not settings.strategy:
                from app.utils.settings_schema import StrategyConfig
                # [위험 지점] StrategyConfig() → ai_provider=기본값(local). GPT 선택 상태가 여기서 초기화됨. docs/P0_AI_PROVIDER_SSOT_DESIGN_AND_PATCH.md
                # 기존 strategy 없음(또는 falsy) → ai_provider 읽을 소스 없음.
                settings.strategy = StrategyConfig()

            settings.strategy.strategy_mode = "ai"

            # AI 매매 성향 3단계 (보수적/중립/공격적) → aggressiveness + 내부 프리셋
            if (hasattr(self, "radio_avoid") and self.radio_avoid.isChecked()) or (hasattr(self, "radio_aggr_conservative") and self.radio_aggr_conservative.isChecked()):
                aggr_key = "conservative"
            elif (hasattr(self, "radio_ai") and self.radio_ai.isChecked()) or (hasattr(self, "radio_aggr_aggressive") and self.radio_aggr_aggressive.isChecked()):
                aggr_key = "aggressive"
            else:
                aggr_key = "neutral"
            settings.strategy.aggressiveness = aggr_key
            preset = AGGRESSIVENESS_PRESETS.get(aggr_key, AGGRESSIVENESS_PRESETS["neutral"])
            settings.strategy.aggressiveness_level = preset["aggressiveness_level"]
            settings.strategy.pos_size_pct = preset["pos_size_pct"]
            settings.strategy.rr_ratio = preset["rr_ratio"]
            settings.strategy.daily_loss_limit_pct = preset["daily_loss_limit_pct"]
            settings.strategy.cooldown_sec = preset["cooldown_sec"]

            # 🔷 로테이션: strategy.rotation (기회비용 창출 매도-only)
            rot_enabled = getattr(self, "chk_rotation_enabled", None) and self.chk_rotation_enabled.isChecked()
            rot_interval = getattr(self, "spn_rotation_interval", None) and self.spn_rotation_interval.value() or 30
            rot_count = getattr(self, "spn_rotation_count", None) and self.spn_rotation_count.value() or 1
            settings.strategy.rotation = {"enabled": rot_enabled, "interval_min": int(rot_interval), "count": int(rot_count)}

            if hasattr(self, "spn_order_amount"):
                settings.strategy.order_amount_krw = self.spn_order_amount.value()
                settings.strategy.single_order_amount = self.spn_order_amount.value()
            if hasattr(self, "spn_max_invest_cap"):
                settings.strategy.max_invest_cap_krw = int(self.spn_max_invest_cap.value())
            if hasattr(self, "chk_allow_downscale"):
                settings.strategy.allow_downscale_order_amount = self.chk_allow_downscale.isChecked()
            if hasattr(self, "cmb_exit_mode"):
                settings.strategy.exit_mode = str(self.cmb_exit_mode.currentText() or "ai")
            # ✅ 0이면 AI 판단, >0이면 사용자 값 최우선 (고정값/폴백 금지)
            if hasattr(self, "spn_stop_loss_pct"):
                settings.strategy.stop_loss_pct = float(self.spn_stop_loss_pct.value())
            elif hasattr(self, "spn_stop_loss"):
                settings.strategy.stop_loss_pct = float(self.spn_stop_loss.value())

            if hasattr(self, "spn_take_profit_pct"):
                settings.strategy.take_profit_pct = float(self.spn_take_profit_pct.value())
            elif hasattr(self, "spn_take_profit"):
                settings.strategy.take_profit_pct = float(self.spn_take_profit.value())

            current_whitelist = []
            current_blacklist = []
            if hasattr(self, "lst_whitelist") and hasattr(self, "lst_blacklist"):
                for i in range(self.lst_whitelist.count()):
                    current_whitelist.append(self.lst_whitelist.item(i).text())
                for i in range(self.lst_blacklist.count()):
                    current_blacklist.append(self.lst_blacklist.item(i).text())
            
            def _norm_symbol(v: str) -> str:
                v = str(v).strip().upper()
                if not v:
                    return ""
                if v.startswith("KRW-"):
                    return v
                if "-" in v:
                    v = v.split("-")[-1]
                return f"KRW-{v}"
            
            current_whitelist = [x for x in (_norm_symbol(s) for s in current_whitelist) if x]
            current_blacklist = [x for x in (_norm_symbol(s) for s in current_blacklist) if x]
            settings.strategy.whitelist = current_whitelist
            settings.strategy.blacklist = current_blacklist
            
            from app.utils.prefs import save_settings
            save_settings(settings)
            if main_window:
                main_window._get_settings_cached(force=True)
            saved_settings = main_window._get_settings_cached(force=True) if main_window else load_settings()
            self._update_summary_from_settings(saved_settings)
            self._update_run_status_card()
            sl_val = float(getattr(settings.strategy, "stop_loss_pct", 0.0) or 0.0)
            tp_val = float(getattr(settings.strategy, "take_profit_pct", 0.0) or 0.0)
            self._log.info(
                "[COMMIT] strategy saved: aggressiveness=%s order_amount=%s sl=%.2f tp=%.2f wl=%d bl=%d",
                aggr_key, getattr(settings.strategy, "order_amount_krw", 0), sl_val, tp_val, len(current_whitelist), len(current_blacklist)
            )
            return True
        except Exception as e:
            if hasattr(self, "_saving_strategy"):
                self._saving_strategy = False
            self._info(f"전략 저장 중 오류: {e}")
            self._log.exception("[STRATEGY] save error: %s", e)
            return False
    
    def _on_save_apply(self):
        """✅ P2-3: SSOT 저장 - 단일 커밋 함수 호출"""
        try:
            # ✅ 저장 가드 설정 (중복 저장 방지)
            if hasattr(self, '_saving_strategy') and self._saving_strategy:
                self._log.warning("[STRATEGY] save already in progress, skipping")
                return
            self._saving_strategy = True
            
            try:
                # ✅ 단일 커밋 함수 호출
                success = self._commit_strategy_from_ui()
                if success:
                    self._info("✅ 전략 설정이 저장되었습니다.")
                    # ✅ P2-5: Dirty 상태 해제
                    self._is_dirty = False
                    self._update_dirty_indicator()
                    # ✅ 설정 적용 시 ai.reco.refresh 발행 → runner에서 ai_reco.update(payload) 호출
                    try:
                        import app.core.bus as eventbus
                        eventbus.publish("ai.reco.refresh", {})
                        self._log.warning("[AI-RECO][PUB] topic=ai.reco.refresh source=config_tabs:_on_save_apply")
                    except Exception:
                        pass
                    # ✅ P0-UI-GLOBAL-STATUS: 전역 상태바 업데이트
                    if hasattr(self, '_parent_window') and self._parent_window:
                        try:
                            self._parent_window.set_global_status("✅ 전략 설정 저장됨", "ok", "save")
                        except Exception:
                            pass
                else:
                    self._info("⚠️ 전략 저장 중 오류가 발생했습니다.")
                    
                    # ✅ P0-UI-GLOBAL-STATUS: 전역 상태바 업데이트
                    if hasattr(self, '_parent_window') and self._parent_window:
                        try:
                            self._parent_window.set_global_status("🔴 저장 실패: 에러 발생", "err", "save")
                        except Exception:
                            pass
            finally:
                # ✅ 저장 가드 해제
                self._saving_strategy = False
                
        except Exception as e:
            if hasattr(self, '_saving_strategy'):
                self._saving_strategy = False
            self._info(f"전략 저장 중 오류: {e}")
            self._log.exception(f"[STRATEGY] save error: {e}")
    
    def _on_manage_watchlist(self):
        """Handle watchlist management button click"""
        # 워치리스트 관리 다이얼로그 열기
        dialog = QDialog(self)
        dialog.setWindowTitle("워치리스트 관리")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 상단 검색창
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("검색:"))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("종목 코드 또는 이름 입력...")
        search_layout.addWidget(search_edit)
        
        btn_search = QPushButton("검색")
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)
        
        # 전체 종목 리스트
        layout.addWidget(QLabel("전체 종목 (거래대금순 1-20위):"))
        lst_all_stocks = QListWidget()
        lst_all_stocks.setMinimumHeight(200)
        lst_all_stocks.setMinimumWidth(300)  # 더 넓게 설정
        lst_all_stocks.setResizeMode(QListWidget.Adjust)
        lst_all_stocks.setUniformItemSizes(False)
        lst_all_stocks.setFont(self.font())  # 현재 폰트 설정
        layout.addWidget(lst_all_stocks)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        btn_add_white = QPushButton("화이트리스트 추가")
        btn_add_black = QPushButton("블랙리스트 추가")
        btn_remove = QPushButton("제거")
        btn_refresh = QPushButton("새로고침")
        
        btn_layout.addWidget(btn_add_white)
        btn_layout.addWidget(btn_add_black)
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_refresh)
        layout.addLayout(btn_layout)
        
        # 확인/취소 버튼
        confirm_layout = QHBoxLayout()
        btn_apply = QPushButton("반영")
        btn_cancel = QPushButton("취소")
        confirm_layout.addWidget(btn_apply)
        confirm_layout.addWidget(btn_cancel)
        layout.addLayout(confirm_layout)
        
        # 로컬 함수들 정의
        def load_top_stocks():
            """KRW 시장 기준 거래대금순 1-20위 코인 로드"""
            try:
                # 실제 KRW 시장 거래대금순 1-20위 (거래대금 포함)
                top_krw_coins_with_volume = [
                    ("AKN", "아카시네트워크", 125000000000),  # 1,250억
                    ("BTC", "비트코인", 98000000000),     # 980억
                    ("ETH", "이더리움", 76000000000),      # 760억
                    ("XRP", "리플", 54000000000),         # 540억
                    ("DOGE", "도지코인", 42000000000),      # 420억
                    ("SOL", "솔라나", 38000000000),        # 380억
                    ("ADA", "카르다노", 32000000000),       # 320억
                    ("SHIB", "시바이누", 28000000000),      # 280억
                    ("AVAX", "아발란치", 24000000000),      # 240억
                    ("DOT", "폴카닷", 21000000000),        # 210억
                    ("MATIC", "폴리곤", 18000000000),      # 180억
                    ("LINK", "체인링크", 15000000000),      # 150억
                    ("UNI", "유니스왑", 13000000000),        # 130억
                    ("LTC", "라이트코인", 11000000000),      # 110억
                    ("ATOM", "코스모스", 9500000000),       # 95억
                    ("FIL", "파일코인", 8500000000),        # 85억
                    ("ETC", "이더리움클래식", 7500000000),  # 75억
                    ("XLM", "스텔라루멘", 6500000000),      # 65억
                    ("VET", "베체인", 5500000000),         # 55억
                ]
                
                # 거래대금순으로 정렬 (이미 정렬되어 있지만 안전장치)
                sorted_coins = sorted(top_krw_coins_with_volume, key=lambda x: x[2], reverse=True)
                
                lst_all_stocks.clear()
                for symbol, name, volume in sorted_coins:
                    # 포맷: "심볼 한글이름 (거래대금)"
                    display_text = f"{symbol} {name} ({volume//100000000}억)"
                    lst_all_stocks.addItem(display_text)
                    
                self._info(f"KRW 시장 거래대금순 1-20위 코인을 로드했습니다.")
                
            except Exception as e:
                self._log.error(f"코인 로드 오류: {e}")
                self._info("코인 로드 중 오류가 발생했습니다.")
        
        def search_stocks():
            """종목 검색"""
            search_text = search_edit.text().strip()
            if not search_text:
                load_top_stocks()
                return
                
            # 검색 로직 (거래대금순 데이터 기반)
            lst_all_stocks.clear()
            all_krw_coins_with_volume = [
                ("AKN", "아카시네트워크", 125000000000),  # 1,250억
                ("BTC", "비트코인", 98000000000),     # 980억
                ("ETH", "이더리움", 76000000000),      # 760억
                ("XRP", "리플", 54000000000),         # 540억
                ("DOGE", "도지코인", 42000000000),      # 420억
                ("SOL", "솔라나", 38000000000),        # 380억
                ("ADA", "카르다노", 32000000000),       # 320억
                ("SHIB", "시바이누", 28000000000),      # 280억
                ("AVAX", "아발란치", 24000000000),      # 240억
                ("DOT", "폴카닷", 21000000000),        # 210억
                ("MATIC", "폴리곤", 18000000000),      # 180억
                ("LINK", "체인링크", 15000000000),      # 150억
                ("UNI", "유니스왑", 13000000000),        # 130억
                ("LTC", "라이트코인", 11000000000),      # 110억
                ("ATOM", "코스모스", 9500000000),       # 95억
                ("FIL", "파일코인", 8500000000),        # 85억
                ("ETC", "이더리움클래식", 7500000000),  # 75억
                ("XLM", "스텔라루멘", 6500000000),      # 65억
                ("VET", "베체인", 5500000000),         # 55억
            ]
            
            # 검색 후 거래대금순 정렬
            filtered_coins = []
            for symbol, name, volume in all_krw_coins_with_volume:
                if search_text.upper() in symbol.upper() or search_text in name:
                    filtered_coins.append((symbol, name, volume))
            
            # 거래대금순으로 정렬
            sorted_filtered = sorted(filtered_coins, key=lambda x: x[2], reverse=True)
            
            for symbol, name, volume in sorted_filtered:
                display_text = f"{symbol} {name} ({volume//100000000}억)"
                lst_all_stocks.addItem(display_text)
                
            self._info(f"\'{search_text}\' 검색 결과: {lst_all_stocks.count()}개")
        
        def add_to_whitelist():
            """화이트리스트에 추가"""
            selected_items = lst_all_stocks.selectedItems()
            if not selected_items:
                self._info("추가할 종목을 선택해주세요.")
                return
                
            for item in selected_items:
                text = item.text()
                # 심볼만 추출 (공백 기준 첫 부분)
                symbol = text.split()[0] if text.split() else text
                # 중복 체크
                existing_items = [self.lst_whitelist.item(i).text().split()[0] for i in range(self.lst_whitelist.count())]
                if symbol not in existing_items:
                    self.lst_whitelist.addItem(text)
                    
            self._info(f"{len(selected_items)}개 종목을 화이트리스트에 추가했습니다.")
        
        def add_to_blacklist():
            """블랙리스트에 추가"""
            selected_items = lst_all_stocks.selectedItems()
            if not selected_items:
                self._info("추가할 종목을 선택해주세요.")
                return
                
            for item in selected_items:
                text = item.text()
                # 심볼만 추출 (공백 기준 첫 부분)
                symbol = text.split()[0] if text.split() else text
                # 중복 체크
                existing_items = [self.lst_blacklist.item(i).text().split()[0] for i in range(self.lst_blacklist.count())]
                if symbol not in existing_items:
                    self.lst_blacklist.addItem(text)
                    
            self._info(f"{len(selected_items)}개 종목을 블랙리스트에 추가했습니다.")
        
        def remove_from_lists():
            """선택된 항목 제거"""
            # 화이트리스트에서 제거
            selected_white = self.lst_whitelist.selectedItems()
            for item in selected_white:
                self.lst_whitelist.takeItem(self.lst_whitelist.row(item))
                
            # 블랙리스트에서 제거
            selected_black = self.lst_blacklist.selectedItems()
            for item in selected_black:
                self.lst_blacklist.takeItem(self.lst_blacklist.row(item))
                
            total_removed = len(selected_white) + len(selected_black)
            if total_removed > 0:
                self._info(f"{total_removed}개 항목을 제거했습니다.")
        
        def apply_watchlist_changes():
            """워치리스트 변경사항을 전략설정에 실제 반영"""
            try:
                self._log.info("[WATCHLIST] APPLY_START whitelist_count=%d blacklist_count=%d", 
                               self.lst_whitelist.count(), self.lst_blacklist.count())
                
                # 화이트리스트 저장
                whitelist = []
                for i in range(self.lst_whitelist.count()):
                    whitelist.append(self.lst_whitelist.item(i).text())
                    
                # 블랙리스트 저장
                blacklist = []
                for i in range(self.lst_blacklist.count()):
                    blacklist.append(self.lst_blacklist.item(i).text())
                    
                # 실제 전략설정에 반영
                white_count = len(whitelist)
                black_count = len(blacklist)
                
                # 1. Draft 상태에만 반영 (Saved 직접 수정 금지)
                if not hasattr(self, '_draft_strategy'):
                    self._draft_strategy = {}
                
                self._draft_strategy['whitelist'] = whitelist
                self._draft_strategy['blacklist'] = blacklist
                
                self._log.info("[WATCHLIST] DRAFT_UPDATE whitelist=%d blacklist=%d", len(whitelist), len(blacklist))
                
                # ✅ P2-5: Dirty 상태 설정
                self._is_dirty = True
                self._update_dirty_indicator()
                
                # 2. UI 표시만 변경 (전략요약 갱신 금지)
                # self._update_summary("watchlist_updated")
                
                # 3. 화이트/블랙리스트 UI에 실제 반영
                # 현재 리스트에 있는 내용을 그대로 유지 (이미 UI에 반영됨)
                
                # 4. 성공 메시지 (임시 반영임을 명확히 표시)
                self.info_label.setText(f"⚠️ 워치리스트 변경이 임시 반영되었습니다. 저장/적용을 눌러 확정하세요. (화이트: {white_count}개, 블랙: {black_count}개)")
                
                # 5. 로그 기록
                self._log.info(f"워치리스트 임시 반영(Draft): 화이트={whitelist}, 블랙={blacklist}")
                
                # 6. 사용자 피드백
                self._info(f"워치리스트 변경이 임시 반영되었습니다. 저장/적용을 눌러 확정하세요. (화이트: {white_count}, 블랙: {black_count})")
                
                # 7. ✅ P1: 이벤트 발행으로 StrategyTab 동기화
                try:
                    import app.core.bus as eventbus
                    eventbus.publish("watchlist.apply.visible_symbols", {
                        "whitelist": whitelist,
                        "blacklist": blacklist,
                        "source": "config_tabs_apply"
                    })
                    self._log.info("[WATCHLIST] PUBLISH_APPLY whitelist=%d blacklist=%d", len(whitelist), len(blacklist))
                except Exception as e:
                    self._log.error(f"Failed to publish watchlist apply event: {e}")
                
                dialog.accept()
                
            except Exception as e:
                self._log.error(f"워치리스트 적용 오류: {e}")
                QMessageBox.warning(self, "오류", f"워치리스트 적용 중 오류가 발생했습니다: {e}")
        
        # 시그널 연결
        btn_search.clicked.connect(search_stocks)
        btn_refresh.clicked.connect(load_top_stocks)
        btn_add_white.clicked.connect(add_to_whitelist)
        btn_add_black.clicked.connect(add_to_blacklist)
        btn_remove.clicked.connect(remove_from_lists)
        btn_apply.clicked.connect(apply_watchlist_changes)
        btn_cancel.clicked.connect(dialog.reject)
        
        # 초기 데이터 로드
        load_top_stocks()
        
        # 다이얼로그 실행
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._log.info("[WATCHLIST] DIALOG_ACCEPTED")
            self._info("워치리스트 변경사항이 적용되었습니다.")
    
    
    def _info(self, msg: str):
        """Single helper for info box messages"""
        self.info_label.setText(msg)
    
    def _build_strategy_summary_display(self):
        """Create enhanced strategy summary using original build_strategy_info_line()"""
        try:
            # ✅ build_strategy_info_line 은 어떤 경로든 반드시 정의되어야 함
            from app.utils.prefs import build_strategy_info_line
            
            # ✅ main window 캐시 getter 사용
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            
            if main_window:
                settings = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                settings = load_settings()
            
            # Get original technical summary
            tech_summary = build_strategy_info_line(settings)
            
            # Create Korean human-readable version
            if hasattr(settings, 'strategy') and settings.strategy:
                strategy = settings.strategy
                if hasattr(strategy, 'model_dump'):
                    strategy = strategy.model_dump()
                
                mode = getattr(strategy, 'strategy_mode', 'MOMENTUM')
                aggr = getattr(strategy, 'aggressiveness_level', 5)
                pos = getattr(strategy, 'pos_size_pct', 2.5)  # percent 단위로 읽기
                rr = getattr(strategy, 'rr_ratio', 2.0)
                cd = getattr(strategy, 'cooldown_sec', 30)
                dll = getattr(strategy, 'daily_loss_limit_pct', 3.0)  # percent 단위로 읽기
                indicators = getattr(strategy, 'indicators', [])
                whitelist = getattr(strategy, 'whitelist', [])
                blacklist = getattr(strategy, 'blacklist', [])
            else:
                mode = strategy.get('strategy_mode', 'ai')
                aggr = strategy.get('aggressiveness_level', 5)
                pos = strategy.get('pos_size_pct', 2.5)  # percent 단위
                rr = strategy.get('rr_ratio', 2.0)
                cd = strategy.get('cooldown_sec', 30)
                dll = strategy.get('daily_loss_limit_pct', 3.0)  # percent 단위
                indicators = strategy.get('indicators', [])
                whitelist = strategy.get('whitelist', [])
                blacklist = strategy.get('blacklist', [])
            
            # Korean mode names
            mode_names = {'avoid': '회피', 'trend_following': '추세', 'ai': 'AI'}
            mode_kr = mode_names.get(mode, mode)
            
            # Format position as percentage (이미 percent 단위)
            try:
                pos_pct = float(pos)  # 이미 percent 단위
                pos_str = f"{pos_pct:.1f}%"
            except:
                pos_str = "—"
            
            # Format daily loss as percentage (이미 percent 단위)
            try:
                dll_pct = float(dll)  # 이미 percent 단위
                dll_str = f"{dll_pct:.1f}%"
            except:
                dll_str = "—"
            
            # Format indicators
            if indicators and isinstance(indicators, str):
                indicators = indicators.split(',')
            if indicators:
                inds_display = ', '.join([i.upper() for i in indicators[:3]])
                if len(indicators) > 3:
                    inds_display += f" 외{len(indicators)-3}개"
            else:
                inds_display = "사용 안함"
            
            # ✅ 워치리스트 정보 포맷팅 (load_settings() 기반으로 SSOT 준수)
            try:
                from app.utils.prefs import load_settings
                settings = load_settings()
                strategy = getattr(settings, 'strategy', None)
                whitelist = getattr(strategy, 'whitelist', []) if strategy else []
                blacklist = getattr(strategy, 'blacklist', []) if strategy else []
                
                self._log.debug(f"[STRAT-SUMMARY] watchlist from load_settings: wl={len(whitelist)} bl={len(blacklist)}")
            except Exception as e:
                self._log.exception(f"[STRAT-SUMMARY] watchlist load error: {e}")
                whitelist = []
                blacklist = []
            
            # 전략요약에서는 카운트만 표시
            watchlist_info = ""
            if whitelist:
                watchlist_info = f"🟢 화이트리스트 {len(whitelist)}개"
            if blacklist:
                if watchlist_info:
                    watchlist_info += " | "
                watchlist_info += f"🔴 블랙리스트 {len(set(blacklist))}개"
            if not watchlist_info:
                watchlist_info = "📋 워치리스트 미설정"
            
            # 한국어 요약 생성
            kr_summary = f"📊 현재 전략: {mode_kr} 모드 | 공격성 {aggr}/10\n"
            kr_summary += f"💰 포지션 비중(1종목 최대) {pos_str} | 손익비(RR) {rr:.1f} | 쿨다운 {cd}초 | 일일 손실 한도(%): {dll_str}\n"
            kr_summary += f"📈 지표: {inds_display}\n"
            kr_summary += f"🎯 {watchlist_info}"
            
            # Combine both for tooltip (technical) and display (Korean)
            return kr_summary, tech_summary
            
        except Exception as e:
            self._log.exception(f"[STRAT-SUMMARY] build error: {e}")
            return "⚠️ 전략 요약을 불러올 수 없습니다", "strategy=—"
    
    def _update_summary_from_settings(self, settings):
        """리디자인: 설정 기준으로 실행 상태·성향 라디오·주문값만 동기화."""
        try:
            if settings is None:
                main_window = self.parent()
                while main_window and not hasattr(main_window, "_get_settings_cached"):
                    main_window = main_window.parent() if hasattr(main_window, "parent") else None
                settings = main_window._get_settings_cached() if main_window else None
            if not settings or not hasattr(settings, "strategy"):
                return
            stg = settings.strategy
            aggr = getattr(stg, "aggressiveness", "neutral") or "neutral"
            if hasattr(self, "radio_avoid"):
                self.radio_avoid.setChecked(aggr == "conservative")
            if hasattr(self, "radio_trend"):
                self.radio_trend.setChecked(aggr == "neutral")
            if hasattr(self, "radio_ai"):
                self.radio_ai.setChecked(aggr == "aggressive")
            if hasattr(self, "radio_aggr_conservative"):
                self.radio_aggr_conservative.setChecked(aggr == "conservative")
            if hasattr(self, "radio_aggr_neutral"):
                self.radio_aggr_neutral.setChecked(aggr == "neutral")
            if hasattr(self, "radio_aggr_aggressive"):
                self.radio_aggr_aggressive.setChecked(aggr == "aggressive")
            if hasattr(self, "spn_order_amount"):
                self.spn_order_amount.setValue(int(getattr(stg, "order_amount_krw", 10000) or 10000))
            if hasattr(self, "spn_max_invest_cap"):
                self.spn_max_invest_cap.setValue(int(getattr(stg, "max_invest_cap_krw", 0) or 0))
            if hasattr(self, "chk_allow_downscale"):
                self.chk_allow_downscale.setChecked(bool(getattr(stg, "allow_downscale_order_amount", False)))
            if hasattr(self, "cmb_exit_mode"):
                em = str(getattr(stg, "exit_mode", "ai") or "ai").lower()
                if em in ("ai", "user", "trail") and self.cmb_exit_mode.findText(em) >= 0:
                    self.cmb_exit_mode.setCurrentText(em)
            sl_v = float(getattr(stg, "stop_loss_pct", 0.0) or 0.0)
            tp_v = float(getattr(stg, "take_profit_pct", 0.0) or 0.0)

            # 주문설정(표준 UI): 0.0 폴백 고정
            if hasattr(self, "spn_stop_loss_pct"):
                self.spn_stop_loss_pct.setValue(sl_v)
            if hasattr(self, "spn_take_profit_pct"):
                self.spn_take_profit_pct.setValue(tp_v)

            # 고급모드(하위호환): 2/5 고정 폴백 금지(0.0으로)
            if hasattr(self, "spn_stop_loss"):
                self.spn_stop_loss.setValue(sl_v)
            if hasattr(self, "spn_take_profit"):
                self.spn_take_profit.setValue(tp_v)

            if hasattr(self, "_update_tp_sl_status"):
                self._update_tp_sl_status()
            self._update_run_status_card()
            if hasattr(self, "lbl_strat_summary"):
                self.lbl_strat_summary.setText(f"AI 성향: {aggr} | 주문 {getattr(stg, 'order_amount_krw', 0):,}원")
        except Exception as e:
            self._log.debug("update_summary_from_settings: %s", e)

    def _update_dirty_indicator(self):
        """✅ P2-5: Dirty 상태 표시 업데이트"""
        if self._is_dirty:
            self.lbl_dirty_state.setText("⚠️ 미저장 변경사항 있음")
            self.btn_save_apply.setText(f"💾 {self._save_btn_base_text}")
        else:
            self.lbl_dirty_state.setText("✅ 저장됨")
            self.btn_save_apply.setText(self._save_btn_base_text)

    def _update_summary(self, reason="initial_load"):
        """리디자인: 실행 상태 카드 + 설정 동기화만 수행."""
        try:
            self._update_run_status_card()
            self._update_summary_from_settings(None)
            if reason == "initial_load":
                self._info("전략 설정이 로드되었습니다.")
        except Exception:
            pass

    # 🔷 StrategyTab Splitter 상태 저장/복원 (UI만)
    def _save_strategy_splitter_state(self):
        try:
            s = QSettings("KMTS", "KMTS-v3")
            if self._strategy_vsplitter:
                s.setValue("strategy_tab/vsplitter", self._strategy_vsplitter.saveState())
            if self._strategy_top_hsplitter:
                s.setValue("strategy_tab/top_hsplitter", self._strategy_top_hsplitter.saveState())
        except Exception as e:
            self._log.debug("[SPLITTER] save failed: %s", e)

    def _restore_strategy_splitter_state(self):
        try:
            s = QSettings("KMTS", "KMTS-v3")
            v_state = s.value("strategy_tab/vsplitter", None)
            h_state = s.value("strategy_tab/top_hsplitter", None)
            if v_state and self._strategy_vsplitter:
                self._strategy_vsplitter.restoreState(v_state)
            if h_state and self._strategy_top_hsplitter:
                self._strategy_top_hsplitter.restoreState(h_state)
        except Exception as e:
            self._log.debug("[SPLITTER] restore failed: %s", e)

    # 🔷 종료 시 저장 트리거
    def closeEvent(self, event):
        self._save_strategy_splitter_state()
        super().closeEvent(event)
