from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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
        self._kpi_values: dict[str, QLabel] = {}
        self._detail_values: dict[str, QLabel] = {}
        self._composition_layout: QVBoxLayout | None = None
        self._risk_values: dict[str, QLabel] = {}
        self._last_totals: dict[str, Any] = {}
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
        title = QLabel("보유 포지션")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

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
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title = QLabel("포트폴리오 구성")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        chart = QFrame()
        chart.setMinimumHeight(110)
        chart.setStyleSheet(
            "background:#f8fafc; border:1px dashed #d1d5db; border-radius:55px;"
            "max-width:120px;"
        )
        chart_layout = QVBoxLayout(chart)
        chart_text = QLabel("구성\n요약")
        chart_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_text.setProperty("muted", True)
        chart_layout.addWidget(chart_text)
        chart_row = QHBoxLayout()
        chart_row.addStretch(1)
        chart_row.addWidget(chart)
        chart_row.addStretch(1)
        layout.addLayout(chart_row)
        self._composition_layout = QVBoxLayout()
        self._composition_layout.setContentsMargins(0, 0, 0, 0)
        self._composition_layout.setSpacing(4)
        layout.addLayout(self._composition_layout)
        return card

    def _build_risk_card(self) -> QFrame:
        card = self._card("riskCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title = QLabel("위험 관리")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        specs = (
            ("positions", "총 포지션 수"),
            ("weight", "총 투자 비중"),
            ("loss_limit", "최대 손실 한도"),
            ("loss_rate", "현재 손실률(추정)"),
        )
        for idx, (key, label) in enumerate(specs):
            box = QFrame()
            box.setProperty("smallMetric", True)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 7, 8, 7)
            name = QLabel(label)
            name.setProperty("muted", True)
            value = QLabel("-")
            value.setStyleSheet("font-weight:900; color:#111827;")
            box_layout.addWidget(name)
            box_layout.addWidget(value)
            self._risk_values[key] = value
            grid.addWidget(box, idx // 2, idx % 2)
        layout.addLayout(grid)
        return card

    def _build_detail_card(self) -> QFrame:
        card = self._card("positionDetailCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title = QLabel("선택 포지션 상세")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        self.lbl_detail_placeholder = QLabel("포지션을 선택해주세요")
        self.lbl_detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_detail_placeholder.setWordWrap(True)
        self.lbl_detail_placeholder.setStyleSheet(
            "background:#f8fafc; border:1px dashed #d1d5db; border-radius:10px;"
            "padding:14px; color:#6b7280; font-weight:800;"
        )
        layout.addWidget(self.lbl_detail_placeholder)
        for key, label in (
            ("symbol", "종목"),
            ("qty", "수량"),
            ("avg", "평균단가"),
            ("price", "현재가"),
            ("return_rate", "수익률"),
            ("ai_state", "AI 상태"),
            ("tp", "TP"),
            ("sl", "SL"),
            ("memo", "실행 메모"),
        ):
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(2)
            name = QLabel(label)
            name.setProperty("muted", True)
            value = QLabel("-")
            value.setWordWrap(True)
            value.setStyleSheet("font-weight:800; color:#111827;")
            row.addWidget(name)
            row.addWidget(value)
            layout.addLayout(row)
            self._detail_values[key] = value
        layout.addStretch(1)
        self._set_detail(None)
        return card

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
        self._positions = self._read_cached_positions()
        self._populate_positions(self._positions)
        self._update_composition(self._positions)
        self._update_risk(self._positions)
        self._set_detail(None)
        self.lbl_updated_at.setText(datetime.now().strftime("%H:%M:%S"))
        self._emit_proof("refresh", reason=reason, rows=len(self._positions))

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

    def _populate_positions(self, rows: list[dict[str, Any]]) -> None:
        table = self.tbl_positions
        try:
            table.clearSpans()
        except Exception:
            pass
        table.clearSelection()
        if not rows:
            table.setRowCount(1)
            try:
                table.setSpan(0, 0, 1, len(self.COLUMNS))
            except Exception:
                pass
            item = QTableWidgetItem("보유 포지션이 없습니다.\n잔고/포지션 정보가 연결되면 이곳에 표시됩니다.")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, None)
            table.setItem(0, 0, item)
            table.setRowHeight(0, 240)
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
            row = self._positions[int(row_index)]
        except Exception:
            row = None
        self._set_detail(row)

    def _set_detail(self, row: dict[str, Any] | None) -> None:
        self.lbl_detail_placeholder.setVisible(row is None)
        values = {
            "symbol": row.get("symbol") if row else "-",
            "qty": row.get("qty") if row else "-",
            "avg": row.get("avg") if row else "-",
            "price": row.get("price") if row else "-",
            "return_rate": row.get("return_rate") if row else "-",
            "ai_state": row.get("ai_state") if row else "-",
            "tp": row.get("tp") if row else "-",
            "sl": row.get("sl") if row else "-",
            "memo": row.get("memo") if row else "-",
        }
        for key, value in values.items():
            label = self._detail_values.get(key)
            if label is not None:
                label.setText(str(value or "-"))

    def _update_composition(self, rows: list[dict[str, Any]]) -> None:
        layout = self._composition_layout
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            label = QLabel("구성 데이터 없음")
            label.setProperty("muted", True)
            layout.addWidget(label)
            return
        for row in rows[:6]:
            text = f"{row.get('symbol', '-')} · {row.get('weight', '-')}"
            label = QLabel(text)
            label.setProperty("muted", True)
            layout.addWidget(label)

    def _update_risk(self, rows: list[dict[str, Any]]) -> None:
        values = {
            "positions": f"{len(rows)}개",
            "weight": self._sum_weight(rows),
            "loss_limit": "-",
            "loss_rate": self._estimate_loss_rate(rows),
        }
        for key, value in values.items():
            label = self._risk_values.get(key)
            if label is not None:
                label.setText(str(value or "-"))

    def _normalize_position(self, row: dict[str, Any]) -> dict[str, Any]:
        symbol = row.get("symbol") or row.get("market") or "-"
        qty = row.get("qty") or row.get("volume") or row.get("balance") or "-"
        avg = row.get("avg") or row.get("avg_price") or row.get("avg_buy_price") or "-"
        price = row.get("price") or row.get("current_price") or row.get("px") or "-"
        pnl = row.get("pnl") or row.get("pnl_krw") or "-"
        ret = row.get("return_rate") or row.get("pnl_pct") or "-"
        weight = row.get("weight") or "-"
        ai_state = row.get("ai_state") or "관망"
        tp = row.get("tp") or row.get("tp_pct") or "-"
        sl = row.get("sl") or row.get("sl_pct") or "-"
        memo = row.get("memo") or row.get("execution_memo") or "읽기 전용"
        return {
            "symbol": symbol,
            "qty": self._format_number(qty),
            "avg": self._format_number(avg),
            "price": self._format_number(price),
            "pnl": self._format_signed_number(pnl),
            "return_rate": self._format_pct(ret),
            "weight": self._format_pct(weight),
            "ai_state": ai_state,
            "tp": tp,
            "sl": sl,
            "tp_sl": f"TP {tp}\nSL {sl}",
            "memo": memo,
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
        return f"{total:.1f}%" if seen else "-"

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
