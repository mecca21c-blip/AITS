from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MethodType

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)


class AIReviewSnapshotWorker(QThread):
    result_ready = Signal(dict)

    def run(self):
        try:
            from app.services.ai_review_status_snapshot import AITSAIReviewStatusSnapshot
            value = AITSAIReviewStatusSnapshot().build()
        except Exception as exc:
            value = {"snapshot_ready": False, "error": type(exc).__name__}
        self.result_ready.emit(value)


class AIReviewGenerationWorker(QThread):
    result_ready = Signal(dict)

    def run(self):
        try:
            from app.services.ai_review_engine import AITSAIReviewEngine
            from app.services.learning_journal_engine import AITSLearningJournalEngine

            review_result = AITSAIReviewEngine().build_reviews(persist=True)
            journal_result = AITSLearningJournalEngine().build(
                review_result["records"], persist=True
            )
            from app.services.local_engine_review_learning_bridge import AITSLocalEngineReviewLearningBridge
            bridge_result = AITSLocalEngineReviewLearningBridge().build(
                review_result["records"], persist=True
            )
            value = {
                "completed": True,
                "review_count": len(review_result["records"]),
                "journal_count": len(journal_result["entries"]),
                "review_learning_eligible_count": int(
                    (bridge_result.get("summary") or {}).get("review_learning_eligible_count") or 0
                ),
            }
        except Exception as exc:
            value = {"completed": False, "error": type(exc).__name__}
        self.result_ready.emit(value)


class AIReviewBackupWorker(QThread):
    result_ready = Signal(dict)

    def run(self):
        try:
            from app.services.ai_review_status_snapshot import AITSAIReviewStatusSnapshot
            value = AITSAIReviewStatusSnapshot().backup_derived()
        except Exception as exc:
            value = {"completed": False, "error": type(exc).__name__}
        self.result_ready.emit(value)


def _runtime_active(window) -> bool:
    return bool(
        getattr(window, "_strategy_running", False)
        or getattr(window, "_aits_runtime_contract_active", False)
    )


def _local_time(value: object) -> str:
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return "시간 확인 필요"


def _set_table_headers(table: QTableWidget, labels: list[str]) -> None:
    table.setHorizontalHeaderLabels(labels)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    header = table.horizontalHeader()
    for column in range(len(labels) - 1):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(len(labels) - 1, QHeaderView.ResizeMode.Stretch)


def _refresh_async(window) -> None:
    if bool(getattr(window, "_ai_review_refresh_inflight", False)):
        return
    window._ai_review_refresh_inflight = True
    worker = AIReviewSnapshotWorker(window)
    window._ai_review_snapshot_worker = worker
    worker.result_ready.connect(lambda value: _apply_snapshot(window, value))
    worker.finished.connect(lambda: setattr(window, "_ai_review_refresh_inflight", False))
    worker.start()


def _apply_snapshot(window, snapshot: dict) -> None:
    if snapshot.get("error"):
        window.lbl_ai_review_cards.setText(
            f"복기 상태를 불러오지 못했습니다. · {snapshot.get('error')}"
        )
        return
    window._ai_review_snapshot = snapshot
    cards = dict(snapshot.get("review_summary_cards") or {})
    window.lbl_ai_review_cards.setText(
        "  ·  ".join(f"{name} {int(value):,}건" for name, value in cards.items())
    )
    reviews = list(snapshot.get("reviews") or [])
    symbols = sorted({str(row.get("symbol") or "") for row in reviews if row.get("symbol")})
    current_symbol = window.cmb_ai_review_symbol.currentText()
    window.cmb_ai_review_symbol.blockSignals(True)
    window.cmb_ai_review_symbol.clear()
    window.cmb_ai_review_symbol.addItem("전체 종목")
    window.cmb_ai_review_symbol.addItems(symbols)
    if current_symbol:
        index = window.cmb_ai_review_symbol.findText(current_symbol)
        if index >= 0:
            window.cmb_ai_review_symbol.setCurrentIndex(index)
    window.cmb_ai_review_symbol.blockSignals(False)
    _apply_review_filters(window)

    journal = list(snapshot.get("journal_entries") or [])
    window.tbl_ai_journal.setRowCount(len(journal))
    for row_no, row in enumerate(journal):
        values = [
            _local_time(row.get("created_at")), row.get("title_ko") or "학습 기록",
            row.get("summary_ko") or "", ", ".join(row.get("affected_tasks") or []) or "전체",
            "확인 필요" if row.get("user_attention_required") else "기록",
        ]
        for column, value in enumerate(values):
            window.tbl_ai_journal.setItem(row_no, column, QTableWidgetItem(str(value)))
    window.tbl_ai_journal.scrollToTop()

    patterns = list(snapshot.get("patterns") or [])
    success = [row for row in patterns if row.get("pattern_kind") == "success"]
    failure = [row for row in patterns if row.get("pattern_kind") == "failure"]
    pattern_lines = [
        "반복 성공 패턴 · " + (", ".join(f"{row.get('title_ko')} {row.get('count')}건" for row in success[:3]) or "아직 충분한 반복 표본이 없습니다."),
        "반복 실패 패턴 · " + (", ".join(f"{row.get('title_ko')} {row.get('count')}건" for row in failure[:3]) or "아직 충분한 반복 표본이 없습니다."),
    ]
    window.lbl_ai_journal_patterns.setText("\n".join(pattern_lines))

    suggestions = list(snapshot.get("policy_suggestions") or [])
    window._ai_policy_suggestions = suggestions
    window.tbl_ai_policy_suggestions.setRowCount(len(suggestions))
    for row_no, row in enumerate(suggestions):
        values = [
            row.get("title_ko") or "정책 개선 제안",
            row.get("status_text") or "검토 대기",
            row.get("evidence_count") or 0,
            row.get("expected_effect_ko") or "검증 후 확인",
        ]
        for column, value in enumerate(values):
            window.tbl_ai_policy_suggestions.setItem(row_no, column, QTableWidgetItem(str(value)))
    window.tbl_ai_policy_suggestions.scrollToTop()
    window.lbl_ai_journal_summary.setText(
        f"학습 일지 {snapshot.get('journal_entry_count', 0):,}건 · "
        f"반복 성공 {snapshot.get('repeated_success_pattern_count', 0):,}개 · "
        f"반복 실패 {snapshot.get('repeated_failure_pattern_count', 0):,}개 · "
        f"정책 제안 {snapshot.get('policy_suggestion_count', 0):,}개\n"
        f"Lv2 보조 판단자 준비 · "
        f"{'기준 충족·사용자 승인 대기' if (snapshot.get('level2_summary') or {}).get('eligible') else '학습 기준 보강 중'} · "
        f"준비된 기능 {len((snapshot.get('level2_summary') or {}).get('eligible_tasks') or [])}개"
    )


def _apply_review_filters(window) -> None:
    snapshot = getattr(window, "_ai_review_snapshot", {}) or {}
    rows = list(snapshot.get("reviews") or [])
    symbol = window.cmb_ai_review_symbol.currentText()
    action = window.cmb_ai_review_action.currentData()
    status = window.cmb_ai_review_status.currentData()
    decision_quality = window.cmb_ai_review_decision_quality.currentData()
    result_quality = window.cmb_ai_review_result_quality.currentData()
    period_days = {1: 7, 2: 30}.get(window.cmb_ai_review_period.currentIndex())
    filtered = []
    for row in rows:
        if period_days:
            try:
                created = datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created < datetime.now(timezone.utc) - timedelta(days=period_days):
                    continue
            except (ValueError, TypeError, OSError):
                continue
        if symbol and symbol != "전체 종목" and row.get("symbol") != symbol:
            continue
        if action and row.get("action") != action:
            continue
        if status and row.get("status") != status:
            continue
        if decision_quality and row.get("decision_quality") != decision_quality:
            continue
        if result_quality and row.get("result_quality") != result_quality:
            continue
        filtered.append(row)
    window._ai_review_filtered_rows = filtered
    window.tbl_ai_reviews.setRowCount(len(filtered))
    for row_no, row in enumerate(filtered):
        values = [
            _local_time(row.get("created_at")), row.get("symbol") or "전체",
            row.get("action_text") or "확인 필요", row.get("result_quality_text") or "확인 필요",
            row.get("review_summary_ko") or "복기 준비 중", row.get("status_text") or "확인 필요",
        ]
        for column, value in enumerate(values):
            window.tbl_ai_reviews.setItem(row_no, column, QTableWidgetItem(str(value)))
    window.tbl_ai_reviews.scrollToTop()
    if filtered:
        window.tbl_ai_reviews.selectRow(0)
        _show_review_detail(window, 0)
    else:
        window.lbl_ai_review_detail.setText("선택한 조건에 맞는 복기가 없습니다.")


def _show_review_detail(window, row_no: int) -> None:
    rows = list(getattr(window, "_ai_review_filtered_rows", []) or [])
    if row_no < 0 or row_no >= len(rows):
        return
    row = rows[row_no]
    copilot = dict(row.get("copilot_decision") or {})
    action_text = {
        "wait": "대기", "hold": "보유", "buy": "매수", "add": "추가 매수",
        "sell": "매도", "reduce": "축소", "take_profit": "익절",
        "stop_loss": "손절", "rotate": "교체",
    }.get(str(copilot.get("action_candidate") or "").lower(), "기록 없음")
    copilot_text = (
        "LOCAL_ENGINE 보조 판단\n"
        f"후보 판단: {action_text} · "
        f"외부 AI 확인: {'필요' if copilot.get('teacher_confirmation_required') else '기록 없음'}\n"
        f"외부 AI 확인 경로 반영: {'사용됨' if row.get('copilot_routing_used') else '사용 안 함'} · "
        f"현재 기능 Level: {int(row.get('task_capability_level') or 0)}\n"
        f"학습 활용: {'가능' if row.get('review_learning_eligible') else '제외'} · "
        f"복기 신뢰 등급: {row.get('review_reliability_grade') or '확인 필요'}\n\n"
    )
    limitations = row.get("review_limitations") or []
    limitation_text = " · ".join("추가 결과 필요" for _ in limitations) if limitations else "확인된 자료 범위 내 평가"
    window.lbl_ai_review_detail.setText(
        copilot_text +
        f"당시 판단\n{row.get('decision_summary_ko') or '기록 확인 필요'}\n\n"
        f"실제 결과\n{row.get('result_summary_ko') or '결과 대기'}\n\n"
        f"판단 평가\n판단 품질 {row.get('decision_quality_text')} · 결과 품질 {row.get('result_quality_text')}\n"
        f"{row.get('review_summary_ko') or ''}\n\n"
        f"잘한 점\n{row.get('what_went_well_ko') or '확인 중'}\n\n"
        f"아쉬운 점\n{row.get('what_went_wrong_ko') or '확인 중'}\n\n"
        f"다음 학습\n{row.get('lesson_ko') or '추가 자료가 필요합니다.'}\n\n"
        f"복기 한계\n{limitation_text}"
    )


def _run_generation(window) -> None:
    if _runtime_active(window):
        QMessageBox.warning(window, "복기 업데이트", "실시간 감시 중에는 전체 복기를 생성할 수 없습니다.")
        return
    if bool(getattr(window, "_ai_review_generation_inflight", False)):
        return
    if QMessageBox.question(
        window, "복기 업데이트",
        "원본 판단과 결과는 수정하지 않고 파생 복기·학습 일지만 다시 만듭니다. 계속할까요?",
    ) != QMessageBox.StandardButton.Yes:
        return
    window._ai_review_generation_inflight = True
    window.btn_ai_review_rebuild.setEnabled(False)
    worker = AIReviewGenerationWorker(window)
    window._ai_review_generation_worker = worker
    worker.result_ready.connect(
        lambda value: QMessageBox.information(
            window, "복기 업데이트",
            f"복기 {value.get('review_count', 0):,}건과 학습 일지 {value.get('journal_count', 0):,}건을 갱신했습니다."
            if value.get("completed") else f"복기를 갱신하지 못했습니다. · {value.get('error', '확인 필요')}",
        )
    )
    worker.finished.connect(
        lambda: (
            setattr(window, "_ai_review_generation_inflight", False),
            window.btn_ai_review_rebuild.setEnabled(not _runtime_active(window)),
            _refresh_async(window),
        )
    )
    worker.start()


def _backup_derived(window) -> None:
    if bool(getattr(window, "_ai_review_backup_inflight", False)):
        return
    if QMessageBox.question(
        window, "복기·일지 백업",
        "원본 데이터는 건드리지 않고 현재 복기·학습 일지 파생 파일을 백업할까요?",
    ) != QMessageBox.StandardButton.Yes:
        return
    window._ai_review_backup_inflight = True
    worker = AIReviewBackupWorker(window)
    window._ai_review_backup_worker = worker
    worker.result_ready.connect(lambda value: QMessageBox.information(
        window, "복기·일지 백업",
        f"백업을 완료했습니다.\n{value.get('backup_path', '')}"
        if value.get("completed") else f"백업하지 못했습니다. · {value.get('error', '확인 필요')}",
    ))
    worker.finished.connect(lambda: setattr(window, "_ai_review_backup_inflight", False))
    worker.start()


def _policy_action(window, action: str) -> None:
    row_no = window.tbl_ai_policy_suggestions.currentRow()
    rows = list(getattr(window, "_ai_policy_suggestions", []) or [])
    if row_no < 0 or row_no >= len(rows):
        QMessageBox.information(window, "정책 개선 제안", "먼저 정책 제안을 선택하세요.")
        return
    suggestion = rows[row_no]
    if action == "detail":
        QMessageBox.information(
            window, "정책 개선 제안",
            f"{suggestion.get('title_ko')}\n\n{suggestion.get('description_ko')}\n\n"
            f"기대 효과\n{suggestion.get('expected_effect_ko')}\n\n주의 사항\n{suggestion.get('risk_ko')}\n\n"
            "승인해도 즉시 적용되지 않으며 검증 단계에서 멈춥니다.",
        )
        return
    action_names = {"approve": "검증 승인", "hold": "보류", "reject": "거절"}
    if QMessageBox.question(
        window, "정책 개선 제안",
        f"'{suggestion.get('title_ko')}' 제안을 {action_names[action]}하시겠습니까?\n즉시 runtime 정책에 적용되지 않습니다.",
    ) != QMessageBox.StandardButton.Yes:
        return
    from app.services.learning_journal_engine import AITSLearningJournalEngine
    result = AITSLearningJournalEngine().review_policy_suggestion(
        str(suggestion.get("suggestion_id") or ""), action
    )
    QMessageBox.information(
        window, "정책 개선 제안",
        "검토 상태를 저장했습니다. 실제 정책에는 적용되지 않았습니다."
        if result.get("updated") else "상태를 저장하지 못했습니다.",
    )
    _refresh_async(window)


def _build_dialog(window) -> QDialog:
    dialog = QDialog(window)
    dialog.setObjectName("ai_review_learning_journal_dialog")
    dialog.setWindowTitle("AI 복기·학습 일지")
    dialog.resize(1180, 780)
    root = QVBoxLayout(dialog)
    header = QHBoxLayout()
    title = QLabel("AI 복기·학습 일지")
    title.setStyleSheet("font-size:18px; font-weight:900;")
    window.btn_ai_review_rebuild = QPushButton("복기 업데이트")
    window.btn_ai_review_rebuild.setEnabled(not _runtime_active(window))
    window.btn_ai_review_rebuild.clicked.connect(lambda: _run_generation(window))
    refresh = QPushButton("상태 새로고침")
    refresh.clicked.connect(lambda: _refresh_async(window))
    header.addWidget(title, 1)
    header.addWidget(window.btn_ai_review_rebuild)
    header.addWidget(refresh)
    root.addLayout(header)
    tabs = QTabWidget()
    tabs.setObjectName("ai_review_learning_journal_tabs")
    root.addWidget(tabs, 1)

    review_tab = QWidget()
    review_layout = QVBoxLayout(review_tab)
    window.lbl_ai_review_cards = QLabel("복기 요약을 불러오는 중입니다.")
    window.lbl_ai_review_cards.setObjectName("ai_review_summary_cards")
    window.lbl_ai_review_cards.setWordWrap(True)
    review_layout.addWidget(window.lbl_ai_review_cards)
    filters = QHBoxLayout()
    window.cmb_ai_review_period = QComboBox()
    window.cmb_ai_review_period.addItems(["전체 기간", "최근 7일", "최근 30일"])
    window.cmb_ai_review_symbol = QComboBox()
    window.cmb_ai_review_action = QComboBox()
    window.cmb_ai_review_status = QComboBox()
    window.cmb_ai_review_decision_quality = QComboBox()
    window.cmb_ai_review_result_quality = QComboBox()
    for combo, values in (
        (window.cmb_ai_review_action, [("전체 판단", None), ("대기", "wait"), ("보유", "hold"), ("매수", "buy"), ("매도", "sell"), ("익절", "take_profit")]),
        (window.cmb_ai_review_status, [("전체 상태", None), ("결과 대기", "pending"), ("5분 결과", "partial_5m"), ("15분 결과", "partial_15m"), ("1시간 결과", "partial_1h"), ("복기 완료", "final")]),
        (window.cmb_ai_review_decision_quality, [("모든 판단 품질", None), ("좋음", "good"), ("타당", "acceptable"), ("개선 필요", "weak"), ("취약", "poor")]),
        (window.cmb_ai_review_result_quality, [("모든 결과 품질", None), ("긍정", "positive"), ("중립", "neutral"), ("부정", "negative"), ("확인 불가", "unavailable")]),
    ):
        for label, data in values:
            combo.addItem(label, data)
    for combo in (
        window.cmb_ai_review_period, window.cmb_ai_review_symbol,
        window.cmb_ai_review_action, window.cmb_ai_review_status,
        window.cmb_ai_review_decision_quality, window.cmb_ai_review_result_quality,
    ):
        combo.currentIndexChanged.connect(lambda _index: _apply_review_filters(window))
        filters.addWidget(combo)
    review_layout.addLayout(filters)
    window.tbl_ai_reviews = QTableWidget(0, 6)
    window.tbl_ai_reviews.setObjectName("ai_review_list")
    _set_table_headers(window.tbl_ai_reviews, ["시각", "종목·범위", "당시 판단", "실제 결과", "복기 결론", "상태"])
    window.tbl_ai_reviews.itemSelectionChanged.connect(
        lambda: _show_review_detail(window, window.tbl_ai_reviews.currentRow())
    )
    review_layout.addWidget(window.tbl_ai_reviews, 2)
    window.lbl_ai_review_detail = QLabel("복기를 선택하면 상세 내용을 표시합니다.")
    window.lbl_ai_review_detail.setObjectName("ai_review_detail")
    window.lbl_ai_review_detail.setWordWrap(True)
    window.lbl_ai_review_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    review_layout.addWidget(window.lbl_ai_review_detail, 1)
    tabs.addTab(review_tab, "AI 복기")

    journal_tab = QWidget()
    journal_layout = QVBoxLayout(journal_tab)
    window.lbl_ai_journal_summary = QLabel("학습 일지 요약을 불러오는 중입니다.")
    window.lbl_ai_journal_summary.setObjectName("learning_journal_summary")
    window.lbl_ai_journal_summary.setWordWrap(True)
    journal_layout.addWidget(window.lbl_ai_journal_summary)
    backup_row = QHBoxLayout()
    backup_row.addStretch(1)
    window.btn_ai_review_backup = QPushButton("복기·일지 백업")
    window.btn_ai_review_backup.clicked.connect(lambda: _backup_derived(window))
    backup_row.addWidget(window.btn_ai_review_backup)
    journal_layout.addLayout(backup_row)
    window.lbl_ai_journal_patterns = QLabel("반복 패턴을 확인하는 중입니다.")
    window.lbl_ai_journal_patterns.setWordWrap(True)
    journal_layout.addWidget(window.lbl_ai_journal_patterns)
    window.tbl_ai_journal = QTableWidget(0, 5)
    window.tbl_ai_journal.setObjectName("learning_journal_timeline")
    _set_table_headers(window.tbl_ai_journal, ["날짜", "학습 기록", "요약", "영향 기능", "사용자 확인"])
    journal_layout.addWidget(window.tbl_ai_journal, 2)
    policy_title = QLabel("정책 개선 제안 · 승인해도 즉시 적용되지 않고 검증 단계에서 멈춥니다.")
    policy_title.setWordWrap(True)
    journal_layout.addWidget(policy_title)
    window.tbl_ai_policy_suggestions = QTableWidget(0, 4)
    window.tbl_ai_policy_suggestions.setObjectName("ai_policy_suggestion_list")
    _set_table_headers(window.tbl_ai_policy_suggestions, ["제안", "상태", "근거 수", "기대 효과"])
    journal_layout.addWidget(window.tbl_ai_policy_suggestions, 1)
    policy_buttons = QHBoxLayout()
    for text, action in (
        ("자세히 보기", "detail"), ("검증 승인", "approve"),
        ("보류", "hold"), ("거절", "reject"),
    ):
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False, value=action: _policy_action(window, value))
        policy_buttons.addWidget(button)
    policy_buttons.addStretch(1)
    journal_layout.addLayout(policy_buttons)
    tabs.addTab(journal_tab, "학습 일지")
    return dialog


def _open_dialog(window) -> None:
    dialog = getattr(window, "_ai_review_learning_journal_dialog", None)
    if dialog is None:
        dialog = _build_dialog(window)
        window._ai_review_learning_journal_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _refresh_async(window)


def install_ai_review_learning_journal_entry(window, layout) -> QPushButton:
    """Single entry point from the existing AI briefing area."""
    window._ai_review_refresh_inflight = False
    window._ai_review_generation_inflight = False
    window._ai_review_backup_inflight = False
    window._open_ai_review_learning_journal = MethodType(lambda self: _open_dialog(self), window)
    button = QPushButton("AI 복기·학습 일지")
    button.setObjectName("open_ai_review_learning_journal")
    button.setToolTip("당시 판단과 실제 결과, 반복 학습 패턴과 정책 개선 제안을 확인합니다.")
    button.clicked.connect(window._open_ai_review_learning_journal)
    layout.addWidget(button)
    return button
