# app/ui/auth_dialogs.py
from __future__ import annotations

import logging
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QPushButton, QMessageBox, QFormLayout,
    QHBoxLayout, QVBoxLayout, QCheckBox,
)

from app.core.auth import has_any_user, create_user, verify_login

log = logging.getLogger(__name__)


# --------- Auth dialogs ---------
class CreateAccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("계정 생성")
        self.email = QLineEdit()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)

        frm = QFormLayout()
        frm.addRow("이메일", self.email)
        frm.addRow("비밀번호", self.pw)

        btn_ok = QPushButton("생성")
        btn_cancel = QPushButton("취소")
        btn_ok.clicked.connect(self._on_create)
        btn_cancel.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        lay = QVBoxLayout(self)
        lay.addLayout(frm)
        lay.addLayout(btns)

    def _on_create(self):
        try:
            create_user(self.email.text(), self.pw.text())
            QMessageBox.information(self, "완료", "계정이 생성되었습니다.")
            self.accept()
        except Exception:
            log.exception("[AUTH] create_user failed")
            QMessageBox.warning(self, "실패", "계정 생성에 실패했습니다.")


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로그인")

        self.email = QLineEdit()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        
        # 아이디 저장 체크박스
        self.cb_remember = QCheckBox("아이디 저장")

        frm = QFormLayout()
        frm.addRow("이메일", self.email)
        frm.addRow("비밀번호", self.pw)
        frm.addRow("", self.cb_remember)

        btn_ok = QPushButton("로그인")
        btn_create = QPushButton("계정 생성")
        btn_cancel = QPushButton("취소")

        btn_ok.clicked.connect(self._on_login)
        btn_create.clicked.connect(self._on_create)
        btn_cancel.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_create)
        btns.addWidget(btn_cancel)

        lay = QVBoxLayout(self)
        lay.addLayout(frm)
        lay.addLayout(btns)
        
        # ✅ 로그인 창 너비 조정 (기본 크기 유지)
        self.setMinimumWidth(300)
        self.adjustSize()  # 레이아웃에 맞게 크기 조정
        
        # 저장된 아이디 로드
        self._load_saved_id()

    def _load_saved_id(self):
        """저장된 아이디가 있으면 자동 입력"""
        try:
            from app.utils.prefs import load_settings
            settings = load_settings()
            ui = getattr(settings, 'ui', None)
            if ui and hasattr(ui, 'saved_id') and ui.saved_id:
                self.email.setText(ui.saved_id)
                self.cb_remember.setChecked(True)
                # 아이디가 이미 채워져 있으면 비밀번호 필드에 포커스 이동
                self.pw.setFocus()
        except Exception:
            pass

    def _save_id_if_checked(self):
        """아이디 저장 체크 시 아이디 저장"""
        try:
            from app.utils.prefs import load_settings, save_settings
            settings = load_settings()
            
            if not hasattr(settings, 'ui'):
                settings.ui = {}
            
            if self.cb_remember.isChecked():
                settings.ui.saved_id = self.email.text().strip()
            else:
                settings.ui.saved_id = ""
            
            save_settings(settings)
        except Exception:
            pass

    def _on_create(self):
        # 계정이 없으면 생성 유도
        if not has_any_user():
            dlg = CreateAccountDialog(self)
            dlg.exec()
            return
        QMessageBox.information(self, "안내", "계정이 이미 존재합니다. 로그인 해주세요.")

    def _on_login(self):
        if verify_login(self.email.text(), self.pw.text()):
            # 아이디 저장 처리
            self._save_id_if_checked()
            self.accept()
            return
        QMessageBox.warning(self, "실패", "이메일 또는 비밀번호가 올바르지 않습니다.")
