from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class AppState:
    user_email: str | None = None
    is_running: bool = False
    is_paused: bool = False

    # AI 추천 연동 상태 (Watchlist/전략요약에서 함께 사용)
    ai_reco_items: list = field(default_factory=list)        # [{"market":"KRW-BTC","score":87.3}, ...]
    ai_reco_regime: dict = field(default_factory=dict)       # {"breadth": ..., "mean_chg": ...}
    ai_reco_strategy: dict = field(default_factory=dict)     # ai.reco.strategy_suggested payload 전체

    def login(self, email: str) -> None:
        self.user_email = email

    def logout(self) -> None:
        self.user_email = None
        self.is_running = False
        self.is_paused = False
        # 세션 종료 시 AI 추천 상태도 초기화
        self.ai_reco_items.clear()
        self.ai_reco_regime.clear()
        self.ai_reco_strategy.clear()

    def set_ai_reco(self, items: list | None, regime: dict | None = None) -> None:
        """
        ai.reco.updated / ai.reco.items 이벤트에서 공통으로 호출할 진입점.
        - items: 리스트 또는 None
        - regime: {"breadth":..., "mean_chg":...} 또는 None
        """
        self.ai_reco_items = list(items or [])
        self.ai_reco_regime = dict(regime or {})

    def set_ai_strategy(self, strategy_payload: dict | None) -> None:
        """
        ai.reco.strategy_suggested payload 전체를 저장.
        UI에서는 이 dict에서 필요한 필드만 꺼내어 사용한다.
        """
        self.ai_reco_strategy = dict(strategy_payload or {})
