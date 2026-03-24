import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QPushButton, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6 import QtGui

import app.core.bus as eventbus

class TradesTab(QWidget):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self._owner = owner
        self._data_dir = getattr(owner, "_data_dir", None)
        self.log = logging.getLogger(__name__)
        
        # ✅ 컬럼폭 적용 1회 보장 플래그
        self._col_widths_applied = False
        self._col_widths_last_sig = None
        
        # ✅ P0-UI-TRADELOG: 컬럼 폭 저장 디바운스 타이머
        self._col_width_save_timer = QTimer()
        self._col_width_save_timer.setSingleShot(True)
        self._col_width_save_timer.timeout.connect(self._save_column_widths_delayed)
        
        self._setup_ui()

        # ✅ 시그널 연결은 TradesTab이 직접 소유한다.
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_export.clicked.connect(self.export_csv)

        # ✅ 주문 기록 시 자동 새로고침 (order_service → log_trade → trades.recorded)
        try:
            eventbus.subscribe("trades.recorded", self._on_trade_recorded)
        except Exception:
            pass

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- 매매기록 테이블 ---
        self.tbl_trades = QTableWidget(self)
        self.tbl_trades.setColumnCount(12)
        self.tbl_trades.setHorizontalHeaderLabels(
            [
                "시간",        # 0: ts 포맷팅 문자열
                "종목",        # 1: market
                "구분",        # 2: side (BUY/SELL)
                "가격",        # 3: price
                "수량",        # 4: volume
                "금액",        # 5: 가격 × 수량
                "주문금액",    # 6: krw_cost
                "매매근거",    # 7: reason_short (툴팁=reason_tooltip, 80자)
                "AI모드",      # 8: selected_mode → GPT/LOCAL
                "선택엔진",    # 9: selected_engine
                "실제엔진",    # 10: actual_engine
                "사유",        # 11: reason_code (툴팁=사유별 설명)
            ]
        )

        header = self.tbl_trades.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # ✅ P0-UI-TRADELOG: 컬럼 폭 저장/복원
        header.sectionResized.connect(self._on_column_resized)
        self._load_column_widths()
        
        # ✅ P0-UI-TRADELOG: 모델 리셋 후에도 폭 재적용
        self.tbl_trades.model().layoutChanged.connect(lambda: QTimer.singleShot(50, self._load_column_widths))

        vheader = self.tbl_trades.verticalHeader()
        vheader.setVisible(False)

        layout.addWidget(self.tbl_trades)

        # --- 하단 버튼 영역 ---
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("새로고침", self)
        self.btn_export = QPushButton("CSV 내보내기", self)

        # (시그널 연결은 __init__에서 TradesTab이 직접 수행)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    # --- 데이터 렌더링 유틸 메서드 (2단계: app_gui → 탭으로 점진 이전용) ---

    def clear_rows(self) -> None:
        """
        매매기록 테이블의 모든 행을 삭제한다.
        """
        if hasattr(self, "tbl_trades") and self.tbl_trades is not None:
            self.tbl_trades.setRowCount(0)

    def _on_trade_recorded(self, _payload=None) -> None:
        """주문 기록 발생 시 매매기록 탭 자동 새로고침. (메인 스레드에서 refresh 보장)"""
        try:
            QTimer.singleShot(0, self._refresh_after_trade_recorded)
        except Exception:
            pass

    def _refresh_after_trade_recorded(self) -> None:
        """trades.recorded 수신 후 메인 스레드에서 호출되는 refresh."""
        try:
            self.refresh()
            try:
                from app.db.trades_db import recent_trades
                rows = recent_trades(5)
                self.log.info("[TRADES] refreshed after trade.recorded count=%d", len(rows or []))
            except Exception:
                pass
        except Exception:
            pass

    def showEvent(self, event) -> None:
        """탭이 보일 때 최신 매매기록 로드. 무거운 작업은 singleShot으로 연기."""
        super().showEvent(event)
        try:
            import logging
            logging.getLogger(__name__).info("[TAB] enter name=Trades")
            QTimer.singleShot(0, self.refresh)
        except Exception:
            pass

    def refresh(self) -> None:
        """
        최근 매매기록을 DB에서 조회 후 테이블을 갱신한다.
        """
        try:
            from app.db.trades_db import recent_trades
            rows = recent_trades(200)
        except Exception:
            rows = []
        self.populate_from_rows(rows or [])

    def export_csv(self) -> None:
        """
        매매기록 CSV 내보내기 (폴더 선택 → exporter 호출)
        """
        import os
        import time as _time
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.utils import exporter

        base_dir = self._data_dir or os.getcwd()
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "매매기록 CSV 저장 위치 선택",
            base_dir,
        )
        if not dir_path:
            return

        try:
            from app.db.trades_db import recent_trades
            rows = recent_trades(200)
        except Exception:
            rows = []

        ts = _time.strftime("%Y%m%d_%H%M%S")
        target_path = os.path.join(dir_path, f"trades_{ts}.csv")

        try:
            try:
                out = exporter.export_trades_csv(target_path, rows)
            except TypeError:
                out = exporter.export_trades_csv(target_path)

            if not out or (isinstance(out, bool) and not out):
                QMessageBox.warning(self, "오류", "CSV 저장 실패: 파일이 생성되지 않았습니다.")
            else:
                QMessageBox.information(self, "완료", f"매매기록 CSV 저장 완료\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"CSV 저장 실패: {e}")

    def populate_from_rows(self, rows: list[dict]) -> None:
        """
        app_gui._reload_trades_table 에 있던
        'rows → QTableWidget' 렌더링 부분을 탭 전용 메서드로 분리한 버전.

        - rows: recent_trades() 결과 리스트 (dict 리스트)
        기대 키:
            ts, market, side, price, volume, krw_cost
        """
        table = getattr(self, "tbl_trades", None)
        if table is None:
            return

        if rows is None:
            rows = []

        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            try:
                ts_raw = r.get("ts")
                try:
                    ts = int(ts_raw or 0)
                except Exception:
                    ts = 0

                if ts:
                    import time as _time
                    hh = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
                else:
                    hh = "-"

                market = r.get("market") or ""
                side = r.get("side") or ""

                # 숫자 필드는 float 로 한 번 정규화
                try:
                    price = float(r.get("price") or 0)
                except Exception:
                    price = 0.0
                try:
                    volume = float(r.get("volume") or 0)
                except Exception:
                    volume = 0.0

                amount = price * volume if (price and volume) else 0.0
                krw_cost = r.get("krw_cost")
                reason_short = (r.get("reason_short") or "").strip()
                reason_tooltip = (r.get("reason_tooltip") or "").strip()
                selected_mode = (r.get("selected_mode") or "").strip().lower()
                selected_engine = (r.get("selected_engine") or "").strip()
                actual_engine = (r.get("actual_engine") or "").strip()
                reason_code = (r.get("reason_code") or "").strip()
                ai_mode_display = "GPT" if selected_mode == "gpt" else "LOCAL" if selected_mode == "local" else (selected_mode or "")
                reason_tooltip_map = {
                    "ok": "선택 엔진으로 정상 진행",
                    "ai_hold": "GPT가 매수 조건 불충족으로 HOLD 판단(정상) — score=0",
                    "inflight": "GPT 응답 지연 → 로컬로 진행",
                    "timeout": "GPT 요청 시간초과 → simple_momo로 진행",
                    "auth_401": "OpenAI 인증 실패(401) → simple_momo로 진행",
                    "http_429": "OpenAI 요청 제한(429) → simple_momo로 진행",
                    "ssl": "SSL/네트워크 오류 → simple_momo로 진행",
                    "no_key": "OpenAI API Key 없음 → simple_momo로 진행",
                    "fallback": "GPT 오류/실패 → 로컬로 진행",
                    "unknown": "예상치 못한 값 감지(로그 확인 필요)",
                    "map_error": "엔진명 매핑 실패 → unknown 처리",
                }
                reason_cell_tooltip = reason_tooltip_map.get(reason_code, reason_tooltip or "")

                vals = [
                    hh,                         # 0: 시간
                    market,                     # 1: 종목
                    side,                       # 2: 구분
                    f"{price}",                 # 3: 가격
                    f"{volume}",                # 4: 수량
                    f"{amount}",                # 5: 금액(가격×수량)
                    "" if krw_cost is None else f"{krw_cost}",  # 6: 주문금액(krw_cost)
                    reason_short,               # 7: 매매근거 (한 줄)
                    ai_mode_display,            # 8: AI모드
                    selected_engine,            # 9: 선택엔진
                    actual_engine,              # 10: 실제엔진
                    reason_code,                # 11: 사유 (짧은 코드)
                ]

                for c, v in enumerate(vals):
                    item = QTableWidgetItem("" if v is None else str(v))
                    item.setTextAlignment(Qt.AlignCenter)
                    if c == 7 and reason_tooltip:
                        item.setToolTip(reason_tooltip)
                    if c == 11 and reason_cell_tooltip:
                        item.setToolTip(reason_cell_tooltip)
                    table.setItem(i, c, item)

                # BUY/SELL 색상 지정 (2번 컬럼 side 기준)
                side_item = table.item(i, 2)
                if side_item:
                    sv = (side_item.text() or "").upper()
                    if sv == "BUY":
                        side_item.setForeground(QtGui.QBrush(QtGui.QColor("#2e7d32")))
                    elif sv == "SELL":
                        side_item.setForeground(QtGui.QBrush(QtGui.QColor("#b71c1c")))
            except Exception:
                # 개별 행에서 오류가 나도 전체 렌더링은 계속 진행
                continue

        # ✅ P0-UI-TRADELOG-RESTORE-FIX: 데이터 갱신 후 폭 재적용
        self._load_column_widths()
        
        # ✅ P0-UI-TRADELOG-FINAL-FIX: 마지막 모델 세팅 후 폭 강제 재적용
        QTimer.singleShot(0, self._load_column_widths)

    def _load_column_widths(self):
        """✅ P0-UI-TRADELOG: prefs에서 컬럼 폭 복원"""
        import logging
        from app.utils.logging_kmt import log_throttled, is_debug_mode
        
        log = logging.getLogger(__name__)
        
        try:
            # ✅ 1회 적용 보장: 이미 적용됐으면 skip
            if self._col_widths_applied:
                if is_debug_mode():
                    log_throttled(log, "tradelog.widths.skip", "[TRADELOG-WIDTHS] skip - already applied", interval_sec=5)
                return
            
            # ✅ main window 캐시 getter 사용
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            
            if main_window:
                s = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                s = load_settings()
                
            hdr = self.tbl_trades.horizontalHeader()
            if s and hasattr(s, 'ui_state') and s.ui_state:
                widths = s.ui_state.get("tradelog_col_widths", [])
                if widths and len(widths) >= 12:
                    for i, w in enumerate(widths[:12]):
                        hdr.resizeSection(i, w)
                elif widths and len(widths) == 8:
                    for i, w in enumerate(widths):
                        hdr.resizeSection(i, w)
                    for j in range(8, 12):
                        hdr.resizeSection(j, 70)
                elif widths and len(widths) == 7:
                    for i, w in enumerate(widths):
                        hdr.resizeSection(i, w)
                    hdr.resizeSection(7, 260)
                    for j in range(8, 12):
                        hdr.resizeSection(j, 70)
                else:
                    hdr.resizeSection(7, 260)
                    for j in range(8, 12):
                        hdr.resizeSection(j, 70)
            else:
                hdr.resizeSection(7, 260)
                for j in range(8, 12):
                    hdr.resizeSection(j, 70)
            
            # ✅ 적용 완료 플래그 설정 및 1회 로그
            self._col_widths_applied = True
            if is_debug_mode():
                log.info("[TRADELOG-WIDTHS] applied after final model setup")
            else:
                log_throttled(log, "tradelog.widths.applied", "[TRADELOG-WIDTHS] applied after final model setup", interval_sec=5)
        except Exception as e:
            log.error(f"[TRADELOG] load column widths error: {e}")

    def _save_column_widths_delayed(self):
        """✅ P0-UI-TRADELOG: 디바운스된 컬럼 폭 저장 (v5.4: 12컬럼)"""
        try:
            hdr = self.tbl_trades.horizontalHeader()
            widths = [hdr.sectionSize(i) for i in range(12)]
            
            # ✅ main window 캐시 getter 사용
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            
            if main_window:
                s = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings, save_settings_patch
                s = load_settings()
                
            if s:
                if not hasattr(s, 'ui_state'):
                    s.ui_state = {}
                s.ui_state["tradelog_col_widths"] = widths
                
                # ✅ 캐시 무효화 후 저장
                if main_window:
                    main_window._get_settings_cached(force=True)
                
                from app.utils.prefs import save_settings_patch
                save_settings_patch(s, {"ui_state": {"tradelog_col_widths": widths}})
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[TRADELOG] save column widths error: {e}")

    def _on_column_resized(self, logical_index, old_size, new_size):
        """✅ P0-UI-TRADELOG: 컬럼 리사이즈 시 디바운스 저장"""
        # 너무 잦은 저장 방지를 위해 500ms 디바운스
        self._col_width_save_timer.start(500)

    def closeEvent(self, event):
        """✅ P0-UI-TRADELOG: 종료 시 즉시 컬럼 폭 저장"""
        try:
            self._save_column_widths_delayed()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[TRADELOG] close save error: {e}")
        super().closeEvent(event)
