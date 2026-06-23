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
        self._column_widths_dirty = False
        self._has_saved_column_widths = False
        self._restoring_column_widths = False
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
        try:
            header.sectionResized.connect(self._on_column_resized)
        except Exception:
            pass
        self._restore_column_widths_from_parent()
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
        self._apply_default_column_widths_if_needed()

    def _apply_default_column_widths_if_needed(self) -> None:
        if self._column_widths_dirty or self._has_saved_column_widths:
            return
        table = getattr(self, "tbl_records", None)
        if table is None:
            return
        try:
            self._restoring_column_widths = True
            table.resizeColumnsToContents()
        except Exception:
            pass
        finally:
            self._restoring_column_widths = False

    def _on_column_resized(self, *_args) -> None:
        if bool(getattr(self, "_restoring_column_widths", False)):
            return
        self._column_widths_dirty = True
        try:
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info("[AITS][TradeLogCenterLayout] event=dirty reason=column_resized submitted=0")
        except Exception:
            pass

    def get_column_widths(self) -> list[int]:
        table = getattr(self, "tbl_records", None)
        if table is None:
            return []
        header = table.horizontalHeader()
        widths: list[int] = []
        try:
            for idx in range(table.columnCount()):
                widths.append(int(header.sectionSize(idx)))
        except Exception:
            return []
        return widths

    def _restore_column_widths_from_parent(self) -> bool:
        try:
            parent = getattr(self, "_parent_window", None)
            ui_getter = getattr(parent, "_get_ui_state_dict", None)
            ui_state = ui_getter() if callable(ui_getter) else {}
            state = dict((ui_state or {}).get("trade_log_center_layout_state") or {})
            widths = state.get("column_widths")
            table = getattr(self, "tbl_records", None)
            if table is None or not isinstance(widths, list) or len(widths) != table.columnCount():
                return False
            self._restoring_column_widths = True
            header = table.horizontalHeader()
            for idx, width in enumerate(widths):
                try:
                    w = int(width)
                except Exception:
                    w = 0
                if w > 20:
                    header.resizeSection(idx, w)
            self._has_saved_column_widths = True
            self._column_widths_dirty = False
            try:
                parent_log = getattr(parent, "_log", None)
                if parent_log is not None:
                    parent_log.info(
                        "[AITS][TradeLogCenterLayout] event=restore_column_widths columns=%s submitted=0",
                        len(widths),
                    )
            except Exception:
                pass
            return True
        except Exception:
            return False
        finally:
            self._restoring_column_widths = False

    def clear_layout_dirty(self) -> None:
        self._column_widths_dirty = False
        self._has_saved_column_widths = True

    def save_layout_state(self) -> bool:
        parent = getattr(self, "_parent_window", None)
        saver = getattr(parent, "_save_trade_log_center_state", None)
        if callable(saver):
            return bool(saver(reason="trade_log_center_tab_save"))
        return False

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

    def _humanize_trade_log_text(self, text: Any) -> str:
        value = str(text or "").strip()
        if not value or value == "-":
            return "-"
        replacements = (
            ("보유 여유슬롯 존재 + 신규 후보 우위", "현재 보유 여력이 있어 신규 후보를 우선 검토하는 상황입니다."),
            ("신규 후보 우위", "새 후보 종목의 우선순위가 높아 추가 관찰 대상으로 검토 중입니다."),
            ("보유 여유슬롯 존재", "현재 보유 여력이 있어 추가 관찰 후보를 검토할 수 있습니다."),
        )
        for old, new in replacements:
            value = value.replace(old, new)
        return value.strip() or "-"

    def _trade_log_basis_kind(self, text: Any, action: Any = "") -> str:
        value = str(text or "").replace(" ", "")
        action_text = str(action or "").lower()
        if "기존보유" in value or "보유유지" in value or "확신부족" in value:
            return "hold_priority"
        if "보유여유" in value or "신규후보우위" in value or "신규후보를우선검토" in value or "추가로관찰할수있는여유" in value:
            return "new_candidate_priority"
        if "데이터부족" in value or "거래대금" in value or "필터" in value:
            return "data_or_liquidity_limited"
        if "판단불가" in value:
            return "undecidable"
        if "진입검토" in value or "진입" in value or "enter" in action_text or "buy" in action_text:
            return "entry_review"
        if "관망" in value or "stay" in action_text or "hold" in action_text or "wait" in action_text:
            return "watch"
        return "generic"

    def _format_trade_log_user_reason(self, basis: Any, reason: Any = "", action: Any = "", status: Any = "") -> tuple[str, bool, str]:
        basis_text = self._humanize_trade_log_text(basis)
        reason_text = self._humanize_trade_log_text(reason)
        action_text = str(action or "").strip()
        status_text = str(status or "").strip()
        combined = " ".join(
            item for item in (str(basis_text or ""), str(reason_text or ""), action_text, status_text) if item and item != "-"
        )
        kind = self._trade_log_basis_kind(combined, action_text)

        if reason_text not in ("", "-") and reason_text != basis_text:
            stripped = reason_text.replace("표시용 판단 기록이며 실제 주문은 실행되지 않았습니다.", "").strip()
            if len(stripped) >= 28 and stripped != basis_text:
                return stripped, False, kind

        templates = {
            "hold_priority": (
                "현재는 새 종목을 추가로 매수하기보다 이미 보유 중인 포지션을 유지하는 쪽이 더 안전하다고 판단했습니다. "
                "새 후보는 가격 흐름이나 거래 조건이 아직 충분히 강하지 않아 관망합니다."
            ),
            "new_candidate_priority": (
                "현재 추가로 관찰할 수 있는 여유가 있고, 새 후보 종목의 우선순위가 기존 후보보다 높게 평가되었습니다. "
                "다만 즉시 주문을 실행할 단계는 아니므로 관찰 대상으로 기록합니다."
            ),
            "data_or_liquidity_limited": (
                "현재 후보 종목은 판단에 필요한 데이터가 부족하거나 거래대금 조건을 충분히 만족하지 못했습니다. "
                "그래서 새로 진입하기보다 추가 확인이 필요하다고 판단했습니다."
            ),
            "watch": (
                "현재는 매수나 매도 중 하나를 선택하기보다 시장 흐름을 더 확인하는 구간입니다. "
                "추가 신호가 확인되기 전까지는 지켜보는 판단입니다."
            ),
            "undecidable": (
                "현재 데이터만으로는 매수·매도 방향을 확정하기 어렵습니다. "
                "신호가 불충분하므로 판단을 보류합니다."
            ),
            "entry_review": (
                "현재 조건은 신규 진입 후보로 검토할 만하지만, 아직 즉시 주문을 실행할 정도로 확정된 상태는 아닙니다. "
                "추가 조건 확인이 필요합니다."
            ),
        }
        if kind in templates:
            return templates[kind], True, kind
        if basis_text not in ("", "-"):
            return (
                f"{basis_text} 이 판단은 참고용 요약이며, 매수·매도 방향을 확정하기 전에 추가 확인이 필요합니다.",
                True,
                kind,
            )
        if action_text:
            return (
                f"{action_text} 상태로 기록된 판단입니다. 현재 화면에서는 주문 실행보다 판단 내용 확인을 우선합니다.",
                True,
                kind,
            )
        return "판단에 필요한 설명 정보가 충분하지 않아 상세 사유를 확인할 수 없습니다.", True, kind

    def _split_journal_basis_reason(self, row: dict[str, Any] | None) -> tuple[str, str, bool]:
        if not row:
            return "-", "-", False
        basis_source = row.get("basis") or row.get("reason_short") or row.get("next_action") or row.get("action_display") or ""
        reason_source = row.get("skip_reason") or row.get("reason") or row.get("safety_note") or row.get("basis") or ""
        basis = self._humanize_trade_log_text(basis_source)
        reason = self._humanize_trade_log_text(reason_source)
        identical_before = bool(basis and reason and basis != "-" and basis == reason)
        if basis in ("", "-") and reason not in ("", "-"):
            basis = reason.split("。")[0].split(".")[0].split("·")[0].strip()[:90] or reason
        if reason in ("", "-") or identical_before:
            reason, _generated, _kind = self._format_trade_log_user_reason(
                basis,
                reason,
                row.get("action") or row.get("action_display") or "",
                row.get("status") or row.get("status_display") or "",
            )
        else:
            reason, _generated, _kind = self._format_trade_log_user_reason(
                basis,
                reason,
                row.get("action") or row.get("action_display") or "",
                row.get("status") or row.get("status_display") or "",
            )
        return basis or "-", reason or "-", identical_before

    def _emit_reason_audit(self, identical_before: bool, basis: str, reason: str) -> None:
        if not identical_before:
            return
        try:
            identical_after = bool(basis and reason and basis == reason)
            message = (
                "[AITS][TradeLogReasonAudit] "
                f"event=detail_reason_split source_fields=basis,reason "
                f"identical_before={identical_before} identical_after={identical_after} submitted=0"
            )
            log.info(message)
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _emit_user_reason_log(self, row: dict[str, Any] | None, basis: str, reason: str) -> None:
        if not row:
            return
        try:
            _reason, generated, kind = self._format_trade_log_user_reason(
                basis,
                row.get("reason") or row.get("skip_reason") or "",
                row.get("action") or row.get("action_display") or "",
                row.get("status") or row.get("status_display") or "",
            )
            message = (
                "[AITS][TradeLogUserReason] "
                f"event={'format' if generated else 'skip'} "
                f"basis_kind={kind} reason_generated={generated} submitted=0"
            )
            log.info(message)
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _parse_ai_decision_ts(self, value: Any) -> datetime | None:
        try:
            if isinstance(value, (int, float)) or str(value).isdigit():
                ts = float(value)
                if ts > 10_000_000_000:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts)
            raw = str(value or "").strip()
            if not raw:
                return None
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            try:
                raw = str(value or "").strip().replace("Z", "").split("+")[0]
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                    try:
                        return datetime.strptime(raw, fmt)
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    def _format_ai_decision_age_label(self, age_sec: int | None) -> str:
        try:
            if age_sec is None:
                return "\ud310\ub2e8 \uc2dc\uac01 \ud655\uc778 \ubd88\uac00"
            sec = max(0, int(age_sec))
            if sec < 60:
                return "\ubc29\uae08 \uc804"
            minutes = sec // 60
            if minutes < 60:
                return f"{minutes}\ubd84 \uc804"
            hours = minutes // 60
            rem = minutes % 60
            return f"{hours}\uc2dc\uac04 {rem}\ubd84 \uc804" if rem else f"{hours}\uc2dc\uac04 \uc804"
        except Exception:
            return "\ud310\ub2e8 \uc2dc\uac01 \ud655\uc778 \ubd88\uac00"

    def _build_trade_log_freshness_state(self, row: dict[str, Any] | None) -> dict[str, Any]:
        try:
            row = row if isinstance(row, dict) else {}
            record_type = str(row.get("record_type") or row.get("type") or "").strip()
            category = str(row.get("category") or "").strip().lower()
            is_journal = bool(record_type or category in {"preview", "blocked", "reflection"})
            if not is_journal:
                return {"display_label": "-", "freshness": "not_applicable", "age_sec": None, "warning_text": ""}
            ts_value = (
                row.get("generated_at")
                or row.get("decision_generated_at")
                or row.get("ai_briefing_generated_at")
                or row.get("timestamp")
                or row.get("ts")
                or row.get("time")
                or row.get("created_at")
            )
            parsed = self._parse_ai_decision_ts(ts_value)
            age_sec = None
            if parsed is not None:
                age_sec = max(0, int((datetime.now() - parsed).total_seconds()))
            if age_sec is None:
                state = "unknown"
                label = "\ud310\ub2e8 \uc2dc\uac01 \ud655\uc778 \ubd88\uac00"
                warning = "\uc0dd\uc131 \uc2dc\uac01\uc744 \ud655\uc778\ud560 \uc218 \uc5c6\uc5b4 \ucd5c\uc2e0 \ud310\ub2e8\uc73c\ub85c \ubcf4\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."
            elif age_sec <= 10 * 60:
                state = "fresh"
                label = f"\ucd5c\uc2e0 \ud310\ub2e8 \u00b7 {self._format_ai_decision_age_label(age_sec)}"
                warning = ""
            elif age_sec <= 30 * 60:
                state = "reference"
                label = f"\ucd5c\uadfc \ucc38\uace0 \ud310\ub2e8 \u00b7 {self._format_ai_decision_age_label(age_sec)}"
                warning = "\uc2dc\uc7a5\uc774 \ubcc0\ud588\uc744 \uc218 \uc788\uc73c\ubbc0\ub85c \ucc38\uace0\uc6a9\uc73c\ub85c \ubcf4\uc138\uc694."
            elif age_sec <= 60 * 60:
                state = "stale"
                label = f"\uc624\ub798\ub41c \ud310\ub2e8 \u00b7 {self._format_ai_decision_age_label(age_sec)} \u00b7 \uc7ac\uac80\ud1a0 \ud544\uc694"
                warning = "\ud604\uc7ac \uc2dc\uc7a5 \uc0c1\ud669\uacfc \ub2e4\ub97c \uc218 \uc788\uc5b4 \uc0c8 \ubd84\uc11d\uc774 \ud544\uc694\ud569\ub2c8\ub2e4."
            else:
                state = "very_stale"
                label = "\uc624\ub798\ub41c \ud310\ub2e8 \u00b7 1\uc2dc\uac04 \uc774\uc0c1 \uacbd\uacfc \u00b7 \uc0c8 \ubd84\uc11d \uad8c\uc7a5"
                warning = "\ucd5c\uc2e0 \ud310\ub2e8\uc73c\ub85c \ubcf4\uae30 \uc5b4\ub835\uc2b5\ub2c8\ub2e4. \uc0c8 \ubd84\uc11d \ud6c4 \ud310\ub2e8\ud558\uc138\uc694."
            return {"display_label": label, "freshness": state, "age_sec": age_sec, "warning_text": warning}
        except Exception:
            return {"display_label": "\ud310\ub2e8 \uc2dc\uac01 \ud655\uc778 \ubd88\uac00", "freshness": "unknown", "age_sec": None, "warning_text": ""}

    def _emit_trade_log_freshness_log(self, row: dict[str, Any] | None, freshness: dict[str, Any]) -> None:
        try:
            if not row:
                return
            state = str(freshness.get("freshness") or "unknown")
            age = freshness.get("age_sec") if freshness.get("age_sec") is not None else "unknown"
            symbol = str(row.get("symbol") or "")
            message = (
                "[AITS][AIDecisionFreshness] "
                f"event=state symbol={symbol} freshness={state} age_sec={age} "
                "source=trade_log submitted=0 order_allowed=False real_order=False"
            )
            log.info(message)
            parent_log = getattr(getattr(self, "_parent_window", None), "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _set_detail(self, row: dict[str, Any] | None) -> None:
        is_empty = row is None
        self.detail_placeholder.setVisible(is_empty)
        basis, reason, identical_before = self._split_journal_basis_reason(row)
        freshness = self._build_trade_log_freshness_state(row)
        self._emit_reason_audit(identical_before, basis, reason)
        self._emit_user_reason_log(row, basis, reason)
        self._emit_trade_log_freshness_log(row, freshness)
        freshness_text = str(freshness.get("display_label") or "-")
        warning_text = str(freshness.get("warning_text") or "").strip()
        if warning_text:
            freshness_text = f"{freshness_text}\n{warning_text}"
        values = {
            "type": row.get("type") if row else "-",
            "symbol": row.get("symbol") if row else "-",
            "action": row.get("action") if row else "-",
            "submitted": row.get("submitted") if row else "-",
            "freshness": freshness_text if row else "-",
            "selected_engine": row.get("selected_engine") if row else "-",
            "actual_engine": row.get("actual_engine") if row else "-",
            "basis": basis,
            "reason": reason,
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
            "freshness": "-",
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
        basis, reason, _identical_before = self._split_journal_basis_reason(row)
        freshness = self._build_trade_log_freshness_state(row)
        freshness_text = str(freshness.get("display_label") or "-")
        warning_text = str(freshness.get("warning_text") or "").strip()
        if warning_text:
            freshness_text = f"{freshness_text}\n{warning_text}"
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
            "basis": basis,
            "reason": reason,
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
