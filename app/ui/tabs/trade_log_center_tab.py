from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


log = logging.getLogger(__name__)


class TradeLogCenterTab(QWidget):
    """Dedicated trade log center.

    This tab is display-only. It does not call provider, router, execution,
    order, or risk guard paths.
    """

    FILTERS = (
        ("all", "전체"),
        ("fills", "실제 체결"),
        ("preview", "Preview 판단"),
        ("reflection", "Reflection"),
        ("blocked", "차단/보류"),
    )

    COLUMNS = (
        "시간",
        "유형",
        "종목",
        "Action",
        "상태",
        "가격",
        "금액",
        "선택 엔진",
        "실제 엔진",
    )

    def __init__(self, parent_window=None, parent=None):
        super().__init__(parent)
        self._parent_window = parent_window
        self._rows: list[dict[str, Any]] = []
        self._visible_rows: list[dict[str, Any]] = []
        self._filter = "all"
        self._detail_values: dict[str, QLabel] = {}
        self._kpi_values: dict[str, QLabel] = {}
        self._filter_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        self.refresh()
        self._emit_proof("create_new_tab", widget="TradeLogCenterTab")

    def _emit_proof(self, event: str, **fields: Any) -> None:
        try:
            parts = [f"event={event}"]
            for key, value in fields.items():
                parts.append(f"{key}={value}")
            message = "[AITS][TradeLogCenterProof] " + " ".join(parts)
            print(message, flush=True)
            log.info(message)
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setObjectName("aitsTradeLogCenterTab")
        self.setStyleSheet(
            """
            QWidget#aitsTradeLogCenterTab {
                background: #f4f6f8;
            }
            QFrame[tradeCard="true"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 12px;
            }
            QFrame[kpiCard="true"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 10px;
            }
            QLabel[muted="true"] {
                color: #667085;
                font-size: 11px;
            }
            QLabel[sectionTitle="true"] {
                color: #17202a;
                font-size: 15px;
                font-weight: 900;
            }
            QLabel[badge="true"] {
                color: #136f45;
                background: #e8f7ef;
                border: 1px solid #b8e2c8;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton[filterButton="true"] {
                border: 1px solid #cfd8e3;
                border-radius: 8px;
                padding: 6px 10px;
                background: #ffffff;
                color: #344054;
                font-weight: 700;
            }
            QPushButton[filterButton="true"]:checked {
                border: 2px solid #1f6feb;
                background: #eef6ff;
                color: #1f4fbf;
            }
            QPushButton[actionButton="true"] {
                border: 1px solid #cfd8e3;
                border-radius: 8px;
                padding: 6px 10px;
                background: #ffffff;
                color: #344054;
                font-weight: 800;
            }
            QLineEdit, QDateEdit {
                min-height: 28px;
                border: 1px solid #cfd8e3;
                border-radius: 8px;
                padding: 2px 8px;
                background: #ffffff;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: #edf2f7;
                selection-background-color: #eaf2ff;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #475467;
                border: none;
                border-right: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
                padding: 7px 8px;
                font-weight: 800;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._build_header())
        root.addLayout(self._build_kpis())
        root.addWidget(self._build_filter_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)
        body.addWidget(self._build_table_card(), 3)
        detail = self._build_detail_card()
        detail.setFixedWidth(320)
        body.addWidget(detail, 1)
        root.addLayout(body, 1)
        self._emit_proof("dashboard_ready", table=True, detail=True)

    def _card(self) -> QFrame:
        card = QFrame()
        card.setProperty("tradeCard", True)
        return card

    def _build_header(self) -> QFrame:
        card = self._card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(5)
        title_row = QHBoxLayout()
        title = QLabel("매매기록 센터")
        title.setStyleSheet("font-size: 20px; font-weight: 900; color: #111827;")
        badge = QLabel("Preview")
        badge.setProperty("badge", True)
        title_row.addWidget(title)
        title_row.addWidget(badge, 0)
        title_row.addStretch(1)
        desc = QLabel("실제 체결, Preview 판단, Reflection, 차단 이력을 구분해 확인합니다.")
        desc.setWordWrap(True)
        desc.setProperty("muted", True)
        text_col.addLayout(title_row)
        text_col.addWidget(desc)
        layout.addLayout(text_col, 1)

        notice = QLabel("기록 확인 전용 · 주문 없음")
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice.setStyleSheet(
            "background:#f8fafc; border:1px solid #dce3ea; border-radius:10px;"
            "padding:8px 12px; color:#344054; font-weight:800; font-size:11px;"
        )
        layout.addWidget(notice, 0)
        return card

    def _build_kpis(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        specs = (
            ("total", "전체 기록"),
            ("fills", "실제 체결"),
            ("preview", "Preview 판단"),
            ("blocked", "차단/보류"),
            ("engine", "최근 엔진"),
        )
        for col, (key, title) in enumerate(specs):
            card = QFrame()
            card.setProperty("kpiCard", True)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(4)
            label = QLabel(title)
            label.setProperty("muted", True)
            value = QLabel("-")
            value.setStyleSheet("font-size: 18px; font-weight: 900; color: #111827;")
            layout.addWidget(label)
            layout.addWidget(value)
            self._kpi_values[key] = value
            grid.addWidget(card, 0, col)
        return grid

    def _build_filter_bar(self) -> QFrame:
        card = self._card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in self.FILTERS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("filterButton", True)
            btn.clicked.connect(lambda checked=False, value=key: self._set_filter(value))
            group.addButton(btn)
            self._filter_buttons[key] = btn
            layout.addWidget(btn, 0)
        self._filter_buttons["all"].setChecked(True)

        self.dt_from = QDateEdit()
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd")
        self.dt_from.setDate(QDate.currentDate().addMonths(-1))
        self.dt_to = QDateEdit()
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd")
        self.dt_to.setDate(QDate.currentDate())
        self.ed_symbol = QLineEdit()
        self.ed_symbol.setPlaceholderText("종목 검색")
        self.ed_symbol.setMaximumWidth(150)
        self.ed_symbol.textChanged.connect(self._apply_filters)
        self.dt_from.dateChanged.connect(self._apply_filters)
        self.dt_to.dateChanged.connect(self._apply_filters)

        layout.addWidget(QLabel("날짜 범위"))
        layout.addWidget(self.dt_from)
        layout.addWidget(self.dt_to)
        layout.addWidget(self.ed_symbol)
        layout.addStretch(1)

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("actionButton", True)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_export = QPushButton("CSV 내보내기")
        self.btn_export.setProperty("actionButton", True)
        self.btn_export.clicked.connect(self.export_csv)
        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.btn_export)
        return card

    def _build_table_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title = QLabel("기록 목록")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        self.empty_label = QLabel(
            "아직 표시할 매매기록이 없습니다.\n"
            "Preview/Shadow 실행 시 AI 판단 기록이 이곳에 표시됩니다.\n"
            "실제 주문이 없으면 체결 기록은 0건일 수 있습니다."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(
            "background:#f8fafc; border:1px dashed #cfd8e3; border-radius:10px;"
            "padding:28px; color:#667085; font-weight:700;"
        )
        self.empty_label.hide()

        self.tbl_records = QTableWidget(0, len(self.COLUMNS))
        self.tbl_records.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.tbl_records.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_records.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_records.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_records.setAlternatingRowColors(True)
        self.tbl_records.setShowGrid(False)
        self.tbl_records.setMinimumHeight(360)
        self.tbl_records.verticalHeader().setVisible(False)
        header = self.tbl_records.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumHeight(36)
        header.setStretchLastSection(True)
        self.tbl_records.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.tbl_records, 1)
        return card

    def _build_detail_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        title = QLabel("기록 상세")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        self.detail_placeholder = QLabel("기록을 선택하면 상세 정보가 표시됩니다.")
        self.detail_placeholder.setWordWrap(True)
        self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_placeholder.setStyleSheet(
            "background:#f8fafc; border:1px dashed #cfd8e3; border-radius:10px;"
            "padding:18px; color:#667085; font-weight:700;"
        )
        layout.addWidget(self.detail_placeholder)

        for key, label in (
            ("type", "기록 유형"),
            ("symbol", "종목"),
            ("action", "판단 Action"),
            ("submitted", "주문 실행 여부"),
            ("selected_engine", "선택 엔진"),
            ("actual_engine", "실제 엔진"),
            ("basis", "판단 근거"),
            ("reason", "사유"),
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            self.refresh()
        except Exception:
            pass

    def refresh(self) -> None:
        rows: list[dict[str, Any]] = []
        try:
            from app.db.trades_db import recent_trades

            rows = list(recent_trades(300) or [])
        except Exception as exc:
            log.info("[TradeLogCenter] recent_trades unavailable: %s", exc)
            rows = []
        normalized = [self._normalize_trade_row(row) for row in rows]
        try:
            parent = getattr(self, "_parent_window", None)
            getter = getattr(parent, "_get_trade_log_shadow_journal_rows", None)
            if callable(getter):
                for row in list(getter(limit=300) or []):
                    if isinstance(row, dict):
                        normalized.append(self._normalize_trade_row(row))
        except Exception as exc:
            log.info("[TradeLogCenter] shadow journal unavailable: %s", exc)
        try:
            normalized.sort(key=lambda row: float(row.get("sort_ts") or 0), reverse=True)
        except Exception:
            pass
        self._rows = normalized[:300]
        self._apply_filters()
        self._emit_proof("refresh", rows=len(self._rows))

    def export_csv(self) -> None:
        QMessageBox.information(
            self,
            "CSV 내보내기",
            "CSV 내보내기는 안전한 기록 export 경로가 확정된 뒤 연결됩니다.\n현재 화면에서는 주문이 실행되지 않습니다.",
        )

    def _set_filter(self, value: str) -> None:
        self._filter = value
        for key, btn in self._filter_buttons.items():
            btn.setChecked(key == value)
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = (self.ed_symbol.text() if hasattr(self, "ed_symbol") else "").strip().upper()
        rows = []
        for row in self._rows:
            if self._filter != "all" and row.get("category") != self._filter:
                continue
            if query and query not in str(row.get("symbol") or "").upper():
                continue
            rows.append(row)
        self._visible_rows = rows
        self._populate_table(rows)
        self._update_kpis()
        self._set_detail(None)

    def _populate_table(self, rows: list[dict[str, Any]]) -> None:
        table = self.tbl_records
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
            item = QTableWidgetItem(
                "아직 표시할 매매기록이 없습니다.\n"
                "Preview/Shadow 실행 시 AI 판단 기록이 이곳에 표시됩니다.\n"
                "실제 주문이 없으면 체결 기록은 0건일 수 있습니다."
            )
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, None)
            table.setItem(0, 0, item)
            table.setRowHeight(0, 230)
            self.empty_label.hide()
            return
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = (
                row.get("time"),
                row.get("type"),
                row.get("symbol"),
                row.get("action"),
                row.get("status"),
                row.get("price"),
                row.get("amount"),
                row.get("selected_engine"),
                row.get("actual_engine"),
            )
            for c, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.ItemDataRole.UserRole, r)
                table.setItem(r, c, item)
            try:
                table.setRowHeight(r, 34)
            except Exception:
                pass
        self.empty_label.hide()
        table.resizeColumnsToContents()

    def _on_row_selected(self) -> None:
        selected = self.tbl_records.selectedItems()
        if not selected:
            self._set_detail(None)
            return
        row_index = selected[0].data(Qt.ItemDataRole.UserRole)
        if row_index is None:
            self._set_detail(None)
            return
        try:
            row = self._visible_rows[int(row_index)]
        except Exception:
            row = None
        self._set_detail(row)

    def _set_detail(self, row: dict[str, Any] | None) -> None:
        is_empty = row is None
        self.detail_placeholder.setVisible(is_empty)
        values = {
            "type": row.get("type") if row else "-",
            "symbol": row.get("symbol") if row else "-",
            "action": row.get("action") if row else "-",
            "submitted": row.get("submitted") if row else "-",
            "selected_engine": row.get("selected_engine") if row else "-",
            "actual_engine": row.get("actual_engine") if row else "-",
            "basis": row.get("basis") if row else "-",
            "reason": row.get("reason") if row else "-",
        }
        for key, value in values.items():
            label = self._detail_values.get(key)
            if label is not None:
                label.setText(str(value or "-"))

    def _update_kpis(self) -> None:
        total = len(self._rows)
        fills = sum(1 for row in self._rows if row.get("category") == "fills")
        preview = sum(1 for row in self._rows if row.get("category") == "preview")
        blocked = sum(1 for row in self._rows if row.get("category") == "blocked")
        engine = "-"
        for row in self._rows:
            engine = row.get("actual_engine") or row.get("selected_engine") or "-"
            if engine != "-":
                break
        values = {
            "total": str(total),
            "fills": str(fills),
            "preview": str(preview),
            "blocked": str(blocked),
            "engine": str(engine),
        }
        for key, value in values.items():
            label = self._kpi_values.get(key)
            if label is not None:
                label.setText(value)

    def _normalize_trade_row(self, row: dict[str, Any]) -> dict[str, Any]:
        if str(row.get("record_type") or "").strip() or str(row.get("category") or "").strip() in {"preview", "blocked", "reflection"}:
            return self._normalize_journal_row(row)
        ts = row.get("ts") or row.get("time") or row.get("created_at")
        time_text = self._format_time(ts)
        symbol = row.get("market") or row.get("symbol") or "-"
        side = str(row.get("side") or row.get("action") or "-").upper()
        price = self._format_number(row.get("price"))
        amount_raw = row.get("krw_cost") if row.get("krw_cost") is not None else row.get("amount")
        amount = self._format_number(amount_raw)
        selected_engine = row.get("selected_engine") or row.get("ai_mode") or row.get("selected_mode") or "-"
        actual_engine = row.get("actual_engine") or "-"
        status = row.get("status") or row.get("state") or "기록"
        reason = row.get("reason_code") or row.get("reason_short") or row.get("reason") or "-"
        submitted = row.get("submitted")
        if submitted is None:
            submitted_text = "체결 기록"
        else:
            submitted_text = "실행됨" if str(submitted) not in ("0", "False", "false", "") else "주문 없음"
        return {
            "category": "fills",
            "sort_ts": self._sort_timestamp(ts),
            "time": time_text,
            "type": "실제 체결",
            "symbol": symbol,
            "action": side,
            "status": status,
            "price": price,
            "amount": amount,
            "selected_engine": selected_engine,
            "actual_engine": actual_engine,
            "submitted": submitted_text,
            "basis": row.get("reason_short") or "-",
            "reason": reason,
        }

    def _normalize_journal_row(self, row: dict[str, Any]) -> dict[str, Any]:
        ts = row.get("ts") or row.get("timestamp") or row.get("time") or row.get("created_at")
        record_type = str(row.get("record_type") or row.get("type") or "preview_decision").strip()
        category = str(row.get("category") or "").strip().lower()
        if not category:
            if record_type in {"blocked", "skipped", "risk_blocked"}:
                category = "blocked"
            elif record_type == "reflection":
                category = "reflection"
            else:
                category = "preview"
        type_label = str(row.get("type_label") or "").strip()
        if not type_label:
            type_label = {
                "shadow_decision": "Shadow 판단",
                "preview_decision": "Preview 판단",
                "blocked": "차단/보류",
                "skipped": "스킵",
                "reflection": "Reflection",
            }.get(record_type, "Preview 판단")
        return {
            "category": category,
            "sort_ts": self._sort_timestamp(ts),
            "time": self._format_time(ts),
            "type": type_label,
            "symbol": row.get("symbol") or "-",
            "action": row.get("action_display") or row.get("action") or "-",
            "status": row.get("status_display") or row.get("status") or "실제 주문 없음",
            "price": row.get("price") or "-",
            "amount": row.get("amount") or "-",
            "selected_engine": row.get("selected_engine") or "-",
            "actual_engine": row.get("actual_engine") or row.get("provider") or "-",
            "submitted": row.get("submitted_display") or "실제 주문 없음",
            "basis": row.get("basis") or row.get("reason") or "-",
            "reason": row.get("skip_reason") or row.get("reason") or row.get("safety_note") or "-",
        }

    def _sort_timestamp(self, value: Any) -> float:
        try:
            if isinstance(value, (int, float)) or str(value).isdigit():
                ts = float(value)
                if ts > 10_000_000_000:
                    ts = ts / 1000
                return ts
            text = str(value or "").strip()
            if text:
                try:
                    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
        except Exception:
            pass
        return 0.0

    def _format_time(self, value: Any) -> str:
        try:
            if isinstance(value, (int, float)) or str(value).isdigit():
                ts = int(float(value))
                if ts > 10_000_000_000:
                    ts = int(ts / 1000)
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            if value:
                return str(value)
        except Exception:
            pass
        return "-"

    def _format_number(self, value: Any) -> str:
        try:
            num = float(value or 0)
            if abs(num) >= 1000:
                return f"{num:,.0f}"
            return f"{num:g}"
        except Exception:
            return "" if value is None else str(value)
