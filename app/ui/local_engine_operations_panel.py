from __future__ import annotations

from pathlib import Path
from types import MethodType

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFormLayout, QFrame, QGridLayout, QHeaderView,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.services.local_engine_user_view_model import human_blocker, human_event, local_time


class LocalEngineSnapshotWorker(QThread):
    result_ready = Signal(dict)

    def __init__(self, provider: str, runtime_active: bool, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.runtime_active = runtime_active

    def run(self):
        try:
            from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot
            value = AITSLocalEngineStatusSnapshot().build(
                provider=self.provider, runtime_active=self.runtime_active
            )
        except Exception as exc:
            value = {"snapshot_ready": False, "error": type(exc).__name__}
        self.result_ready.emit(value)


class LocalEngineMaintenanceWorker(QThread):
    result_ready = Signal(dict)

    def run(self):
        try:
            from app.services.local_engine_operations import AITSLocalEngineOperations
            value = AITSLocalEngineOperations().request_maintenance_training(
                runtime_active=False, execute=True
            )
        except Exception as exc:
            value = {"maintenance_started": False, "blocker": type(exc).__name__}
        self.result_ready.emit(value)


def _provider(window) -> str:
    try:
        return str(window._selected_ai_decision_provider() or "")
    except Exception:
        return ""


def _runtime_active(window) -> bool:
    return bool(
        getattr(window, "_strategy_running", False)
        or getattr(window, "_aits_runtime_contract_active", False)
    )


def local_provider_button_text(window) -> str:
    snapshot = getattr(window, "_local_engine_status_snapshot", {}) or {}
    if not snapshot:
        try:
            from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot
            snapshot = AITSLocalEngineStatusSnapshot().build(
                provider=_provider(window), runtime_active=_runtime_active(window)
            )
        except Exception:
            return "LOCAL · 상태 확인 필요\n후보 판단 상태 확인 필요"
    view = dict(snapshot.get("user_view") or {})
    level = snapshot.get("effective_level")
    if level is None:
        return "LOCAL · 상태 확인 필요\n후보 판단 상태 확인 필요"
    return f"LOCAL · Lv{int(level)}\n{snapshot.get('level_name')} · {view.get('role_text') or '상태 확인 필요'}"


def _confirm(window, title: str, body: str) -> bool:
    return QMessageBox.question(window, title, body) == QMessageBox.StandardButton.Yes


def _operation(window, action: str) -> None:
    from app.services.local_engine_operations import AITSLocalEngineOperations

    ops = AITSLocalEngineOperations()
    snapshot = getattr(window, "_local_engine_status_snapshot", {}) or {}
    current = int(snapshot.get("effective_level") or 0)
    prompts = {
        "demote": (
            "LOCAL_ENGINE 한 단계 낮추기",
            f"현재 Lv{current}에서 한 단계 낮춥니다. 외부 AI 확인 범위가 늘어나며, 필요하면 승인된 범위에서 다시 시작할 수 있습니다. 계속할까요?",
        ),
        "pause": (
            "LOCAL 판단 권한 일시 중지",
            "LOCAL 후보 판단을 일시 중지하고 외부 AI 전용으로 전환합니다. 계속할까요?",
        ),
        "resume": (
            "LOCAL 판단 권한 재개",
            "이미 승인된 Level 범위까지만 후보 판단을 재개합니다. Level 승격은 발생하지 않습니다. 계속할까요?",
        ),
        "promote": (
            "Level 승격 승인",
            "Level 승격은 LOCAL_ENGINE의 판단 권한을 확대합니다. 평가를 통과한 승격 후보만 승인되며, 근거가 없으면 변경되지 않습니다. 계속할까요?",
        ),
        "reject": (
            "이번 Level 승격 보류",
            "현재 승격 후보를 보류하고 기존 Level과 판단 권한을 유지합니다. 계속할까요?",
        ),
        "champion": (
            "새 모델 적용",
            "동일한 Level에서 현재 모델을 새 모델 후보로 교체합니다. LOCAL_ENGINE Level과 판단 권한은 변하지 않습니다. 계속할까요?",
        ),
        "rollback": (
            "이전 모델로 되돌리기",
            "이전에 정상 사용한 모델로 되돌립니다. Level과 판단 권한은 안전 범위에서 유지됩니다. 계속할까요?",
        ),
        "teacher": (
            "GPT/Gemini로 최신 시장 다시 학습",
            "현재 AI 제공자 설정은 바꾸지 않고 최신 시장 학습 요청만 기록합니다. 계속할까요?",
        ),
    }
    title, body = prompts[action]
    if not _confirm(window, title, body):
        return
    if action == "demote":
        result = ops.request_manual_demotion()
    elif action == "pause":
        result = ops.pause_local_authority()
    elif action == "resume":
        result = ops.resume_local_authority()
    elif action == "promote":
        result = ops.approve_promotion(approved_by="local_user")
    elif action == "reject":
        result = ops.reject_promotion()
    elif action == "champion":
        result = ops.approve_same_level_champion_replacement(approved_by="local_user")
    elif action == "rollback":
        result = ops.rollback_champion()
    else:
        result = ops.request_teacher_sync(provider=_provider(window))
    blocker = str(result.get("blocker") or result.get("promotion_blocker") or "")
    QMessageBox.information(
        window,
        title,
        "요청이 반영되었습니다." if not blocker else f"요청을 적용하지 못했습니다.\n{human_blocker(blocker)}",
    )
    window._refresh_local_engine_operations_async()


def refresh_async(window) -> None:
    if bool(getattr(window, "_local_engine_snapshot_refresh_inflight", False)):
        return
    window._local_engine_snapshot_refresh_inflight = True
    worker = LocalEngineSnapshotWorker(_provider(window), _runtime_active(window), window)
    window._local_engine_snapshot_worker = worker
    worker.result_ready.connect(lambda value: _apply_snapshot(window, value))
    worker.finished.connect(
        lambda: setattr(window, "_local_engine_snapshot_refresh_inflight", False)
    )
    worker.start()


def _metric_delta(metrics: dict, key: str, lower_is_better: bool = False) -> str:
    values = dict(metrics.get(key) or {})
    current = values.get("champion")
    proposed = values.get("challenger")
    if current is None or proposed is None:
        return "평가 자료 없음"
    delta = float(proposed) - float(current)
    improved = delta <= 0 if lower_is_better else delta >= 0
    return f"{float(current):.4f} → {float(proposed):.4f} · {'개선' if improved else '확인 필요'}"


def _apply_snapshot(window, snapshot: dict) -> None:
    if snapshot.get("error"):
        window.lbl_local_ops_overview.setText(
            f"LOCAL_ENGINE 상태를 불러오지 못했습니다. · {snapshot['error']}"
        )
        return
    window._local_engine_status_snapshot = snapshot
    view = dict(snapshot.get("user_view") or {})
    window.lbl_local_ops_overview.setText(
        f"{view.get('headline', 'LOCAL_ENGINE 상태 확인 필요')}\n"
        f"{view.get('health_summary', '전체 상태 · 확인 필요')}  |  현재 역할 · {view.get('role_text', '확인 필요')}\n"
        f"{view.get('final_decision_message', '')}\n"
        f"{view.get('health_detail', '')}\n"
        f"현재 사용 모델 · {view.get('current_model_text', '확인 필요')}  |  최근 학습 · {view.get('last_training_text', '기록 없음')}"
    )
    if hasattr(window, "btn_engine_local"):
        window.btn_engine_local.setText(local_provider_button_text(window))
        window.btn_engine_local.setToolTip(
            f"판단 권한: {view.get('role_text', '확인 필요')}\n"
            f"전체 상태: {snapshot.get('health_name', '확인 필요')}\n"
            "최종 주문 판단 적용: 아니요\n외부 AI 확인 필요: 예\n"
            f"최근 학습: {view.get('last_training_text', '기록 없음')}"
        )

    rows = list(view.get("simple_tasks") or [])
    window.tbl_local_capability.setRowCount(len(rows))
    for row_no, row in enumerate(rows):
        values = [
            row.get("name"), row.get("status"), row.get("local_role"),
            row.get("external_ai"), row.get("next_condition"),
        ]
        technical = dict(row.get("technical") or {})
        tooltip = (
            f"기술 상세 · Lv{technical.get('level', 0)}\n"
            f"교사 AI 표본: {technical.get('teacher_samples', 0)}\n"
            f"실제 결과 표본: {technical.get('outcome_samples', 0)}\n"
            f"비대기 표본: {technical.get('non_wait_samples', 0)}\n"
            f"지원 판단: {', '.join(technical.get('supported_actions') or []) or '아직 없음'}"
        )
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(tooltip)
            window.tbl_local_capability.setItem(row_no, col, item)
    window.tbl_local_capability.scrollToTop()

    growth = list(view.get("learning_data_summary") or [])
    window.lbl_local_data_status.setText(
        "성장 현황\n" + "  ·  ".join(f"{name} {int(value):,}건" for name, value in growth)
        + "\n최근 학습 이후 새 데이터는 다음 모델 갱신 시 정확히 집계됩니다."
    )

    challenger_visible = bool(view.get("challenger_visible"))
    window.frm_local_new_model.setVisible(challenger_visible)
    window.lbl_local_models_status.setText(
        f"{view.get('challenger_title', '')}\n{view.get('challenger_detail', '')}\n"
        f"{view.get('same_level_explanation', '')}"
    )
    window.btn_local_ops_champion.setVisible(challenger_visible)
    window.btn_local_ops_champion.setEnabled(bool(view.get("challenger_better")))

    recommended = dict(view.get("recommended_action") or {})
    window.lbl_local_recommended_action.setText(
        f"지금 필요한 작업 · {recommended.get('text', '현재 필요한 작업 없음')}"
    )
    window.btn_local_primary_action.setText(recommended.get("button") or "상태 새로고침")
    window.btn_local_primary_action.setProperty("localActionCode", recommended.get("code") or "collect_data")

    teacher = dict(view.get("teacher_sync_summary") or {})
    window.lbl_local_teacher_sync.setText(
        f"{teacher.get('title', '교사 AI · 확인 필요')}\n{teacher.get('detail', '')}"
    )
    maintenance = dict(view.get("maintenance_summary") or {})
    window.lbl_local_maintenance.setText(
        f"{maintenance.get('title', '모델 갱신 · 확인 필요')}\n{maintenance.get('detail', '')}"
    )
    live = bool(snapshot.get("runtime_active"))
    window.btn_local_ops_maintenance.setEnabled(
        not live and not bool(getattr(window, "_local_engine_maintenance_inflight", False))
    )

    metrics = dict(view.get("technical_metrics") or {})
    window.lbl_local_technical_metrics.setText(
        "기술 성능 지표\n"
        f"판단 균형: {_metric_delta(metrics, 'macro_f1')}\n"
        f"균형 정확도: {_metric_delta(metrics, 'balanced_accuracy')}\n"
        f"신뢰도 오차: {_metric_delta(metrics, 'brier_score', lower_is_better=True)}"
    )

    promotion_visible = bool(view.get("promotion_visible"))
    window.frm_local_promotion.setVisible(promotion_visible)
    window.btn_local_ops_approve.setVisible(promotion_visible)
    window.btn_local_ops_reject.setVisible(promotion_visible)
    window.btn_local_ops_rollback.setVisible(bool(view.get("rollback_visible")))

    files = list(view.get("friendly_state_files") or [])
    window.tbl_local_state_files.setRowCount(len(files))
    for row_no, row in enumerate(files):
        values = [
            row.get("friendly_name"), row.get("status"), row.get("local_modified_at"),
            row.get("record_count") if row.get("record_count") is not None else "요약 준비 중",
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(
                f"원본 이름: {row.get('name')}\n구분: {row.get('kind')}\n크기: {row.get('size_bytes', 0):,} bytes"
            )
            window.tbl_local_state_files.setItem(row_no, col, item)
    window.tbl_local_state_files.scrollToTop()

    from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot
    events = AITSLocalEngineStatusSnapshot.recent_history(limit=8)
    lines = [
        f"{local_time(row.get('timestamp'))} · {human_event(row.get('event'))}"
        for row in reversed(events)
    ]
    window.lbl_local_history.setText(
        "최근 운영 이력\n" + ("\n".join(lines) if lines else "기록이 없습니다.")
    )


def _run_primary_action(window) -> None:
    code = str(window.btn_local_primary_action.property("localActionCode") or "")
    if code == "apply_challenger":
        _operation(window, "champion")
    elif code == "teacher_sync":
        _operation(window, "teacher")
    elif code == "maintenance":
        _maintenance(window)
    else:
        window._refresh_local_engine_operations_async()


def _maintenance(window) -> None:
    if _runtime_active(window):
        QMessageBox.warning(
            window, "모델 갱신", "실시간 감시 중에는 모델 학습을 실행할 수 없습니다."
        )
        return
    if bool(getattr(window, "_local_engine_maintenance_inflight", False)):
        return
    if not _confirm(
        window,
        "새 모델 학습",
        "앱 OFF 상태에서 학습 데이터 정리부터 새 모델 평가까지 실행합니다. 계속할까요?",
    ):
        return
    window._local_engine_maintenance_inflight = True
    window.btn_local_ops_maintenance.setEnabled(False)
    window.lbl_local_maintenance.setText(
        "모델 갱신 · 실행 중\n학습 데이터를 정리하고 새 모델을 만들고 있습니다."
    )
    worker = LocalEngineMaintenanceWorker(window)
    window._local_engine_maintenance_worker = worker
    worker.result_ready.connect(
        lambda result: QMessageBox.information(
            window,
            "새 모델 학습",
            "학습 작업이 완료되었습니다."
            if result.get("maintenance_started")
            else f"학습을 시작하지 못했습니다.\n{human_blocker(result.get('blocker'))}",
        )
    )
    worker.finished.connect(
        lambda: (
            setattr(window, "_local_engine_maintenance_inflight", False),
            window._refresh_local_engine_operations_async(),
        )
    )
    worker.start()


def _state_file_action(window, action: str) -> None:
    from app.services.local_engine_operations import AITSLocalEngineOperations

    if action == "folder":
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str((Path("data") / "local_engine").resolve()))
        )
        return
    ops = AITSLocalEngineOperations()
    if action == "regenerate":
        if not _confirm(window, "파생 데이터 다시 만들기", "원본 기록은 유지하고 다시 만들 수 있는 파생 데이터만 갱신 요청합니다. 계속할까요?"):
            return
        result = ops.request_derived_regeneration(runtime_active=_runtime_active(window))
    elif action == "backup":
        if not _confirm(window, "상태 백업", "현재 LOCAL_ENGINE 상태 snapshot을 백업합니다. 계속할까요?"):
            return
        result = ops.backup_state_snapshot()
    else:
        row_no = window.tbl_local_state_files.currentRow()
        files = list(
            (getattr(window, "_local_engine_status_snapshot", {}) or {})
            .get("user_view", {})
            .get("friendly_state_files", [])
        )
        if row_no < 0 or row_no >= len(files):
            QMessageBox.information(window, "손상된 파생 파일 격리", "먼저 데이터 행을 선택하세요.")
            return
        if not _confirm(window, "손상된 파생 파일 격리", "원본 기록은 격리할 수 없습니다. 선택한 파생 파일만 안전하게 격리할까요?"):
            return
        result = ops.quarantine_corrupt_derived(files[row_no].get("path") or "")
    blocker = str(result.get("blocker") or "")
    QMessageBox.information(
        window,
        "데이터·복구 작업",
        "요청이 반영되었습니다." if not blocker else human_blocker(blocker),
    )
    window._refresh_local_engine_operations_async()


def _toggle_advanced(window, checked: bool) -> None:
    window.frm_local_advanced.setVisible(checked)
    window.btn_local_advanced_toggle.setText(
        "상세 관리 접기" if checked else "상세 관리 펼치기"
    )
    if checked:
        window.tbl_local_capability.scrollToTop()
        window.tbl_local_state_files.scrollToTop()


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight: 700; font-size: 14px; margin-top: 6px;")
    return label


def build_local_engine_operations_card(window, build_card):
    window._refresh_local_engine_operations_async = MethodType(refresh_async, window)
    window._local_engine_provider_button_text = MethodType(local_provider_button_text, window)
    window._local_engine_snapshot_refresh_inflight = False
    window._local_engine_maintenance_inflight = False

    card = build_card("4. LOCAL_ENGINE 성장·운영")
    card.setObjectName("local_engine_operations_panel")
    layout = card.layout()
    layout.addWidget(_section_label("LOCAL_ENGINE 한눈에 보기"))
    window.lbl_local_ops_overview = QLabel("LOCAL_ENGINE 상태를 불러오는 중입니다.")
    window.lbl_local_ops_overview.setObjectName("local_engine_overview_ui")
    window.lbl_local_ops_overview.setWordWrap(True)
    layout.addWidget(window.lbl_local_ops_overview)

    layout.addWidget(_section_label("현재 가능한 역할"))
    window.tbl_local_capability = QTableWidget(0, 5)
    window.tbl_local_capability.setObjectName("local_engine_task_capability_matrix")
    window.tbl_local_capability.setHorizontalHeaderLabels(
        ["판단 기능", "현재 상태", "LOCAL 역할", "외부 AI", "다음 성장 조건"]
    )
    window.tbl_local_capability.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    window.tbl_local_capability.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    window.tbl_local_capability.setMaximumHeight(300)
    header = window.tbl_local_capability.horizontalHeader()
    for col in range(4):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    layout.addWidget(window.tbl_local_capability)

    layout.addWidget(_section_label("성장 현황"))
    window.lbl_local_data_status = QLabel("")
    window.lbl_local_data_status.setObjectName("local_engine_data_status")
    window.lbl_local_data_status.setWordWrap(True)
    layout.addWidget(window.lbl_local_data_status)

    window.frm_local_new_model = QFrame()
    window.frm_local_new_model.setObjectName("local_engine_champion_challenger")
    model_layout = QVBoxLayout(window.frm_local_new_model)
    model_layout.setContentsMargins(12, 10, 12, 10)
    model_layout.addWidget(_section_label("새 모델 안내"))
    window.lbl_local_models_status = QLabel("")
    window.lbl_local_models_status.setWordWrap(True)
    model_layout.addWidget(window.lbl_local_models_status)
    window.btn_local_ops_champion = QPushButton("새 모델 적용")
    window.btn_local_ops_champion.clicked.connect(lambda: _operation(window, "champion"))
    model_layout.addWidget(window.btn_local_ops_champion)
    layout.addWidget(window.frm_local_new_model)

    action_row = QHBoxLayout()
    window.lbl_local_recommended_action = QLabel("지금 필요한 작업을 확인하는 중입니다.")
    window.lbl_local_recommended_action.setObjectName("local_engine_single_recommended_action")
    window.lbl_local_recommended_action.setWordWrap(True)
    window.btn_local_primary_action = QPushButton("상태 새로고침")
    window.btn_local_primary_action.setObjectName("local_engine_primary_action")
    window.btn_local_primary_action.clicked.connect(lambda: _run_primary_action(window))
    refresh = QPushButton("상태 새로고침")
    refresh.clicked.connect(window._refresh_local_engine_operations_async)
    action_row.addWidget(window.lbl_local_recommended_action, 1)
    action_row.addWidget(window.btn_local_primary_action)
    action_row.addWidget(refresh)
    layout.addLayout(action_row)

    window.btn_local_advanced_toggle = QPushButton("상세 관리 펼치기")
    window.btn_local_advanced_toggle.setObjectName("local_engine_advanced_toggle")
    window.btn_local_advanced_toggle.setCheckable(True)
    layout.addWidget(window.btn_local_advanced_toggle)
    window.frm_local_advanced = QWidget()
    window.frm_local_advanced.setObjectName("local_engine_advanced_details")
    advanced = QVBoxLayout(window.frm_local_advanced)
    advanced.setContentsMargins(0, 6, 0, 0)
    advanced.setSpacing(8)
    window.btn_local_advanced_toggle.toggled.connect(
        lambda checked: _toggle_advanced(window, checked)
    )

    window.lbl_local_technical_metrics = QLabel("기술 성능 지표를 불러오는 중입니다.")
    window.lbl_local_technical_metrics.setWordWrap(True)
    advanced.addWidget(window.lbl_local_technical_metrics)

    window.lbl_local_teacher_sync = QLabel("교사 AI 연결 상태를 확인하는 중입니다.")
    window.lbl_local_teacher_sync.setObjectName("local_engine_teacher_sync_ui")
    window.lbl_local_teacher_sync.setWordWrap(True)
    teacher_row = QHBoxLayout()
    teacher_row.addWidget(window.lbl_local_teacher_sync, 1)
    teacher_button = QPushButton("GPT/Gemini로 최신 시장 다시 학습")
    teacher_button.clicked.connect(lambda: _operation(window, "teacher"))
    teacher_row.addWidget(teacher_button)
    advanced.addLayout(teacher_row)

    window.lbl_local_maintenance = QLabel("모델 갱신 상태를 확인하는 중입니다.")
    window.lbl_local_maintenance.setObjectName("local_engine_maintenance_status")
    window.lbl_local_maintenance.setWordWrap(True)
    maintenance_row = QHBoxLayout()
    maintenance_row.addWidget(window.lbl_local_maintenance, 1)
    window.btn_local_ops_maintenance = QPushButton("앱이 OFF일 때 새 모델 학습")
    window.btn_local_ops_maintenance.setObjectName("local_engine_maintenance_off_only")
    window.btn_local_ops_maintenance.clicked.connect(lambda: _maintenance(window))
    maintenance_row.addWidget(window.btn_local_ops_maintenance)
    advanced.addLayout(maintenance_row)

    advanced.addWidget(_section_label("Level·판단 권한 관리"))
    authority_row = QGridLayout()
    controls = (
        ("btn_local_ops_demotion", "한 단계 낮추기", "demote", 0, 0),
        ("btn_local_ops_pause", "판단 권한 일시 중지", "pause", 0, 1),
        ("btn_local_ops_resume", "판단 권한 재개", "resume", 0, 2),
        ("btn_local_ops_rollback", "이전 모델로 되돌리기", "rollback", 1, 0),
    )
    for attr, text, action, row, col in controls:
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False, name=action: _operation(window, name))
        setattr(window, attr, button)
        authority_row.addWidget(button, row, col)
    advanced.addLayout(authority_row)

    window.frm_local_promotion = QFrame()
    promotion_layout = QVBoxLayout(window.frm_local_promotion)
    promotion_layout.addWidget(QLabel("Level 승격은 판단 권한을 확대하며 사용자 승인이 필요합니다."))
    promotion_buttons = QHBoxLayout()
    window.btn_local_ops_approve = QPushButton("Level 승격 승인")
    window.btn_local_ops_reject = QPushButton("이번 승격 보류")
    window.btn_local_ops_approve.clicked.connect(lambda: _operation(window, "promote"))
    window.btn_local_ops_reject.clicked.connect(lambda: _operation(window, "reject"))
    promotion_buttons.addWidget(window.btn_local_ops_approve)
    promotion_buttons.addWidget(window.btn_local_ops_reject)
    promotion_layout.addLayout(promotion_buttons)
    advanced.addWidget(window.frm_local_promotion)

    advanced.addWidget(_section_label("데이터·복구"))
    window.tbl_local_state_files = QTableWidget(0, 4)
    window.tbl_local_state_files.setObjectName("local_engine_state_file_table")
    window.tbl_local_state_files.setHorizontalHeaderLabels(
        ["데이터 이름", "상태", "마지막 갱신", "기록 수"]
    )
    window.tbl_local_state_files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    window.tbl_local_state_files.setMaximumHeight(250)
    state_header = window.tbl_local_state_files.horizontalHeader()
    state_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in range(1, 4):
        state_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    advanced.addWidget(window.tbl_local_state_files)
    file_actions = QHBoxLayout()
    for text, action in (
        ("데이터 폴더 열기", "folder"),
        ("상태 백업", "backup"),
        ("파생 데이터 다시 만들기", "regenerate"),
        ("손상된 파생 파일 격리", "quarantine"),
    ):
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False, name=action: _state_file_action(window, name))
        file_actions.addWidget(button)
    advanced.addLayout(file_actions)

    window.lbl_local_history = QLabel("최근 운영 이력을 확인하는 중입니다.")
    window.lbl_local_history.setObjectName("local_engine_history_ui")
    window.lbl_local_history.setWordWrap(True)
    advanced.addWidget(window.lbl_local_history)

    window.chk_policy_local_auto_manage = QCheckBox("원본 데이터 보관 정책 사용")
    window.chk_policy_local_auto_summary = QCheckBox("복기용 요약 준비")
    window.chk_policy_local_block_unverified = QCheckBox("검증 전 학습 결과 적용 차단")
    for widget in (
        window.chk_policy_local_auto_manage,
        window.chk_policy_local_auto_summary,
        window.chk_policy_local_block_unverified,
    ):
        widget.setChecked(True)
        widget.stateChanged.connect(window._on_ai_policy_changed)
        advanced.addWidget(widget)
    window.sp_policy_raw_retention_days = QSpinBox()
    window.sp_policy_reflection_retention_days = QSpinBox()
    for spin, value in (
        (window.sp_policy_raw_retention_days, 30),
        (window.sp_policy_reflection_retention_days, 365),
    ):
        spin.setRange(1, 3650)
        spin.setValue(value)
        spin.valueChanged.connect(window._on_ai_policy_changed)
    retention = QFormLayout()
    retention.addRow("원본 보관 기간", window.sp_policy_raw_retention_days)
    retention.addRow("복기 데이터 보관 기간", window.sp_policy_reflection_retention_days)
    advanced.addLayout(retention)
    window.frm_local_advanced.setVisible(False)
    layout.addWidget(window.frm_local_advanced)

    QTimer.singleShot(0, window._refresh_local_engine_operations_async)
    return card


def build_policy_center_operations_card(policy_tab, parent_window):
    """Bind the active AI policy tab to the shared user-centered panel."""

    def _build_card(title: str):
        card = policy_tab._card("aitsPolicyLocalEngineOperationsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        layout.addWidget(policy_tab._section_title(title))
        return card

    card = build_local_engine_operations_card(parent_window, _build_card)
    policy_tab.chk_auto_manage = parent_window.chk_policy_local_auto_manage
    policy_tab.chk_auto_summary = parent_window.chk_policy_local_auto_summary
    policy_tab.chk_block_learning = parent_window.chk_policy_local_block_unverified
    policy_tab.sp_raw_days = parent_window.sp_policy_raw_retention_days
    policy_tab.sp_reflection_days = parent_window.sp_policy_reflection_retention_days
    for widget in (
        policy_tab.chk_auto_manage,
        policy_tab.chk_auto_summary,
        policy_tab.chk_block_learning,
    ):
        widget.stateChanged.connect(policy_tab._on_policy_changed)
    for widget in (policy_tab.sp_raw_days, policy_tab.sp_reflection_days):
        widget.valueChanged.connect(policy_tab._on_policy_changed)
    return card
