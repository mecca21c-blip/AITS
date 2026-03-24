# app/ui/tabs/watchlist_tab.py

# ⚠️ 봉인 선언: 역할 변경/이동/삭제/리팩터링 금지
# - 현 단계에서는 안정화 우선
# - 구조 변경은 v-next에서만 수행
# - 이 파일의 역할/위치/구조는 변경하지 말 것

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, 
    QAbstractItemView, QCheckBox, QTableWidgetItem, QLabel, QPushButton
)
from PySide6.QtCore import Qt, QCoreApplication, QTimer, QMetaObject, Signal, Slot
from PySide6.QtGui import QShowEvent

# ✅ WatchlistTab이 "심볼 산출 + 6개 항목 채우기 + 이벤트 구독"을 단독 소유한다.
# (app_gui.py에서 _rebuild_watchlist_symbols 제거됨에 따른 구조 정리)
import inspect
import os
import time
import logging
import concurrent.futures


def _is_ai_trace() -> bool:
    """KMTS_DEBUG_AI_TRACE=1 일 때만 [WL-SCORE-TRACE] 로그 출력"""
    return os.environ.get("KMTS_DEBUG_AI_TRACE", "0") == "1"


def _get_watchlist_refresh_ms() -> int:
    """KMTS_WATCHLIST_REFRESH_MS 환경변수, 없으면 기본 30000(30초)"""
    try:
        v = os.environ.get("KMTS_WATCHLIST_REFRESH_MS", "30000")
        return max(5000, int(v))  # 최소 5초
    except (ValueError, TypeError):
        return 30000


def _is_wl_perf_gate() -> bool:
    """[WL-PERF] 로그 출력 게이트: KMTS_DEBUG_WL_PERF=1 또는 KMTS_DEBUG_AI_TRACE=1"""
    return os.environ.get("KMTS_DEBUG_WL_PERF", "0") == "1" or _is_ai_trace()


# P0-3: API 호출용 worker (UI thread 블로킹 방지)
# P0-B: max_workers=2 - top20과 ticks 채우기가 병렬로 실행되어, top20 대기 동안에도 가격 표시 가능
_WL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="wl_worker")

import app.core.bus as eventbus
from app.services.upbit import get_tickers, get_top_markets_by_volume
from app.services.market_feed import get_markets_with_names
from app.services.order_service import svc_order
from app.utils.prefs import load_settings

log = logging.getLogger(__name__)

class WatchlistTab(QWidget):    
    """
    KMTS-v3: Watchlist 탭 (소유권 확정)

    ✅ 이 탭이 100% 소유:
    - 심볼 목록 산출(기본 심볼 + TopN 자동)
    - 6개 항목(가격/등락/보유/종목점수/화이트/블랙) 채우기
    - eventbus 구독(ai.reco.updated / ai.reco.items / ai.reco.strategy_suggested)
    - payload {"advice": {...}} / {...} 두 형태 모두 처리

    ❌ app_gui.py는 UI/테이블 직접 접근 금지(호출만 가능)
    """
    # Signal for worker thread → main thread callback (QMetaObject.invokeMethod 대체)
    _top20_flush_signal = Signal()
    _pending_flush_signal = Signal()  # refresh(dict) flush용
    def _norm_krw_market(self, x: str) -> str:
        x = (x or "").strip().upper()
        if not x:
            return ""
        # 이미 "KRW-XXX"면 그대로
        if x.startswith("KRW-"):
            return x
        # "BTC" / "USDT-BTC" 같은 형태가 오면 마지막 토큰만 취함
        if "-" in x:
            x = x.split("-")[-1]
        return f"KRW-{x}"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ✅ P0-WATCHLIST: _log 초기화 확실히 추가
        self._log = logging.getLogger(__name__)
        
        self._subscribed = False
        
        # ✅ SSOT: 내부 체크 상태 저장소 (UI 스캔 금지)
        self._wl_set = set()  # whitelist 상태 저장
        self._bl_set = set()  # blacklist 상태 저장

        # WatchlistTab 내부 캐시/상태(탭이 소유)
        self._wl_symbols: list[str] = []
        
        # ✅ ROOT-FIX: attach_owner(→bootstrap)는 self.tbl 생성 후에만 호출 (테이블 없이 set_symbols 호출 시 실패)
        self._topN_cached: list[str] = []
        self._topN_last_ts: float = 0.0

        # 최신 점수 캐시(탭이 소유)
        self._ai_scores: dict[str, float] = {}
        
        # ✅ P0-UI-HOLDINGS: 컬럼 폭 저장 디바운스 타이머
        self._col_width_save_timer = QTimer()
        self._col_width_save_timer.setSingleShot(True)
        self._col_width_save_timer.timeout.connect(self._save_column_widths_delayed)
        # ✅ P0-4B: 탭 전환 시 refresh 1회 debounce (1~2초)
        self._tab_visible_refresh_timer = QTimer()
        self._tab_visible_refresh_timer.setSingleShot(True)
        self._tab_visible_refresh_timer.timeout.connect(self._do_tab_visible_refresh)
        self._pending_tab_refresh = False
        self._tab_activated_connected = False  # P0-4B: currentChanged 1회 연결
        self._last_poll_empty_trigger_ts = 0.0  # P0-4B: symbols=0 시 refresh throttle
        
        # ✅ P0-BOOT-SCORE-INITIAL: 부트 리프레시 플래그
        self._boot_refreshed = False
        # ✅ P0-HOTFIX: 부팅 직후 첫 1회 fetch/apply 강제 (가드 무시)
        self._wl_boot_done = False
        
        # ✅ P0-WATCHLIST: 체크박스 가드 플래그
        self._restoring_checks = False
        self._pending_restore_timer = None
        self._restore_token = 0
        # ✅ WL-SYNC: set_symbols/refresh로 테이블을 다시 그릴 때 디스크(settings)로 UI를 덮어쓰면
        # 저장 전 체크(draft)가 사라짐. 최초 1회만 settings에서 _wl_set/_bl_set 시드 후 SSOT는 메모리만 사용.
        self._wb_ssot_seeded: bool = False

        # ✅ (핵심) 심볼 → 현재 행 인덱스 맵 (행 탐색 안정화)
        # 테이블이 정렬/갱신/아이템 교체로 흔들려도 점수/가격/보유 업데이트가
        # -1로 빠지지 않도록 단일 소유 맵을 유지한다.
        self._row_map: dict[str, int] = {}
        self._top20_inflight = False  # PATCH-1: top20 중복 실행 방지
        self._top20_applied_flag = False  # top20 한 번이라도 apply되면 True — default3 덮어쓰기 방지
        self._last_interval_top20_ts = 0.0  # 상위 N 주기 갱신(분) 기반 재조회 시각

        # MainWindow(owner) 참조는 이후 2·3단계에서
        # 이벤트버스 구독/화이트·블랙 토글 로직을 탭 안으로 옮길 때 사용한다.
        # 지금은 None 으로만 초기화하고, 실제 주입은 app_gui 쪽에서 attach_owner()로 처리한다.
        self._owner = None  # type: ignore[assignment]

        # 루트 레이아웃 (탭 컨테이너)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ----------------------------
        # WL/BL 상단 버튼 행 (모두체크해제 + 점수 일괄 체크)
        # ----------------------------
        top_btn_layout = QHBoxLayout()
        top_btn_layout.addStretch(1)
        self.btn_clear_all = QPushButton("모두 체크해제", self)
        self.btn_clear_all.clicked.connect(self._on_clear_all_checks)
        self.btn_clear_all.setMaximumWidth(140)
        self.btn_wl_100 = QPushButton("화이트 100점 모두체크", self)
        self.btn_wl_100.clicked.connect(self._on_wl_score_100_plus)
        self.btn_wl_100.setMaximumWidth(160)
        self.btn_wl_100.setToolTip("종목점수 100 이상인 행을 모두 화이트리스트로 체크")
        self.btn_bl_40 = QPushButton("블랙 40점 이하 모두체크", self)
        self.btn_bl_40.clicked.connect(self._on_bl_score_40_below)
        self.btn_bl_40.setMaximumWidth(150)
        self.btn_bl_40.setToolTip("종목점수 40 이하인 행을 모두 블랙리스트로 체크")
        top_btn_layout.addWidget(self.btn_clear_all)
        top_btn_layout.addWidget(self.btn_wl_100)
        top_btn_layout.addWidget(self.btn_bl_40)
        root.addLayout(top_btn_layout)

        # ----------------------------
        # 테이블 생성 (기존 구조 유지)
        # ----------------------------
        self.tbl = QTableWidget(0, 7, self)
        self.tbl.setObjectName("tblWatchlist")
        self.tbl.setHorizontalHeaderLabels(
            ["심볼", "가격", "등락", "보유", "종목점수", "화이트", "블랙"]
        )

        # 헤더/행 표시 스타일
        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        
        # ✅ P0-UI-WATCHLIST: 컬럼 폭 저장/복원
        hdr.sectionResized.connect(self._on_column_resized)
        self._load_column_widths()
        
        # ✅ P0-UI-WATCHLIST-RESTORE-FIX: 모델 리셋 후에도 폭 재적용
        self.tbl.model().layoutChanged.connect(lambda: QTimer.singleShot(50, self._load_column_widths))

        # 선택/편집 동작: 행 단위 선택, 직접 편집은 비활성화
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)

        # 헤더 툴팁 (기존 app_gui.py에 있던 설명 그대로 유지)
        tips = {
            0: "거래 심볼 (예: KRW-BTC)",
            1: "현재가",
            2: "등락률(%)",
            3: "보유수량 여부",
            4: "AI 추천 종목점수",
            5: "화이트리스트(우선 매매 대상)",
            6: "블랙리스트(제외 대상)",
        }
        for idx, tip in tips.items():
            try:
                h = self.tbl.horizontalHeaderItem(idx)
                if h:
                    h.setToolTip(tip)
            except Exception:
                pass

        # ✅ 체크박스는 체크박스가 직접 클릭을 처리하도록 둔다.
        # 다만 "셀 영역 클릭"은 체크박스까지 정확히 눌러야 해서 사용자가 '두 번 클릭' 체감이 생길 수 있다.
        # 그래서 5/6열은 cellClicked로도 토글을 지원한다(체크박스 클릭과 중복 토글은 click-guard로 방지).
        self._wb_click_guard_ts: float = 0.0
        self._wb_click_guard_key: str = ""

        try:
            self.tbl.cellClicked.connect(self._on_wb_cell_clicked)
        except Exception:
            pass

        # ✅ P0-UI-GLOBAL-STATUS-①: 탭 내부 상태바 제거 (전역 상태바로 단일화)
        # self.lbl_status 위젯은 생성하되 레이아웃에는 추가하지 않음
        try:
            self.lbl_status = QLabel("🟢 정상")
            self.lbl_status.setObjectName("watchlist_status")
            self.lbl_status.setFixedHeight(32)
            self.lbl_status.setStyleSheet("""
                QLabel#watchlist_status {
                    background-color: #e8f5e8;
                    border: 1px solid #4caf50;
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-weight: bold;
                    color: #2e7d32;
                    font-size: 12px;
                }
            """)
            # root.addWidget(self.lbl_status)  # ✅ 제거: 전역 상태바로 단일화
        except Exception:
            pass

        root.addWidget(self.tbl)

        self.setLayout(root)

        # Signal-Slot 연결: worker thread → main thread callback 보장
        self._top20_flush_signal.connect(self._wl_flush_top20_cb)
        self._pending_flush_signal.connect(self._wl_flush_pending_cb)

        # ✅ ROOT-FIX: attach_owner(→bootstrap)는 self.tbl 생성 후에만 호출
        if parent is not None:
            self._log.info("[WL-SCORES] init: parent provided, calling attach_owner (tbl ready)")
            self.attach_owner(parent)

    def set_settings(self, s) -> None:
        """app_gui 가 prefs를 폼/메모리에 로드한 뒤 호출 — 다음 테이블 복원 시 디스크 기준으로 WL/BL을 다시 시드."""
        try:
            _ = s
            self._wb_ssot_seeded = False
        except Exception:
            pass

    def attach_owner(self, owner: QWidget) -> None:
        """
        MainWindow(owner) 인스턴스 주입 + 이벤트버스 구독(1회)
        + ✅ 최초 1회 워치리스트 부팅(심볼 산출→표 생성→컬럼 채움)
        """
        self._owner = owner
        
        # ✅ P0-BOOT-SCORE: 구독 시작 로그
        self._log.info(f"[WL-SCORES] init: subscribed={getattr(self, '_subscribed', False)}")
        self._ensure_event_subscriptions()
        self._log.info(f"[WL-SCORES] init: subscribed={getattr(self, '_subscribed', False)} after ensure")

        # ✅ app_gui가 set_symbols를 안 부르거나 순서가 꼬여도, 탭이 스스로 1회는 채운다.
        try:
            self._bootstrap_watchlist(reason="attach_owner")
        except Exception:
            pass

        # ✅ P0-BOOT-SCORE-INITIAL: 자동 리프레시는 부팅 시퀀스에서 처리 (중복 방지)
        # 부팅 시 app_gui.py의 _boot_sequence_step2에서 refresh() 호출

    def set_symbols(self, symbols) -> None:
        """
        ✅ 워치리스트 테이블 '행 생성/표시' 소유권은 WatchlistTab만 가진다.
        app_gui는 심볼 리스트만 넘기고, 실제 렌더링은 여기서 처리한다.
        """
        if not hasattr(self, "tbl") or self.tbl is None:
            self._log.warning("[WL-MODEL] set_symbols skipped: tbl not ready")
            return
        arr = symbols or []
        n = len(arr)
        now = time.time()
        last = getattr(self, "_wl_symbols_log_last", (None, 0.0))
        if last[0] != n or (now - last[1]) >= 5:
            st = inspect.stack()
            caller = st[1].function if len(st) > 1 else "?"
            self._log.info("[WL-SYMBOLS] set_symbols n=%d sample=%s caller=%s", n, arr[:3], caller)
            if _is_wl_perf_gate():
                self._log.info("[WL-SET] set_symbols n=%d sample=%s", n, ",".join(str(x) for x in (arr or [])[:3]))
            self._wl_symbols_log_last = (n, now)
        
        try:
            items = [self._norm_krw_market(str(x)) for x in (symbols or []) if str(x).strip()]
            items = [x for x in items if x]
        except Exception:
            items = []

        # ✅ 비어있으면 표도 비운다(현재 증상 재현 시 즉시 확인 가능)
        if not items:
            try:
                self._wl_symbols = []
            except Exception:
                pass
            try:
                self._log.warning("[WL-MODEL] setRowCount(0) called in set_symbols - items empty")
                self.tbl.setRowCount(0)
            except Exception:
                pass
            return

        # ✅ 핵심: 내부 상태(현재 표시 심볼)를 반드시 저장해야 refresh/poll_tick이 동작한다.
        try:
            self._wl_symbols = list(items)
        except Exception:
            pass

        # ✅ (핵심) 심볼→행 맵 재구성 (set_symbols가 유일한 진실)
        try:
            self._row_map = {sym: idx for idx, sym in enumerate(self._wl_symbols)}
        except Exception:
            self._row_map = {}

        # 1) 행 생성
        try:
            self.tbl.setRowCount(len(items))
            
            # ✅ (c) 테이블에 모델 반영 직후 상태 확인
            set_model_rows = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
            self._log.info(f"[WL-MODEL] step=c rows={set_model_rows}")
        except Exception:
            return

        # 2) 기본 셀 구성 + 체크박스 위젯 구성(5/6열)
        for r, sym in enumerate(items):
            # 심볼(0) + 한글 종목명 병기(예: 비트코인 KRW-BTC)
            try:
                it0 = self.tbl.item(r, 0)
                if it0 is None:
                    it0 = QTableWidgetItem()
                    self.tbl.setItem(r, 0, it0)

                name_map = self._get_market_name_map()
                kname = (name_map.get(sym) or "").strip()
                it0.setText(f"{kname} {sym}" if kname else sym)
                it0.setTextAlignment(Qt.AlignCenter)

                # row 탐색/토글 로직이 깨지지 않도록 "원본 심볼"을 UserRole에 저장
                try:
                    it0.setData(Qt.UserRole, sym)
                except Exception:
                    pass

                # 가격/등락/보유(1~3) placeholder
                for c in range(1, 4):
                    try:
                        if self.tbl.item(r, c) is None:
                            it = QTableWidgetItem("-")
                            it.setTextAlignment(Qt.AlignCenter)
                            self.tbl.setItem(r, c, it)
                    except Exception:
                        pass
                # 종목점수(4): 소스=_ai_scores. 유효 점수만 표시, None/0.0은 "—"
                try:
                    if self.tbl.item(r, 4) is None:
                        sc = (self._ai_scores or {}).get(sym)
                        has_valid = sc is not None and isinstance(sc, (int, float)) and float(sc) != 0.0
                        if has_valid:
                            it = QTableWidgetItem(f"{float(sc):.2f}")
                        else:
                            it = QTableWidgetItem("—")
                        it.setTextAlignment(Qt.AlignCenter)
                        self.tbl.setItem(r, 4, it)
                except Exception:
                    pass

                # 화이트/블랙(5/6) 체크박스 구성
                try:
                    self._ensure_wb_checkbox(r, 5, sym)
                except Exception:
                    pass
                try:
                    self._ensure_wb_checkbox(r, 6, sym)
                except Exception:
                    pass
            except Exception:
                pass

        # 3) settings 기준 체크 상태 동기화 (지연 실행)
        try:
            # ✅ P0-WATCHLIST: 기존 타이머 취소
            if self._pending_restore_timer:
                self._pending_restore_timer.stop()
            
            # ✅ P0-WATCHLIST: 새 토큰으로 restore 예약
            self._restore_token += 1
            current_token = self._restore_token
            
            def delayed_restore():
                if current_token == self._restore_token:
                    self._sync_wb_from_settings(list(items))
            
            self._pending_restore_timer = QTimer()
            self._pending_restore_timer.setSingleShot(True)
            self._pending_restore_timer.timeout.connect(delayed_restore)
            self._pending_restore_timer.start(100)  # 100ms 지연
        except Exception:
            pass

    def eventFilter(self, obj, event):
            # viewport 토글 강제 로직은 사용하지 않는다(체크박스 직접 클릭으로 통일).
            return super().eventFilter(obj, event)

    def showEvent(self, event: QShowEvent) -> None:
        """P0-4B: 탭 전환(activated) 시 refresh 1회 보장, 1~2초 debounce로 중복 방지"""
        super().showEvent(event)
        self._connect_tab_activated_once()
        self.on_tab_activated()

    def _connect_tab_activated_once(self) -> None:
        """P0-4B: currentChanged 연결 1회 (showEvent만으로 놓치는 경우 대비).
        QTabWidget 구조: Widget->StackedWidget->Container->QTabWidget. 부모를 올라가며 찾음."""
        if getattr(self, "_tab_activated_connected", False):
            return
        try:
            w = self.parent()
            while w and hasattr(w, "parent"):
                if hasattr(w, "currentChanged") and hasattr(w, "indexOf"):
                    tw = w
                    break
                w = w.parent()
            else:
                return
            my_idx = tw.indexOf(self)
            if my_idx < 0:
                return

            def _on_tab_changed(i):
                if i == my_idx:
                    self.on_tab_activated()

            tw.currentChanged.connect(_on_tab_changed)
            self._tab_activated_connected = True
        except Exception:
            pass

    def on_tab_activated(self) -> None:
        """P0-4B: 탭 선택(activated) 시 refresh 1회 예약. 1초 debounce로 중복 방지."""
        self._tab_visible_refresh_timer.stop()
        self._tab_visible_refresh_timer.start(1000)  # 1초 debounce — 탭 전환 시 반드시 1회 refresh 보장

    def _do_tab_visible_refresh(self) -> None:
        """P0-4B: debounce 타이머 만료 시, 탭이 보이면 refresh 1회 강제 (가격/등락 채우기).
        isVisible()이 아직 False면 Qt 타이밍 이슈로 1회 재시도(200ms)."""
        if not self.isVisible():
            retry = getattr(self, "_tab_visible_retry_count", 0)
            if retry < 1:
                self._tab_visible_retry_count = retry + 1
                QTimer.singleShot(200, self._do_tab_visible_refresh)
                return
            self._tab_visible_retry_count = 0
            return
        self._tab_visible_retry_count = 0
        self._pending_tab_refresh = False  # 이번 refresh로 소비
        if hasattr(self, "refresh"):
            self.refresh(caller="tab_visible")

    def _on_tab_visible_refresh(self) -> None:
        """(레거시) QTimer.singleShot 콜백용. _do_tab_visible_refresh로 대체됨."""
        self._do_tab_visible_refresh()

    def _ensure_wb_checkbox(self, row: int, col: int, sym_hint: str = "") -> None:
        """
        화이트/블랙 컬럼(5/6)은 QTableWidgetItem 텍스트가 아니라 체크박스를 사용한다.

        ✅ 현재 단계에서 확정:
        - 클릭 토글이 "저장"까지 반영되어야 새로고침/AI push 후에도 체크가 되돌아가지 않는다.
        - 화이트/블랙은 상호배타(동시에 체크 불가)
        """
        if self.tbl.cellWidget(row, col) is not None:
            return

        cb = QCheckBox()
        cb.setTristate(False)

        # ✅ 체크박스는 직접 클릭 가능해야 한다(현재 증상: 클릭해도 무반응)
        cb.setFocusPolicy(Qt.NoFocus)


        cb.setProperty("kmts_col", int(col))

        sym = (sym_hint or "").strip().upper()
        if not sym:
            try:
                it = self.tbl.item(row, 0)
                sym = (it.text() if it else "") or ""
                sym = sym.strip().upper()
            except Exception:
                sym = ""
        cb.setProperty("kmts_symbol", sym)

        try:
            # ✅ clicked 기반(사용자 클릭 의도에 더 가깝고, programmatic setChecked 영향이 덜함)
            cb.clicked.connect(self._on_wb_checkbox_changed)
        except Exception:
            pass

        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(cb)

        self.tbl.setCellWidget(row, col, box)

    def _set_wb_sets(self, wl: set[str], bl: set[str]) -> None:
        """
        ✅ SSOT: 내부 체크 상태 저장소만 업데이트 (디스크 저장 금지)
        - UI 스캔 방지로 안정성 확보
        - 이벤트 발행은 _on_wb_checkbox_changed에서 처리
        """
        # 내부 상태 저장소 업데이트
        self._wl_set = set(wl)
        self._bl_set = set(bl)
        
        # 디버그 로그
        log.debug(f"[WATCHLIST] internal state updated: wl={len(self._wl_set)} bl={len(self._bl_set)}")

    def _on_wb_cell_clicked(self, row: int, col: int) -> None:
        """
        ✅ 셀 영역 클릭으로도 토글되게 지원(사용자가 체크박스를 정확히 눌러야 하는 불편 제거)
        - 체크박스 자체 클릭과의 "중복 토글"은 click-guard로 방지
        """
        if col not in (5, 6):
            return

        # click-guard: 같은 이벤트에서 checkbox clicked + cellClicked가 연달아 오는 케이스 방지
        try:
            now = time.time()
        except Exception:
            now = 0.0
        key = f"{row}:{col}"
        if self._wb_click_guard_key == key and (now - self._wb_click_guard_ts) < 0.15:
            return

        box = self.tbl.cellWidget(row, col)
        if box is None:
            return
        cb = box.findChild(QCheckBox)
        if cb is None:
            return

        self._wb_click_guard_key = key
        self._wb_click_guard_ts = now

        try:
            cb.toggle()
        except Exception:
            try:
                cb.setChecked(not cb.isChecked())
            except Exception:
                pass

    def _on_wb_checkbox_changed(self, checked: bool) -> None:
        """
        ✅ SSOT: 체크박스 토글 시 내부 상태 저장소 기반으로 단일 처리
        - 상호배타성 강제
        - UI 스캔 금지로 안정성 확보
        """
        # ✅ P0-WATCHLIST: 체크 복원 중에는 사용자 변경 무시
        if self._restoring_checks:
            return
            
        try:
            sender = self.sender()
        except Exception:
            sender = None

        if sender is None or not isinstance(sender, QCheckBox):
            return

        try:
            col = int(sender.property("kmts_col") or 0)
        except Exception:
            col = 0

        sym = str(sender.property("kmts_symbol") or "").upper()
        if not sym:
            try:
                r_guess = -1
                for r in range(self.tbl.rowCount()):
                    w = self.tbl.cellWidget(r, col)
                    if w is not None:
                        cb = w.findChild(QCheckBox)
                        if cb is sender:
                            r_guess = r
                            break
                if r_guess >= 0:
                    it = self.tbl.item(r_guess, 0)
                    sym = (it.text() if it else "") or ""
                    sym = sym.upper()
                    sender.setProperty("kmts_symbol", sym)
            except Exception:
                sym = ""

        if not sym:
            return

        checked = bool(checked)
        sym_k = self._norm_krw_market(sym)
        if not sym_k:
            return

        # ✅ STEP 1: 내부 상태 저장소에서 현재 상태 로드
        wl = set(self._wl_set)
        bl = set(self._bl_set)
        
        # ✅ STEP 2: 상호배타성 강제 및 상태 업데이트
        if col == 5:  # 화이트 체크
            if checked:
                wl.add(sym_k)
                bl.discard(sym_k)  # 블랙에서 제거
            else:
                wl.discard(sym_k)
        elif col == 6:  # 블랙 체크
            if checked:
                bl.add(sym_k)
                wl.discard(sym_k)  # 화이트에서 제거
            else:
                bl.discard(sym_k)

        # ✅ STEP 3: 내부 상태 저장소 업데이트
        self._wl_set = wl
        self._bl_set = bl
        
        # ✅ STEP 4: UI 동기화 (상호배타성 적용)
        self._sync_ui_checkbox(sym_k, wl, bl)

        if col == 5:
            act = "wl_on" if checked else "wl_off"
        elif col == 6:
            act = "bl_on" if checked else "bl_off"
        else:
            act = "unknown"
        ui_wl_after = self._count_ui_wl_checks()
        self._log.info(
            "[WL-SYNC] ui_checked=%s model_checked=%s action=%s sym=%s",
            ui_wl_after,
            len(wl),
            act,
            sym_k,
        )

        # ✅ STEP 5: 전체 리스트 발행
        whitelist_list = sorted(list(wl))
        blacklist_list = sorted(list(bl))
        
        log.info("[WL-APPLY] whitelist_n=%d blacklist_n=%d symbols=%s", len(whitelist_list), len(blacklist_list), whitelist_list)
        log.info(f"[WATCHLIST] publishing wb.changed wl={len(wl)} bl={len(bl)} whitelist={whitelist_list} blacklist={blacklist_list} last={sym_k}")
        
        eventbus.publish("watchlist.wb.changed", {
            "whitelist": whitelist_list,
            "blacklist": blacklist_list,
            "source": "watchlist_tab",
            # ✅ draft_view: 체크 변경 중(저장 전)
            # ✅ apply_view : 반영 버튼으로 확정(저장/StrategyTab 동기화 트리거)
            "mode": "draft_view",
            # ✅ 하위호환/안전: payload 직접형/{"advice":{...}} 혼용처럼
            # 수신자가 payload.get(...)만으로 안전 처리 가능하도록 키 고정
        })

    def _sync_ui_checkbox(self, sym_k: str, wl: set[str], bl: set[str]) -> None:
        """특정 심볼의 UI 체크박스를 내부 상태와 동기화"""
        try:
            row = self._row_index_of(sym_k)
            if row < 0:
                return
                
            # 화이트 체크박스 동기화
            w_box = self.tbl.cellWidget(row, 5)
            if w_box is not None:
                cb = w_box.findChild(QCheckBox)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(sym_k in wl)
                    cb.blockSignals(False)
            
            # 블랙 체크박스 동기화
            b_box = self.tbl.cellWidget(row, 6)
            if b_box is not None:
                cb = b_box.findChild(QCheckBox)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(sym_k in bl)
                    cb.blockSignals(False)
        except Exception as e:
            log.error(f"[WATCHLIST] UI sync error for {sym_k}: {e}")

    def _on_clear_all_checks(self) -> None:
        """✅ SSOT: 모든 체크박스 해제 및 이벤트 발행"""
        try:
            # ✅ 내부 상태 저장소 초기화
            self._wl_set.clear()
            self._bl_set.clear()
            
            # ✅ UI 체크박스 모두 해제
            for r in range(self.tbl.rowCount()):
                for col in (5, 6):
                    box = self.tbl.cellWidget(r, col)
                    if box is not None:
                        cb = box.findChild(QCheckBox)
                        if cb is not None:
                            cb.blockSignals(True)
                            cb.setChecked(False)
                            cb.blockSignals(False)
            
            # ✅ 빈 리스트 발행
            log.info("[WL-APPLY] whitelist_n=0 blacklist_n=0 symbols=%s action=clear_all", [])
            log.info(f"[WATCHLIST] publishing wb.changed wl=0 bl=0 whitelist=[] blacklist=[] source=clear_all")
            eventbus.publish("watchlist.wb.changed", {
                "whitelist": [],
                "blacklist": [],
                "source": "watchlist_tab",
                # ✅ draft_view: 체크 변경 중(저장 전)
                # ✅ apply_view : 반영 버튼으로 확정(저장/StrategyTab 동기화 트리거)
                "mode": "draft_view",
                # ✅ 하위호환/안전: payload 직접형/{"advice":{...}} 혼용처럼
                # 수신자가 payload.get(...)만으로 안전 처리 가능하도록 키 고정
            })
            
        except Exception as e:
            log.error(f"[WATCHLIST] clear all checks error: {e}")

    def _get_row_score(self, row: int) -> float | None:
        """행의 종목점수(컬럼 4)를 float으로 반환. 없거나 숫자가 아니면 None."""
        try:
            item = self.tbl.item(row, 4)
            if item is None:
                return None
            text = (item.text() or "").strip()
            if not text or text == "-":
                return None
            return float(text)
        except (ValueError, TypeError):
            return None

    def _get_row_symbol(self, row: int) -> str | None:
        """행의 심볼(컬럼 0 UserRole 또는 텍스트에서 추출) 반환."""
        try:
            item = self.tbl.item(row, 0)
            if item is None:
                return None
            sym = item.data(Qt.UserRole)
            if sym:
                return self._norm_krw_market(str(sym))
            text = (item.text() or "").strip()
            for part in text.split():
                if part.startswith("KRW-"):
                    return self._norm_krw_market(part)
            return None
        except Exception:
            return None

    def _on_wl_score_100_plus(self) -> None:
        """점수 100 이상인 행을 모두 화이트리스트로 체크."""
        try:
            for r in range(self.tbl.rowCount()):
                score = self._get_row_score(r)
                sym = self._get_row_symbol(r)
                if sym and score is not None and score >= 100:
                    self._wl_set.add(sym)
                    self._bl_set.discard(sym)
                    self._sync_ui_checkbox(sym, self._wl_set, self._bl_set)
            wl_list = sorted(self._wl_set)
            bl_list = sorted(self._bl_set)
            log.info("[WATCHLIST] 점수 100 이상 → 화이트 적용 wl=%d bl=%d", len(wl_list), len(bl_list))
            log.info("[WL-APPLY] whitelist_n=%d blacklist_n=%d symbols=%s action=wl_100_plus", len(wl_list), len(bl_list), wl_list)
            eventbus.publish("watchlist.wb.changed", {"whitelist": wl_list, "blacklist": bl_list, "source": "watchlist_tab", "mode": "draft_view"})
        except Exception as e:
            log.error("[WATCHLIST] WL 100+ error: %s", e)

    def _on_bl_score_40_below(self) -> None:
        """점수 40 이하인 행을 모두 블랙리스트로 체크."""
        try:
            for r in range(self.tbl.rowCount()):
                score = self._get_row_score(r)
                sym = self._get_row_symbol(r)
                if sym and score is not None and score <= 40:
                    self._bl_set.add(sym)
                    self._wl_set.discard(sym)
                    self._sync_ui_checkbox(sym, self._wl_set, self._bl_set)
            wl_list = sorted(self._wl_set)
            bl_list = sorted(self._bl_set)
            log.info("[WATCHLIST] 점수 40 이하 → 블랙 적용 wl=%d bl=%d", len(wl_list), len(bl_list))
            log.info("[WL-APPLY] whitelist_n=%d blacklist_n=%d symbols=%s action=bl_40_below", len(wl_list), len(bl_list), wl_list)
            eventbus.publish("watchlist.wb.changed", {"whitelist": wl_list, "blacklist": bl_list, "source": "watchlist_tab", "mode": "draft_view"})
        except Exception as e:
            log.error("[WATCHLIST] BL 40- error: %s", e)

    def _get_wb_sets(self) -> tuple[set[str], set[str]]:
        """
        settings.strategy.whitelist / settings.strategy.blacklist 를 안전하게 set으로 반환
        (dict / pydantic model 둘 다 대응)

        ✅ 중요:
        - 반환 set은 항상 'KRW-COIN' 단일 형태로만 구성한다.
        - BTC와 KRW-BTC를 동시에 넣으면 동시 체크가 가능해져 UI가 깨진다.
        """
        s = self._get_settings()
        if s is None:
            return set(), set()

        try:
            stg = getattr(s, "strategy", None)
            if stg is None:
                return set(), set()

            if not isinstance(stg, dict):
                try:
                    stg = stg.model_dump()
                except Exception:
                    stg = {}

            def _norm_one(v: str) -> str:
                v = str(v).strip().upper()
                if not v:
                    return ""
                if v.startswith("KRW-"):
                    return v
                if "-" in v:
                    v = v.split("-")[-1]
                return f"KRW-{v}"

            def _norm_entries(values) -> set[str]:
                out = set()
                for x in (values or []):
                    k = _norm_one(x)
                    if k:
                        out.add(k)
                return out

            wl = _norm_entries(stg.get("whitelist") or [])
            bl = _norm_entries(stg.get("blacklist") or [])

            # ✅ 상호배타 보정(혹시 설정에 동시에 들어있으면 whitelist 우선으로 정리)
            bl = set([x for x in bl if x not in wl])

            return wl, bl
        except Exception:
            return set(), set()

    def get_current_whitelist_blacklist(self) -> tuple[list[str], list[str]]:
        """
        실행 시점 스냅샷: 현재 UI 체크 상태(_wl_set, _bl_set)를 리스트로 반환.
        - 화이트리스트 = 매매 대상 풀(우선순위 가중치)
        - 블랙리스트 = 완전 제외
        """
        wl_list = sorted(self._wl_set) if self._wl_set else []
        bl_list = sorted(self._bl_set) if self._bl_set else []
        return wl_list, bl_list

    def _count_ui_wl_checks(self) -> int:
        """테이블에 표시된 화이트(열 5) 체크 개수 — [WL-SYNC] 디버그용."""
        try:
            n = 0
            for r in range(self.tbl.rowCount()):
                box = self.tbl.cellWidget(r, 5)
                if box is None:
                    continue
                cb = box.findChild(QCheckBox)
                if cb is not None and cb.isChecked():
                    n += 1
            return n
        except Exception:
            return -1

    def get_displayed_symbols_for_snapshot(self, limit: int = 30) -> list[str]:
        """
        실행 순간 스냅샷용: 워치리스트 탭에 현재 표시된 종목 목록(순서 유지).
        - 최대 limit개(기본 30) 반환
        """
        raw = (self._wl_symbols or [])[:limit]
        return [self._norm_krw_market(str(s)) for s in raw if str(s).strip()]

    def _sync_wb_from_settings(self, symbols: list[str]) -> None:
        """
        테이블 행에 화이트/블랙 체크 상태를 SSOT(_wl_set/_bl_set)에 맞춰 복원.

        ✅ 최초 1회만 settings(디스크)에서 _wl_set/_bl_set을 시드한다.
        이후 set_symbols/refresh/탭 전환에서 디스크를 다시 읽지 않아 저장 전 draft가 유지된다.
        """
        # ✅ P0-WATCHLIST: 현재 토큰 확인 및 로그
        current_token = self._restore_token
        n_sym = len(symbols or [])
        self._log.info(f"[WL-RESTORE] start token={current_token} symbols={n_sym}")
        
        if not getattr(self, "_wb_ssot_seeded", False):
            wl_disk, bl_disk = self._get_wb_sets()
            self._wl_set = set(wl_disk)
            self._bl_set = set(bl_disk)
            self._wb_ssot_seeded = True
            self._log.info("[WL-RESTORE] seed_from_disk wl_n=%d bl_n=%d", len(self._wl_set), len(self._bl_set))

        wl, bl = self._wl_set, self._bl_set
        if _is_wl_perf_gate():
            self._log.info("[WL-WB] apply_filter wl_n=%d bl_n=%d result_n=%d", len(wl), len(bl), n_sym)
        
        # ✅ P0-WATCHLIST: 테이블 신호 차단
        self.tbl.blockSignals(True)
        
        # ✅ P0-WATCHLIST: 체크 복원 가드 설정
        self._restoring_checks = True
        
        restored_n = 0
        try:
            for sym in (symbols or []):
                sym_u = self._norm_krw_market(sym)
                r = self._row_index_of(sym_u)
                if r < 0:
                    continue
                restored_n += 1

                w_box = self.tbl.cellWidget(r, 5)
                if w_box is not None:
                    cb = w_box.findChild(QCheckBox)
                    if cb is not None:
                        cb.blockSignals(True)
                        cb.setProperty("kmts_symbol", sym_u)
                        cb.setChecked(sym_u in wl)
                        cb.blockSignals(False)

                b_box = self.tbl.cellWidget(r, 6)
                if b_box is not None:
                    cb = b_box.findChild(QCheckBox)
                    if cb is not None:
                        cb.blockSignals(True)
                        cb.setProperty("kmts_symbol", sym_u)
                        cb.setChecked(sym_u in bl)
                        cb.blockSignals(False)
        finally:
            # ✅ P0-WATCHLIST: 체크 복원 가드 해제
            self._restoring_checks = False
            
            # ✅ P0-WATCHLIST: 테이블 신호 복원
            self.tbl.blockSignals(False)
            
            # ✅ P0-WATCHLIST: 토큰 검증 후 로그 (P0-A: symbols 개수 포함)
            if current_token == self._restore_token:
                ui_ct = self._count_ui_wl_checks()
                self._log.info(
                    "[WL-RESTORE] restored_n=%d wl_n=%d bl_n=%d ui_wl_checked=%d token=%s",
                    restored_n,
                    len(wl),
                    len(bl),
                    ui_ct,
                    current_token,
                )
            if _is_wl_perf_gate():
                self._log.info("[WL-WB] sync_wb wl_n=%d bl_n=%d symbols_n=%d", len(wl), len(bl), n_sym)

    def _show_error_message(self, message: str) -> None:
        """워치리스트 영역에 에러 메시지 표시"""
        try:
            self.tbl.setRowCount(1)
            self.tbl.setColumnCount(1)
            error_item = QTableWidgetItem(message)
            error_item.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(0, 0, error_item)
            
            # ✅ P0-UI-WATCHLIST-STATUS: 오류 상태로 변경
            self._update_status("오류", "error")
        except Exception:
            pass

    def _update_status(self, message: str, level: str = "ok") -> None:
        """✅ P0-UI-WATCHLIST-STATUS: 상태창 업데이트"""
        try:
            if not hasattr(self, 'lbl_status'):
                return
                
            # 텍스트 기반 상태 레벨 자동 판정
            msg_lower = message.lower()
            if level == "ok" or any(word in msg_lower for word in ["정상", "완료", "성공"]):
                icon = "🟢"
                style = """
                    QLabel#watchlist_status {
                        background-color: #e8f5e8;
                        border: 1px solid #4caf50;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-weight: bold;
                        color: #2e7d32;
                        font-size: 12px;
                    }
                """
            elif level == "warn" or any(word in msg_lower for word in ["로딩", "새로고침", "초기화", "대기", "접속"]):
                icon = "⏳"
                style = """
                    QLabel#watchlist_status {
                        background-color: #fff3e0;
                        border: 1px solid #ff9800;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-weight: bold;
                        color: #f57c00;
                        font-size: 12px;
                    }
                """
            elif level == "error" or any(word in msg_lower for word in ["오류", "실패", "에러"]):
                icon = "🔴"
                style = """
                    QLabel#watchlist_status {
                        background-color: #ffebee;
                        border: 1px solid #f44336;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-weight: bold;
                        color: #d32f2f;
                        font-size: 12px;
                    }
                """
            else:
                icon = "🟢"
                style = """
                    QLabel#watchlist_status {
                        background-color: #e8f5e8;
                        border: 1px solid #4caf50;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-weight: bold;
                        color: #2e7d32;
                        font-size: 12px;
                    }
                """
                
            self.lbl_status.setText(f"{icon} {message}")
            self.lbl_status.setStyleSheet(style)
        except Exception:
            pass

    def refresh(self, caller: str = None) -> None:
        """
        ✅ 새로고침(수동 refresh) 동작 고정:
        - 가격/등락/보유는 새로 갱신
        - 종목점수는 "새로고침 시점에는 의미가 없으므로" 무조건 초기화('-') (A안)
          → 이후 ai.reco.* 이벤트가 들어올 때만 점수 채움
        - caller: P0-4A top20_applied 시 명시 전달 (스택 추론 대체)
        """
        import traceback
        
        # ✅ CALLER: 명시 전달 또는 스택 추론
        if caller is None:
            stack = traceback.extract_stack()
            frame = stack[-2]  # Caller frame
            if "tables_timer" in frame.name or "_refresh_visible" in frame.name:
                caller = "tables_timer_tick"
            elif "_on_watchlist_tick" in frame.name:
                caller = "fast_timer_tick"
            elif "dataChanged" in str(frame) or "model" in str(frame):
                caller = "model_signal"
            elif "refresh" in frame.name or "button" in str(frame).lower():
                caller = "manual_refresh_button"
            elif "_execute_watchlist_boot" in frame.name:
                caller = "_execute_watchlist_boot"
            elif "_do_tab_visible_refresh" in frame.name or "_on_tab_visible_refresh" in frame.name:
                caller = "tab_visible"
            else:
                caller = frame.name if hasattr(frame, 'name') else "unknown"
        
        # ✅ P0-4A: top20_applied 호출 시 throttle/inflight 무시 (가격/등락 채우기 강제)
        # ✅ P0-4B: tab_visible/empty_retry/poll_tick_empty 시 throttle 무시 (탭 전환 시 1회 refresh 보장)
        if caller in ("top20_applied", "tab_visible", "empty_retry", "poll_tick_empty"):
            pass  # 아래 가드 모두 통과
        # ✅ 부팅 시 1회만: 호출 스택 로그 (호출자, 타이머, in-flight)
        if caller == "_execute_watchlist_boot" and not getattr(self, "_boot_stack_logged", False):
            self._log.info("[WL-BOOT-STACK] caller=_execute_watchlist_boot timer=app_gui_singleShot inflight=%s", getattr(self, "_refresh_inflight", False))
            self._boot_stack_logged = True
        
        try:
            self._log.info(f"[WL-REFRESH] start caller={caller}")
            
            # ✅ 반복 트리거 가드: 타이머는 부트 1회 완료 전까지 refresh 스킵 (무한 로딩 방지)
            # ✅ P0-HOTFIX: _execute_watchlist_boot 호출 시에는 무조건 실행 (가드 무시)
            if caller == "fast_timer_tick" and not getattr(self, "_boot_refresh_done", False):
                self._log.info("[WL-BOOT] skip timer (boot not done)")
                return
            if caller == "_execute_watchlist_boot":
                self._wl_boot_done = False  # 부팅 직후 첫 1회: fetch/apply 강제
            
            # ✅ RE-ENTRANCY GUARD: Skip if already in flight (top20_applied는 강제 실행)
            if caller != "top20_applied" and getattr(self, '_refresh_inflight', False):
                self._log.info("[WL-REFRESH] skip inflight")
                if caller == "tab_visible":
                    self._pending_tab_refresh = True  # P0-4B: inflight 완료 후 재시도
                return
            
            # ✅ P0-HOTFIX: isVisible() 가드 없음 — 부팅 직후 Trades 탭이 기본이어도 worker/apply 반드시 실행
            
            # ✅ P0-3: THROTTLE GUARD — KMTS_WATCHLIST_REFRESH_MS (기본 30초), 수동/부트/탭전환은 제외
            current_time = time.time()
            last_refresh = getattr(self, '_last_refresh_ts', 0)
            throttle_ms = _get_watchlist_refresh_ms()
            # ✅ P0-HOTFIX: 부팅/탭전환 시 throttle 무시 (최소 1회 fetch/apply 보장)
            if caller in ("fast_timer_tick", "tables_timer_tick") and getattr(self, "_boot_refresh_done", False):
                if current_time - last_refresh < throttle_ms / 1000:
                    self._log.info(f"[WL-REFRESH] skip throttle age={current_time - last_refresh:.3f}s limit={throttle_ms}ms")
                    return
            
            self._refresh_inflight = True
            self._last_refresh_ts = current_time
            t_refresh_start = time.perf_counter()
            
            # ✅ (a) refresh 시작 직후 모델 상태 확인
            tbl_id = id(self.tbl) if hasattr(self, 'tbl') else None
            tbl_rows = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
            self._log.info(f"[WL-MODEL] step=a tbl={tbl_id} rows={tbl_rows}")
            
            # PATCH 4: _wl_symbols>=10이면 최우선 (top20 적용된 세션, compute_symbols_fast 우선순위 싸움 방지)
            symbols = []
            if len(self._wl_symbols or []) >= 10:
                symbols = list(self._wl_symbols or [])
                if symbols:
                    self._log.info("[WL-REFRESH] use _wl_symbols n=%d (top20_session)", len(symbols))
            if not symbols and caller == "top20_applied":
                symbols = list(self._wl_symbols or [])
                if symbols:
                    self._log.info("[WL-REFRESH] use _wl_symbols n=%d (top20_applied)", len(symbols))
            if not symbols and hasattr(self, '_top20_cache') and self._top20_cache:
                cache_time, cached = self._top20_cache
                if (time.time() - cache_time) < 600 and len(cached) >= 10:
                    symbols = list(cached)
                    self._log.info("[WL-REFRESH] use top20_cache n=%d", len(symbols))
            if not symbols:
                symbols = self._compute_symbols_fast() or []
            
            # ✅ P0-HOTFIX: 부팅 첫 1회는 가드 무시, 반드시 worker→apply 수행 (Trades 탭 기본이어도)
            if getattr(self, '_boot_refresh_done', False):
                self._log.info("[WL-BOOT] boot refresh already done (will still run worker if symbols)")
            else:
                self._log.info("[WL-BOOT] refresh start (first boot, worker/apply 강제)")
                self._boot_refresh_done = True
            self._log.info("[WL-BOOT] populated rows=%d", len(symbols))
            
            self._log.info(f"[WL-REFRESH] symbols n={len(symbols)} sample={symbols[:5]}")
            
            # P0-BLOCK 3: 심볼 0개여도 조기 return 금지 — _bootstrap_watchlist가 async top20으로 채움
            if not symbols:
                self._log.info("[WL-REFRESH] symbols=0, bootstrap will async fetch top20")
                
            log.info(f"[WATCHLIST] refresh symbols count={len(symbols)}")
            if symbols:
                log.info(f"[WATCHLIST] refresh symbols[:5]={symbols[:5]}")
        except Exception as e:
            self._log.error(f"[WL-REFRESH] FAIL {e}\n{traceback.format_exc()}")
            if hasattr(self, '_owner') and self._owner:
                try:
                    self._owner.set_global_status(f"🔴 워치리스트 로딩 실패: {e}", "err", "watchlist")
                except Exception:
                    pass
            self._refresh_inflight = False
            return

        # ✅ P0-UI-WATCHLIST-STATUS: 새로고침 시작
        self._update_status("새로고침 중...", "warn")
        
        # ✅ P0-UI-GLOBAL-STATUS: 전역 상태바 업데이트
        if hasattr(self, '_owner') and self._owner:
            try:
                self._owner.set_global_status("워치리스트 갱신 중...", "busy", "watchlist")
            except Exception:
                pass

        # ✅ 핵심: 내부 심볼이 비어있으면 탭이 스스로 심볼 산출/표 생성부터 복구한다.
        self._log.info(f"[WL-MODEL] refresh symbols check: len={len(symbols)} empty={not symbols}")
        if not symbols:
            try:
                self._bootstrap_watchlist(reason="manual_refresh_empty")
                symbols = list(self._wl_symbols or [])
                
                # ✅ (b) populate 직후 모델 상태 확인
                model_rows = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
                self._log.info(f"[WL-MODEL] step=b rows={model_rows}")
            except Exception:
                symbols = []
        else:
            # ✅ P0-A: 더 적은 심볼로 덮어쓰기 방지 (top20 완료 후 refresh가 3으로 덮어쓰는 문제)
            # PATCH-1: top20이 한 번이라도 적용된 세션(_wl_symbols>=10)이면 prefs.symbols fallback으로 되돌리지 않음
            # PATCH-2: 테이블 비어있으면(tbl_rows=0) 절대 skip 금지 — 가격/등락/보유가 적용되려면 행이 있어야 함
            current_n = len(self._wl_symbols or [])
            tbl_rows = self.tbl.rowCount() if hasattr(self, 'tbl') else 0
            _top20_pending = getattr(self, "_top20_pending", False)
            skip_set = (
                tbl_rows > 0  # ✅ 핵심: 테이블 비어있으면 무조건 set_symbols 호출
                and (
                    (
                        current_n > 0
                        and len(symbols) < current_n
                        and (caller == "_execute_watchlist_boot" or _top20_pending or current_n >= 10)
                    )
                    or (
                        _top20_pending and len(symbols) < 10
                        and current_n > 0
                    )
                )
            )
            if skip_set:
                self._log.info("[WL-REFRESH] skip set_symbols(n=%d) current=%d (keep larger)", len(symbols), current_n)
                symbols = list(self._wl_symbols or symbols)
            else:
                # ✅ symbols가 있으면 set_symbols 호출로 테이블 populate
                try:
                    self.set_symbols(symbols)
                    
                    # ✅ (b) populate 직후 모델 상태 확인
                    model_rows = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
                    self._log.info(f"[WL-MODEL] step=b rows={model_rows}")
                except Exception:
                    pass

        if not symbols:
            self._log.info("[WL-REFRESH] skip symbols_n=0 err=no_symbols_after_bootstrap")
            self._update_status("데이터 없음", "warn")
            self._refresh_inflight = False
            return

        # P0-3: API 호출(가격/보유)을 worker에서 비동기 실행 → UI 블로킹 없음
        def _do_fetch():
            return self._fetch_ticks_and_owned(symbols)

        def _on_refresh_fetch_done(result):
            try:
                if result is None:
                    self._log.warning("[WL-WORKER-EMPTY] reason=none_or_exception")
                    self._log.info("[WL-WORKER] done ok=0 ticks_n=0 owned_n=0 err=result_none")
                    result = {"ticks": [], "owned": set(), "errors": {"worker": "exception"}, "symbols": symbols}
                    if hasattr(self, '_owner') and self._owner:
                        try:
                            self._owner.set_global_status("🔴 시세 로딩 실패(네트워크/API)", "err", "watchlist")
                        except Exception:
                            pass
                self._apply_worker_result(result, symbols)
                self._fill_score_column(symbols)
                self._update_status("정상", "ok")
                if hasattr(self, '_owner') and self._owner:
                    try:
                        self._owner.set_global_status("워치리스트 최신화 완료", "ok", "watchlist")
                    except Exception:
                        pass
                rc = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
                self._log.info(f"[WL-REFRESH] applied rows={rc}")
                if _is_wl_perf_gate():
                    elapsed_ms = int((time.perf_counter() - t_refresh_start) * 1000)
                    self._log.info("[WL-PERF] refresh_ms=%d symbols=%d", elapsed_ms, len(symbols))
                # P0-4B: result_len=0 시 5초 후 1회 retry (5~10초 내 가격 채우기)
                ticks_n = len((result or {}).get("ticks") or [])
                if ticks_n == 0 and len(symbols) > 0 and self.isVisible():
                    retry_ts = getattr(self, "_wl_empty_retry_ts", 0)
                    if time.time() - retry_ts > 5:  # 5초 throttle (5~10초 내 가격 채우기)
                        self._wl_empty_retry_ts = time.time()
                        QTimer.singleShot(5000, lambda: self.refresh(caller="empty_retry"))
            except Exception as e:
                self._log.error(f"[WL-REFRESH] FAIL apply {e}\n{traceback.format_exc()}")
                if hasattr(self, '_owner') and self._owner:
                    try:
                        self._owner.set_global_status(f"🔴 워치리스트 적용 실패: {e}", "err", "watchlist")
                    except Exception:
                        pass
            finally:
                self._refresh_inflight = False
                if getattr(self, "_pending_tab_refresh", False):
                    self._pending_tab_refresh = False
                    QTimer.singleShot(300, lambda: self.refresh(caller="tab_visible"))

        if caller == "_execute_watchlist_boot" and symbols:
            self._log.info("[WL-BOOT] worker submit symbols=%d (apply 강제)", len(symbols))
        self._run_wl_worker(_do_fetch, _on_refresh_fetch_done)

    def poll_tick(self) -> None:
        """
        app_gui 타이머에서 주기적으로 호출되는 tick 엔트리(탭 소유).
        P0-3: API 호출은 worker에서 비동기 실행 → UI thread 블로킹 없음.
        P0-4B: fetch는 항상 실행, UI apply만 on_done에서 isVisible()일 때 수행 (isVisible 스킵으로 빈 결과 방지).
        """
        symbols = list(self._wl_symbols or [])
        if not symbols:
            self._log.info("[WL-WORKER] poll_tick skip symbols_n=0 tickers_n=0 owned_n=0 err=no_symbols")
            # P0-4B: bootstrap 시도 (10초 throttle)
            now = time.time()
            if now - getattr(self, "_last_poll_empty_trigger_ts", 0) > 10:
                self._last_poll_empty_trigger_ts = now
                QTimer.singleShot(500, lambda: self.refresh(caller="poll_tick_empty"))
            return
        now = time.time()
        last = getattr(self, "_last_poll_ts", 0)
        throttle_ms = _get_watchlist_refresh_ms()
        if now - last < throttle_ms / 1000:
            return
        self._last_poll_ts = now
        t_start = time.perf_counter()

        def _do_fetch():
            return self._fetch_ticks_and_owned(symbols)

        def _on_done(result):
            if result is None:
                self._log.warning("[WL-WORKER-EMPTY] reason=none_or_exception")
                self._log.info("[WL-WORKER] done ok=0 ticks_n=0 owned_n=0 err=result_none")
                result = {"ticks": [], "owned": set(), "errors": {"worker": "exception"}, "symbols": symbols}
            # P0-4B: 탭 비가시 시 UI apply 스킵 (fetch는 완료됐으나 적용만 보류) — 탭 활성화 시 refresh 1회로 보장
            if self.isVisible():
                self._apply_worker_result(result, symbols)
                self._fill_score_column(symbols)
                # P0-4B: result_len=0 시 5초 후 1회 retry (5~10초 내 가격 채우기)
                ticks_n = len((result or {}).get("ticks") or [])
                if ticks_n == 0 and len(symbols) > 0:
                    retry_ts = getattr(self, "_wl_empty_retry_ts", 0)
                    if time.time() - retry_ts > 5:  # 5초 throttle
                        self._wl_empty_retry_ts = time.time()
                        QTimer.singleShot(5000, lambda: self.refresh(caller="empty_retry"))
            else:
                # P0-4B: fetch는 했으나 apply 스킵 (탭 비가시) → 탭 활성화 시 refresh 1회 예약
                self._pending_tab_refresh = True
                ticks_n = len((result or {}).get("ticks") or [])
                self._log.info("[WL-POLL] apply_skipped isVisible=0 ticks_n=%d pending_tab_refresh=1", ticks_n)
            if _is_wl_perf_gate():
                elapsed_ms = int((time.perf_counter() - t_start) * 1000)
                self._log.info("[WL-PERF] refresh_ms=%d symbols=%d", elapsed_ms, len(symbols))

        self._run_wl_worker(_do_fetch, _on_done)
        self._maybe_periodic_top20_refresh()

    def _maybe_periodic_top20_refresh(self) -> None:
        """settings.poll.topN_refresh_min 간격으로 상위 거래대금 목록 재조회(auto_top20일 때)."""
        try:
            owner = getattr(self, "_owner", None)
            if owner is None:
                return
            s = owner._get_settings_cached() if hasattr(owner, "_get_settings_cached") else None
            if s is None:
                return
            if not bool(getattr(s, "auto_top20", True)):
                return
            poll = getattr(s, "poll", None)
            refresh_min = int(getattr(poll, "topN_refresh_min", 30) or 30) if poll else 30
            refresh_min = max(1, refresh_min)
            refresh_sec = max(60.0, float(refresh_min) * 60.0)
            now = time.time()
            last_sched = float(getattr(self, "_last_interval_top20_ts", 0.0) or 0.0)
            cache_ts = 0.0
            tc = getattr(self, "_top20_cache", None)
            if isinstance(tc, tuple) and len(tc) >= 1:
                try:
                    cache_ts = float(tc[0])
                except Exception:
                    cache_ts = 0.0
            base_ts = max(last_sched, cache_ts)
            if base_ts <= 0:
                return
            if now - base_ts < refresh_sec:
                return
            if getattr(self, "_top20_inflight", False):
                return
            self._last_interval_top20_ts = now
            self._submit_top20_worker_only(reason="interval_topn")
        except Exception:
            pass

    def _submit_top20_worker_only(self, reason: str = "interval") -> None:
        """부트스트랩과 동일한 Top 거래대금 worker만 제출(주기 갱신용)."""
        if getattr(self, "_top20_inflight", False):
            self._log.info("[WL-TOP20] skipped reason=inflight")
            return
        symbols_fast = list(self._wl_symbols or [])
        self._top20_pending = True

        def _fetch_top20():
            try:
                self._log.info("[WL-TOP20] worker enter reason=%s", reason)
                out = get_top_markets_by_volume(30) or []
                self._log.info("[WL-TOP20] n=%s list=%s", len(out), out[:10])
                self._log.info("[WL-TOP20] worker exit n=%d", len(out))
                return out
            except Exception as e:
                self._log.warning("[WL-TOP20] fetch failed: %s", e)
                return None

        def _on_top20_done(result):
            try:
                self._top20_pending = False
                if not result or not isinstance(result, (list, tuple)):
                    self._top20_inflight = False
                    if not symbols_fast:
                        self._update_status("데이터 없음", "warn")
                    self._log.info("[WL-TOP20] done ok=false reason=result_empty_or_invalid")
                    return
                symbols = [self._norm_krw_market(str(s)) for s in result if s]
                if len(symbols) < 10:
                    self._top20_inflight = False
                    self._log.info("[WL-TOP20] done ok=false reason=len=%d_need_ge_10", len(symbols))
                    return
                top20_symbols = symbols
                self._log.info("[WL-TOP20] done n=%d reason=%s", len(top20_symbols), reason)

                self._top20_inflight = False
                try:
                    self._wl_symbols = list(top20_symbols)
                    self.set_symbols(top20_symbols)
                    self._top20_applied_flag = True
                    self._log.info("[WL-TOP20] applied n=%d", len(top20_symbols))
                except Exception as ui_ex:
                    self._log.warning("[WL-TOP20] applied err=%s", str(ui_ex)[:80])
                    return
                self._top20_cache = (time.time(), top20_symbols)
                self._apply_wl_source_log("top20", len(top20_symbols), reason=reason)
                self._update_status("정상", "ok")
                if hasattr(self, "_owner") and self._owner:
                    try:
                        self._owner.set_global_status("워치리스트 최신화 완료", "ok", "watchlist")
                    except Exception:
                        pass
                saved = False
                try:
                    s2 = self._get_settings()
                    if s2 and len(top20_symbols) > 0:
                        from app.utils.prefs import save_settings_patch
                        s_new = save_settings_patch({"watchlist_symbols": top20_symbols}, base_settings=s2)
                        if s_new:
                            if hasattr(self, "_owner") and self._owner:
                                try:
                                    self._owner._settings = s_new
                                except Exception:
                                    pass
                            saved = True
                except Exception as ex:
                    self._log.info("[WL-TOP20] saved err=%s", str(ex)[:80])
                if saved:
                    self._log.info("[WL-TOP20] saved n=%d", len(top20_symbols))
                self.refresh(caller="top20_applied")
            except Exception as e:
                self._top20_inflight = False
                self._log.error("[WL-TOP20] fail err=%s", str(e)[:100])

        def _on_top20_timeout():
            if getattr(self, "_top20_inflight", False):
                t = getattr(self, "_wl_pending_top20", None)
                if t:
                    self._wl_flush_top20_cb()
                self._top20_inflight = False
                self._log.info("[WL-TOP20] timeout reason=30000ms")

        self._top20_inflight = True
        self._top20_fetch_start = time.perf_counter()
        self._log.info("[WL-TOP20] start n=30 reason=%s", reason)
        self._run_wl_worker(_fetch_top20, _on_top20_done)
        QTimer.singleShot(30000, _on_top20_timeout)

    def update_ai_scores(self, wl_symbols, scores: dict) -> None:
        """
        Watchlist 테이블의 '종목점수' 열(4번 컬럼)에 AI 추천 점수를 반영한다.
        소스: scores dict → _ai_scores 갱신 → _fill_score_column과 동일 규칙 적용.
        """
        tbl = getattr(self, "tbl", None)
        if tbl is None:
            return
        # _ai_scores 갱신 후 _fill_score_column 호출 (덮어쓰기 차단 규칙 통일)
        self._ai_scores = dict(scores or {})
        self._fill_score_column(list(wl_symbols or []))

    def _normalize_ai_reco_items(self, payload: dict):
        """
        AI 추천 페이로드 정규화:
        - {"items": [...]} 직접 본문
        - {"advice": {"items": [...]}} 중첩 본문
        - 또는 list 자체가 올 수도 있음
        """
        data = payload or {}

        # {"advice": {...}} 형태면 advice 내부로 진입
        if isinstance(data, dict) and "advice" in data:
            data = data.get("advice") or {}

        # 바로 list가 오는 경우
        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            return []

        # 기본: items 키 우선
        items = data.get("items")
        # 호환: markets / symbols 등에 담겨 있을 수도 있음
        if items is None:
            items = data.get("markets") or data.get("symbols") or []

        if not isinstance(items, list):
            return []
        return items

    # -----------------------------
    # 탭 소유: 이벤트 구독/심볼 산출/6개 항목 채우기
    # -----------------------------
    def _bootstrap_watchlist(self, reason: str = "") -> None:
        """
        P0-BLOCK 3: 워치리스트 부팅 — top20 fetch를 worker로 옮겨 UI 블로킹 제거.
        - 기존 wl_symbols/캐시/설정이 있으면 즉시 표시
        - top20은 worker에서 비동기 fetch, 도착 시 교체 적용
        """
        # 1) 즉시 표시할 심볼 (네트워크 없음)
        symbols_fast = self._compute_symbols_fast() or []
        if getattr(self, '_wl_symbols', None) and not symbols_fast:
            symbols_fast = list(self._wl_symbols)
            self._apply_wl_source_log("session", len(symbols_fast), sample=symbols_fast)
        if len(symbols_fast) == 3 and _is_wl_perf_gate():
            self._log.info("[WL-SOURCE] bootstrap_initial n=3 reason=default3_fallback sample=%s", ",".join(symbols_fast[:3]))
        if symbols_fast:
            try:
                self._log.info(f"[WL-MODEL] bootstrap fast symbols={len(symbols_fast)} sample={symbols_fast[:5]}")
                self.set_symbols(symbols_fast)
                self._update_status("로딩 중...", "warn")
            except Exception as e:
                log.error(f"[WATCHLIST] bootstrap fast error: {e}")
        else:
            try:
                self.tbl.setRowCount(0)
            except Exception:
                pass

        # 2) top20을 worker에서 비동기 fetch (UI 블로킹 없음) — 먼저 제출해 refresh 이전에 완료 시도
        self._top20_pending = True  # ✅ P0-A: 부팅 refresh가 set_symbols(3) 덮어쓰기 방지용

        # PATCH-1: 중복 실행 방지 — top20 inflight 중에는 다시 start하지 않음
        if getattr(self, "_top20_inflight", False):
            self._log.info("[WL-TOP20] skipped reason=inflight")
            return

        # 가격/보유는 worker에서 비동기 채움 (3개 즉시 표시용)
        if symbols_fast:
            def _do_fill():
                return self._fetch_ticks_and_owned(symbols_fast)
            def _on_fill_done(result):
                try:
                    if result is None or not isinstance(result, dict):
                        err = "result_none" if result is None else "fill_result_invalid"
                        self._log.info("[WL-WORKER] done ok=0 ticks_n=0 owned_n=0 err=%s", err)
                        result = {"ticks": [], "owned": set(), "errors": {"worker": err}, "symbols": symbols_fast}
                    self._apply_worker_result(result, symbols_fast)
                    self._ai_scores = {}
                    self._fill_score_column(symbols_fast)
                    self._update_status("정상", "ok")
                except Exception as e:
                    self._log.error("[WL-WORKER-ERR] %s", str(e)[:200])
            self._run_wl_worker(_do_fill, _on_fill_done)

        def _fetch_top20():
            try:
                self._log.info("[WL-TOP20] worker enter")
                out = get_top_markets_by_volume(30) or []
                self._log.info("[WL-TOP20] n=%s list=%s", len(out), out[:10])
                self._log.info("[WL-TOP20] worker exit n=%d", len(out))
                return out
            except Exception as e:
                self._log.warning("[WL-TOP20] fetch failed: %s", e)
                return None

        def _on_top20_done(result):
            """P0-WL-TOP20: Top20 완료 → apply → prefs 저장 → refresh. 반드시 메인스레드에서 실행."""
            try:
                self._top20_pending = False
                elapsed_ms = int((time.perf_counter() - getattr(self, "_top20_fetch_start", time.perf_counter())) * 1000)
                if not result or not isinstance(result, (list, tuple)):
                    self._top20_inflight = False
                    if not symbols_fast:
                        self._update_status("데이터 없음", "warn")
                    self._log.info("[WL-TOP20] done ok=false reason=result_empty_or_invalid")
                    return
                symbols = [self._norm_krw_market(str(s)) for s in result if s]
                if len(symbols) < 10:
                    self._top20_inflight = False
                    self._log.info("[WL-TOP20] done ok=false reason=len=%d_need_ge_10", len(symbols))
                    return
                top20_symbols = symbols
                self._log.info("[WL-TOP20] done n=%d", len(top20_symbols))

                # P0-WL-TOP20: apply + saved (watchlist_symbols만 prefs에 저장)
                self._top20_inflight = False
                try:
                    self._wl_symbols = list(top20_symbols)
                    self.set_symbols(top20_symbols)
                    self._top20_applied_flag = True
                    self._log.info("[WL-TOP20] applied n=%d", len(top20_symbols))
                except Exception as ui_ex:
                    self._log.warning("[WL-TOP20] applied err=%s", str(ui_ex)[:80])
                    return
                self._top20_cache = (time.time(), top20_symbols)
                self._apply_wl_source_log("top20", len(top20_symbols), reason="")
                self._update_status("정상", "ok")
                if hasattr(self, '_owner') and self._owner:
                    try:
                        self._owner.set_global_status("워치리스트 최신화 완료", "ok", "watchlist")
                    except Exception:
                        pass
                saved = False
                try:
                    s = self._get_settings()
                    if s and len(top20_symbols) > 0:
                        from app.utils.prefs import save_settings_patch
                        s_new = save_settings_patch({"watchlist_symbols": top20_symbols}, base_settings=s)
                        if s_new:
                            if hasattr(self, "_owner") and self._owner:
                                try:
                                    self._owner._settings = s_new
                                except Exception:
                                    pass
                            saved = True
                except Exception as ex:
                    self._log.info("[WL-TOP20] saved err=%s", str(ex)[:80])
                if saved:
                    self._log.info("[WL-TOP20] saved n=%d", len(top20_symbols))
                self.refresh(caller="top20_applied")
            except Exception as e:
                self._top20_inflight = False
                self._log.error("[WL-TOP20] fail err=%s", str(e)[:100])

        def _on_top20_timeout():
            if getattr(self, "_top20_inflight", False):
                t = getattr(self, '_wl_pending_top20', None)
                if t:
                    self._wl_flush_top20_cb()
                self._top20_inflight = False
                self._log.info("[WL-TOP20] timeout reason=30000ms")

        self._top20_inflight = True
        self._top20_fetch_start = time.perf_counter()
        self._log.info("[WL-TOP20] start n=30")
        self._run_wl_worker(_fetch_top20, _on_top20_done)
        QTimer.singleShot(30000, _on_top20_timeout)

    def _ensure_event_subscriptions(self) -> None:
        if self._subscribed:
            return
        # ✅ UI는 3개 토픽 모두 구독
        # - ai.reco.updated
        # - ai.reco.items
        # - ai.reco.strategy_suggested
        try:
            self._log.info("[WL-SCORES] SUBSCRIBE topic=ai.reco.updated")
            eventbus.subscribe("ai.reco.updated", self.handle_ai_reco)
        except Exception:
            pass
        try:
            self._log.info("[WL-SCORES] SUBSCRIBE topic=ai.reco.items")
            eventbus.subscribe("ai.reco.items", self.handle_ai_reco)
        except Exception:
            pass
        try:
            self._log.info("[WL-SCORES] SUBSCRIBE topic=ai.reco.strategy_suggested")
            eventbus.subscribe("ai.reco.strategy_suggested", self.handle_ai_reco)
        except Exception:
            pass

        self._subscribed = True

    def _get_settings(self):
        owner = getattr(self, "_owner", None)
        s = getattr(owner, "_settings", None) if owner is not None else None
        if s is not None:
            return s
        try:
            # ✅ main window 캐시 getter 사용
            if owner and hasattr(owner, '_get_settings_cached'):
                return owner._get_settings_cached()
            else:
                return load_settings()
        except Exception:
            return None

    def _apply_wl_source_log(self, source: str, n: int, sample: list = None, reason: str = "") -> None:
        """[WL-SOURCE] source=watchlist_symbols|top20|default3|strategy_whitelist|cache|empty — 최종선택 1줄 (짧게)."""
        now = time.time()
        last = getattr(self, "_wl_source_log_last", (None, None, 0.0))
        if last[0] == source and last[1] == n and (now - last[2]) < 3:
            return
        reason_p = f" reason={reason}" if reason else ""
        self._log.info("[WL-SOURCE] source=%s n=%d%s", source, n, reason_p)
        self._wl_source_log_last = (source, n, now)

    def _compute_symbols_fast(self) -> list[str]:
        """
        P0-BLOCK 3: 네트워크 없이 심볼 반환 (캐시 또는 설정).
        top20 fetch는 호출하지 않음. 부팅 시 즉시 표시용.
        P0-4B: _top20_applied_flag이면 무조건 _wl_symbols 반환 — default3 덮어쓰기 방지.
        """
        current_time = time.time()
        cache_ttl = 600
        # top20 한 번이라도 적용되면 무조건 _wl_symbols 사용 (default3 복귀 방지)
        if getattr(self, "_top20_applied_flag", False):
            wl_n = len(self._wl_symbols or [])
            if wl_n >= 10:
                self._apply_wl_source_log("_wl_symbols", wl_n, sample=(self._wl_symbols or [])[:5], reason="top20_applied")
                return list(self._wl_symbols or [])
        # P0-4B: _wl_symbols가 10개 이상이면 우선 사용 (top20 적용된 세션)
        wl_n = len(self._wl_symbols or [])
        if wl_n >= 10:
            self._apply_wl_source_log("_wl_symbols", wl_n, sample=(self._wl_symbols or [])[:5], reason="top20_applied")
            return list(self._wl_symbols or [])
        if hasattr(self, '_top20_cache') and self._top20_cache:
            cache_time, cached_symbols = self._top20_cache
            if current_time - cache_time < cache_ttl:
                self._apply_wl_source_log("top20", len(cached_symbols), sample=cached_symbols, reason="cache")
                return cached_symbols
        s = self._get_settings()
        if s:
            try:
                payload = s.model_dump() if hasattr(s, 'model_dump') else getattr(s, '__dict__', {}) or {}
                # P0-A: watchlist_symbols 우선 (저장된 워치리스트), symbols는 기본값 폴백
                # P0-WL-FIX: watchlist_symbols=[] → "미로드" 취급, symbols(3)는 임시 표시용 (top20 완료 시 교체)
                for path in [("watchlist_symbols",), ("symbols",), ("watchlist", "symbols"), ("strategy", "whitelist")]:
                    cur = payload
                    for key in path:
                        if cur is None:
                            break
                        cur = cur.get(key) if isinstance(cur, dict) else getattr(cur, key, None)
                    if path == ("watchlist_symbols",) and isinstance(cur, list) and not cur:
                        # CURSOR 지시: watchlist_symbols가 비어있더라도,
                        # 이미 TOP20이 UI에 적용된 상태(_wl_symbols가 충분히 채워짐)면 그 값을 우선 사용한다.
                        # default3 fallback으로 회귀하지 않게 하는 최소 방어선이다.
                        if isinstance(getattr(self, "_wl_symbols", None), list) and len(self._wl_symbols) >= 10:
                            return list(self._wl_symbols)
                        # watchlist_symbols=[] → unloaded, fall through to symbols
                        if _is_wl_perf_gate():
                            self._log.info("[WL-SOURCE] watchlist_symbols=[] unloaded, fallback")
                        continue
                    if isinstance(cur, list) and cur:
                        out = [self._norm_krw_market(str(x)) for x in cur if str(x).strip()]
                        # Add WL-MERGE log for final targets
                        try:
                            top20_n = len(getattr(self, '_top20_cache', [])[1] or [])
                            # Get current holdings from accounts
                            owned = set()
                            try:
                                accounts = svc_order.fetch_accounts() or []
                                for a in accounts:
                                    cur = a.get("currency", "").strip().upper()
                                    bal = float(a.get("balance", 0) or 0)
                                    lck = float(a.get("locked", 0) or 0)
                                    if (bal + lck) > 0:
                                        owned.add(f"KRW-{cur}")
                            except Exception:
                                pass
                            hold_n = len(owned)
                            union_n = len(out)
                            union_contains_holdings = any(sym in out for sym in [sym.replace("KRW-", "") for sym in owned])
                            missing_holdings = [sym.replace("KRW-", "") for sym in owned if sym.replace("KRW-", "") not in out]
                            self._log.info("[WL-MERGE] top20_n=%s hold_n=%s union_n=%s union_contains_holdings=%s missing_holdings=%s", 
                                             top20_n, hold_n, union_n, union_contains_holdings, missing_holdings[:5])
                        except Exception:
                            pass
                        if path == ("watchlist_symbols",):
                            src, reason = "watchlist_symbols", ""
                        elif path == ("symbols",) and len(out) == 3:
                            wl_n = len(self._wl_symbols or [])
                            if wl_n >= 10:
                                out = list(self._wl_symbols or [])
                                self._apply_wl_source_log("top20", len(out), sample=out[:5], reason="keep_applied")
                                return out
                            src, reason = "default3", "prefs_symbols_fallback"
                        elif path == ("strategy", "whitelist"):
                            src, reason = "strategy_whitelist", ""
                        else:
                            src, reason = "prefs_" + ".".join(path), ""
                        self._apply_wl_source_log(src, len(out), sample=out, reason=reason)
                        return out
            except Exception:
                pass
        self._apply_wl_source_log("empty", 0, reason="no_prefs_or_cache")
        return []

    def _compute_symbols(self) -> list[str]:
        """
        P0-BLOCK 3: UI 블로킹 제거 — 네트워크 호출 없이 _compute_symbols_fast에 위임.
        top20은 _bootstrap_watchlist의 async worker에서만 fetch.
        """
        return self._compute_symbols_fast() or []

    def _row_index_of(self, symbol: str) -> int:
        """
        P0-1: 행 탐색 강화 — row_map 우선, 없으면 테이블 스캔 fallback.
        - sym_norm = _norm_krw_market(sym)로 정규화
        - 찾으면 _row_map에 저장하여 다음번 빠른 조회
        """
        tbl = getattr(self, "tbl", None)
        if tbl is None:
            return -1

        sym_norm = self._norm_krw_market(symbol)
        if not sym_norm:
            return -1

        # 1) ✅ row_map 우선
        try:
            r = int((self._row_map or {}).get(sym_norm, -1))
            if 0 <= r < tbl.rowCount():
                return r
        except Exception:
            pass

        # 2) P0-1: 테이블 스캔 fallback 강화
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            if not it:
                continue

            # UserRole 우선 확인
            try:
                raw = it.data(Qt.UserRole)
                if isinstance(raw, str) and raw:
                    raw_norm = self._norm_krw_market(raw)
                    if raw_norm == sym_norm:
                        try:
                            self._row_map[sym_norm] = r
                        except Exception:
                            pass
                        if _is_ai_trace():
                            self._log.info("[WL-ROWMAP-FIX] sym=%s row=%d via=userrole", sym_norm, r)
                        return r
            except Exception:
                pass

            # 텍스트 매칭 강화: endswith 또는 " KRW-XXX" 포함
            try:
                txt = (it.text() or "").strip()
                if not txt:
                    continue
                # 끝에 심볼이 있거나, 공백+심볼 형태로 포함되어 있는지 확인
                if txt.endswith(sym_norm) or f" {sym_norm}" in txt:
                    try:
                        self._row_map[sym_norm] = r
                    except Exception:
                        pass
                    if _is_ai_trace():
                        self._log.info("[WL-ROWMAP-FIX] sym=%s row=%d via=scan", sym_norm, r)
                    return r
            except Exception:
                pass

        if _is_wl_perf_gate():
            row_map_n = len(self._row_map) if self._row_map else 0
            self._log.info("[WL-ROW-MISS] sym=%s row_map_n=%d sample=%s",
                          sym_norm, row_map_n, list((self._row_map or {}).keys())[:3])
        return -1

    def _set_cell(self, row: int, col: int, text: str, align_center: bool = True) -> None:
        if row < 0:
            return
        it = self.tbl.item(row, col)
        if it is None:
            it = QTableWidgetItem()
            self.tbl.setItem(row, col, it)
        it.setText(text)
        if align_center:
            it.setTextAlignment(Qt.AlignCenter)

    def _get_market_name_map(self) -> dict:
        """
        ✅ Upbit market/all에서 KRW-XXX -> Korean name 맵 캐시.
        네트워크 실패 시 빈 dict로 폴백(워치리스트 기능 영향 최소화).
        """
        if hasattr(self, "_market_name_map") and isinstance(getattr(self, "_market_name_map"), dict):
            return getattr(self, "_market_name_map")

        mp: dict = {}
        try:
            import requests  # 프로젝트에 이미 사용 중일 가능성이 높음
            url = "https://api.upbit.com/v1/market/all?isDetails=false"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                arr = r.json() or []
                for x in arr:
                    try:
                        m = str(x.get("market") or "").upper()
                        # 여러 필드에서 한글 이름 찾기
                        kn = (str(x.get("korean_name") or "").strip() or 
                              str(x.get("english_name") or "").strip() or 
                              str(x.get("market_warning") or "").strip())
                        if m and kn:
                            mp[m] = kn
                        elif m:
                            # 한글 이름이 없으면 영문 이름 사용
                            en_name = str(x.get("english_name") or "").strip()
                            if en_name:
                                mp[m] = en_name
                            else:
                                # 마켓 코드에서 심볼만 추출
                                if "-" in m:
                                    symbol = m.split("-")[1]
                                else:
                                    symbol = m
                                mp[m] = symbol
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error getting market name map: {e}")
            mp = {}

        setattr(self, "_market_name_map", mp)
        return mp

    def _fill_market_columns(self, symbols: list[str]) -> None:
        """동기 버전 (부트스트랩 등). 무거운 API는 worker에서 호출 후 _apply_market_from_ticks 사용."""
        try:
            ticks = get_tickers(symbols) or []
        except Exception as e:
            log.error(f"[WATCHLIST] Error getting tickers: {e}")
            ticks = []
        self._apply_market_from_ticks(ticks, symbols)

    def _apply_market_from_ticks(self, ticks: list, symbols: list[str]) -> None:
        """UI thread 전용: ticks 데이터로 가격/등락 컬럼 렌더링. P0-B: row<0이면 continue(return 금지)."""
        symbols_n = len(symbols or [])
        row_map_n = len(self._row_map) if self._row_map else 0
        ticks_n = len(ticks or [])
        
        # P0-A: row_map을 테이블에서 직접 재구성 → itersyms/row_map 불일치 race 제거
        try:
            self._row_map = {}
            for r in range(self.tbl.rowCount()):
                it = self.tbl.item(r, 0)
                if not it:
                    continue
                raw = None
                try:
                    raw = it.data(Qt.UserRole)
                except Exception:
                    pass
                if not raw:
                    raw = (it.text() or "").strip()
                sym_norm = self._norm_krw_market(str(raw or ""))
                if sym_norm:
                    self._row_map[sym_norm] = r
            if _is_wl_perf_gate() and self._row_map:
                self._log.info("[WL-ROWMAP] rebuilt from table n=%d", len(self._row_map))
        except Exception:
            self._row_map = self._row_map or {}
        
        # P0-A: mp 키를 _norm_krw_market으로 통일 → sym_norm 조회 시 키 불일치 제거
        mp = {}
        for t in (ticks or []):
            try:
                m = (t.get("market") or "").strip()
                if m:
                    m_norm = self._norm_krw_market(m)
                    if m_norm:
                        mp[m_norm] = t
            except Exception:
                pass
        if _is_wl_perf_gate() and mp:
            sample_m = next(iter(mp.keys()), "")
            sample_t = mp.get(sample_m, {})
            price = sample_t.get("trade_price", "?")
            self._log.info("[WL-TICKS] sample=%s:trade_price=%s", sample_m, price)
        if _is_wl_perf_gate() and (self._row_map or {}) and not mp:
            self._log.info("[WL-MISS] mp_empty row_map_n=%d ticks_n=%d", len(self._row_map or {}), ticks_n)
        
        # P0-A: row_map 기준으로 순회 → itersyms/row_map 불일치로 인한 ROW-MISS 제거
        # (row_map은 테이블에서 직접 구축했으므로, sym→r 매핑이 항상 유효)
        matched = 0
        for sym_norm, r in (self._row_map or {}).items():
            if r < 0:
                continue
            t = mp.get(sym_norm) or {}
            try:
                price = float(t.get("trade_price") or 0.0)
                change_rate = float(t.get("signed_change_rate") or 0.0)
                change_pct = change_rate * 100
                self._set_cell(r, 1, f"{price:,.0f}" if price > 0 else "-", True)
                self._set_cell(r, 2, f"{change_pct:+.2f}%" if change_pct != 0 else "-", True)
                if price > 0:
                    matched += 1
            except Exception:
                self._set_cell(r, 1, "-", True)
                self._set_cell(r, 2, "-", True)
        if _is_wl_perf_gate() and (self._row_map or {}) and mp and matched == 0:
            rm_keys = list((self._row_map or {}).keys())[:5]
            mp_keys = list(mp.keys())[:5]
            self._log.info("[WL-MISS] 0_matches row_map_sample=%s mp_sample=%s", rm_keys, mp_keys)
        
        try:
            from PySide6.QtGui import QColor
            for sym_norm, r in (self._row_map or {}).items():
                if r < 0:
                    continue
                it = self.tbl.item(r, 2)
                if it is not None:
                    try:
                        change_rate = float((mp.get(sym_norm) or {}).get("signed_change_rate") or 0.0)
                        if change_rate > 0:
                            it.setForeground(QColor(255, 80, 80))
                        elif change_rate < 0:
                            it.setForeground(QColor(80, 140, 255))
                    except Exception:
                        pass
        except Exception:
            pass

    def _apply_empty_ticks_indicator(self, symbols: list[str]) -> None:
        """PATCH 3: ticks_n==0일 때 가격/등락 칼럼에 상태 표시 (API/—). 원인 해결 시 제거."""
        tbl = getattr(self, "tbl", None)
        if not tbl:
            return
        syms_set = {self._norm_krw_market(s) for s in (symbols or []) if self._norm_krw_market(s)}
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            if not it:
                continue
            raw = None
            try:
                raw = it.data(Qt.UserRole)
            except Exception:
                pass
            if not raw:
                raw = (it.text() or "").strip()
            sym_norm = self._norm_krw_market(str(raw or ""))
            if sym_norm and sym_norm in syms_set:
                self._set_cell(r, 1, "API", True)
                self._set_cell(r, 2, "—", True)

    def _fill_holdings_column(self, symbols: list[str]) -> None:
        """동기 버전. 무거운 API는 worker에서 호출 후 _apply_holdings_from_owned 사용."""
        try:
            rows = svc_order.fetch_accounts() or []
        except Exception:
            rows = []
        owned = set()
        for a in rows:
            cur = (a.get("currency") or "").upper()
            if not cur or cur == "KRW":
                continue
            try:
                bal = float(a.get("balance") or 0.0)
                lck = float(a.get("locked") or 0.0)
            except Exception:
                bal = lck = 0.0
            if (bal + lck) > 0:
                owned.add(f"KRW-{cur}")
        self._apply_holdings_from_owned(owned, symbols)

    def _apply_holdings_from_owned(self, owned: set, symbols: list[str]) -> None:
        """UI thread 전용: owned set으로 보유 컬럼 렌더링. P0-A: row_map 기준 순회(ROW-MISS 방지)"""
        # P0-A: owned 키를 _norm_krw_market으로 통일 → sym_norm 조회 시 키 불일치 제거
        owned_norm = {self._norm_krw_market(x) for x in (owned or set()) if self._norm_krw_market(x)}
        self._log.info("[WL-HOLD] n=%s list=%s", len(owned_norm), list(owned_norm)[:10])
        for sym_norm, r in (self._row_map or {}).items():
            if r < 0:
                continue
            self._set_cell(r, 3, "O" if sym_norm in owned_norm else "-", True)

    def _fetch_ticks_and_owned(self, symbols: list[str]) -> dict:
        """
        Worker 전용: get_tickers(공개 API) + fetch_accounts(키 필요).
        P0-B: 항상 dict 반환(result=None 금지). accounts 실패해도 ticks는 반영.
        P0-4B: 심볼 sanitize(strip/upper/개행제거) 후 재시도 1회. 두 번 다 []면 [WL-TICKS-EMPTY] (10초 throttle).
        """
        sym_list = list(symbols or [])
        ticks = []
        owned = set()
        errors = {}
        last_empty_reason = "empty"
        try:
            try:
                ticks = get_tickers(sym_list) or []
                if sym_list and not ticks:
                    errors["get_tickers"] = "api_returned_empty"
                    # 심볼 sanitize: 공백/개행/소문자/None → 정규화 후 재시도 1회
                    symbols_sanitized = [
                        self._norm_krw_market(str(s or "").strip().upper().replace("\n", "").replace("\r", ""))
                        for s in sym_list
                    ]
                    symbols_sanitized = [x for x in symbols_sanitized if x]
                    if symbols_sanitized:
                        time.sleep(0.5)
                        ticks = get_tickers(symbols_sanitized) or []
                        if ticks:
                            errors.pop("get_tickers", None)
            except Exception as e:
                ticks = []
                last_empty_reason = f"ex_{type(e).__name__}:{str(e)[:60]}"
                err_s = str(e)[:80]
                errors["get_tickers"] = err_s
                # Check if any symbol being processed is a holding
                is_holding_symbol = any(sym.replace("KRW-", "") in [a.get("currency", "").strip().upper() for a in (svc_order.fetch_accounts() or []) for sym in (symbols or [])])
                log.error("[WL-WORKER-ERR] %s %s holdings_symbol=%s", type(e).__name__, str(e)[:200], "True" if is_holding_symbol else "False", exc_info=True)
            try:
                rows = svc_order.fetch_accounts() or []
                for a in rows:
                    cur = (a.get("currency") or "").upper()
                    if not cur or cur == "KRW":
                        continue
                    try:
                        bal = float(a.get("balance") or 0.0)
                        lck = float(a.get("locked") or 0.0)
                    except Exception:
                        bal = lck = 0.0
                    if (bal + lck) > 0:
                        owned.add(f"KRW-{cur}")
            except Exception:
                owned = set()
                errors["accounts"] = "fetch_accounts failed"
            if not ticks and sym_list:
                # [WL-TICKS-EMPTY] 10초 throttle 스팸 방지 (함수 객체에 공유 타임스탬프 보관)
                now_ts = time.time()
                _fn = type(self)._fetch_ticks_and_owned
                last_ts = getattr(_fn, "_last_empty_ts", 0)
                if now_ts - last_ts >= 10.0:
                    _fn._last_empty_ts = now_ts
                    log.warning(
                        "[WL-TICKS-EMPTY] symbols=%d sample=%s reason=%s",
                        len(sym_list),
                        sym_list[:3],
                        errors.get("get_tickers") or last_empty_reason,
                    )
            log.info("[WL-WORKER] done ok=%s syms=%d ticks=%d", bool(ticks), len(sym_list), len(ticks))
            return {"ticks": ticks, "owned": owned, "errors": errors, "symbols": sym_list}
        except Exception as e:
            log.error("[WL-WORKER-ERR] %s %s", type(e).__name__, str(e)[:200], exc_info=True)
            return {"ticks": ticks, "owned": owned, "errors": {"worker": str(e)[:200]}, "symbols": sym_list}

    def _apply_worker_result(self, result, symbols: list[str]) -> None:
        """
        Worker dict 결과를 UI에 반영. P0-B: ticks만 있으면 가격/등락 렌더, owned 비어있으면 보유만 '-'.
        P0-A: _wl_symbols 비어있고 syms 있으면 set_symbols로 테이블 먼저 채움 → ROW-MISS 방지.
        P0-HOTFIX: result None/empty 시 반드시 [WL-WORKER] done ok=0 ... err=... 로그.
        P0-4A: top20 적용 후 소수(예: 3) 결과로 덮어쓰지 않도록 — 현재 심볼 수보다 적으면 스킵.
        """
        current_n = len(self._wl_symbols or [])
        if symbols and len(symbols) < current_n:
            self._log.info("[WL-APPLY] skip stale result symbols_n=%d current_n=%d", len(symbols), current_n)
            return
        if not isinstance(result, dict):
            self._log.info("[WL-WORKER] done ok=0 ticks_n=0 owned_n=0 err=result_not_dict")
            self._log.info("[WL-APPLY] symbols=%d ticks=0 owned=0 rows=-1 row_map=-1 err=result_not_dict", len(symbols or []))
            return
        ticks = result.get("ticks") or []
        owned = result.get("owned") or set()
        syms = result.get("symbols") or symbols or []
        # P0-A: 테이블 비어있으면 populate; ticks에 있고 테이블에 없으면 merge (전부 '-' 방지)
        syms_from_ticks = set()
        for t in ticks:
            m = (t.get("market") or "").strip()
            if m:
                n = self._norm_krw_market(m)
                if n:
                    syms_from_ticks.add(n)
        current = set(self._wl_symbols or [])
        if syms and not current:
            try:
                self.set_symbols(syms)
            except Exception:
                pass
        elif syms_from_ticks and syms_from_ticks - current:
            try:
                merged = list(syms_from_ticks) + [x for x in current if x not in syms_from_ticks]
                self.set_symbols(merged)
                if _is_ai_trace():
                    self._log.info("[WL-MERGE] ticks_n=%d merged_n=%d", len(syms_from_ticks), len(merged))
            except Exception:
                pass
        errors = result.get("errors") or {}
        err_accounts = 1 if errors.get("accounts") else 0
        ticks_n, owned_n = len(ticks), len(owned)
        ok = 1 if (ticks_n > 0 or syms) else 0
        err_msg = (str(errors.get("get_tickers") or errors.get("accounts") or errors.get("worker") or ""))[:80] if (err_accounts or not ticks_n) else ""
        if ok == 0 and syms:
            err_msg = err_msg or f"no_data_for_{len(syms)}_symbols"
        if ok == 0:
            err_msg = err_msg or "empty_result"
        self._log.info("[WL-WORKER] done ok=%d ticks_n=%d owned_n=%d err=%s",
                       ok, ticks_n, owned_n, err_msg or "-")
        row_map_n = len(self._row_map) if self._row_map else 0
        rows = self.tbl.rowCount() if hasattr(self, 'tbl') else -1
        self._log.info("[WL-APPLY] symbols=%d ticks=%d owned=%d rows=%d row_map=%d", len(syms), ticks_n, owned_n, rows, row_map_n)
        if err_accounts and hasattr(self, '_owner') and self._owner:
            try:
                self._owner.set_global_status("API 키 없음 (보유 미표시)", "warn", "watchlist")
            except Exception:
                pass
        # P0-4B: ticks가 있을 때만 가격/등락 덮어쓰기 — 빈 결과로 '-'로 덮어쓰지 않음
        if ticks_n > 0:
            self._apply_market_from_ticks(ticks, syms)
            self._log.info("[WL-APPLY] ticks_n=%d applied", ticks_n)
        elif ticks_n == 0 and syms:
            self._apply_empty_ticks_indicator(syms)
        self._apply_holdings_from_owned(owned, syms)
        self._wl_boot_done = True  # ✅ P0-HOTFIX: apply 완료 (부팅 첫 1회 포함)

    def _run_wl_worker(self, fn, on_done) -> None:
        """무거운 작업을 worker에서 실행, 완료 시 main thread에서 on_done(result) 호출.
        P0-4B: result_len=0 등 빈 결과 시 항상 1줄 로그 (symbols_n, tickers_n, owned_n, err).
        """
        def _on_future_done(fut):
            result = None
            try:
                result = fut.result()
                if isinstance(result, dict):
                    ticks = result.get("ticks") or []
                    owned = result.get("owned") or set()
                    syms = result.get("symbols") or []
                    err = (result.get("errors") or {})
                    # P0-4B: result_len=0 원인 1줄 항상 출력 (symbols_n, tickers_n, owned_n, err)
                    err_s = (str(err.get("get_tickers") or err.get("worker") or err.get("accounts") or ""))[:80]
                    if not err_s and len(syms) > 0 and len(ticks) == 0:
                        err_s = "get_tickers_empty"
                    tickers_n = len(ticks)
                    result_len = tickers_n
                    syms_n = len(syms)
                    owned_n = len(owned)
                    ok = 1 if result_len > 0 else 0
                    # P0-4B: result_len=0 시 이유 1줄 항상 (grep 가능) — symbols_n, tickers_n, owned_n, err
                    self._log.info("[WL-WORKER] future_done ok=%d result_len=%d symbols_n=%d tickers_n=%d owned_n=%d err=%s",
                                   ok, result_len, syms_n, tickers_n, owned_n, err_s or "-")
                elif isinstance(result, (list, tuple)):
                    n = len(result)
                    ok = 1 if n > 0 else 0
                    err_s = "top20_empty" if n == 0 else "-"
                    self._log.info("[WL-WORKER] future_done ok=%d result_len=%d symbols_n=%d tickers_n=0 owned_n=0 err=%s",
                                   ok, n, n, err_s)
                else:
                    self._log.info("[WL-WORKER] future_done ok=0 result_len=0 symbols_n=0 tickers_n=0 owned_n=0 err=result_not_dict_or_list")
            except Exception as e:
                err_s = str(e)[:200]
                self._log.error("[WL-WORKER-ERR] %s %s", type(e).__name__, err_s, exc_info=True)
                self._log.info("[WL-WORKER] future_done ok=0 result_len=0 symbols_n=0 tickers_n=0 owned_n=0 err=ex_%s", err_s[:60])
                result = None
            # P0-WL-TOP20: worker 스레드에서 add_done_callback 실행 → QTimer.singleShot(0,...)로는 메인스레드 콜백 미보장.
            # top20(list) vs refresh(dict) 분리 — 단일 슬롯 덮어쓰기로 top20 콜백 discard 방지
            if isinstance(result, (list, tuple)) and len(result) >= 10:
                setattr(self, '_wl_pending_top20', (result, on_done))
                self._top20_flush_signal.emit()  # Signal/Slot 방식으로 메인스레드 호출 보장
            else:
                setattr(self, '_wl_pending_cb', (result, on_done))
                self._pending_flush_signal.emit()  # dict 결과도 메인스레드 flush 보장

        _WL_EXECUTOR.submit(fn).add_done_callback(_on_future_done)

    @Slot()
    def _wl_flush_top20_cb(self):
        """top20 전용 flush — refresh와 슬롯 분리로 apply/saved 확정."""
        t = getattr(self, '_wl_pending_top20', None)
        if t:
            delattr(self, '_wl_pending_top20')
            t[1](t[0])

    @Slot()
    def _wl_flush_pending_cb(self):
        """P0-WL-TOP20: 메인스레드에서 pending worker 콜백 실행 (토큰 1회 소비)."""
        t = getattr(self, '_wl_pending_cb', None)
        if t:
            delattr(self, '_wl_pending_cb')
            t[1](t[0])

    def _fill_wb_columns(self, symbols: list[str]) -> None:
        """
        (호환 유지) 과거에는 5/6 컬럼을 텍스트(✓/-)로 채웠지만,
        현재는 체크박스 위젯을 사용하므로 settings 기준으로 체크 상태만 동기화한다.
        """
        try:
            self._sync_wb_from_settings(list(symbols or []))
        except Exception:
            pass

    def _clear_score_column(self, symbols: list[str]) -> None:
        """✅ P0-1: 값 없을 때만 "—" 표시, 기존 score 있으면 유지 (덮어쓰기 차단)"""
        try:
            if not hasattr(self, 'tbl'):
                return
            # ✅ _fill_score_column과 동일 로직: _ai_scores 기준으로 표시
            self._fill_score_column(symbols or [])
        except Exception:
            pass

    def _fill_score_column(self, symbols: list[str]) -> None:
        """
        종목점수(컬럼 4) 표시 — 소스: self._ai_scores (symbol → float).
        - 값 없음(None) 또는 0.0: "—" 표시, 단 기존에 유효 점수가 있으면 덮어쓰지 않음.
        - 유효 점수: _ai_scores에 있고 0이 아닌 숫자.
        P0-1: sym_norm으로 정규화하여 조회
        """
        scores = dict(self._ai_scores or {})
        for sym in symbols:
            sym_norm = self._norm_krw_market(sym)
            if not sym_norm:
                continue
            r = self._row_index_of(sym_norm)
            if r < 0:
                continue
            sc = scores.get(sym_norm)
            # 유효 점수: None 아님, 숫자, 0.0 아님 (0.0은 "없음"으로 취급)
            has_valid = sc is not None and isinstance(sc, (int, float)) and float(sc) != 0.0
            if has_valid:
                self._set_cell(r, 4, f"{float(sc):.2f}", True)
            else:
                # 값 없을 때만 "—" 표시, 기존 score 있으면 유지 (덮어쓰기 차단)
                try:
                    it = self.tbl.item(r, 4)
                    cur = (it.text() or "").strip() if it else ""
                except Exception:
                    cur = ""
                if cur and cur not in ("—", "-", ""):
                    try:
                        float(cur)  # 이미 유효 숫자면 유지
                        continue
                    except (ValueError, TypeError):
                        pass
                self._set_cell(r, 4, "—", True)


    def handle_ai_reco(self, payload: dict) -> None:
        """
        ai.reco.* 이벤트 핸들러(탭 소유):
        - payload 정규화 → scores 생성
        - 탭 내부 캐시에 저장
        - 현재 워치리스트 심볼 순서 기준으로 '종목점수' 열 업데이트
        """
        t_start = time.perf_counter()
        try:
            self._log.info(f"[WL-SCORES-RX] topic=ai.reco.* keys={list(payload.keys()) if payload else []}")

            # ✅ 전략 추천 payload는 점수(items) 이벤트가 아니다.
            # - ai.reco.strategy_suggested: {ts, regime, reason, suggested}
            # - watchlist 점수표는 ai.reco.updated/items의 items(list)만 사용
            if isinstance(payload, dict) and ("suggested" in payload) and ("items" not in payload):
                self._log.info("[WL-SCORES-RX] skip strategy_suggested payload (not scores)")
                return
            
            data = payload or {}
            if isinstance(data, dict) and "advice" in data:
                data = data.get("advice") or {}

            scores: dict[str, float] = {}

            # 1) scores dict 직접 형태
            if isinstance(data, dict) and isinstance(data.get("scores"), dict):
                for k, v in (data.get("scores") or {}).items():
                    try:
                        scores[self._norm_krw_market(str(k))] = float(v)
                    except Exception:
                        pass

            # 2) items(list) 형태
            if not scores:
                items = self._normalize_ai_reco_items(payload)
                self._log.info(f"[WL-SCORES-RX] items={len(items)}")
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sym = (it.get("market") or it.get("symbol") or "").strip()
                    if not sym:
                        continue
                    sym = self._norm_krw_market(sym)
                    raw_score = None
                    for key in ("score", "score_norm", "score_total"):
                        if it.get(key) is not None:
                            raw_score = it.get(key)
                            break
                    if raw_score is None:
                        continue
                    try:
                        scores[sym] = float(raw_score)
                    except Exception:
                        pass

            if not scores:
                self._log.info("[WL-SCORES-RX] scores empty -> applied_n=0 FAIL")
                return

            wl_symbols = list(self._wl_symbols or [])
            n = len(wl_symbols)
            matched_symbols = sum(1 for sym in wl_symbols if sym in scores)
            fail_count = n - matched_symbols
            elapsed_ms = int((time.perf_counter() - t_start) * 1000)
            self._log.info("[WL-SCORE] computed n=%d ok=%d fail=%d elapsed_ms=%d", n, matched_symbols, fail_count, elapsed_ms)
            for sym in wl_symbols:
                if sym not in scores:
                    self._log.info("[WL-SCORE] fail symbol=%s reason=no_score_or_engine_fail", sym)

            row_count = self.tbl.rowCount() if hasattr(self, 'tbl') else 0
            # ✅ P0-1: 표시 필드 고정 — 종목점수는 항상 컬럼 4
            score_col = 4
            self._log.info(f"[WL-SCORES-RX] before_apply: rows={row_count} score_col={score_col} matched={matched_symbols}")

            # 탭 캐시 갱신
            self._ai_scores = dict(scores)
            # ✅ [WL-SCORE-TRACE] KMTS_DEBUG_AI_TRACE=1: 모델(_ai_scores)에 score 반영 확인
            if _is_ai_trace():
                sample = {k: self._ai_scores[k] for k in list(self._ai_scores.keys())[:3]} if self._ai_scores else {}
                self._log.info("[WL-SCORE-TRACE] model _ai_scores updated n=%d sample=%s", len(self._ai_scores), sample)

            # 표 반영 (P0-1: sym_norm으로 row lookup)
            self._fill_score_column(list(self._wl_symbols or []))
            
            # ✅ (C) 적용 후 실제 반영 확인
            applied_n = 0
            if score_col >= 0 and hasattr(self, 'tbl'):
                for sym_norm in wl_symbols:
                    r = self._row_index_of(sym_norm)
                    if r < 0:
                        continue
                    try:
                        item = self.tbl.item(r, score_col)
                        if item and item.text() not in ("-", "—"):
                            applied_n += 1
                    except Exception:
                        pass
            
            # P0-1: [WL-SCORE-APPLY] 디버그 로그
            if _is_ai_trace():
                self._log.info("[WL-SCORE-APPLY] applied_n=%d rows=%d", applied_n, self.tbl.rowCount() if hasattr(self, 'tbl') else 0)
            
            # ✅ [WL-SCORE-TRACE] KMTS_DEBUG_AI_TRACE=1: applied 후 모델/표시 값 검증
            if _is_ai_trace() and score_col >= 0 and wl_symbols:
                for sym in wl_symbols[:5]:  # 샘플 5개
                    r = self._row_index_of(sym)
                    if r < 0:
                        continue
                    model_score = scores.get(sym)
                    displayed = ""
                    try:
                        it = self.tbl.item(r, score_col)
                        displayed = (it.text() or "").strip() if it else ""
                    except Exception:
                        pass
                    self._log.info(
                        "[WL-SCORE-TRACE] symbol=%s displayed_score_text=%s model_score=%s",
                        sym, displayed, model_score
                    )
            
            # ✅ (D) 최종 판정
            if applied_n > 0:
                self._log.info(f"[WL-SCORES-RX] SUCCESS applied_n={applied_n}")
                # ✅ [WL-SCORE] applied: KMTS_DEBUG_AI_TRACE=1 시 표시값 검증 1줄
                if _is_ai_trace() and wl_symbols and score_col >= 0:
                    sym0 = wl_symbols[0]
                    r0 = self._row_index_of(sym0)
                    disp0 = ""
                    if r0 >= 0:
                        try:
                            it = self.tbl.item(r0, score_col)
                            disp0 = (it.text() or "").strip() if it else ""
                        except Exception:
                            pass
                    self._log.info(
                        "[WL-SCORE-TRACE] [WL-SCORE] applied symbol=%s displayed_score_text=%s model_score=%s",
                        sym0, disp0, scores.get(sym0)
                    )
                # ✅ P0-DATA-BOOT: 점수 처리 결과 로그
                self._log.info(f"[SCORES] ok n={len(scores)} / fail n=0")
                
                # ✅ P0-BOOT-SCORE: app_gui에 성공 콜백
                if hasattr(self, '_owner') and self._owner:
                    try:
                        self._owner.set_global_status("🟢 종목점수 로딩 완료", "ok", "boot")
                    except Exception:
                        pass
            else:
                self._log.error(f"[WL-SCORES-RX] FAIL applied_n=0 (scores={len(scores)})")
                self._log.info("[SCORES] ok n=0 / fail n=1")
                
                # ✅ P0-BOOT-SCORE: app_gui에 실패 콜백
                if hasattr(self, '_owner') and self._owner:
                    try:
                        self._owner.set_global_status("🔴 종목점수 로딩 실패(반영 0건)", "err", "boot")
                    except Exception:
                        pass

        except Exception:
            try:
                self._log.error("[WL-SCORES-RX] EXCEPTION applied_n=0")
                self._log.error("[SCORES] ok n=0 / fail n=1")
                logging.getLogger(__name__).exception("[AI-RECO] handle_ai_reco 실패")
            except Exception:
                pass

    def _load_column_widths(self):
        """✅ P0-UI-WATCHLIST: prefs에서 컬럼 폭 복원"""
        try:
            s = self._get_settings()
            if s and hasattr(s, 'ui_state') and s.ui_state:
                widths = s.ui_state.get("watchlist_col_widths", [])
                if widths and len(widths) == 7:
                    hdr = self.tbl.horizontalHeader()
                    for i, w in enumerate(widths):
                        hdr.resizeSection(i, w)
        except Exception as e:
            log.error(f"[WATCHLIST] load column widths error: {e}")

    def _on_column_resized(self, logical_index, old_size, new_size):
        """✅ P0-UI-WATCHLIST: 컬럼 리사이즈 시 디바운스 저장"""
        # 너무 잦은 저장 방지를 위해 500ms 디바운스
        self._col_width_save_timer.start(500)

    def _save_column_widths_delayed(self):
        """✅ P0-UI-WATCHLIST: 디바운스된 컬럼 폭 저장. P0-A: patch 전용(빈 목록 덮어쓰기 방지)"""
        try:
            hdr = self.tbl.horizontalHeader()
            widths = [hdr.sectionSize(i) for i in range(7)]
            
            s = self._get_settings()
            if s:
                from app.utils.prefs import save_settings_patch
                save_settings_patch({"ui_state": {"watchlist_col_widths": widths}}, base_settings=s)
                log.debug(f"[WATCHLIST] saved column widths: {widths}")
        except Exception as e:
            log.error(f"[WATCHLIST] save column widths error: {e}")

    def closeEvent(self, event):
        """✅ P0-UI-WATCHLIST-RESTORE-FIX: 종료 시 즉시 컬럼 폭 저장"""
        try:
            self._save_column_widths_delayed()
        except Exception as e:
            log.error(f"[WATCHLIST] close save error: {e}")
        super().closeEvent(event)



