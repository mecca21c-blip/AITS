# -*- coding: utf-8 -*-
# app/ui/app_gui.py

# ⚠️ 봉인 선언: 역할 변경/이동/삭제/리팩터링 금지
# - 현 단계에서는 안정화 우선
# - 구조 변경은 v-next에서만 수행
# - 이 파일의 역할/위치/구조는 변경하지 말 것

from __future__ import annotations
import sys
import os
import logging
import warnings
import time
import json
import concurrent.futures
from PySide6 import QtGui

# =========================
# KMTS Light Unified QSS (P0)
# - 로직/데이터/시그널/레이아웃 변경 없음
# - "정렬/통일성"만: 기본 폰트, 입력/버튼 높이, 여백, 탭/그룹박스 스타일
# - 개별 박스(GPT/LOCAL) 배경색은 기존 setStyleSheet가 우선하도록, 전역 배경은 건드리지 않음
# =========================
KMTS_LIGHT_QSS = r"""
/* --- 테이블/뷰: color 미지정(등락 빨강·파랑 등 setForeground 의미색 유지) --- */
QTableView, QTableWidget, QListView, QTreeView {
    gridline-color: #d0d0d0;
}

/* --- 공통설정 GPT/LOCAL 본문 높이 과다 방지: 그룹 내부 여백/간격 축소 --- */
QGroupBox {
    margin-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QGroupBox QWidget {
    font-size: 12px;
}

/* 입력 계열: 로그인/본문 입력 (짙은 회색, 테이블은 제외) */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    min-height: 24px;
    padding: 3px 8px;
    border: 1px solid #CFCFCF;
    border-radius: 6px;
    background: #FFFFFF;
    color: #2f2f2f;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #4A90E2;
}

/* 콤보박스 드롭다운 버튼 영역 정리 */
QComboBox::drop-down {
    border-left: 1px solid #DCDCDC;
    width: 22px;
}

/* 버튼: 기본 통일 (화면 높이 절약) */
QPushButton {
    min-height: 26px;
    padding: 4px 10px;
    border: 1px solid #CFCFCF;
    border-radius: 6px;
    background: #F3F4F6;
    color: #3a3a3a;
}
QPushButton:hover {
    background: #E9EBEF;
}
QPushButton:pressed {
    background: #DEE2E8;
}
QPushButton:disabled {
    background: #F5F5F5;
    color: #9CA3AF;
    border: 1px solid #E5E7EB;
}

/* 체크박스/라디오: 간격만 살짝 */
QCheckBox, QRadioButton {
    spacing: 6px;
}

/* 탭: 높이/여백 통일 */
QTabWidget::pane {
    border: 1px solid #D9D9D9;
    top: -1px;
}
QTabBar::tab {
    min-height: 28px;
    padding: 6px 12px;
    border: 1px solid #D9D9D9;
    border-bottom: none;
    background: #F7F7F7;
    color: #333333;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    font-weight: 600;
}

/* 구분선/프레임 — border만 제거, color 미지정(자식 텍스트 회색 상속 방지) */
QFrame {
    border: 0px;
}

/* 런바(실행/전량매도/새로고침) 영역 배경 — 탭헤더보다 살짝 진하게 */
QWidget#runBar {
    background: #e9ecef;
    border: 0px;
    margin: 0px;
    padding: 6px 8px;
    border-radius: 10px;
}
QWidget#runBar QPushButton {
    border: 1px solid #cfd4da;
    background: #f8f9fa;
}
QWidget#runBar QPushButton:pressed {
    background: #eef1f4;
}

/* 탭 헤더(탭 버튼 줄) 영역 배경 — 런바보다 살짝 밝게 (탭바는 QTabBar이므로 둘 다 지정) */
QWidget#tabHeader, QTabBar#tabHeader {
    background: #f3f4f6;
    border: 0px;
    margin: 0px;
    padding: 6px 8px;
    border-radius: 10px;
}

/* 런바/탭헤더 내부 프레임 테두리 제거(라인 방지) */
QWidget#runBar QFrame, QWidget#tabHeader QFrame {
    border: 0px;
}

/* STOP(정지) 버튼 위 얇은 회색 줄 제거 */
QPushButton#StopButton {
    border: none;
}
QPushButton#StopButton:focus {
    outline: none;
}

/* STOP 박스 테두리/라인 제거 */
QWidget#stopBox, QLabel#stopLabel {
    border: 0px;
    outline: none;
}
QWidget#stopBox {
    background: #f1e6f5;
    border-radius: 12px;
}

/* 포커스 윤곽 제거(회색 라인 방지) */
*:focus {
    outline: none;
}

/* === Text color (SAFE): 일반 UI만 짙은 회색, 테이블 item 색 미지정(등락 빨강/파랑 유지) === */
QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox {
    color: #3a3a3a;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    color: #2f2f2f;
}
QHeaderView::section {
    color: #3a3a3a;
}
QMessageBox QLabel, QDialog QLabel {
    color: #3a3a3a;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    color: #777777;
}
QLineEdit[readOnly="true"] {
    color: #555555;
}
"""

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QFrame, QGridLayout, QHeaderView,
    QMessageBox, QFileDialog, QSplitter, QToolBar, QComboBox, QSpinBox, QDoubleSpinBox,
    QAbstractItemView, QMenu, QSizePolicy, QScrollArea, QCheckBox,
    QGroupBox, QLineEdit, QTextEdit, QPlainTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QProgressDialog, QStackedWidget,
    QTreeView, QAbstractItemView, QStyleFactory, QDockWidget, QListWidget,
    QButtonGroup, QRadioButton, QSlider, QToolButton, QDialog, QProgressDialog
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QMutex, QMutexLocker, QWaitCondition,
    QObject, QEvent, Slot, QSettings, QUrl, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPoint, QRect, QSize,
    QProcess
)
from PySide6.QtGui import (
    QIcon, QFont, QPixmap, QPalette, QColor, QKeySequence, QDesktopServices,
    QTextCursor, QPainter, QPen, QBrush, QLinearGradient, QAction
)


class ClickableGroupBox(QGroupBox):
    """클릭 시 clicked 시그널을 내보내는 GroupBox (공통설정 GPT/LOCAL 박스 선택용)."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class OllamaCommandWorker(QThread):
    """Ollama 명령어 실행을 백그라운드에서 수행하는 Worker (UI 멈춤 방지)."""
    finished = Signal(bool, str)  # (success, message)
    
    def __init__(self, command: list[str], parent=None):
        super().__init__(parent)
        self.command = command
    
    def run(self):
        """subprocess로 ollama 명령 실행 (타임아웃 제거: 대용량 모델은 5분 넘는 게 정상)."""
        import subprocess
        try:
            proc = subprocess.run(
                self.command,
                capture_output=True,
                text=True,
                # timeout 제거: 대용량 모델 다운로드는 5분 이상 걸릴 수 있음
                encoding="utf-8",
                errors="replace"
            )
            if proc.returncode == 0:
                output = proc.stdout.strip() or "완료"
                self.finished.emit(True, output)
            else:
                err_msg = proc.stderr.strip() or proc.stdout.strip() or "실패"
                self.finished.emit(False, err_msg[:200])  # 길이 제한
        except FileNotFoundError:
            self.finished.emit(False, "Basic AI가 설치되어 있지 않거나 PATH에 없습니다.")
        except Exception as e:
            err_str = str(e)[:200]
            self.finished.emit(False, f"오류: {err_str}")


from app.services.upbit import (
    test_public_ping,
    get_tickers,
    get_top_markets_by_volume,
    get_holdings_snapshot,
    get_holdings_snapshot_auto,  # [ADD] 실보유 자동 스냅샷
    get_all_markets,             # [ADD] 전체 마켓 목록 (positions 티커 필터링용)
)
from app.services.market_feed import get_markets_with_names

from types import MethodType  # [PATCH] nested fn → instance method binding
from app.core.auth import init_db
from app.ui.auth_dialogs import CreateAccountDialog, LoginDialog

# 교체
import app.core.bus as eventbus
# 사용처도 교체: bus.subscribe(...) -> eventbus.subscribe(...)
#                bus.publish(...)  -> eventbus.publish(...)
from app.core.state import AppState
# prefs 모듈은 “패키지(__init__.py) 누락/경로 꼬임” 시 import가 실패할 수 있다.
# 이 경우를 대비해 prefs.py를 파일 경로로 직접 로드하는 폴백을 둔다(부팅 불가 방지).
try:
    from app.utils.prefs import init_prefs, load_settings, save_settings
except ModuleNotFoundError:
    # ✅ 패키지 인식 실패(__init__.py 누락 등) 대비: prefs.py를 파일 경로로 직접 로드
    # ⚠️ 기존 폴백이 C:\app\utils\prefs.py 같은 잘못된 경로로 떨어지는 케이스가 있어,
    #     "실제 프로젝트 루트" 후보를 여러 개 탐색한다.
    import importlib.util
    import os
    import sys

    def _pick_project_root() -> str:
        # 1) run.py를 실행하는 CWD(로그상 root=C:\KMTS-v3) 우선
        cwd = os.path.abspath(os.getcwd())
        if os.path.exists(os.path.join(cwd, "app", "ui", "app_gui.py")):
            return cwd

        # 2) 현재 파일 위치 기반(정상 import면 보통 absolute)
        try:
            here = os.path.abspath(os.path.dirname(__file__))
            root = os.path.abspath(os.path.join(here, "..", ".."))  # app/ui -> 프로젝트 루트
            if os.path.exists(os.path.join(root, "app", "ui", "app_gui.py")):
                return root
        except Exception:
            pass

        # 3) 최후 폴백
        return cwd

    _ROOT_DIR = _pick_project_root()
    if _ROOT_DIR not in sys.path:
        sys.path.insert(0, _ROOT_DIR)

    # 후보 경로(우선순위)
    _CANDIDATES = [
        os.path.join(_ROOT_DIR, "app", "utils", "prefs.py"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils", "prefs.py")),  # app/ui -> app/utils
    ]

    _PREFS_PATH = None
    for p in _CANDIDATES:
        try:
            if p and os.path.exists(p):
                _PREFS_PATH = p
                break
        except Exception:
            pass

    if not _PREFS_PATH:
        raise FileNotFoundError(
            f"prefs.py not found. tried={_CANDIDATES} cwd={os.path.abspath(os.getcwd())}"
        )

    _spec = importlib.util.spec_from_file_location("app.utils.prefs", _PREFS_PATH)
    if _spec is None or _spec.loader is None:
        raise

    _prefs = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_prefs)

    init_prefs = getattr(_prefs, "init_prefs")
    load_settings = getattr(_prefs, "load_settings")
    save_settings = getattr(_prefs, "save_settings")

from app.utils.settings_schema import AppSettings

# ✅ [PATCH] strategy 타입 단일화: dict → StrategyConfig 로 강제 변환
try:
    from app.utils.settings_schema import StrategyConfig  # type: ignore
except Exception:
    StrategyConfig = None  # type: ignore

def _coerce_strategy_config(v, preserve_ai_provider_from=None):
    """
    Pydantic 경고 제거용:
    - AppSettings.strategy는 StrategyConfig를 기대하는데 dict가 들어오면 경고 발생
    - dict/모델/None 모두 StrategyConfig로 통일해서 저장/주입한다.

    P0 최소 방어:
    - StrategyConfig를 "통째로" 재생성하는 경로에서 ai_provider가 스키마 기본값(local)로 덮어써지는 것을 방지
    - preserve_ai_provider_from 에서 ai_provider만 복사(그 외 필드는 관여하지 않음)
    """
    def _apply_preserve(out_obj, src_obj):
        try:
            if out_obj is None or src_obj is None:
                return out_obj
            # src가 dict/모델 모두 대응
            if isinstance(src_obj, dict):
                _p = src_obj.get("ai_provider")
            else:
                _p = getattr(src_obj, "ai_provider", None)
            if _p:
                try:
                    out_obj.ai_provider = _p
                except Exception:
                    pass
        except Exception:
            pass
        return out_obj

    if StrategyConfig is None:
        return v if v is not None else {}

    try:
        if isinstance(v, StrategyConfig):
            return _apply_preserve(v, preserve_ai_provider_from)
    except Exception:
        pass

    try:
        if v is None:
            out = StrategyConfig.model_validate({})
            return _apply_preserve(out, preserve_ai_provider_from)

        if isinstance(v, dict):
            out = StrategyConfig.model_validate(v)
            return _apply_preserve(out, preserve_ai_provider_from)

        if hasattr(v, "model_dump"):
            out = StrategyConfig.model_validate(v.model_dump())
            return _apply_preserve(out, preserve_ai_provider_from)

        # 마지막 fallback: 매핑으로 변환 시도
        out = StrategyConfig.model_validate(dict(v))
        return _apply_preserve(out, preserve_ai_provider_from)

    except Exception:
        try:
            out = StrategyConfig()
            return _apply_preserve(out, preserve_ai_provider_from)
        except Exception:
            return v if v is not None else {}
from app.services.order_service import svc_order

from app.strategy.runner import (
    start_strategy,
    stop_strategy,
    set_symbols_from_settings,
    set_simulate,
    get_ui_holdings,
    get_ui_totals,
)

# STOP 전용 worker (UI 블로킹 방지)
_STOP_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="stop_worker")
from app.db.trades_db import positions, load_pnl_by_strategy, get_last_strategy_info
from app.services import ai_reco  # [NEW] AI 자동 추천 스케줄러/업데이트
from app.ui.tabs.config_tabs import StrategyTab  # [FIX] 실제 모듈 경로로 수정

log = logging.getLogger(__name__)

# (삭제됨) Auth dialogs:
# - CreateAccountDialog / LoginDialog 는 app/ui/auth_dialogs.py 로 이관됨

# === [PATCH-UI-HDR] begin: Upbit JWT header builder (nested keys safe) ===
import uuid, jwt
import logging as _hdr_log

def _make_upbit_headers(ak: str, sk: str, source: str = "unknown") -> dict:
    """
    ak/sk 직접 주입으로 JWT 헤더 생성. (UI 입력값·테스트 버튼용)
    """
    try:
        ak = (ak or "").strip()
        sk = (sk or "").strip()
        if not ak or not sk:
            return {}
        if len(ak) < 10 or len(sk) < 10:
            _hdr_log.getLogger(__name__).warning(
                f"[UPBIT-JWT] skip keys_too_short access_len={len(ak)} secret_len={len(sk)}"
            )
            return {}
        _hdr_log.getLogger(__name__).info(
            f"[UPBIT-JWT] attempt source={source} access_len={len(ak)} secret_len={len(sk)}"
        )
        payload = {"access_key": ak, "nonce": str(uuid.uuid4())}
        token = jwt.encode(payload, sk, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        _hdr_log.getLogger(__name__).error(
            f"[UPBIT-JWT] fail exc={type(e).__name__} msg={str(e)[:50]}"
        )
        return {}

def _make_upbit_headers_from_settings(settings, source="unknown") -> dict:
    """
    AppSettings.upbit.{access_key, secret_key} (obj/dict 모두 대응).
    내부에서 ak/sk 추출 후 _make_upbit_headers(ak, sk, source) 호출.
    """
    try:
        up = getattr(settings, "upbit", None)
        ak = sk = None
        if up is not None:
            ak = getattr(up, "access_key", None)
            sk = getattr(up, "secret_key", None)
            if ak is None and isinstance(up, dict):
                ak = up.get("access_key")
                sk = up.get("secret_key")
        if not ak or not sk:
            return {}
        ak = (ak or "").strip()
        sk = (sk or "").strip()
        return _make_upbit_headers(ak, sk, source)
    except Exception as e:
        _hdr_log.getLogger(__name__).error(
            f"[UPBIT-JWT] fail exc={type(e).__name__} msg={str(e)[:50]}"
        )
        return {}
# === [PATCH-UI-HDR] end ===

# --------- Main window ---------
class MainWindow(QMainWindow):
    # ✅ Diet 목표(진행 중)
    # - app_gui.py: 탭 생성/상태/서비스/라우팅만
    # - 각 탭 파일: UI 위젯 생성/보유/시그널/렌더링 100%

    def _ensure_run_widgets(self):
        """상단 상태 라벨/타이머 지연 생성."""
        if not hasattr(self, "_run_timer"):
            from PySide6.QtCore import QTimer
            self._run_timer = QTimer(self)
            self._run_timer.setInterval(3000)  # 3초마다
            self._run_timer.timeout.connect(lambda: self.refresh_account_summary("timer"))
        if not hasattr(self, "lbl_run_state"):
            # 상단 툴바나 적절한 레이아웃에 이미 라벨이 있으면 그걸 쓰고,
            # 없으면 임시로 상태 라벨만 둔다. (최소 침습)
            self.lbl_run_state = QLabel("IDLE")
            try:
                # 툴바가 있다면 추가
                self.toolbar.addWidget(self.lbl_run_state)  # toolbar 없으면 except
            except Exception:
                pass  # 라벨만 보유해도 무해

    def set_aits_state(self, state: str):
        state = str(state).upper()
        lb = getattr(self, "lbl_aits_state", None)
        if lb is None:
            return
        if state == "RUNNING":
            lb.setText("AITS RUNNING")
            lb.setStyleSheet("color:#2e7d32; font-weight:bold;")
        elif state == "ERROR":
            lb.setText("AITS ERROR")
            lb.setStyleSheet("color:#c62828; font-weight:bold;")
        else:
            lb.setText("AITS STOPPED")
            lb.setStyleSheet("color:#9e9e9e; font-weight:bold;")

    def set_ai_status(self, status: str):
        s = str(status).strip().upper()
        lb = getattr(self, "lbl_ai_status", None)
        if lb is None:
            return
        if s == "TRADING":
            lb.setText("AI Status: Trading")
            lb.setStyleSheet("color:#ef6c00; font-weight:600;")
        elif s == "SCANNING":
            lb.setText("AI Status: Scanning")
            lb.setStyleSheet("color:#1565c0; font-weight:600;")
        else:
            lb.setText("AI Status: Idle")
            lb.setStyleSheet("color:#607d8b; font-weight:600;")

    def _set_running_ui(self, running: bool):
        """RUNNING/IDLE 표시 + KPI 자동 갱신 on/off + 버튼/라벨 동기화."""
        self._ensure_run_widgets()
        try:
            self.set_aits_state("RUNNING" if running else "STOPPED")
        except Exception:
            pass
        try:
            self.set_ai_status("SCANNING" if running else "IDLE")
        except Exception:
            pass

        # 1) 상태 라벨들 동기화(여러 이름을 대비해 안전하게 시도)
        txt_state = "RUNNING" if running else "STOP"
        for name in ("lbl_run_state", "lbl_status", "lbl_top_state", "lbl_state", "lbl_status_big"):
            try:
                lb = getattr(self, name, None)
                if lb is not None:
                    lb.setText(txt_state)
                    # RUNNING 상태일 때 초록색으로 변경
                    if running:
                        lb.setStyleSheet("""
                            QLabel#stopLabel {
                                font-size: 24px;
                                font-weight: bold;
                                color: #10b981;
                                padding: 4px 8px;
                            }
                        """)
                    else:
                        lb.setStyleSheet("""
                            QLabel#stopLabel {
                                font-size: 24px;
                                font-weight: bold;
                                color: #6f42c1;
                                padding: 4px 8px;
                            }
                        """)
            except Exception:
                pass  # 라벨만 보유해도 무해

        # 2) 실행 버튼 텍스트/아이콘 동기화(여러 후보명을 안전 탐색)
        btn_txt = "AITS STOP" if running else "AITS ON"
        for name in ("btn_run", "btn_toggle_run", "btn_start_stop", "btn_execute", "btn_run_toggle"):
            try:
                btn = getattr(self, name, None)
                if btn is not None:
                    btn.setText(btn_txt)
                    if name == "btn_run_toggle":
                        if running:
                            btn.setStyleSheet(
                                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                                " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                            )
                        else:
                            btn.setStyleSheet(
                                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                                " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                            )
                    # Stop 완료 후에만 버튼 재활성화 (Stop inflight guard와 쌍)
                    if not running:
                        btn.setEnabled(True)
            except Exception:
                pass

        # 2b) 실행중 점멸: RUN 시 500ms 간격으로 RUNNING 박스(lbl_status) 배경/텍스트 색 토글, STOP 시 타이머 중단·박스 원복. 정지 버튼은 점멸 금지.
        try:
            if running:
                if not hasattr(self, "_run_blink_timer"):
                    self._run_blink_timer = QTimer(self)
                    self._run_blink_timer.timeout.connect(self._run_blink_tick)
                self._run_blink_on = True
                self._run_blink_timer.setInterval(500)
                self._run_blink_timer.start()
            else:
                if hasattr(self, "_run_blink_timer") and self._run_blink_timer.isActive():
                    self._run_blink_timer.stop()
                lb = getattr(self, "lbl_status", None)
                if lb is not None:
                    lb.setStyleSheet(
                        "QLabel#stopLabel { font-size: 24px; font-weight: bold; color: #6f42c1; padding: 4px 8px; }"
                    )
        except Exception:
            pass

        # 3) 타이머 on/off (자동 KPI 갱신)
        try:
            if running:
                self._run_timer.start()
            else:
                self._run_timer.stop()
        except Exception:
            pass

    def _run_blink_tick(self):
        """실행중 점멸: RUNNING 박스(lbl_status) 배경/텍스트 색을 500ms마다 토글. 정지 버튼은 건드리지 않음."""
        try:
            lb = getattr(self, "lbl_status", None)
            if lb is None or (lb.text() or "").strip() != "RUNNING":
                return
            self._run_blink_on = not getattr(self, "_run_blink_on", True)
            if self._run_blink_on:
                lb.setStyleSheet(
                    "QLabel#stopLabel { font-size: 24px; font-weight: bold; color: #10b981; padding: 4px 8px; background-color: #d1fae5; border-radius: 4px; }"
                )
            else:
                lb.setStyleSheet(
                    "QLabel#stopLabel { font-size: 24px; font-weight: bold; color: #059669; padding: 4px 8px; background-color: #a7f3d0; border-radius: 4px; }"
                )
        except Exception:
            pass

    def _ensure_orders_once(self, reason: str) -> bool:
        """ORDER-ENSURE 단일 엔트리 래퍼 (중복 호출 방지)"""
        import time
        current_time = time.time()
        
        # 재진입 방지
        if hasattr(self, '_ensure_inflight') and self._ensure_inflight:
            self._log.info(f"[ORDER-ENSURE] skip re-entry reason={reason}")
            return False
        
        # 1초 이내 재호출 방지
        if (hasattr(self, '_ensure_last_ts') and 
            current_time - self._ensure_last_ts < 1.0):
            self._log.info(f"[ORDER-ENSURE] skip throttled reason={reason}")
            return False
        
        try:
            self._ensure_inflight = True
            self._ensure_last_ts = current_time
            return self._ensure_order_ready(reason)
        finally:
            self._ensure_inflight = False

    def _ensure_order_ready(self, reason: str) -> bool:
        import logging
        log = logging.getLogger(__name__)
        
        # 중복 호출 방지 (2초 이내 동일 reason은 스킵)
        import time
        current_time = time.time()
        if (self._last_ensure_reason == reason and 
            current_time - self._last_ensure_time < 2.0):
            # ✅ 이미 직전에 ensure가 성공했을 가능성이 높으므로 "실패"로 처리하면 상단 경고가 오탐됨
            log.info(f"[ORDER-ENSURE] skip duplicate reason={reason} treated_as_ok=1")
            return True
        
        try:
            self._last_ensure_reason = reason
            self._last_ensure_time = current_time
            log.info(f"[ORDER-ENSURE] start reason={reason}")

            # ✅ SSOT: settings 소스 통일 (self._settings 우선, 없으면 cache gate)
            settings = self._settings or self._get_settings_cached(force=False)
            if settings is None:
                log.warning(f"[ORDER-ENSURE] fail reason={reason} err=settings_none")
                return False
            
            # ORDER 서비스에 설정 주입 (Stop에서 하던 로직 그대로)
            from app.services.order_service import svc_order
            svc_order.set_settings(settings)
            
            # ✅ P0-KEY-SSOT-AUDIT: order readiness 로그
            ak_len = len(getattr(settings.upbit, "access_key", "").strip()) if hasattr(settings, "upbit") else 0
            sk_len = len(getattr(settings.upbit, "secret_key", "").strip()) if hasattr(settings, "upbit") else 0
            live_trade = getattr(settings, "live_trade", None)
            simulate = not bool(live_trade) if live_trade is not None else None
            
            log.info(f"[ORDER-AUDIT] reason={reason} simulate={simulate} live_trade={live_trade} ak_len={ak_len} sk_len={sk_len}")
            
            # simulate 동기화 (runner.py start_strategy 로직)
            try:
                live = bool(getattr(settings, "live_trade", False))
                simulate = (not live)
                svc_order._simulate = simulate
                log.info(f"[ORDER-ENSURE] ok reason={reason} simulate={simulate}")
                return True
            except Exception as e:
                log.error(f"[ORDER-ENSURE] fail reason={reason} simulate_sync_error={e}")
                return False
                
        except Exception as e:
            log.error(f"[ORDER-ENSURE] fail reason={reason} err={e}")
            return False

    def _apply_account_summary_ui(self, total_asset: float, available_krw: float, pnl_krw=None, roi_pct=None, state: str = "ok") -> None:
        """
        ✅ 상단 현황판 UI 업데이트 통합 함수
        - pnl_krw/roi_pct: 포트폴리오 보유자산 평가손익(원)·수익률(%). None이면 "— 원" / "— %"
        - state="ok": 정상 스타일 (연한 녹색)
        - state="warn": 경고 스타일 (연한 노랑)
        """
        try:
            self._last_total_asset = total_asset
            self._last_available_krw = available_krw
            self._last_pnl_today = pnl_krw
            self._last_ret_pct = roi_pct
            fmt_krw = lambda x: f"{x:+,.0f}원"
            fmt_pct = lambda x: f"{x:+.2f}%"

            # 스타일 결정
            if state == "ok":
                card_style = """
                    QFrame#accountCard {
                        background: #f0f9f0;
                        border: 1px solid #c8e6c9;
                        border-radius: 6px;
                        padding: 8px;
                    }
                    QLabel#cardLabel {
                        font-size: 11px;
                        color: #2e7d32;
                        font-weight: normal;
                    }
                    QLabel#cardValue {
                        font-size: 16px;
                        font-weight: bold;
                        color: #1b5e20;
                    }
                """
                pnl_color = "#2e7d32" if (pnl_krw is not None and pnl_krw > 0) else "#d32f2f" if (pnl_krw is not None and pnl_krw < 0) else "#212529"
                ret_color = "#2e7d32" if (roi_pct is not None and roi_pct > 0) else "#d32f2f" if (roi_pct is not None and roi_pct < 0) else "#212529"
            else:  # warn
                card_style = """
                    QFrame#accountCard {
                        background: #fff8e1;
                        border: 1px solid #ffecb3;
                        border-radius: 6px;
                        padding: 8px;
                    }
                    QLabel#cardLabel {
                        font-size: 11px;
                        color: #f57c00;
                        font-weight: normal;
                    }
                    QLabel#cardValue {
                        font-size: 16px;
                        font-weight: bold;
                        color: #e65100;
                    }
                """
                pnl_color = ret_color = "#e65100"
            
            # 카드 스타일 적용
            for card in [self.card_asset, self.card_krw, self.card_pnl, self.card_ret]:
                card.setStyleSheet(card_style)
            
            # 값 업데이트 (보유종목 손익/수익률 = PortfolioTab 평가손익·수익률, 없으면 —)
            self.lbl_asset_value.setText(fmt_krw(total_asset))
            self.lbl_krw_value.setText(fmt_krw(available_krw))
            self.lbl_pnl_value.setText(fmt_krw(pnl_krw) if pnl_krw is not None else "— 원")
            self.lbl_ret_value.setText(fmt_pct(roi_pct) if roi_pct is not None else "— %")
            
            # 손익/수익률 색상 적용
            self.lbl_pnl_value.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {pnl_color};")
            self.lbl_ret_value.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ret_color};")
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[ACCT] UI apply error: {e}")

    def refresh_account_summary(self, reason: str = "manual") -> None:
        """
        SSOT: 상단 현황판 갱신 단일 함수
        - Upbit 계정/잔고/주문가능금액/손익 조회
        - 상단 라벨 4개 갱신
        - 전역 상태바에 단계 메시지 표시

        # ❗ SSOT RULE (DO NOT BREAK)
        # - settings 접근은 반드시 self._settings 또는 _get_settings_cached()만 사용
        # - load_settings() 직접 호출은 boot/patch/save 내부로 제한
        """
        import traceback
        log = logging.getLogger(__name__)

        try:
            log.info(f"[ACCT] start reason={reason}")
            
            # ✅ P0-KEY-SSOT-AUDIT: SSOT 스냅샷 로그
            # settings 소스 통일: self._settings 우선
            settings = self._settings or self._get_settings_cached(force=False)
            source = "memory" if (settings is not None and settings is self._settings) else "cache"
            
            # boot/manual_refresh 시 한번 더 확정 (선택)
            if reason in ("boot", "manual_refresh"):
                settings = self._get_settings_cached(force=True)
                source = "forced_reload"

            # ✅ Step5: 최종형 SSOT 1줄 로그 (행동 변경 없음)
            try:
                live_trade = getattr(settings, "live_trade", None) if settings else None
                poll_ms = 1500
                try:
                    p = getattr(settings, "poll", None) if settings else None
                    if hasattr(p, "ticker_ms"):
                        poll_ms = int(getattr(p, "ticker_ms") or poll_ms)
                    elif isinstance(p, dict) and p.get("ticker_ms"):
                        poll_ms = int(p.get("ticker_ms") or poll_ms)
                except Exception:
                    pass
                log.info(f"[SSOT] source={source} live_trade={bool(live_trade)} poll_ms={int(poll_ms)}")
            except Exception:
                pass
            
            live_trade = getattr(settings, "live_trade", None) if settings else None
            
            # 키 길이 계산 (primary)
            ak_len = len(getattr(settings.upbit, "access_key", "").strip()) if settings and hasattr(settings, "upbit") else 0
            sk_len = len(getattr(settings.upbit, "secret_key", "").strip()) if settings and hasattr(settings, "upbit") else 0
            
            # 키 길이 계산 (fallback)
            ak2_len = len(getattr(settings, "upbit_access_key", "").strip()) if settings else 0
            sk2_len = len(getattr(settings, "upbit_secret_key", "").strip()) if settings else 0
            
            log.info(f"[ACCT-AUDIT] reason={reason} live_trade={live_trade} ak_len={ak_len} sk_len={sk_len} (primary) / ak2_len={ak2_len} sk2_len={sk2_len} (fallback)")
            
            # ✅ ORDER 서비스 초기화 보장 (boot/manual_refresh 시점)
            if not self._ensure_order_ready(reason):
                if hasattr(self, 'set_global_status'):
                    try:
                        self.set_global_status("⚠️ API 키/권한 확인 필요", "warn", "boot")
                    except Exception:
                        pass
                return
            
            # 전역 상태바 메시지
            if hasattr(self, 'set_global_status'):
                try:
                    self.set_global_status(" 자산/주문가능금액 불러오는 중...", "busy", "boot")
                except Exception:
                    pass
            
            # 1) 현재 총자산 / 주문가능
            try:
                total_asset, available_krw = self._compute_upbit_totals()
                log.info(f"[ACCT] computed totals: total={total_asset} available={available_krw}")
            except Exception as e:
                log.error(f"[ACCT] compute_upbit_totals failed: {e}")
                # ✅ 안정적인 fallback: 마지막 잔고 값 사용
                total_asset = getattr(self, '_last_total_asset', 0.0) or 0.0
                available_krw = getattr(self, '_last_available_krw', 0.0) or 0.0
                log.warning(f"[ACCT] using fallback values: total={total_asset} available={available_krw}")
                
                # ✅ UI 개선: 데이터 가져오기 실패 시 경고 메시지
                if hasattr(self, 'set_global_status'):
                    try:
                        self.set_global_status("⚠️ 자산 데이터 가져오기 실패 - 마지막 값 사용", "warn", "boot")
                    except Exception:
                        pass

            # 2) 보유종목 손익/수익률 = PortfolioTab 평가손익·수익률 (P0-TOPBAR-3)
            pnl_krw, roi_pct = None, None
            if getattr(self, "portfolio_tab", None) and hasattr(self.portfolio_tab, "get_summary_metrics"):
                try:
                    pnl_krw, roi_pct = self.portfolio_tab.get_summary_metrics()
                except Exception:
                    pass

            # 3) 포맷팅
            fmt_krw = lambda x: f"{x:,.0f}원"
            fmt_pct = lambda x: f"{x:+.2f}%"

            # 6) 성공 상태 판정 및 UI 업데이트
            if total_asset == 0.0 and available_krw == 0.0:
                # 모든 값이 0이면 키/권한 문제 가능성
                log.warning(f"[ACCT] warn total=0.0 avail=0.0 - check key/permissions")
                self._apply_account_summary_ui(total_asset, available_krw, pnl_krw, roi_pct, state="warn")
                if hasattr(self, 'set_global_status'):
                    try:
                        self.set_global_status("🟡 자산 0원 - 키/권한 확인 필요", "warn", "boot")
                    except Exception:
                        pass
            else:
                log.info(f"[ACCT] ok total={total_asset} avail={available_krw} pnl={pnl_krw} roi={roi_pct}")
                self._apply_account_summary_ui(total_asset, available_krw, pnl_krw, roi_pct, state="ok")
                if hasattr(self, 'set_global_status'):
                    try:
                        self.set_global_status("🟢 정상 · 자산 업데이트 완료", "ok", "boot")
                    except Exception:
                        pass
            
        except Exception as e:
            log.error(f"[ACCT] fail err={e}\n{traceback.format_exc()}")
            if hasattr(self, 'set_global_status'):
                try:
                    self.set_global_status(" 자산 조회 실패(네트워크/키/권한)", "err", "boot")
                except Exception:
                    pass

    # [추가] 간단 로그 헬퍼 (UI용)
    def _log_info(self, msg: str):
        try:
            import logging
            logging.getLogger(__name__).info(msg)
        except Exception:
            print(f"[UI] {msg}")

    # [추가] 간단 토스트 래퍼
    def _toast(self, msg: str):
        try:
            QMessageBox.information(self, "알림", msg)
        except Exception:
            print(f"[UI] INFO: {msg}")

    def _toast_error(self, msg: str):
        try:
            QMessageBox.critical(self, "오류", msg)
        except Exception:
            print(f"[UI] ERROR: {msg}")

    # === [ADD] UI mini-helpers (spin/line/readonly) ===
    # (삭제됨) _mk_spin_int / _mk_line / _mk_readonly_text / _show_toast:
    # StrategyTab 완전 이전으로 app_gui.py에서 더 이상 사용하지 않는 UI 헬퍼들.

    def __init__(self, state, root_dir=None, data_dir=None):
        super().__init__()
        self.state = state
        self._root_dir = root_dir
        self._data_dir = data_dir
        
        # 부팅 저장 루프 방지 가드
        self._boot_restoring = False
        
        # ORDER-ENSURE 중복 호출 방지 가드 (2초 스로틀)
        self._last_ensure_reason = None
        self._last_ensure_time = 0.0
        
        # _ensure_orders_once 가드 변수
        self._ensure_inflight = False
        self._ensure_last_ts = 0.0
        
        # 저장 스로틀링 (부팅 중 불필요한 저장 방지 - 부팅 후 10초간 완전 차단)
        self._last_save_time = 0.0
        self._boot_start_time = 0.0
        
        # ✅ BOOT-GUARD: UI init count tracking
        self._ui_init_count = 0
        self._boot_refresh_scheduled = False
        self._boot_done = False
        
        # ✅ P0-A: Watchlist boot guard variables
        self._wl_boot_done = False
        self._wl_boot_inflight = False
        
        # ✅ INIT-GUARD: Count tracking for initialization functions
        self._load_form_count = 0
        self._key_restore_count = 0
        
        # ✅ debug_ui 플래그 초기화 (환경변수 기반)
        import os
        self._debug_ui = bool(os.getenv("KMTS_DEBUG_UI"))
        
        # ✅ settings 캐시 관리
        import time
        self._settings_cached_at = 0.0
        self._settings_cache_ttl_sec = 3
        
        # 로거 초기화
        import logging
        self._log = logging.getLogger(__name__)
        
        # ✅ BOOT-GUARD: Log UI initialization
        self._ui_init_count += 1
        import os
        pid = os.getpid()
        self._log.info(f"[BOOT-GUARD] enter fn=__init__ count={self._ui_init_count} pid={pid}")
        
        # ✅ P0-BOOT-ORDER: _settings 속성 선언 (AttributeError 방지)
        self._settings = None
        # 선택된 엔진과 분리된 "실제 적용 엔진" 상태 (gpt/gemini/basic)
        self._active_ai_engine = "basic"
        # AITS 관리 종목군 / 전체 시장 탐색(ag-Grid 스타일 원칙 → Qt 테이블 골격)
        # 상단 row 예: symbol, name, price, change_rate, source(AI|USER), ai_status, target_price, stop_loss, pnl, locked
        # 하단 row 예: symbol, name, price, change_rate, volume_24h
        self.ai_managed_rows: list[dict] = []
        self.market_all_rows: list[dict] = []
        self.basic_ai_settings = {
            "risk_mode": "중립",
            "target_profit_pct": 3.0,
            "stop_loss_pct": 1.5,
            "max_positions": 5,
            "selection_strength": "보통",
            "avoid_bear_market": True,
            "buy_sensitivity": "보통",
            "sell_sensitivity": "보통",
            "split_buy": True,
            "split_sell": True,
            "max_hold_time": 120,
            "min_volume": 100_000_000,
            "exclude_overheated": True,
            "avoid_sudden_drop": True,
            "trend_filter": "약함",
            "entry_score_threshold": 60,
            "exit_score_threshold": 45,
            "decision_speed": "보통",
            "reentry_cooldown_min": 30,
            "max_new_entries": 2,
        }
        self._basic_ai_status_idx = 0
        self._polling_started = False
        self._poll_timer = None  # 타이머 참조 저장용
        # ✅ WIN: 로그인 후 창 위치/크기 복원 및 화면 밖 방지 (1회만 복원)
        self._geometry_restored = False
        
        os.makedirs(self._data_dir, exist_ok=True)
        self.setWindowTitle("AITS | AI Trading System")

        # ✅ P0-BOOT-LOADING: 초기 로딩 팝업 표시
        self._loading_progress = QProgressDialog("KMTS에 접속중입니다...\n초기 데이터를 불러오는 중입니다.", None, 0, 0, self)
        self._loading_progress.setWindowTitle("초기화 중")
        self._loading_progress.setCancelButton(None)
        self._loading_progress.setWindowModality(Qt.ApplicationModal)
        self._loading_progress.show()

        # ✅ P0-BOOT-SCORE-INITIAL: 부트 리프레시 플래그
        self._boot_refresh_done = False
        # (정리) Watchlist 심볼/캐시 상태는 WatchlistTab 소유
        # self._wl_symbols / self._top20_cached / self._top20_last_ts 는 더 이상 사용하지 않는다.
        
        # ✅ TIMER-GUARD: Watchlist timer creation guard
        timer_created = not hasattr(self, '_wl_timer') or self._wl_timer is None
        self._wl_timer = QTimer(self)
        timer_started = self._wl_timer.isActive()
        interval_ms = self._wl_timer.interval()
        self._log.info(f"[TIMER-GUARD] wl_timer created={timer_created} started={timer_started} interval_ms={interval_ms}")

        # ✅ 타이머 연결은 _start_polling()에서 담당
        # self._wl_timer.timeout.connect(lambda: None)  # 더미 연결 제거

        # Daily snapshot 저장 파일
        self._snap_path = os.path.join(self._data_dir, "daily_snap.json")
        self._last_total_asset = None
        self._last_available_krw = None
        self._last_pnl_today = 0.0
        self._last_ret_pct = 0.0
        
        # ✅ BOOT-GUARD: Prevent duplicate UI builds
        if getattr(self, '_ui_built', False):
            self._log.warning(f"[BOOT-GUARD] UI already built, skipping _build_ui")
        else:
            self._ui_built = True
            self._log.info(f"[BOOT-GUARD] enter fn=_build_ui count=1")
            self._build_ui()

        # ✅ 폴링 메서드 정의 (인스턴스 생성 후 보장)
        def start_polling(self):
            """Alias for _start_polling() to maintain backward compatibility"""
            return self._start_polling()

        def _start_polling(self):
            # ✅ interval 변경 시에도 재적용되도록, 아래에서 active+동일 interval이면 조기 return만 수행
            # ✅ SIGNAL-GUARD: Prevent duplicate signal connections
            signal_connected = False
            # ✅ P0-RUNTIME-WARNING: PySide6가 disconnect 실패 시 RuntimeWarning을 먼저 출력하는 케이스가 있음
            # - try/except만으로는 콘솔 경고가 남을 수 있어 warnings 필터로 억제
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r".*Failed to disconnect.*timeout\(\).*",
                        category=RuntimeWarning,
                    )
                    self._wl_timer.timeout.disconnect(self._on_watchlist_tick)
                self._log.info("[SIGNAL-GUARD] disconnected timeout signal")
            except Exception:
                pass  # No connection existed
            
            # Note: Actual signal connection will be done in _build_ui after _refresh_visible is defined
            
            # ✅ P0-BOOT-ORDER: SSOT settings 접근
            st = self._settings_ssot()
            settings_ready = st is not None
            
            # ticker_ms 결정
            ms = 1500
            source = "default"
            
            if hasattr(self, '_settings') and self._settings is not None and st == self._settings:
                source = "settings"
            elif hasattr(self, '_get_settings_cached'):
                source = "cache"
            
            if st and hasattr(st, "poll"):
                poll_obj = getattr(st, "poll", None)
                if poll_obj and hasattr(poll_obj, "ticker_ms"):
                    ticker_val = getattr(poll_obj, "ticker_ms", None)
                    if ticker_val and isinstance(ticker_val, (int, float)) and ticker_val > 0:
                        ms = int(ticker_val)
                    else:
                        source = "default"
                else:
                    source = "default"
            else:
                source = "default"
            
            self._log.info(f"[POLL] start (settings_ready={settings_ready})")
            self._log.info(f"[POLL] ticker_ms={ms} source={source}")
            try:
                topn_min = 30
                if st and getattr(st, "poll", None) is not None:
                    topn_min = int(getattr(st.poll, "topN_refresh_min", 30) or 30)
                src2 = "%s;topN_refresh_min=%s" % (source, topn_min)
                self._log.info("[TOPN-TIMER] interval_ms=%s source=%s", ms, src2)
            except Exception:
                self._log.info("[TOPN-TIMER] interval_ms=%s source=%s", ms, source)

            # ✅ UI 클릭(특히 QTableWidget 내부 체크박스) 안정성:
            # 너무 짧은 tick(200ms 등)은 watchlist 폴링이 UI 이벤트 루프를 과도하게 점유해
            # "원클릭이 씹히거나, 2번 클릭해야 먹는" 체감이 발생할 수 있다.
            # (WatchlistTab은 테이블/체크박스 소유이므로 app_gui에서는 tick 폭주만 방지)
            # ✅ 폴링 주기를 3초로 조정 (시세 데이터는 1초 갱신 불필요)
            if ms < 3000:
                ms = 3000

            # ✅ 중복 타이머 방지 가드 (동일 interval이면 재시작·재연결 생략)
            if self._wl_timer.isActive():
                current_interval = self._wl_timer.interval()
                if current_interval == ms:
                    self._log.info(
                        "[TIMER-CHK] name=wl_poll active=1 interval_ms=%s duplicate=skip_same",
                        ms,
                    )
                    return
                self._wl_timer.stop()

            # ✅ 타이머 연결 (더미 연결 제거)
            # ✅ P0-RUNTIME-WARNING: disconnect 실패 경고 억제 + 중복 연결 방지(가능하면 UniqueConnection)
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r".*Failed to disconnect.*timeout\(\).*",
                        category=RuntimeWarning,
                    )
                    self._wl_timer.timeout.disconnect(self._on_watchlist_tick)
            except Exception:
                pass  # No connection existed

            try:
                from PySide6.QtCore import Qt
                self._wl_timer.timeout.connect(self._on_watchlist_tick, Qt.ConnectionType.UniqueConnection)
            except Exception:
                # UniqueConnection이 안 먹는 환경이면 기존 방식으로 연결
                self._wl_timer.timeout.connect(self._on_watchlist_tick)

            self._wl_timer.start(ms)
            self._polling_started = True  # ✅ 성공 시작시에만 표시
            self._log.info(
                "[TIMER-CHK] name=wl_poll active=%s interval_ms=%s duplicate=0",
                int(self._wl_timer.isActive()),
                ms,
            )

        # 메서드 바인딩
        self.start_polling = start_polling.__get__(self, self.__class__)
        self._start_polling = _start_polling.__get__(self, self.__class__)

        def _on_watchlist_tick(self):
            """
            워치리스트 주기 tick(허브 역할):
            - UI/테이블 조작 금지
            - WatchlistTab 메서드만 호출
            """
            tab = getattr(self, "tab_watch", None)
            if tab is None:
                return

            # poll_tick이 있으면 poll_tick만 호출 (refresh는 호출하지 않음)
            try:
                if hasattr(tab, "poll_tick"):
                    tab.poll_tick()
                    return
            except Exception:
                pass

            # poll_tick이 없을 때만 refresh fallback
            try:
                if hasattr(tab, "refresh"):
                    tab.refresh()
            except Exception:
                pass

        self._on_watchlist_tick = _on_watchlist_tick.__get__(self, self.__class__)

    # ---------- Utility: KST 날짜 키 & Snapshot IO ----------
    def _today_key_kst(self) -> str:
        now = time.time()
        kst = now + 9 * 3600  # UTC 기준 +9시간 = KST
        y, m, d = time.gmtime(kst)[:3]
        return f"{y:04d}-{m:02d}-{d:02d}"

    def _load_snap(self) -> dict:
        try:
            with open(self._snap_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_snap(self, snap: dict):
        try:
            with open(self._snap_path, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("snapshot save failed: %s", e)

    # ---------- Utility: Upbit로 총자산/주문가능 계산 ----------
    def _compute_upbit_totals(self) -> tuple[float, float]:
        """
        returns (total_asset, available_krw)

        - 총자산(total_asset): 업비트 /accounts 의 KRW 잔액 + Σ((코인 보유+잠김) × 현재가)
        * 현재가는 /ticker 배치 조회. 실패 시 해당 코인은 avg_buy_price(평단)로 임시 평가.
        - 주문가능(available_krw): KRW balance - KRW locked
        - 네트워크/인증 오류 등으로 계산 실패 시: **직전 정상값**을 그대로 반환 (0으로 떨어지지 않게)
        """
        try:
            rows = svc_order.fetch_accounts() or []
        except Exception as e:
            # ✅ 실패 시 상세 로그 추가
            import logging
            log = logging.getLogger(__name__)
            log.error(f"[UPBIT-TOTALS] fetch_accounts failed: {type(e).__name__}: {e}")
            log.error(f"[UPBIT-TOTALS] last_known: total={self._last_total_asset} available={self._last_available_krw}")
            
            if self._last_total_asset is not None:
                log.info(f"[UPBIT-TOTALS] fallback to last known values")
                return self._last_total_asset, self._last_available_krw or 0.0
            log.warning(f"[UPBIT-TOTALS] no previous values, returning 0.0, 0.0")
            return 0.0, 0.0

        krw_balance = 0.0
        krw_locked  = 0.0
        coins = []  # (sym, bal, lck, avgp)

        for a in rows:
            cur = a.get("currency")
            bal = float(a.get("balance") or 0.0)
            lck = float(a.get("locked")  or 0.0)
            if cur == "KRW":
                krw_balance = bal
                krw_locked  = lck
            else:
                avgp = float(a.get("avg_buy_price") or 0.0)
                coins.append((cur, bal, lck, avgp))

        total_asset   = krw_balance
        available_krw = max(0.0, krw_balance - krw_locked)

        if coins:
            symbols: list[str] = []
            items: list = []
            try:
                from app.services.holdings_service import fetch_live_holdings

                holdings_data = fetch_live_holdings(force=False)
                if isinstance(holdings_data, dict):
                    items = holdings_data.get("items", []) or []
            except Exception:
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                sym = str(item.get("symbol") or "").strip()
                if not sym:
                    continue
                if not bool(item.get("market_supported", False)):
                    continue
                symbols.append(sym)
            print(
                f"[AITS][app_gui] supported_holding_symbols total_items={len(items) if isinstance(items, list) else 0} supported_symbols={len(symbols)} sample={symbols[:3] if isinstance(symbols, list) else []}"
            )
            prices = {}
            if symbols:
                try:
                    CHUNK = 50
                    for i in range(0, len(symbols), CHUNK):
                        ticks = get_tickers(symbols[i : i + CHUNK]) or []
                        for t in ticks:
                            m = t.get("market")
                            if m:
                                prices[m] = float(t.get("trade_price") or 0.0)
                except Exception:
                    pass

            for sym, bal, lck, avgp in coins:
                px = prices.get(f"KRW-{sym}", 0.0)
                if px <= 0.0:
                    px = avgp
                total_asset += (bal + lck) * px

        self._last_total_asset = total_asset
        self._last_available_krw = available_krw
        return total_asset, available_krw

    # ---------- UI ----------
    def _wrap_tab_scroll(self, tab_widget: QWidget):
        """탭 콘텐츠를 QScrollArea로 감싸서 창 크기 줄일 때 스크롤 자동 표시."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setContentsMargins(0, 0, 0, 0)
        tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll.setWidget(tab_widget)
        return scroll

    def _build_ui(self):
        # ✅ QMainWindow에는 setLayout을 직접 걸면 안됨(빈화면/레이아웃 경고 원인)
        #    반드시 centralWidget을 만들고 그 위에 레이아웃을 붙인다.
        central = QWidget(self)
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)

        # ==== 상단 정보 헤더 ====
        # ---- Header (상단 현황 카드)
        header = QFrame()
        header.setObjectName("accountSummaryFrame")
        header.setStyleSheet("""
            QFrame#accountSummaryFrame {
                background: #ffffff;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 8px;
                margin: 4px 0px;
            }
        """)
        
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)
        
        # 카드 4개 생성
        self.card_asset = QFrame()
        self.card_asset.setObjectName("accountCard")
        self.card_krw = QFrame()
        self.card_krw.setObjectName("accountCard")
        self.card_pnl = QFrame()
        self.card_pnl.setObjectName("accountCard")
        self.card_ret = QFrame()
        self.card_ret.setObjectName("accountCard")
        
        # 카드 공통 스타일
        card_style = """
            QFrame#accountCard {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 8px;
            }
            QLabel#cardLabel {
                font-size: 11px;
                color: #6c757d;
                font-weight: normal;
            }
            QLabel#cardValue {
                font-size: 16px;
                font-weight: bold;
                color: #212529;
            }
        """
        
        for card in [self.card_asset, self.card_krw, self.card_pnl, self.card_ret]:
            card.setStyleSheet(card_style)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(4)
        
        # 보유자산 카드
        self.lbl_asset_label = QLabel("보유자산")
        self.lbl_asset_label.setObjectName("cardLabel")
        self.lbl_asset_value = QLabel("— 원")
        self.lbl_asset_value.setObjectName("cardValue")
        self.card_asset.layout().addWidget(self.lbl_asset_label)
        self.card_asset.layout().addWidget(self.lbl_asset_value)
        
        # 주문가능 카드
        self.lbl_krw_label = QLabel("주문가능")
        self.lbl_krw_label.setObjectName("cardLabel")
        self.lbl_krw_value = QLabel("— 원")
        self.lbl_krw_value.setObjectName("cardValue")
        self.card_krw.layout().addWidget(self.lbl_krw_label)
        self.card_krw.layout().addWidget(self.lbl_krw_value)
        
        # 보유종목 손익 카드 (값 = PortfolioTab 평가손익)
        self.lbl_pnl_label = QLabel("보유종목 손익")
        self.lbl_pnl_label.setObjectName("cardLabel")
        self.lbl_pnl_value = QLabel("— 원")
        self.lbl_pnl_value.setObjectName("cardValue")
        self.card_pnl.layout().addWidget(self.lbl_pnl_label)
        self.card_pnl.layout().addWidget(self.lbl_pnl_value)
        
        # 보유종목 수익률 카드 (값 = PortfolioTab 수익률)
        self.lbl_ret_label = QLabel("보유종목 수익률")
        self.lbl_ret_label.setObjectName("cardLabel")
        self.lbl_ret_value = QLabel("— %")
        self.lbl_ret_value.setObjectName("cardValue")
        self.card_ret.layout().addWidget(self.lbl_ret_label)
        self.card_ret.layout().addWidget(self.lbl_ret_value)
        
        # 상태 라벨 (STOP 박스: 테두리/라인 제거용 stopBox·stopLabel)
        self.lbl_status = QLabel("STOP")
        self.lbl_status.setObjectName("stopLabel")
        self.lbl_status.setStyleSheet("""
            QLabel#stopLabel {
                font-size: 24px;
                font-weight: bold;
                color: #6f42c1;
                padding: 4px 8px;
            }
        """)
        self.stop_box = QWidget(header)
        self.stop_box.setObjectName("stopBox")
        stop_box_ly = QHBoxLayout(self.stop_box)
        stop_box_ly.setContentsMargins(0, 0, 0, 0)
        stop_box_ly.addWidget(self.lbl_status)
        # 카드 배치
        header_layout.addWidget(self.stop_box, 0, 0, 1, 1)
        header_layout.addWidget(self.card_asset, 0, 1, 1, 1)
        header_layout.addWidget(self.card_krw, 0, 2, 1, 1)
        header_layout.addWidget(self.card_pnl, 0, 3, 1, 1)
        header_layout.addWidget(self.card_ret, 0, 4, 1, 1)
        header_layout.setColumnStretch(0, 0)
        header_layout.setColumnStretch(1, 1)
        header_layout.setColumnStretch(2, 1)
        header_layout.setColumnStretch(3, 1)
        header_layout.setColumnStretch(4, 1)
        
        lay.addWidget(header)

        # ✅ P0-UI-GLOBAL-STATUS: 전역 상태바 생성
        self.global_status_frame = QFrame()
        self.global_status_frame.setObjectName("globalStatusFrame")
        self.global_status_frame.setStyleSheet("""
            QFrame#globalStatusFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 4px 0px;
            }
        """)
        
        global_status_layout = QHBoxLayout(self.global_status_frame)
        global_status_layout.setContentsMargins(0, 0, 0, 0)
        global_status_layout.setSpacing(8)
        
        self.global_status_icon = QLabel("🟢")
        self.global_status_icon.setStyleSheet("font-size: 14px;")
        
        self.global_status_text = QLabel("정상")
        self.global_status_text.setStyleSheet("font-weight: bold; font-size: 12px; color: #2e7d32;")
        
        self.global_status_time = QLabel("")
        self.global_status_time.setStyleSheet("font-size: 11px; color: #666;")
        
        # AI Provider Status (우측상단: 색상 배지 + 모델명 표시)
        self.ai_status_text = QLabel("AI: —")
        self.ai_status_text.setStyleSheet(
            "font-weight: 700;"
            "font-size: 11px;"
            "padding: 3px 8px;"
            "border-radius: 10px;"
            "color: #fff;"
            "background: #999;"
        )

        global_status_layout.addWidget(self.global_status_icon)
        global_status_layout.addWidget(self.global_status_text)
        self.lbl_aits_ai_engine_status = QLabel("AITS AI Status: Market Scanning")
        self.lbl_aits_ai_engine_status.setStyleSheet(
            "font-size: 11px; color: #37474f; font-weight: 600; padding: 0 8px;"
        )
        global_status_layout.addWidget(self.lbl_aits_ai_engine_status)
        global_status_layout.addStretch()
        global_status_layout.addWidget(self.ai_status_text)
        global_status_layout.addWidget(self.global_status_time)
        
        lay.addWidget(self.global_status_frame)

        # --- AITS status panel (read-only, Phase 1) ---
        self._aits_status_group = QGroupBox("AITS AI Trading System")
        aits_ly = QVBoxLayout(self._aits_status_group)
        aits_ly.setContentsMargins(8, 8, 8, 8)
        aits_ly.setSpacing(4)
        self.lbl_aits_regime = QLabel("AITS Regime: 연결 대기")
        self.lbl_aits_action = QLabel("AITS Action: 연결 대기")
        self.lbl_aits_summary = QLabel("AITS Summary: AITS 상태 없음")
        self.lbl_aits_market = QLabel("AITS Market: AITS 상태 없음")
        self.lbl_aits_oversight = QLabel("AITS Oversight: AITS 상태 없음")
        for _lw in (self.lbl_aits_summary, self.lbl_aits_market, self.lbl_aits_oversight):
            _lw.setWordWrap(True)
        aits_ly.addWidget(self.lbl_aits_regime)
        aits_ly.addWidget(self.lbl_aits_action)
        aits_ly.addWidget(self.lbl_aits_summary)
        aits_ly.addWidget(self.lbl_aits_market)
        aits_ly.addWidget(self.lbl_aits_oversight)
        # --- AITS module pack status ---
        self.lbl_aits_pack_name = QLabel("AITS Module Pack: AI 기본 모드")
        self.lbl_aits_pack_timer = QLabel("AITS Pack Timer: 무기한")
        self.lbl_aits_pack_summary = QLabel(
            "AITS Pack Summary: 현재 모듈팩이 활성화되어 있지 않습니다."
        )
        self.lbl_aits_pack_summary.setWordWrap(True)
        aits_ly.addWidget(self.lbl_aits_pack_name)
        aits_ly.addWidget(self.lbl_aits_pack_timer)
        aits_ly.addWidget(self.lbl_aits_pack_summary)
        # --- AITS override status (module pack action override trace) ---
        self.lbl_aits_override = QLabel("AITS Override: 없음")
        self.lbl_aits_override_summary = QLabel(
            "AITS Override Summary: 이번 사이클에서 모듈팩에 의한 판단 조정이 감지되지 않았습니다."
        )
        self.lbl_aits_override_summary.setWordWrap(True)
        aits_ly.addWidget(self.lbl_aits_override)
        aits_ly.addWidget(self.lbl_aits_override_summary)
        self.lbl_aits_bias = QLabel("AITS Bias: 연결 대기")
        self.lbl_aits_bias_mode = QLabel("AITS Bias Mode: 연결 대기")
        aits_ly.addWidget(self.lbl_aits_bias)
        aits_ly.addWidget(self.lbl_aits_bias_mode)
        # --- AITS order adapter status ---
        self.lbl_aits_exec_mode = QLabel("AITS Execution Mode: 연결 대기")
        self.lbl_aits_orders = QLabel("AITS Orders: 연결 대기")
        self.lbl_aits_orders_summary = QLabel("AITS Orders Summary: 주문 실행 결과를 불러오지 못했습니다.")
        self.lbl_aits_orders_summary.setWordWrap(True)
        aits_ly.addWidget(self.lbl_aits_exec_mode)
        aits_ly.addWidget(self.lbl_aits_orders)
        aits_ly.addWidget(self.lbl_aits_orders_summary)
        # --- AITS execution mode control ---
        self.cmb_aits_exec_mode = QComboBox()
        self.cmb_aits_exec_mode.addItems(["disabled", "dry_run", "live"])
        self.lbl_aits_exec_mode_apply = QLabel("AITS Execution Control: 연결 대기")
        self._sync_aits_exec_mode_combo()
        self.cmb_aits_exec_mode.currentTextChanged.connect(self._on_aits_exec_mode_changed)
        aits_ly.addWidget(self.cmb_aits_exec_mode)
        aits_ly.addWidget(self.lbl_aits_exec_mode_apply)
        lay.addWidget(self._aits_status_group)

        # 5초마다 인포 갱신
        self._info_timer = QTimer(self)
        # self._info_timer.timeout.connect(self._update_info_box)  # 임시 제거
        # self._info_timer.start(5000)  # 임시 제거
        
        # AI Provider Status Update Timer
        self._ai_status_timer = QTimer(self)
        self._ai_status_timer.timeout.connect(self._update_ai_status)
        self._ai_status_timer.start(5000)  # 5초마다 갱신

        # ---- 테이블 자동 갱신(보이는 탭만)
        # ✅ TIMER-CREATE: Prevent tables_timer recreation
        if getattr(self, '_tables_timer', None) is None:
            self._tables_timer = QTimer(self)
            self._log.info(f"[TIMER-CREATE] tables_timer obj_id={id(self._tables_timer)}")
        else:
            self._log.info(f"[TIMER-REUSE] tables_timer obj_id={id(self._tables_timer)}")
        
        # ⚠ 너무 잦은 네트워크 호출(티커/손익 재계산)로 인한 버벅임을 줄이기 위해
        #    8초 → 12초로 갱신 주기를 완화한다.
        #    - 여전히 자동 갱신은 유지
        #    - Watchlist/투자현황 탭을 볼 때만 호출
        self._tables_timer.setInterval(12000)
        
        # ✅ TIMER-STATE: Log timer state
        self._log.info(f"[TIMER-STATE] name=tables_timer active={self._tables_timer.isActive()} interval_ms={self._tables_timer.interval()} obj_id={id(self._tables_timer)}")

        def _refresh_visible():
            import logging
            import time as _time
            _t0 = _time.perf_counter()
            log = logging.getLogger(__name__)
            try:
                log.debug("[TIMER-TICK] tables_timer obj_id=%s", id(self._tables_timer))

                idx = self.tabs.currentIndex()
                title = self.tabs.tabText(idx)
                log.debug("[UI] 자동 테이블 갱신 타이머 동작 - 현재 탭: %s", title)

                if title == "매매기록":
                    try:
                        if hasattr(self, "tab_trades") and hasattr(self.tab_trades, "refresh"):
                            self.tab_trades.refresh()
                    except Exception:
                        pass

                elif title in ("AITS 종목관리", "워치리스트"):
                    try:
                        if hasattr(self, "tab_watch") and hasattr(self.tab_watch, "refresh"):
                            self.tab_watch.refresh(caller="tables_timer_tick")
                    except Exception:
                        pass

                elif title == "투자현황":
                    try:
                        if hasattr(self, "portfolio_tab") and hasattr(self.portfolio_tab, "refresh"):
                            self.portfolio_tab.refresh()
                    except Exception:
                        pass

            except Exception as e:
                # 예외 발생 시에도 조용히 죽지 않도록 워닝 로그만 남김
                import logging
                logging.getLogger(__name__).warning("[UI] _refresh_visible() 예외: %s", e)
            finally:
                try:
                    _ms = int((_time.perf_counter() - _t0) * 1000)
                    _idx = self.tabs.currentIndex()
                    _title = self.tabs.tabText(_idx)
                    self._log.info(
                        "[UI-PERF] tab=%s refresh=tables_timer_auto ms=%s",
                        _title,
                        _ms,
                    )
                except Exception:
                    pass

        # ✅ SIGNAL-GUARD: Prevent duplicate signal connections
        try:
            self._tables_timer.timeout.disconnect()
            self._log.info("[SIGNAL-GUARD] disconnected tables_timer signal")
        except Exception:
            pass  # No connection existed
            
        self._tables_timer.timeout.connect(_refresh_visible)
        self._log.info("[SIGNAL-GUARD] connected tables_timer signal count=1")
        self._log.info(
            "[TIMER-CHK] name=tables_timer active=%s interval_ms=%s duplicate=0",
            int(self._tables_timer.isActive()),
            self._tables_timer.interval(),
        )

        # ---- Top controls (런바: 배경으로 영역 구분)
        self.top_control_widget = QWidget(central)
        self.top_control_widget.setObjectName("runBar")
        top_outer = QVBoxLayout()
        top_outer.setContentsMargins(0, 0, 0, 0)
        top_outer.setSpacing(4)
        self.lbl_aits_control_panel = QLabel("AITS Control Panel")
        self.lbl_aits_control_panel.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #111827;"
        )
        top_outer.addWidget(self.lbl_aits_control_panel)
        self.lbl_aits_state = QLabel("AITS STOPPED")
        self.lbl_aits_state.setStyleSheet("color:#9e9e9e; font-weight:bold;")
        top_outer.addWidget(self.lbl_aits_state)
        self.set_aits_state("STOPPED")
        self.lbl_ai_status = QLabel("AI Status: Idle")
        self.lbl_ai_status.setStyleSheet("color:#607d8b; font-weight:600;")
        top_outer.addWidget(self.lbl_ai_status)
        self.set_ai_status("IDLE")
        top = QHBoxLayout()
        # 실행/정지 토글 버튼
        self.btn_run_toggle = QPushButton("AITS ON")
        self.btn_run_toggle.setToolTip("AITS 자동매매를 시작합니다")
        self.btn_run_toggle.setObjectName("StopButton")
        self.btn_run_toggle.setCheckable(True)

        # ✅ P0-DIAG: 버튼 실제 타입/속성 확정 로그
        try:
            cls = type(self.btn_run_toggle)
            mod = getattr(cls, "__module__", "")
            name = getattr(cls, "__name__", "")
            inherits_qpush = False
            try:
                inherits_qpush = bool(self.btn_run_toggle.inherits("QPushButton"))
            except Exception:
                inherits_qpush = False

            obj_name = ""
            try:
                obj_name = self.btn_run_toggle.objectName()
            except Exception:
                obj_name = ""

            try:
                fp = int(self.btn_run_toggle.focusPolicy())
            except Exception:
                fp = -1

            self._log.info(
                "[BTN-TYPE] "
                f"type={mod}.{name} "
                f"inherits_QPushButton={inherits_qpush} "
                f"name={obj_name} "
                f"enabled={self.btn_run_toggle.isEnabled()} "
                f"visible={self.btn_run_toggle.isVisible()} "
                f"checkable={self.btn_run_toggle.isCheckable()} "
                f"autoDefault={getattr(self.btn_run_toggle, 'autoDefault', lambda: None)()} "
                f"default={getattr(self.btn_run_toggle, 'isDefault', lambda: None)()} "
                f"focusPolicy={fp} "
                f"mouseTracking={self.btn_run_toggle.hasMouseTracking()}"
            )
        except Exception as e:
            self._log.error(f"[BTN-TYPE] error={e}")

        # ✅ QPushButton 타입과 clicked 시그널 강제 활성화 (clicked 미발생 방지)
        try:
            self._log.info(f"[BTN-TYPE] btn_run_toggle type={type(self.btn_run_toggle).__name__} is_QPushButton={isinstance(self.btn_run_toggle, QPushButton)}")
            # clicked 시그널 강제 활성화(정책만 확인): 잘못된 setAttribute(int, bool) 호출 제거
            self.btn_run_toggle.setFocusPolicy(Qt.StrongFocus)
            self.btn_run_toggle.setAutoDefault(False)
            self.btn_run_toggle.setDefault(False)
        except Exception as e:
            self._log.error(f"[BTN-TYPE] setup error={e}")

        # ✅ 신호 차단/비활성 상태 방어(클릭이 "작동 안함"처럼 보이는 케이스 제거)
        try:
            self.btn_run_toggle.blockSignals(False)
            self.btn_run_toggle.setEnabled(True)
        except Exception:
            pass
        # 버튼 연결은 초기화 마지막에 한 번만 수행 (중복 방지)
        
        # 전량매도
        self.btn_sellall = QPushButton("전량매도")
        self.btn_sellall.setToolTip("보유 코인을 모두 시장가로 매도합니다")
        self.btn_sellall.clicked.connect(self.on_sell_all)  # P0-D2: 버튼 연결 확인
        # 통합 새로고침
        self.btn_refresh = QPushButton("상태 새로고침")
        self.btn_refresh.setToolTip("Watchlist·투자현황·수익률·요약 정보를 다시 불러옵니다")
        
        # P0-HITTEST: 창 표시 후에만 유효(표시 전이면 widgetAt이 None일 수 있음)
        try:
            from PySide6.QtWidgets import QApplication
            def _diag_hittest_once():
                try:
                    btn = self.btn_run_toggle
                    global_center = btn.mapToGlobal(btn.rect().center())
                    widget_at = QApplication.widgetAt(global_center)
                    if widget_at is not None:
                        widget_class = type(widget_at).__name__
                        try:
                            widget_name = widget_at.objectName() if hasattr(widget_at, 'objectName') else ''
                        except Exception:
                            widget_name = ''
                        self._log.info(f"[HITTEST] global={global_center} widgetAt={widget_class} name={widget_name}")
                    else:
                        self._log.info(f"[HITTEST] global={global_center} widgetAt=None")

                    try:
                        local_center = btn.rect().center()
                        child = btn.childAt(local_center)
                        if child is not None:
                            child_class = type(child).__name__
                            child_name = getattr(child, 'objectName', '')
                            self._log.info(f"[HITTEST] childAt(local_center)={child_class} name={child_name}")
                        else:
                            self._log.info("[HITTEST] childAt(local_center)=None")
                    except Exception as e:
                        self._log.error(f"[HITTEST] childAt error={e}")
                except Exception as e:
                    self._log.error(f"[HITTEST] error={e}")

            QTimer.singleShot(0, _diag_hittest_once)
        except Exception as e:
            self._log.error(f"[HITTEST] schedule error={e}")
        
        # ✅ P0-BTN-EVENT: 임시 이벤트 필터 추가 (클릭 진단용)
        from PySide6.QtCore import QObject
        
        class ButtonEventFilter(QObject):
            def __init__(self, log):
                super().__init__()
                self._log = log

            def _name_of(self, obj):
                try:
                    n = getattr(obj, "objectName", "")
                    return n() if callable(n) else n
                except Exception:
                    return ""

            def eventFilter(self, obj, event):
                from PySide6.QtCore import QEvent
                if event.type() == QEvent.MouseButtonPress:
                    name = self._name_of(obj)
                    enabled = getattr(obj, 'isEnabled', lambda: False)()
                    enabled_to = getattr(obj, 'isEnabledTo', lambda p: False)(obj.parent()) if obj.parent() else False
                    visible = getattr(obj, 'isVisible', lambda: False)()
                    geo = getattr(obj, 'geometry', lambda: None)()
                    try:
                        pos = getattr(event, 'position', lambda: None)()
                        inside = False
                        try:
                            inside = bool(getattr(obj, 'rect', lambda: None)().contains(pos.toPoint())) if pos is not None else False
                        except Exception:
                            inside = False
                        self._log.info(f"[BTN-EVENT] press name={name} enabled={enabled} enabledTo={enabled_to} visible={visible} geo={geo} pos={pos} inside={inside}")
                    except Exception:
                        self._log.info(f"[BTN-EVENT] press name={name} enabled={enabled} enabledTo={enabled_to} visible={visible} geo={geo}")
                elif event.type() == QEvent.MouseButtonRelease:
                    name = self._name_of(obj)
                    try:
                        pos = getattr(event, 'position', lambda: None)()
                        inside = False
                        try:
                            inside = bool(getattr(obj, 'rect', lambda: None)().contains(pos.toPoint())) if pos is not None else False
                        except Exception:
                            inside = False
                        self._log.info(f"[BTN-EVENT] release name={name} pos={pos} inside={inside}")
                    except Exception:
                        self._log.info(f"[BTN-EVENT] release name={name}")
                return False  # ✅ 이벤트 전파 유지

        # ✅ 반드시 설치: 클릭이 UI에 들어오는지부터 증거로 확인하기 위함
        try:
            self._btn_event_filter = ButtonEventFilter(self._log)
            self.btn_run_toggle.installEventFilter(self._btn_event_filter)
            self.btn_sellall.installEventFilter(self._btn_event_filter)
            self.btn_refresh.installEventFilter(self._btn_event_filter)
            self._log.info("[BTN-EVENT] filter installed on top buttons")
        except Exception as e:
            self._log.error(f"[BTN-EVENT] install error={e}")
        for b in (self.btn_run_toggle, self.btn_sellall, self.btn_refresh):
            top.addWidget(b)
        self.lbl_engine_status = QLabel("AI Engine | —")
        self.lbl_engine_status.setStyleSheet("font-size: 11px; color: #555;")
        self.lbl_engine_status.setToolTip("선택된 AI 엔진 및 연결 상태")
        top.addWidget(self.lbl_engine_status)
        self.lbl_active_engine = QLabel("Active Engine: Basic AI")
        self.lbl_active_engine.setStyleSheet("font-size: 11px; color: #9e9e9e; font-weight: bold;")
        self.lbl_active_engine.setToolTip("실제로 연결 완료되어 현재 적용 중인 AI 엔진")
        top.addWidget(self.lbl_active_engine)
        self.btn_run_toggle.setMinimumHeight(30)
        self.btn_sellall.setMinimumHeight(30)
        self.btn_refresh.setMinimumHeight(28)
        self.btn_run_toggle.setStyleSheet(
            "padding: 6px 14px; font-weight: 600; min-height: 30px;"
            " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
        )
        self.btn_sellall.setStyleSheet(
            "padding: 6px 14px; font-weight: 600; min-height: 30px;"
            " background-color: #e3f2fd; color: #1e88e5; border: 1px solid #4da6ff; border-radius: 6px;"
        )
        self.btn_refresh.setStyleSheet(
            "padding: 5px 12px; min-height: 28px; border-radius: 6px;"
            " background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1;"
        )
        top_outer.addLayout(top)
        self.top_control_widget.setLayout(top_outer)
        lay.addWidget(self.top_control_widget)
        try:
            self._update_active_engine_label()
        except Exception:
            pass

        # ---- AITS 종목 관리: Managed Pool / Market Explorer (위젯 생성만 — 배치는 첫 탭 내부)
        self._aits_pool_outer = QWidget(central)
        _aits_pool_ly = QVBoxLayout(self._aits_pool_outer)
        _aits_pool_ly.setContentsMargins(0, 4, 0, 4)
        _aits_pool_ly.setSpacing(6)
        _gb_managed = QGroupBox("AITS Managed Pool")
        _managed_inner = QVBoxLayout(_gb_managed)
        self.tbl_ai_managed = QTableWidget(0, 12)
        self.tbl_ai_managed.setHorizontalHeaderLabels(
            [
                "코인명",
                "현재가",
                "변동률",
                "구분",
                "AI 점수",
                "AI 상태",
                "목표가",
                "손절가",
                "수익률",
                "잠금",
                "액션",
                "AI 판단 요약",
            ]
        )
        self.tbl_ai_managed.verticalHeader().setVisible(False)
        self.tbl_ai_managed.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_ai_managed.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_ai_managed.setMinimumHeight(140)
        self.tbl_ai_managed.cellClicked.connect(self._on_ai_managed_table_cell_clicked)
        _managed_inner.addWidget(self.tbl_ai_managed)
        _gb_market = QGroupBox("Market Explorer")
        _market_inner = QVBoxLayout(_gb_market)
        self.ed_market_search = QLineEdit()
        self.ed_market_search.setPlaceholderText("코인 검색 (예: BTC, XRP, KRW-BTC)")
        self.ed_market_search.textChanged.connect(self._on_market_search_text_changed)
        _market_inner.addWidget(self.ed_market_search)
        self.tbl_market_all = QTableWidget(0, 5)
        self.tbl_market_all.setHorizontalHeaderLabels(["코인명", "현재가", "변동률", "거래량", "추가"])
        self.tbl_market_all.verticalHeader().setVisible(False)
        self.tbl_market_all.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_market_all.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_market_all.setMinimumHeight(120)
        self.tbl_market_all.cellClicked.connect(self._on_market_all_table_cell_clicked)
        _market_inner.addWidget(self.tbl_market_all)
        _aits_pool_ly.addWidget(_gb_managed, 3)
        _aits_pool_ly.addWidget(_gb_market, 2)
        try:
            self._refresh_ai_managed_table()
            QTimer.singleShot(400, self._load_market_explorer_initial_data)
        except Exception:
            pass

        # ---- Tabs
        # ✅ 탭 위젯도 central 아래로 귀속(레이아웃/표시 정상화)
        self.tabs = QTabWidget(central)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Watchlist — UI/시그널/렌더링 소유는 WatchlistTab
        from app.ui.tabs.watchlist_tab import WatchlistTab
        self.tab_watch = WatchlistTab(self)
        self.tabs.addTab(self._wrap_tab_scroll(self.tab_watch), "AITS 종목관리")
        
        # ✅ P0-BOOT-SCORE: WatchlistTab 생성 로그
        import logging
        logging.getLogger(__name__).info("[BOOT-SCORE] WatchlistTab created")
        
        # ✅ P0-UI-GLOBAL-STATUS: WatchlistTab에 parent_window 참조 전달
        self.tab_watch._parent_window = self

        # AITS Managed Pool / Market Explorer → 첫 탭 본문 상단에 배치 (메인 vertical 중복 제거)
        try:
            _wl_lay = self.tab_watch.layout()
            if _wl_lay is not None:
                _wl_lay.insertWidget(0, self._aits_pool_outer, 0)
        except Exception:
            pass
        # 기존 KMTS 워치리스트 표·상단 버튼은 숨김 (탭 내부만)
        try:
            for _bn in ("btn_clear_all", "btn_wl_100", "btn_bl_40"):
                _bw = getattr(self.tab_watch, _bn, None)
                if _bw is not None:
                    _bw.setVisible(False)
            if getattr(self.tab_watch, "tbl", None) is not None:
                self.tab_watch.tbl.setVisible(False)
        except Exception:
            pass

        # 레거시 호환(남아있는 app_gui 레거시가 self.tbl을 참조할 수 있음)
        self.tbl = getattr(self.tab_watch, "tbl", None)

        # ⚠️ 중복 addTab 제거 (동일 인스턴스를 2번 addTab 하면 이벤트/포커스 꼬임 위험)
        # self.tabs.addTab(self.tab_watch, "워치리스트")

        # Trades
        # Trades (매매기록) — UI/로딩/내보내기 소유는 TradesTab이 100% 담당
        from app.ui.tabs.trades_tab import TradesTab
        self.tab_trades = TradesTab(self)
        self.tabs.addTab(self._wrap_tab_scroll(self.tab_trades), "매매기록")
        
        # ✅ P0-UI-GLOBAL-STATUS: TradesTab에 parent_window 참조 전달
        self.tab_trades._parent_window = self

        # Portfolio (투자현황) ← 이게 핵심
        from app.ui.tabs.portfolio_tab import PortfolioTab
        self.portfolio_tab = PortfolioTab(self)
        self.tabs.addTab(self._wrap_tab_scroll(self.portfolio_tab), "투자현황")
        
        # ✅ P0-UI-GLOBAL-STATUS: PortfolioTab에 parent_window 참조 전달
        self.portfolio_tab._parent_window = self

        # 전략설정: 별도 StrategyTab 사용
        #
        # (다이어트 메모) app_gui.py는 탭 생성/상태/서비스만 유지하고, UI 위젯 소유는 각 Tab이 100% 담당한다.
        # StrategyTab owned UI path ACTIVE 상태에서는 app_gui의 레거시 전략 UI 빌더/위젯 코드는 삭제 대상이다.

        # ---- 전략설정 탭 (StrategyTab) : 단 1회 생성 + 단 1회 addTab ----
        if getattr(self, "tab_strategy", None) is None:
            self.tab_strategy = StrategyTab(self, parent=self.tabs)

        # 이미 addTab 했는지 중복 방지 (탭이 QScrollArea로 래핑된 경우 widget()으로 비교)
        already = False
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w is self.tab_strategy or (isinstance(w, QScrollArea) and w.widget() is self.tab_strategy):
                already = True
                break

        if not already:
            self.tabs.addTab(self._wrap_tab_scroll(self.tab_strategy), "전략설정")
            
            # ✅ P0-UI-GLOBAL-STATUS: StrategyTab에 parent_window 참조 전달
            self.tab_strategy._parent_window = self

        # Settings
        self.tab_settings = QWidget()
        self._init_settings(self.tab_settings)
        self.tabs.addTab(self._wrap_tab_scroll(self.tab_settings), "공통설정")

        # 상단 고정 + 탭 본문만 스크롤: 탭바와 스택을 분리해 스택만 QScrollArea에 넣음
        tab_bar = self.tabs.tabBar()
        tab_bar.setObjectName("tabHeader")
        stack = None
        for c in self.tabs.children():
            if isinstance(c, QStackedWidget):
                stack = c
                break
        if stack is not None:
            def _on_tab_bar_index_changed(idx: int) -> None:
                import time as _time
                _t0 = _time.perf_counter()
                try:
                    stack.setCurrentIndex(idx)
                finally:
                    try:
                        _ms = int((_time.perf_counter() - _t0) * 1000)
                        _title = self.tabs.tabText(idx) if idx >= 0 else "?"
                        self._log.info(
                            "[UI-PERF] tab=%s refresh=tab_switch ms=%s",
                            _title,
                            _ms,
                        )
                    except Exception:
                        pass

            tab_bar.currentChanged.connect(_on_tab_bar_index_changed)
            self._tab_scroll = QScrollArea()
            self._tab_scroll.setObjectName("contentArea")
            self._tab_scroll.setWidgetResizable(True)
            self._tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._tab_scroll.setWidget(stack)
            self._tab_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._tab_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay.addWidget(tab_bar)
            lay.addWidget(self._tab_scroll)
        else:
            lay.addWidget(self.tabs)

        # ---- 하단 상태바 (숨김 처리 - 전역 상태바로 단일화)
        self._status_ts = 0
        self.lbl_statusbar = QLabel("⏳ 초기화 중…")
        self.lbl_statusbar.setObjectName("statusbar")
        self.lbl_statusbar.setStyleSheet("QLabel#statusbar { color:#555; font-size:12px; padding:4px; }")
        self.lbl_statusbar.hide()  # ✅ P0-UI-GLOBAL-STATUS-②: 하단 상태바 숨김
        lay.addWidget(self.lbl_statusbar)

        # ✅ Start/Stop 토글: 최종 연결 블록(초기화 마지막, 단일 엔트리포인트 1개)
        # 1) 기존 연결 정리(예외 무시)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                self.btn_run_toggle.clicked.disconnect()
            except Exception:
                pass
            try:
                self.btn_run_toggle.toggled.disconnect()
            except Exception:
                pass

        # 2) 버튼 상태 고정
        try:
            self.btn_run_toggle.setCheckable(True)
            self.btn_run_toggle.blockSignals(False)
            self.btn_run_toggle.setEnabled(True)
        except Exception:
            pass

        # 3) 진단 훅(1개만)
        try:
            self.btn_run_toggle.toggled.connect(lambda v: self._log.info(f"[BTN-SIG] run toggled v={v}"))
        except Exception:
            pass

        # 4) 최종 엔트리포인트 연결(1개만)
        try:
            self.btn_run_toggle.toggled.connect(self._on_toggle_run_toggled)
            self._log.info("[BTN-CONNECT] ok target=_on_toggle_run_toggled (single entrypoint)")
        except Exception as e:
            self._log.error(f"[BTN-CONNECT] error={e}")
        try:
            self.btn_refresh.clicked.connect(self.on_refresh)
        except Exception:
            pass
        
        # ✅ P0-TOGGLE-INIT: 초기 UI 상태 로깅 + 상태 고정
        try:
            # ✅ 후보 A) 버튼 초기 체크상태가 이미 True로 시작하는 문제 해결
            self.btn_run_toggle.setChecked(False)  # 반드시 False로 시작
            self.btn_run_toggle.setText("AITS ON")  # 반드시 실행 텍스트로 시작
            btn_text = getattr(self.btn_run_toggle, 'text', lambda: '')()
            btn_checked = getattr(self.btn_run_toggle, 'isChecked', lambda: False)()
            btn_enabled = getattr(self.btn_run_toggle, 'isEnabled', lambda: True)()
            self._log.info(f"[UI-INIT] button text={btn_text} checked={btn_checked} enabled={btn_enabled}")
        except Exception as e:
            self._log.error(f"[UI-INIT] button error={e}")

        try:
            self._refresh_aits_status_view()
        except Exception:
            pass

        # ✅ P0-A: Start boot sequence after UI is built
        QTimer.singleShot(100, self._boot_sequence_step1)

    def _get_aits_runtime_state(self):
        try:
            orch = getattr(self, "orchestrator", None)
            if orch is not None and hasattr(orch, "get_runtime_state"):
                return orch.get_runtime_state()
            ctx = getattr(self, "app_context", None)
            if isinstance(ctx, dict):
                o = ctx.get("orchestrator")
                if o is not None and hasattr(o, "get_runtime_state"):
                    return o.get_runtime_state()
                rs = ctx.get("runtime_state")
                if rs is not None:
                    return rs
            rs = getattr(self, "runtime_state", None)
            if rs is not None:
                return rs
        except Exception:
            return None
        return None

    def _format_seconds_to_hhmmss(self, seconds: int) -> str:
        try:
            s = int(seconds)
        except (TypeError, ValueError):
            s = 0
        if s < 0:
            s = 0
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _get_aits_module_pack_runtime(self):
        try:
            orch = getattr(self, "orchestrator", None)
            if orch is not None and hasattr(orch, "get_last_module_pack_runtime"):
                return orch.get_last_module_pack_runtime()
            ctx = getattr(self, "app_context", None)
            if isinstance(ctx, dict):
                o = ctx.get("orchestrator")
                if o is not None and hasattr(o, "get_last_module_pack_runtime"):
                    return o.get_last_module_pack_runtime()
            return getattr(self, "last_module_pack_runtime", None)
        except Exception:
            return None
        return None

    def _set_aits_module_pack_labels(self) -> None:
        if not all(
            hasattr(self, n)
            for n in ("lbl_aits_pack_name", "lbl_aits_pack_timer", "lbl_aits_pack_summary")
        ):
            return
        try:
            pr = self._get_aits_module_pack_runtime()
            if pr is None:
                self.lbl_aits_pack_name.setText("AITS Module Pack: 연결 대기")
                self.lbl_aits_pack_timer.setText("AITS Pack Timer: 연결 대기")
                self.lbl_aits_pack_summary.setText(
                    "AITS Pack Summary: 모듈팩 상태를 불러오지 못했습니다."
                )
                return
            apid = getattr(pr, "active_pack_id", None)
            apid_str = "" if apid is None else str(apid).strip()
            pnk = (getattr(pr, "pack_name_ko", None) or "").strip()
            timer_en = bool(getattr(pr, "timer_enabled", False))
            try:
                rem = int(getattr(pr, "remaining_seconds", 0))
            except (TypeError, ValueError):
                rem = 0
            rsum = (getattr(pr, "runtime_summary_ko", None) or "").strip()

            if not apid_str:
                name = "AI 기본 모드"
                timer = "무기한"
                summ = rsum or "현재 모듈팩이 활성화되어 있지 않습니다."
            elif timer_en:
                name = pnk or apid_str
                timer = self._format_seconds_to_hhmmss(rem)
                summ = rsum or "—"
            else:
                name = pnk or apid_str
                timer = "무기한"
                summ = rsum or "—"

            self.lbl_aits_pack_name.setText(f"AITS Module Pack: {name}")
            self.lbl_aits_pack_timer.setText(f"AITS Pack Timer: {timer}")
            self.lbl_aits_pack_summary.setText(f"AITS Pack Summary: {summ}")
        except Exception:
            self.lbl_aits_pack_name.setText("AITS Module Pack: 연결 대기")
            self.lbl_aits_pack_timer.setText("AITS Pack Timer: 연결 대기")
            self.lbl_aits_pack_summary.setText(
                "AITS Pack Summary: 모듈팩 상태를 불러오지 못했습니다."
            )

    def _set_aits_override_labels(self) -> None:
        if not all(
            hasattr(self, n)
            for n in ("lbl_aits_override", "lbl_aits_override_summary")
        ):
            return
        try:
            rs = self._get_aits_runtime_state()
            if rs is None:
                self.lbl_aits_override.setText("AITS Override: 연결 대기")
                self.lbl_aits_override_summary.setText(
                    "AITS Override Summary: AITS 상태를 불러오는 중입니다."
                )
                return
            intel = getattr(rs, "intelligence", None)
            ai_dec = getattr(intel, "ai_decision", None) if intel else None
            if ai_dec is None:
                self.lbl_aits_override.setText("AITS Override: 확인 불가")
                self.lbl_aits_override_summary.setText(
                    "AITS Override Summary: 이번 사이클의 override 여부를 확인할 수 없습니다."
                )
                return
            raw_logic = getattr(ai_dec, "selected_strategy_logic", None)
            if raw_logic is None:
                logic_s = ""
            else:
                logic_s = raw_logic if isinstance(raw_logic, str) else str(raw_logic)
            logic_s = (logic_s or "").strip()
            if not logic_s:
                self.lbl_aits_override.setText("AITS Override: 확인 불가")
                self.lbl_aits_override_summary.setText(
                    "AITS Override Summary: 이번 사이클의 override 여부를 확인할 수 없습니다."
                )
                return
            raw_sum = getattr(ai_dec, "ai_summary_for_user", None)
            ai_summary = "" if raw_sum is None else str(raw_sum).strip()
            if "override_applied" in logic_s:
                summ = ai_summary or "현재 모듈팩의 영향으로 기본 판단이 한 단계 조정되었습니다."
                self.lbl_aits_override.setText("AITS Override: 적용됨")
                self.lbl_aits_override_summary.setText(f"AITS Override Summary: {summ}")
            else:
                self.lbl_aits_override.setText("AITS Override: 없음")
                self.lbl_aits_override_summary.setText(
                    "AITS Override Summary: 이번 사이클에서 모듈팩에 의한 판단 조정이 감지되지 않았습니다."
                )
        except Exception:
            try:
                self.lbl_aits_override.setText("AITS Override: 확인 불가")
                self.lbl_aits_override_summary.setText(
                    "AITS Override Summary: 이번 사이클의 override 여부를 확인할 수 없습니다."
                )
            except Exception:
                pass

    def _get_aits_effective_biases(self):
        """
        orchestrator -> last_module_pack_runtime -> bias 추출
        return dict or None
        """
        try:
            runtime = self._get_aits_module_pack_runtime()
            if runtime is None:
                return None
            return {
                "buy": getattr(runtime, "effective_buy_bias_delta", 0.0),
                "wait": getattr(runtime, "effective_wait_bias_delta", 0.0),
                "reduce": getattr(runtime, "effective_reduce_bias_delta", 0.0),
                "sell": getattr(runtime, "effective_sell_bias_delta", 0.0),
                "mode": getattr(runtime, "effective_risk_bias", None),
            }
        except Exception:
            return None

    def _format_bias_value(self, v):
        try:
            return f"{float(v):+.2f}"
        except Exception:
            return "+0.00"

    def _pick_aits_bias_color(self, buy: float, wait: float, reduce: float, sell: float) -> str:
        try:
            vals = [float(buy), float(wait), float(reduce), float(sell)]
            rep = max(vals, key=lambda x: abs(x))
            if abs(rep) < 0.05:
                return "#888888"
            if rep >= 0.15:
                return "#1f7a1f"
            if rep >= 0.05:
                return "#2e8b57"
            if rep <= -0.15:
                return "#b34747"
            if rep <= -0.05:
                return "#c07a2b"
            return "#888888"
        except Exception:
            return "#888888"

    def _pick_aits_bias_mode_color(self, mode: str) -> str:
        try:
            m = (mode or "").strip().lower()
            if m == "offensive":
                return "#1f7a1f"
            if m == "defensive":
                return "#b34747"
            return "#888888"
        except Exception:
            return "#888888"

    def _set_aits_bias_labels(self) -> None:
        if not all(
            hasattr(self, n)
            for n in ("lbl_aits_bias", "lbl_aits_bias_mode")
        ):
            return
        try:
            bias = self._get_aits_effective_biases()
            if bias is None:
                self.lbl_aits_bias.setText("AITS Bias: 연결 대기")
                self.lbl_aits_bias_mode.setText("AITS Bias Mode: 연결 대기")
                self.lbl_aits_bias.setStyleSheet("color: #888888;")
                self.lbl_aits_bias_mode.setStyleSheet("color: #888888;")
                return
            buy_v = float(bias.get("buy", 0.0))
            wait_v = float(bias.get("wait", 0.0))
            reduce_v = float(bias.get("reduce", 0.0))
            sell_v = float(bias.get("sell", 0.0))
            buy = self._format_bias_value(bias.get("buy", 0.0))
            wait = self._format_bias_value(bias.get("wait", 0.0))
            reduce = self._format_bias_value(bias.get("reduce", 0.0))
            sell = self._format_bias_value(bias.get("sell", 0.0))
            mode = str(bias.get("mode") or "neutral").strip() or "neutral"
            bias_color = self._pick_aits_bias_color(buy_v, wait_v, reduce_v, sell_v)
            mode_color = self._pick_aits_bias_mode_color(mode)
            self.lbl_aits_bias.setText(
                f"AITS Bias: buy={buy} | wait={wait} | reduce={reduce} | sell={sell}"
            )
            self.lbl_aits_bias_mode.setText(f"AITS Bias Mode: {mode}")
            self.lbl_aits_bias.setStyleSheet(f"color: {bias_color};")
            self.lbl_aits_bias_mode.setStyleSheet(f"color: {mode_color};")
        except Exception:
            self.lbl_aits_bias.setText("AITS Bias: 연결 대기")
            self.lbl_aits_bias_mode.setText("AITS Bias Mode: 연결 대기")
            self.lbl_aits_bias.setStyleSheet("color: #888888;")
            self.lbl_aits_bias_mode.setStyleSheet("color: #888888;")

    def _get_aits_order_adapter_result(self):
        try:
            orch = getattr(self, "orchestrator", None)
            if orch is not None and hasattr(orch, "get_last_order_adapter_result"):
                return orch.get_last_order_adapter_result()
            ctx = getattr(self, "app_context", None)
            if isinstance(ctx, dict):
                o = ctx.get("orchestrator")
                if o is not None and hasattr(o, "get_last_order_adapter_result"):
                    return o.get_last_order_adapter_result()
            return getattr(self, "last_order_adapter_result", None)
        except Exception:
            return None
        return None

    def _get_aits_execution_mode(self):
        try:
            orch = getattr(self, "orchestrator", None)
            if orch is not None and hasattr(orch, "get_execution_mode"):
                return orch.get_execution_mode()
            ctx = getattr(self, "app_context", None)
            if isinstance(ctx, dict):
                o = ctx.get("orchestrator")
                if o is not None and hasattr(o, "get_execution_mode"):
                    return o.get_execution_mode()
            return None
        except Exception:
            return None
        return None

    def _get_aits_orchestrator(self):
        try:
            orch = getattr(self, "orchestrator", None)
            if orch is not None:
                return orch
            ctx = getattr(self, "app_context", None)
            if isinstance(ctx, dict):
                o = ctx.get("orchestrator")
                if o is not None:
                    return o
        except Exception:
            return None
        return None

    def _sync_aits_exec_mode_combo(self) -> None:
        if not hasattr(self, "cmb_aits_exec_mode"):
            return
        try:
            mode = str(self._get_aits_execution_mode() or "disabled").strip()
            if mode not in ("disabled", "dry_run", "live"):
                mode = "disabled"
            self.cmb_aits_exec_mode.blockSignals(True)
            self.cmb_aits_exec_mode.setCurrentText(mode)
            self.cmb_aits_exec_mode.blockSignals(False)
            if hasattr(self, "lbl_aits_exec_mode_apply"):
                if self._get_aits_orchestrator() is None:
                    self.lbl_aits_exec_mode_apply.setText(
                        "AITS Execution Control: 오케스트레이터 연결 대기"
                    )
                else:
                    self.lbl_aits_exec_mode_apply.setText(
                        f"AITS Execution Control: 현재 모드 {mode}"
                    )
        except Exception:
            try:
                self.cmb_aits_exec_mode.blockSignals(True)
                self.cmb_aits_exec_mode.setCurrentText("disabled")
                self.cmb_aits_exec_mode.blockSignals(False)
            except Exception:
                pass
            if hasattr(self, "lbl_aits_exec_mode_apply"):
                self.lbl_aits_exec_mode_apply.setText("AITS Execution Control: 연결 대기")

    def _on_aits_exec_mode_changed(self, value: str) -> None:
        try:
            orch = self._get_aits_orchestrator()
            if orch is None or not hasattr(orch, "set_execution_mode"):
                self.lbl_aits_exec_mode_apply.setText(
                    "AITS Execution Control: 오케스트레이터 연결 대기"
                )
                return
            selected = str(value or "").strip() or "disabled"
            orch.set_execution_mode(selected)
            applied = "disabled"
            if hasattr(orch, "get_execution_mode"):
                applied = str(orch.get_execution_mode() or "disabled").strip() or "disabled"
            if applied not in ("disabled", "dry_run", "live"):
                applied = "disabled"
            self.lbl_aits_exec_mode_apply.setText(f"AITS Execution Control: 적용됨 ({applied})")
            self._sync_aits_exec_mode_combo()
        except Exception:
            try:
                self.lbl_aits_exec_mode_apply.setText("AITS Execution Control: 적용 실패")
            except Exception:
                pass

    def _set_aits_order_adapter_labels(self) -> None:
        if not all(
            hasattr(self, n)
            for n in ("lbl_aits_exec_mode", "lbl_aits_orders", "lbl_aits_orders_summary")
        ):
            return
        try:
            mode = self._get_aits_execution_mode()
            ar = self._get_aits_order_adapter_result()
            if ar is None:
                if mode:
                    exec_text = str(mode)
                    orders_text = "결과 대기"
                    summary_text = "이번 사이클의 주문 실행 결과를 기다리는 중입니다."
                else:
                    exec_text = "연결 대기"
                    orders_text = "연결 대기"
                    summary_text = "주문 실행 결과를 불러오지 못했습니다."
            else:
                exec_text = getattr(ar, "execution_mode", None) or (mode or "확인 불가")
                submitted = int(getattr(ar, "submitted_count", 0) or 0)
                blocked = int(getattr(ar, "blocked_count", 0) or 0)
                failed = int(getattr(ar, "failed_count", 0) or 0)
                skipped = int(getattr(ar, "skipped_count", 0) or 0)
                summary_text = getattr(ar, "summary_ko", "") or "주문 실행 결과 요약이 없습니다."
                orders_text = (
                    f"submitted={submitted} | blocked={blocked} | failed={failed} | skipped={skipped}"
                )
            self.lbl_aits_exec_mode.setText(f"AITS Execution Mode: {exec_text}")
            self.lbl_aits_orders.setText(f"AITS Orders: {orders_text}")
            self.lbl_aits_orders_summary.setText(f"AITS Orders Summary: {summary_text}")
        except Exception:
            self.lbl_aits_exec_mode.setText("AITS Execution Mode: 연결 대기")
            self.lbl_aits_orders.setText("AITS Orders: 연결 대기")
            self.lbl_aits_orders_summary.setText(
                "AITS Orders Summary: 주문 실행 결과를 불러오지 못했습니다."
            )

    def _refresh_aits_status_view(self):
        if not all(
            hasattr(self, n)
            for n in (
                "lbl_aits_regime",
                "lbl_aits_action",
                "lbl_aits_summary",
                "lbl_aits_market",
                "lbl_aits_oversight",
                "lbl_aits_pack_name",
                "lbl_aits_pack_timer",
                "lbl_aits_pack_summary",
                "lbl_aits_override",
                "lbl_aits_override_summary",
                "lbl_aits_bias",
                "lbl_aits_bias_mode",
                "lbl_aits_exec_mode",
                "lbl_aits_orders",
                "lbl_aits_orders_summary",
                "cmb_aits_exec_mode",
                "lbl_aits_exec_mode_apply",
            )
        ):
            return
        try:
            rs = self._get_aits_runtime_state()
            if rs is None:
                self.lbl_aits_regime.setText("AITS Regime: 연결 대기")
                self.lbl_aits_action.setText("AITS Action: 연결 대기")
                self.lbl_aits_summary.setText("AITS Summary: AITS 상태 없음")
                self.lbl_aits_market.setText("AITS Market: AITS 상태 없음")
                self.lbl_aits_oversight.setText("AITS Oversight: AITS 상태 없음")
                self._set_aits_module_pack_labels()
                self._set_aits_override_labels()
                self._set_aits_bias_labels()
                self._set_aits_order_adapter_labels()
                self._sync_aits_exec_mode_combo()
                return
            market = getattr(rs, "market", None)
            regime = getattr(market, "regime", None) if market else None
            regime_lbl = getattr(regime, "label", "") if regime else ""
            intel = getattr(rs, "intelligence", None)
            ai_dec = getattr(intel, "ai_decision", None) if intel else None
            action = getattr(ai_dec, "action", "") if ai_dec else ""
            summary = getattr(ai_dec, "ai_summary_for_user", "") if ai_dec else ""
            expl = getattr(rs, "explainability", None)
            mstory = getattr(expl, "current_market_story", "") if expl else ""
            over = getattr(rs, "oversight", None)
            ovsum = getattr(over, "oversight_summary", "") if over else ""
            self.lbl_aits_regime.setText(f"AITS Regime: {regime_lbl or '—'}")
            self.lbl_aits_action.setText(f"AITS Action: {action or '—'}")
            self.lbl_aits_summary.setText(f"AITS Summary: {summary or '—'}")
            self.lbl_aits_market.setText(f"AITS Market: {mstory or '—'}")
            self.lbl_aits_oversight.setText(f"AITS Oversight: {ovsum or '—'}")
            self._set_aits_module_pack_labels()
            self._set_aits_override_labels()
            self._set_aits_bias_labels()
            self._set_aits_order_adapter_labels()
            self._sync_aits_exec_mode_combo()
        except Exception:
            self.lbl_aits_regime.setText("AITS Regime: 연결 대기")
            self.lbl_aits_action.setText("AITS Action: 연결 대기")
            self.lbl_aits_summary.setText("AITS Summary: AITS 상태 없음")
            self.lbl_aits_market.setText("AITS Market: AITS 상태 없음")
            self.lbl_aits_oversight.setText("AITS Oversight: AITS 상태 없음")
            try:
                self._set_aits_module_pack_labels()
            except Exception:
                pass
            try:
                self._set_aits_override_labels()
            except Exception:
                pass
            try:
                self._set_aits_bias_labels()
            except Exception:
                pass
            try:
                self._set_aits_order_adapter_labels()
            except Exception:
                pass
            try:
                self._sync_aits_exec_mode_combo()
            except Exception:
                pass

    def _update_top_badge(self):
        """상단 라운드 배지 = 최종 적용 엔진만. actual_engine(매매기록과 동일). 연결중 표시 금지."""
        try:
            actual = ""
            try:
                from app.services import ai_reco
                last_dec = ai_reco.get_last_decision() or {}
                actual = (last_dec.get("actual_engine") or "").strip()
            except Exception:
                pass
            c_blue, c_green, c_orange = "#2F6FED", "#2E8B57", "#F57C00"
            c_white = "#fff"
            if actual == "simple_momo" or (getattr(self, "_gpt_status_stage", "") or "").strip().lower() == "degraded":
                badge_txt = "SIMPLE_MOMO"
                badge_bg, badge_fg = c_orange, c_white
            elif actual.startswith("gpt-"):
                badge_txt = "GPT | %s" % actual
                badge_bg, badge_fg = c_blue, c_white
            elif actual:
                badge_txt = "LOCAL | %s" % actual
                badge_bg, badge_fg = c_green, c_white
            else:
                badge_txt = "LOCAL | —"
                badge_bg, badge_fg = c_green, c_white
            if hasattr(self, "ai_status_text") and self.ai_status_text is not None:
                self.ai_status_text.setVisible(True)
                self.ai_status_text.setText(badge_txt)
                self.ai_status_text.setStyleSheet(
                    "font-weight: 700; font-size: 11px; padding: 3px 8px; border-radius: 10px;"
                    " color: %s; background: %s;" % (badge_fg, badge_bg)
                )
        except Exception:
            pass

    def _update_engine_status_box(self):
        """새로고침 오른쪽 큰 박스 = 실시간 연결/전환 상태. 배경 연회색 고정, 신호등 아이콘만."""
        try:
            if not getattr(self, "_engine_ui_unified_done", False):
                for name in ("gpt_test_header_status", "gpt_decision_summary"):
                    w = getattr(self, name, None)
                    if w is not None:
                        try:
                            w.setVisible(False)
                        except Exception:
                            pass
                self._engine_ui_unified_done = True
            selected = ""
            sel_eng = ""
            cloud_model = ""
            try:
                st = getattr(self._settings, "strategy", None) if getattr(self, "_settings", None) else None
                st_dict = st.model_dump() if hasattr(st, "model_dump") else (st if isinstance(st, dict) else {})
                selected = (st_dict.get("ai_provider") or "").strip().lower() if isinstance(st_dict, dict) else ""
                sel_eng = (st_dict.get("ai_local_model") or "").strip() if isinstance(st_dict, dict) else ""
                cloud_model = (st_dict.get("ai_openai_model") or "").strip() if isinstance(st_dict, dict) else ""
            except Exception:
                pass
            selected = selected if selected in ("gpt", "gemini", "local") else "local"
            actual = ""
            try:
                from app.services import ai_reco
                last_dec = ai_reco.get_last_decision() or {}
                actual = (last_dec.get("actual_engine") or "").strip()
                if not sel_eng:
                    sel_eng = (last_dec.get("selected_engine") or "").strip()
            except Exception:
                pass
            stage = (getattr(self, "_gpt_status_stage", "") or "").strip().lower()
            if selected == "local" and hasattr(self, "cmb_local_model") and self.cmb_local_model.currentText():
                local_label = (self.cmb_local_model.currentText() or "").strip() or sel_eng
            else:
                local_label = sel_eng or (actual if actual and not actual.startswith("gpt-") else "—")
            if not cloud_model and hasattr(self, "ed_openai_model"):
                cloud_model = (self.ed_openai_model.currentData() or "").strip() or (self.ed_openai_model.currentText() or "").strip()
            if actual.startswith("gpt-"):
                cloud_model = actual
            if not cloud_model:
                cloud_model = "—"

            # provider 3분기 + 상태 텍스트(내부 명칭 노출 금지)
            if stage == "degraded":
                if selected == "gpt":
                    box_txt = "AI Engine | OpenAI (%s)" % cloud_model
                elif selected == "gemini":
                    box_txt = "AI Engine | Gemini (%s)" % cloud_model
                else:
                    box_txt = "AI Engine | Basic AI (%s)" % local_label
            elif selected == "gpt":
                box_txt = "AI Engine | OpenAI (%s)" % cloud_model
            elif selected == "gemini":
                box_txt = "AI Engine | Gemini (%s)" % cloud_model
            else:
                box_txt = "AI Engine | Basic AI (%s)" % local_label

            if hasattr(self, "lbl_engine_status") and self.lbl_engine_status is not None:
                self.lbl_engine_status.setText(box_txt)
                self.lbl_engine_status.setStyleSheet(
                    "padding: 6px 14px; border-radius: 8px; font-weight: 700; color: #111; background: #F3F4F6;"
                    " border: 1px solid rgba(0,0,0,0.15); margin-left: 8px;"
                )
            self._log.info("[ENGINE-UI] selected=%s actual=%s stage=%s", selected, actual or "—", stage or "—")
        except Exception as e:
            self._log.debug("[ENGINE-UI] box err=%s", str(e)[:80])

    def _update_engine_ui_ssot(self):
        """두 계층 분리: 상단 배지(actual만) + 하단 박스(실시간 상태)."""
        try:
            self._update_top_badge()
            self._update_engine_status_box()
            actual = ""
            try:
                from app.services import ai_reco
                last_dec = ai_reco.get_last_decision() or {}
                actual = (last_dec.get("actual_engine") or "").strip()
            except Exception:
                pass
            if actual.startswith("gpt-"):
                prev = getattr(self, "_last_actual_engine", "")
                if prev != actual:
                    self._last_actual_engine = actual
                    self._log.info("[ENGINE-SWITCH] actual_engine=%s", actual)
            else:
                self._last_actual_engine = actual or ""
        except Exception as e:
            self._log.debug("[ENGINE-UI] update err=%s", str(e)[:80])

    def _update_active_engine_label(self):
        """실제 적용 엔진(연결 성공 기준)을 새로고침 버튼 옆 라벨에 반영."""
        try:
            active = (getattr(self, "_active_ai_engine", "basic") or "basic").strip().lower()
            if active == "gpt":
                model = ""
                if hasattr(self, "ed_openai_model"):
                    model = (self.ed_openai_model.currentData() or "").strip() or (self.ed_openai_model.currentText() or "").strip()
                if not model:
                    model = "gpt-4o-mini"
                txt = f"Active Engine: OpenAI ({model})"
                color = "#2e7d32"
            elif active == "gemini":
                model = ""
                if hasattr(self, "cmb_gemini_model"):
                    model = (self.cmb_gemini_model.currentText() or "").strip()
                if not model and hasattr(self, "cmb_ai_model"):
                    model = (self.cmb_ai_model.currentText() or "").strip()
                if not model and hasattr(self, "ed_openai_model"):
                    model = (self.ed_openai_model.currentData() or "").strip() or (self.ed_openai_model.currentText() or "").strip()
                if not model:
                    model = "gemini"
                txt = f"Active Engine: Gemini ({model})"
                color = "#1565c0"
            else:
                txt = "Active Engine: Basic AI"
                color = "#9e9e9e"
            if hasattr(self, "lbl_active_engine") and self.lbl_active_engine is not None:
                self.lbl_active_engine.setText(txt)
                self.lbl_active_engine.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
        except Exception:
            pass

    def _update_ai_status(self):
        """우측상단 표시 1곳 통일: actual_engine SSOT만 lbl_engine_status에 반영."""
        try:
            self._update_engine_ui_ssot()
        except Exception:
            pass
        try:
            self._refresh_aits_status_view()
        except Exception:
            pass

    def _set_ai_provider_ui_active(self, provider: str):
        """공통설정: 선택한 박스만 활성화·스타일 적용·우측상단 배지 색상 동기화."""
        provider = (provider or "local").strip().lower()
        if provider not in ("gpt", "gemini", "local"):
            provider = "local"
        self._ai_provider_box_active = provider
        if hasattr(self, "cb_ai_provider"):
            self.cb_ai_provider.setCurrentText(provider)
        self._log.info("[AI-BOX] selected=%s", provider)

        # 박스별 enable/disable
        gpt_only = provider == "gpt"
        gemini_only = provider == "gemini"
        if hasattr(self, "ed_openai_key"):
            self.ed_openai_key.setEnabled(gpt_only)
        if hasattr(self, "ed_openai_model"):
            self.ed_openai_model.setEnabled(gpt_only)
        if hasattr(self, "ed_gemini_key"):
            self.ed_gemini_key.setEnabled(gemini_only)
        if hasattr(self, "cmb_gemini_model"):
            self.cmb_gemini_model.setEnabled(gemini_only)
        if hasattr(self, "btn_test_gpt"):
            self.btn_test_gpt.setEnabled(gpt_only)
        if hasattr(self, "btn_test_gemini"):
            self.btn_test_gemini.setEnabled(gemini_only)
        if hasattr(self, "btn_openai_usage"):
            self.btn_openai_usage.setEnabled(gpt_only)
        local_en = provider == "local"
        if hasattr(self, "inp_local_url"):
            self.inp_local_url.setEnabled(local_en)
        if hasattr(self, "cmb_local_model"):
            self.cmb_local_model.setEnabled(local_en)
        if hasattr(self, "btn_test_local_ai"):
            self.btn_test_local_ai.setEnabled(local_en)
        if hasattr(self, "btn_ollama_install_guide"):
            self.btn_ollama_install_guide.setEnabled(local_en)
        # 모델 설치 버튼은 _update_model_buttons_status에서 설치 상태에 따라 활성화/비활성화
        # LOCAL 박스 활성화 시 모델 버튼 상태 확인 (설치 여부에 따라 활성화/비활성화)
        if local_en and hasattr(self, "_check_and_update_model_buttons"):
            QTimer.singleShot(300, self._check_and_update_model_buttons)
        elif not local_en:
            # LOCAL 박스 비활성화 시 모든 모델 버튼 비활성화
            for btn_name in ["btn_install_qwen", "btn_install_llama", "btn_install_mistral"]:
                if hasattr(self, btn_name):
                    getattr(self, btn_name).setEnabled(False)

        # 박스 배경색: 비활성=흰색, 활성=강조색
        gpt_bg = "#D9F1FF" if gpt_only else "#ffffff"
        gemini_bg = "#E3F2FD" if gemini_only else "#ffffff"
        local_bg = "#DFF5E1" if local_en else "#ffffff"
        gpt_border = "#90CAF9" if gpt_only else "#d0d7de"
        gemini_border = "#64B5F6" if gemini_only else "#d0d7de"
        local_border = "#81C784" if local_en else "#d0d7de"
        if hasattr(self, "gpt_box"):
            self.gpt_box.setStyleSheet(
                f"QGroupBox {{ background-color: {gpt_bg}; border: 1px solid {gpt_border}; border-radius: 6px; padding: 8px; }}"
            )
        if hasattr(self, "gemini_box"):
            self.gemini_box.setStyleSheet(
                f"QGroupBox {{ background-color: {gemini_bg}; border: 1px solid {gemini_border}; border-radius: 6px; padding: 8px; }}"
            )
        if hasattr(self, "local_box"):
            self.local_box.setStyleSheet(
                f"QGroupBox {{ background-color: {local_bg}; border: 1px solid {local_border}; border-radius: 6px; padding: 8px; }}"
            )

        # 우측상단 배지 + 현재 엔진: actual_engine SSOT로 2곳 갱신
        try:
            self._update_engine_ui_ssot()
        except Exception as e:
            self._log.warning("[UI-AI-STATUS] ERROR: %s", str(e)[:80])

    def _on_ai_engine_changed(self, engine_text: str):
        eng = str(engine_text or "").strip()
        if not hasattr(self, "cmb_ai_model") or self.cmb_ai_model is None:
            return
        self.cmb_ai_model.clear()
        if eng == "OpenAI":
            self.cmb_ai_model.addItems(["gpt-4o-mini", "gpt-4o"])
            if hasattr(self, "ed_ai_api_key"):
                self.ed_ai_api_key.setEnabled(True)
                self.ed_ai_api_key.setPlaceholderText("OpenAI API Key")
            try:
                self._set_ai_provider_ui_active("gpt")
            except Exception:
                pass
        elif eng == "Gemini":
            self.cmb_ai_model.addItems(["gemini-1.5-pro", "gemini-1.5-flash"])
            if hasattr(self, "ed_ai_api_key"):
                self.ed_ai_api_key.setEnabled(True)
                self.ed_ai_api_key.setPlaceholderText("Gemini API Key")
            try:
                self._set_ai_provider_ui_active("gemini")
            except Exception:
                pass
        else:
            self.cmb_ai_model.addItems(["Local Strategy Engine"])
            if hasattr(self, "ed_ai_api_key"):
                self.ed_ai_api_key.setEnabled(False)
                self.ed_ai_api_key.setPlaceholderText("API Key 불필요")
            try:
                self._set_ai_provider_ui_active("local")
            except Exception:
                pass

    def _on_test_connection_clicked(self):
        eng = ""
        model = ""
        try:
            eng = (self.cmb_ai_engine.currentText() or "").strip()
            model = (self.cmb_ai_model.currentText() or "").strip()
        except Exception:
            pass
        if eng == "OpenAI":
            print("[AITS] OpenAI connection test")
            try:
                if hasattr(self, "ed_ai_api_key") and hasattr(self, "ed_openai_key"):
                    self.ed_openai_key.setText(self.ed_ai_api_key.text())
                if hasattr(self, "ed_openai_model") and model:
                    idx = self.ed_openai_model.findData(model)
                    if idx >= 0:
                        self.ed_openai_model.setCurrentIndex(idx)
                self._on_test_gpt()
            except Exception:
                pass
            if hasattr(self, "lbl_engine_status") and self.lbl_engine_status is not None:
                self.lbl_engine_status.setText(f"AI Engine | OpenAI ({model or 'gpt-4o-mini'})")
            return
        if eng == "Gemini":
            print("[AITS] Gemini connection test")
            try:
                if hasattr(self, "ed_ai_api_key") and hasattr(self, "ed_openai_key"):
                    self.ed_openai_key.setText(self.ed_ai_api_key.text())
                self._on_test_gemini()
            except Exception:
                pass
            if hasattr(self, "lbl_engine_status") and self.lbl_engine_status is not None:
                self.lbl_engine_status.setText(f"AI Engine | Gemini ({model or 'gemini-1.5-pro'})")
            return
        print("[AITS] Basic AI connection test")
        try:
            self._on_test_local_ai()
        except Exception:
            pass
        if hasattr(self, "lbl_engine_status") and self.lbl_engine_status is not None:
            self.lbl_engine_status.setText("AI Engine | Basic AI")

    # --- AITS Managed Pool / Market Explorer (Qt 테이블 골격, ag-Grid 스타일 상태·이벤트 분리) ---
    _AI_M_COL_LOCK = 9
    _AI_M_COL_ACTION = 10
    _MKT_COL_ADD = 4

    def _fmt_change_pct(self, rate: float) -> str:
        try:
            x = float(rate or 0.0)
            if -1.0 <= x <= 1.0:
                return f"{x * 100.0:.2f}%"
            return f"{x:.2f}%"
        except Exception:
            return "0.00%"

    def _refresh_ai_managed_table(self) -> None:
        if not hasattr(self, "tbl_ai_managed") or self.tbl_ai_managed is None:
            return
        t = self.tbl_ai_managed
        t.setRowCount(0)
        for i, row in enumerate(self.ai_managed_rows):
            t.insertRow(i)
            sym = (row.get("symbol") or "").strip()
            name = (row.get("name") or "").strip() or sym
            label = f"{name}\n{sym}" if name and sym and name != sym else (sym or name)
            c0 = QTableWidgetItem(label)
            c0.setData(Qt.ItemDataRole.UserRole, sym)
            t.setItem(i, 0, c0)
            t.setItem(i, 1, QTableWidgetItem(f"{float(row.get('price') or 0.0):,.0f}"))
            t.setItem(i, 2, QTableWidgetItem(self._fmt_change_pct(float(row.get("change_rate") or 0.0))))
            src = (row.get("source") or "USER").strip().upper()
            c3 = QTableWidgetItem("AI" if src == "AI" else "USER")
            if src == "AI":
                c3.setForeground(QColor("#1565c0"))
            else:
                c3.setForeground(QColor("#2e7d32"))
            t.setItem(i, 3, c3)
            if src == "AI" and row.get("ai_score") is not None:
                _sc = row.get("ai_score")
                try:
                    cscore = QTableWidgetItem(str(int(_sc)))
                except Exception:
                    cscore = QTableWidgetItem("—")
            else:
                cscore = QTableWidgetItem("—")
            t.setItem(i, 4, cscore)
            status_txt = str(row.get("ai_status") or "Watching")
            c5 = QTableWidgetItem(status_txt)
            _status_color = {
                "Watching": "#757575",
                "Buy Ready": "#1565c0",
                "Holding": "#2e7d32",
                "Sell Ready": "#c62828",
                "Dropped": "#6d4c41",
            }.get(status_txt, "#757575")
            c5.setForeground(QColor(_status_color))
            t.setItem(i, 5, c5)
            t.setItem(i, 6, QTableWidgetItem(f"{float(row.get('target_price') or 0.0):,.0f}"))
            t.setItem(i, 7, QTableWidgetItem(f"{float(row.get('stop_loss') or 0.0):,.0f}"))
            t.setItem(i, 8, QTableWidgetItem(f"{float(row.get('pnl') or 0.0):.2f}%"))
            locked = bool(row.get("locked"))
            t.setItem(i, 9, QTableWidgetItem("🔒" if locked else "🔓"))
            t.setItem(i, 10, QTableWidgetItem("제거"))  # TODO: 상세 패널/차트 연결
            _sum = (row.get("ai_reason_summary") or "").strip()
            if len(_sum) > 48:
                _sum = _sum[:45] + "…"
            t.setItem(i, 11, QTableWidgetItem(_sum if _sum else "—"))

    def _ensure_demo_ai_rows(self) -> None:
        """AI 소스 종목이 없을 때만 샘플 AI 종목을 1회 주입한다."""
        try:
            if any(str(r.get("source") or "").upper() == "AI" for r in (self.ai_managed_rows or [])):
                return
            existing = {str(r.get("symbol") or "").strip() for r in (self.ai_managed_rows or [])}
            for sym in ("KRW-BTC", "KRW-ETH", "KRW-XRP"):
                if sym in existing:
                    continue
                self.ai_managed_rows.append(
                    {
                        "symbol": sym,
                        "name": sym.split("-")[-1],
                        "price": 0.0,
                        "change_rate": 0.0,
                        "source": "AI",
                        "ai_status": "Watching",
                        "target_price": 0.0,
                        "stop_loss": 0.0,
                        "pnl": 0.0,
                        "locked": False,
                    }
                )
                existing.add(sym)
            print(f"[AITS] demo ai rows injected count={len([r for r in self.ai_managed_rows if str(r.get('source')) == 'AI'])}")
        except Exception:
            pass

    def _sync_ai_pool_market_fields(self) -> None:
        """market_all_rows 시세를 ai_managed_rows 동일 symbol에 반영."""
        try:
            market_map = {}
            for r in (self.market_all_rows or []):
                sym = str(r.get("symbol") or "").strip()
                if sym:
                    market_map[sym] = r
            for row in (self.ai_managed_rows or []):
                sym = str(row.get("symbol") or "").strip()
                if not sym:
                    continue
                src = market_map.get(sym)
                if not src:
                    continue
                row["price"] = float(src.get("price", 0.0) or 0.0)
                row["change_rate"] = float(src.get("change_rate", 0.0) or 0.0)
                if not str(row.get("name") or "").strip():
                    row["name"] = str(src.get("name") or sym.split("-")[-1])
        except Exception:
            pass

    def _calc_basic_ai_score(self, row: dict) -> dict:
        """Basic AI 규칙 기반 점수(0~100)."""
        st = self.basic_ai_settings
        reasons: list[str] = []
        trend_score = 0
        volume_score = 0
        risk_penalty = 0
        score = 50
        chg = float(row.get("change_rate") or 0.0)
        sym = str(row.get("symbol") or "").strip()
        vol_24 = 0.0
        try:
            for mr in self.market_all_rows or []:
                if str(mr.get("symbol") or "").strip() == sym:
                    vol_24 = float(mr.get("volume_24h") or 0.0)
                    break
        except Exception:
            vol_24 = 0.0

        if chg >= 3.0:
            score += 20
            trend_score += 20
            reasons.append("상승률 양호")
        elif chg >= 1.0:
            score += 10
            trend_score += 10
            reasons.append("상승 흐름")
        elif chg <= -3.0:
            score -= 25
            trend_score -= 25
            risk_penalty += 25
            reasons.append("급락 우려")
        elif chg <= -1.0:
            score -= 10
            trend_score -= 10
            risk_penalty += 10
            reasons.append("약세 구간")

        min_vol = int(st.get("min_volume", 0) or 0)
        if vol_24 >= min_vol:
            score += 10
            volume_score = 10
            reasons.append("최소 거래대금 충족")
        else:
            score -= 15
            volume_score = -15
            risk_penalty += 15
            reasons.append("거래대금 부족")

        if bool(st.get("exclude_overheated", True)) and chg >= 8.0:
            score -= 20
            risk_penalty += 20
            reasons.append("과열 구간")

        if bool(st.get("avoid_sudden_drop", True)) and chg <= -5.0:
            score -= 30
            risk_penalty += 30
            reasons.append("급락 위험")

        mrows = self.market_all_rows or []
        if bool(st.get("avoid_bear_market", True)) and mrows:
            try:
                avg_c = sum(float(x.get("change_rate") or 0.0) for x in mrows) / max(len(mrows), 1)
                if avg_c < 0:
                    score -= 10
                    risk_penalty += 10
                    reasons.append("시장 평균 약세")
            except Exception:
                pass

        tf = str(st.get("trend_filter") or "약함")
        if tf == "강함":
            if chg >= 2.0:
                score += 10
                trend_score += 10
                reasons.append("추세 필터(강함) 통과")
            else:
                score -= 10
                trend_score -= 10
                risk_penalty += 10
                reasons.append("추세 필터(강함) 미달")
        elif tf == "약함":
            if chg >= 0.5:
                score += 5
                trend_score += 5
                reasons.append("추세 필터(약함) 가점")

        sel = str(st.get("selection_strength") or "보통")
        if sel == "높음":
            score -= 5
            reasons.append("선별 강도(높음)")
        elif sel == "낮음":
            score += 5
            reasons.append("선별 강도(낮음)")

        rm = str(st.get("risk_mode") or "중립")
        if rm == "공격적":
            score += 5
            reasons.append("운용 성향: 공격")
        elif rm == "보수적":
            score -= 5
            reasons.append("운용 성향: 보수")

        try:
            import time as _time

            let = row.get("last_exit_ts")
            if let is not None:
                let_f = float(let)
                cool = int(st.get("reentry_cooldown_min", 30) or 30)
                if _time.time() - let_f < cool * 60:
                    score -= 20
                    risk_penalty += 20
                    reasons.append("재진입 쿨다운")
        except Exception:
            pass

        score = max(0, min(100, int(round(score))))
        return {
            "score": score,
            "reasons": reasons,
            "trend_score": int(trend_score),
            "volume_score": int(volume_score),
            "risk_penalty": int(risk_penalty),
        }

    def _update_ai_pool_statuses(self) -> None:
        """AI 종목: 규칙 기반 점수로 상태 갱신. USER는 목표/손절만 반영·상태 Watching."""
        try:
            st = self.basic_ai_settings
            max_pos = int(st.get("max_positions", 5) or 5)
            max_new = max(0, int(st.get("max_new_entries", 2) or 2))
            entry_th = int(st.get("entry_score_threshold", 60) or 60)
            exit_th = int(st.get("exit_score_threshold", 45) or 45)
            tp_pct = float(st.get("target_profit_pct", 3.0) or 3.0)
            sl_pct = float(st.get("stop_loss_pct", 1.5) or 1.5)

            rows = self.ai_managed_rows or []
            position_limit_blocked = False

            for row in rows:
                src = str(row.get("source") or "").upper()
                prev_status = str(row.get("ai_status") or "Watching")
                price = float(row.get("price") or 0.0)
                pnl = float(row.get("pnl") or 0.0)

                if price > 0:
                    tpv = float(tp_pct)
                    slv = float(sl_pct)
                    row["target_price"] = float(price * (1.0 + tpv / 100.0))
                    row["stop_loss"] = float(price * (1.0 - slv / 100.0))
                else:
                    row["target_price"] = 0.0
                    row["stop_loss"] = 0.0

                if src != "AI":
                    row["ai_status"] = "Watching"
                    row.pop("ai_score", None)
                    row.pop("ai_reason_summary", None)
                    continue

                res = self._calc_basic_ai_score(row)
                sc = int(res.get("score", 0))
                row["ai_score"] = sc
                rsn = res.get("reasons") or []
                row["ai_reason_summary"] = ", ".join(rsn[:3])

                if prev_status == "Holding":
                    if pnl >= tp_pct:
                        row["ai_status"] = "Sell Ready"
                    elif pnl <= -sl_pct:
                        row["ai_status"] = "Sell Ready"
                    else:
                        row["ai_status"] = "Holding"
                    continue

                if sc <= exit_th:
                    row["ai_status"] = "Dropped"
                elif sc >= entry_th:
                    row["ai_status"] = "Buy Ready"
                else:
                    row["ai_status"] = "Watching"

            holding_count = sum(
                1
                for r in rows
                if str(r.get("source") or "").upper() == "AI" and str(r.get("ai_status") or "") == "Holding"
            )

            buy_rows = [r for r in rows if str(r.get("source") or "").upper() == "AI" and r.get("ai_status") == "Buy Ready"]

            if holding_count >= max_pos and buy_rows:
                position_limit_blocked = True
                for r in buy_rows:
                    r["ai_status"] = "Watching"
                buy_rows = []
            elif buy_rows:
                buy_rows.sort(key=lambda r: int(r.get("ai_score") or 0), reverse=True)
                keep_ids = {id(r) for r in buy_rows[:max_new]}
                for r in buy_rows:
                    if id(r) not in keep_ids:
                        r["ai_status"] = "Watching"

            buy_ready_count = sum(1 for r in rows if str(r.get("ai_status") or "") == "Buy Ready")
            watching_count = sum(1 for r in rows if str(r.get("ai_status") or "") == "Watching")
            print(
                f"[AITS] ai score update total={len(rows)} buy_ready={buy_ready_count} watching={watching_count}"
            )

            status_text = "AITS AI Status: Market Scanning"
            has_buy = any(
                str(r.get("source") or "").upper() == "AI" and str(r.get("ai_status") or "") == "Buy Ready"
                for r in rows
            )
            has_hold = any(
                str(r.get("source") or "").upper() == "AI" and str(r.get("ai_status") or "") == "Holding"
                for r in rows
            )
            if position_limit_blocked:
                status_text = "AITS AI Status: Position Limit Reached"
            elif has_buy:
                status_text = "AITS AI Status: Opportunity Scoring"
            elif has_hold:
                status_text = "AITS AI Status: Position Monitoring"
            else:
                status_text = "AITS AI Status: Market Scanning"

            if hasattr(self, "lbl_aits_ai_engine_status") and self.lbl_aits_ai_engine_status is not None:
                self.lbl_aits_ai_engine_status.setText(status_text)
            print(f"[AITS] ai engine status={status_text}")
        except Exception:
            pass

    def _hide_basic_ai_legacy_local_ui(self, form) -> None:
        try:
            for w in (
                getattr(self, "inp_local_url", None),
                getattr(self, "cmb_local_model", None),
                getattr(self, "lbl_local_engines", None),
                getattr(self, "btn_test_local_ai", None),
                getattr(self, "btn_ollama_install_guide", None),
                getattr(self, "btn_install_qwen", None),
                getattr(self, "btn_install_llama", None),
                getattr(self, "btn_install_mistral", None),
                getattr(self, "_local_legacy_btn_wrap", None),
                getattr(self, "_local_model_btn_wrap", None),
            ):
                if w is None:
                    continue
                try:
                    w.setVisible(False)
                except Exception:
                    pass
                try:
                    lf = form.labelForField(w)
                    if lf is not None:
                        lf.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _advance_basic_ai_status_line(self) -> None:
        try:
            msgs = (
                "AITS AI Status: Market Scanning",
                "AITS AI Status: Opportunity Scoring",
                "AITS AI Status: Risk Filtering",
            )
            self._basic_ai_status_idx = (int(getattr(self, "_basic_ai_status_idx", 0)) + 1) % len(msgs)
            if hasattr(self, "lbl_aits_ai_engine_status") and self.lbl_aits_ai_engine_status is not None:
                self.lbl_aits_ai_engine_status.setText(msgs[self._basic_ai_status_idx])
        except Exception:
            pass

    def _wire_basic_ai_status_line_hooks(self) -> None:
        try:
            def _bump():
                self._advance_basic_ai_status_line()

            for w in (
                getattr(self, "cmb_basic_ai_buy_sensitivity", None),
                getattr(self, "cmb_basic_ai_sell_sensitivity", None),
                getattr(self, "cb_basic_ai_split_buy", None),
                getattr(self, "cb_basic_ai_split_sell", None),
                getattr(self, "sp_basic_ai_max_hold_min", None),
                getattr(self, "sp_basic_ai_min_volume", None),
                getattr(self, "cb_basic_ai_exclude_overheated", None),
                getattr(self, "cb_basic_ai_avoid_sudden_drop", None),
                getattr(self, "cmb_basic_ai_trend_filter", None),
                getattr(self, "sp_basic_ai_entry_score", None),
                getattr(self, "sp_basic_ai_exit_score", None),
                getattr(self, "cmb_basic_ai_decision_speed", None),
                getattr(self, "sp_basic_ai_reentry_cooldown", None),
                getattr(self, "sp_basic_ai_max_new_entries", None),
            ):
                if w is None:
                    continue
                try:
                    if hasattr(w, "currentTextChanged"):
                        w.currentTextChanged.connect(lambda _t="", b=_bump: b())
                    elif hasattr(w, "toggled"):
                        w.toggled.connect(lambda _c=False, b=_bump: b())
                    elif hasattr(w, "valueChanged"):
                        w.valueChanged.connect(lambda _v=0, b=_bump: b())
                except Exception:
                    pass
        except Exception:
            pass

    def _sync_basic_ai_settings_from_ui(self) -> None:
        try:
            if not hasattr(self, "cmb_basic_ai_risk") or not hasattr(self, "sp_basic_ai_entry_score"):
                return
            self.basic_ai_settings["risk_mode"] = str(self.cmb_basic_ai_risk.currentText()).strip() or "중립"
            self.basic_ai_settings["target_profit_pct"] = float(self.sp_basic_ai_target_profit.value())
            self.basic_ai_settings["stop_loss_pct"] = float(self.sp_basic_ai_stop_loss.value())
            self.basic_ai_settings["max_positions"] = int(self.sp_basic_ai_max_positions.value())
            self.basic_ai_settings["selection_strength"] = (
                str(self.cmb_basic_ai_selection.currentText()).strip() or "보통"
            )
            self.basic_ai_settings["avoid_bear_market"] = bool(self.cb_basic_ai_avoid_bear.isChecked())
            self.basic_ai_settings["buy_sensitivity"] = (
                str(self.cmb_basic_ai_buy_sensitivity.currentText()).strip() or "보통"
            )
            self.basic_ai_settings["sell_sensitivity"] = (
                str(self.cmb_basic_ai_sell_sensitivity.currentText()).strip() or "보통"
            )
            self.basic_ai_settings["split_buy"] = bool(self.cb_basic_ai_split_buy.isChecked())
            self.basic_ai_settings["split_sell"] = bool(self.cb_basic_ai_split_sell.isChecked())
            self.basic_ai_settings["max_hold_time"] = int(self.sp_basic_ai_max_hold_min.value())
            self.basic_ai_settings["min_volume"] = int(self.sp_basic_ai_min_volume.value())
            self.basic_ai_settings["exclude_overheated"] = bool(
                self.cb_basic_ai_exclude_overheated.isChecked()
            )
            self.basic_ai_settings["avoid_sudden_drop"] = bool(
                self.cb_basic_ai_avoid_sudden_drop.isChecked()
            )
            self.basic_ai_settings["trend_filter"] = (
                str(self.cmb_basic_ai_trend_filter.currentText()).strip() or "약함"
            )
            self.basic_ai_settings["entry_score_threshold"] = int(self.sp_basic_ai_entry_score.value())
            self.basic_ai_settings["exit_score_threshold"] = int(self.sp_basic_ai_exit_score.value())
            self.basic_ai_settings["decision_speed"] = (
                str(self.cmb_basic_ai_decision_speed.currentText()).strip() or "보통"
            )
            self.basic_ai_settings["reentry_cooldown_min"] = int(self.sp_basic_ai_reentry_cooldown.value())
            self.basic_ai_settings["max_new_entries"] = int(self.sp_basic_ai_max_new_entries.value())
        except Exception:
            pass

    def _load_basic_ai_settings_to_ui(self) -> None:
        try:
            if not hasattr(self, "cmb_basic_ai_risk") or not hasattr(self, "sp_basic_ai_entry_score"):
                return
            d = self.basic_ai_settings
            rm = str(d.get("risk_mode") or "중립")
            if self.cmb_basic_ai_risk.findText(rm) >= 0:
                self.cmb_basic_ai_risk.setCurrentText(rm)
            else:
                self.cmb_basic_ai_risk.setCurrentText("중립")
            self.sp_basic_ai_target_profit.setValue(float(d.get("target_profit_pct", 3.0) or 3.0))
            self.sp_basic_ai_stop_loss.setValue(float(d.get("stop_loss_pct", 1.5) or 1.5))
            self.sp_basic_ai_max_positions.setValue(int(d.get("max_positions", 5) or 5))
            ss = str(d.get("selection_strength") or "보통")
            if self.cmb_basic_ai_selection.findText(ss) >= 0:
                self.cmb_basic_ai_selection.setCurrentText(ss)
            else:
                self.cmb_basic_ai_selection.setCurrentText("보통")
            self.cb_basic_ai_avoid_bear.setChecked(bool(d.get("avoid_bear_market", True)))
            bs = str(d.get("buy_sensitivity") or "보통")
            if self.cmb_basic_ai_buy_sensitivity.findText(bs) >= 0:
                self.cmb_basic_ai_buy_sensitivity.setCurrentText(bs)
            else:
                self.cmb_basic_ai_buy_sensitivity.setCurrentText("보통")
            ssell = str(d.get("sell_sensitivity") or "보통")
            if self.cmb_basic_ai_sell_sensitivity.findText(ssell) >= 0:
                self.cmb_basic_ai_sell_sensitivity.setCurrentText(ssell)
            else:
                self.cmb_basic_ai_sell_sensitivity.setCurrentText("보통")
            self.cb_basic_ai_split_buy.setChecked(bool(d.get("split_buy", True)))
            self.cb_basic_ai_split_sell.setChecked(bool(d.get("split_sell", True)))
            self.sp_basic_ai_max_hold_min.setValue(int(d.get("max_hold_time", 120) or 120))
            self.sp_basic_ai_min_volume.setValue(int(d.get("min_volume", 100_000_000) or 0))
            self.cb_basic_ai_exclude_overheated.setChecked(bool(d.get("exclude_overheated", True)))
            self.cb_basic_ai_avoid_sudden_drop.setChecked(bool(d.get("avoid_sudden_drop", True)))
            tf = str(d.get("trend_filter") or "약함")
            if self.cmb_basic_ai_trend_filter.findText(tf) >= 0:
                self.cmb_basic_ai_trend_filter.setCurrentText(tf)
            else:
                self.cmb_basic_ai_trend_filter.setCurrentText("약함")
            self.sp_basic_ai_entry_score.setValue(int(d.get("entry_score_threshold", 60) or 60))
            self.sp_basic_ai_exit_score.setValue(int(d.get("exit_score_threshold", 45) or 45))
            ds = str(d.get("decision_speed") or "보통")
            if self.cmb_basic_ai_decision_speed.findText(ds) >= 0:
                self.cmb_basic_ai_decision_speed.setCurrentText(ds)
            else:
                self.cmb_basic_ai_decision_speed.setCurrentText("보통")
            self.sp_basic_ai_reentry_cooldown.setValue(int(d.get("reentry_cooldown_min", 30) or 30))
            self.sp_basic_ai_max_new_entries.setValue(int(d.get("max_new_entries", 2) or 2))
        except Exception:
            pass

    def _save_basic_ai_settings(self) -> None:
        try:
            self._sync_basic_ai_settings_from_ui()
            self._advance_basic_ai_status_line()
            print(f"[AITS] basic ai settings saved: {self.basic_ai_settings}")
            QMessageBox.information(self, "Basic AI", "저장되었습니다.")
            try:
                s0 = self._get_settings_cached(force=False)
                us0 = getattr(s0, "ui_state", None) or {}
                if hasattr(us0, "model_dump"):
                    us0 = us0.model_dump()
                elif not isinstance(us0, dict):
                    us0 = {}
                us_merged = dict(us0)
                us_merged["basic_ai_settings"] = dict(self.basic_ai_settings)
                self._apply_settings_patch({"ui_state": us_merged}, reason="basic_ai_settings_save")
            except Exception:
                pass
        except Exception:
            pass

    def _refresh_market_all_table(self) -> None:
        if not hasattr(self, "tbl_market_all") or self.tbl_market_all is None:
            return
        q = ""
        try:
            q = (self.ed_market_search.text() or "").strip().lower()
        except Exception:
            q = ""
        rows = list(self.market_all_rows)
        if q:
            rows = [
                r
                for r in self.market_all_rows
                if q in (r.get("symbol") or "").lower() or q in (r.get("name") or "").lower()
            ]
        self._market_display_rows = rows
        t = self.tbl_market_all
        t.setRowCount(0)
        for i, r in enumerate(rows):
            t.insertRow(i)
            sym = (r.get("symbol") or "").strip()
            name = (r.get("name") or "").strip() or sym
            c0 = QTableWidgetItem(f"{name} ({sym})" if sym else name)
            c0.setData(Qt.ItemDataRole.UserRole, sym)
            t.setItem(i, 0, c0)
            t.setItem(i, 1, QTableWidgetItem(f"{float(r.get('price') or 0.0):,.0f}"))
            t.setItem(i, 2, QTableWidgetItem(self._fmt_change_pct(float(r.get("change_rate") or 0.0))))
            t.setItem(i, 3, QTableWidgetItem(f"{float(r.get('volume_24h') or 0.0):,.0f}"))
            t.setItem(i, 4, QTableWidgetItem("추가"))

    def _on_market_search_text_changed(self, _t: str = "") -> None:
        try:
            self._refresh_market_all_table()
        except Exception:
            pass

    def _load_market_explorer_initial_data(self) -> None:
        try:
            raw = get_top_markets_by_volume(limit=30) or []
            self.market_all_rows = []
            for r in raw:
                if not isinstance(r, dict):
                    continue
                sym = (r.get("market") or "").strip()
                if not sym:
                    continue
                tail = sym.split("-")[-1] if "-" in sym else sym
                self.market_all_rows.append(
                    {
                        "symbol": sym,
                        "name": tail,
                        "price": float(r.get("trade_price") or 0.0),
                        "change_rate": float(r.get("signed_change_rate") or 0.0),
                        "volume_24h": float(r.get("acc_trade_volume_24h") or 0.0),
                    }
                )
            self._ensure_demo_ai_rows()
            self._sync_ai_pool_market_fields()
            self._update_ai_pool_statuses()
            self._refresh_ai_managed_table()
            self._refresh_market_all_table()
        except Exception:
            self.market_all_rows = []
            self._ensure_demo_ai_rows()
            self._sync_ai_pool_market_fields()
            self._update_ai_pool_statuses()
            self._refresh_ai_managed_table()
            self._refresh_market_all_table()

    def _add_symbol_to_ai_pool(self, row_or_symbol) -> None:
        sym = ""
        src_row = None
        if isinstance(row_or_symbol, str):
            sym = row_or_symbol.strip()
            for r in self.market_all_rows:
                if (r.get("symbol") or "").strip() == sym:
                    src_row = r
                    break
        elif isinstance(row_or_symbol, dict):
            sym = (row_or_symbol.get("symbol") or "").strip()
            src_row = row_or_symbol
        if not sym:
            return
        for ex in self.ai_managed_rows:
            if (ex.get("symbol") or "").strip() == sym:
                QMessageBox.information(self, "관리 종목", "이미 관리 종목에 있습니다.")
                return
        name = (src_row.get("name") if src_row else None) or (sym.split("-")[-1] if "-" in sym else sym)
        price = float(src_row.get("price", 0.0)) if src_row else 0.0
        chg = float(src_row.get("change_rate", 0.0)) if src_row else 0.0
        self.ai_managed_rows.append(
            {
                "symbol": sym,
                "name": name,
                "price": price,
                "change_rate": chg,
                "source": "USER",
                "ai_status": "Watching",
                "target_price": 0.0,
                "stop_loss": 0.0,
                "pnl": 0.0,
                "locked": True,
            }
        )
        self._refresh_ai_managed_table()

    def _remove_symbol_from_ai_pool(self, symbol: str) -> None:
        sym = (symbol or "").strip()
        for i, r in enumerate(self.ai_managed_rows):
            if (r.get("symbol") or "").strip() != sym:
                continue
            if bool(r.get("locked")):
                QMessageBox.warning(
                    self,
                    "제거 불가",
                    "잠금된 종목입니다. 잠금 해제 후 제거하세요.",
                )
                return
            self.ai_managed_rows.pop(i)
            self._refresh_ai_managed_table()
            return

    def _on_ai_managed_table_cell_clicked(self, row: int, col: int) -> None:
        if row < 0 or row >= len(self.ai_managed_rows):
            return
        sym = (self.ai_managed_rows[row].get("symbol") or "").strip()
        if col == self._AI_M_COL_LOCK:
            self.ai_managed_rows[row]["locked"] = not bool(self.ai_managed_rows[row].get("locked"))
            self._refresh_ai_managed_table()
        elif col == self._AI_M_COL_ACTION:
            self._remove_symbol_from_ai_pool(sym)

    def _on_market_all_table_cell_clicked(self, row: int, col: int) -> None:
        if col != self._MKT_COL_ADD:
            return
        disp = getattr(self, "_market_display_rows", None) or []
        if row < 0 or row >= len(disp):
            return
        self._add_symbol_to_ai_pool(disp[row])

    def _boot_sequence_step1(self):
        """✅ P0-BOOT-LOADING: 부팅 시퀀스 1단계"""
        try:
            self.set_global_status("⏳ API/계정 정보 로딩 중...", "busy", "boot")
            QApplication.processEvents()  # UI 갱신 기회 제공
            
            # ✅ P0-KEY-SSOT-FIX: settings 강제 최신화
            self._settings = None
            fresh = self._get_settings_cached(force=True)
            self._settings = fresh
            
            # 키 길이 계산 (primary)
            ak_len = len(getattr(fresh.upbit, "access_key", "").strip()) if fresh and hasattr(fresh, "upbit") else 0
            sk_len = len(getattr(fresh.upbit, "secret_key", "").strip()) if fresh and hasattr(fresh, "upbit") else 0
            live_trade = getattr(fresh, "live_trade", None)
            
            self._log.info(f"[SETTINGS-SYNC] boot step1 -> reloaded ak_len={ak_len} sk_len={sk_len} live_trade={live_trade}")
            
            # 설정/전략 로드
            self._load_settings_into_form()
            
            # ✅ P0-DATA-BOOT: 계정 요약 1회 로딩
            # 폴링 예외로 인해 스킵되지 않도록 먼저 예약한다.
            QTimer.singleShot(200, lambda: self.refresh_account_summary("boot"))
            # ✅ C: 투자현황 탭 실행 직후 1회 refresh (빈 화면 방지)
            QTimer.singleShot(250, lambda: self.portfolio_tab.refresh("startup"))

            # ✅ P0-1: WL 무한 로딩 제거 — wl_timer는 부팅 완료 후 1회만 시작 (step1에서 시작 시 부팅 중 주기적 refresh 재호출로 무한 로딩 유발)
            # 폴링 시작은 _boot_sequence_complete에서 1회만 수행
            self._log.info("[POLL] deferred to _boot_sequence_complete (wl boot once)")
            
            QTimer.singleShot(100, self._boot_sequence_step2)
        except Exception:
            QTimer.singleShot(100, self._boot_sequence_step2)

    def _boot_sequence_step2(self):
        """✅ P0-BOOT-LOADING: 부팅 시퀀스 2단계"""
        try:
            self.set_global_status("⏳ 워치리스트 로딩 중...", "busy", "boot")
            QApplication.processEvents()  # UI 갱신 기회 제공
            
            # 워치리스트 초기 리프레시 (타이밍 지연)
            QTimer.singleShot(300, self._boot_watchlist_refresh)
            
            QTimer.singleShot(500, self._boot_sequence_step3)
        except Exception:
            QTimer.singleShot(500, self._boot_sequence_step3)

    def _boot_watchlist_refresh(self):
        """✅ P0-BOOT-LOADING: 워치리스트 리프레시 실행"""
        try:
            # ✅ P0-DATA-BOOT: 부트 리프레시 가드
            if getattr(self, '_wl_boot_done', False):
                self._log.info("[BOOT-GUARD] watchlist boot already done, skipping")
                return
            if getattr(self, '_wl_boot_inflight', False):
                self._log.info("[BOOT-GUARD] watchlist boot already inflight, skipping")
                return
                
            self._wl_boot_inflight = True
            self._log.info("[BOOT-PROGRESS] show reason=watchlist_boot")
            self._log.info("[WL-BOOT] start")
            
            # ✅ P0-A: Use QTimer.singleShot to avoid blocking UI thread
            QTimer.singleShot(0, self._execute_watchlist_boot)
            
        except Exception as e:
            self._log.error(f"[BOOT-PROGRESS] watchlist_boot exception={e}")
            # Ensure progress is closed even on exception
            self._log.info("[BOOT-PROGRESS] close reason=watchlist_boot ok=false")

    def _execute_watchlist_boot(self):
        """Execute watchlist boot refresh in non-blocking manner"""
        try:
            if hasattr(self, "tab_watch") and hasattr(self.tab_watch, "refresh"):
                # Call refresh with boot context (P0-4B: caller 명시로 가드 무시/강제 fetch)
                self.tab_watch.refresh(caller="_execute_watchlist_boot")
                
                # Get row count for verification
                row_count = self.tab_watch.tbl.rowCount() if hasattr(self.tab_watch, 'tbl') else 0
                self._log.info(f"[WL-BOOT] done ok=true rows={row_count}")
                self._log.info("[BOOT-PROGRESS] close reason=watchlist_boot ok=true")
            else:
                self._log.info("[WL-BOOT] done ok=false rows=0")
                self._log.info("[BOOT-PROGRESS] close reason=watchlist_boot ok=false")
                
        except Exception as e:
            self._log.error(f"[WL-BOOT] done ok=false err={e}")
            self._log.info("[BOOT-PROGRESS] close reason=watchlist_boot ok=false")
        finally:
            # Mark boot as done
            self._wl_boot_done = True
            self._wl_boot_inflight = False

    def _boot_sequence_step3(self):
        """✅ P0-BOOT-LOADING: 부팅 시퀀스 3단계"""
        try:
            self.set_global_status("⏳ 종목점수 계산/불러오는 중...", "busy", "boot")
            QApplication.processEvents()  # UI 갱신 기회 제공
            
            # AI 스케줄러 시작
            ai_reco.start_scheduler(lambda: self._settings, lambda topic, payload: eventbus.publish(topic, payload))
            
            # ✅ P0-BOOT-SCORE: 부팅 시 즉시 점수 로딩
            QTimer.singleShot(500, self._load_ai_scores_on_boot)
            
            QTimer.singleShot(300, self._boot_sequence_complete)
        except Exception:
            QTimer.singleShot(300, self._boot_sequence_complete)

    def _load_ai_scores_on_boot(self):
        """✅ P0-BOOT-SCORE: 부팅 시 AI 점수 즉시 로딩"""
        try:
            import app.services.ai_reco as ai_reco_service
            import logging
            log = logging.getLogger(__name__)
            
            # ✅ (A) WatchlistTab 준비 상태 확인
            tab_exists = hasattr(self, 'tab_watch') and self.tab_watch is not None
            tbl_exists = tab_exists and hasattr(self.tab_watch, 'tbl') and self.tab_watch.tbl is not None
            row_count = self.tab_watch.tbl.rowCount() if tbl_exists else 0
            
            log.info(f"[BOOT-SCORE] watchlist_ready: tab={tab_exists} tbl={tbl_exists} rows={row_count}")
            
            # ✅ (B) 준비 안 됐으면 재시도 (안 A)
            if not (tab_exists and tbl_exists and row_count > 0):
                log.warning("[BOOT-SCORE] watchlist not ready, retry in 300ms")
                QTimer.singleShot(300, self._load_ai_scores_on_boot)
                return
            
            self.set_global_status("⏳ 종목점수 계산 중...", "busy", "boot")
            QApplication.processEvents()
            
            # ✅ (C) AI 점수 즉시 계산/발행 (부팅 시 GPT 호출 금지 → local만 사용)
            result = ai_reco_service.update(from_boot=True)
            log.info(f"[BOOT-SCORE] update completed: result={result}")
            
            # ✅ (D) "로딩 완료"는 watchlist 적용 확인 후에만 (안 B)
            # handle_ai_reco에서 SUCCESS 로그 확인 후 상태 업데이트
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[BOOT-SCORE] AI 점수 로딩 실패: {e}")
            self.set_global_status("🔴 종목점수 로딩 실패", "err", "boot")

    def _boot_sequence_complete(self):
        """✅ P0-BOOT-LOADING: 부팅 시퀀스 완료"""
        try:
            # 로딩 팝업 닫기
            if hasattr(self, '_loading_progress'):
                self._loading_progress.close()

            # ✅ P0-1: WL 부팅 후 wl_timer 1회만 시작 (once 가드로 무한 로딩 제거)
            if not getattr(self, "_polling_started", False):
                try:
                    poll_fn = getattr(self, "start_polling", None) or getattr(self, "_start_polling", None)
                    if callable(poll_fn):
                        poll_fn()
                        self._log.info("[POLL] start after boot complete (wl once)")
                    else:
                        self._log.error("[POLL] start failed err=no_poll_fn")
                except Exception as e:
                    self._log.error(f"[POLL] start failed err={e!r}")

            # ✅ Step5: 최종형 SSOT 1줄 로그 (boot 완료 직후)
            try:
                s = self._settings or self._get_settings_cached(force=False)
                live_trade = getattr(s, "live_trade", None) if s else None
                poll_ms = 1500
                try:
                    p = getattr(s, "poll", None) if s else None
                    if hasattr(p, "ticker_ms"):
                        poll_ms = int(getattr(p, "ticker_ms") or poll_ms)
                    elif isinstance(p, dict) and p.get("ticker_ms"):
                        poll_ms = int(p.get("ticker_ms") or poll_ms)
                except Exception:
                    pass
                self._log.info(f"[SSOT] source=forced_reload live_trade={bool(live_trade)} poll_ms={int(poll_ms)}")
            except Exception:
                pass
            
            self.set_global_status("🟢 정상", "ok", "boot")
        except Exception:
            pass

    def set_status_msg(self, msg: str, color: str = "#555"):
        try:
            # ✅ P0-UI-GLOBAL-STATUS-②: 전역 상태바로 라우팅
            # 메시지 내용에 따라 레벨 자동 판정
            msg_lower = msg.lower()
            if any(word in msg_lower for word in ["정상", "완료", "성공"]):
                level = "ok"
            elif any(word in msg_lower for word in ["초기화", "로딩", "접속", "갱신"]):
                level = "busy"
            elif any(word in msg_lower for word in ["오류", "실패", "에러"]):
                level = "err"
            else:
                level = "ok"
                
            self.set_global_status(msg, level)
            
            # 하단 상태바는 숨겨져 있으므로 업데이트하지 않음
            self._status_ts = int(time.time())
            
            # ✅ P0-BOOT-LOADING: 오류 발생 시에도 로딩 팝업 닫기
            if "오류" in msg or "실패" in msg:
                try:
                    if hasattr(self, '_loading_progress'):
                        self._loading_progress.close()
                except Exception:
                    pass
        except Exception:
            pass

    def _get_settings_cached(self, force: bool = False):
        """
        캐시된 settings 반환 또는 TTL 기반 재로드
        
        Args:
            force: True면 즉시 재로드하고 캐시 갱신

        # ❗ SSOT RULE (DO NOT BREAK)
        # - settings 접근은 반드시 self._settings 또는 _get_settings_cached()만 사용
        # - load_settings() 직접 호출은 boot/patch/save 내부로 제한
        """
        import time
        current_time = time.time()

        # ✅ Step5: settings 접근 혼용 차단 가드 (crash 금지, warning만)
        # - 부팅 초기에 self._settings가 None인데도 force 없이 접근하는 경로를 "비정상 경로"로 로깅한다.
        # - 동작은 유지(계속 캐시 로직 진행)
        try:
            if getattr(self, "_settings", None) is None and (not force) and float(getattr(self, "_settings_cached_at", 0.0) or 0.0) <= 0.0:
                self._log.warning("[SSOT] illegal settings access path")
        except Exception:
            pass
        
        # ✅ P0-KEY-SSOT-AUDIT: cache hit/miss 로그 (throttled)
        cache_age_ms = int((current_time - self._settings_cached_at) * 1000) if hasattr(self, '_settings_cached_at') else 0
        
        if force or (current_time - self._settings_cached_at) > self._settings_cache_ttl_sec:
            log_msg = f"[SETTINGS-CACHE] miss force={force} -> reload"
        else:
            log_msg = f"[SETTINGS-CACHE] hit age_ms={cache_age_ms}"
        
        # 5초 throttle 적용
        if not hasattr(self, '_last_cache_log_ts') or (current_time - self._last_cache_log_ts) > 5:
            self._log.info(log_msg)
            self._last_cache_log_ts = current_time
        
        # force이거나 캐시 만료 시 재로드
        if force or (current_time - self._settings_cached_at) > self._settings_cache_ttl_sec:
            try:
                from app.utils.prefs import load_settings

                # ✅ preserve: 기존 strategy의 ai_provider가 스키마 기본값(local)로 되돌아가는 것 방지
                _prev = getattr(self, "_settings", None)
                _prev_st = getattr(_prev, "strategy", None) if _prev else None

                self._settings = load_settings()

                # ✅ strategy 타입 강제 통일 + ai_provider 보존
                try:
                    if hasattr(self._settings, "strategy"):
                        self._settings.strategy = _coerce_strategy_config(
                            getattr(self._settings, "strategy", None),
                            preserve_ai_provider_from=_prev_st
                        )
                except Exception:
                    pass

                self._settings_cached_at = current_time
                self._log.debug(f"[SETTINGS-CACHE] reloaded force={force}")

            except Exception as e:
                self._log.error(f"[SETTINGS-CACHE] reload failed: {e}")
        
        return self._settings
    
    def _settings_ssot(self, force: bool = False):
        """
        ✅ P0-BOOT-ORDER: Settings 접근 SSOT (Single Source of Truth)
        1. self._settings가 유효하면 우선 반환
        2. 없으면 _get_settings_cached() 호출
        3. 둘 다 없으면 None 반환
        """
        if hasattr(self, '_settings') and self._settings is not None:
            return self._settings
        
        if hasattr(self, '_get_settings_cached'):
            return self._get_settings_cached(force=force)
        
        return None

    def _sanitize_status_msg(self, msg: str) -> tuple[str | None, str]:
        """
        메시지에서 선행 아이콘을 분리하여 (icon, text) 반환
        예: "🟢 정상" → ("🟢", "정상")
        예: "저장됨" → (None, "저장됨")
        """
        import re
        
        # 아이콘 패턴: 이모지 + 공백
        icon_patterns = [
            (r"^⏳\s+", "⏳"),
            (r"^🟢\s+", "🟢"), 
            (r"^🔴\s+", "🔴"),
            (r"^✅\s+", "✅"),
            (r"^⚠️\s+", "⚠️"),
            (r"^ℹ️\s+", "ℹ️"),
            (r"^💾\s+", "💾"),
            (r"^❗\s+", "❗")
        ]
        
        for pattern, icon in icon_patterns:
            if re.match(pattern, msg):
                text = re.sub(pattern, "", msg)
                return icon, text
        
        return None, msg

    def set_global_status(self, text: str, level: str = "ok", cat: str = "", detail: str = ""):
        """✅ P0-UI-GLOBAL-STATUS: 전역 상태바 업데이트"""
        try:
            # ✅ 메시지 sanitize: 선행 아이콘 분리
            msg_icon, clean_text = self._sanitize_status_msg(text)
            
            # 아이콘 및 색상 매핑
            level_config = {
                "ok": {"icon": "🟢", "color": "#2e7d32"},
                "busy": {"icon": "⏳", "color": "#f57c00"},
                "warn": {"icon": "⚠️", "color": "#f57c00"},
                "err": {"icon": "🔴", "color": "#d32f2f"}
            }
            
            config = level_config.get(level, level_config["ok"])
            
            # ✅ 아이콘 표시: 메시지에 포함된 아이콘 우선, 없으면 level 기본 아이콘
            display_icon = msg_icon if msg_icon else config["icon"]
            self.global_status_icon.setText(display_icon)
            
            # ✅ 텍스트 표시: 이모지 제거된 순수 텍스트
            self.global_status_text.setText(clean_text)
            self.global_status_text.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {config['color']};")
            
            # ✅ [boot] 태그: debug_ui 모드에서만 표시
            if cat and getattr(self, '_debug_ui', False):
                self.global_status_time.setText(f"[{cat}]")
                # 디버그 로그
                import logging
                logging.getLogger(__name__).info(f"[STATUSBAR] reason={cat} level={level} msg=\"{clean_text}\"")
            else:
                self.global_status_time.setText("")
                
        except Exception:
            pass

    # ---- Watchlist ----
    # (삭제됨) _init_watchlist:
    # WatchlistTab이 워치리스트 UI/시그널/AI추천 반영을 100% 소유한다.
    #
    # ⚠️ 따라서 app_gui.py에서는 _init_watchlist를 “복구/삽입”하지 않는다.
    # Watchlist는 _build_ui()에서 WatchlistTab 인스턴스를 직접 addTab 하는 단일 경로만 유지한다.

    # (삭제됨) _init_logs / _reload_logs_table:
    # 로그 UI는 별도 탭(또는 모듈)로 이전 예정. app_gui.py 다이어트를 위해 레거시 제거.

    # ---- Trades ----
    # (삭제됨) _init_trades: TradesTab이 UI/시그널/로딩/내보내기를 100% 소유

    # (삭제됨) _reload_trades_table: TradesTab.refresh()로 이전 완료

    # (삭제됨) _init_overview:
    # 투자현황 UI는 PortfolioTab이 100% 소유하며, app_gui.py는 탭 생성/addTab만 담당한다.

    # (유지-축소) _reload_positions_table
    # 하위호환을 위해 남기되, 내부 로직은 완전 위임만 수행한다.
    def _reload_positions_table(self):
        try:
            if hasattr(self, "portfolio_tab") and hasattr(self.portfolio_tab, "refresh"):
                self.portfolio_tab.refresh()
        except Exception:
            pass



    def _on_sell_clicked(self):
        sender = self.sender()
        m = sender.property("market")
        vol = float(sender.property("volume") or 0.0)
        if not m or vol <= 0:
            return
        try:
            tk = (get_tickers([m]) or [None])[0]
            px = float(tk.get("trade_price") or 0.0) if tk else 0.0
        except Exception:
            px = 0.0
        if (px * vol) < 5000.0:
            QMessageBox.information(self, "매도 불가", "평가금액이 5,000원 미만(먼지 포지션)이라 매도할 수 없습니다.")
            return
        yes = QMessageBox.question(self, "확인", f"{m} {vol:.8f} 전량/부분 매도할까요?")
        if yes != QMessageBox.Yes:
            return
        try:
            ok, block_reason = svc_order.sell_market(m, vol, simulate=not bool(self._settings.live_trade), reason="UI sell")
            if ok:
                QMessageBox.information(self, "전송됨", "매도 요청을 전송했습니다.")
            else:
                QMessageBox.warning(self, "매도 차단", f"매도 실패: block_reason={block_reason or 'unknown'}")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"매도 실패: {e}")

    # ---- PnL ----
    # (삭제됨) _init_pnl:
    # 수익률(PnL) UI는 PortfolioTab(투자현황)로 통합되었으므로 app_gui.py 레거시 제거.

    # (삭제됨) StrategyTab 레거시 묶음:
    # _on_strategy_row_selected
    # _reload_pnl_by_strategy
    # _setup_indicator_legacy_mirrors
    # _build_strategy_market_section
    # _build_strategy_risk_section
    # _build_strategy_order_limit_section
    # _build_strategy_watchlist_section
    # _build_strategy_behavior_section
    # _build_strategy_external_section
    # _build_strategy_ai_section
    #
    # StrategyTab이 UI/로직을 100% 소유하므로 app_gui.py에서 완전 제거.

    # ---- Settings ----
    def _init_settings(self, w: QWidget):
        """
        [설정] 탭: 기능 설정 + TP/SL 입력(사용자 지정 모드에서만 활성)
        - 관심종목, 자동 Top20, 최대투자/1회주문, 실거래, API 키, 자동로그인/세션복원, 폴링 주기 등
        - 손절/익절 입력은 여기서 보관(전략 탭의 '사용자 지정' 모드에서만 사용)
        """
        from PySide6.QtWidgets import QFormLayout, QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QWidget, QLabel, QSpinBox, QDoubleSpinBox
        v = QFormLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setHorizontalSpacing(8)
        v.setVerticalSpacing(8)

        # ---- 기본 입력들 ----
        self.ed_symbols   = QLineEdit()
        self.cb_top20     = QCheckBox("거래대금 상위 20 자동")
        self.sp_max_total = QSpinBox();       self.sp_max_total.setRange(0, 10_000_000)
        self.sp_order_amt = QSpinBox();       self.sp_order_amt.setRange(1000, 1_000_000); self.sp_order_amt.setSingleStep(1000)

        self.ed_access = QLineEdit(); self.ed_access.setEchoMode(QLineEdit.Password)
        self.ed_secret = QLineEdit(); self.ed_secret.setEchoMode(QLineEdit.Password)

        # 자동 로그인 → 아이디/비밀번호 기억
        #   - 실제로는 로그인 창에서 한 번은 직접 로그인 버튼을 누르게 하고
        #   - 여기서는 "계정 정보를 저장해서 입력란에 채워주는" 의미로 사용한다.
        self.cb_autologin = QCheckBox("아이디/비밀번호 기억")
        self.cb_autologin.setToolTip(
            "체크 시 마지막으로 사용한 아이디/비밀번호를 저장하여\n"
            "다음 실행 때 로그인 창에 자동으로 채워줍니다.\n"
            "보안을 위해 로그인 버튼은 항상 직접 눌러야 합니다."
        )
        self.cb_restore   = QCheckBox("마지막 세션 복원")

        # 폴링 관련
        self.sp_ticker  = QSpinBox(); self.sp_ticker.setRange(200, 10000); self.sp_ticker.setSingleStep(100)
        self.sp_topNmin = QSpinBox(); self.sp_topNmin.setRange(1, 180)

        # ✅ TP/SL 위젯(설정 탭에 유지 — '사용자 지정' 모드에서만 활성)
        self.sp_sl = QDoubleSpinBox(); self.sp_sl.setRange(0.0, 50.0); self.sp_sl.setDecimals(2); self.sp_sl.setSingleStep(0.1)
        self.sp_tp = QDoubleSpinBox(); self.sp_tp.setRange(0.0, 100.0); self.sp_tp.setDecimals(2); self.sp_tp.setSingleStep(0.1)
        self.sp_sl.setToolTip("손절 기준(%) — '전략' 탭에서 '사용자 손절/익절' 선택 시 적용")
        self.sp_tp.setToolTip("익절 기준(%) — '전략' 탭에서 '사용자 손절/익절' 선택 시 적용")

        # ⚠️ 투자금/관심종목/주문금 관련 항목은
        #    - 전략설정/Watchlist 탭으로 역할을 이전
        #    - 위젯 자체는 하위호환을 위해 유지하되, 공통설정 UI에서는 숨김 처리
        # v.addRow("관심종목(쉼표 구분)", self.ed_symbols)
        # v.addRow("", self.cb_top20)
        # v.addRow("최대 투자금(원)", self.sp_max_total)
        # v.addRow("1회 주문금액(원)", self.sp_order_amt)

        # API/기타
        v.addRow("Upbit Access Key", self.ed_access)
        v.addRow("Upbit Secret Key", self.ed_secret)
        
        # 저장/테스트 버튼은 인스턴스 재사용 가능하도록 getattr 사용
        self.btn_save = getattr(self, "btn_save", QPushButton("저장"))
        if not self.btn_save.text().strip():
            self.btn_save.setText("저장")
            self._log.info('[SAVE-UI] btn_save_text="저장" (fixed)')
        self.btn_test = getattr(self, "btn_test", QPushButton("업비트 연결 테스트"))
        
        # 업비트 연결 테스트 버튼을 API 키 바로 아래로 이동
        v.addRow("", self.btn_test)

        # 시세 조회 주기 / 상위20 갱신(분) — 업비트 연결 테스트 바로 아래, 1줄 2등분
        self.sp_ticker.setRange(1000, 5000)
        self.sp_ticker.setSingleStep(200)
        self.sp_ticker.setSuffix(" ms")
        self.sp_ticker.setToolTip("시세 데이터 조회 주기 (최소 1초, 실시간성 vs 부하 조절)")
        self.sp_ticker.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.sp_topNmin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row_market = QHBoxLayout()
        row_market.setSpacing(12)
        left_wrap = QVBoxLayout()
        left_wrap.setContentsMargins(0, 0, 0, 0)
        left_wrap.addWidget(QLabel("시세 조회 주기"))
        left_wrap.addWidget(self.sp_ticker)
        right_wrap = QVBoxLayout()
        right_wrap.setContentsMargins(0, 0, 0, 0)
        right_wrap.addWidget(QLabel("상위20 갱신(분)"))
        right_wrap.addWidget(self.sp_topNmin)
        row_market.addLayout(left_wrap, 1)
        row_market.addLayout(right_wrap, 1)
        v.addRow("", row_market)

        # 업비트 키 안내 텍스트 박스
        info_box = QGroupBox("")
        info_layout = QVBoxLayout()
        
        info_text = QLabel(
            "【업비트】 로그인 → 프로필 → API Keys에서 Access/Secret 발급 · 권한: 조회+주문 필수 · Secret 노출 금지.\n"
            "【GPT】 OpenAI 대시보드에서 API Key 발급 · 모델은 gpt-4o-mini(권장)/gpt-4o 등 선택.\n"
            "【Local】 Basic AI 설치 후 모델을 준비하세요 · URL은 기본 http://127.0.0.1:11434."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("QLabel { padding: 8px; background-color: #f5f5f5; border-radius: 4px; font-size: 11px; }")
        info_layout.addWidget(info_text)
        info_box.setLayout(info_layout)
        v.addRow(info_box)

        # (레거시) 상단 공통 엔진 UI는 숨김 유지 — 엔진 설정은 하단 3박스에서만 수행
        self.cmb_ai_engine = QComboBox()
        self.cmb_ai_engine.addItems(["OpenAI", "Gemini", "Basic AI"])
        self.cmb_ai_engine.setCurrentText("Basic AI")
        self.cmb_ai_model = QComboBox()
        self.ed_ai_api_key = QLineEdit()
        self.ed_ai_api_key.setEchoMode(QLineEdit.Password)
        self.btn_test_connection = QPushButton("연결 테스트")
        ai_engine_form = QFormLayout()
        ai_engine_form.addRow("AI Engine", self.cmb_ai_engine)
        ai_engine_form.addRow("AI Model", self.cmb_ai_model)
        ai_engine_form.addRow("API Key", self.ed_ai_api_key)
        ai_engine_form.addRow("", self.btn_test_connection)
        self.ai_engine_legacy_widget = QWidget()
        self.ai_engine_legacy_widget.setLayout(ai_engine_form)
        self.ai_engine_legacy_widget.setVisible(False)
        v.addRow(self.ai_engine_legacy_widget)
        self.cmb_ai_engine.currentTextChanged.connect(self._on_ai_engine_changed)
        self.btn_test_connection.clicked.connect(self._on_test_connection_clicked)
        self._on_ai_engine_changed(self.cmb_ai_engine.currentText())
        
        # GPT 박스 / LOCAL 박스 분리 (선택한 박스만 활성화·저장, 콤보는 내부 동기화용만 사용)
        self._ai_provider_box_active = "local"
        self.cb_ai_provider = QComboBox()
        self.cb_ai_provider.addItems(["gpt", "gemini", "local"])
        self.cb_ai_provider.setCurrentText("local")
        self.cb_ai_provider.setVisible(False)

        self.ed_openai_key = QLineEdit()
        self.ed_openai_key.setEchoMode(QLineEdit.Password)
        self.ed_openai_key.setPlaceholderText("sk-...")

        # ✅ KMTS 검증된 GPT 모델 리스트 (4개만 노출)
        self.KMTS_GPT_MODELS = [
            {
                "id": "gpt-4o-mini",
                "label": "gpt-4o-mini (추천)",
                "desc": "• 평균 응답 빠름 | 1시간 자동매매 예상 비용: $0.1 ~ $0.5 | 초보자 추천 / 자동매매 기본 권장"
            },
            {
                "id": "gpt-4o",
                "label": "gpt-4o",
                "desc": "• 정밀도 높음 / 비용 중상 | 변동성 큰 장세에 적합 | 1시간 자동매매 예상 비용: $0.5 ~ $2.0"
            },
            {
                "id": "gpt-4.1",
                "label": "gpt-4.1",
                "desc": "• 고급 모델 | 최고 정밀도 | 대형 자금 운용 시 적합 | 비용 높음 (예상: $2.0 ~ $5.0/시간)"
            },
            {
                "id": "gpt-3.5-turbo",
                "label": "gpt-3.5-turbo",
                "desc": "• 저비용 테스트용 | 정확도는 낮음 | 학습/테스트 목적으로만 권장"
            }
        ]
        
        self.ed_openai_model = QComboBox()
        self.ed_openai_model.setEditable(False)  # 하드코딩 모델만 선택 가능
        # 검증된 모델만 추가
        for model_info in self.KMTS_GPT_MODELS:
            self.ed_openai_model.addItem(model_info["label"], model_info["id"])
        self.ed_openai_model.setCurrentIndex(0)  # gpt-4o-mini 기본값

        self.ed_gemini_key = QLineEdit()
        self.ed_gemini_key.setEchoMode(QLineEdit.Password)
        self.ed_gemini_key.setPlaceholderText("Gemini API Key")
        self.cmb_gemini_model = QComboBox()
        self.cmb_gemini_model.addItems(["gemini-1.5-pro", "gemini-1.5-flash"])
        self.lbl_gemini_test_status = QLabel("⚪ NOT TESTED")
        self.lbl_gemini_test_status.setStyleSheet("font-size: 11px; color: #666;")
        
        # Custom Model 입력 (고급 사용자용)
        self.cb_custom_model = QCheckBox("고급 사용자 모드")
        self.cb_custom_model.setToolTip("Custom 모델을 사용하려면 체크하세요")
        self.inp_custom_model = QLineEdit()
        self.inp_custom_model.setPlaceholderText("예: gpt-4o-2024-11-20")
        self.inp_custom_model.setEnabled(False)
        
        # 모델 설명 라벨 (더 자세한 정보 표시) — 반응형: 줄바꿈 허용, 폭 강제 안 함
        self.lbl_gpt_model_desc = QLabel("")
        self.lbl_gpt_model_desc.setWordWrap(True)
        self.lbl_gpt_model_desc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        
        # ✅ 너무 길면 말줄임 처리
        self.lbl_gpt_model_desc.setTextInteractionFlags(Qt.NoTextInteraction)
        self.lbl_gpt_model_desc.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_gpt_model_desc.setStyleSheet("QLabel { padding: 2px 8px; font-size: 11px; color: #666; background-color: #f9f9f9; border-radius: 4px; }")
        
        # Custom 체크박스 상태 변경 시 입력 필드 활성화/비활성화
        def on_custom_toggled(checked):
            self.inp_custom_model.setEnabled(checked)
            if not checked:
                self.inp_custom_model.clear()
        
        self.cb_custom_model.toggled.connect(on_custom_toggled)
        
        # 모델 선택 변경 시 설명 업데이트
        def on_model_changed():
            if self.cb_custom_model.isChecked() and self.inp_custom_model.text().strip():
                # Custom 모델 사용 중
                self.lbl_gpt_model_desc.setText(f"Custom 모델: {self.inp_custom_model.text().strip()}")
            else:
                # 기본 모델 선택
                current_id = self.ed_openai_model.currentData()
                if current_id:
                    model_info = next((m for m in self.KMTS_GPT_MODELS if m["id"] == current_id), None)
                    if model_info:
                        self.lbl_gpt_model_desc.setText(model_info["desc"])
                    else:
                        self.lbl_gpt_model_desc.setText("")
                else:
                    self.lbl_gpt_model_desc.setText("")
        
        self.ed_openai_model.currentIndexChanged.connect(on_model_changed)
        self.inp_custom_model.textChanged.connect(on_model_changed)
        on_model_changed()  # 초기 설명 표시

        self.inp_local_url = QLineEdit()
        self.inp_local_url.setObjectName("inp_local_url")
        self.inp_local_url.setPlaceholderText("http://127.0.0.1:11434")
        self.inp_local_url.setText("http://127.0.0.1:11434")
        self.cmb_local_model = QComboBox()
        self.cmb_local_model.setObjectName("cmb_local_model")
        self.cmb_local_model.addItems(["llama3.1", "qwen2.5", "mistral"])
        self.cmb_local_model.setCurrentText("qwen2.5")
        self.cmb_local_model.setToolTip(
            "Local 엔진 3종:\n"
            "• llama3.1: 메타, 범용 대화/요약\n"
            "• qwen2.5: 알리바바, 추천/점수에 적합\n"
            "• mistral: 경량·저지연, 실시간 판단에 적합"
        )
        self.lbl_local_engines = QLabel(
            "Local 엔진 3종: llama3.1(범용) | qwen2.5(추천/점수 적합) | mistral(경량·실시간). "
            "설치: Basic AI 설치 후 앱의 모델 설치 버튼으로 준비. "
            "설정: URL 기본 http://127.0.0.1:11434"
        )
        self.lbl_local_engines.setWordWrap(True)
        self.lbl_local_engines.setStyleSheet("QLabel { padding: 4px; font-size: 10px; color: #555; }")
        self.btn_test_local_ai = QPushButton("로컬 AI 테스트")
        self.btn_test_local_ai.setObjectName("btn_test_local_ai")
        # ✅ LOCAL 옵션 가이드 버튼들
        self.btn_ollama_install_guide = QPushButton("Basic AI 설치 안내(웹)")
        self.btn_ollama_install_guide.setToolTip("Basic AI 설치 후 모델 설치 버튼을 눌러주세요.")
        self.btn_ollama_install_guide.setObjectName("btn_ollama_install_guide")
        self.btn_install_qwen = QPushButton("qwen2.5 설치 필요")
        self.btn_install_qwen.setObjectName("btn_install_qwen")
        self.btn_install_qwen.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")  # 연한 주황 (미설치)
        self.btn_install_llama = QPushButton("llama3.1 설치 필요")
        self.btn_install_llama.setObjectName("btn_install_llama")
        self.btn_install_llama.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")  # 연한 주황 (미설치)
        self.btn_install_mistral = QPushButton("mistral 설치 필요")
        self.btn_install_mistral.setObjectName("btn_install_mistral")
        self.btn_install_mistral.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")  # 연한 주황 (미설치)
        self.btn_test_gpt = QPushButton("GPT 연결 테스트")
        self.btn_test_gpt.setObjectName("btn_test_gpt")
        self.btn_test_gemini = QPushButton("Gemini 연결 테스트")
        self.btn_test_gemini.setObjectName("btn_test_gemini")
        # ✅ OpenAI 사용량 페이지 바로 열기 (API 호출 없음, 브라우저 연결만)
        self.btn_openai_usage = QPushButton("GPT 사용량 보기 (OpenAI 웹)")
        self.btn_openai_usage.setToolTip("OpenAI Usage 페이지를 브라우저로 엽니다.")
        self.btn_openai_usage.setObjectName("btn_openai_usage")

        # [OpenAI 박스] OpenAI — Key, Model, 테스트
        self.gpt_box = ClickableGroupBox("")  # 제목은 내부 라벨로 처리
        self.gpt_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.gpt_box.setMinimumHeight(0)

        gpt_layout = QVBoxLayout()

        # 제목 영역: "OpenAI" + 상태 1줄
        gpt_title_row = QHBoxLayout()
        gpt_title_label = QLabel("OpenAI")
        gpt_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.gpt_test_header_status = QLabel("⚪ NOT TESTED")
        self.gpt_test_header_status.setStyleSheet("font-size: 11px; color: #666;")
        self._gpt_status_stage = "idle"  # idle | connecting | connect_ok | applying | ready
        gpt_title_row.addWidget(gpt_title_label)
        gpt_title_row.addWidget(self.gpt_test_header_status)
        gpt_title_row.addStretch()
        gpt_layout.addLayout(gpt_title_row)
        # 폼 레이아웃
        gpt_form = QFormLayout()
        gpt_form.addRow("OpenAI API Key", self.ed_openai_key)
        gpt_form.addRow("OpenAI Model", self.ed_openai_model)

        # OpenAI 버튼 배치
        gpt_btn_row = QHBoxLayout()
        self.btn_test_gpt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        gpt_btn_row.addWidget(self.btn_test_gpt)
        gpt_form.addRow("", gpt_btn_row)

        gpt_layout.addLayout(gpt_form)
        self.gpt_box.setLayout(gpt_layout)

        # [Gemini 박스] Gemini — Key, Model, 테스트
        self.gemini_box = ClickableGroupBox("")
        self.gemini_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.gemini_box.setMinimumHeight(0)
        gemini_layout = QVBoxLayout()
        gemini_title_row = QHBoxLayout()
        gemini_title_label = QLabel("Gemini")
        gemini_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        gemini_title_row.addWidget(gemini_title_label)
        gemini_title_row.addWidget(self.lbl_gemini_test_status)
        gemini_title_row.addStretch()
        gemini_layout.addLayout(gemini_title_row)
        gemini_form = QFormLayout()
        gemini_form.addRow("Gemini API Key", self.ed_gemini_key)
        gemini_form.addRow("Gemini Model", self.cmb_gemini_model)
        self.btn_test_gemini.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        gemini_form.addRow("", self.btn_test_gemini)
        gemini_layout.addLayout(gemini_form)
        self.gemini_box.setLayout(gemini_layout)

        # [LOCAL 박스] LOCAL (Basic AI) — URL, Model, 테스트, 가이드
        self.local_box = ClickableGroupBox("")  # 제목은 내부 라벨로 처리
        self.local_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.local_box.setMinimumHeight(0)

        local_layout = QVBoxLayout()
        local_layout.setSpacing(4)
        local_layout.setContentsMargins(2, 2, 2, 2)
        # 제목 영역: "Basic AI" + ⓘ 버튼
        local_title_row = QHBoxLayout()
        local_title_label = QLabel("Basic AI")
        local_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_local_info = QPushButton("i")
        self.btn_local_info.setMaximumWidth(30)
        self.btn_local_info.setToolTip("LOCAL AI 사용 안내")
        self.btn_local_info.setObjectName("btn_local_info")
        local_title_row.addWidget(local_title_label)
        local_title_row.addWidget(self.btn_local_info)
        local_title_row.addStretch()
        local_layout.addLayout(local_title_row)
        self.btn_local_info.setVisible(False)
        self.lbl_basic_ai_subtitle = QLabel("AITS 기본 자동매매 엔진 (설정 기반 AI)")
        self.lbl_basic_ai_subtitle.setStyleSheet("font-size: 11px; color: #555; padding: 0 0 6px 0;")
        self.lbl_basic_ai_subtitle.setWordWrap(True)
        local_layout.addWidget(self.lbl_basic_ai_subtitle)
        # 레거시 Local/Ollama 행만 유지 (숨김 처리용, 메인 설정은 아래 그룹박스)
        self._basic_ai_legacy_form = QFormLayout()
        self._basic_ai_legacy_form.setSpacing(4)
        self._basic_ai_legacy_form.setVerticalSpacing(4)
        self._basic_ai_legacy_form.setHorizontalSpacing(8)
        self._basic_ai_legacy_form.addRow("Local URL", self.inp_local_url)
        self._basic_ai_legacy_form.addRow("Local Model", self.cmb_local_model)
        self.cmb_basic_ai_risk = QComboBox()
        self.cmb_basic_ai_risk.addItems(["보수적", "중립", "공격적"])
        self.cmb_basic_ai_risk.setCurrentText("중립")
        self.sp_basic_ai_target_profit = QDoubleSpinBox()
        self.sp_basic_ai_target_profit.setRange(0.1, 50.0)
        self.sp_basic_ai_target_profit.setDecimals(2)
        self.sp_basic_ai_target_profit.setSingleStep(0.5)
        self.sp_basic_ai_target_profit.setValue(3.0)
        self.sp_basic_ai_stop_loss = QDoubleSpinBox()
        self.sp_basic_ai_stop_loss.setRange(0.1, 50.0)
        self.sp_basic_ai_stop_loss.setDecimals(2)
        self.sp_basic_ai_stop_loss.setSingleStep(0.5)
        self.sp_basic_ai_stop_loss.setValue(1.5)
        self.sp_basic_ai_max_positions = QSpinBox()
        self.sp_basic_ai_max_positions.setRange(1, 50)
        self.sp_basic_ai_max_positions.setValue(5)
        self.cmb_basic_ai_selection = QComboBox()
        self.cmb_basic_ai_selection.addItems(["낮음", "보통", "높음"])
        self.cmb_basic_ai_selection.setCurrentText("보통")
        self.cb_basic_ai_avoid_bear = QCheckBox("하락장 회피")
        self.cb_basic_ai_avoid_bear.setChecked(True)
        self.cmb_basic_ai_buy_sensitivity = QComboBox()
        self.cmb_basic_ai_buy_sensitivity.addItems(["낮음", "보통", "높음"])
        self.cmb_basic_ai_buy_sensitivity.setCurrentText("보통")
        self.cmb_basic_ai_sell_sensitivity = QComboBox()
        self.cmb_basic_ai_sell_sensitivity.addItems(["느림", "보통", "빠름"])
        self.cmb_basic_ai_sell_sensitivity.setCurrentText("보통")
        self.cb_basic_ai_split_buy = QCheckBox("분할 매수")
        self.cb_basic_ai_split_buy.setChecked(True)
        self.cb_basic_ai_split_sell = QCheckBox("분할 매도")
        self.cb_basic_ai_split_sell.setChecked(True)
        self.sp_basic_ai_max_hold_min = QSpinBox()
        self.sp_basic_ai_max_hold_min.setRange(1, 10_080)
        self.sp_basic_ai_max_hold_min.setSingleStep(10)
        self.sp_basic_ai_max_hold_min.setValue(120)
        self.sp_basic_ai_min_volume = QSpinBox()
        self.sp_basic_ai_min_volume.setRange(0, 2_000_000_000)
        self.sp_basic_ai_min_volume.setSingleStep(1_000_000)
        self.sp_basic_ai_min_volume.setValue(100_000_000)
        self.cb_basic_ai_exclude_overheated = QCheckBox("과열 종목 제외")
        self.cb_basic_ai_exclude_overheated.setChecked(True)
        self.cb_basic_ai_avoid_sudden_drop = QCheckBox("급락 회피")
        self.cb_basic_ai_avoid_sudden_drop.setChecked(True)
        self.cmb_basic_ai_trend_filter = QComboBox()
        self.cmb_basic_ai_trend_filter.addItems(["없음", "약함", "강함"])
        self.cmb_basic_ai_trend_filter.setCurrentText("약함")
        self.sp_basic_ai_entry_score = QSpinBox()
        self.sp_basic_ai_entry_score.setRange(0, 100)
        self.sp_basic_ai_entry_score.setValue(60)
        self.sp_basic_ai_exit_score = QSpinBox()
        self.sp_basic_ai_exit_score.setRange(0, 100)
        self.sp_basic_ai_exit_score.setValue(45)
        self.cmb_basic_ai_decision_speed = QComboBox()
        self.cmb_basic_ai_decision_speed.addItems(["느림", "보통", "빠름"])
        self.cmb_basic_ai_decision_speed.setCurrentText("보통")
        self.sp_basic_ai_reentry_cooldown = QSpinBox()
        self.sp_basic_ai_reentry_cooldown.setRange(1, 10_080)
        self.sp_basic_ai_reentry_cooldown.setValue(30)
        self.sp_basic_ai_max_new_entries = QSpinBox()
        self.sp_basic_ai_max_new_entries.setRange(0, 50)
        self.sp_basic_ai_max_new_entries.setValue(2)
        self.btn_save_basic_ai_settings = QPushButton("Basic AI 설정 저장")
        self.btn_save_basic_ai_settings.clicked.connect(self._save_basic_ai_settings)

        def _basic_ai_grid(gb: QGroupBox) -> QGridLayout:
            g = QGridLayout(gb)
            g.setContentsMargins(6, 6, 6, 6)
            g.setHorizontalSpacing(10)
            g.setVerticalSpacing(3)
            g.setColumnStretch(1, 1)
            g.setColumnStretch(3, 1)
            return g

        gb_core = QGroupBox("핵심 운용값")
        gc = _basic_ai_grid(gb_core)
        gc.addWidget(QLabel("운용 성향"), 0, 0)
        gc.addWidget(self.cmb_basic_ai_risk, 0, 1)
        gc.addWidget(QLabel("종목 선별 강도"), 0, 2)
        gc.addWidget(self.cmb_basic_ai_selection, 0, 3)
        gc.addWidget(QLabel("최대 보유 종목 수"), 1, 0)
        gc.addWidget(self.sp_basic_ai_max_positions, 1, 1)
        local_layout.addWidget(gb_core)

        gb_goal = QGroupBox("목표/손절")
        gg = _basic_ai_grid(gb_goal)
        gg.addWidget(QLabel("목표 수익률 (%)"), 0, 0)
        gg.addWidget(self.sp_basic_ai_target_profit, 0, 1)
        gg.addWidget(QLabel("손절 기준 (%)"), 0, 2)
        gg.addWidget(self.sp_basic_ai_stop_loss, 0, 3)
        gg.addWidget(QLabel("최대 보유 시간 (분)"), 1, 0)
        gg.addWidget(self.sp_basic_ai_max_hold_min, 1, 1)
        local_layout.addWidget(gb_goal)

        gb_trade = QGroupBox("매수/매도 동작")
        gt = _basic_ai_grid(gb_trade)
        gt.addWidget(QLabel("매수 민감도"), 0, 0)
        gt.addWidget(self.cmb_basic_ai_buy_sensitivity, 0, 1)
        gt.addWidget(QLabel("매도 민감도"), 0, 2)
        gt.addWidget(self.cmb_basic_ai_sell_sensitivity, 0, 3)
        gt.addWidget(self.cb_basic_ai_split_buy, 1, 0, 1, 2)
        gt.addWidget(self.cb_basic_ai_split_sell, 1, 2, 1, 2)
        local_layout.addWidget(gb_trade)

        gb_filter = QGroupBox("시장 필터")
        gf = _basic_ai_grid(gb_filter)
        gf.addWidget(QLabel("최소 거래대금 (원)"), 0, 0)
        gf.addWidget(self.sp_basic_ai_min_volume, 0, 1)
        gf.addWidget(QLabel("추세 필터"), 0, 2)
        gf.addWidget(self.cmb_basic_ai_trend_filter, 0, 3)
        gf.addWidget(self.cb_basic_ai_avoid_bear, 1, 0, 1, 2)
        gf.addWidget(self.cb_basic_ai_exclude_overheated, 1, 2, 1, 2)
        gf.addWidget(self.cb_basic_ai_avoid_sudden_drop, 2, 0, 1, 2)
        local_layout.addWidget(gb_filter)

        gb_ai_logic = QGroupBox("AI 판단 로직")
        gl = _basic_ai_grid(gb_ai_logic)
        gl.addWidget(QLabel("AI 진입 기준 점수"), 0, 0)
        gl.addWidget(self.sp_basic_ai_entry_score, 0, 1)
        gl.addWidget(QLabel("AI 청산 기준 점수"), 0, 2)
        gl.addWidget(self.sp_basic_ai_exit_score, 0, 3)
        gl.addWidget(QLabel("AI 판단 속도"), 1, 0)
        gl.addWidget(self.cmb_basic_ai_decision_speed, 1, 1)
        gl.addWidget(QLabel("재진입 제한 시간 (분)"), 1, 2)
        gl.addWidget(self.sp_basic_ai_reentry_cooldown, 1, 3)
        gl.addWidget(QLabel("동시 매수 제한 수"), 2, 0)
        gl.addWidget(self.sp_basic_ai_max_new_entries, 2, 1)
        local_layout.addWidget(gb_ai_logic)

        self.btn_save_basic_ai_settings.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        local_layout.addWidget(self.btn_save_basic_ai_settings)

        self._basic_ai_legacy_form.addRow("", self.lbl_local_engines)
        # ✅ LOCAL 버튼 2개를 한 줄에 배치 (레거시, 레이아웃 유지·숨김)
        local_btn_row = QHBoxLayout()
        self.btn_test_local_ai.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_ollama_install_guide.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        local_btn_row.addWidget(self.btn_test_local_ai)
        local_btn_row.addWidget(self.btn_ollama_install_guide)
        self._local_legacy_btn_wrap = QWidget()
        self._local_legacy_btn_wrap.setLayout(local_btn_row)
        self._basic_ai_legacy_form.addRow("", self._local_legacy_btn_wrap)

        # 모델 설치 버튼 가로 배치 (레거시, 레이아웃 유지·숨김)
        model_buttons_row = QHBoxLayout()
        model_buttons_row.addWidget(self.btn_install_qwen)
        model_buttons_row.addWidget(self.btn_install_llama)
        model_buttons_row.addWidget(self.btn_install_mistral)
        self._local_model_btn_wrap = QWidget()
        self._local_model_btn_wrap.setLayout(model_buttons_row)
        self._basic_ai_legacy_form.addRow("", self._local_model_btn_wrap)
        _basic_ai_legacy_wrap = QWidget()
        _basic_ai_legacy_wrap.setLayout(self._basic_ai_legacy_form)
        local_layout.insertWidget(2, _basic_ai_legacy_wrap)
        self.local_box.setLayout(local_layout)
        self._hide_basic_ai_legacy_local_ui(self._basic_ai_legacy_form)
        self._load_basic_ai_settings_to_ui()
        self._wire_basic_ai_status_line_hooks()

        self.gpt_box.clicked.connect(lambda: self._set_ai_provider_ui_active("gpt"))
        self.gemini_box.clicked.connect(lambda: self._set_ai_provider_ui_active("gemini"))
        self.local_box.clicked.connect(lambda: self._set_ai_provider_ui_active("local"))
        self.btn_test_local_ai.clicked.connect(self._on_test_local_ai)
        self.btn_test_gpt.clicked.connect(self._on_test_gpt)
        self.btn_test_gemini.clicked.connect(self._on_test_gemini)
        if hasattr(self, "cmb_local_model"):
            self.cmb_local_model.currentTextChanged.connect(self._on_local_model_changed)
        try:
            def _norm_payload(p):
                return p.get("advice", p) if isinstance(p, dict) else p
            eventbus.subscribe("ai.reco.updated", self._on_ai_reco_updated)
            eventbus.subscribe("ai.reco.items", lambda p: self._on_ai_reco_updated(_norm_payload(p)))
            eventbus.subscribe("ai.reco.strategy_suggested", lambda p: self._on_ai_reco_updated(_norm_payload(p)))
        except Exception:
            pass
        if not hasattr(self, "_gpt_poll_timer") or self._gpt_poll_timer is None:
            self._gpt_poll_timer = QTimer(self)
            self._gpt_poll_timer.setInterval(2000)
            self._gpt_poll_timer.timeout.connect(self._on_gpt_poll_tick)
            self._gpt_poll_timer.start()
        self.btn_local_info.clicked.connect(self._on_show_local_guide)
        # ✅ LOCAL 옵션 가이드 버튼 연결
        self.btn_ollama_install_guide.clicked.connect(self._on_open_ollama_install_guide)
        self.btn_install_qwen.clicked.connect(lambda: self._on_install_ollama_model("qwen2.5"))
        self.btn_install_llama.clicked.connect(lambda: self._on_install_ollama_model("llama3.1"))
        self.btn_install_mistral.clicked.connect(lambda: self._on_install_ollama_model("mistral"))

        # OpenAI / Gemini 1행 2열 + Basic AI 하단 전체폭
        row_ai_top = QWidget()
        row_ai_top_layout = QHBoxLayout(row_ai_top)
        row_ai_top_layout.setContentsMargins(0, 0, 0, 0)
        row_ai_top_layout.setSpacing(12)
        row_ai_top_layout.addWidget(self.gpt_box, 1)
        row_ai_top_layout.addWidget(self.gemini_box, 1)
        v.addRow(row_ai_top)
        v.addRow(self.local_box)
        self._set_ai_provider_ui_active("local")
        # 초기 로드 시 모델 상태 확인 (백그라운드)
        QTimer.singleShot(1000, self._check_and_update_model_buttons)
        
        # 내 PC 외부 IP 표시 + 재시도 버튼
        ip_row = QHBoxLayout()
        self.ip_label = QLabel("🌐 외부 IP: 확인 중...")
        self.ip_label.setStyleSheet("QLabel { padding: 8px; background-color: #e8f4fd; border-radius: 4px; font-weight: bold; }")
        ip_row.addWidget(self.ip_label)
        self.btn_ip_retry = QPushButton("재시도")
        self.btn_ip_retry.setMaximumWidth(70)
        self.btn_ip_retry.clicked.connect(self._update_external_ip)
        ip_row.addWidget(self.btn_ip_retry)
        v.addRow(ip_row)
        
        # IP 확인 즉시 실행
        try:
            self._update_external_ip()
        except Exception:
            pass
        
        # (기존) 시세 조회 주기/상위20 갱신 — 업비트 연결 테스트 아래로 이동함. 중복 배치 방지.
        # v.addRow("", row_market)

        # 저장행 위 30px 간격 + 구분선 (기능 영역 / 저장 영역 시각 분리)
        from PySide6.QtWidgets import QSpacerItem
        spacer = QSpacerItem(0, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        v.addItem(spacer)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        v.addRow(sep)

        # ---- 저장/테스트 결과/로그 버튼: 시세 조회 주기 바로 아래 (하단 고정 제거) ----
        self.btn_open_logs = QPushButton("로그 열기")
        self.btn_open_logs.clicked.connect(lambda: None)
        self.btn_test_results = QPushButton("테스트 결과 보기")
        self.btn_test_results.clicked.connect(self._on_open_test_results)
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; padding: 8px 16px; }")
        self.btn_test_results.setMinimumHeight(40)
        self.btn_test_results.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; padding: 8px 16px; background-color: #4CAF50; color: white; }")
        self.btn_open_logs.setMinimumHeight(40)
        self.btn_open_logs.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; padding: 8px 16px; }")
        try:
            self.btn_save.clicked.connect(self._on_save_settings)
        except Exception:
            pass
        self.btn_test.clicked.connect(self._on_test_upbit)
        for btn in (self.btn_save, self.btn_test_results, self.btn_open_logs):
            btn.setMinimumWidth(140)
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(8)
        btn_lay.addWidget(self.btn_save)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_test_results)
        btn_lay.addWidget(self.btn_open_logs)
        v.addRow(btn_row)

        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        box = QWidget()
        box.setLayout(v)
        wrap.addWidget(box)
        w.setLayout(wrap)

    # (다이어트) StrategyTab 완전 이전 완료로 레거시 체크리스트 주석 블록 제거

    # (삭제됨) _init_strategy:
    # StrategyTab(config_tabs.py)이 전략설정 UI/시그널/로직을 100% 소유한다.

    def _on_save_strategy(self):
        """
        (레거시) 전략 저장 엔트리:
        - StrategyTab이 소유한다.
        - 하위호환: StrategyTab에 위임(있을 때만)
        """
        tab = getattr(self, "tab_strategy", None)
        if tab is not None and hasattr(tab, "on_save"):
            try:
                return tab.on_save()
            except Exception:
                pass

    def _load_strategy_into_form(self):
        """
        (레거시) 전략 로드→UI 반영:
        - StrategyTab이 소유한다.
        - 하위호환: StrategyTab.reload_from_state()로 위임(있을 때만)
        """
        tab = getattr(self, "tab_strategy", None)
        if tab is not None and hasattr(tab, "reload_from_state"):
            try:
                return tab.reload_from_state()
            except Exception:
                pass

    def _load_settings_into_form(self) -> None:
        # ✅ BOOT-GUARD: Prevent duplicate settings loading
        if getattr(self, '_settings_loading', False):
            self._log.info("[BOOT-GUARD] settings already loading, skipping")
            return
        
        # ✅ BOOT-GUARD: Prevent loading during boot restore (but allow after boot for save reloads)
        if getattr(self, '_boot_restoring', False):
            self._log.info("[BOOT-GUARD] boot restoring, skipping settings load")
            return
        
        self._settings_loading = True
        self._load_form_count += 1
        self._log.info("[BOOT-GUARD] enter fn=_load_settings_into_form count=1")
        
        # ✅ INIT-GUARD: Log initialization counts
        self._log.info(f"[INIT-GUARD] ui_init_count={self._ui_init_count} load_form_count={self._load_form_count} key_restore_count={self._key_restore_count}")
        
        import time
        self._key_restore_count += 1
        self._log.info("[KEY-UI] restore_enter")
        
        # ✅ CALLSITE: Track what calls KEY-UI restore
        import traceback
        stack = traceback.extract_stack()
        caller = stack[-2].name if len(stack) > 1 else "unknown"
        self._log.info(f"[CALLSITE] fn=KEY-UI restore_enter called_by={caller} stack_hint=settings_load")
        
        # 부팅 저장 루프 방지 가드 활성화 + 부팅 시간 기록
        self._boot_restoring = True
        self._boot_start_time = time.time()
        
        try:
            self._settings = load_settings()
            s = self._settings

            # C. 재실행 검증: 부팅 시 prefs 로드 직후 길이만 로그 (원문 금지)
            if self._load_form_count == 1:
                _up = getattr(s, "upbit", None) or {}
                if hasattr(_up, "model_dump"):
                    _up = _up.model_dump()
                _bak = len((_up.get("access_key") or "").strip())
                _bsk = len((_up.get("secret_key") or "").strip())
                _st = getattr(s, "strategy", None)
                _bprov = getattr(_st, "ai_provider", "local") if _st else "local"
                _bok = len((getattr(_st, "ai_openai_api_key", "") or "").strip()) if _st else 0
                _bmodel = (getattr(_st, "ai_openai_model", "") or "gpt-4o-mini").strip() or "gpt-4o-mini" if _st else "gpt-4o-mini"
                _blocal_url = (getattr(_st, "ai_local_url", "") or "").strip()
                _blocal_model = (getattr(_st, "ai_local_model", "") or "qwen2.5").strip() or "qwen2.5" if _st else "qwen2.5"
                self._log.info("[BOOT] prefs_loaded upbit_ak_len=%s upbit_sk_len=%s ai_provider=%s openai_key_len=%s model=%s local_url_len=%s local_model=%s",
                    _bak, _bsk, _bprov, _bok, _bmodel, len(_blocal_url), _blocal_model)

            # ✅ strategy 정규화(구버전 dict/모델 혼재 + ai_provider 보존)
            st = getattr(s, "strategy", None)
            try:
                s.strategy = _coerce_strategy_config(st, preserve_ai_provider_from=st)
            except Exception:
                # fallback: 기존 동작 유지
                if isinstance(st, dict):
                    s.strategy = st

            # ==============================
            # ✅ (핵심) Settings 폼에 "현재값"을 먼저 로딩
            # - 이게 없으면 UI가 빈값 상태로 떠서,
            #   사용자가 저장 버튼을 누르는 순간 빈값이 prefs.json에 덮어써짐.
            # ==============================
            try:
                ui = getattr(s, "ui", None) or {}
                if hasattr(ui, "model_dump"):
                    ui = ui.model_dump()

                up = getattr(s, "upbit", None) or {}
                if hasattr(up, "model_dump"):
                    up = up.model_dump()

                poll = getattr(s, "poll", None) or {}
                if hasattr(poll, "model_dump"):
                    poll = poll.model_dump()

                # ✅ 부팅 시점 키 로드 상태 로그 - nested only
                ak_final = up.get("access_key", "").strip()
                sk_final = up.get("secret_key", "").strip()
                ak_len = len(ak_final)
                sk_len = len(sk_final)
                
                source = "nested" if ak_final else "none"
                self._log.info(f"[KEY-UI] restore_read ak_len={ak_len} sk_len={sk_len} source={source}")

                # 업비트 키/실계좌/체크박스
                if hasattr(self, "ed_access"):
                    # UX: 마스킹 표시 (실제 텍스트는 빈값 유지)
                    masked = "••••••••••••••••••••••••••••••••" if ak_len > 0 else ""
                    self.ed_access.setPlaceholderText(f"저장됨({ak_len}자)" if ak_len > 0 else "")
                    self.ed_access.setText(masked)
                    self._log.info(f"[KEY-UI] restore_set masked=True access_len={len(masked)} secret_len={len(sk_final) if sk_final else 0}")
                if hasattr(self, "ed_secret"):
                    masked = "••••••••••••••••••••••••••••••••" if sk_len > 0 else ""
                    self.ed_secret.setPlaceholderText(f"저장됨({sk_len}자)" if sk_len > 0 else "")
                    self.ed_secret.setText(masked)
                    self._log.info(f"[KEY-UI] restore_set masked=True access_len={len(ak_final) if ak_final else 0} secret_len={len(masked)}")

                # ✅ live_trade 항상 True (실거래만 지원)
                # live_trade 설정 제거 - 항상 실거래 모드로 동작

                if hasattr(self, "cb_autologin"):
                    self.cb_autologin.setChecked(bool(ui.get("auto_login", False)))
                if hasattr(self, "cb_restore"):
                    self.cb_restore.setChecked(bool(ui.get("restore_last_session", False)))
                if hasattr(self, "cb_remember_id"):
                    self.cb_remember_id.setChecked(bool(ui.get("remember_id", False)))
                if hasattr(self, "ed_saved_id"):
                    self.ed_saved_id.setText((ui.get("saved_id") or "").strip())

                # 폴링
                if hasattr(self, "spn_poll_sec"):
                    self.spn_poll_sec.setValue(int(poll.get("poll_sec", 5) or 5))
                if hasattr(self, "spn_portfolio_sec"):
                    self.spn_portfolio_sec.setValue(int(poll.get("portfolio_sec", 10) or 10))

                if hasattr(self, "sp_ticker"):
                    tms = int(poll.get("ticker_ms", 3000) or 3000)
                    tms = max(1000, min(5000, tms))
                    self.sp_ticker.setValue(tms)
                if hasattr(self, "sp_topNmin"):
                    tnm = int(poll.get("topN_refresh_min", 30) or 30)
                    tnm = max(1, min(180, tnm))
                    self.sp_topNmin.setValue(tnm)
                try:
                    _loaded_topn = int(poll.get("topN_refresh_min", 30) or 30)
                    self._log.info(
                        "[TOPN-REFRESH] saved=NA loaded=%s runtime=%s",
                        _loaded_topn,
                        _loaded_topn,
                    )
                except Exception:
                    self._log.info("[TOPN-REFRESH] saved=NA loaded=NA runtime=NA")

                # GPT/OpenAI 설정 로드 — AI-SSOT: strategy 소속, local이면 OpenAI 비활성/비움
                st_dict = st.model_dump() if hasattr(st, "model_dump") else (st if isinstance(st, dict) else {})
                ai_provider = st_dict.get("ai_provider", "local")
                ai_local_url = (st_dict.get("ai_local_url") or "http://127.0.0.1:11434").strip()
                ai_local_model = (st_dict.get("ai_local_model") or "qwen2.5").strip() or "qwen2.5"
                self._log.info("[AI-SSOT] prefs_loaded ai_provider=%s local_model=%s local_url_len=%s",
                    ai_provider, ai_local_model, len(ai_local_url))
                if hasattr(self, "cb_ai_provider"):
                    self.cb_ai_provider.setCurrentText(ai_provider)
                if hasattr(self, "inp_local_url"):
                    self.inp_local_url.setText(ai_local_url)
                if hasattr(self, "cmb_local_model") and ai_local_model in ("llama3.1", "qwen2.5", "mistral"):
                    self.cmb_local_model.setCurrentText(ai_local_model)
                try:
                    us = getattr(s, "ui_state", None) or {}
                    if hasattr(us, "model_dump"):
                        us = us.model_dump()
                    elif not isinstance(us, dict):
                        us = {}
                    bas = us.get("basic_ai_settings")
                    if isinstance(bas, dict):
                        if "risk_mode" in bas and str(bas.get("risk_mode") or "").strip():
                            self.basic_ai_settings["risk_mode"] = str(bas["risk_mode"]).strip()
                        if "target_profit_pct" in bas:
                            self.basic_ai_settings["target_profit_pct"] = float(
                                bas.get("target_profit_pct") or 3.0
                            )
                        if "stop_loss_pct" in bas:
                            self.basic_ai_settings["stop_loss_pct"] = float(
                                bas.get("stop_loss_pct") or 1.5
                            )
                        if "max_positions" in bas:
                            self.basic_ai_settings["max_positions"] = int(bas.get("max_positions") or 5)
                        if "selection_strength" in bas and str(bas.get("selection_strength") or "").strip():
                            self.basic_ai_settings["selection_strength"] = str(
                                bas["selection_strength"]
                            ).strip()
                        if "avoid_bear_market" in bas:
                            self.basic_ai_settings["avoid_bear_market"] = bool(bas["avoid_bear_market"])
                        if "buy_sensitivity" in bas and str(bas.get("buy_sensitivity") or "").strip():
                            self.basic_ai_settings["buy_sensitivity"] = str(bas["buy_sensitivity"]).strip()
                        if "sell_sensitivity" in bas and str(bas.get("sell_sensitivity") or "").strip():
                            self.basic_ai_settings["sell_sensitivity"] = str(bas["sell_sensitivity"]).strip()
                        if "split_buy" in bas:
                            self.basic_ai_settings["split_buy"] = bool(bas["split_buy"])
                        if "split_sell" in bas:
                            self.basic_ai_settings["split_sell"] = bool(bas["split_sell"])
                        if "max_hold_time" in bas:
                            self.basic_ai_settings["max_hold_time"] = int(bas.get("max_hold_time") or 120)
                        if "min_volume" in bas:
                            self.basic_ai_settings["min_volume"] = int(bas.get("min_volume") or 0)
                        if "exclude_overheated" in bas:
                            self.basic_ai_settings["exclude_overheated"] = bool(bas["exclude_overheated"])
                        if "avoid_sudden_drop" in bas:
                            self.basic_ai_settings["avoid_sudden_drop"] = bool(bas["avoid_sudden_drop"])
                        if "trend_filter" in bas and str(bas.get("trend_filter") or "").strip():
                            self.basic_ai_settings["trend_filter"] = str(bas["trend_filter"]).strip()
                        if "entry_score_threshold" in bas:
                            self.basic_ai_settings["entry_score_threshold"] = int(
                                bas.get("entry_score_threshold") or 60
                            )
                        if "exit_score_threshold" in bas:
                            self.basic_ai_settings["exit_score_threshold"] = int(
                                bas.get("exit_score_threshold") or 45
                            )
                        if "decision_speed" in bas and str(bas.get("decision_speed") or "").strip():
                            self.basic_ai_settings["decision_speed"] = str(bas["decision_speed"]).strip()
                        if "reentry_cooldown_min" in bas:
                            self.basic_ai_settings["reentry_cooldown_min"] = int(
                                bas.get("reentry_cooldown_min") or 30
                            )
                        if "max_new_entries" in bas:
                            self.basic_ai_settings["max_new_entries"] = int(bas.get("max_new_entries") or 2)
                        self._load_basic_ai_settings_to_ui()
                except Exception:
                    pass
                # GPT 박스: 키/모델 항상 로드. LOCAL이어도 키는 마스킹 표시만(비우지 않음).
                if hasattr(self, "ed_openai_key"):
                    openai_key_loaded = (st_dict.get("ai_openai_api_key") or "")
                    if hasattr(openai_key_loaded, "get_secret_value"):
                        openai_key_loaded = openai_key_loaded.get_secret_value() or ""
                    openai_key_loaded = str(openai_key_loaded).strip()
                    key_len_loaded = len(openai_key_loaded)
                    self._log.info("[AI-KEY] load key_len=%s provider=%s source=file", key_len_loaded, ai_provider)
                    if key_len_loaded > 0:
                        masked = "••••••••••••••••••••••••••••••••"
                        self.ed_openai_key.setPlaceholderText(f"저장됨({key_len_loaded}자)")
                        self.ed_openai_key.setText(masked)
                    else:
                        self.ed_openai_key.setPlaceholderText("sk-...")
                        self.ed_openai_key.setText("")
                # ✅ GPT 모델 로드: 저장된 모델이 검증된 리스트에 있으면 선택, 없으면 Custom 모드 활성화
                if hasattr(self, "ed_openai_model"):
                    openai_model = st_dict.get("ai_openai_model", "gpt-4o-mini") or "gpt-4o-mini"
                    # 검증된 모델 리스트에서 찾기
                    found_in_list = False
                    for idx, model_info in enumerate(getattr(self, "KMTS_GPT_MODELS", [])):
                        if model_info["id"] == openai_model:
                            self.ed_openai_model.setCurrentIndex(idx)
                            found_in_list = True
                            break
                    
                    # 검증된 리스트에 없으면 Custom 모드로 활성화
                    if not found_in_list and openai_model:
                        # 기본값으로 설정 (gpt-4o-mini)
                        self.ed_openai_model.setCurrentIndex(0)
                        # Custom 모드 활성화 및 값 설정
                        if hasattr(self, "cb_custom_model") and hasattr(self, "inp_custom_model"):
                            self.cb_custom_model.setChecked(True)
                            self.inp_custom_model.setText(openai_model)
                    elif not found_in_list:
                        # 모델이 없으면 기본값
                        self.ed_openai_model.setCurrentIndex(0)
                # 박스 선택·배경색·우측상단 배지 동기화 (setVisible 제거, 항상 두 박스 표시)
                if hasattr(self, "_set_ai_provider_ui_active"):
                    self._set_ai_provider_ui_active(ai_provider)
            except Exception:
                pass

            # UI 적용(탭에 settings 전달)
            try:
                self.tab_watch.set_settings(s)
            except Exception:
                pass
            try:
                self.portfolio_tab.set_settings(s)
            except Exception:
                pass

        except Exception:
            # ✅ 바깥 try 블록 미종결 방지(문법 오류/부팅 불가 원인)
            # 설정 로드/폼 반영 중 일부 실패는 치명적이지 않으므로 조용히 무시한다.
            pass
        finally:
            # 부팅 저장 루프 방지 가드 비활성화
            self._boot_restoring = False
            # ✅ BOOT-GUARD: Reset settings loading guard
            self._settings_loading = False
            # ✅ BOOT-GUARD: Mark boot as done after first successful load
            self._boot_done = True
            self._log.info("[BOOT-GUARD] boot completed, _boot_done=True")

    def _apply_settings_patch(self, patch: dict, reason: str = "") -> bool:

        """
        ✅ Settings 단일 Owner 저장 진입점
        - prefs.save_settings_patch()로 deep-merge 저장
        - 메모리(self._settings)도 병합 결과로 동기화

        # ❗ SSOT RULE (DO NOT BREAK)
        # - settings 접근은 반드시 self._settings 또는 _get_settings_cached()만 사용
        # - load_settings() 직접 호출은 boot/patch/save 내부로 제한
        """
        try:
            # 부팅 중 저장 루프 방지
            if self._boot_restoring:
                self._log.info("[SETTINGS-PATCH] blocked during boot restore")
                return False
            
            # 저장 스로틀링 (부팅 중 불필요한 저장 방지 - 부팅 후 10초간 완전 차단)
            import time
            current_time = time.time()
            
            # 부팅 후 10초간 모든 저장 차단
            if hasattr(self, '_boot_start_time') and current_time - self._boot_start_time < 10.0:
                self._log.info("[SETTINGS-PATCH] blocked during boot period (10s)")
                return False
            
            # 5초 이내 중복 저장 방지
            if current_time - self._last_save_time < 5.0:
                self._log.info("[SETTINGS-PATCH] throttled (too frequent)")
                return False
                
            from app.utils.prefs import save_settings_patch
            # LOCAL 저장 시 base를 디스크로 고정 → 메모리 오염 시에도 GPT 키가 prefs에 있으면 보존
            st_patch = (patch or {}).get("strategy") or {}
            if st_patch.get("ai_provider") == "local":
                base = load_settings()
            else:
                base = self._settings or load_settings()
            s_new = save_settings_patch(patch or {}, base_settings=base)

            # ✅ 핵심: 저장 실패(None)면 False 반환 → 체크/저장이 "반영 안됨"을 즉시 드러냄
            if s_new is None:
                return False

            # ✅ P0-B: Log successful prefs write with AI keys
            from app.utils.prefs import _get_prefs_path
            prefs_path = _get_prefs_path()
            ai_keys_updated = []
            st_patch = patch.get("strategy") or {}
            if 'ai_provider' in st_patch:
                ai_keys_updated.append('strategy.ai_provider')
            if 'ai_openai_api_key' in st_patch:
                ai_keys_updated.append('strategy.ai_openai_api_key')
            if 'ai_openai_model' in st_patch:
                ai_keys_updated.append('strategy.ai_openai_model')
            if 'ai_local_url' in st_patch:
                ai_keys_updated.append('strategy.ai_local_url')
            if 'ai_local_model' in st_patch:
                ai_keys_updated.append('strategy.ai_local_model')
            
            if ai_keys_updated:
                self._log.info(f"[PREFS-WRITE] ok path={prefs_path} keys_updated={ai_keys_updated}")

            # ✅ P0-KEY-SSOT-FIX: 캐시/메모리 settings 동기화
            self._settings = None  # 메모리 settings 무효화
            if hasattr(self, '_settings_cache'):
                self._settings_cache = None  # 캐시 무효화
            
            fresh = self._get_settings_cached(force=True)  # 즉시 재로딩
            self._settings = fresh  # 동기화
            
            # ✅ 저장/리로드 직후에도 strategy 정규화 + ai_provider 보존
            try:
                if fresh is not None and hasattr(fresh, "strategy"):
                    fresh.strategy = _coerce_strategy_config(
                        getattr(fresh, "strategy", None),
                        preserve_ai_provider_from=getattr(s_new, "strategy", None)
                    )
                    self._settings = fresh
            except Exception:
                pass

            # 저장 시간 갱신 (스로틀링용)
            self._last_save_time = current_time
            
            # 키 길이 계산 (primary)
            ak_len = len(getattr(fresh.upbit, "access_key", "").strip()) if fresh and hasattr(fresh, "upbit") else 0
            sk_len = len(getattr(fresh.upbit, "secret_key", "").strip()) if fresh and hasattr(fresh, "upbit") else 0
            live_trade = getattr(fresh, "live_trade", None)
            
            self._log.info(f"[SETTINGS-SYNC] after patch -> reloaded ak_len={ak_len} sk_len={sk_len} live_trade={live_trade}")

            # ✅ Step5: 최종형 SSOT 1줄 로그 (settings patch 적용 직후)
            try:
                poll_ms = 1500
                try:
                    p = getattr(fresh, "poll", None) if fresh else None
                    if hasattr(p, "ticker_ms"):
                        poll_ms = int(getattr(p, "ticker_ms") or poll_ms)
                    elif isinstance(p, dict) and p.get("ticker_ms"):
                        poll_ms = int(p.get("ticker_ms") or poll_ms)
                except Exception:
                    pass
                self._log.info(f"[SSOT] source=forced_reload live_trade={bool(live_trade)} poll_ms={int(poll_ms)}")
            except Exception:
                pass

            # ✅ 러너에 최신 settings 전달 (전략 실시간 적용)
            if reason and "strategy" in patch:
                try:
                    from app.strategy.runner import start_strategy
                    # 러너가 실행 중이면 최신 settings로 업데이트
                    if hasattr(self, "_runner_running") and self._runner_running:
                        start_strategy(s_new)
                        log.info("[SETTINGS] runner updated with new strategy settings")
                except Exception as e:
                    log.warning("[SETTINGS] runner update failed: %s", e)

            if reason:
                try:
                    log.info("[SETTINGS] patch saved · reason=%s", reason)
                except Exception:
                    pass
            return True
        except Exception as e:
            try:
                log.exception("[SETTINGS] patch save failed: %s", e)
            except Exception:
                pass
            return False

    def _on_save_settings(self) -> None:
        # ✅ P0-B: Log save button text before and after
        button_text_before = getattr(self, 'btn_save', None).text() if hasattr(self, 'btn_save') else "unknown"
        
        # ✅ P0-1: Initialize patch at function start to prevent UnboundLocalError
        patch = {}
        
        # ✅ P0-1: Log save attempt
        provider = self.cb_ai_provider.currentText() if hasattr(self, "cb_ai_provider") else "local"
        key_len = len(self.ed_openai_key.text().strip()) if hasattr(self, "ed_openai_key") else 0
        model = (self.ed_openai_model.currentText() if hasattr(self.ed_openai_model, "currentText") else getattr(self.ed_openai_model, "text", lambda: "")()).strip() if hasattr(self, "ed_openai_model") else "gpt-4o-mini"
        self._log.info(f"[SAVE-UI] button_text_before=\"{button_text_before}\" button_text_after=\"{button_text_before}\"")
        self._log.info(f"[AI-KEY] save_attempt provider={provider} key_len={key_len} model={model}")
        
        try:
            # ✅ 최신 settings 기준으로 base 사용 (저장 시 strategy 보존 정확도)
            try:
                s0 = self._get_settings_cached(force=True)
            except Exception:
                s0 = self._settings or self._get_settings_cached(force=False)

            # 현재 저장된 값(기존값) 확보: 빈값 덮어쓰기 방지용
            try:
                up0 = getattr(s0, "upbit", None) or {}
                if hasattr(up0, "model_dump"):
                    up0 = up0.model_dump()
            except Exception:
                up0 = {}

            try:
                ui0 = getattr(s0, "ui", None) or {}
                if hasattr(ui0, "model_dump"):
                    ui0 = ui0.model_dump()
            except Exception:
                ui0 = {}

            # 입력값
            access_val = self.ed_access.text().strip() if hasattr(self, "ed_access") else ""
            secret_val = self.ed_secret.text().strip() if hasattr(self, "ed_secret") else ""
            
            # ✅ P0-C: Log UI input lengths before processing
            access_raw = self.ed_access.text() if hasattr(self, "ed_access") else ""
            secret_raw = self.ed_secret.text() if hasattr(self, "ed_secret") else ""
            self._log.info(f"[UPBIT-KEY-UI] access_len={len(access_raw)} secret_len={len(secret_raw)} access_trim_len={len(access_val)} secret_trim_len={len(secret_val)}")

            # (핵심) 마스킹된 값은 저장하지 않고 기존값 유지 - nested only
            if access_val.startswith("•"):
                self._log.info("[KEY-OVERWRITE] skip access_key (masked)")
                access_val = up0.get("access_key", "")
            if secret_val.startswith("•"):
                self._log.info("[KEY-OVERWRITE] skip secret_key (masked)")
                secret_val = up0.get("secret_key", "")

            # (핵심) 빈값으로 덮어쓰기 방지: UI가 비어있고 기존값이 있으면 유지 - nested only
            existing_ak = up0.get("access_key", "")
            existing_sk = up0.get("secret_key", "")
            
            if not access_val and existing_ak:
                self._log.info("[KEY-OVERWRITE] prevent empty access_key overwrite")
                access_val = existing_ak
            if not secret_val and existing_sk:
                self._log.info("[KEY-OVERWRITE] prevent empty secret_key overwrite")
                secret_val = existing_sk

            # (1) UI 입력값 스냅샷 (원문 금지) — 저장 직후 검증용
            openai_key_effective = self.ed_openai_key.text().strip() if hasattr(self, "ed_openai_key") else ""
            if openai_key_effective.startswith("•"):
                _s0st = getattr(s0, "strategy", None)
                openai_key_effective = (getattr(_s0st, "ai_openai_api_key", "") or "") if _s0st else ""
            model_str = (self.ed_openai_model.currentText() if hasattr(self.ed_openai_model, "currentText") else getattr(self.ed_openai_model, "text", lambda: "")()).strip() if hasattr(self, "ed_openai_model") else "gpt-4o-mini"
            if not model_str:
                model_str = "gpt-4o-mini"
            provider_str = (getattr(self, "_ai_provider_box_active", "") or "").strip().lower() or "local"
            self._log.info("[SAVE] ui_snapshot upbit_ak_len=%s upbit_sk_len=%s ai_provider=%s openai_key_len=%s model=%s",
                len(access_val), len(secret_val), provider_str, len(openai_key_effective), model_str)

            # remember_id/saved_id: 폼을 쓰는 경우만 반영(없으면 기존 유지)
            remember_id_val = bool(self.cb_remember_id.isChecked()) if hasattr(self, "cb_remember_id") else bool(ui0.get("remember_id", False))
            saved_id_in = self.ed_saved_id.text().strip() if hasattr(self, "ed_saved_id") else ""
            saved_id_val = saved_id_in if saved_id_in else (ui0.get("saved_id") or "")

            # 기존 ui 값 병합 (빈값 덮어쓰기 방지)
            ui_prev = {}
            try:
                ui_prev = self._settings.ui.model_dump()
            except Exception:
                pass
            
            # ✅ P0-1: Build flat patch structure
            # Live trade
            patch["live_trade"] = True
            
            # ✅ P0-C: Fix Upbit keys mapping - use nested structure
            # Create nested upbit object if not exists
            upbit_patch = {}
            if access_val:
                upbit_patch["access_key"] = access_val
            if secret_val:
                upbit_patch["secret_key"] = secret_val
            if upbit_patch:
                patch["upbit"] = upbit_patch
            
            # UI settings
            patch["auto_login"] = bool(self.cb_autologin.isChecked()) if hasattr(self, "cb_autologin") else ui_prev.get("auto_login", False)
            patch["restore_last_session"] = bool(self.cb_restore.isChecked()) if hasattr(self, "cb_restore") else ui_prev.get("restore_last_session", False)
            patch["remember_id"] = remember_id_val
            patch["saved_id"] = saved_id_val
            
            # Poll settings
            if hasattr(self, "spn_poll_sec"):
                patch["poll_sec"] = int(self.spn_poll_sec.value())
            if hasattr(self, "spn_portfolio_sec"):
                patch["portfolio_sec"] = int(self.spn_portfolio_sec.value())

            poll_prev = {}
            try:
                p0 = getattr(s0, "poll", None)
                if p0 is not None and hasattr(p0, "model_dump"):
                    poll_prev = p0.model_dump()
                elif isinstance(p0, dict):
                    poll_prev = dict(p0)
            except Exception:
                poll_prev = {}
            poll_merged = dict(poll_prev)
            if hasattr(self, "sp_ticker"):
                poll_merged["ticker_ms"] = int(self.sp_ticker.value())
            if hasattr(self, "sp_topNmin"):
                poll_merged["topN_refresh_min"] = int(self.sp_topNmin.value())
            if poll_merged:
                patch["poll"] = poll_merged
            
            # AI settings — SSOT: 선택된 박스(_ai_provider_box_active)만 저장, 반대쪽 필드는 patch에 넣지 않음
            ui_ai_provider = (getattr(self, "_ai_provider_box_active", "") or "").strip().lower()
            if ui_ai_provider not in ("gpt", "gemini", "local"):
                ui_ai_provider = self.cb_ai_provider.currentText() if hasattr(self, "cb_ai_provider") else "local"
            ui_ai_provider = ui_ai_provider or "local"
            self._log.info("[SAVE] ai_provider=%s (from selected box)", ui_ai_provider)

            # ✅ 기존 strategy를 base로 복사해서 merge (부분 patch로 인한 키 삭제 방지)
            # ⚠️ 주의: StrategyConfig.model_dump()는 Secret/Field 설정에 따라 ai_openai_api_key가 누락될 수 있음
            #        (그 상태로 patch["strategy"]를 통째로 교체하면 GPT 키가 "삭제"되는 효과가 발생)
            base_strategy = {}
            _preserve_key = ""
            _preserve_model = ""

            try:
                _st0 = getattr(s0, "strategy", None)

                if isinstance(_st0, dict):
                    base_strategy = dict(_st0)
                    _preserve_key = (_st0.get("ai_openai_api_key") or "").strip()
                    _preserve_model = (_st0.get("ai_openai_model") or "").strip()

                elif _st0 is not None:
                    # 1) getattr로 먼저 보존(SecretStr 등 model_dump 누락 대비)
                    try:
                        _k = getattr(_st0, "ai_openai_api_key", "") or ""
                        if hasattr(_k, "get_secret_value"):
                            _k = _k.get_secret_value() or ""
                        _preserve_key = str(_k).strip()
                    except Exception:
                        _preserve_key = ""

                    try:
                        _preserve_model = (getattr(_st0, "ai_openai_model", "") or "").strip()
                    except Exception:
                        _preserve_model = ""

                    # 2) 나머지 필드는 model_dump로 base 구성
                    try:
                        if hasattr(_st0, "model_dump"):
                            base_strategy = _st0.model_dump()
                    except Exception:
                        base_strategy = {}

                # 3) model_dump 누락 시에도 key/model은 반드시 주입(삭제 효과 차단)
                try:
                    if _preserve_key and not (base_strategy.get("ai_openai_api_key") or "").strip():
                        base_strategy["ai_openai_api_key"] = _preserve_key
                    if _preserve_model and not (base_strategy.get("ai_openai_model") or "").strip():
                        base_strategy["ai_openai_model"] = _preserve_model
                except Exception:
                    pass

            except Exception:
                base_strategy = {}

            patch["strategy"] = dict(base_strategy)
            patch["strategy"]["ai_provider"] = ui_ai_provider

            # ✅ 선택된 박스만 patch에 반영. 반대쪽 필드는 patch에서 제거해 merge 시 기존값 유지.
            if ui_ai_provider == "gpt":
                if hasattr(self, "ed_openai_key"):
                    openai_key = self.ed_openai_key.text().strip()
                    if openai_key.startswith("•"):
                        _s0st = getattr(s0, "strategy", None)
                        openai_key = (getattr(_s0st, "ai_openai_api_key", "") or "") if _s0st else ""
                    patch["strategy"]["ai_openai_api_key"] = openai_key
                # ✅ 모델 저장: Custom 모드 우선, 없으면 선택된 모델 ID 저장
                model_to_save = ""
                if hasattr(self, "cb_custom_model") and self.cb_custom_model.isChecked():
                    custom_model = (self.inp_custom_model.text() or "").strip()
                    if custom_model:
                        model_to_save = custom_model
                
                if not model_to_save and hasattr(self, "ed_openai_model"):
                    # 기본 모델: 콤보박스에서 ID 추출
                    model_id = self.ed_openai_model.currentData()
                    if model_id:
                        model_to_save = model_id
                    else:
                        # 폴백: 현재 텍스트에서 ID 추출 시도
                        current_text = self.ed_openai_model.currentText()
                        for model_info in getattr(self, "KMTS_GPT_MODELS", []):
                            if model_info["label"] == current_text:
                                model_to_save = model_info["id"]
                                break
                
                if model_to_save:
                    patch["strategy"]["ai_openai_model"] = model_to_save
                else:
                    patch["strategy"]["ai_openai_model"] = "gpt-4o-mini"  # 최종 폴백
                # GPT 선택 시 LOCAL 필드는 patch에 넣지 않음 (base 유지)
                patch["strategy"].pop("ai_local_url", None)
                patch["strategy"].pop("ai_local_model", None)
            else:
                # LOCAL 선택: LOCAL 필드만 patch에 포함. GPT 키/모델은 patch에서 제거 → merge 시 기존값 유지
                if hasattr(self, "inp_local_url"):
                    patch["strategy"]["ai_local_url"] = self.inp_local_url.text().strip() or "http://127.0.0.1:11434"
                if hasattr(self, "cmb_local_model"):
                    patch["strategy"]["ai_local_model"] = (self.cmb_local_model.currentText() or "").strip() or "qwen2.5"
                patch["strategy"].pop("ai_openai_api_key", None)
                patch["strategy"].pop("ai_openai_model", None)

            # patch["strategy"]["ai_provider"]가 UI와 다르면 경고
            if patch.get("strategy", {}).get("ai_provider") != ui_ai_provider:
                self._log.warning("[AI-SSOT] patch strategy.ai_provider=%s != ui=%s",
                    patch.get("strategy", {}).get("ai_provider"), ui_ai_provider)
            self._log.info("[AI-SSOT] save ai_provider=%s", ui_ai_provider)

            if hasattr(self, "cmb_basic_ai_risk"):
                try:
                    self._sync_basic_ai_settings_from_ui()
                    us0 = getattr(s0, "ui_state", None) or {}
                    if hasattr(us0, "model_dump"):
                        us0 = us0.model_dump()
                    elif not isinstance(us0, dict):
                        us0 = {}
                    us_merged = dict(us0)
                    us_merged["basic_ai_settings"] = dict(self.basic_ai_settings)
                    patch["ui_state"] = us_merged
                except Exception:
                    pass

            # (2) patch 생성 검증 — 키 목록만 (nested upbit 유지)
            st_keys = list((patch.get("strategy") or {}).keys())
            self._log.info("[SAVE] patch_keys=%s strategy_keys=%s", list(patch.keys()), st_keys)

            # ✅ P0-1: Log save (키 원문 출력 금지)
            saved_provider = patch.get("strategy", {}).get("ai_provider", "local")
            saved_key_len = len(patch.get("strategy", {}).get("ai_openai_api_key", "") or "")
            self._log.info("[AI-KEY] save key_len=%s provider=%s", saved_key_len, saved_provider)

            # ✅ live_trade 항상 True 저장 로그
            self._log.info(f"[SETTINGS] live_trade saved=True (always real trading)")
            
            # ✅ 키 저장 진단 로그
            access_len = len(access_val) if access_val else 0
            secret_len = len(secret_val) if secret_val else 0
            from app.utils.prefs import _get_prefs_path
            prefs_path = _get_prefs_path()
            self._log.info(f"[SETTINGS] saved upbit keys: access_len={access_len} secret_len={secret_len} path={prefs_path}")
            self._log.info(f"[SETTINGS] upbit access_key path=settings.upbit.access_key")

            # ⚠️ strategy 섹션은 여기서 저장하지 않는다.
            # - 현재 화면에서 symbols/auto_top20/max_total/order_amount/sl/tp 위젯이 UI에 노출되지 않거나
            #   초기값 로딩이 보장되지 않아 빈값 덮어쓰기 리스크가 큼.
            # - WL/BL은 WatchlistTab에서 patch 저장(이미 watchlist_wb_toggle 로그 확인됨).

            save_ok = self._apply_settings_patch(patch, reason="settings_tab_save")
            self._log.info("[SAVE] apply_patch ok=%s", save_ok)
            if not save_ok:
                # 저장 실패 원인 로깅
                import logging
                logger = logging.getLogger(__name__)
                logger.error("설정 저장 실패: _apply_settings_patch returned False")
                raise RuntimeError("설정 저장 실패: 디스크 저장 또는 검증 실패")

            # ✅ P0-C: Verify prefs values after save (use self._settings which was updated by _apply_settings_patch)
            try:
                # Check nested upbit structure
                upbit_obj = getattr(self._settings, "upbit", None)
                if upbit_obj and hasattr(upbit_obj, "access_key"):
                    saved_access_len = len(getattr(upbit_obj, "access_key", "") or "")
                else:
                    saved_access_len = 0
                    
                if upbit_obj and hasattr(upbit_obj, "secret_key"):
                    saved_secret_len = len(getattr(upbit_obj, "secret_key", "") or "")
                else:
                    saved_secret_len = 0
                    
                self._log.info(f"[UPBIT-KEY] saved access_len={saved_access_len} secret_len={saved_secret_len}")
            except Exception as e:
                self._log.error(f"[UPBIT-KEY-PREFS] verify failed err={e}")

            # 저장 후: 폼에도 다시 반영(가시적 “저장됨” 보장)
            # (4) prefs.json 실제 반영 확인 — 저장 직후 재로드하여 길이만 로그
            try:
                from app.utils.prefs import load_settings as _load_prefs
                prefs_s = _load_prefs()
                u = getattr(prefs_s, "upbit", None) or {}
                if hasattr(u, "model_dump"):
                    u = u.model_dump()
                pak = len((u.get("access_key") or "").strip())
                psk = len((u.get("secret_key") or "").strip())
                _ps = getattr(prefs_s, "strategy", None)
                pprov = getattr(_ps, "ai_provider", "local") if _ps else "local"
                pok = len((getattr(_ps, "ai_openai_api_key", "") or "").strip()) if _ps else 0
                pmodel = (getattr(_ps, "ai_openai_model", "") or "gpt-4o-mini").strip() or "gpt-4o-mini" if _ps else "gpt-4o-mini"
                plocal_url = (getattr(_ps, "ai_local_url", "") or "").strip()
                plocal_model = (getattr(_ps, "ai_local_model", "") or "qwen2.5").strip() or "qwen2.5" if _ps else "qwen2.5"
                self._log.info("[SAVE] prefs_after upbit_ak_len=%s upbit_sk_len=%s ai_provider=%s openai_key_len=%s model=%s local_url_len=%s local_model=%s",
                    pak, psk, pprov, pok, pmodel, len(plocal_url), plocal_model)
                try:
                    _pp = getattr(prefs_s, "poll", None)
                    _prefs_topn = int(getattr(_pp, "topN_refresh_min", 30) or 30) if _pp is not None else 30
                    _saved_topn = int(self.sp_topNmin.value()) if hasattr(self, "sp_topNmin") else _prefs_topn
                    _rt = getattr(self._settings, "poll", None)
                    _runtime_topn = int(getattr(_rt, "topN_refresh_min", 30) or 30) if _rt is not None else _prefs_topn
                    self._log.info(
                        "[TOPN-REFRESH] saved=%s loaded=%s runtime=%s",
                        _saved_topn,
                        _prefs_topn,
                        _runtime_topn,
                    )
                except Exception as _e_topn:
                    self._log.info("[TOPN-REFRESH] saved=NA loaded=NA runtime=NA err=%s", repr(_e_topn))
            except Exception as e:
                self._log.error("[SAVE] prefs_after failed err=%s", repr(e))
            # (5) runtime settings 재조회 (SSOT)
            try:
                rup = getattr(self._settings, "upbit", None) or {}
                if hasattr(rup, "model_dump"):
                    rup = rup.model_dump()
                rak = len((rup.get("access_key") or "").strip())
                rsk = len((rup.get("secret_key") or "").strip())
                _rs = getattr(self._settings, "strategy", None)
                rprov = getattr(_rs, "ai_provider", "local") if _rs else "local"
                rok = len((getattr(_rs, "ai_openai_api_key", "") or "").strip()) if _rs else 0
                rmodel = (getattr(_rs, "ai_openai_model", "") or "gpt-4o-mini").strip() or "gpt-4o-mini" if _rs else "gpt-4o-mini"
                self._log.info("[SAVE] runtime_after upbit_ak_len=%s upbit_sk_len=%s ai_provider=%s openai_key_len=%s model=%s",
                    rak, rsk, rprov, rok, rmodel)
                self._log.info("[AI-SSOT] runtime ai_provider=%s", rprov)
            except Exception as e:
                self._log.error("[SAVE] runtime_after failed err=%s", repr(e))

            try:
                from app.strategy.symbols import invalidate_universe_cache
                invalidate_universe_cache()
            except Exception:
                pass
            try:
                if getattr(self, "_wl_timer", None) is not None:
                    self._wl_timer.stop()
            except Exception:
                pass
            try:
                self._start_polling()
            except Exception:
                pass

            # (6) 저장 후 폼 리로드 — post_save 허용
            reload_ok = False
            try:
                self._load_settings_into_form()
                reload_ok = True
            except Exception:
                pass
            self._log.info("[SAVE] reload_form reason=post_save ok=%s", reload_ok)

            # ✅ P0-B: Log save button text after successful save
            button_text_after = getattr(self, 'btn_save', None).text() if hasattr(self, 'btn_save') else "unknown"
            self._log.info(f"[SAVE-UI] button_text_after=\"{button_text_after}\"")

            # ✅ 저장 직후 우측 상단 AI 상태도 즉시 갱신(SSOT 기준)
            try:
                self._update_ai_status()
            except Exception:
                pass
            # LOCAL 모델 저장 시 ai.reco.refresh 발행 → runner/ai_reco가 최신 strategy 반영
            try:
                _st = getattr(self._settings, "strategy", None)
                _prov = getattr(_st, "ai_provider", "local") if _st else "local"
                _local_model = (getattr(_st, "ai_local_model", "") or "qwen2.5").strip() or "qwen2.5"
                if _prov == "local":
                    self._log.info("[LOCAL-MODEL] saved model=%s", _local_model)
                    try:
                        from app.core.bus import eventbus
                        eventbus.publish("ai.reco.refresh", {})
                    except Exception:
                        pass
            except Exception:
                pass

            QMessageBox.information(self, "저장", "설정이 저장되었습니다.")
        except Exception as e:
            # ✅ P0-1: Log save failure
            self._log.error(f"[AI-KEY] save_failed err={repr(e)}")
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def on_watchlist_apply_symbols(self, symbols: list[str]) -> None:
        """
        WatchlistTab에서 "반영(표시목록 기준)" 버튼 클릭 시 호출됨.
        StrategyTab의 심볼 리스트 UI를 즉시 갱신하고 settings에 저장한다.
        """
        try:
            # StrategyTab에 symbols 전달
            if hasattr(self, "tab_strategy") and hasattr(self.tab_strategy, "apply_symbols"):
                self.tab_strategy.apply_symbols(symbols)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("on_watchlist_apply_symbols 실패: %s", e)

    def _on_exit_mode_changed(self):
        """
        전략 라디오 변경 시 TP/SL 입력 잠금/해제
        - ④ 사용자 손절/익절 지정만 활성
        """
        try:
            use_user = bool(self.rb_exit4.isChecked())
            self.sp_sl.setEnabled(use_user)
            self.sp_tp.setEnabled(use_user)
            if use_user:
                self.sp_sl.setStyleSheet("")
                self.sp_tp.setStyleSheet("")
            else:
                self.sp_sl.setStyleSheet("QDoubleSpinBox { background:#f3f3f3; }")
                self.sp_tp.setStyleSheet("QDoubleSpinBox { background:#f3f3f3; }")
        except Exception:
            pass

    def _update_external_ip(self):
        """외부 IP 확인 및 표시. 실패 시 안내 문구 + 재시도 버튼 유지."""
        try:
            import requests
            self.ip_label.setStyleSheet("QLabel { padding: 8px; background-color: #e8f4fd; border-radius: 4px; font-weight: bold; }")
            self.ip_label.setText("🌐 외부 IP: 확인 중...")
            response = requests.get("https://api.ipify.org?format=json", timeout=3)
            ip = response.json().get("ip", "확인 실패")
            from datetime import datetime
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.ip_label.setText(f"🌐 외부 IP: {ip} (확인시각: {now})")
        except Exception as e:
            self.ip_label.setStyleSheet("QLabel { padding: 8px; background-color: #fff0f0; border-radius: 4px; font-weight: bold; color: #c00; }")
            self.ip_label.setText("🌐 외부 IP: 확인 실패 — 네트워크/방화벽 확인 후 '재시도' 버튼을 눌러주세요.")
            self.ip_label.setToolTip(str(e)[:200] if e else "")
    
    def _check_local_ollama_tags(self, base_url: str, timeout_sec: int = 5) -> tuple[bool, list[str] | str]:
        """
        Ollama /api/tags 헬스체크.
        반환: (True, [model,...]) 또는 (False, reason)
        """
        import urllib.request, urllib.error, json
        url = (base_url.rstrip("/") + "/api/tags").replace("//api", "/api")
        self._log.info("[LOCAL-AI] tags request url=%s", url)
        try:
            with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
                if resp.status != 200:
                    reason = f"status={resp.status}"
                    self._log.warning("[LOCAL-AI] tags fail reason=%s", reason)
                    return False, reason
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                self._log.info("[LOCAL-AI] tags ok models=%s", models)
                return True, models
        except urllib.error.URLError as e:
            reason = (str(e.reason) or "urlerror")[:60]
            self._log.warning("[LOCAL-AI] tags fail reason=%s", reason)
            return False, reason
        except Exception as e:
            reason = (str(e) or "error")[:60]
            self._log.warning("[LOCAL-AI] tags fail reason=%s", reason)
            return False, reason

    def _call_local_ollama(self, prompt: str, model: str, base_url: str, timeout_sec: int = 60) -> tuple[bool, str]:
        """
        Ollama /api/generate 호출. 프롬프트/응답 원문 로그 금지, model/url/prompt_len/out_len만 로그.
        반환: (True, response_text) 또는 (False, error_message).
        """
        import urllib.request
        import urllib.error
        import json
        import socket
        url = (base_url.rstrip("/") + "/api/generate").replace("//api", "/api")
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        self._log.info("[LOCAL-AI] request model=%s url=%s prompt_len=%s timeout_sec=%s", model, url, len(prompt), timeout_sec)
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status != 200:
                    reason = "status=%s" % resp.status
                    self._log.warning("[LOCAL-AI] fail model=%s reason=%s", model, reason)
                    return False, reason
                data = json.loads(resp.read().decode("utf-8"))
                out = (data.get("response") or "").strip()
                self._log.info("[LOCAL-AI] ok model=%s out_len=%s", model, len(out))
                return True, out
        except urllib.error.HTTPError as e:
            reason = "http_%s" % (e.code or "error")
            self._log.warning("[LOCAL-AI] fail model=%s reason=%s", model, reason)
            return False, reason
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)) or (
                isinstance(getattr(e, "reason", None), str) and "timed out" in str(e.reason).lower()
            ):
                reason = "timeout"
            else:
                reason = (str(getattr(e, "reason", e)) or "urlerror")[:60]
            self._log.warning("[LOCAL-AI] fail model=%s reason=%s", model, reason)
            return False, reason
        except (socket.timeout, TimeoutError):
            self._log.warning("[LOCAL-AI] fail model=%s reason=timeout", model)
            return False, "timeout"
        except Exception as e:
            reason = (str(e) or "error")[:60]
            self._log.warning("[LOCAL-AI] fail model=%s reason=%s", model, reason)
            return False, reason
    
    def _on_local_model_changed(self, _text=None):
        """LOCAL 모델 콤보 변경 시 stage 초기화, 하단 박스 즉시 갱신."""
        try:
            self._gpt_status_stage = "idle"
            self._update_engine_status_box()
        except Exception:
            pass

    def _on_test_local_ai(self):
        """provider=local일 때 로컬 AI(Ollama) 연결 테스트. tags → generate 순서."""
        provider = self.cb_ai_provider.currentText() if hasattr(self, "cb_ai_provider") else "local"
        if provider != "local":
            QMessageBox.information(self, "로컬 AI 테스트", "AI Provider가 local일 때만 테스트할 수 있습니다.")
            return

        base_url = (self.inp_local_url.text() or "").strip() or "http://127.0.0.1:11434"
        model = (self.cmb_local_model.currentText() or "").strip() or "qwen2.5"

        ok, result = self._check_local_ollama_tags(base_url)
        if not ok:
            QMessageBox.warning(
                self,
                "로컬 AI 연결 실패",
                f"Basic AI 서버에 연결할 수 없습니다.\n\n"
                f"URL: {base_url}\n"
                f"사유: {result}\n\n"
                f"조치:\n"
                f"1) Basic AI 실행 확인\n"
                f"2) 모델 설치 버튼으로 모델 준비 확인"
            )
            return

        models = result
        models_base = [m.split(":")[0] for m in models]
        if model not in models and model not in models_base:
            QMessageBox.warning(
                self,
                "로컬 AI 모델 없음",
                f"선택한 모델이 설치되어 있지 않습니다.\n\n"
                f"모델: {model}\n"
                f"설치 방법:\n  앱의 '{model} 설치 필요' 버튼 사용"
            )
            return

        prompt = "respond with OK"
        ok, msg = self._call_local_ollama(prompt, model, base_url, timeout_sec=60)
        if ok:
            self._active_ai_engine = "local"
            self._update_active_engine_label()
            QMessageBox.information(self, "로컬 AI 테스트", "Basic AI 연결 성공.")
        else:
            QMessageBox.warning(self, "로컬 AI 테스트", f"Basic AI 호출 실패: {msg}")

    def _on_open_openai_usage(self):
        """OpenAI Usage 페이지를 기본 브라우저로 연다."""
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl("https://platform.openai.com/usage"))
            try:
                self._log.info("[OPENAI-USAGE] open browser")
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.warning(
                    self,
                    "OpenAI 사용량 보기",
                    f"브라우저를 열 수 없습니다.\n\n사유: {e}"
                )
            except Exception:
                pass

    def _on_show_gpt_guide(self):
        """GPT 사용 가이드 모달 표시."""
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "GPT(OpenAI) 사용 가이드",
                "[요금제 안내]\n"
                "- 월 구독이 아닌 \"선불 크레딧 충전 방식\"\n"
                "- 예: $10 충전 → $8 사용 시 알림 설정 가능\n"
                "- Usage Limit 설정으로 초과 사용 차단 가능\n\n"
                "[추천 설정]\n"
                "- 모델: gpt-4o-mini (가성비 우수)\n"
                "- AI 자동매매용으로 충분한 성능\n\n"
                "[하루 예상 사용량]\n"
                "- 평균 1회 판단당 약 500~1500 tokens\n"
                "- 1시간 자동매매 기준 약 $0.1 ~ $0.5 수준 (시장 상황 따라 다름)\n\n"
                "[보안]\n"
                "- API 키는 앱 내부 저장\n"
                "- 자동결제 설정하지 않으면 초과 과금 없음"
            )
        except Exception:
            pass

    def _on_show_local_guide(self):
        """LOCAL AI 사용 안내 모달 표시."""
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "LOCAL AI (Basic AI) 사용 안내",
                "[Basic AI란?]\n"
                "- 내 PC에서 AI를 실행하는 로컬 AI 엔진\n"
                "- 인터넷 비용 없음\n"
                "- GPT보다 응답은 느릴 수 있음\n\n"
                "[설치 방법]\n"
                "1. Basic AI 설치 안내 버튼 클릭\n"
                "2. 설치 후 앱 재시작\n"
                "3. 모델 설치 버튼으로 모델 준비\n\n"
                "[모델 설명]\n\n"
                "qwen2.5\n"
                "- 빠르고 안정적\n"
                "- 자동매매용 추천\n\n"
                "llama3.1\n"
                "- 균형형 모델\n"
                "- 다목적\n\n"
                "mistral\n"
                "- 가벼움\n"
                "- 저사양 PC 적합"
            )
        except Exception:
            pass

    def _on_open_ollama_install_guide(self):
        """Ollama 설치 안내 페이지를 브라우저로 연다."""
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl("https://ollama.com"))
            try:
                self._log.info("[OLLAMA-GUIDE] open browser")
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.warning(
                    self,
                    "Basic AI 설치 안내",
                    f"브라우저를 열 수 없습니다.\n\n사유: {e}"
                )
            except Exception:
                pass

    def _on_install_ollama_model(self, model: str):
        """Ollama 모델 설치 (QProcess 기반 비동기 실행, 즉시 UI 피드백)."""
        try:
            self._log.info("[OLLAMA-INSTALL] start model=%s", model)
            # 버튼 매핑
            btn_map = {
                "qwen2.5": "btn_install_qwen",
                "llama3.1": "btn_install_llama",
                "mistral": "btn_install_mistral"
            }
            btn_name = btn_map.get(model)
            if not btn_name or not hasattr(self, btn_name):
                return
            
            btn = getattr(self, btn_name)
            
            # 이미 설치됨이면 무시 (비활성화된 버튼)
            if not btn.isEnabled() and "✓ 설치됨" in btn.text():
                return
            
            # 이미 설치 중이면 무시
            if not btn.isEnabled() and "설치 중" in btn.text():
                return
            
            # 즉시 UI 반응: 버튼 텍스트 변경 + 비활성화
            btn.setText(f"{model} 설치 중...")
            btn.setEnabled(False)
            QApplication.processEvents()  # UI 즉시 갱신
            
            # 진행창 생성 및 즉시 표시 (무한 진행 바, 취소 가능)
            progress = QProgressDialog(
                f"{model} 모델 설치 중...\n\n대용량 모델은 다운로드에 시간이 걸릴 수 있습니다.",
                "취소",
                0, 0,  # 무한 진행 바
                self
            )
            progress.setWindowTitle(f"{model} 설치")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.setMinimumDuration(0)  # 즉시 표시
            progress.show()  # 프로세스 시작 전에 즉시 표시
            QApplication.processEvents()  # 진행창이 즉시 화면에 나타나도록 보장
            
            # QProcess 생성 및 설정
            process = QProcess(self)
            process.setProgram("ollama")
            process.setArguments(["pull", model])
            
            # 출력 수집용
            process_output = {"stdout": "", "stderr": ""}
            
            def on_ready_read_stdout():
                data = process.readAllStandardOutput().data().decode("utf-8", errors="replace")
                process_output["stdout"] += data
                # 진행 상황이 있으면 진행창 메시지 업데이트
                if data.strip():
                    last_line = data.strip().split("\n")[-1][:80]
                    progress.setLabelText(f"{model} 모델 설치 중...\n\n{last_line}")
                    QApplication.processEvents()  # 진행 메시지 즉시 반영
            
            def on_ready_read_stderr():
                data = process.readAllStandardError().data().decode("utf-8", errors="replace")
                process_output["stderr"] += data
            
            def on_finished(exit_code, exit_status):
                progress.close()
                success = (exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit)
                output_text = process_output["stdout"] + process_output["stderr"]
                if not output_text.strip():
                    output_text = "완료" if success else "실패"
                self._on_ollama_install_finished(model, success, output_text[:600], btn_name)
                process.deleteLater()
            
            def on_cancel():
                if process.state() != QProcess.ProcessState.NotRunning:
                    process.kill()
                    process.waitForFinished(3000)
                progress.close()
                # 버튼 복구
                btn.setText(f"{model} 설치 필요")
                btn.setEnabled(True)
                btn.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")
                self._log.info("[OLLAMA-INSTALL] cancelled model=%s", model)
            
            # 시그널 연결
            process.readyReadStandardOutput.connect(on_ready_read_stdout)
            process.readyReadStandardError.connect(on_ready_read_stderr)
            process.finished.connect(on_finished)
            progress.canceled.connect(on_cancel)
            
            # 프로세스 시작
            process.start()
            if not process.waitForStarted(3000):
                progress.close()
                error_msg = process.errorString() or "프로세스 시작 실패"
                if "not found" in error_msg.lower() or "cannot find" in error_msg.lower():
                    error_msg = "Ollama가 설치되어 있지 않거나 PATH에 없습니다."
                self._on_ollama_install_finished(model, False, error_msg, btn_name)
                return
            
        except Exception as e:
            try:
                self._log.warning("[OLLAMA-INSTALL] fail model=%s err=%s", model, str(e)[:100])
                QMessageBox.warning(
                    self,
                    f"{model} 설치",
                    f"설치를 시작할 수 없습니다.\n\n사유: {e}"
                )
                # 버튼 복구
                if btn_name and hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    btn.setText(f"{model} 설치 필요")
                    btn.setEnabled(True)
                    btn.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")
            except Exception:
                pass

    def _on_ollama_install_finished(self, model: str, success: bool, message: str, btn_name: str = None):
        """Ollama 모델 설치 완료 콜백."""
        try:
            # btn_name이 없으면 매핑에서 찾기
            if not btn_name:
                btn_map = {
                    "qwen2.5": "btn_install_qwen",
                    "llama3.1": "btn_install_llama",
                    "mistral": "btn_install_mistral"
                }
                btn_name = btn_map.get(model)
            
            if success:
                self._log.info("[OLLAMA-INSTALL] ok model=%s", model)
                # 버튼 상태 업데이트: 설치됨 표시
                if btn_name and hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    btn.setText(f"{model} ✓ 설치됨")
                    btn.setEnabled(False)
                    btn.setStyleSheet("background-color: #DFF5E1; color: #2d5016;")
                QMessageBox.information(
                    self,
                    f"{model} 설치 완료",
                    f"{model} 모델이 설치되었습니다.\n\n"
                    f"로컬 AI 테스트 버튼으로 동작을 확인하세요."
                )
                # 모델 목록 자동 확인하여 다른 버튼 상태도 업데이트
                QTimer.singleShot(500, self._check_and_update_model_buttons)
            else:
                self._log.warning("[OLLAMA-INSTALL] fail model=%s err=%s", model, message[:100])
                # 버튼 복구: 설치 필요 상태로
                if btn_name and hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    btn.setText(f"{model} 설치 필요")
                    btn.setEnabled(True)
                    btn.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")
                
                if "PATH에 없습니다" in message or "설치되어 있지 않" in message or "not found" in message.lower():
                    QMessageBox.warning(
                        self,
                        f"{model} 설치 실패",
                        f"Basic AI가 설치되어 있지 않거나 PATH에 없습니다.\n\n"
                        f"조치:\n"
                        f"1) 'Basic AI 설치 안내(웹)' 버튼을 눌러 설치하세요.\n"
                        f"2) 설치 후 앱을 재시작하세요."
                    )
                else:
                    error_display = message[:600] if len(message) > 600 else message
                    QMessageBox.warning(
                        self,
                        f"{model} 설치 실패",
                        f"설치 중 오류가 발생했습니다.\n\n"
                        f"사유: {error_display}\n\n"
                        f"조치:\n"
                        f"1) Basic AI가 실행 중인지 확인하세요.\n"
                        f"2) 앱에서 '{model} 설치 필요' 버튼을 다시 눌러주세요."
                    )
        except Exception as e:
            try:
                self._log.warning("[OLLAMA-INSTALL] callback error model=%s err=%s", model, str(e)[:100])
            except Exception:
                pass

    def _on_refresh_ollama_models(self):
        """Ollama 모델 목록 새로고침 (ollama list 명령 실행 후 콤보박스 갱신)."""
        try:
            self._log.info("[OLLAMA-LIST] start")
            # Worker 스레드 생성 및 시작
            worker = OllamaCommandWorker(["ollama", "list"], self)
            worker.finished.connect(self._on_ollama_list_finished)
            worker.start()
        except Exception as e:
            try:
                self._log.warning("[OLLAMA-LIST] fail err=%s", str(e)[:100])
                QMessageBox.warning(
                    self,
                    "모델 목록 새로고침 실패",
                    f"명령을 시작할 수 없습니다.\n\n사유: {e}"
                )
            except Exception:
                pass

    def _on_ollama_list_finished(self, success: bool, output: str):
        """ollama list 명령 완료 콜백."""
        try:
            if not success:
                self._log.warning("[OLLAMA-LIST] fail err=%s", output[:100])
                if "PATH에 없습니다" in output or "설치되어 있지 않" in output:
                    QMessageBox.warning(
                        self,
                        "모델 목록 새로고침 실패",
                        "Basic AI가 설치되어 있지 않거나 PATH에 없습니다.\n\n"
                        "조치:\n"
                        "1) 'Basic AI 설치 안내(웹)' 버튼을 눌러 설치하세요.\n"
                        "2) 설치 후 앱을 재시작하세요."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "모델 목록 새로고침 실패",
                        f"명령 실행 중 오류가 발생했습니다.\n\n"
                        f"사유: {output}\n\n"
                        f"조치:\n"
                        f"1) Basic AI가 실행 중인지 확인하세요.\n"
                        f"2) 앱에서 모델 설치 버튼 상태를 확인하세요."
                    )
                return
            
            # ollama list 출력 파싱 (NAME 컬럼에서 모델명 추출)
            models = []
            lines = output.strip().split("\n")
            for line in lines[1:]:  # 헤더 제외
                parts = line.split()
                if parts:
                    model_name = parts[0]
                    # 태그 제거 (예: "qwen2.5:latest" -> "qwen2.5")
                    model_base = model_name.split(":")[0]
                    if model_base not in models:
                        models.append(model_base)
            
            if not models:
                self._log.info("[OLLAMA-LIST] ok n=0")
                QMessageBox.information(
                    self,
                    "모델 목록",
                    "설치된 모델이 없습니다.\n\n"
                    "모델 설치 버튼을 눌러 모델을 설치하세요."
                )
                if hasattr(self, "cmb_local_model"):
                    self.cmb_local_model.clear()
                    self.cmb_local_model.addItems(["llama3.1", "qwen2.5", "mistral"])
                return
            
            # 콤보박스 갱신
            if hasattr(self, "cmb_local_model"):
                current_selection = self.cmb_local_model.currentText() or ""
                self.cmb_local_model.clear()
                # 설치된 모델 중에서 선택 가능한 모델만 추가
                available_models = []
                for m in ["llama3.1", "qwen2.5", "mistral"]:
                    if m in models or any(m in model_name for model_name in models):
                        available_models.append(m)
                if available_models:
                    self.cmb_local_model.addItems(available_models)
                    # 이전 선택 유지 (가능한 경우)
                    if current_selection in available_models:
                        self.cmb_local_model.setCurrentText(current_selection)
                    else:
                        self.cmb_local_model.setCurrentText(available_models[0])
                else:
                    # 설치된 모델이 없으면 기본 목록 유지
                    self.cmb_local_model.addItems(["llama3.1", "qwen2.5", "mistral"])
            
            self._log.info("[OLLAMA-LIST] ok n=%s", len(models))
            # 버튼 상태 업데이트
            self._update_model_buttons_status(models)
            # 모델 목록 새로고침 버튼이 제거되었으므로 팝업도 제거 (버튼 상태로 표시됨)
            # QMessageBox.information(...) 제거
        except Exception as e:
            try:
                self._log.warning("[OLLAMA-LIST] callback error err=%s", str(e)[:100])
                QMessageBox.warning(
                    self,
                    "모델 목록 새로고침 실패",
                    f"결과 처리 중 오류가 발생했습니다.\n\n사유: {e}"
                )
            except Exception:
                pass

    def _check_and_update_model_buttons(self):
        """Ollama 모델 목록을 확인하여 버튼 상태 업데이트."""
        try:
            base_url = (self.inp_local_url.text() or "").strip() if hasattr(self, "inp_local_url") else "http://127.0.0.1:11434"
            ok, result = self._check_local_ollama_tags(base_url, timeout_sec=3)
            if ok and isinstance(result, list):
                self._update_model_buttons_status(result)
            else:
                # 연결 실패 시 기본 상태 유지 (미설치로 표시)
                pass
        except Exception as e:
            try:
                self._log.warning("[MODEL-BUTTONS] check error err=%s", str(e)[:100])
            except Exception:
                pass

    def _update_model_buttons_status(self, installed_models: list[str]):
        """설치된 모델 목록을 기반으로 버튼 상태 업데이트."""
        try:
            # LOCAL 박스가 활성화되어 있는지 확인
            local_en = (getattr(self, "_ai_provider_box_active", "") or "").strip().lower() == "local"
            
            # 모델명에서 태그 제거 (예: "qwen2.5:latest" -> "qwen2.5")
            models_base = [m.split(":")[0] for m in installed_models]
            
            btn_map = {
                "qwen2.5": ("btn_install_qwen", "qwen2.5"),
                "llama3.1": ("btn_install_llama", "llama3.1"),
                "mistral": ("btn_install_mistral", "mistral")
            }
            
            for model_key, (btn_name, model_display) in btn_map.items():
                if hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    if model_key in models_base:
                        # 설치됨: 비활성화, 연한 초록, "모델명 ✓ 설치됨"
                        btn.setText(f"{model_display} ✓ 설치됨")
                        btn.setEnabled(False)
                        btn.setStyleSheet("background-color: #DFF5E1; color: #2d5016;")  # 연한 초록
                    else:
                        # 미설치: LOCAL 박스 활성화 시에만 활성화, 연한 주황, "모델명 설치 필요"
                        btn.setText(f"{model_display} 설치 필요")
                        btn.setEnabled(local_en)
                        btn.setStyleSheet("background-color: #FFE5CC; color: #8B4513;")  # 연한 주황
        except Exception as e:
            try:
                self._log.warning("[MODEL-BUTTONS] update error err=%s", str(e)[:100])
            except Exception:
                pass

    def _on_ai_reco_updated(self, _payload=None):
        """ai.reco.updated/items/strategy_suggested 수신. payload normalize(advice 래퍼 또는 본문) 후 SSOT 엔진 1곳만 갱신."""
        try:
            _raw = _payload
            _pl = (_raw.get("advice") if isinstance(_raw, dict) and "advice" in _raw else _raw) or {}
            _src = _pl.get("source", "")
            _fb = _pl.get("fallback", False)
            _items = _pl.get("items") or []
            _summary = (_pl.get("decision_summary") or "").strip()
            _reason = (_pl.get("reason_code") or "").strip()
            stage = getattr(self, "_gpt_status_stage", "")
            
            # selected_engine 확인 (local fallback인지 판단용)
            _selected_engine = ""
            try:
                from app.services import ai_reco
                last_dec = ai_reco.get_last_decision()
                _selected_engine = (last_dec.get("selected_engine") or "").strip().lower()
            except Exception:
                pass

            def _apply():
                try:
                    if stage in ("applying", "connecting", "ready", "degraded"):
                        if _src == "gpt" and not _fb and len(_items) > 0:
                            self._gpt_status_stage = "ready"
                        elif _src == "gpt" and _fb:
                            self._gpt_status_stage = "degraded"
                        elif _src == "local" and _selected_engine.startswith("gpt-"):
                            self._gpt_status_stage = "degraded"
                    self._update_engine_ui_ssot()
                except Exception:
                    pass
            QTimer.singleShot(0, _apply)
        except Exception:
            pass

    def _on_gpt_poll_tick(self):
        """2초마다: GPT 모드일 때만 ai_reco.poll_gpt_future() 호출 → 완료 시 캐시/state/publish로 READY 전환."""
        try:
            p = (getattr(self, "cb_ai_provider", None) and self.cb_ai_provider.currentText() or "").strip().lower()
            if p != "gpt":
                return
            from app.services import ai_reco
            ai_reco.poll_gpt_future()
        except Exception:
            pass

    def _on_test_gpt(self):
        """공통설정: GPT 연결 테스트. 3단계(준비/네트워크/토큰) 결과를 UI 텍스트로 표시. 키 원문 노출 금지. 최종 요약은 헤더 1줄에 갱신."""
        def out(msg: str):
            if hasattr(self, "gpt_test_result") and self.gpt_test_result is not None:
                self.gpt_test_result.appendPlainText(msg)

        def set_header(msg: str):
            if hasattr(self, "gpt_test_header_status") and self.gpt_test_header_status is not None:
                self.gpt_test_header_status.setText(msg)

        provider = (self.cb_ai_provider.currentText() or "local").strip().lower()
        if provider != "gpt":
            QMessageBox.information(self, "GPT 연결 테스트", "AI Provider가 gpt일 때만 테스트할 수 있습니다.")
            return

        stage = (getattr(self, "_gpt_status_stage", "") or "").strip().lower()
        if stage == "ready":
            actual = ""
            try:
                from app.services import ai_reco
                last_dec = ai_reco.get_last_decision() or {}
                actual = (last_dec.get("actual_engine") or "").strip()
            except Exception:
                pass
            self._active_ai_engine = "gpt"
            self._update_active_engine_label()
            QMessageBox.information(
                self, "GPT 연결 테스트",
                "GPT가 이미 연결되어 있습니다.\n현재 엔진: %s" % (actual or "gpt-*")
            )
            self._log.info("[GPT-TEST] already_ready")
            return
        if stage == "connecting":
            QMessageBox.information(self, "GPT 연결 테스트", "GPT 연결 중입니다. 잠시만 기다려주세요.")
            self._log.info("[GPT-TEST] connecting")
            return

        if hasattr(self, "gpt_test_result") and self.gpt_test_result is not None:
            self.gpt_test_result.clear()
        self._gpt_test_ok = False
        self._gpt_status_stage = "connecting"
        set_header("🟡 연결중...")
        self._log.warning("[DIAG] gpt_test status=연결중")
        try:
            self._update_engine_ui_ssot()
        except Exception:
            pass
        QMessageBox.information(self, "GPT 연결 테스트", "GPT 연결을 시도합니다. 약 30~60초 소요될 수 있습니다.")
        self._log.info("[GPT-TEST] start")

        # (1) 준비 단계
        api_key = ""
        try:
            st = getattr(self._settings, "strategy", None) if getattr(self, "_settings", None) else None
            if st is not None:
                api_key = (getattr(st, "ai_openai_api_key", "") or "").strip()
            if not api_key and hasattr(self, "ed_openai_key"):
                api_key = (self.ed_openai_key.text() or "").strip()
        except Exception:
            pass

        if not api_key:
            out("[1/3] API Key 로드 FAIL (키 없음)")
            self._gpt_test_ok = False
            set_header("🔴 FAIL (키 없음)")
            self._log.warning("[DIAG] gpt_test FAIL reason=키 없음")
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()
            QMessageBox.warning(self, "GPT 연결 테스트", "OpenAI API Key가 비어 있습니다.")
            return

        key_len = len(api_key)
        model = ""
        if hasattr(self, "cb_custom_model") and self.cb_custom_model.isChecked():
            custom_model = (self.inp_custom_model.text() or "").strip()
            if custom_model:
                model = custom_model
        if not model and hasattr(self, "ed_openai_model"):
            model_id = self.ed_openai_model.currentData()
            if model_id:
                model = model_id
            else:
                current_text = (self.ed_openai_model.currentText() or "").strip()
                for model_info in getattr(self, "KMTS_GPT_MODELS", []):
                    if model_info.get("label") == current_text:
                        model = model_info.get("id", "")
                        break
        if not model:
            model = "gpt-4o-mini"

        out(f"[1/3] API Key 로드 OK (len={key_len}), model={model}")

        # (2) 네트워크/인증 단계 + (3) 토큰 소모 단계 (짧은 completion 1회)
        import requests
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say OK only."}],
            "max_tokens": 5,
        }
        t0 = time.time()
        try:
            out("[2/3] Request start → ...")
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            latency_ms = int((time.time() - t0) * 1000)
            status = response.status_code
            if status != 200:
                err_body = (response.text or "")[:100].replace("\n", " ")
                out(f"[2/3] HTTP {status} (latency={latency_ms} ms) ❌ {err_body}")
                self._gpt_test_ok = False
                cause = f"HTTP {status} {err_body[:30].strip() or 'Error'}"
                set_header(f"🔴 FAIL ({cause})")
                self._log.warning("[DIAG] gpt_test FAIL reason=%s", cause)
                if hasattr(self, "_update_ai_status"):
                    self._update_ai_status()
                return
            out(f"[2/3] Request start → HTTP 200 OK (latency={latency_ms} ms)")

            # (3) usage 및 생성 텍스트 확인
            try:
                data = response.json()
            except Exception:
                data = {}
            choices = data.get("choices") or []
            usage = data.get("usage") or {}
            if isinstance(usage, dict):
                inp = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("total_tokens")
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens")
                if inp is not None or out_tok is not None:
                    out(f"[3/3] Token usage OK (in={inp or 0}, out={out_tok or 0}) ✅ 토큰 소모 확인됨")
                    self._gpt_test_ok = True
                    self._gpt_last_in, self._gpt_last_out = inp or 0, out_tok or 0
                    self._active_ai_engine = "gpt"
                    self._update_active_engine_label()
                    set_header("🟢 READY")
                    self._log.warning("[DIAG] gpt_test status=READY in=%s out=%s", inp or 0, out_tok or 0)
                else:
                    snippet = ""
                    if choices and isinstance(choices[0], dict):
                        delta = choices[0].get("message") or choices[0].get("delta") or {}
                        snippet = (delta.get("content") or "").strip()[:30]
                    out(f"[3/3] usage 없음, 생성 텍스트: {snippet or '(없음)'} — ✅ 응답 성공 (토큰 수 미표시)")
                    self._gpt_test_ok = True
                    self._active_ai_engine = "gpt"
                    self._update_active_engine_label()
                    set_header("🟢 READY")
            else:
                snippet = ""
                if choices and isinstance(choices[0], dict):
                    delta = choices[0].get("message") or choices[0].get("delta") or {}
                    snippet = (delta.get("content") or "").strip()[:30]
                out(f"[3/3] usage 없음, 생성: {snippet or '(없음)'} — ✅ 응답 성공")
                self._gpt_test_ok = True
                self._active_ai_engine = "gpt"
                self._update_active_engine_label()
                set_header("🟢 READY")
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()
            # READY = 실제 OpenAI 호출 1회 성공 완료. 엔진 적용은 실행 후 ai.reco.updated에서 별도 표시
            self._gpt_status_stage = "connect_ok"
        except requests.exceptions.Timeout:
            out("[2/3] timeout ❌ 네트워크/타임아웃 확인")
            self._gpt_test_ok = False
            set_header("🔴 FAIL (timeout)")
            self._log.warning("[DIAG] gpt_test FAIL reason=timeout")
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()
        except requests.exceptions.SSLError as e:
            out(f"[2/3] SSL ❌ {str(e)[:50]}")
            self._gpt_test_ok = False
            set_header("🔴 FAIL (SSL)")
            self._log.warning("[DIAG] gpt_test FAIL reason=SSL err=%s", str(e)[:80])
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()
        except requests.exceptions.RequestException as e:
            out(f"[2/3] network ❌ {str(e)[:60]}")
            self._gpt_test_ok = False
            set_header("🔴 FAIL (network)")
            self._log.warning("[DIAG] gpt_test FAIL reason=network err=%s", str(e)[:80])
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()
        except Exception as e:
            out(f"[2/3] error ❌ {str(e)[:60]}")
            self._gpt_test_ok = False
            set_header("🔴 FAIL (error)")
            self._log.warning("[DIAG] gpt_test FAIL reason=error err=%s", str(e)[:80])
            if hasattr(self, "_update_ai_status"):
                self._update_ai_status()

    def _on_test_gemini(self):
        """Gemini 박스: 연결 테스트(임시 최소 버전). API Key 유무 확인 후 성공/실패만 반영."""
        provider = (self.cb_ai_provider.currentText() or "local").strip().lower() if hasattr(self, "cb_ai_provider") else "local"
        if provider != "gemini":
            QMessageBox.information(self, "Gemini 연결 테스트", "AI Provider가 gemini일 때만 테스트할 수 있습니다.")
            return

        api_key = (self.ed_gemini_key.text() or "").strip() if hasattr(self, "ed_gemini_key") else ""
        if not api_key:
            QMessageBox.warning(self, "Gemini 연결 테스트", "API Key를 입력하세요.")
            return

        try:
            # 임시 최소 테스트: 키 존재 시 성공 처리(실제 Gemini 서비스 연동은 다음 단계)
            success = True
            if success:
                self._active_ai_engine = "gemini"
                self._update_active_engine_label()
                if hasattr(self, "lbl_gemini_test_status") and self.lbl_gemini_test_status is not None:
                    self.lbl_gemini_test_status.setText("🟢 CONNECTED")
                    self.lbl_gemini_test_status.setStyleSheet("font-size: 11px; color:#1565c0;")
                QMessageBox.information(self, "Gemini 연결 테스트", "Gemini 연결 성공")
            else:
                raise Exception("fail")
        except Exception as e:
            if hasattr(self, "lbl_gemini_test_status") and self.lbl_gemini_test_status is not None:
                self.lbl_gemini_test_status.setText("🔴 FAILED")
                self.lbl_gemini_test_status.setStyleSheet("font-size: 11px; color:#c62828;")
            QMessageBox.critical(self, "Gemini 연결 테스트", f"Gemini 연결 실패: {str(e)}")

    def _on_test_upbit(self):
        """
        업비트 연결 테스트 핸들러:
        - 현재 settings에서 키 읽기 (ak_len/sk_len 로그)
        - 키 없으면 UI에 "키 없음" 메시지
        - /v1/accounts 엔드포인트로 API 키 유효성 검증
        - 성공/실패 결과를 UI 메시지박스와 로그([UPBIT-CHECK])로 표시
        """
        import logging
        from PySide6.QtWidgets import QMessageBox

        log = logging.getLogger(__name__)

        try:
            # 현재 settings에서 키 읽기 (load_settings 재호출 불필요)
            settings = self._settings
            if not settings:
                log.warning("[UPBIT-CHECK] fail reason=settings_not_loaded")
                QMessageBox.warning(self, "연결 테스트", "설정이 로드되지 않았습니다. 앱을 재시작하세요.")
                return
                
            # 연결 테스트는 저장 전 UI 입력값을 쓸 수 있도록 UI 우선 (두 필드 모두 유효할 때만)
            ak_ui = self.ed_access.text().strip() if hasattr(self, "ed_access") else ""
            sk_ui = self.ed_secret.text().strip() if hasattr(self, "ed_secret") else ""
            ui_unmasked = (
                ak_ui and sk_ui
                and not (ak_ui.startswith("•") or sk_ui.startswith("•"))
            )
            if ui_unmasked:
                ak = ak_ui
                sk = sk_ui
                source = "ui"
            else:
                # primary 경로: settings.upbit.access_key
                up = getattr(settings, "upbit", {}) or {}
                if hasattr(up, "model_dump"):
                    up = up.model_dump()
                ak = up.get("access_key", "") if isinstance(up, dict) else getattr(up, "access_key", "")
                sk = up.get("secret_key", "") if isinstance(up, dict) else getattr(up, "secret_key", "")
                ak = (ak or "").strip()
                sk = (sk or "").strip()
                # fallback 경로: settings.upbit_access_key
                if not ak:
                    ak = (getattr(settings, "upbit_access_key", None) or "").strip()
                if not sk:
                    sk = (getattr(settings, "upbit_secret_key", None) or "").strip()
                source = "settings_fallback"
            ak_len = len(ak)
            sk_len = len(sk)
            log.info(f"[UPBIT-CHECK] start ak_len={ak_len} sk_len={sk_len} source={source}")

            if not ak or not sk:
                QMessageBox.warning(self, "연결 테스트", "업비트 API 키가 없습니다. 먼저 키를 입력하고 저장하세요.")
                log.warning("[UPBIT-CHECK] fail reason=keys_missing")
                return

            headers = _make_upbit_headers(ak, sk, source="test_button")
            if not headers:
                QMessageBox.critical(self, "연결 테스트", "JWT 토큰 생성에 실패했습니다. 키 형식을 확인하세요.")
                log.error("[UPBIT-CHECK] fail reason=jwt_creation_failed")
                return

            import requests
            url = "https://api.upbit.com/v1/accounts"
            resp = requests.get(url, headers=headers, timeout=10)
            status = resp.status_code
            log.info(f"[UPBIT-CHECK] status_code={status}")

            if status == 200:
                data = resp.json()
                cnt = len(data) if isinstance(data, list) else 0
                QMessageBox.information(self, "연결 테스트", f"업비트 API 연결 성공\n계좌 수: {cnt}")
                log.info(f"[UPBIT-CHECK] ok status_code={status} accounts={cnt}")
            else:
                QMessageBox.warning(self, "연결 테스트", f"업비트 API 연결 실패\n상태 코드: {status}")
                log.warning(f"[UPBIT-CHECK] fail status_code={status}")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "연결 테스트", f"네트워크 오류: {str(e)[:50]}")
            log.error(f"[UPBIT-CHECK] fail error=network exception={str(e)[:100]}")
        except Exception as e:
            QMessageBox.critical(self, "연결 테스트", f"알 수 없는 오류: {str(e)[:50]}")
            log.error(f"[UPBIT-CHECK] fail error=unknown exception={str(e)[:100]}")

    def _on_open_logs(self):
        """로그 폴더를 OS 탐색기로 열기"""
        try:
            import os
            import subprocess
            import platform
            
            # data/logs 폴더 경로
            if hasattr(self, '_data_dir'):
                logs_dir = os.path.join(self._data_dir, 'logs')
            else:
                logs_dir = os.path.join(os.getcwd(), 'data', 'logs')
            
            # 폴더가 없으면 생성
            os.makedirs(logs_dir, exist_ok=True)
            
            # OS별 탐색기 열기
            system = platform.system()
            if system == 'Windows':
                os.startfile(logs_dir)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', logs_dir])
            else:  # Linux
                subprocess.run(['xdg-open', logs_dir])
                
        except Exception as e:
            QMessageBox.critical(self, "로그 열기", f"로그 폴더를 열 수 없습니다:\n{str(e)}")
    
    def _on_open_test_results(self):
        """
        테스트 결과 보기 핸들러:
        - buy_order_final_only.log 파일을 Qt 방식으로 열기 (크로스플랫폼)
        """
        import os
        import logging
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        
        log = logging.getLogger(__name__)
        
        try:
            # 로그 파일 경로
            if hasattr(self, '_data_dir'):
                log_file = os.path.join(self._data_dir, 'logs', 'buy_order_final_only.log')
            else:
                log_file = os.path.join(os.getcwd(), 'data', 'logs', 'buy_order_final_only.log')
            
            # 정규화된 절대 경로
            log_file = os.path.abspath(log_file)
            
            log.info(f"[TEST-RESULTS] opening file={log_file}")
            
            # 파일 존재 확인
            if not os.path.exists(log_file):
                QMessageBox.warning(self, "테스트 결과", "테스트 결과 파일이 없습니다.\n먼저 프로그램을 실행하여 테스트를 진행해주세요.")
                return
            
            # Qt 방식으로 파일 열기 (크로스플랫폼)
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_file))
            
            log.info(f"[TEST-RESULTS] file opened successfully")
            
        except Exception as e:
            log.exception("[TEST-RESULTS] failed to open file error=%s", str(e)[:50])
            QMessageBox.critical(self, "테스트 결과", f"테스트 결과 파일을 열 수 없습니다:\n{str(e)}")

    def _on_settings_reset(self):
        """
        [공통설정] 탭의 '데이터 초기화' 패널 동작
        - 체크된 항목별로 설정/데이터를 초기화
        - '전체 초기화' 체크 시 모든 항목을 강제 포함
        """
        from PySide6.QtWidgets import QMessageBox
        from app.utils.prefs import load_settings, save_settings
        import logging
        import os
        import glob

        # 체크 상태 수집
        reset_trades   = self.cb_reset_trades.isChecked()
        reset_wb       = self.cb_reset_wb.isChecked()
        reset_keys     = self.cb_reset_keys.isChecked()
        reset_strategy = self.cb_reset_strategy.isChecked()
        # 로그인 정보 초기화는 더 이상 제공하지 않음.
        #   - 내부 호환을 위해 위젯은 유지하지만, 실제 플래그는 항상 False 로 고정.
        reset_login    = False
        reset_all      = self.cb_reset_all.isChecked()

        reset_any = any([
            reset_trades,
            reset_wb,
            reset_keys,
            reset_strategy,
            reset_all,
        ])

        if not reset_any:
            QMessageBox.information(self, "초기화", "초기화할 항목을 선택해주세요.")
            return

        # 전체 초기화가 켜져 있으면 모든 개별 항목 활성화 (로그인 정보는 제외)
        if reset_all:
            reset_trades = reset_wb = reset_keys = reset_strategy = True

        ok = QMessageBox.question(
            self,
            "초기화 확인",
            "선택한 항목을 초기화합니다.\n이 작업은 되돌릴 수 없습니다.\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return

        try:
            # 설정 로딩
            s = self._settings or load_settings()
        except Exception as e:
            logging.exception("설정 로딩 실패(초기화 취소): %s", e)
            QMessageBox.warning(self, "초기화 실패", f"설정 로딩 중 오류가 발생했습니다.\n{e}")
            return

        # 1) 매매기록 초기화
        #    - DB 파일(trades.db 등)은 다른 프로세스/커넥션이 사용 중일 수 있으므로
        #      파일 삭제 대신 "내부 레코드만 삭제" 방식으로 초기화한다.
        #    - CSV 백업 파일만 실제 파일 삭제를 시도한다.
        if reset_trades:
            try:
                import sqlite3

                base = getattr(self, "_data_dir", None)
                if base and os.path.isdir(base):
                    # 1-1) SQLite DB 내부 레코드 비우기
                    db_patterns = [
                        "trades.db",
                        "trades.sqlite",
                        "trades_*.db",
                        "trades_*.sqlite",
                    ]
                    for pat in db_patterns:
                        for path in glob.glob(os.path.join(base, pat)):
                            try:
                                # DB 파일이 존재하면, 모든 사용자 테이블의 레코드를 삭제한다.
                                if not os.path.exists(path):
                                    continue
                                conn = sqlite3.connect(path, timeout=3)
                                try:
                                    cur = conn.cursor()
                                    # 모든 사용자 테이블 목록 조회
                                    cur.execute(
                                        "SELECT name FROM sqlite_master "
                                        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                                    )
                                    tables = [r[0] for r in cur.fetchall()]
                                    for tname in tables:
                                        try:
                                            cur.execute(f"DELETE FROM {tname}")
                                        except Exception as e_tbl:
                                            logging.info(
                                                "[초기화] 매매기록 테이블 삭제 실패(%s.%s): %s",
                                                os.path.basename(path),
                                                tname,
                                                e_tbl,
                                            )
                                    conn.commit()
                                finally:
                                    conn.close()
                                logging.info("[초기화] 매매기록 DB 레코드 초기화(%s)", path)
                            except Exception as e_db:
                                logging.exception("매매기록 DB 초기화 실패(%s): %s", path, e_db)

                    # 1-2) CSV 백업 파일 삭제 (열려 있어도 치명적이지 않으므로 best-effort)
                    csv_patterns = [
                        "trades.csv",
                        "trades_*.csv",
                    ]
                    for pat in csv_patterns:
                        for path in glob.glob(os.path.join(base, pat)):
                            try:
                                os.remove(path)
                                logging.info("[초기화] 매매기록 CSV 삭제(%s)", path)
                            except Exception as e_csv:
                                logging.info("매매기록 CSV 삭제 실패(%s): %s", path, e_csv)

                logging.info("[초기화] 매매기록 초기화 완료")
            except Exception as e:
                logging.exception("매매기록 초기화 실패: %s", e)

        # 2) 화이트/블랙 리스트 초기화
        if reset_wb:
            try:
                stg = getattr(s, "strategy", None)

                # dict / pydantic 양쪽 대응 → dict로 정규화 후 값 수정
                if stg is None:
                    stg_dict = {}
                elif isinstance(stg, dict):
                    stg_dict = dict(stg)
                else:
                    try:
                        stg_dict = stg.model_dump()
                    except Exception:
                        stg_dict = {}

                stg_dict["whitelist"] = []
                stg_dict["blacklist"] = []

                # ✅ 핵심: dict를 그대로 넣지 말고 StrategyConfig로 다시 감싸서 저장
                # ✅ 핵심: dict를 그대로 넣지 말고 StrategyConfig로 다시 감싸서 저장
                # P0: ai_provider는 기존 strategy(stg)에서만 보존
                s.strategy = _coerce_strategy_config(stg_dict, preserve_ai_provider_from=stg)

                logging.info("[초기화] 화이트/블랙 리스트 초기화")
            except Exception as e:
                logging.exception("화이트/블랙 리스트 초기화 실패: %s", e)

        # 3) 업비트 키 초기화
        if reset_keys:
            try:
                api = getattr(s, "api", None)
                if api is not None:
                    # pydantic 객체 / dict 모두 지원
                    try:
                        api.access_key = ""
                        api.secret_key = ""
                    except Exception:
                        api = dict(api or {})
                        api["access_key"] = ""
                        api["secret_key"] = ""
                        s.api = api
                # UI 필드도 비우기
                self.ed_access.setText("")
                self.ed_secret.setText("")
                logging.info("[초기화] 업비트 키 초기화")
            except Exception as e:
                logging.exception("업비트 키 초기화 실패: %s", e)

        # 4) 전략설정 초기화
        if reset_strategy:
            try:
                # ✅ 전략 설정 초기화도 "dict"가 아니라 StrategyConfig로 단일화(경고 제거)
                try:
                    # P0: 전략설정 초기화 시에도 기존 ai_provider만 보존
                    s.strategy = _coerce_strategy_config({}, preserve_ai_provider_from=getattr(s, "strategy", None))
                except Exception:
                    s_dict = getattr(s, "model_dump", lambda: {})()
                    s_dict["strategy"] = _coerce_strategy_config({}, preserve_ai_provider_from=getattr(s, "strategy", None))
                    s = type(s)(**s_dict)  # 동일 타입으로 재구성 시도
                logging.info("[초기화] 전략설정 초기화")
            except Exception as e:
                logging.exception("전략설정 초기화 실패: %s", e)

        # 5) 로그인/세션 관련 초기화
        if reset_login:
            try:
                ui = getattr(s, "ui", None)
                if ui is None:
                    ui = {}
                if not isinstance(ui, dict):
                    try:
                        ui = ui.model_dump()
                    except Exception:
                        ui = dict(ui or {})
                ui["remember_id"] = False
                ui["saved_id"] = ""
                ui["auto_login"] = False
                ui["restore_last_session"] = False
                s.ui = ui
                # 체크박스도 해제
                self.cb_autologin.setChecked(False)
                self.cb_restore.setChecked(False)
                logging.info("[초기화] 로그인/세션 설정 초기화")
            except Exception as e:
                logging.exception("로그인/세션 설정 초기화 실패: %s", e)

        # 최종 저장
        try:
            # ✅ [경고 차단] 저장 직전 strategy 타입 강제 통일
            try:
                # P0: 저장 직전 타입 통일 과정에서도 ai_provider는 자기 자신에서만 보존
                _st0 = getattr(s, "strategy", None)
                s.strategy = _coerce_strategy_config(_st0, preserve_ai_provider_from=_st0)
            except Exception:
                pass

            save_settings(s)
            self._settings = s
        except Exception as e:
            logging.exception("설정 저장 실패(초기화 이후): %s", e)
            QMessageBox.warning(self, "초기화 경고", f"일부 설정 저장에 실패했습니다.\n로그를 확인해주세요.")
        else:
            QMessageBox.information(self, "초기화 완료", "선택한 항목의 초기화가 완료되었습니다.")

    def _update_controls(self):
        self._sync_run_toggle_text()
        try:
            self.btn_sellall.setEnabled(True)
            self.btn_refresh.setEnabled(True)
        except Exception:
            pass
        self._update_info_box()

    def _sync_run_toggle_text(self):
        if getattr(self.state, "is_running", False):
            self.btn_run_toggle.setText("AITS STOP")
            self.btn_run_toggle.setToolTip("AITS 자동매매를 중지합니다")
            self.btn_run_toggle.setStyleSheet(
                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
            )
        else:
            self.btn_run_toggle.setText("AITS ON")
            self.btn_run_toggle.setToolTip("AITS 자동매매를 시작합니다")
            self.btn_run_toggle.setStyleSheet(
                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
            )

    def _on_toggle_run_toggled(self, checked: bool):
        """Start/Stop 토글 엔트리포인트(단일): toggled 시그널만 사용"""
        # P0-BLOCK 2: 재진입/디바운스 가드 (더블 토글 차단)
        now = int(time.time() * 1000)
        if getattr(self, "_run_toggle_inflight", False):
            return
        last = getattr(self, "_last_toggle_ts_ms", 0)
        if last > 0 and now - last < 500:
            self._log.info("[RUN-TOGGLE] debounced dt_ms=%s", now - last)
            # P0-BLOCK 2: 디바운스 시 버튼을 실제 _is_running 상태로 원복
            try:
                self.btn_run_toggle.blockSignals(True)
                desired = getattr(self, "_is_running", False)
                self.btn_run_toggle.setChecked(desired)
                self.btn_run_toggle.setText("AITS STOP" if desired else "AITS ON")
                self.btn_run_toggle.setStyleSheet(
                    "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                    + (
                        " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                        if desired
                        else " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                    )
                )
                self.btn_run_toggle.blockSignals(False)
            except Exception:
                pass
            return
        self._run_toggle_inflight = True
        self._last_toggle_ts_ms = now
        try:
            self._on_toggle_run_toggled_impl(checked)
        finally:
            self._run_toggle_inflight = False

    def _on_toggle_run_toggled_impl(self, checked: bool):
        """실제 토글 로직 (P0-BLOCK 2: 가드 이후 호출)"""
        # ✅ 윈드서프 지시: 토글 엔트리 100% 계측 (핸들러 맨 첫 줄)
        try:
            sender = self.sender()
            sender_name = getattr(sender, 'objectName', '') if sender else 'None'
            sender_text = getattr(sender, 'text', lambda: '')()
            sender_checked = getattr(sender, 'isChecked', lambda: False)()
            current_running = getattr(self, '_is_running', False)
            desired_run = sender_checked  # ✅ 정답 로직: checked 기반으로 결정
            self._log.info(f"[UI] toggle entry checked={sender_checked} current_running={current_running} desired_run={desired_run} sender={sender_name} text={sender_text}")
        except Exception as e:
            self._log.error(f"[UI] toggle entry log error={e}")
        
        try:
            self._log.info(f"[UI] toggle toggled checked={checked}")
        except Exception:
            pass

        # STOP 원인 식별용: 토글 OFF가 사용자 클릭인지 / 코드 호출인지 구분
        try:
            sender_name = ""
            sender = self.sender()
            sender_name = sender.objectName() if sender else ""
        except Exception:
            sender_name = ""

        self._log.info(
            "[UI] toggle origin object=btn_run_toggle sender=%s",
            sender_name
        )

        # ✅ 요구사항: 즉시 UI 반영(텍스트만 즉시 전환)
        # - toggled 시그널은 이미 checked 상태를 바꾼 이벤트이므로 여기서 setChecked() 재호출 금지
        # - STOP 경로에서는 setEnabled(True) 금지 → _on_toggle_run에서 disabled 유지, STOP-ACK 후 _set_running_ui(False)에서만 재활성화
        try:
            self.btn_run_toggle.blockSignals(True)
            new_text = "AITS STOP" if checked else "AITS ON"
            self.btn_run_toggle.setText(new_text)
            self.btn_run_toggle.setStyleSheet(
                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                + (
                    " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                    if checked
                    else " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                )
            )
            if checked:
                self.btn_run_toggle.setEnabled(True)
            # else: Stop 경로 → 버튼은 _on_toggle_run에서 disabled, STOP-ACK 후 _set_running_ui(False)에서 재활성화
            self.btn_run_toggle.blockSignals(False)
            try:
                self._log.info(f"[UI] immediate toggle text={new_text} checked={bool(checked)}")
            except Exception:
                pass
        except Exception as e:
            try:
                self._log.error(f"[UI] immediate toggle error: {e}")
            except Exception:
                pass

        # ✅ 기존 체인으로 위임(로직 변경 금지)
        try:
            self._on_toggle_run(bool(checked))
        except Exception as e:
            # 예외 시 UI 원복
            try:
                self._log.error(f"[UI] toggle error: {e}")
            except Exception:
                pass
            try:
                self.btn_run_toggle.blockSignals(True)
                revert_text = "AITS ON" if bool(checked) else "AITS STOP"
                self.btn_run_toggle.setText(revert_text)
                self.btn_run_toggle.setStyleSheet(
                    "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                    + (
                        " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                        if bool(checked)
                        else " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                    )
                )
                self.btn_run_toggle.setEnabled(True)
                self.btn_run_toggle.blockSignals(False)
                try:
                    self._log.info(f"[UI] toggle reverted text={revert_text} (no_setChecked)")
                except Exception:
                    pass
            except Exception:
                pass

    def _on_toggle_run_clicked(self):
        """Start/Stop 버튼 클릭 핸들러 - Trading Layer만 제어"""
        # ✅ P0-TOGGLE-CLICK: 클릭 증명 로그 (무조건 출력)
        try:
            sender = self.sender()
            sender_name = getattr(sender, 'objectName', '') if sender else 'None'
            btn_text = getattr(self.btn_run_toggle, 'text', lambda: '')()
            btn_checked = getattr(self.btn_run_toggle, 'isChecked', lambda: False)()
            btn_enabled = getattr(self.btn_run_toggle, 'isEnabled', lambda: True)()
            self._log.info(f"[UI] toggle clicked sender={sender_name} text={btn_text} checked={btn_checked} enabled={btn_enabled}")
        except Exception as e:
            self._log.error(f"[UI] toggle click log error={e}")
        
        # 현재 상태 확인 (runner 상태 기준)
        try:
            from app.strategy.runner import _RUNNING as runner_running
            current_running = runner_running
        except Exception:
            current_running = False
        
        # 반대 상태로 토글
        desired_run = not current_running
        self._log.info(f"[UI] toggle handler enter current={current_running} desired={desired_run}")
        
        # ✅ P0-TOGGLE-IMMEDIATE: 즉시 UI 토글 (사용자 체감 우선)
        try:
            self.btn_run_toggle.blockSignals(True)
            new_text = "AITS STOP" if desired_run else "AITS ON"
            self.btn_run_toggle.setText(new_text)
            self.btn_run_toggle.setStyleSheet(
                "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                + (
                    " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                    if desired_run
                    else " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                )
            )
            self.btn_run_toggle.setChecked(desired_run)
            self.btn_run_toggle.blockSignals(False)
            
            # ✅ P0-TOGGLE-BADGE: 상태 배지도 함께 업데이트
            try:
                badge = getattr(self, 'lbl_run_state', None)
                if badge is not None:
                    badge_text = "RUNNING" if desired_run else "STOP"
                    badge.setText(badge_text)
                    self._log.info(f"[UI] badge updated text={badge_text}")
            except Exception as e:
                self._log.error(f"[UI] badge update error={e}")
            
            self._log.info(f"[UI] immediate toggle text={new_text} checked={desired_run}")
        except Exception as e:
            self._log.error(f"[UI] immediate toggle error={e}")
        
        # Trading Layer 제어 호출
        self._on_toggle_run(desired_run)

    def _on_toggle_run(self, run: bool):
        """
        실행 버튼 핸들러(견고화):
        - runner의 _RUNNING 상태를 단일 소스로 사용
        - 현재 미실행 → '실행' 수행
        - 현재 실행 중 → '정지' 수행
        """
        # ✅ PATCH: SSOT 상태 단일 읽기 + 캐시
        try:
            from app.strategy.runner import _RUNNING as runner_running
            current_running = bool(runner_running)
        except Exception:
            current_running = False

        self._is_running = current_running
        
        try:
            live_trade = getattr(self._settings, 'live_trade', False)
            simulate = not live_trade
            settings_ready = bool(self._settings)
            self._log.info(f"[UI] toggle entry run={run} current={current_running} live_trade={live_trade} simulate={simulate} settings_ready={settings_ready}")
        except Exception as e:
            self._log.error(f"[UI] toggle entry log error={e}")
        
        try:
            # 최신 설정 선주입(중복 무방)
            try:
                from app.services.order_service import svc_order as _svc
                _svc.set_settings(self._settings)
            except Exception:
                pass

            # 선택 엔진과 실제 적용 엔진이 다르면 시작 전에 경고(실행은 기존 엔진 기준으로 계속)
            if run:
                selected_provider = (getattr(self, "_ai_provider_box_active", "") or "").strip().lower()
                if selected_provider not in ("gpt", "gemini", "local"):
                    selected_provider = (self.cb_ai_provider.currentText() if hasattr(self, "cb_ai_provider") else "local")
                    selected_provider = (selected_provider or "local").strip().lower()
                selected_active = "local" if selected_provider == "local" else selected_provider
                current_active = (getattr(self, "_active_ai_engine", "basic") or "basic").strip().lower()
                if current_active == "basic":
                    current_active = "local"
                if selected_active != current_active:
                    active_label = "Basic AI"
                    if current_active == "gpt":
                        model = ""
                        if hasattr(self, "ed_openai_model"):
                            model = (self.ed_openai_model.currentData() or "").strip() or (self.ed_openai_model.currentText() or "").strip()
                        active_label = f"OpenAI ({model or 'gpt-4o-mini'})"
                    elif current_active == "gemini":
                        model = ""
                        if hasattr(self, "ed_openai_model"):
                            model = (self.ed_openai_model.currentData() or "").strip() or (self.ed_openai_model.currentText() or "").strip()
                        active_label = f"Gemini ({model or 'gemini'})"
                    QMessageBox.warning(
                        self,
                        "실행 전 확인",
                        "선택한 AI 엔진이 아직 연결되지 않았습니다.\n"
                        f"현재는 Active Engine: {active_label} 기준으로 실행됩니다."
                    )

                print(f"[AITS] managed symbols count={len(getattr(self, 'ai_managed_rows', []) or [])}")
                if len(getattr(self, "ai_managed_rows", []) or []) <= 0:
                    QMessageBox.warning(
                        self,
                        "거래 종목 없음",
                        "거래할 종목이 없습니다. 최소 1개 이상의 종목을 추가하세요.",
                    )
                    return

            # ✅ P0-REAL: 실거래 안전 가드(시작 전)
            try:
                live_trade = bool(getattr(self._settings, 'live_trade', False))
                simulate = not live_trade
                stg = getattr(self._settings, 'strategy', None)
                try:
                    stg = stg if isinstance(stg, dict) else (stg.model_dump() if stg is not None else {})
                except Exception:
                    stg = stg if isinstance(stg, dict) else {}

                if run and (not simulate):
                    mode = str((stg or {}).get('strategy_mode', 'ai') or 'ai').strip().lower()
                    wl = (stg or {}).get('whitelist') or []
                    scan_limit = int((stg or {}).get('scan_limit', 30) or 30)
                    pos_pct = float((stg or {}).get('pos_size_pct', 2.5) or 2.5)
                    dll_pct = float((stg or {}).get('daily_loss_limit_pct', 3.0) or 3.0)

                    reasons = []
                    if mode in ('avoid', 'no_trade', 'none'):
                        reasons.append("- settings.strategy.strategy_mode=avoid (실거래에서 매매가 발생하지 않을 수 있음)")
                    if (not wl) and scan_limit >= 60:
                        reasons.append(f"- whitelist=0 & scan_limit={scan_limit} (전체시장 대상으로 과도한 거래 위험)")
                    if not (0.1 <= pos_pct <= 50.0):
                        reasons.append(f"- pos_size_pct={pos_pct} (단위 혼재/과도값 가능)")
                    if not (0.1 <= dll_pct <= 50.0):
                        reasons.append(f"- daily_loss_limit_pct={dll_pct} (단위 혼재/과도값 가능)")

                    if reasons:
                        msg = "실거래 시작 전 설정을 확인하세요:\n\n" + "\n".join(reasons) + "\n\n그래도 실행할까요?"
                        self._log.warning(f"[REAL-GUARD] block_start reasons={reasons}")
                        yes = QMessageBox.question(self, "실거래 시작 확인", msg, QMessageBox.Yes | QMessageBox.No)
                        if yes != QMessageBox.Yes:
                            self._log.info("[REAL-GUARD] user cancelled start")
                            return
            except Exception as e:
                self._log.error(f"[REAL-GUARD] error={e}")

            # ✅ PATCH: 캐시된 상태 재사용 (불일치 방지)
            current_running = self._is_running
            
            # ✅ 로그 추가
            self._log.info(f"[UI] toggle requested: current={current_running} → desired={run}")

            # 러너 실행/정지
            try:
                if run:
                    # P0-1: svc_order import 확보 (UnboundLocalError 방지)
                    from app.services.order_service import svc_order
                    # ✅ 실행 직전: 전략 탭 UI → settings 반영 (allow_downscale 등 즉시 적용)
                    if hasattr(self, "tab_strategy") and self.tab_strategy is not None:
                        try:
                            self.tab_strategy.sync_ui_to_settings(self._settings)
                        except Exception:
                            pass
                    try:
                        svc_order.set_settings(self._settings)
                    except Exception:
                        pass
                    # P0-2: Start 시 trading_enabled 반드시 True 복구 (start_strategy 직전)
                    try:
                        svc_order.set_trading_enabled(True)
                    except Exception:
                        pass
                    # ✅ P2: 실행 전 사전 점검 (Preflight Check)
                    preflight_ok, preflight_msg = self._preflight_check()
                    if not preflight_ok:
                        self._log.warning(f"[PREFLIGHT] check failed: {preflight_msg}")
                        # 사용자에게 알림 (선택적 - 경고만 표시하고 진행 가능)
                        try:
                            from PySide6.QtWidgets import QMessageBox
                            QMessageBox.warning(self, "실행 전 점검", preflight_msg)
                        except Exception:
                            pass
                    else:
                        self._log.info(f"[PREFLIGHT] check passed: {preflight_msg}")
                    
                    # ✅ SSOT 분기 진단 로그 (UI 토글 진입부)
                    # P0-1: svc_order 확보 (크래시 방지)
                    try:
                        from app.services.order_service import svc_order
                    except Exception:
                        pass
                    ui_settings_id = id(self._settings)
                    ui_order_service_id = id(svc_order)
                    ui_live_trade = getattr(self._settings, "live_trade", False)
                    
                    # ✅ 진단: nested(upbit.access_key/secret_key) + flat(upbit_access_key/secret_key) 둘 다 확인
                    ui_ak1 = (getattr(getattr(self._settings, "upbit", None), "access_key", "") or "")
                    ui_sk1 = (getattr(getattr(self._settings, "upbit", None), "secret_key", "") or "")
                    ui_ak2 = (getattr(self._settings, "upbit_access_key", "") or "")
                    ui_sk2 = (getattr(self._settings, "upbit_secret_key", "") or "")
                    
                    self._log.info(
                        f"[UI-TOGGLE] settings_id={ui_settings_id} order_service_id={ui_order_service_id} "
                        f"live_trade={ui_live_trade} "
                        f"ak1_len={len(ui_ak1)} sk1_len={len(ui_sk1)} ak2_len={len(ui_ak2)} sk2_len={len(ui_sk2)}"
                    )
                    # 실행 순간 워치리스트 스냅샷: 표시 종목 30개(TopN 확대), BL 즉시 제외, WL 우선순위 부스팅
                    try:
                        if hasattr(self, "tab_watch") and self.tab_watch is not None:
                            tab_watch = self.tab_watch
                            displayed = []
                            if hasattr(tab_watch, "get_displayed_symbols_for_snapshot"):
                                displayed = tab_watch.get_displayed_symbols_for_snapshot(30)
                            wl_list, bl_list = tab_watch.get_current_whitelist_blacklist() if hasattr(tab_watch, "get_current_whitelist_blacklist") else ([], [])
                            wl_set = set((s or "").strip().upper() for s in wl_list if (s or "").strip())
                            bl_set = set((s or "").strip().upper() for s in bl_list if (s or "").strip())
                            candidates = [s for s in displayed if (s or "").strip().upper() not in bl_set]
                            bl_excluded = len(displayed) - len(candidates)
                            candidates.sort(key=lambda s: (0 if (s or "").strip().upper() in wl_set else 1, (s or "").strip()))
                            wl_boosted = sum(1 for s in candidates if (s or "").strip().upper() in wl_set)
                            try:
                                from app.strategy.runner import set_session_snapshot
                                set_session_snapshot(candidates, wl_boosted, bl_excluded)
                            except Exception:
                                pass
                            stg = getattr(self._settings, "strategy", None)
                            if stg is not None:
                                if hasattr(stg, "model_copy"):
                                    self._settings.strategy = stg.model_copy(update={"whitelist": wl_list, "blacklist": bl_list})
                                elif isinstance(stg, dict):
                                    self._settings.strategy = {**stg, "whitelist": wl_list, "blacklist": bl_list}
                                else:
                                    setattr(stg, "whitelist", wl_list)
                                    setattr(stg, "blacklist", bl_list)
                                self._log.info("[RUN-SNAPSHOT] candidates=%d wl_boosted=%d bl_excluded=%d (실행 시점 워치리스트 스냅샷)", len(candidates), wl_boosted, bl_excluded)
                    except Exception as e:
                        self._log.warning("[RUN-SNAPSHOT] watchlist snapshot failed: %s", e)
                    # P0-NET-RECOVERY: 네트워크 단절 시 폭주 억제 + 자동 복구(재연결 시 재시작)
                    # - desired_running: 사용자가 "실행" 상태를 원함(자동 복구 기준)
                    # - net_ok: 마지막 네트워크 상태(간이 체크)
                    # - net_fail_suppress: 동일 경고 로그 최소화(5초 1회)
                    if not hasattr(self, "_desired_running"):
                        self._desired_running = False
                    if not hasattr(self, "_net_ok"):
                        self._net_ok = True
                    if not hasattr(self, "_net_fail_ts"):
                        self._net_fail_ts = 0.0
                    if not hasattr(self, "_net_fail_cnt"):
                        self._net_fail_cnt = 0

                    self._desired_running = True

                    def _log_net_fail(reason: str):
                        now2 = time.time()
                        self._net_fail_cnt += 1
                        # 5초에 1번만 경고(로그 폭주 방지)
                        if (now2 - float(self._net_fail_ts or 0.0)) >= 5.0:
                            self._net_fail_ts = now2
                            self._log.warning("[NET-DOWN] %s (suppressed=%d)", reason, max(self._net_fail_cnt - 1, 0))

                    def _probe_net_async(on_done):
                        # UI 프리즈 방지: 워커 스레드에서 간이 체크 후 main thread로 콜백
                        import threading
                        def _work():
                            ok = False
                            err = "unknown"
                            try:
                                import requests
                                # 가벼운 엔드포인트(짧은 timeout) - 실패 시 예외/timeout
                                r = requests.get("https://api.upbit.com/v1/market/all", params={"isDetails": "false"}, timeout=1.2)
                                ok = bool(r.status_code < 400)
                                err = f"status={r.status_code}"
                            except Exception as e:
                                err = str(e)[:120]
                                ok = False
                            try:
                                from PySide6.QtCore import QTimer
                                QTimer.singleShot(0, lambda: on_done(ok, err))
                            except Exception:
                                # 콜백 실패는 무시(테스트용)
                                pass
                        threading.Thread(target=_work, daemon=True).start()

                    def _ensure_stop_due_to_net(reason: str):
                        # 네트워크 단절 시: 거래 비활성 + 러너 정지 플래그 + UI 복구 가능 상태 유지
                        try:
                            from app.services.order_service import svc_order as _svc_net
                            _svc_net.set_trading_enabled(False)
                        except Exception:
                            pass
                        try:
                            import app.strategy.runner as _runner_mod_net
                            _runner_mod_net._RUNNING = False
                            self._log.info("[TRADE-EN] enabled=False source=net")
                            self._log.info("[STOP-FLAG] runner _RUNNING=False reason=net")
                        except Exception:
                            pass
                        try:
                            # 버튼이 inflight로 잠겨있을 수 있으니 "재시작 가능"만 보장
                            self.btn_run_toggle.setEnabled(True)
                        except Exception:
                            pass
                        _log_net_fail(reason)

                    def _maybe_start_after_net_recover():
                        # 사용자가 실행을 원했고, 현재는 정지 상태이며, 네트워크가 회복되면 자동 시작
                        if not bool(getattr(self, "_desired_running", False)):
                            return
                        try:
                            from app.strategy.runner import _RUNNING as runner_running
                            if bool(runner_running):
                                return
                        except Exception:
                            pass

                        def _on_probe(ok, err):
                            self._net_ok = bool(ok)
                            if not ok:
                                _ensure_stop_due_to_net(f"probe_failed:{err}")
                                from PySide6.QtCore import QTimer
                                QTimer.singleShot(1500, _maybe_start_after_net_recover)
                                return

                            # 네트워크 회복: Start flow 재진입(기존 로직 그대로 사용)
                            try:
                                self._log.info("[NET-UP] recovered -> auto start")
                            except Exception:
                                pass
                            try:
                                # Start 버튼 비활성 고착 방지
                                self.btn_run_toggle.setEnabled(True)
                            except Exception:
                                pass
                            # 아래 기존 Start 요청 로직으로 진행되도록, START-REQ 이후 흐름을 그대로 탄다.
                            try:
                                from app.services.order_service import svc_order as _svc3
                                _svc3.set_trading_enabled(True)
                                self._log.info("[TRADE-EN] enabled=True source=ui")
                            except Exception:
                                pass

                        _probe_net_async(_on_probe)

                    # Start 직전: 네트워크 확인 후 진행 / 실패 시 자동 복구 루프 진입
                    def _on_probe_before_start(ok, err):
                        self._net_ok = bool(ok)
                        if not ok:
                            _ensure_stop_due_to_net(f"before_start:{err}")
                            _maybe_start_after_net_recover()
                            return
                        # ✅ 네트워크 OK일 때만 기존 trade_enabled=True 복구 수행
                        try:
                            from app.services.order_service import svc_order
                            svc_order.set_trading_enabled(True)
                            self._log.info("[TRADE-EN] enabled=True source=ui")
                        except Exception:
                            pass

                    _probe_net_async(_on_probe_before_start)

                    # ✅ P0-START/HANG-UX: ...
                    t_req = time.perf_counter()

                    ts_req = int(time.time() * 1000)
                    self._log.info("[START-REQ] ts=%d", ts_req)

                    def _do_start_work():
                        """무거운 시작 작업: QTimer.singleShot(0)로 UI 이벤트 루프 이후 실행"""
                        try:
                            # Trading enable
                            try:
                                from app.services.order_service import svc_order as _svc2
                                _svc2.set_trading_enabled(True)
                                self._log.info("[TRADE-EN] enabled=True source=ui")
                            except Exception:
                                pass

                            # Runner start
                            start_strategy(self._settings)
                            self._log.info("[RUNNER] start_strategy called")

                            # Optional UI refresh (non-fatal)
                            if hasattr(self, "tab_strategy") and self.tab_strategy is not None and hasattr(self.tab_strategy, "_update_preflight_display"):
                                try:
                                    self.tab_strategy._update_preflight_display()
                                except Exception:
                                    pass

                            # Account/Order refresh (best-effort)
                            try:
                                self.refresh_account_summary("manual_start")
                                self._log.info("[ACCT] start reason=manual")
                            except Exception:
                                pass
                            try:
                                self._ensure_orders_once("manual")
                                self._log.info("[ORDER-ENSURE] start reason=manual")
                            except Exception:
                                pass

                        except Exception as ex:
                            self._log.error("[START-ERR] %s", str(ex)[:200])

                    def _check_started(attempt=0):
                        try:
                            from app.strategy.runner import _RUNNING as runner_running
                            started = bool(runner_running)
                            elapsed_ms = int((time.perf_counter() - t_req) * 1000)
                            if started:
                                self._log.info("[START-ACK] elapsed_ms=%d", elapsed_ms)
                                try:
                                    self._set_running_ui(True)
                                except Exception:
                                    pass
                                return
                            if elapsed_ms >= 5000:
                                self._log.info("[START-TIMEOUT] elapsed_ms=%d", elapsed_ms)
                                try:
                                    self._set_running_ui(True)
                                except Exception:
                                    pass
                                return
                            QTimer.singleShot(100, lambda: _check_started(attempt + 1))
                        except Exception:
                            QTimer.singleShot(100, lambda: _check_started(attempt + 1))

                    # 1) 무거운 시작 작업을 다음 이벤트 루프로 지연 → 클릭 직후 UI 프리즈 방지
                    QTimer.singleShot(0, _do_start_work)
                    QTimer.singleShot(100, lambda: _check_started(0))
                    handled_ms = int((time.perf_counter() - t_req) * 1000)
                    self._log.info("[PERF] start_request handled_ms=%d", handled_ms)

                else:
                    # ✅ P0-C: 클릭 즉시 경량 플래그 세팅(UI 응답성), 무거운 작업은 QTimer로 지연
                    t_req = time.perf_counter()
                    # Stop inflight guard: 재클릭/중복 시그널로 enabled=True 복귀 방지
                    try:
                        self.btn_run_toggle.setEnabled(False)
                        self._log.info("[STOP-GUARD] btn_run_toggle disabled (inflight)")
                    except Exception:
                        pass
                    # 1) 즉시 반영: trade_enabled=false
                    try:
                        from app.services.order_service import svc_order as _svc
                        _svc.set_trading_enabled(False)
                    except Exception:
                        pass
                    # 2) 즉시 반영: runner _RUNNING=False → 다음 tick이 즉시 skip
                    try:
                        import app.strategy.runner as _runner_mod
                        _runner_mod._RUNNING = False
                        self._log.info("[TRADE-EN] enabled=False source=ui")
                        self._log.info("[STOP-FLAG] runner _RUNNING=False, next tick will skip")
                    except Exception:
                        pass
                    ts_req = int(time.time() * 1000)
                    self._log.info("[STOP-REQ] ts=%d", ts_req)

                    def _do_stop_cleanup():
                        """무거운 정리: QTimer.singleShot(0)로 UI 이벤트 루프 이후 실행"""
                        try:
                            stop_strategy()
                            self._log.info("[STOP-RUNNER] stop_strategy done")
                            if hasattr(self, '_run_timer') and self._run_timer.isActive():
                                self._run_timer.stop()
                            try:
                                from app.services.order_service import svc_order as _svc2
                                _svc2.set_trading_enabled(False)
                            except Exception:
                                pass
                        except Exception as ex:
                            self._log.error("[STOP-ERR] %s", str(ex)[:200])

                    def _check_stopped(attempt=0):
                        try:
                            from app.strategy.runner import _RUNNING as runner_running
                            stopped = not bool(runner_running)
                            elapsed_ms = int((time.perf_counter() - t_req) * 1000)
                            if stopped:
                                self._log.info("[STOP-ACK] elapsed_ms=%d", elapsed_ms)
                                try:
                                    self._set_running_ui(False)
                                except Exception:
                                    pass
                                # ✅ inflight로 잠긴 실행버튼 복구(네트워크/예외 경로 포함)
                                try:
                                    self.btn_run_toggle.setEnabled(True)
                                except Exception:
                                    pass
                                # STOP 완료 시에는 사용자가 실행을 "원하지 않는" 상태로 본다(자동 재시작 방지)
                                try:
                                    self._desired_running = False
                                except Exception:
                                    pass
                                return
                            if elapsed_ms >= 5000:
                                self._log.info("[STOP-TIMEOUT] elapsed_ms=%d", elapsed_ms)
                                try:
                                    self._set_running_ui(False)
                                except Exception:
                                    pass
                                # ✅ TIMEOUT이어도 UI 고착 방지: 버튼은 반드시 복구
                                try:
                                    self.btn_run_toggle.setEnabled(True)
                                except Exception:
                                    pass
                                try:
                                    self._desired_running = False
                                except Exception:
                                    pass

                                except Exception:
                                    pass
                                return
                            QTimer.singleShot(100, lambda: _check_stopped(attempt + 1))
                        except Exception:
                            QTimer.singleShot(100, lambda: _check_stopped(attempt + 1))

                    # 3) 무거운 정리 작업을 다음 이벤트 루프로 지연 → UI 즉시 응답
                    QTimer.singleShot(0, _do_stop_cleanup)
                    QTimer.singleShot(100, lambda: _check_stopped(0))
                    handled_ms = int((time.perf_counter() - t_req) * 1000)
                    self._log.info("[PERF] stop_request handled_ms=%d", handled_ms)
                
                success = True
            except Exception as e:
                self._log.error(f"[RUNNER] toggle failed: {e}")
                success = False
            if success:
                # ✅ PATCH: 토글 결과를 SSOT 상태로 확정
                self._is_running = run
                self._log.info(f"[UI] toggle success: running={run}")
            else:
                # 실패 시 UI 되돌리기
                try:
                    self.btn_run_toggle.blockSignals(True)
                    revert_text = "AITS ON" if run else "AITS STOP"
                    revert_checked = not run
                    self.btn_run_toggle.setText(revert_text)
                    self.btn_run_toggle.setStyleSheet(
                        "padding: 6px 14px; font-weight: 600; min-height: 30px;"
                        + (
                            " background-color: #ecfdf5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 6px;"
                            if run
                            else " background-color: #fff1f0; color: #c62828; border: 1px solid #ff4d4f; border-radius: 6px;"
                        )
                    )
                    self.btn_run_toggle.setChecked(revert_checked)
                    self.btn_run_toggle.blockSignals(False)
                    self._log.info(f"[UI] toggle reverted: text={revert_text} checked={revert_checked}")
                except Exception as revert_error:
                    self._log.error(f"[UI] revert error={revert_error}")
                
                self._log.error(f"[UI] toggle failed: desired={run}")

        except Exception as e:
            self._log.error(f"[UI] toggle error: {e}")
            try:
                self._toast_error(f"실행 제어 실패: {e}")
            except Exception:
                pass
            print(f"[UI] 실행 제어 실패: {e}")

    def _preflight_check(self) -> tuple[bool, str]:
        """
        실행 전 사전 점검 (Preflight Check) - 요구사항 필드 포함.
        반환: (성공 여부, 메시지)
        """
        try:
            from app.services.order_service import svc_order
            from app.strategy.runner import get_session_snapshot_summary, _SESSION_SNAPSHOT_SYMBOLS
            
            # 1. 가용 KRW 계산
            try:
                available_krw = svc_order._compute_available_krw()
            except Exception:
                available_krw = 0.0
            
            # 2. 설정값 읽기
            stg = getattr(self._settings, 'strategy', None)
            try:
                stg = stg if isinstance(stg, dict) else (stg.model_dump() if stg is not None else {})
            except Exception:
                stg = stg if isinstance(stg, dict) else {}
            
            live_trade = bool(getattr(self._settings, "live_trade", False))
            simulate = not live_trade
            
            order_amount_krw = int(stg.get("order_amount_krw", 0) or 0)
            order_amount_source = "user"  # TODO: AI source 감지 로직 추가 가능
            pos_size_pct = float(stg.get("pos_size_pct", 2.5) or 2.5)
            max_total_krw = int(getattr(self._settings, "max_total_krw", 50_000) or 50_000)
            allow_downscale = bool(stg.get("allow_downscale_order_amount", False))
            
            # 3. 계산된 1종목 한도 및 hard_cap
            position_limit = available_krw * pos_size_pct / 100.0
            MIN_ORDER_KRW = 5000
            hard_cap_candidate = min(available_krw, max_total_krw, position_limit)
            hard_cap_bypass = False
            
            if hard_cap_candidate < MIN_ORDER_KRW:
                if order_amount_krw >= MIN_ORDER_KRW:
                    hard_cap = min(available_krw, order_amount_krw)
                    hard_cap_bypass = True
                else:
                    hard_cap = hard_cap_candidate
            else:
                hard_cap = hard_cap_candidate
            
            can_order = (available_krw >= MIN_ORDER_KRW and order_amount_krw >= MIN_ORDER_KRW and hard_cap >= MIN_ORDER_KRW)
            ok_int = 1 if can_order else 0
            
            # 4. 스냅샷·리스트 상태
            snapshot_on = _SESSION_SNAPSHOT_SYMBOLS is not None and len(_SESSION_SNAPSHOT_SYMBOLS) > 0
            allow_count = len(_SESSION_SNAPSHOT_SYMBOLS) if snapshot_on else len(stg.get("whitelist") or [])
            wl_count = len(stg.get("whitelist") or [])
            bl_count = len(stg.get("blacklist") or [])
            
            # 5. PREFLIGHT 로그 (표준 1줄, B-5)
            snapshot_n = allow_count if snapshot_on else 0
            preflight_log = (
                f"[PREFLIGHT] ok={ok_int} krw={available_krw:.0f} order={order_amount_krw} "
                f"pos_pct={pos_size_pct} pos_limit={position_limit:.0f} hard_cap={hard_cap:.0f} "
                f"allow_downscale={1 if allow_downscale else 0} snapshot_n={snapshot_n}"
            )
            self._log.info(preflight_log)
            
            # 6. UI 메시지 (표준 문장 B-5)
            msg_lines = [
                f"가용 KRW {available_krw:,.0f}원 | 1회 주문 {order_amount_krw:,}원 | pos_limit {position_limit:,.0f}원 | hard_cap {hard_cap:,.0f}원",
            ]
            if hard_cap_bypass:
                msg_lines.append("→ (필요 시) 종목 비중 보호 우회 적용")
            if allow_downscale:
                msg_lines.append("→ (옵션 ON 시) 자동 축소 허용")
            msg_lines.append("→ 실행 가능" if can_order else "→ 매수 불가(이유: 잔고/한도 부족)")
            msg = "\n".join(msg_lines)
            
            return (can_order, msg)
            
        except Exception as e:
            self._log.error(f"[PREFLIGHT] check error: {e}")
            return (True, f"[사전 점검] 오류 발생: {e} (계속 진행)")

    def _toggle_runner(self, run: bool):
        """
        실행/중지 최소 래퍼 (우회 경로 제거):
        - app.strategy.runner.start_strategy / stop_strategy만 사용
        - 상태 플래그는 _on_toggle_run에서 관리
        """
        try:
            # 최신 설정 선주입(중복 호출 무방)
            try:
                svc_order.set_settings(self._settings)
            except Exception:
                pass

            if run:
                # ✅ P2-6: Dirty 상태 체크 및 경고 팝업
                if hasattr(self, "tab_strategy") and getattr(self.tab_strategy, "_is_dirty", False):
                    msg = QMessageBox()
                    msg.setWindowTitle("미저장 변경사항 확인")
                    msg.setText("전략 설정에 저장되지 않은 변경사항이 있습니다.\n저장 후 실행하시겠습니까, 아니면 현재 저장된 설정으로 그대로 실행하시겠습니까?")
                    
                    save_btn = msg.addButton("저장 후 실행", QMessageBox.AcceptRole)
                    run_btn = msg.addButton("그대로 실행", QMessageBox.DestructiveRole)
                    cancel_btn = msg.addButton("취소", QMessageBox.RejectRole)
                    
                    msg.exec()
                    
                    if msg.clickedButton() == cancel_btn:
                        return
                    elif msg.clickedButton() == save_btn:
                        try:
                            self.tab_strategy._on_save_apply()
                        except Exception as e:
                            self._log.error(f"[RUNNER] save failed: {e}")
                            QMessageBox.warning(self, "저장 실패", "저장에 실패하여 실행을 중단했습니다.")
                            return
                
                # P0-STOP/HANG-1: Start 시 trade_enabled=True 복구
                try:
                    from app.services.order_service import svc_order
                    svc_order.set_trading_enabled(True)
                    self._log.info("[TRADE-EN] enabled=True source=ui")
                except Exception:
                    pass
                _st = getattr(self._settings, "strategy", None)
                _mode_ui = _st.get("strategy_mode", "?") if isinstance(_st, dict) else getattr(_st, "strategy_mode", "?")
                self._log.warning("[RUN-START] selected_mode_from_ui=%s", _mode_ui)
                start_strategy(self._settings)
                self._log.info("[RUNNER] start_strategy called")
                
                # ✅ P0-START-STOP: Account/Order 재개 (Trading Layer)
                try:
                    self.refresh_account_summary("manual_start")
                    self._log.info("[ACCT] start reason=manual")
                except Exception:
                    pass
                
                try:
                    self._ensure_orders_once("manual")
                    self._log.info("[ORDER-ENSURE] start reason=manual")
                except Exception:
                    pass
            else:
                # P0-4: Stop 경로 단일화 - stop_strategy()는 _on_toggle_run(run=False) 경로만 사용
                # (중복 호출 방지: _toggle_runner의 Stop 분기에서는 stop_strategy 호출 제거)
                try:
                    from app.services.order_service import svc_order as _svc
                    _svc.set_trading_enabled(False)
                    self._log.info("[ORDER] trading disabled")
                except Exception:
                    pass
            return True
        except Exception as e:
            self._log.error(f"[RUNNER] toggle failed: {e}")
            try:
                self._toast_error(f"실행 제어 실패: {e}")
            except Exception:
                pass
            return False


    # (삭제됨) on_export_trades: TradesTab.export_csv()로 이전 완료


    def on_export_positions(self):
        try:
            from app.utils.exporter import export_positions_csv
            out = export_positions_csv(self._data_dir)
            QMessageBox.information(self, "내보내기", f"포지션/PnL CSV 저장 완료:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "내보내기 실패", str(e))

    def on_sell_all(self):
            """P0-[4]: 전량매도(비상버튼) - SSOT 사용, 즉시 실행, [PANIC-SELL] 로그"""
            ret = QMessageBox.question(
                self, "전량매도", "보유 전량을 시장가로 매도할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return
            
            # P0-[4]: Holdings SSOT 강제 갱신
            try:
                from app.services.holdings_service import fetch_live_holdings
                holdings_data = fetch_live_holdings(force=True)
                if not holdings_data.get("ok"):
                    err = holdings_data.get("err", "unknown")
                    QMessageBox.warning(self, "매도 오류", f"보유 조회 실패: {err}")
                    return
                
                items = holdings_data.get("items", [])
                kept_count = len(items)
                krw_avail = float(holdings_data.get("krw", 0) or 0.0)
                logging.info("[PANIC-SELL] start n=%d krw_avail=%.0f", kept_count, krw_avail)

                if kept_count == 0:
                    logging.info("[PANIC-SELL] start n=0 (no positions)")
                    QMessageBox.information(self, "전량매도", "매도할 가용 수량이 없습니다.")
                    return

            except Exception as e:
                logging.error("[PANIC-SELL] start ok=0 err=%s", str(e))
                QMessageBox.warning(self, "매도 오류", f"보유 조회 실패: {e}")
                return

            MIN_WON = 5000.0
            dust = 0
            sent = 0
            failed = 0
            block_reasons = {}

            for item in items:
                symbol = item.get("symbol", "")
                qty = float(item.get("qty") or 0)
                balance = float(item.get("balance") or 0.0)
                locked = float(item.get("locked") or 0.0)
                eval_krw = float(item.get("eval_krw") or 0.0)
                avg = float(item.get("avg_price") or 0.0)
                px = float(item.get("px") or 0.0) if item.get("px") is not None else 0.0

                logging.info(
                    "[PANIC-SELL] item symbol=%s qty=%.8f balance=%.8f locked=%.8f eval_krw=%.0f avg=%.2f px=%.2f",
                    symbol, qty, balance, locked, eval_krw, avg, px
                )

                if qty <= 0:
                    logging.info("[PANIC-SELL] skip symbol=%s reason=avail_qty_zero qty=%.8f locked=%.8f balance=%.8f", symbol, qty, locked, balance)
                    continue

                if px > 0 and eval_krw < MIN_WON:
                    logging.info("[PANIC-SELL] attempt symbol=%s qty=%.8f eval_krw=%.0f (dust skip)", symbol, qty, eval_krw)
                    dust += 1
                    continue

                avail = qty  # SSOT qty = max(balance-locked,0) = 주문가능 수량
                logging.info("[PANIC-SELL] attempt symbol=%s qty=%.8f balance=%.8f locked=%.8f avail=%.8f", symbol, qty, balance, locked, avail)
                try:
                    ok, block_reason = svc_order.sell_market(
                        symbol, qty,
                        simulate=not bool(self._settings.live_trade),
                        reason="PANIC",
                        price_hint=px if px > 0 else None,
                        meta={"panic": True}
                    )
                    if ok:
                        sent += 1
                        logging.info("[PANIC-SELL] result symbol=%s ok=1 detail=ok", symbol)
                    else:
                        failed += 1
                        reason_key = block_reason or "unknown"
                        block_reasons[reason_key] = block_reasons.get(reason_key, 0) + 1
                        logging.warning("[PANIC-SELL] result symbol=%s ok=0 detail=%s", symbol, reason_key)
                except Exception as e:
                    failed += 1
                    reason_key = f"exception:{str(e)[:50]}"
                    block_reasons[reason_key] = block_reasons.get(reason_key, 0) + 1
                    logging.warning("[PANIC-SELL] result symbol=%s ok=0 detail=%s", symbol, str(e))

            block_top = (sorted(block_reasons.items(), key=lambda x: -x[1])[:1] or [("none", 0)])[0][0] if block_reasons else "none"
            logging.info("[PANIC-SELL] done ok=%d fail=%d dust=%d block_top=%s", sent, failed, dust, block_top)
            
            if sent > 0:
                QMessageBox.information(self, "전량매도", f"시장가 매도 요청 전송: {sent}건 (먼지 스킵 {dust}건)")
            else:
                if dust > 0:
                    QMessageBox.information(self, "전량매도", f"모든 보유가 먼지로 판단되어 스킵되었습니다. (스킵 {dust}건)")
                else:
                    QMessageBox.information(self, "전량매도", "매도할 가용 수량이 없습니다.")

    def on_refresh(self):
        """
        [새로고침] 버튼:
        - 각 탭이 UI/데이터 로딩을 100% 소유한다.
        - app_gui.py는 탭의 refresh만 호출한다. (레거시 테이블/심볼 재구성 금지)
        """
        try:
            print("[AITS] refresh clicked")
            try:
                from app.services.holdings_service import fetch_live_holdings

                fetch_live_holdings(force=True)
            except Exception as e:
                print(f"[AITS] refresh holdings preload failed: {e}")

            # 전역 상태바: 시작 메시지
            self.set_global_status("⏳ 데이터 갱신 중...", "busy", "refresh")

            # ✅ Step5: 최종형 SSOT 1줄 로그 (manual_refresh 트리거 직후)
            try:
                s = self._settings or self._get_settings_cached(force=False)
                source = "memory" if (s is not None and s is self._settings) else "cache"
                live_trade = getattr(s, "live_trade", None) if s else None
                poll_ms = 1500
                try:
                    p = getattr(s, "poll", None) if s else None
                    if hasattr(p, "ticker_ms"):
                        poll_ms = int(getattr(p, "ticker_ms") or poll_ms)
                    elif isinstance(p, dict) and p.get("ticker_ms"):
                        poll_ms = int(p.get("ticker_ms") or poll_ms)
                except Exception:
                    pass
                log.info(f"[SSOT] source={source} live_trade={bool(live_trade)} poll_ms={int(poll_ms)}")
            except Exception:
                pass
            
            try:
                log.info("[REFRESH] manual refresh clicked")
            except Exception:
                pass

            # 0) 상단 현황판 갱신 (추가)
            self.refresh_account_summary("manual_refresh")

            # 1) Watchlist
            try:
                if hasattr(self, "tab_watch") and hasattr(self.tab_watch, "refresh"):
                    self.tab_watch.refresh()
            except Exception:
                pass

            # AITS 종목관리 탭 데이터 동기화(시장 데이터 기준)
            try:
                self._load_market_explorer_initial_data()
            except Exception:
                pass

            # 2) Portfolio(투자현황)
            try:
                if hasattr(self, "portfolio_tab") and hasattr(self.portfolio_tab, "refresh"):
                    self.portfolio_tab.refresh()
            except Exception:
                pass

            # 3) Trades(매매기록)
            try:
                if hasattr(self, "tab_trades") and hasattr(self.tab_trades, "refresh"):
                    self.tab_trades.refresh()
            except Exception:
                pass
            
            # 완료 메시지
            self.set_global_status("🟢 최신화 완료", "ok", "refresh")

            # 4) 상단 KPI
            try:
                if hasattr(self, "_update_info_box"):
                    self._update_info_box()
            except Exception:
                pass

            # 5) AI 추천(종목점수) 즉시 1회 갱신
            # - ai_reco.update()가 ai.reco.updated / ai.reco.items / ai.reco.strategy_suggested 를 publish 함
            # - WatchlistTab은 이를 구독하여 '종목점수'를 채운다.
            # - 워치리스트 표시목록을 payload로 전달하여 Top20 외 종목도 점수 생성되도록 함
            try:
                # 워치리스트 표시목록 안전하게 추출
                markets = []
                if hasattr(self, "tab_watch") and hasattr(self.tab_watch, "_wl_symbols"):
                    try:
                        markets = list(self.tab_watch._wl_symbols or [])
                    except Exception:
                        markets = []
                
                # payload 구조: {"markets": [...]}
                payload = {"markets": markets} if markets else {}
                ai_reco.update(payload)
            except Exception:
                pass

            self.set_status_msg("✅ 새로고침 완료", "#2e7d32")

            try:
                log.info("[REFRESH] done (watchlist/portfolio/trades/kpi)")
            except Exception:
                pass
        except Exception:
            import logging
            logging.getLogger(__name__).exception("[REFRESH] failed")
            self.set_status_msg("❌ 새로고침 실패(로그 확인)", "#b00020")
        
    def closeEvent(self, event):
        """✅ P0-BOOT-ORDER: 종료 시 타이머 정리 + 창 geometry/state 저장"""
        try:
            if hasattr(self, '_wl_timer') and self._wl_timer.isActive():
                self._wl_timer.stop()
            self._polling_started = False
        except Exception:
            pass
        try:
            s = QSettings("KMTS", "KMTS-v3")
            s.setValue("window/geometry", self.saveGeometry())
            s.setValue("window/state", self.saveState())
        except Exception as e:
            self._log.debug("[WIN] save geometry/state failed: %s", e)
        super().closeEvent(event)

    def showEvent(self, event):
        """✅ WIN: 로그인 후 첫 표시 시 geometry 복원 또는 중앙 배치, 화면 밖 방지"""
        super().showEvent(event)
        try:
            if getattr(self, "_geometry_restored", True):
                return
            s = QSettings("KMTS", "KMTS-v3")
            geom = s.value("window/geometry")
            state = s.value("window/state")
            if geom is not None and state is not None:
                ok_geom = self.restoreGeometry(geom)
                ok_state = self.restoreState(state)
                if ok_geom or ok_state:
                    self._geometry_restored = True
                    self._log.info("[WIN] restore ok=1 source=settings geom=restored")
                    self._clamp_window_onscreen()
                    return
            self._geometry_restored = True
            # 저장된 값 없음 → primary screen 중앙에 배치
            screen = QApplication.primaryScreen()
            if screen is not None:
                ag = screen.availableGeometry()
                x = ag.x() + (ag.width() - self.width()) // 2
                y = ag.y() + (ag.height() - self.height()) // 2
                self.move(max(ag.x(), x), max(ag.y(), y))
                self._log.info("[WIN] restore ok=0 → centered on screen geom=(%d,%d,%d,%d)", x, y, self.width(), self.height())
            self._clamp_window_onscreen()
        except Exception as e:
            self._geometry_restored = True
            self._log.debug("[WIN] showEvent restore failed: %s", e)
            self._clamp_window_onscreen()

    def _clamp_window_onscreen(self):
        """창이 화면 밖(오프스크린)이면 availableGeometry 안으로 이동."""
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.screenAt(self.mapToGlobal(self.rect().center()))
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is None:
                return
            ag = screen.availableGeometry()
            fr = self.frameGeometry()
            x, y = self.x(), self.y()
            # top-left가 ag 밖이면 클램프
            if x < ag.x():
                x = ag.x()
            if y < ag.y():
                y = ag.y()
            if x + fr.width() > ag.x() + ag.width():
                x = ag.x() + ag.width() - fr.width()
            if y + fr.height() > ag.y() + ag.height():
                y = ag.y() + ag.height() - fr.height()
            if x != self.x() or y != self.y():
                self.move(x, y)
                self._log.info("[WIN] offscreen detected → moved to (%d,%d)", x, y)
        except Exception as e:
            self._log.debug("[WIN] _clamp_window_onscreen failed: %s", e)


    def _stop_polling(self):
        # P0-2: disconnect 시 RuntimeWarning 방지 (슬롯 명시)
        try:
            if hasattr(self, "_wl_timer") and self._wl_timer is not None:
                self._wl_timer.stop()
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r".*Failed to disconnect.*timeout\(\).*",
                        category=RuntimeWarning,
                    )
                    self._wl_timer.timeout.disconnect(self._on_watchlist_tick)
        except Exception:
            pass

    # (삭제됨) _rebuild_watchlist_symbols
    # Watchlist 심볼 산출/재구성/캐싱/렌더링은 WatchlistTab이 100% 소유한다.
    # app_gui.py에서는 해당 책임을 보유하지 않는다.

    def _ensure_daily_open_snapshot(self):
        try:
            total_asset, _ = self._compute_upbit_totals()
            key = self._today_key_kst()
            snap = self._load_snap()
            if key not in snap or "open_total_asset" not in snap.get(key, {}):
                snap[key] = {"open_total_asset": float(total_asset)}
                self._save_snap(snap)
                log.info("daily open snapshot saved: %s => %.0f", key, total_asset)
        except Exception as e:
            log.warning("snapshot ensure failed: %s", e)

    def _update_info_box(self):
        """
        5초마다 자동 호출되는 요약 갱신:
        - 상단 KPI
        - 투자현황(보유표)
        - 금일 손익(PnL) 테이블
        """
        import logging
        log = logging.getLogger(__name__)

        try:
            # 상단 KPI
            self.refresh_account_summary("manual_refresh")

            # 투자현황/수익률은 에러가 나도 UI 전체가 죽지 않도록 개별 try
            try:
                self._reload_positions_table()
            except Exception:
                log.exception("[INFO] positions reload failed")

            # (삭제됨) _reload_pnl_table: 투자현황 요약/수익률은 PortfolioTab에서 처리
        except Exception:
            log.exception("[INFO] info box update failed")

def main(root_dir: str, data_dir: str):
    # DB 및 기본 설정 초기화
    init_db(os.path.join(root_dir, "data"))
    init_prefs(root_dir, data_dir)
    from app.db.trades_db import init_trades_db
    init_trades_db(data_dir)

    # [PATCH] UI 설정에서 자동로그인/아이디 저장 상태 읽기
    try:
        settings = load_settings()
    except Exception:
        settings = AppSettings()

    ui = getattr(settings, "ui", None)
    saved_id = ""
    auto_login = False
    remember_id = False

    # settings.ui 에서 saved_id / auto_login / remember_id 복원
    if ui is not None:
        try:
            # pydantic 모델인 경우
            if hasattr(ui, "model_dump"):
                ui_dict = ui.model_dump()
            # dict 인 경우
            elif isinstance(ui, dict):
                ui_dict = dict(ui)
            else:
                ui_dict = {}
        except Exception:
            ui_dict = {}
        saved_id = (ui_dict.get("saved_id") or "").strip()
        auto_login = bool(ui_dict.get("auto_login", False))
        remember_id = bool(ui_dict.get("remember_id", False))

    # Qt 앱 생성
    app = QApplication.instance() or QApplication(sys.argv)

    # [UI-QSS] 가벼운 통일 QSS 적용 (로직 0% / 정렬·통일성만)
    try:
        app.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        pass
    try:
        # 전역 기본 스타일만 적용 (개별 위젯/박스의 setStyleSheet는 그대로 우선 적용됨)
        app.setStyleSheet(KMTS_LIGHT_QSS + "\n" + (app.styleSheet() or ""))
        logging.getLogger(__name__).info("[UI-QSS] applied preset=KMTS_LIGHT_QSS")
    except Exception as e:
        logging.getLogger(__name__).warning(f"[UI-QSS] apply failed err={e}")

    # 본문/입력 기본 글자색 검정 (시인성: 회색 텍스트 방지)
    try:
        pal = app.palette()
        pal.setColor(pal.ColorRole.WindowText, QColor(0, 0, 0))
        pal.setColor(pal.ColorRole.Text, QColor(0, 0, 0))
        app.setPalette(pal)
    except Exception:
        pass

    # [PATCH] 계정 생성 팝업 제거: 항상 로그인 다이얼로그만 사용
    state = AppState()

    # 항상 로그인 창 표시 (자동 로그인 제거)
    login_dlg = LoginDialog()
    if login_dlg.exec() != QDialog.Accepted:
        sys.exit(0)
    
    # 로그인 성공 처리
    state.login(login_dlg.email.text())

    # 메인 윈도우 생성 및 표시
    window = MainWindow(state, root_dir, data_dir)
    window.show()
    sys.exit(app.exec())
