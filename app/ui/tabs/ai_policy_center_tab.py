from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.utils.prefs import load_settings, save_settings_patch


log = logging.getLogger(__name__)


class AIPolicyCenterTab(QWidget):
    """Dedicated AI Policy Center surface.

    This tab owns only UI policy snapshot editing. It does not attach StrategyTab,
    and it does not call provider, router, execution, order, or risk guard paths.
    """

    MODE_LABELS = {
        "ai_led": "AI 주도형",
        "balanced": "균형형",
        "user_controlled": "사용자 통제형",
    }
    INVOLVEMENT_LABELS = {
        "low": "낮음",
        "standard": "표준",
        "high": "높음",
    }

    def __init__(self, parent_window=None, parent=None):
        super().__init__(parent)
        self._parent_window = parent_window
        self._mode_buttons: dict[str, QRadioButton] = {}
        self._mode_cards: dict[str, QFrame] = {}
        self._involvement_buttons: dict[str, QRadioButton] = {}
        self._involvement_cards: dict[str, QFrame] = {}
        self._summary_values: dict[str, QLabel] = {}
        self._summary_label: QLabel | None = None
        self._saved_at_label: QLabel | None = None
        self._loading = False
        self._emit_policy_tab_proof("create_new_tab", widget="AIPolicyCenterTab")
        self._build_ui()
        self._restore_snapshot()
        self._update_summary()
        self._emit_policy_tab_proof("active_policy_tab_ready", dashboard=True, sidebar=True, legacy_default_visible=False)

    def _emit_policy_tab_proof(self, event: str, **fields: Any) -> None:
        try:
            parts = [f"event={event}"]
            for key, value in fields.items():
                parts.append(f"{key}={value}")
            message = "[AITS][PolicyTabProof] " + " ".join(parts)
            print(message, flush=True)
            log.info(message)
            parent = getattr(self, "_parent_window", None)
            parent_log = getattr(parent, "_log", None)
            if parent_log is not None:
                parent_log.info(message)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setObjectName("aitsAiPolicyCenterDedicatedTab")
        self.setStyleSheet(
            """
            QWidget#aitsAiPolicyCenterDedicatedTab {
                background: #f4f6f8;
            }
            QFrame[policyCard="true"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 12px;
            }
            QFrame[modeCard="true"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 10px;
            }
            QFrame[modeCardSelected="true"] {
                background: #eef6ff;
                border: 2px solid #1f6feb;
                border-radius: 10px;
            }
            QFrame[compactField="true"] {
                background: #f8fafc;
                border: 1px solid #dce3ea;
                border-radius: 10px;
            }
            QFrame[summarySection="true"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 10px;
            }
            QFrame[accentStrip="true"] {
                background: #1f6feb;
                border: none;
                border-radius: 3px;
                min-width: 4px;
                max-width: 4px;
            }
            QLabel[sectionTitle="true"] {
                color: #17202a;
                font-size: 15px;
                font-weight: 800;
            }
            QLabel[muted="true"] {
                color: #667085;
                font-size: 11px;
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
            QLabel[selectedMark="true"] {
                color: #1f6feb;
                background: #eaf2ff;
                border: 1px solid #bfd7ff;
                border-radius: 7px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 800;
            }
            QSpinBox {
                min-height: 26px;
                max-width: 168px;
                border: 1px solid #cfd8e3;
                border-radius: 6px;
                padding: 2px 8px;
                background: #ffffff;
            }
            QRadioButton::indicator {
                width: 0px;
                height: 0px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header_card())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        main_col = QVBoxLayout()
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(10)
        main_col.addWidget(self._build_operating_mode_card())
        main_col.addWidget(self._build_risk_budget_card())
        main_col.addWidget(self._build_involvement_card())
        main_col.addWidget(self._build_local_data_card())
        main_col.addStretch(1)

        sidebar = self._build_summary_sidebar()
        sidebar.setFixedWidth(310)

        body.addLayout(main_col, 3)
        body.addWidget(sidebar, 1)
        root.addLayout(body, 1)
        self._emit_policy_tab_proof("dashboard_ready", left_cards=4, sidebar=True)

    def _card(self, object_name: str | None = None) -> QFrame:
        card = QFrame()
        if object_name:
            card.setObjectName(object_name)
        card.setProperty("policyCard", True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        return card

    def _build_header_card(self) -> QFrame:
        card = self._card("aitsPolicyHeaderCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(6)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("AI 정책 센터")
        title.setStyleSheet("font-size: 19px; font-weight: 900; color: #111827;")
        badge = QLabel("Preview")
        badge.setProperty("badge", True)
        row.addWidget(title)
        row.addWidget(badge, 0)
        row.addStretch(1)
        desc = QLabel(
            "AI 정책을 설정하는 Preview 영역입니다. 저장만으로 주문은 실행되지 않으며 실제 매매는 별도 실행 모드와 안전 조건을 따릅니다."
        )
        desc.setWordWrap(True)
        desc.setProperty("muted", True)
        text_col.addLayout(row)
        text_col.addWidget(desc)
        layout.addLayout(text_col, 1)

        notice = QLabel("Preview/정책 관리 전용\n저장 시에도 주문 없음")
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice.setStyleSheet(
            "background: #f8fafc; border: 1px solid #dce3ea; border-radius: 10px;"
            "padding: 8px 12px; color: #344054; font-weight: 800; font-size: 11px;"
        )
        layout.addWidget(notice, 0)
        return card

    def _build_operating_mode_card(self) -> QFrame:
        card = self._card("aitsPolicyOperatingModeCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(self._section_title("1. AI 운용 방식"))

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        specs = (
            ("ai_led", "AI 주도형", "AI가 시장을 분석하고 관망·진입·청산 후보를 적극적으로 조절합니다."),
            ("balanced", "균형형", "AI 판단과 안전 조건을 균형 있게 반영합니다. 기본 권장 모드입니다."),
            ("user_controlled", "사용자 통제형", "AI는 분석과 후보를 제시하고 사용자의 확인을 더 우선합니다."),
        )
        for value, title, desc in specs:
            mode_card = QFrame()
            mode_card.setProperty("modeCard", True)
            mode_card.setCursor(Qt.CursorShape.PointingHandCursor)
            outer = QHBoxLayout(mode_card)
            outer.setContentsMargins(10, 9, 10, 9)
            outer.setSpacing(9)
            strip = QFrame()
            strip.setProperty("accentStrip", True)
            strip.setVisible(False)
            mode_layout = QVBoxLayout()
            mode_layout.setContentsMargins(0, 0, 0, 0)
            mode_layout.setSpacing(5)
            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            radio = QRadioButton(title)
            radio.setStyleSheet("font-weight: 900; color: #111827;")
            mark = QLabel("선택됨")
            mark.setProperty("selectedMark", True)
            mark.setVisible(False)
            detail = QLabel(desc)
            detail.setWordWrap(True)
            detail.setProperty("muted", True)
            top.addWidget(radio)
            top.addStretch(1)
            top.addWidget(mark)
            mode_layout.addLayout(top)
            mode_layout.addWidget(detail)
            outer.addWidget(strip, 0)
            outer.addLayout(mode_layout, 1)
            self.mode_group.addButton(radio)
            self._mode_buttons[value] = radio
            self._mode_cards[value] = mode_card
            mode_card._selected_mark = mark
            mode_card._accent_strip = strip
            radio.toggled.connect(lambda checked, v=value: self._on_mode_changed(v, checked))
            mode_card.mousePressEvent = lambda event, v=value: self._select_operating_mode(v)
            row.addWidget(mode_card, 1)
        layout.addLayout(row)
        return card

    def _build_risk_budget_card(self) -> QFrame:
        card = self._card("aitsPolicyRiskBudgetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(self._section_title("2. 운용 자금 한도"))

        self.sp_total_budget = self._money_spin()
        self.sp_max_entry = self._money_spin()
        self.sp_reserve_cash = self._money_spin()
        self.sp_max_positions = QSpinBox()
        self.sp_max_positions.setRange(1, 50)
        self.sp_max_positions.setValue(3)
        self.sp_daily_loss = self._money_spin()

        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(10)
        first_row.addWidget(self._field_block("총 운용 한도", "AITS가 운용 대상으로 삼을 수 있는 최대 금액입니다.", self.sp_total_budget), 1)
        first_row.addWidget(self._field_block("1회 진입 한도", "한 번의 신규 진입 또는 한 종목 기준 최대 진입 금액입니다.", self.sp_max_entry), 1)
        layout.addLayout(first_row)

        second_row = QHBoxLayout()
        second_row.setContentsMargins(0, 0, 0, 0)
        second_row.setSpacing(10)
        second_row.addWidget(self._field_block("예비 현금", "항상 남겨둘 최소 KRW입니다.", self.sp_reserve_cash), 1)
        second_row.addWidget(self._field_block("동시 보유 종목 수", "동시에 보유 가능한 최대 종목 수입니다.", self.sp_max_positions), 1)
        second_row.addWidget(self._field_block("일일 손실 제한", "한도 도달 시 신규 진입 중지 후보입니다. 즉시 강제 매도를 의미하지 않습니다.", self.sp_daily_loss), 1)
        layout.addLayout(second_row)

        for widget in (self.sp_total_budget, self.sp_max_entry, self.sp_reserve_cash, self.sp_max_positions, self.sp_daily_loss):
            widget.valueChanged.connect(self._on_policy_changed)
        return card

    def _build_involvement_card(self) -> QFrame:
        card = self._card("aitsPolicyInvolvementCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        layout.addWidget(self._section_title("3. AI 관여 수준"))
        desc = QLabel("AI 관여 수준은 판단 후보와 조건 계산에 반영되는 참고 강도입니다. 직접 주문 권한을 의미하지 않습니다.")
        desc.setWordWrap(True)
        desc.setProperty("muted", True)
        layout.addWidget(desc)
        self.involvement_group = QButtonGroup(self)
        self.involvement_group.setExclusive(True)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for value, title, hint in (
            ("low", "낮음", "보수적 참고"),
            ("standard", "표준", "기본 권장"),
            ("high", "높음", "강한 참고"),
        ):
            card_item = self._segment_card(value, title, hint)
            row.addWidget(card_item, 1)
        layout.addLayout(row)
        return card

    def _build_local_data_card(self) -> QFrame:
        card = self._card("aitsPolicyLocalDataCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        layout.addWidget(self._section_title("4. LOCAL 데이터 정책"))
        desc = QLabel("LOCAL 데이터 정책은 모델 선택이 아니라 데이터 보관, 복기, 학습 반영 기준을 정합니다.")
        desc.setWordWrap(True)
        desc.setProperty("muted", True)
        layout.addWidget(desc)

        self.chk_auto_manage = QCheckBox("권장 자동 관리")
        self.chk_auto_summary = QCheckBox("자동 요약")
        self.chk_block_learning = QCheckBox("검증 전 학습 차단")
        self.sp_raw_days = QSpinBox()
        self.sp_raw_days.setRange(7, 3650)
        self.sp_raw_days.setSuffix(" 일")
        self.sp_reflection_days = QSpinBox()
        self.sp_reflection_days.setRange(30, 3650)
        self.sp_reflection_days.setSuffix(" 일")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.addWidget(self._toggle_block(self.chk_auto_manage, "권장 자동 관리", "기본 보관/요약 정책을 사용합니다."), 0, 0)
        grid.addWidget(self._toggle_block(self.chk_auto_summary, "자동 요약", "오래된 원본은 요약 후보로 관리합니다."), 0, 1)
        grid.addWidget(self._toggle_block(self.chk_block_learning, "검증 전 학습 차단", "검증 전 후보는 active 반영하지 않습니다."), 0, 2)
        grid.addWidget(self._field_block("상세 데이터 보관 기간", "최근 원본 상세 데이터 기준입니다.", self.sp_raw_days), 1, 0)
        grid.addWidget(self._field_block("복기 데이터 보관 기간", "Reflection 이벤트 보관 기준입니다.", self.sp_reflection_days), 1, 1)
        layout.addLayout(grid)

        for widget in (self.chk_auto_manage, self.chk_auto_summary, self.chk_block_learning):
            widget.stateChanged.connect(self._on_policy_changed)
        for widget in (self.sp_raw_days, self.sp_reflection_days):
            widget.valueChanged.connect(self._on_policy_changed)
        return card

    def _build_summary_sidebar(self) -> QFrame:
        card = self._card("aitsPolicySummarySidebar")
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("정책 요약")
        title.setProperty("sectionTitle", True)
        badge = QLabel("Preview")
        badge.setProperty("badge", True)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(badge)
        layout.addLayout(title_row)

        layout.addWidget(self._summary_section("mode", "AI 운용 방식"))
        layout.addWidget(self._summary_section("budget", "운용 자금 한도"))
        layout.addWidget(self._summary_section("local", "LOCAL 데이터 정책"))
        layout.addWidget(self._summary_section("safe", "Preview/주문 없음"))

        self._saved_at_label = QLabel("미저장")
        self._saved_at_label.setProperty("muted", True)
        layout.addWidget(self._saved_at_label)

        notice = QLabel("저장은 정책 snapshot만 갱신합니다. 주문, 매수, 매도는 실행되지 않습니다.")
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px;"
            "padding: 8px; color: #7c2d12; font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(notice)

        layout.addStretch(1)
        self._emit_policy_tab_proof("summary_ready", sidebar=True)
        return card

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("sectionTitle", True)
        return label

    def _field_block(self, title: str, desc: str, widget: QWidget) -> QFrame:
        box = QFrame()
        box.setProperty("compactField", True)
        box.setMinimumHeight(96)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 800; color: #344054;")
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setProperty("muted", True)
        layout.addWidget(title_label)
        widget.setMaximumWidth(168)
        layout.addWidget(widget)
        layout.addWidget(desc_label)
        return box

    def _toggle_block(self, checkbox: QCheckBox, title: str, desc: str) -> QFrame:
        box = QFrame()
        box.setProperty("compactField", True)
        box.setMinimumHeight(78)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        checkbox.setText(title)
        checkbox.setStyleSheet("font-weight: 800; color: #344054;")
        hint = QLabel(desc)
        hint.setWordWrap(True)
        hint.setProperty("muted", True)
        layout.addWidget(checkbox)
        layout.addWidget(hint)
        return box

    def _segment_card(self, value: str, title: str, hint: str) -> QFrame:
        card = QFrame()
        card.setProperty("modeCard", True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)
        radio = QRadioButton(title)
        radio.setStyleSheet("font-weight: 900; color: #111827;")
        desc = QLabel(hint)
        desc.setProperty("muted", True)
        layout.addWidget(radio)
        layout.addWidget(desc)
        self.involvement_group.addButton(radio)
        self._involvement_buttons[value] = radio
        self._involvement_cards[value] = card
        radio.toggled.connect(lambda checked, v=value: self._on_involvement_changed(v, checked))
        card.mousePressEvent = lambda event, v=value: self._select_involvement(v)
        return card

    def _summary_section(self, key: str, title: str) -> QFrame:
        section = QFrame()
        section.setProperty("summarySection", True)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; font-weight: 900; color: #344054;")
        value_label = QLabel("")
        value_label.setWordWrap(True)
        value_label.setStyleSheet("font-size: 12px; color: #111827; line-height: 145%;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        self._summary_values[key] = value_label
        return section

    def _money_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 2_000_000_000)
        spin.setSingleStep(10_000)
        spin.setGroupSeparatorShown(True)
        spin.setSpecialValueText("미설정")
        spin.setSuffix(" 원")
        return spin

    def _select_operating_mode(self, value: str) -> None:
        button = self._mode_buttons.get(value)
        if button is not None:
            button.setChecked(True)

    def _on_mode_changed(self, value: str, checked: bool) -> None:
        if checked:
            self._refresh_mode_cards()
            self._on_policy_changed()

    def _refresh_mode_cards(self) -> None:
        selected = self._current_mode()
        for value, card in self._mode_cards.items():
            is_selected = value == selected
            card.setProperty("modeCardSelected", is_selected)
            card.setProperty("modeCard", not is_selected)
            mark = getattr(card, "_selected_mark", None)
            if mark is not None:
                mark.setVisible(is_selected)
            strip = getattr(card, "_accent_strip", None)
            if strip is not None:
                strip.setVisible(is_selected)
            card.style().unpolish(card)
            card.style().polish(card)

    def _select_involvement(self, value: str) -> None:
        button = self._involvement_buttons.get(value)
        if button is not None:
            button.setChecked(True)

    def _on_involvement_changed(self, value: str, checked: bool) -> None:
        if checked:
            self._refresh_involvement_cards()
            self._on_policy_changed()

    def _refresh_involvement_cards(self) -> None:
        selected = self._current_involvement()
        for value, card in self._involvement_cards.items():
            is_selected = value == selected
            card.setProperty("modeCardSelected", is_selected)
            card.setProperty("modeCard", not is_selected)
            card.style().unpolish(card)
            card.style().polish(card)

    def _on_policy_changed(self, *args) -> None:
        if self._loading:
            return
        self._update_summary()

    def _current_mode(self) -> str:
        for value, button in self._mode_buttons.items():
            if button.isChecked():
                return value
        return "balanced"

    def _current_involvement(self) -> str:
        for value, button in self._involvement_buttons.items():
            if button.isChecked():
                return value
        return "standard"

    def _snapshot(self) -> dict[str, Any]:
        mode = self._current_mode()
        involvement = self._current_involvement()
        risk_budget = {
            "total_budget_krw": int(self.sp_total_budget.value()),
            "max_entry_krw": int(self.sp_max_entry.value()),
            "reserve_cash_krw": int(self.sp_reserve_cash.value()),
            "max_positions": int(self.sp_max_positions.value()),
            "daily_loss_limit_krw": int(self.sp_daily_loss.value()),
        }
        local_data = {
            "auto_manage": bool(self.chk_auto_manage.isChecked()),
            "raw_retention_days": int(self.sp_raw_days.value()),
            "reflection_retention_days": int(self.sp_reflection_days.value()),
            "auto_summary_enabled": bool(self.chk_auto_summary.isChecked()),
            "block_unverified_learning": bool(self.chk_block_learning.isChecked()),
        }
        return {
            "schema": "aits_ai_policy_snapshot.v1",
            "policy_style": self.MODE_LABELS.get(mode, "균형형"),
            "preset_name": mode,
            "risk_level": 50,
            "wait_preference": 50,
            "autonomy_level": {"low": 30, "standard": 50, "high": 70}.get(involvement, 50),
            "preview_only": True,
            "applied_to_runtime": False,
            "applied_to_order": False,
            "ai_policy": {
                "operating_mode": mode,
                "ai_involvement_level": involvement,
                "risk_budget": risk_budget,
                "local_data": local_data,
            },
        }

    def get_policy_snapshot(self) -> dict[str, Any]:
        """Export the current UI-only policy snapshot without side effects."""
        return dict(self._snapshot())

    def export_policy_snapshot(self) -> dict[str, Any]:
        return self.get_policy_snapshot()

    def apply_policy_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        """Apply a saved UI policy snapshot to widgets and refresh the summary."""
        self._loading = True
        try:
            if not isinstance(snapshot, dict):
                snapshot = {}
            ai_policy = snapshot.get("ai_policy", {})
            if not isinstance(ai_policy, dict):
                ai_policy = {}
            risk_budget = ai_policy.get("risk_budget", {})
            if not isinstance(risk_budget, dict):
                risk_budget = {}
            local_data = ai_policy.get("local_data", {})
            if not isinstance(local_data, dict):
                local_data = {}

            mode = str(ai_policy.get("operating_mode") or snapshot.get("preset_name") or "balanced")
            if mode not in self._mode_buttons:
                mode = "balanced"
            self._mode_buttons[mode].setChecked(True)

            involvement = str(ai_policy.get("ai_involvement_level") or "standard")
            if involvement not in self._involvement_buttons:
                involvement = "standard"
            self._involvement_buttons[involvement].setChecked(True)

            self.sp_total_budget.setValue(max(0, int(risk_budget.get("total_budget_krw") or 0)))
            self.sp_max_entry.setValue(max(0, int(risk_budget.get("max_entry_krw") or 0)))
            self.sp_reserve_cash.setValue(max(0, int(risk_budget.get("reserve_cash_krw") or 0)))
            self.sp_max_positions.setValue(max(1, int(risk_budget.get("max_positions") or 3)))
            self.sp_daily_loss.setValue(max(0, int(risk_budget.get("daily_loss_limit_krw") or 0)))

            self.chk_auto_manage.setChecked(bool(local_data.get("auto_manage", True)))
            self.sp_raw_days.setValue(max(7, int(local_data.get("raw_retention_days") or 30)))
            self.sp_reflection_days.setValue(max(30, int(local_data.get("reflection_retention_days") or 365)))
            self.chk_auto_summary.setChecked(bool(local_data.get("auto_summary_enabled", True)))
            self.chk_block_learning.setChecked(bool(local_data.get("block_unverified_learning", True)))
        except Exception as exc:
            self._emit_policy_tab_proof("apply_snapshot_error", error=type(exc).__name__)
        finally:
            self._loading = False
            self._refresh_mode_cards()
            self._refresh_involvement_cards()
            self._update_summary()

    def load_policy_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        self.apply_policy_snapshot(snapshot)

    def _restore_snapshot(self) -> None:
        try:
            settings = load_settings()
            ui_state = getattr(settings, "ui_state", None)
            if hasattr(ui_state, "model_dump"):
                ui_state = ui_state.model_dump()
            if not isinstance(ui_state, dict):
                ui_state = {}
            snapshot = ui_state.get("ai_policy_snapshot", {})
            if not isinstance(snapshot, dict):
                snapshot = {}
            self.apply_policy_snapshot(snapshot)
        except Exception as exc:
            self._emit_policy_tab_proof("restore_error", error=type(exc).__name__)
            self._mode_buttons.get("balanced").setChecked(True)

    def _update_summary(self) -> None:
        if not self._summary_values:
            return
        mode = self.MODE_LABELS.get(self._current_mode(), "균형형")
        involvement = self.INVOLVEMENT_LABELS.get(self._current_involvement(), "표준")
        values = {
            "mode": f"{mode}\n관여 수준 {involvement}",
            "budget": (
                f"총 운용 한도: {self._fmt_krw(self.sp_total_budget.value())}\n"
                f"1회 진입: {self._fmt_krw(self.sp_max_entry.value())}\n"
                f"예비 현금: {self._fmt_krw(self.sp_reserve_cash.value())}\n"
                f"동시 보유: {self.sp_max_positions.value()}개\n"
                f"일일 손실: {self._fmt_krw(self.sp_daily_loss.value())}"
            ),
            "local": (
                f"자동 관리: {self._yn(self.chk_auto_manage.isChecked())}\n"
                f"상세 보관: {self.sp_raw_days.value()}일\n"
                f"복기 보관: {self.sp_reflection_days.value()}일\n"
                f"자동 요약: {self._yn(self.chk_auto_summary.isChecked())}\n"
                f"검증 전 차단: {self._yn(self.chk_block_learning.isChecked())}"
            ),
            "safe": "Preview 전용\n저장만으로 주문 없음",
        }
        for key, text in values.items():
            label = self._summary_values.get(key)
            if label is not None:
                label.setText(text)

    def _fmt_krw(self, value: int) -> str:
        value = int(value or 0)
        return "미설정" if value <= 0 else f"{value:,}원"

    def _yn(self, enabled: bool) -> str:
        return "사용" if enabled else "미사용"

    def save_policy_snapshot(self) -> bool:
        try:
            snapshot = self._snapshot()
            saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            snapshot["saved_at"] = saved_at
            saved = save_settings_patch(
                {"ui_state": {"ai_policy_snapshot": snapshot}},
                save_source="ai_policy_center_tab",
            )
            ok = saved is not None
            if ok:
                parent = getattr(self, "_parent_window", None)
                if parent is not None:
                    try:
                        parent._settings = saved
                    except Exception:
                        pass
            if self._saved_at_label is not None:
                self._saved_at_label.setText(f"마지막 저장: {saved_at}" if ok else "저장 실패")
            self._emit_policy_tab_proof("snapshot_saved", ok=ok)
            return ok
        except Exception as exc:
            self._emit_policy_tab_proof("snapshot_save_error", error=type(exc).__name__)
            if self._saved_at_label is not None:
                self._saved_at_label.setText("저장 실패")
            return False
