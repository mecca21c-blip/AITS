from __future__ import annotations

from types import MethodType
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFormLayout, QHeaderView, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)


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
    return bool(getattr(window, "_strategy_running", False) or getattr(window, "_aits_runtime_contract_active", False))


def local_provider_button_text(window) -> str:
    snapshot = getattr(window, "_local_engine_status_snapshot", {}) or {}
    if not snapshot:
        try:
            from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot
            snapshot = AITSLocalEngineStatusSnapshot().build(provider=_provider(window), runtime_active=_runtime_active(window))
        except Exception:
            return "LOCAL · 상태 확인 필요\n후보 판단 상태 확인 필요"
    level = snapshot.get("effective_level")
    if level is None:
        return "LOCAL · 상태 확인 필요\n후보 판단 상태 확인 필요"
    return f"LOCAL · Lv{int(level)}\n{snapshot.get('level_name')} · {snapshot.get('authority_name')}"


def _confirm(window, title: str, body: str) -> bool:
    return QMessageBox.question(window, title, body) == QMessageBox.StandardButton.Yes


def _human_code(value: object) -> str:
    text = str(value or "")
    labels = {
        "user_approval_required_above_candidate": "후보 판단을 넘는 권한은 사용자 승인이 필요합니다.",
        "candidate_only_evidence": "후보 판단 근거만 확보되었습니다.",
        "non_wait_recall_insufficient": "비대기 판단 재현율이 부족합니다.",
        "portfolio_teacher_labels_missing": "포트폴리오 교사 표본이 부족합니다.",
        "rotation_teacher_labels_missing": "로테이션 교사 표본이 부족합니다.",
        "buy_add_teacher_labels_missing": "매수·추가 교사 표본이 부족합니다.",
        "insufficient_task_evidence": "작업별 근거 데이터가 부족합니다.",
    }
    return labels.get(text, "없음" if not text else "추가 평가가 필요합니다.")


def _operation(window, action: str) -> None:
    from app.services.local_engine_operations import AITSLocalEngineOperations
    ops = AITSLocalEngineOperations()
    snapshot = getattr(window, "_local_engine_status_snapshot", {}) or {}
    current = int(snapshot.get("effective_level") or 0)
    prompts = {
        "demote": ("LOCAL_ENGINE 강등", f"현재 Lv{current}에서 한 단계 강등합니다. 외부 AI 확인 범위가 늘어납니다. 계속할까요?"),
        "pause": ("LOCAL 권한 일시 중지", "LOCAL 후보 권한을 일시 중지하고 외부 AI 전용으로 전환합니다. 계속할까요?"),
        "resume": ("LOCAL 권한 재개", "이미 승인된 Level 범위까지만 LOCAL 후보 권한을 재개합니다. 승격은 발생하지 않습니다."),
        "promote": ("승격 후보 승인", "평가를 통과한 승격 후보를 승인합니다. 승인 근거가 없으면 변경되지 않습니다."),
        "reject": ("승격 후보 거절", "현재 승격 후보를 거절하고 Level을 유지합니다."),
        "champion": ("Challenger 승인", "동일 Level 내에서 Challenger를 Champion으로 교체합니다. 권한 Level은 바뀌지 않습니다."),
        "rollback": ("Champion 롤백", "이전 usable Champion으로 되돌리고 권한을 안전 범위로 유지합니다."),
        "teacher": ("Teacher Sync 요청", "현재 AI Provider 설정은 바꾸지 않고 Teacher Sync 요청만 기록합니다."),
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
    QMessageBox.information(window, title, "요청이 반영되었습니다." if not blocker else f"요청을 적용하지 못했습니다.\n{_human_code(blocker)}")
    window._refresh_local_engine_operations_async()


def refresh_async(window) -> None:
    if bool(getattr(window, "_local_engine_snapshot_refresh_inflight", False)):
        return
    window._local_engine_snapshot_refresh_inflight = True
    worker = LocalEngineSnapshotWorker(_provider(window), _runtime_active(window), window)
    window._local_engine_snapshot_worker = worker
    worker.result_ready.connect(lambda value: _apply_snapshot(window, value))
    worker.finished.connect(lambda: setattr(window, "_local_engine_snapshot_refresh_inflight", False))
    worker.start()


def _apply_snapshot(window, snapshot: dict) -> None:
    if snapshot.get("error"):
        window.lbl_local_ops_overview.setText(f"LOCAL_ENGINE 상태 확인 실패 · {snapshot['error']}")
        return
    window._local_engine_status_snapshot = snapshot
    authority = snapshot.get("authority") or {}
    window.lbl_local_ops_overview.setText(
        f"LOCAL_ENGINE Lv{snapshot.get('effective_level')} · {snapshot.get('level_name')}\n"
        f"Authority · {snapshot.get('authority_name')}  |  Health · {snapshot.get('health_name')}\n"
        f"현재는 후보 판단만 수행하며 최종 판단에는 적용되지 않습니다.\n"
        f"최근 판단 근거 · {_human_code(authority.get('blocker'))}"
    )
    if hasattr(window, "btn_engine_local"):
        window.btn_engine_local.setText(local_provider_button_text(window))
        window.btn_engine_local.setToolTip(
            f"Authority: {snapshot.get('authority_name')}\nHealth: {snapshot.get('health_name')}\n"
            f"최종 판단 가능: 아니요\nGPT/Gemini 확인 필요: 예\n최근 학습: {(snapshot.get('learning') or {}).get('last_training_at') or '기록 없음'}"
        )

    rows = list(snapshot.get("task_rows") or [])
    window.tbl_local_capability.setRowCount(len(rows))
    for row_no, row in enumerate(rows):
        values = [row.get("task_name"), f"Lv{row.get('level')}", row.get("authority"), ", ".join(row.get("supported_actions") or []) or "미지원", row.get("teacher_samples"), row.get("outcome_samples"), row.get("health"), _human_code(row.get("blocker"))]
        for col, value in enumerate(values):
            window.tbl_local_capability.setItem(row_no, col, QTableWidgetItem(str(value)))

    counts = snapshot.get("data_counts") or {}
    count_names = {"candidate_observations": "후보 판단", "outcome_decisions": "Outcome", "curated_records": "정제", "excluded_records": "제외", "feature_records": "Feature", "distillation_records": "교사 학습", "teacher_present": "교사 있음", "teacher_absent": "교사 없음", "calibration_usable": "Calibration 유효", "portfolio_teacher": "포트폴리오 교사"}
    window.lbl_local_data_status.setText("데이터 현황 · " + "  |  ".join(f"{count_names.get(key, '기타')}: {value}" for key, value in counts.items()))
    champion = snapshot.get("champion") or {}
    challenger = snapshot.get("challenger") or {}
    c_metrics = champion.get("metrics") or {}
    n_metrics = challenger.get("metrics") or {}
    window.lbl_local_models_status.setText(
        f"Champion · {champion.get('model_id') or '없음'} · Macro-F1 {c_metrics.get('macro_f1', '-')} · Brier {c_metrics.get('brier_score', '-')}\n"
        f"Challenger · {challenger.get('model_id') or '대기'} · Macro-F1 {n_metrics.get('macro_f1', '-')} · Brier {n_metrics.get('brier_score', '-')}\n"
        "Challenger 교체와 Level 승격은 사용자 승인 전까지 적용되지 않습니다."
    )
    window.lbl_local_teacher_sync.setText(
        f"Teacher Sync · {'필요' if snapshot.get('teacher_sync_required') else '정상'} · 현재 Provider {_provider(window) or '확인 필요'}"
    )
    live = bool(snapshot.get("runtime_active"))
    window.btn_local_ops_maintenance.setEnabled(not live and not bool(getattr(window, "_local_engine_maintenance_inflight", False)))
    window.lbl_local_maintenance.setText("Live ON 중에는 학습을 실행할 수 없습니다." if live else f"Maintenance · {(snapshot.get('learning') or {}).get('status') or 'idle'}")

    files = list(snapshot.get("state_files") or [])
    window.tbl_local_state_files.setRowCount(len(files))
    for row_no, row in enumerate(files):
        values = [row.get("name"), row.get("status"), "유효" if row.get("valid") else "확인 필요", row.get("modified_at"), row.get("size_bytes"), row.get("record_count") if row.get("record_count") is not None else "요약 없음", row.get("kind")]
        for col, value in enumerate(values):
            window.tbl_local_state_files.setItem(row_no, col, QTableWidgetItem(str(value)))
    from app.services.local_engine_status_snapshot import AITSLocalEngineStatusSnapshot
    events = AITSLocalEngineStatusSnapshot.recent_history(limit=8)
    event_names = {"level_initialized": "Level 초기화", "capability_evaluated": "Capability 평가", "automatic_demotion": "자동 강등", "user_demotion": "사용자 강등", "teacher_sync_requested": "Teacher Sync 요청", "promotion_approved": "승격 승인", "promotion_rejected": "승격 거절", "champion_replaced": "Champion 교체", "rollback_completed": "롤백 완료", "authority_resumed": "권한 재개"}
    window.lbl_local_history.setText("최근 운영 이력\n" + "\n".join(f"{row.get('timestamp', '')} · {event_names.get(row.get('event'), '운영 상태 변경')} · Lv{row.get('global_level_before')}→Lv{row.get('global_level_after')}" for row in events[-8:]))


def _maintenance(window) -> None:
    if _runtime_active(window):
        QMessageBox.warning(window, "Maintenance", "Live ON 중에는 학습을 실행할 수 없습니다.")
        return
    if bool(getattr(window, "_local_engine_maintenance_inflight", False)):
        return
    if not _confirm(window, "Maintenance", "앱 OFF 상태에서 curation부터 Challenger 평가까지 실행합니다. 계속할까요?"):
        return
    window._local_engine_maintenance_inflight = True
    window.btn_local_ops_maintenance.setEnabled(False)
    window.lbl_local_maintenance.setText("Maintenance 실행 중")
    worker = LocalEngineMaintenanceWorker(window)
    window._local_engine_maintenance_worker = worker
    worker.result_ready.connect(lambda result: QMessageBox.information(window, "Maintenance", "완료되었습니다." if result.get("maintenance_started") else f"실행되지 않았습니다.\n{result.get('blocker', '')}"))
    worker.finished.connect(lambda: (setattr(window, "_local_engine_maintenance_inflight", False), window._refresh_local_engine_operations_async()))
    worker.start()


def _state_file_action(window, action: str) -> None:
    from app.services.local_engine_operations import AITSLocalEngineOperations
    if action == "folder":
        QDesktopServices.openUrl(QUrl.fromLocalFile(str((Path("data") / "local_engine").resolve())))
        return
    if action == "summary":
        snapshot = getattr(window, "_local_engine_status_snapshot", {}) or {}
        valid = sum(1 for row in snapshot.get("state_files") or [] if row.get("valid"))
        total = len(snapshot.get("state_files") or [])
        QMessageBox.information(window, "상태 파일 요약", f"정상 또는 유효: {valid}/{total}\n원본 파일은 삭제하거나 편집하지 않습니다.")
        return
    ops = AITSLocalEngineOperations()
    if action == "regenerate":
        result = ops.request_derived_regeneration(runtime_active=_runtime_active(window))
    elif action == "backup":
        result = ops.backup_state_snapshot()
    else:
        row_no = window.tbl_local_state_files.currentRow()
        files = list((getattr(window, "_local_engine_status_snapshot", {}) or {}).get("state_files") or [])
        if row_no < 0 or row_no >= len(files):
            QMessageBox.information(window, "파생 파일 격리", "먼저 상태 파일 행을 선택하세요.")
            return
        result = ops.quarantine_corrupt_derived(files[row_no].get("path") or "")
    blocker = str(result.get("blocker") or "")
    QMessageBox.information(window, "상태 파일 작업", "요청이 반영되었습니다." if not blocker else _human_code(blocker))
    window._refresh_local_engine_operations_async()


def build_local_engine_operations_card(window, build_card):
    window._refresh_local_engine_operations_async = MethodType(refresh_async, window)
    window._local_engine_provider_button_text = MethodType(local_provider_button_text, window)
    window._local_engine_snapshot_refresh_inflight = False
    window._local_engine_maintenance_inflight = False

    card = build_card("4. LOCAL_ENGINE 성장·운영")
    card.setObjectName("local_engine_operations_panel")
    layout = card.layout()
    desc = QLabel("LOCAL_ENGINE의 학습·성능·권한을 SSOT에서 읽습니다. 현재는 후보 판단만 수행하며 최종 판단이나 주문에는 적용되지 않습니다.")
    desc.setWordWrap(True)
    layout.addWidget(desc)
    window.lbl_local_ops_overview = QLabel("LOCAL_ENGINE 상태를 불러오는 중입니다.")
    window.lbl_local_ops_overview.setObjectName("local_engine_overview_ui")
    window.lbl_local_ops_overview.setWordWrap(True)
    layout.addWidget(window.lbl_local_ops_overview)

    window.tbl_local_capability = QTableWidget(0, 8)
    window.tbl_local_capability.setObjectName("local_engine_task_capability_matrix")
    window.tbl_local_capability.setHorizontalHeaderLabels(["작업", "Level", "권한", "지원 action", "Teacher", "Outcome", "Health", "Blocker"])
    window.tbl_local_capability.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    window.tbl_local_capability.setMaximumHeight(280)
    window.tbl_local_capability.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    layout.addWidget(window.tbl_local_capability)
    window.lbl_local_data_status = QLabel("")
    window.lbl_local_data_status.setObjectName("local_engine_data_status")
    window.lbl_local_data_status.setWordWrap(True)
    layout.addWidget(window.lbl_local_data_status)
    window.lbl_local_models_status = QLabel("")
    window.lbl_local_models_status.setObjectName("local_engine_champion_challenger")
    window.lbl_local_models_status.setWordWrap(True)
    layout.addWidget(window.lbl_local_models_status)

    controls = QHBoxLayout()
    for attr, text, action in (("btn_local_ops_demotion", "한 단계 강등", "demote"), ("btn_local_ops_pause", "권한 중지", "pause"), ("btn_local_ops_resume", "권한 재개", "resume"), ("btn_local_ops_approve", "승격 승인", "promote"), ("btn_local_ops_reject", "승격 거절", "reject"), ("btn_local_ops_champion", "Challenger 승인", "champion"), ("btn_local_ops_rollback", "롤백", "rollback")):
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False, name=action: _operation(window, name))
        setattr(window, attr, button)
        controls.addWidget(button)
    layout.addLayout(controls)

    teacher = QHBoxLayout()
    window.lbl_local_teacher_sync = QLabel("Teacher Sync 확인 중")
    window.lbl_local_teacher_sync.setObjectName("local_engine_teacher_sync_ui")
    teacher.addWidget(window.lbl_local_teacher_sync, 1)
    teacher_button = QPushButton("Teacher Sync 요청")
    teacher_button.clicked.connect(lambda: _operation(window, "teacher"))
    teacher.addWidget(teacher_button)
    layout.addLayout(teacher)

    maintenance = QHBoxLayout()
    window.lbl_local_maintenance = QLabel("Maintenance 확인 중")
    window.lbl_local_maintenance.setObjectName("local_engine_maintenance_status")
    window.btn_local_ops_maintenance = QPushButton("OFF 상태에서 Maintenance 실행")
    window.btn_local_ops_maintenance.setObjectName("local_engine_maintenance_off_only")
    window.btn_local_ops_maintenance.clicked.connect(lambda: _maintenance(window))
    refresh = QPushButton("전체 상태 새로고침")
    refresh.clicked.connect(window._refresh_local_engine_operations_async)
    maintenance.addWidget(window.lbl_local_maintenance, 1)
    maintenance.addWidget(window.btn_local_ops_maintenance)
    maintenance.addWidget(refresh)
    layout.addLayout(maintenance)

    window.tbl_local_state_files = QTableWidget(0, 7)
    window.tbl_local_state_files.setObjectName("local_engine_state_file_table")
    window.tbl_local_state_files.setHorizontalHeaderLabels(["이름", "상태", "유효", "수정 시각", "크기", "레코드", "구분"])
    window.tbl_local_state_files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    window.tbl_local_state_files.setMaximumHeight(250)
    window.tbl_local_state_files.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    layout.addWidget(window.tbl_local_state_files)
    file_actions = QHBoxLayout()
    for text, action in (("폴더 열기", "folder"), ("상태 요약 보기", "summary"), ("파생 파일 재생성 요청", "regenerate"), ("손상 파생 파일 격리", "quarantine"), ("상태 Snapshot 백업", "backup")):
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False, name=action: _state_file_action(window, name))
        file_actions.addWidget(button)
    layout.addLayout(file_actions)
    window.lbl_local_history = QLabel("최근 운영 이력 확인 중")
    window.lbl_local_history.setObjectName("local_engine_history_ui")
    window.lbl_local_history.setWordWrap(True)
    layout.addWidget(window.lbl_local_history)

    window.chk_policy_local_auto_manage = QCheckBox("원본 데이터 보관 정책 사용")
    window.chk_policy_local_auto_summary = QCheckBox("복기용 요약 준비")
    window.chk_policy_local_block_unverified = QCheckBox("검증 전 학습 결과 적용 차단")
    for widget in (window.chk_policy_local_auto_manage, window.chk_policy_local_auto_summary, window.chk_policy_local_block_unverified):
        widget.setChecked(True)
        widget.stateChanged.connect(window._on_ai_policy_changed)
        layout.addWidget(widget)
    window.sp_policy_raw_retention_days = QSpinBox()
    window.sp_policy_reflection_retention_days = QSpinBox()
    for spin, value in ((window.sp_policy_raw_retention_days, 30), (window.sp_policy_reflection_retention_days, 365)):
        spin.setRange(1, 3650)
        spin.setValue(value)
        spin.valueChanged.connect(window._on_ai_policy_changed)
    retention = QFormLayout()
    retention.addRow("원본 보관 기간", window.sp_policy_raw_retention_days)
    retention.addRow("복기 데이터 보관 기간", window.sp_policy_reflection_retention_days)
    layout.addLayout(retention)
    QTimer.singleShot(0, window._refresh_local_engine_operations_async)
    return card


def build_policy_center_operations_card(policy_tab, parent_window):
    """Bind the active AIPolicyCenterTab to the shared operations panel."""
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
    for widget in (policy_tab.chk_auto_manage, policy_tab.chk_auto_summary, policy_tab.chk_block_learning):
        widget.stateChanged.connect(policy_tab._on_policy_changed)
    for widget in (policy_tab.sp_raw_days, policy_tab.sp_reflection_days):
        widget.valueChanged.connect(policy_tab._on_policy_changed)
    return card
