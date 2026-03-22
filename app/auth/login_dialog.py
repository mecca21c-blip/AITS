from __future__ import annotations
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Qt


class LoginDialog(QDialog):
    """
    프로그램 자체 로그인/계정 관리를 위한 간단한 로그인 다이얼로그.

    - 아이디(이메일 형식 추천) 입력
    - '아이디 저장', '자동로그인' 체크박스
    - 확인/취소 버튼

    주의:
      * 이 다이얼로그는 생성만 해둔 상태이며,
        실제 표시/동작은 app_gui 등에서 명시적으로 연결해야 한다.
      * 업비트 API 키와는 별개인 '프로그램 계정' 개념이다.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        initial_id: str = "",
        remember_id: bool = False,
        auto_login: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("로그인")
        self.setModal(True)
        self._result: Dict[str, Any] | None = None

        # ----- 위젯 구성 -----
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # 안내 문구
        lbl_info = QLabel("프로그램에서 사용할 로그인 계정을 입력하세요.\n"
                          "이 계정은 업비트 키와는 별개로, 설정/전략/최근 세션을 구분하는 용도로 사용됩니다.")
        lbl_info.setWordWrap(True)
        main.addWidget(lbl_info)

        # 아이디 입력
        row_id = QHBoxLayout()
        lbl_id = QLabel("아이디(이메일):")
        self.edit_id = QLineEdit()
        self.edit_id.setPlaceholderText("예: user@example.com")
        if initial_id:
            self.edit_id.setText(initial_id)

        row_id.addWidget(lbl_id)
        row_id.addWidget(self.edit_id)
        main.addLayout(row_id)

        # 체크박스: 아이디 저장 / 자동로그인
        self.chk_remember = QCheckBox("아이디 저장")
        self.chk_auto = QCheckBox("자동로그인")

        self.chk_remember.setChecked(bool(remember_id))
        self.chk_auto.setChecked(bool(auto_login))

        main.addWidget(self.chk_remember)
        main.addWidget(self.chk_auto)

        # 버튼 영역
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_ok = QPushButton("확인")
        btn_cancel = QPushButton("취소")

        btn_ok.clicked.connect(self._on_accept)
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)

        main.addLayout(btn_row)

        # 엔터키로 확인, ESC로 닫기
        self.edit_id.returnPressed.connect(self._on_accept)

        # 크기/플래그
        self.setMinimumWidth(380)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

    # ------------------------------------------------------------------ #
    # 내부 핸들러
    # ------------------------------------------------------------------ #
    def _on_accept(self) -> None:
        user_id = self.edit_id.text().strip()

        # ✅ LoginDialog는 '저장'을 하지 않는다.
        # - settings / prefs / disk I/O 금지
        # - MainWindow(Owner)가 결과(dict)를 받아 patch 저장을 결정한다.

        if not user_id:
            # 아이디가 비어 있으면 간단 안내만 하고 닫지 않는다.
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "입력 필요",
                "아이디(이메일)를 입력해 주세요.",
            )
            return

        # ✅ intent payload (저장 아님)
        # - user_id: 로그인 식별자
        # - remember_id / auto_login: UI 의사만 전달
        self._result = {
            "user_id": user_id,
            "remember_id": bool(self.chk_remember.isChecked()),
            "auto_login": bool(self.chk_auto.isChecked()),
        }

        self.accept()

    # ------------------------------------------------------------------ #
    # 외부에서 결과를 가져가는 헬퍼
    # ------------------------------------------------------------------ #
    def get_result(self) -> Optional[Dict[str, Any]]:
        """
        사용자가 '확인'으로 닫은 경우:
            {"user_id": str, "remember_id": bool, "auto_login": bool}
        취소/닫기 등:
            None
        """
        return self._result


def run_login_dialog(
    parent: Optional[QWidget] = None,
    *,
    initial_id: str = "",
    remember_id: bool = False,
    auto_login: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    ✅ LoginDialog 실행 헬퍼 (저장 금지 계약)
    - 이 함수는 UI를 띄우고 '의사(intent)'만 반환한다.
    - settings 저장/로드/patch는 반드시 MainWindow(Owner)에서 수행해야 한다.
    """

    """
    간단 실행 헬퍼:
      result = run_login_dialog(...)
    형태로 호출하면 QDialog를 띄우고, 닫힌 뒤 결과 dict 또는 None을 반환한다.

    이 함수 자체를 사용하지 않고, LoginDialog를 직접 생성/exec_ 해도 무방하다.
    """
    dlg = LoginDialog(
        parent,
        initial_id=initial_id,
        remember_id=remember_id,
        auto_login=auto_login,
    )
    ok = dlg.exec()
    if ok == QDialog.Accepted:
        return dlg.get_result()
    return None
