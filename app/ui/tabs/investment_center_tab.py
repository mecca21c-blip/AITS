from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


log = logging.getLogger(__name__)


class DonutChartWidget(QWidget):
    """Small read-only donut chart used by the Investment Center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[float, QColor]] = []
        self._center_title = "구성"
        self._center_value = "없음"
        self.setMinimumSize(128, 128)
        self.setMaximumSize(150, 150)

    def set_data(self, segments: list[tuple[float, str]], title: str, value: str) -> None:
        colors = ("#3b82f6", "#16a34a", "#f59e0b", "#8b5cf6", "#06b6d4", "#64748b")
        parsed: list[tuple[float, QColor]] = []
        for idx, (weight, color) in enumerate(segments or []):
            try:
                amount = max(0.0, float(weight or 0.0))
            except Exception:
                amount = 0.0
            if amount <= 0:
                continue
            parsed.append((amount, QColor(color or colors[idx % len(colors)])))
        self._segments = parsed
        self._center_title = str(title or "구성")
        self._center_value = str(value or "없음")
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        side = min(self.width(), self.height()) - 14
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        pen = QPen(QColor("#e5e7eb"), 14)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        total = sum(amount for amount, _color in self._segments)
        if total > 0:
            start = 90 * 16
            for amount, color in self._segments:
                span = int(-360 * 16 * (amount / total))
                pen = QPen(color, 14)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawArc(rect, start, span)
                start += span
        painter.setPen(QColor("#111827"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._center_title}\n{self._center_value}")


class InvestmentCenterTab(QWidget):
    """Dedicated investment status center.

    This tab is UI-first and read-only. It does not call provider, router,
    execution, order, or risk guard paths.
    """

    COLUMNS = (
        "종목",
        "수량",
        "평균단가",
        "현재가",
        "평가손익",
        "수익률",
        "비중",
        "AI 관리 상태",
        "TP/SL",
        "실행 메모",
    )

    def __init__(self, parent_window=None, parent=None):
        super().__init__(parent)
        self._parent_window = parent_window
        self._positions: list[dict[str, Any]] = []
        self._visible_positions: list[dict[str, Any]] = []
        self._hidden_dust_position_count = 0
        self._dust_position_count = 0
        self._kpi_values: dict[str, QLabel] = {}
        self._detail_values: dict[str, QLabel] = {}
        self._composition_layout: QVBoxLayout | None = None
        self._risk_values: dict[str, QLabel] = {}
        self._last_totals: dict[str, Any] = {}
        self._position_source_state: dict[str, Any] = {
            "status": "unknown",
            "source": "init",
            "rows": [],
            "message": "포지션 상태를 확인 중입니다.",
        }
        self._build_ui()
        self.refresh("init")
        self._emit_proof("create_new_tab", widget="InvestmentCenterTab")

    def _emit_proof(self, event: str, **fields: Any) -> None:
        try:
            parts = [f"event={event}"]
            for key, value in fields.items():
                parts.append(f"{key}={value}")
            message = "[AITS][InvestmentCenterProof] " + " ".join(parts)
            print(message, flush=True)
            log.info(message)
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setObjectName("investmentCenter")
        self.setStyleSheet(
            """
            QWidget#investmentCenter {
                background: #f8fafc;
            }
            QFrame[centerCard="true"] {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
            }
            QFrame[kpiCard="true"] {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
            }
            QFrame[smallMetric="true"] {
                background: #f8fafc;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
            }
            QLabel[muted="true"] {
                color: #6b7280;
                font-size: 11px;
            }
            QLabel[sectionTitle="true"] {
                color: #111827;
                font-size: 15px;
                font-weight: 900;
            }
            QLabel[badge="true"] {
                color: #1d4ed8;
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel[stateBadge="hold"] {
                color: #15803d;
                background: #ecfdf3;
                border: 1px solid #bbf7d0;
                border-radius: 7px;
                padding: 3px 7px;
                font-weight: 800;
            }
            QLabel[stateBadge="watch"] {
                color: #475467;
                background: #f8fafc;
                border: 1px solid #e5e7eb;
                border-radius: 7px;
                padding: 3px 7px;
                font-weight: 800;
            }
            QLabel[stateBadge="risk"] {
                color: #c2410c;
                background: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 7px;
                padding: 3px 7px;
                font-weight: 800;
            }
            QPushButton[actionButton="true"] {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 7px 12px;
                background: #ffffff;
                color: #374151;
                font-weight: 800;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                gridline-color: #edf2f7;
                selection-background-color: #eaf2ff;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #475467;
                border: none;
                border-right: 1px solid #e5e7eb;
                border-bottom: 1px solid #e5e7eb;
                padding: 7px 8px;
                font-weight: 800;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._build_header())
        root.addLayout(self._build_kpi_row())
        root.addWidget(self._build_ai_decision_card())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("investmentMainSplitter")
        splitter.addWidget(self._build_positions_card())
        splitter.addWidget(self._build_right_column())
        splitter.setSizes([980, 420])
        root.addWidget(splitter, 1)
        root.addWidget(self._build_footer_notice())
        self._emit_proof("dashboard_ready", splitter=True, right_cards=3)

    def _card(self, object_name: str | None = None) -> QFrame:
        card = QFrame()
        if object_name:
            card.setObjectName(object_name)
        card.setProperty("centerCard", True)
        return card

    def _build_header(self) -> QFrame:
        card = self._card("headerSection")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(5)
        title_row = QHBoxLayout()
        title = QLabel("투자현황 센터")
        title.setStyleSheet("font-size: 20px; font-weight: 900; color: #111827;")
        badge = QLabel("Preview")
        badge.setProperty("badge", True)
        title_row.addWidget(title)
        title_row.addWidget(badge, 0)
        title_row.addStretch(1)
        desc = QLabel("현재 보유 자산과 포트폴리오 현황, AI가 관리 중인 포지션을 모니터링하는 화면입니다.")
        desc.setWordWrap(True)
        desc.setProperty("muted", True)
        left.addLayout(title_row)
        left.addWidget(desc)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        label = QLabel("마지막 업데이트")
        label.setProperty("muted", True)
        self.lbl_updated_at = QLabel("-")
        self.lbl_updated_at.setStyleSheet("font-weight: 900; color: #111827;")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("actionButton", True)
        self.btn_refresh.clicked.connect(lambda: self.refresh("manual"))
        right.addWidget(label)
        right.addWidget(self.lbl_updated_at)
        right.addWidget(self.btn_refresh)
        layout.addLayout(right, 0)
        return card

    def _build_kpi_row(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        specs = (
            ("total_asset", "총 평가금액", "자산 평가 합계"),
            ("pnl", "평가손익", "보유 포지션 손익"),
            ("return_rate", "수익률", "보유 평가 기준"),
            ("available_cash", "주문가능(KRW)", "읽기 전용 표시"),
        )
        for col, (key, title, hint) in enumerate(specs):
            card = QFrame()
            card.setObjectName({
                "total_asset": "kpiTotalAsset",
                "pnl": "kpiPnL",
                "return_rate": "kpiReturn",
                "available_cash": "kpiAvailableCash",
            }.get(key, "kpiCard"))
            card.setProperty("kpiCard", True)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(4)
            label = QLabel(title)
            label.setProperty("muted", True)
            value = QLabel("-")
            value.setStyleSheet("font-size: 18px; font-weight: 900; color: #111827;")
            sub = QLabel(hint)
            sub.setProperty("muted", True)
            layout.addWidget(label)
            layout.addWidget(value)
            layout.addWidget(sub)
            self._kpi_values[key] = value
            grid.addWidget(card, 0, col)
        return grid

    def _build_ai_decision_card(self) -> QFrame:
        card = self._card("aiDecisionCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(5)
        title = QLabel("최근 AI 판단")
        title.setProperty("sectionTitle", True)
        self.lbl_ai_decision_summary = QLabel("최근 AI 판단 정보가 아직 없습니다.")
        self.lbl_ai_decision_summary.setWordWrap(True)
        self.lbl_ai_decision_summary.setProperty("muted", True)
        text_col.addWidget(title)
        text_col.addWidget(self.lbl_ai_decision_summary)
        layout.addLayout(text_col, 1)
        for text, kind in (("관망", "watch"), ("보유 유지", "hold"), ("리스크 관리", "risk")):
            tag = QLabel(text)
            tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag.setProperty("stateBadge", kind)
            layout.addWidget(tag, 0)
        return card

    def _build_positions_card(self) -> QFrame:
        card = self._card("portfolioCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self.lbl_positions_title = QLabel("보유 포지션")
        self.lbl_positions_title.setProperty("sectionTitle", True)
        title_row.addWidget(self.lbl_positions_title, 1)
        self.chk_show_dust_positions = QCheckBox("먼지 종목 표시")
        self.chk_show_dust_positions.setObjectName("showDustPositionsCheck")
        self.chk_show_dust_positions.setToolTip(
            "평가금액이 작거나 시장 정보가 부족한 잔여 종목을 함께 표시합니다."
        )
        self.chk_show_dust_positions.setChecked(False)
        self.chk_show_dust_positions.toggled.connect(self._on_show_dust_positions_toggled)
        title_row.addWidget(self.chk_show_dust_positions, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_row)

        self.tbl_positions = QTableWidget(0, len(self.COLUMNS))
        self.tbl_positions.setObjectName("positionTable")
        self.tbl_positions.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.tbl_positions.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_positions.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_positions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_positions.setAlternatingRowColors(True)
        self.tbl_positions.setShowGrid(False)
        self.tbl_positions.verticalHeader().setVisible(False)
        header = self.tbl_positions.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumHeight(36)
        self.tbl_positions.itemSelectionChanged.connect(self._on_position_selected)
        layout.addWidget(self.tbl_positions, 1)
        return card

    def _build_right_column(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_composition_card())
        layout.addWidget(self._build_risk_card())
        layout.addWidget(self._build_detail_card(), 1)
        return wrap

    def _build_composition_card(self) -> QFrame:
        card = self._card("portfolioCard")
        card.setMinimumHeight(220)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        title = QLabel("포트폴리오 구성")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        self._composition_donut = DonutChartWidget()
        self._composition_donut.setObjectName("portfolioDonut")
        content.addWidget(self._composition_donut, 0, Qt.AlignmentFlag.AlignTop)

        list_wrap = QVBoxLayout()
        list_wrap.setContentsMargins(0, 0, 0, 0)
        list_wrap.setSpacing(5)
        self.lbl_composition_empty = QLabel("보유 포지션이 없어 구성 그래프를 표시할 수 없습니다.")
        self.lbl_composition_empty.setWordWrap(True)
        self.lbl_composition_empty.setStyleSheet(
            "background:#f8fafc; border:1px dashed #d1d5db; border-radius:10px;"
            "padding:10px; color:#6b7280; font-weight:700;"
        )
        list_wrap.addWidget(self.lbl_composition_empty)
        self._composition_layout = QVBoxLayout()
        self._composition_layout.setContentsMargins(0, 0, 0, 0)
        self._composition_layout.setSpacing(4)
        list_wrap.addLayout(self._composition_layout)
        list_wrap.addStretch(1)
        content.addLayout(list_wrap, 1)
        layout.addLayout(content)
        return card

    def _build_risk_card(self) -> QFrame:
        card = self._card("riskCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(7)
        title = QLabel("위험 관리")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(6)
        specs = (
            ("positions", "총 포지션 수"),
            ("weight", "총 투자 비중"),
            ("loss_limit", "최대 손실 한도"),
            ("loss_rate", "현재 손실률(추정)"),
        )
        for idx, (key, label) in enumerate(specs):
            box = QFrame()
            box.setProperty("smallMetric", True)
            box_layout = QHBoxLayout(box)
            box_layout.setContentsMargins(8, 6, 8, 6)
            box_layout.setSpacing(6)
            name = QLabel(label)
            name.setProperty("muted", True)
            value = QLabel("-")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet("font-weight:900; color:#111827;")
            box_layout.addWidget(name)
            box_layout.addStretch(1)
            box_layout.addWidget(value)
            self._risk_values[key] = value
            grid.addWidget(box, idx // 2, idx % 2)
        layout.addLayout(grid)
        return card

    def _build_detail_card(self) -> QFrame:
        card = self._card("positionDetailCard")
        card.setMinimumHeight(220)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(7)
        title = QLabel("선택 포지션 상세")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        self.lbl_detail_placeholder = QLabel("포지션을 선택해주세요\n좌측 표에서 종목을 선택하면 상세 정보가 표시됩니다.")
        self.lbl_detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_detail_placeholder.setWordWrap(True)
        self.lbl_detail_placeholder.setStyleSheet(
            "background:#f8fafc; border:1px dashed #d1d5db; border-radius:10px;"
            "padding:9px; color:#6b7280; font-weight:800;"
        )
        layout.addWidget(self.lbl_detail_placeholder)

        layout.addWidget(self._detail_section("기본 정보", (("symbol", "종목"), ("qty", "수량"), ("avg", "평균단가"), ("price", "현재가"))))
        layout.addWidget(self._detail_section("손익 정보", (("cost_basis", "매입원금"), ("eval_amount", "현재 평가금액"), ("pnl", "평가손익"), ("return_rate", "수익률"), ("weight", "비중"))))
        layout.addWidget(self._detail_section("AI 관리", (("ai_state", "AI 상태"), ("tp", "TP"), ("sl", "SL"))))

        memo_title = QLabel("실행 메모")
        memo_title.setProperty("muted", True)
        self.lbl_detail_memo = QLabel("-")
        self.lbl_detail_memo.setWordWrap(True)
        self.lbl_detail_memo.setStyleSheet(
            "background:#f8fafc; border:1px solid #e5e7eb; border-radius:10px;"
            "padding:6px 8px; color:#111827; font-weight:800;"
        )
        layout.addWidget(memo_title)
        layout.addWidget(self.lbl_detail_memo)
        self._detail_values["memo"] = self.lbl_detail_memo
        layout.addStretch(1)
        self._set_detail(None)
        return card

    def _detail_section(self, title: str, fields: tuple[tuple[str, str], ...]) -> QFrame:
        box = QFrame()
        box.setProperty("smallMetric", True)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:11px; font-weight:900; color:#374151;")
        layout.addWidget(title_label)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for idx, (key, label) in enumerate(fields):
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(5)
            name = QLabel(label)
            name.setProperty("muted", True)
            value = QLabel("-")
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet("font-weight:800; color:#111827;")
            cell.addWidget(name)
            cell.addStretch(1)
            cell.addWidget(value)
            grid.addLayout(cell, idx // 2, idx % 2)
            self._detail_values[key] = value
        layout.addLayout(grid)
        return box

    def _build_footer_notice(self) -> QLabel:
        label = QLabel("본 화면은 보유 자산 모니터링 및 AI 관리 상태 확인용이며, 직접 주문은 불가능합니다.")
        label.setObjectName("footerNotice")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px;"
            "padding:8px 12px; color:#1e3a8a; font-size:11px; font-weight:800;"
        )
        return label

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            self.refresh("show")
        except Exception:
            pass

    def set_settings(self, _settings) -> None:
        return None

    def refresh(self, reason: str = "manual") -> None:
        self._update_kpis_from_parent()
        source_state = self._load_position_source_state(reason)
        self._position_source_state = source_state
        source_rows = source_state.get("rows") if isinstance(source_state, dict) else []
        if not isinstance(source_rows, list):
            source_rows = []
        self._positions = [
            self._normalize_position(row) for row in source_rows if isinstance(row, dict)
        ]
        visible_rows = self._get_visible_position_rows()
        self._populate_positions(visible_rows, source_state)
        self._update_composition(visible_rows, source_state)
        self._update_risk(visible_rows, source_state)
        self._set_detail(None)
        self.lbl_updated_at.setText(datetime.now().strftime("%H:%M:%S"))
        self._emit_proof(
            "refresh",
            reason=reason,
            rows=len(self._positions),
            visible_rows=len(visible_rows),
            hidden_dust=self._hidden_dust_position_count,
            source_status=source_state.get("status"),
            source=source_state.get("source"),
        )

    def get_summary_metrics(self):
        totals = self._last_totals or {}
        return (totals.get("pnl"), totals.get("return_rate"))

    def _update_kpis_from_parent(self) -> None:
        parent = self._parent_window
        total = self._read_label_text(parent, "lbl_asset_value") or self._format_krw(getattr(parent, "_last_total_asset", None))
        cash = self._read_label_text(parent, "lbl_krw_value") or self._format_krw(getattr(parent, "_last_available_krw", None))
        pnl = self._read_label_text(parent, "lbl_pnl_value") or self._format_signed_krw(getattr(parent, "_last_pnl_today", None))
        ret = self._read_label_text(parent, "lbl_ret_value") or self._format_pct(getattr(parent, "_last_roi_today", None))
        values = {
            "total_asset": total or "-",
            "pnl": pnl or "-",
            "return_rate": ret or "-",
            "available_cash": cash or "-",
        }
        for key, value in values.items():
            label = self._kpi_values.get(key)
            if label is not None:
                label.setText(value)
        self._last_totals = {
            "pnl": self._parse_number(pnl),
            "return_rate": self._parse_number(ret),
        }

    def _read_cached_positions(self) -> list[dict[str, Any]]:
        parent = self._parent_window
        candidates = (
            "_investment_center_positions",
            "_portfolio_positions",
            "_holdings_rows",
            "portfolio_rows",
        )
        for name in candidates:
            rows = getattr(parent, name, None)
            if isinstance(rows, list):
                return [self._normalize_position(row) for row in rows if isinstance(row, dict)]
        return []

    def _load_position_source_state(self, reason: str = "manual") -> dict[str, Any]:
        pending = getattr(self, "_pending_position_source_state", None)
        if isinstance(pending, dict):
            try:
                delattr(self, "_pending_position_source_state")
            except Exception:
                pass
            return self._finalize_position_source_state(pending)

        parent = self._parent_window
        loader = getattr(parent, "_refresh_investment_position_source", None)
        if callable(loader):
            try:
                return self._finalize_position_source_state(loader(reason))
            except Exception as exc:
                self._emit_proof(
                    "position_source_failed",
                    reason=type(exc).__name__,
                    submitted=0,
                )
                return self._finalize_position_source_state({
                    "status": "failed",
                    "source": "parent_loader",
                    "rows": [],
                    "message": "보유 포지션 조회 실패\n계좌 연결 상태를 확인하세요.",
                })

        rows = self._read_cached_positions()
        status = "ok" if rows else "unavailable"
        return self._finalize_position_source_state({
            "status": status,
            "source": "owner_cache" if rows else "unavailable",
            "rows": rows,
            "message": f"포지션 조회 완료 · {len(rows)}개 보유" if rows else "보유 포지션 source가 아직 연결되지 않았습니다.",
        })

    def _finalize_position_source_state(self, state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(state, dict):
            state = {}
        rows = state.get("rows") if isinstance(state.get("rows"), list) else []
        status = str(state.get("status") or "unknown")
        if not rows and status == "empty" and self._account_summary_implies_positions():
            status = "mismatch"
            state = dict(state)
            state["status"] = "mismatch"
            state["source"] = f"{state.get('source', 'unknown')}:mismatch"
            state["message"] = "계좌 요약에는 비현금 자산이 있으나\n포지션 상세를 불러오지 못했습니다.\n계좌/포지션 연결 상태를 확인하세요."
        state = dict(state)
        state["status"] = status
        state["rows"] = rows
        if not state.get("message"):
            state["message"] = self._position_source_messages(status)[0]
        try:
            total, cash = self._account_summary_values()
            non_cash = (total - cash) if total is not None and cash is not None else None
            self._emit_proof(
                "position_source_classify",
                status=status,
                source=state.get("source", "-"),
                rows=len(rows),
                total_asset=total,
                available_krw=cash,
                non_cash_estimate=non_cash,
                submitted=0,
            )
        except Exception:
            pass
        return state

    def _parse_krw_display_value_for_investment(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            text = str(value).strip()
            if not text or text in {"-", "None"}:
                return None
            filtered = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
            if filtered in {"", "-", ".", "-."}:
                return None
            return float(filtered)
        except Exception:
            return None

    def _account_summary_values(self) -> tuple[float | None, float | None]:
        parent = self._parent_window

        def _label_num(name: str) -> float | None:
            try:
                label = getattr(parent, name, None)
                if label is not None and hasattr(label, "text"):
                    return self._parse_krw_display_value_for_investment(label.text())
            except Exception:
                pass
            return None

        total = self._parse_krw_display_value_for_investment(
            getattr(parent, "_last_total_asset", None)
        )
        cash = self._parse_krw_display_value_for_investment(
            getattr(parent, "_last_available_krw", None)
        )
        if total is None:
            total = _label_num("lbl_asset_value")
        if cash is None:
            cash = _label_num("lbl_krw_value")
        return total, cash

    def _account_summary_implies_positions(self) -> bool:
        total, cash = self._account_summary_values()
        if total is None or cash is None:
            return False
        return total > max(cash + 1000.0, cash * 1.01)

    def _position_source_messages(self, status: str) -> tuple[str, str, str]:
        if status == "mismatch":
            return (
                "계좌 요약에는 비현금 자산이 있으나\n포지션 상세를 불러오지 못했습니다.\n계좌/포지션 연결 상태를 확인하세요.",
                "계좌 요약과 포지션 상세가 일치하지 않아\n구성 그래프를 표시하지 않습니다.",
                "계좌 요약과 포지션 상세가 일치하지 않습니다.",
            )
        if status == "empty":
            return (
                "실제 보유 포지션이 없습니다.",
                "보유 포지션이 없어 구성 그래프를 표시할 수 없습니다.",
                "실제 보유 포지션이 없습니다.",
            )
        if status == "failed":
            return (
                "보유 포지션 조회 실패\n계좌 연결 상태를 확인하세요.",
                "포지션 조회 실패로 구성 그래프를 표시할 수 없습니다.",
                "포지션 조회 실패 상태입니다.",
            )
        if status == "unavailable":
            return (
                "보유 포지션 source가 아직 연결되지 않았습니다.",
                "포지션 source 연결 대기 중입니다.",
                "포지션 source 연결 대기 중입니다.",
            )
        return (
            "포지션 상태를 확인 중입니다.",
            "포지션 상태 확인 후 구성 그래프를 표시합니다.",
            "포지션 상태를 확인 중입니다.",
        )

    def _populate_positions(self, rows: list[dict[str, Any]], source_state: dict[str, Any] | None = None) -> None:
        table = self.tbl_positions
        try:
            table.clearSpans()
        except Exception:
            pass
        table.clearSelection()
        if not rows:
            status = str((source_state or {}).get("status") or "unknown")
            table_message = self._position_source_messages(status)[0]
            if (
                status == "ok"
                and self._hidden_dust_position_count > 0
                and not self._show_dust_positions_enabled()
            ):
                table_message = (
                    "유효 보유 포지션이 없습니다.\n"
                    f"먼지 종목 {self._hidden_dust_position_count}개가 숨겨져 있습니다.\n"
                    "'먼지 종목 표시'를 켜면 함께 확인할 수 있습니다."
                )
            table.setRowCount(1)
            try:
                table.setSpan(0, 0, 1, len(self.COLUMNS))
            except Exception:
                pass
            item = QTableWidgetItem(table_message)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, None)
            table.setItem(0, 0, item)
            table.setRowHeight(0, 240)
            self._emit_proof(
                "position_source_last_writer",
                target="positions_table",
                status=status,
                writer="InvestmentCenterTab._populate_positions",
                submitted=0,
            )
            return
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = (
                row.get("symbol"),
                row.get("qty"),
                row.get("avg"),
                row.get("price"),
                row.get("pnl"),
                row.get("return_rate"),
                row.get("weight"),
                row.get("ai_state"),
                row.get("tp_sl"),
                row.get("memo"),
            )
            for c, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.ItemDataRole.UserRole, r)
                if c in (4, 5):
                    num = self._parse_number(value)
                    if num is not None and num > 0:
                        item.setForeground(QColor("#16a34a"))
                    elif num is not None and num < 0:
                        item.setForeground(QColor("#dc2626"))
                table.setItem(r, c, item)
        table.resizeColumnsToContents()

    def _on_position_selected(self) -> None:
        selected = self.tbl_positions.selectedItems()
        if not selected:
            self._set_detail(None)
            return
        row_index = selected[0].data(Qt.ItemDataRole.UserRole)
        if row_index is None:
            self._set_detail(None)
            return
        try:
            rows = self._visible_positions or []
            row = rows[int(row_index)]
        except Exception:
            row = None
        self._set_detail(row)

    def _on_show_dust_positions_toggled(self, _checked: bool = False) -> None:
        try:
            source_state = self._position_source_state or {"status": "unknown", "source": "unknown"}
            visible_rows = self._get_visible_position_rows()
            self._populate_positions(visible_rows, source_state)
            self._update_composition(visible_rows, source_state)
            self._update_risk(visible_rows, source_state)
            self._set_detail(None)
        except Exception as exc:
            self._emit_proof("dust_filter_failed", reason=type(exc).__name__, submitted=0)

    def _show_dust_positions_enabled(self) -> bool:
        checkbox = getattr(self, "chk_show_dust_positions", None)
        try:
            return bool(checkbox is not None and checkbox.isChecked())
        except Exception:
            return False

    def _get_visible_position_rows(self) -> list[dict[str, Any]]:
        rows = list(self._positions or [])
        dust_flags = [self._is_dust_position_row(row) for row in rows]
        dust_count = sum(1 for is_dust in dust_flags if is_dust)
        show_dust = self._show_dust_positions_enabled()
        if show_dust:
            visible_rows = rows
            hidden_dust = 0
        else:
            visible_rows = [row for row, is_dust in zip(rows, dust_flags) if not is_dust]
            hidden_dust = dust_count
        self._dust_position_count = dust_count
        self._hidden_dust_position_count = hidden_dust
        self._visible_positions = visible_rows
        self._update_positions_title()
        self._emit_proof(
            "dust_filter",
            show_dust=show_dust,
            total_rows=len(rows),
            visible_rows=len(visible_rows),
            hidden_dust=hidden_dust,
            submitted=0,
        )
        return visible_rows

    def _update_positions_title(self) -> None:
        label = getattr(self, "lbl_positions_title", None)
        if label is None:
            return
        if self._show_dust_positions_enabled() and self._dust_position_count > 0:
            text = f"보유 포지션 · 전체 {len(self._positions or [])}개 표시"
        elif self._hidden_dust_position_count > 0:
            text = f"보유 포지션 · 먼지 {self._hidden_dust_position_count}개 숨김"
        else:
            text = "보유 포지션"
        label.setText(text)

    def _is_dust_position_row(self, row: dict[str, Any]) -> bool:
        if not isinstance(row, dict):
            return False
        explicit = row.get("dust")
        if explicit is None:
            explicit = row.get("is_dust")
        if isinstance(explicit, bool):
            return explicit
        eval_value = self._parse_number(row.get("eval_krw"))
        if eval_value is not None:
            return 0 <= eval_value < 5000
        price = self._parse_number(row.get("price"))
        memo = str(row.get("memo") or row.get("execution_memo") or "")
        market_supported = row.get("market_supported")
        missing_market_value = price is None and eval_value is None
        if missing_market_value and (market_supported is False or "시장 지원 확인 필요" in memo):
            return True
        weight = self._parse_number(row.get("weight"))
        pnl = self._parse_number(row.get("pnl"))
        if missing_market_value and weight is not None and abs(weight) < 0.01 and pnl is None:
            return True
        return False

    def _set_detail(self, row: dict[str, Any] | None) -> None:
        self.lbl_detail_placeholder.setVisible(row is None)
        if row is None:
            status = str((self._position_source_state or {}).get("status") or "unknown")
            self.lbl_detail_placeholder.setText(self._position_source_messages(status)[2])
        values = {
            "symbol": row.get("symbol") if row else "-",
            "qty": row.get("qty") if row else "-",
            "avg": row.get("avg") if row else "-",
            "price": row.get("price") if row else "-",
            "cost_basis": row.get("cost_basis_label") if row else "-",
            "eval_amount": row.get("eval_amount_label") if row else "-",
            "pnl": row.get("pnl") if row else "-",
            "return_rate": row.get("return_rate") if row else "-",
            "weight": row.get("weight") if row else "-",
            "ai_state": row.get("ai_state") if row else "-",
            "tp": row.get("tp") if row else "-",
            "sl": row.get("sl") if row else "-",
            "memo": row.get("memo") if row else "-",
        }
        for key, value in values.items():
            label = self._detail_values.get(key)
            if label is not None:
                label.setText(str(value or "-"))
                if key in {"pnl", "return_rate"}:
                    num = self._parse_number(value)
                    if num is not None and num > 0:
                        label.setStyleSheet("font-weight:900; color:#16a34a;")
                    elif num is not None and num < 0:
                        label.setStyleSheet("font-weight:900; color:#dc2626;")
                    else:
                        label.setStyleSheet("font-weight:800; color:#111827;")

    def _update_composition(self, rows: list[dict[str, Any]], source_state: dict[str, Any] | None = None) -> None:
        layout = self._composition_layout
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            status = str((source_state or {}).get("status") or "unknown")
            composition_message = self._position_source_messages(status)[1]
            if (
                status == "ok"
                and self._hidden_dust_position_count > 0
                and not self._show_dust_positions_enabled()
            ):
                composition_message = (
                    "유효 포지션이 없어 구성 그래프를 표시하지 않습니다.\n"
                    f"먼지 종목 {self._hidden_dust_position_count}개가 숨겨져 있습니다."
                )
            if hasattr(self, "_composition_donut"):
                self._composition_donut.set_data([], "구성", "없음")
            if hasattr(self, "lbl_composition_empty"):
                self.lbl_composition_empty.setText(composition_message)
                self.lbl_composition_empty.setVisible(True)
            self._emit_proof(
                "position_source_last_writer",
                target="composition_empty",
                status=status,
                writer="InvestmentCenterTab._update_composition",
                submitted=0,
            )
            return
        if hasattr(self, "lbl_composition_empty"):
            self.lbl_composition_empty.setVisible(False)
        segments = []
        total_basis = 0.0
        basis = "eval_amount"
        for idx, row in enumerate(rows[:6]):
            basis_value = self._row_valuation_basis_value(row)
            weight = self._parse_number(row.get("weight"))
            if weight is None and basis_value is not None:
                row_total = sum(
                    value for value in (self._row_valuation_basis_value(item) for item in rows)
                    if value is not None
                )
                if row_total > 0:
                    weight = basis_value / row_total * 100.0
            if weight is None:
                continue
            segments.append((weight, ""))
            if basis_value is not None:
                total_basis += basis_value
            if row.get("valuation_source") not in {"current_price", "current_market_price"}:
                basis = "cost_basis"
        center_value = self._format_krw(total_basis) if total_basis > 0 else f"{len(rows)}개"
        center_title = "구성" if basis == "eval_amount" else "매입 기준"
        if hasattr(self, "_composition_donut"):
            self._composition_donut.set_data(segments, center_title, center_value)
        for row in rows[:6]:
            source_label = "현재 평가" if row.get("valuation_source") in {"current_price", "current_market_price"} else "매입원금 기준"
            text = f"{row.get('symbol', '-')} · {row.get('weight', '-')} · {source_label}"
            label = QLabel(text)
            label.setProperty("muted", True)
            label.setStyleSheet(
                "background:#f8fafc; border:1px solid #e5e7eb; border-radius:8px;"
                "padding:5px 7px; color:#374151; font-weight:700;"
            )
            layout.addWidget(label)
        self._emit_proof(
            "valuation_composition",
            basis=basis,
            total=round(total_basis, 2) if total_basis else 0,
            submitted=0,
        )

    def _update_risk(self, rows: list[dict[str, Any]], source_state: dict[str, Any] | None = None) -> None:
        status = str((source_state or {}).get("status") or "unknown")
        values = {
            "positions": f"{len(rows)}개",
            "weight": self._sum_weight(rows),
            "loss_limit": "-",
            "loss_rate": self._estimate_loss_rate(rows),
        }
        basis_label = self._valuation_basis_label(rows)
        if rows and basis_label == "매입원금 기준" and values["weight"] != "-":
            values["weight"] = f"{values['weight']} · 매입원금 기준"
        if not rows and status in {"mismatch", "failed", "unavailable", "unknown"}:
            values.update({
                "positions": "0개",
                "weight": "-",
                "loss_limit": "미연결",
                "loss_rate": "-",
            })
        for key, value in values.items():
            label = self._risk_values.get(key)
            if label is not None:
                label.setText(str(value or "-"))
        if not rows:
            self._emit_proof(
                "position_source_last_writer",
                target="risk_summary",
                status=status,
                writer="InvestmentCenterTab._update_risk",
                submitted=0,
            )

    def _normalize_position(self, row: dict[str, Any]) -> dict[str, Any]:
        symbol = row.get("symbol") or row.get("market") or "-"
        qty = row.get("qty") or row.get("volume") or row.get("balance") or "-"
        avg = row.get("avg") or row.get("avg_price") or row.get("avg_buy_price") or "-"
        price = row.get("current_price")
        if price is None or str(price).strip() == "":
            price = row.get("price")
        if price is None or str(price).strip() == "":
            price = row.get("market_price")
        if price is None or str(price).strip() == "":
            price = row.get("px") if row.get("valuation_source") == "current_price" else "-"
        pnl = row.get("pnl") or row.get("pnl_krw") or "-"
        ret = row.get("return_rate") or row.get("pnl_pct") or "-"
        weight = row.get("weight") or "-"
        cost_basis = row.get("cost_basis") or row.get("buy_amount") or row.get("principal")
        if cost_basis is None:
            qty_num = self._parse_number(qty)
            avg_num = self._parse_number(avg)
            if qty_num is not None and avg_num is not None:
                cost_basis = qty_num * avg_num
        eval_krw = row.get("eval_krw")
        if eval_krw is None:
            eval_krw = row.get("eval_amount")
        if eval_krw is None or str(eval_krw).strip() == "":
            eval_krw = row.get("value_krw")
        if eval_krw is None or str(eval_krw).strip() == "":
            eval_krw = row.get("position_krw")
        if eval_krw is None or str(eval_krw).strip() == "":
            eval_krw = row.get("total_krw")
        if eval_krw is None or str(eval_krw).strip() == "":
            eval_krw = "-"
        valuation_source = row.get("valuation_source") or ("current_market_price" if self._parse_number(price) is not None else "cost_basis_only")
        if valuation_source not in {"current_price", "current_market_price"}:
            price = "-"
            eval_krw = "-"
            pnl = "-"
            ret = "-"
        ai_state = row.get("ai_state") or "관망"
        tp = row.get("tp") or row.get("tp_pct") or "-"
        sl = row.get("sl") or row.get("sl_pct") or "-"
        memo = row.get("memo") or row.get("execution_memo") or "읽기 전용"
        market_supported = row.get("market_supported")
        explicit_dust = row.get("dust")
        if explicit_dust is None:
            explicit_dust = row.get("is_dust")
        return {
            "symbol": symbol,
            "qty": self._format_number(qty),
            "avg": self._format_number(avg),
            "price": self._format_number(price),
            "pnl": self._format_signed_number(pnl),
            "return_rate": self._format_pct(ret),
            "weight": self._format_pct(weight),
            "eval_krw": eval_krw,
            "eval_amount": eval_krw,
            "eval_amount_label": self._format_krw(eval_krw),
            "cost_basis": cost_basis,
            "cost_basis_label": self._format_krw(cost_basis),
            "valuation_source": valuation_source,
            "price_source": row.get("price_source") or "unknown",
            "cost_basis_source": row.get("cost_basis_source") or "avg_price",
            "ai_state": ai_state,
            "tp": tp,
            "sl": sl,
            "tp_sl": f"TP {tp}\nSL {sl}",
            "memo": memo,
            "market_supported": market_supported,
            "dust": explicit_dust,
        }

    def _read_label_text(self, owner: Any, name: str) -> str:
        try:
            label = getattr(owner, name, None)
            if label is not None and hasattr(label, "text"):
                text = str(label.text() or "").strip()
                if text and text not in {"-", "—", "— 원", "— %"}:
                    return text
        except Exception:
            pass
        return ""

    def _sum_weight(self, rows: list[dict[str, Any]]) -> str:
        total = 0.0
        seen = False
        for row in rows:
            value = self._parse_number(row.get("weight"))
            if value is not None:
                total += value
                seen = True
        if seen:
            return f"{total:.1f}%"
        position_basis = sum(
            value for value in (self._row_valuation_basis_value(row) for row in rows)
            if value is not None
        )
        account_total = None
        try:
            account_total = self._parse_number(self._kpi_values.get("total_asset").text())
        except Exception:
            account_total = None
        if position_basis > 0 and account_total and account_total > 0:
            return f"{(position_basis / account_total * 100.0):.1f}%"
        return "-"

    def _row_valuation_basis_value(self, row: dict[str, Any]) -> float | None:
        if not isinstance(row, dict):
            return None
        eval_value = self._parse_number(row.get("eval_krw"))
        if eval_value is None:
            eval_value = self._parse_number(row.get("eval_amount"))
        if row.get("valuation_source") in {"current_price", "current_market_price"} and eval_value is not None:
            return eval_value
        return self._parse_number(row.get("cost_basis"))

    def _valuation_basis_label(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        if all(row.get("valuation_source") in {"current_price", "current_market_price"} for row in rows):
            return "현재 평가 기준"
        return "매입원금 기준"

    def _estimate_loss_rate(self, rows: list[dict[str, Any]]) -> str:
        losses = [self._parse_number(row.get("return_rate")) for row in rows]
        losses = [value for value in losses if value is not None and value < 0]
        if not losses:
            return "-"
        return f"{min(losses):.2f}%"

    def _format_krw(self, value: Any) -> str:
        num = self._parse_number(value)
        return "-" if num is None else f"{num:,.0f}원"

    def _format_signed_krw(self, value: Any) -> str:
        num = self._parse_number(value)
        return "-" if num is None else f"{num:+,.0f}원"

    def _format_number(self, value: Any) -> str:
        num = self._parse_number(value)
        if num is None:
            return "" if value is None else str(value)
        if abs(num) >= 1000:
            return f"{num:,.0f}"
        return f"{num:g}"

    def _format_signed_number(self, value: Any) -> str:
        num = self._parse_number(value)
        if num is None:
            return "" if value is None else str(value)
        return f"{num:+,.0f}" if abs(num) >= 1000 else f"{num:+g}"

    def _format_pct(self, value: Any) -> str:
        num = self._parse_number(value)
        if num is None:
            return "" if value is None else str(value)
        return f"{num:.2f}%"

    def _parse_number(self, value: Any) -> float | None:
        try:
            text = str(value).replace(",", "").replace("원", "").replace("%", "").strip()
            if text in {"", "-", "—", "None"}:
                return None
            return float(text)
        except Exception:
            return None

    def show_no_save_message(self) -> None:
        QMessageBox.information(self, "저장 대상 없음", "투자현황 탭은 저장할 설정이 없습니다 · 주문 없음")
