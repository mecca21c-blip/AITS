import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView, QGridLayout, QFrame, QSizePolicy, QPlainTextEdit
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextOption, QBrush, QColor

log = logging.getLogger(__name__)

class PortfolioTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owner = parent
        self.log = log
        
        # ✅ 컬럼폭 적용 1회 보장 플래그
        self._col_widths_applied = False
        self._col_widths_last_sig = None
        log.info(f"[PORTFOLIO-TAB] using={__file__} class={self.__class__.__name__}")
        
        # ✅ P0-UI-HOLDINGS: 컬럼 폭 저장 디바운스 타이머
        self._col_width_save_timer = QTimer()
        self._col_width_save_timer.setSingleShot(True)
        self._col_width_save_timer.timeout.connect(self._save_column_widths_delayed)
        
        self._init_ui()
        # ✅ P1: 매매 발생 시 투자현황 탭도 갱신
        try:
            import app.core.bus as eventbus
            eventbus.subscribe("trades.recorded", self._on_trade_recorded)
        except Exception:
            pass

    def showEvent(self, event):
        """탭이 표시될 때마다 1회 자동 refresh 예약. 무거운 작업은 singleShot으로 연기."""
        super().showEvent(event)
        log.info("[TAB] enter name=Portfolio")
        log.info("[PORTFOLIO] showEvent -> refresh scheduled")
        if hasattr(self, "lbl_empty_holdings"):
            self.lbl_empty_holdings.setText("로딩중…")
            self.lbl_empty_holdings.show()
        QTimer.singleShot(0, lambda: self.refresh("show"))
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # P2-4B / P0-UI-2: 최근 AI 판단. 5줄 높이 고정 + 스크롤, 히스토리 상한 300줄.
        self._ai_decision_lines = []
        self._ai_decision_max_lines = 300
        self.gb_ai_decision = QGroupBox("최근 AI 판단")
        self.gb_ai_decision.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        ai_lay = QVBoxLayout(self.gb_ai_decision)
        ai_lay.setContentsMargins(8, 6, 8, 6)
        # 안내 문구 라벨 (값이 없을 때 표시)
        self.lbl_ai_recent_hint = QLabel("BUY/SELL/스킵 사유가 여기 표시됩니다. (최신 10개)")
        self.lbl_ai_recent_hint.setStyleSheet("QLabel { font-size: 11px; color: #888; padding: 4px; }")
        self.lbl_ai_recent_hint.setWordWrap(True)
        ai_lay.addWidget(self.lbl_ai_recent_hint)
        # AI 판단 로그 표시 영역 (값이 있을 때 표시)
        self.lbl_ai_decision = QPlainTextEdit("")
        self.lbl_ai_decision.setReadOnly(True)
        self.lbl_ai_decision.setStyleSheet("QPlainTextEdit { font-size: 11px; color: #333; padding: 4px; border: none; background: transparent; }")
        self.lbl_ai_decision.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        fm = self.lbl_ai_decision.fontMetrics()
        line_h = fm.lineSpacing()
        self.lbl_ai_decision.setFixedHeight(line_h * 5 + 12)
        self.lbl_ai_decision.hide()  # 초기에는 숨김 (안내 문구가 보임)
        ai_lay.addWidget(self.lbl_ai_decision)
        try:
            import app.core.bus as eventbus
            eventbus.subscribe("strategy.last_event", self._on_strategy_last_event)
        except Exception:
            pass
        
        # 보유종목 테이블
        self.gb_positions = QGroupBox("보유종목")
        positions_layout = QVBoxLayout(self.gb_positions)
        self.lbl_empty_holdings = QLabel("보유 없음")
        self.lbl_empty_holdings.setStyleSheet("color: #666; font-size: 12px; padding: 8px;")
        self.lbl_empty_holdings.setAlignment(Qt.AlignCenter)
        self.lbl_empty_holdings.hide()
        positions_layout.addWidget(self.lbl_empty_holdings)
        self.tbl_positions = QTableWidget()
        self.tbl_positions.setColumnCount(13)
        # P0-3: AI 매도대기 = 비중 오른쪽(컬럼 7)
        self.tbl_positions.setHorizontalHeaderLabels([
            "종목", "수량", "평균단가", "현재가", "평가손익", "수익률", "비중",
            "AI 매도대기", "TP/SL", "TP%", "SL%", "TP가", "SL가"
        ])
        
        # ✅ P0-UI-HOLDINGS: 컬럼 리사이즈 Interactive. P0-3: AI 매도대기(7) 초기 280
        header = self.tbl_positions.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(60)
        try:
            if header.count() > 7:
                header.resizeSection(7, 280)
        except Exception:
            pass
        
        # ✅ P0-UI-HOLDINGS: 컬럼 폭 저장/복원
        header.sectionResized.connect(self._on_column_resized)
        self._load_column_widths()
        
        # ✅ P0-UI-HOLDINGS: 모델 리셋 후에도 폭 재적용
        self.tbl_positions.model().layoutChanged.connect(lambda: QTimer.singleShot(50, self._load_column_widths))
        # P0-정렬2: 헤더 클릭 정렬 활성화 (채우기 시 잠시 OFF 후 다시 ON)
        self.tbl_positions.setSortingEnabled(True)
        # P0-정렬3: 정렬 상태 저장(헤더 클릭 시) + 리부팅 후 복원
        self._restoring_sort = False
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        self._load_sort_state()
        positions_layout.addWidget(self.tbl_positions)
        
        layout.addWidget(self.gb_ai_decision, 0)
        layout.addWidget(self.gb_positions, 1)
    
    def _on_strategy_last_event(self, payload):
        """P0-UI-2: strategy.last_event 수신 → append, 최대 300줄 유지, 연속 중복 무시, 스크롤로 과거 확인."""
        try:
            msg = (payload or {}).get("message", "") if isinstance(payload, dict) else ""
            msg = str(msg)[:120] if msg else ""
            lines = getattr(self, "_ai_decision_lines", [])
            if msg and (not lines or lines[-1] != msg):
                lines.append(msg)
            max_n = getattr(self, "_ai_decision_max_lines", 300)
            if len(lines) > max_n:
                lines = lines[-max_n:]
            self._ai_decision_lines = lines
            if hasattr(self, "lbl_ai_decision") and isinstance(self.lbl_ai_decision, QPlainTextEdit):
                if lines:
                    # 값이 있으면 안내 문구 숨기고 값 표시
                    if hasattr(self, "lbl_ai_recent_hint"):
                        self.lbl_ai_recent_hint.hide()
                    self.lbl_ai_decision.show()
                    self.lbl_ai_decision.setPlainText("\n".join(lines))
                    sb = self.lbl_ai_decision.verticalScrollBar()
                    sb.setValue(sb.maximum())
                else:
                    # 값이 없으면 안내 문구 표시하고 값 영역 숨김
                    if hasattr(self, "lbl_ai_recent_hint"):
                        self.lbl_ai_recent_hint.show()
                    self.lbl_ai_decision.hide()
        except Exception:
            pass
    
    def _format_exit_wait_display(self, pos: dict) -> str:
        """P1-5A: AI 매도대기 1줄. 조건 기반(몇 % 남음)만 표시, 시간 예측 없음.
        - TP/SL 둘 다 0(=AI): AI Exit TP x% / SL y% | now z%
        - 사용자 고정값: USER TP x% / SL y% | now z%
        - dust/쿨다운/가드 스킵 시: 대기: (짧은 사유)
        """
        try:
            symbol = pos.get("market", "")
            # 1) Runner 캐시 우선 (전략 실행 중 dust/쿨다운/가드 대기 사유 포함)
            from app.strategy.runner import get_exit_display_for_ui
            by_sym = get_exit_display_for_ui()
            d = by_sym.get(symbol) if by_sym else None
            if d:
                wait = (d.get("wait_reason") or "").strip()
                if wait:
                    return f"대기: {wait[:30]}"
                tp = d.get("tp_pct")
                sl = d.get("sl_pct")
                now = d.get("pnl_pct")
                is_ai = d.get("is_ai", True)
                trigger = d.get("trigger", "NONE")
                dist_tp = d.get("distance_tp_pct")
                tp = float(tp) if tp is not None else 0.0
                sl = float(sl) if sl is not None else 0.0
                now = float(now) if now is not None else 0.0
                prefix = "AI Exit" if is_ai else "USER"
                base = f"{prefix} TP {tp:.1f}% / SL {sl:.1f}% | now {now:.1f}%"
                if trigger == "TP":
                    return base + " → TP 충족"
                if trigger == "SL":
                    return base + " → SL 충족"
                if dist_tp is not None and float(dist_tp) > 0:
                    return base + f" → TP까지 +{float(dist_tp):.1f}%"
                return base
            # 2) Fallback: 포지션만으로 표시 (전략 미실행/캐시 없음)
            if pos.get("dust"):
                return "대기: dust<min_sell_krw"
            tp_num = pos.get("tp_pct_display_num")
            sl_num = pos.get("sl_pct_display_num")
            now_val = pos.get("return_rate")
            if now_val is None:
                return "—"
            tp_num = float(tp_num) if tp_num is not None else 0.0
            sl_num = float(sl_num) if sl_num is not None else 0.0
            now_val = float(now_val)
            is_ai = (pos.get("tp_sl_mode") == "AI")
            prefix = "AI Exit" if is_ai else "USER"
            base = f"{prefix} TP {tp_num:.1f}% / SL {sl_num:.1f}% | now {now_val:.1f}%"
            if tp_num > 0 and now_val >= tp_num:
                return base + " → TP 충족"
            if sl_num > 0 and now_val <= -sl_num:
                return base + " → SL 충족"
            if tp_num > 0:
                dist_tp = max(0.0, tp_num - now_val)
                return base + f" → TP까지 +{dist_tp:.1f}%"
            return base
        except Exception:
            return "—"

    def _update_positions_table(self, positions):
        """보유종목 테이블 업데이트. P0-정렬2: 정렬 OFF 후 채우기, 숫자 컬럼은 DisplayRole에 숫자로 넣어 정렬 정상화."""
        try:
            table = self.tbl_positions
            table.setSortingEnabled(False)
            if hasattr(self, "lbl_empty_holdings"):
                if len(positions) == 0:
                    self.lbl_empty_holdings.show()
                    self.lbl_empty_holdings.setText("보유 없음")
                else:
                    self.lbl_empty_holdings.hide()
            table.setRowCount(len(positions))
            
            def _cell(v):
                if v is None: return "—"
                return str(v)
            def _num(val, default=0.0):
                if val is None: return default
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return default
            def _parse_pct(s, default=0.0):
                if s is None or s == "—" or str(s).strip() in ("", "AI"): return default
                try:
                    return float(str(s).replace("%", "").replace(",", "").strip())
                except (TypeError, ValueError):
                    return default
            for row_idx, pos in enumerate(positions):
                market_str = str(pos.get('market', ''))
                if pos.get('dust'):
                    market_str = market_str + " [DUST]"
                tp_price = pos.get('tp_price')
                sl_price = pos.get('sl_price')
                exit_wait_str = self._format_exit_wait_display(pos)
                vol, avg, cur = _num(pos.get('volume')), _num(pos.get('avg_buy_price')), _num(pos.get('current_price'))
                pnl = pos.get('pnl')
                pnl_num = int(pnl) if pnl is not None and isinstance(pnl, (int, float)) else _num(pnl)
                ret = pos.get('return_rate')
                # P0-UI-3: 수익률이 퍼센트 문자열("-0.34%")이면 '%' 제거 후 변환
                if isinstance(ret, str) and '%' in ret:
                    ret_num = _parse_pct(ret)
                else:
                    ret_num = _num(ret)
                weight_str = str(pos.get('weight', ''))
                weight_num = _parse_pct(weight_str)
                tp_pct_str = _cell(pos.get('tp_pct'))
                sl_pct_str = _cell(pos.get('sl_pct'))
                tp_num = _num(tp_price)
                sl_num = _num(sl_price)
                tp_pct_num = _parse_pct(pos.get('tp_pct'))
                sl_pct_num = _parse_pct(pos.get('sl_pct'))
                # P0-3: 순서 = 종목,수량,평균단가,현재가,평가손익,수익률,비중, AI매도대기, TP/SL,TP%,SL%,TP가,SL가
                cells = [
                    (market_str, None),
                    (_cell(pos.get('volume')), vol),
                    (_cell(pos.get('avg_buy_price')), avg),
                    (_cell(pos.get('current_price')), cur),
                    (_cell(pnl), pnl_num),
                    (_cell(ret), ret_num),
                    (weight_str, weight_num),
                    (exit_wait_str, None),
                    (_cell(pos.get('tp_sl_mode')), None),
                    (tp_pct_str, tp_pct_num),
                    (sl_pct_str, sl_pct_num),
                    (_cell(f"{tp_price:,.0f}" if tp_price is not None else None), tp_num),
                    (_cell(f"{sl_price:,.0f}" if sl_price is not None else None), sl_num),
                ]
                for col_idx, (display_val, sort_num) in enumerate(cells):
                    if sort_num is not None:
                        item = QTableWidgetItem()
                        item.setData(Qt.ItemDataRole.DisplayRole, sort_num)
                    else:
                        item = QTableWidgetItem(display_val if display_val is not None else "—")
                    # P0-UI-3: 평가손익(4), 수익률(5) 색상 적용: +초록, -빨강, 0기본
                    if col_idx == 4:  # 평가손익
                        if pnl_num is not None:
                            if pnl_num > 0:
                                item.setForeground(QBrush(QColor("#2e7d32")))
                            elif pnl_num < 0:
                                item.setForeground(QBrush(QColor("#d32f2f")))
                    elif col_idx == 5:  # 수익률
                        if ret_num is not None:
                            if ret_num > 0:
                                item.setForeground(QBrush(QColor("#2e7d32")))
                            elif ret_num < 0:
                                item.setForeground(QBrush(QColor("#d32f2f")))
                    table.setItem(row_idx, col_idx, item)
            table.setSortingEnabled(True)
            # P0-정렬3: 리프레시 후에도 저장된 정렬 상태 유지
            self._load_sort_state()
        except Exception as e:
            log.error(f"[PORTFOLIO] _update_positions_table error: {e}")
        
        # ✅ P0-UI-HOLDINGS: 데이터 갱신 후 폭 강제 재적용
        QTimer.singleShot(0, self._load_column_widths)
    
    def _on_trade_recorded(self, _payload=None) -> None:
        """매매 기록 시 투자현황 탭 새로고침. (메인 스레드에서 refresh 보장)"""
        try:
            QTimer.singleShot(0, lambda: self.refresh("trade_recorded"))
        except Exception:
            pass

    def refresh(self, reason: str = "manual") -> None:
        """투자현황 탭 단일 진입점. 실 보유 표시 + 최근 AI 판단(최대 5줄). reason: show|trade_recorded|startup|manual"""
        try:
            log.info("[PORTFOLIO] refresh start reason=%s", reason)
            if hasattr(self, "lbl_ai_decision"):
                lines = getattr(self, "_ai_decision_lines", [])
                if lines:
                    # 값이 있으면 안내 문구 숨기고 값 표시
                    if hasattr(self, "lbl_ai_recent_hint"):
                        self.lbl_ai_recent_hint.hide()
                    if isinstance(self.lbl_ai_decision, QPlainTextEdit):
                        self.lbl_ai_decision.show()
                        self.lbl_ai_decision.setPlainText("\n".join(lines))
                        sb = self.lbl_ai_decision.verticalScrollBar()
                        sb.setValue(sb.maximum())
                    else:
                        self.lbl_ai_decision.show()
                        self.lbl_ai_decision.setText("\n".join(lines))
                else:
                    # 값이 없으면 안내 문구 표시하고 값 영역 숨김
                    if hasattr(self, "lbl_ai_recent_hint"):
                        self.lbl_ai_recent_hint.show()
                    if isinstance(self.lbl_ai_decision, QPlainTextEdit):
                        self.lbl_ai_decision.hide()
                    else:
                        self.lbl_ai_decision.hide()
            owner = getattr(self, "_owner", None)
            if owner is None:
                log.info("[PORTFOLIO] refresh skip reason=account_not_ready")
                return
            if owner and hasattr(owner, "refresh_account_summary"):
                try:
                    owner.refresh_account_summary("portfolio_tab")
                except Exception:
                    pass
            # P0-[2]: Holdings SSOT 사용
            from app.services.holdings_service import fetch_live_holdings
            from app.utils.prefs import load_settings
            force_refresh = (reason == "manual")
            holdings_data = fetch_live_holdings(force=force_refresh)
            
            # TP/SL 표시용: strategy에서만 읽기 (SSOT)
            try:
                s = load_settings()
                stg = getattr(s, "strategy", {}) or {}
                if hasattr(stg, "model_dump"):
                    stg = stg.model_dump()
                tp_pct_val = float(stg.get("take_profit_pct", 0) or 0)
                sl_pct_val = float(stg.get("stop_loss_pct", 0) or 0)
            except Exception:
                tp_pct_val = 0.0
                sl_pct_val = 0.0
            
            positions_mapped = []
            totals = {}
            
            if not holdings_data.get("ok"):
                err = holdings_data.get("err", "unknown")
                log.info("[PORTFOLIO] render source=ssot n=0 reason=%s", err)
                if hasattr(self, "lbl_empty_holdings"):
                    self.lbl_empty_holdings.setText(f"불러오기 실패: err={err}")
                    self.lbl_empty_holdings.show()
                positions_mapped = []
                totals = {}
                self._last_totals = {}
            else:
                items = holdings_data.get("items", [])
                kept_count = len(items)
                priced = sum(1 for it in items if it.get("px") is not None and float(it.get("px") or 0) > 0)
                unpriced = kept_count - priced
                total_eval = sum(float(it.get("eval_krw", 0)) for it in items)
                total_buy = sum(float(it.get("avg_price", 0)) * (float(it.get("balance", 0)) + float(it.get("locked", 0))) for it in items)
                total_pnl = total_eval - total_buy
                total_pnl_rate = (total_pnl / total_buy * 100.0) if total_buy > 0 else 0.0
                totals = {
                    "total_eval": int(total_eval),
                    "total_buy": int(total_buy),
                    "pnl": int(total_pnl),
                    "pnl_rate": round(total_pnl_rate, 2),
                }
                self._last_totals = totals
                # P1-5A: AI Exit일 때 TP/SL 숫자(레짐 기반) 1회 계산
                ai_tp_pct_num = None
                ai_sl_pct_num = None
                if tp_pct_val <= 0 and sl_pct_val <= 0 and items:
                    try:
                        from app.services.upbit import get_tickers
                        from app.strategy.runner import _get_ai_exit_thresholds
                        symbols = [it.get("symbol") for it in items if it.get("symbol")]
                        tickers = get_tickers(symbols) or []
                        by_m = {t.get("market"): t for t in tickers if t.get("market")}
                        _tp, _sl, _ = _get_ai_exit_thresholds(by_m)
                        ai_tp_pct_num = float(_tp or 0) * 100.0
                        ai_sl_pct_num = float(_sl or 0) * 100.0
                    except Exception:
                        ai_tp_pct_num = 4.0
                        ai_sl_pct_num = 2.5
                for it in items:
                    symbol = it.get("symbol", "")
                    qty = float(it.get("qty", 0))
                    balance = float(it.get("balance", 0)) + float(it.get("locked", 0))
                    avg = float(it.get("avg_price", 0))
                    px_raw = it.get("px")
                    px = float(px_raw) if (px_raw is not None and float(px_raw) > 0) else None
                    ev = float(it.get("eval_krw", 0))
                    if px is not None and avg > 0 and balance > 0:
                        pnl_row = ev - (avg * balance)
                        pnl_rate = float(it.get("pnl_pct")) if it.get("pnl_pct") is not None else ((px / avg - 1.0) * 100.0)
                    else:
                        pnl_row = None
                        pnl_rate = None
                    weight = (ev / total_eval * 100) if total_eval > 0 else 0
                    dust = it.get("is_dust", ev < 5000 and ev > 0)
                    tp_sl_mode = "AI" if (tp_pct_val <= 0 and sl_pct_val <= 0) else "Manual"
                    tp_pct_str = "AI" if tp_pct_val <= 0 else f"{tp_pct_val:.2f}%"
                    sl_pct_str = "AI" if sl_pct_val <= 0 else f"{sl_pct_val:.2f}%"
                    tp_price = (avg * (1 + tp_pct_val / 100.0)) if (avg and avg > 0 and tp_pct_val > 0) else None
                    sl_price = (avg * (1 - sl_pct_val / 100.0)) if (avg and avg > 0 and sl_pct_val > 0) else None
                    # P1-5A: AI 매도대기 컬럼용 숫자 (USER=설정값, AI=레짐 기반)
                    if tp_pct_val > 0 or sl_pct_val > 0:
                        tp_num, sl_num = tp_pct_val, sl_pct_val
                    else:
                        tp_num = ai_tp_pct_num if ai_tp_pct_num is not None else 4.0
                        sl_num = ai_sl_pct_num if ai_sl_pct_num is not None else 2.5
                    positions_mapped.append({
                        "market": symbol,
                        "volume": qty,
                        "avg_buy_price": avg,
                        "current_price": px,
                        "pnl": int(pnl_row) if pnl_row is not None else None,
                        "return_rate": round(pnl_rate, 2) if pnl_rate is not None else None,
                        "weight": f"{weight:.1f}%",
                        "dust": dust,
                        "tp_sl_mode": tp_sl_mode,
                        "tp_pct": tp_pct_str,
                        "sl_pct": sl_pct_str,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                        "tp_pct_display_num": tp_num,
                        "sl_pct_display_num": sl_num,
                    })
                if unpriced > 0:
                    log.info("[PORTFOLIO-RENDER] n=%d priced=%d unpriced=%d reason=price_unavailable total_eval=%.0f total_pnl=%.0f", kept_count, priced, unpriced, total_eval, total_pnl)
                else:
                    log.info("[PORTFOLIO-RENDER] n=%d priced=%d unpriced=%d total_eval=%.0f total_pnl=%.0f", kept_count, priced, unpriced, total_eval, total_pnl)

            self._update_positions_table(positions_mapped)
            if not holdings_data.get("ok") and hasattr(self, "lbl_empty_holdings"):
                self.lbl_empty_holdings.setText(f"불러오기 실패: err={holdings_data.get('err', 'unknown')}")
                self.lbl_empty_holdings.show()
            # P0-TOPBAR-3: 포트폴리오 갱신 후 상단바(금일손익/수익률) 1회 갱신
            if owner and hasattr(owner, "refresh_account_summary"):
                try:
                    owner.refresh_account_summary("portfolio_tab")
                except Exception:
                    pass
        except Exception as e:
            log.error("[PORTFOLIO] refresh failed: %s", e)

    def get_summary_metrics(self):
        """P0-TOPBAR-3: 상단바용 보유자산 평가손익(원)·수익률(%). (pnl_krw, roi_pct) 또는 (None, None)."""
        t = getattr(self, "_last_totals", None) or {}
        return (t.get("pnl"), t.get("pnl_rate"))

    def _show_api_warning(self) -> None:
        """API 미설정 안내문 표시"""
        try:
            warning_text = "업비트 API 키가 설정되지 않아 투자요약을 불러올 수 없습니다. (공통설정에서 API 키를 등록하세요)"
            
            if hasattr(self, '_warning_label'):
                self._warning_label.setText(warning_text)
                return
            
            from PySide6.QtWidgets import QLabel
            self._warning_label = QLabel(warning_text, self)
            self._warning_label.setStyleSheet("color: #ff6b6b; padding: 5px;")
            self._warning_label.setWordWrap(True)
            
            if hasattr(self, "gb_ai_decision") and hasattr(self.gb_ai_decision, "layout"):
                layout = self.gb_ai_decision.layout()
                if layout:
                    layout.insertWidget(0, self._warning_label)
        except Exception as e:
            log.error(f"[PORTFOLIO] failed to show api warning: {e}")

    def _load_column_widths(self):
        """✅ P0-UI-HOLDINGS: prefs에서 컬럼 폭 복원"""
        try:
            # ✅ 이미 적용된 경우 스킵 (디버그 모드에서만 skip 로그)
            if self._col_widths_applied:
                from app.utils.logging_kmt import log_throttled, is_debug_mode
                if is_debug_mode():
                    log_throttled(log, "holdings.widths.skip", "[HOLDINGS-WIDTHS] skip - already applied", interval_sec=5)
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
                
            if s and hasattr(s, 'ui_state') and s.ui_state:
                widths = s.ui_state.get("holdings_col_widths", [])
                from app.utils.logging_kmt import log_throttled, is_debug_mode
                if is_debug_mode():
                    log.info(f"[HOLDINGS-WIDTHS] source=load_settings widths={widths}")
                else:
                    log_throttled(log, "holdings_widths", f"[HOLDINGS-WIDTHS] source=load_settings widths={widths}", interval_sec=5)
                    
                # P2-6A: 13컬럼 저장/복원 (기존 7개 호환). 저장 없을 때 전체 기본폭 적용.
                hdr = self.tbl_positions.horizontalHeader()
                n_cols = 13
                if widths and len(widths) == n_cols:
                    for i, w in enumerate(widths):
                        hdr.resizeSection(i, w)
                    self._col_widths_applied = True
                elif widths and len(widths) == 7:
                    for i, w in enumerate(widths):
                        hdr.resizeSection(i, w)
                    # P0-3: 7=AI 매도대기(280), 8~12=TP/SL,TP%,SL%,TP가,SL가
                    defaults_7_12 = [280, 90, 90, 90, 85, 85]
                    for i, w in enumerate(defaults_7_12):
                        hdr.resizeSection(7 + i, w)
                    self._col_widths_applied = True
                else:
                    # P0-3: 저장 없음 시 13컬럼 기본폭. 7=AI 매도대기 280
                    default_all = [100, 70, 90, 90, 90, 70, 60, 280, 90, 90, 90, 85, 85]
                    for i, w in enumerate(default_all):
                        hdr.resizeSection(i, w)
                    self._col_widths_applied = True
                if self._col_widths_applied:
                    if is_debug_mode():
                        log.info("[HOLDINGS-WIDTHS] applied after final model setup")
                    else:
                        log_throttled(log, "holdings.widths.applied", "[HOLDINGS-WIDTHS] applied after final model setup", interval_sec=5)
        except Exception as e:
            log.error(f"[HOLDINGS] load column widths error: {e}")

    def _on_column_resized(self, logical_index, old_size, new_size):
        """✅ P0-UI-HOLDINGS: 컬럼 리사이즈 시 디바운스 저장"""
        # 너무 잦은 저장 방지를 위해 500ms 디바운스
        self._col_width_save_timer.start(500)

    def _save_column_widths_delayed(self):
        """✅ P0-UI-HOLDINGS: 디바운스된 컬럼 폭 저장. P2-6A: 13컬럼 전체 저장."""
        try:
            hdr = self.tbl_positions.horizontalHeader()
            widths = [hdr.sectionSize(i) for i in range(13)]
            
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
                s.ui_state["holdings_col_widths"] = widths
                
                # ✅ 캐시 무효화 후 저장
                if main_window:
                    main_window._get_settings_cached(force=True)
                
                from app.utils.prefs import save_settings_patch
                save_settings_patch(s, {"ui_state": {"holdings_col_widths": widths}})
        except Exception as e:
            log.error(f"[HOLDINGS] save column widths error: {e}")

    def _load_sort_state(self):
        """P0-정렬3: prefs에서 정렬 컬럼/방향 복원 후 테이블에 적용."""
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            if main_window:
                s = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                s = load_settings()
            if not s or not getattr(s, 'ui_state', None):
                return
            col = s.ui_state.get("portfolio_holdings_sort_col")
            order_str = s.ui_state.get("portfolio_holdings_sort_order", "asc")
            if col is None:
                return
            n_cols = self.tbl_positions.columnCount()
            if not (0 <= col < n_cols):
                return
            order = Qt.SortOrder.DescendingOrder if (order_str == "desc") else Qt.SortOrder.AscendingOrder
            header = self.tbl_positions.horizontalHeader()
            self._restoring_sort = True
            try:
                header.setSortIndicator(col, order)
                self.tbl_positions.sortItems(col, order)
            finally:
                self._restoring_sort = False
        except Exception as e:
            log.error(f"[PORTFOLIO] load sort state error: {e}")

    def _on_sort_indicator_changed(self, logical_index, order):
        """P0-정렬3: 헤더 정렬 변경 시 prefs에 저장 (복원 중에는 스킵)."""
        if getattr(self, "_restoring_sort", False):
            return
        self._save_sort_state(logical_index, order)

    def _save_sort_state(self, col, order):
        """P0-정렬3: 정렬 컬럼/방향을 ui_state에 저장."""
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_get_settings_cached'):
                main_window = main_window.parent()
            if main_window:
                s = main_window._get_settings_cached()
            else:
                from app.utils.prefs import load_settings
                s = load_settings()
            if not s:
                return
            if not hasattr(s, 'ui_state'):
                s.ui_state = {}
            ui = dict(s.ui_state)
            ui["portfolio_holdings_sort_col"] = col
            ui["portfolio_holdings_sort_order"] = "desc" if order == Qt.SortOrder.DescendingOrder else "asc"
            if main_window:
                main_window._get_settings_cached(force=True)
            from app.utils.prefs import save_settings_patch
            save_settings_patch(s, {"ui_state": ui})
        except Exception as e:
            log.error(f"[PORTFOLIO] save sort state error: {e}")

    def closeEvent(self, event):
        """✅ P0-UI-HOLDINGS: 종료 시 즉시 컬럼 폭 저장"""
        try:
            self._save_column_widths_delayed()
        except Exception as e:
            log.error(f"[HOLDINGS] close save error: {e}")
        super().closeEvent(event)
