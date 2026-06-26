from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


RISK_KEYWORDS = (
    "submitted=1",
    "submitted=True",
    "order_allowed=True",
    "real_order=True",
    "place_order",
    "create_order",
    "buy_market_order",
    "sell_market_order",
    "OrderAdapter",
    "ExecutionBridge",
    "RiskGuard",
)

CORE_WIDGETS = {
    "main_window": ("object", "main_window_aits"),
    "power_state": ("property", "lbl_aits_power_state"),
    "safety_state": ("property", "lbl_aits_safety_state"),
    "selected_engine": ("object", "lbl_selected_ai_engine"),
    "applied_engine": ("object", "lbl_applied_ai_engine"),
    "connection_state": ("object", "lbl_provider_connection_state"),
    "provider_combo": ("object", "cmb_ai_provider"),
    "managed_tab": ("property", "tab_aits_managed"),
    "trade_log_tab": ("property", "tab_trade_log"),
    "investment_tab": ("property", "tab_investment"),
    "ai_policy_tab": ("property", "tab_ai_policy_center"),
    "common_settings_tab": ("property", "tab_common_settings"),
    "ai_refresh_button": ("property", "btn_ai_analysis_refresh"),
    "status_refresh_button": ("property", "btn_ai_status_refresh"),
    "managed_table": ("property", "tbl_ai_managed"),
    "trade_log_table": ("object", "tbl_trade_log"),
    "trade_log_detail": ("object", "pnl_trade_log_detail"),
    "trade_log_save": ("property", "btn_trade_log_save"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(widget: Any) -> str:
    if widget is None:
        return ""
    for attr in ("text", "currentText", "toPlainText"):
        fn = getattr(widget, attr, None)
        if callable(fn):
            try:
                value = str(fn() or "").strip()
                if value:
                    return value
            except Exception:
                pass
    try:
        from PySide6.QtWidgets import QLabel

        labels = widget.findChildren(QLabel)
        parts = [str(lb.text() or "").strip() for lb in labels if str(lb.text() or "").strip()]
        return " | ".join(parts)
    except Exception:
        return ""


def _find_by_property(root: Any, value: str) -> Any:
    try:
        from PySide6.QtWidgets import QWidget

        widgets = root.findChildren(QWidget)
    except Exception:
        widgets = []
    for widget in widgets:
        try:
            if str(widget.property("smokeObjectName") or "") == value:
                return widget
        except Exception:
            pass
    return None


def _find_widget(root: Any, kind: str, value: str) -> Any:
    if kind == "object":
        try:
            if str(root.objectName() or "") == value:
                return root
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QWidget

            found = root.findChild(QWidget, value)
            if found is not None:
                return found
        except Exception:
            pass
    if kind == "property":
        found = _find_by_property(root, value)
        if found is not None:
            return found
    return None


def _table_row_count(widget: Any) -> int | None:
    fn = getattr(widget, "rowCount", None)
    if callable(fn):
        try:
            return int(fn())
        except Exception:
            return None
    return None


def _table_row_text(widget: Any, row: int = 0) -> str:
    if widget is None:
        return ""
    try:
        rows = int(widget.rowCount())
        cols = int(widget.columnCount())
        if rows <= row:
            return ""
        values: list[str] = []
        for col in range(cols):
            item = widget.item(row, col)
            values.append("" if item is None else str(item.text() or "").strip())
        return " | ".join(v for v in values if v)
    except Exception:
        return ""


def _read_log_tail(log_dir: Path, started_at_epoch: float) -> dict[str, Any]:
    log_path = log_dir / "aits.log"
    result: dict[str, Any] = {
        "path": str(log_path),
        "found": log_path.exists(),
        "provider_call_markers": 0,
        "risk_hits": [],
        "errors": [],
    }
    if not log_path.exists():
        return result
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")[-300_000:]
    except Exception as exc:
        result["warning"] = f"log_read_failed:{type(exc).__name__}"
        return result
    active_lines: list[str] = []
    active = False
    for line in text.splitlines():
        if len(line) >= 23 and line[4:5] == "-" and line[19:20] == ",":
            try:
                stamp = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
                active = stamp.timestamp() >= (started_at_epoch - 1.0)
            except Exception:
                pass
        if active:
            active_lines.append(line)
    active_text = "\n".join(active_lines)
    provider_markers = (
        "[AITS][OpenAIProviderProof] event=request_attempt",
        "[AITS][GeminiPayloadProof] event=request_summary",
        "[AITS][AIRefreshWorker] event=start",
    )
    result["provider_call_markers"] = sum(active_text.count(marker) for marker in provider_markers)
    result["risk_hits"] = [kw for kw in RISK_KEYWORDS if kw in active_text]
    result["errors"] = [
        line[-500:]
        for line in active_lines
        if any(token in line for token in ("Traceback", "CRITICAL", "ERROR"))
    ][-20:]
    return result


def _install_network_guards(report: dict[str, Any]) -> None:
    try:
        import requests

        class _DryReadResponse:
            status_code = 200
            text = "[]"

            def json(self) -> list[Any]:
                return []

            def raise_for_status(self) -> None:
                return None

        def _blocked_post(*args: Any, **kwargs: Any) -> Any:
            report["provider_call_blocked"] = True
            raise RuntimeError("AITS Qt smoke harness blocked provider POST in dry mode")

        requests.post = _blocked_post
        requests.get = lambda *args, **kwargs: _DryReadResponse()
    except Exception as exc:
        report.setdefault("warnings", []).append(f"network_guard_install_failed:{type(exc).__name__}")


def _patch_provider_verification(main_window_cls: Any, report: dict[str, Any]) -> None:
    def _skip_connection_check(self: Any, *args: Any, **kwargs: Any) -> None:
        report["startup_connection_check_skipped"] = True
        try:
            log = getattr(self, "_log", None)
            if log is not None:
                log.info("[AITS][QtSmokeHarness] startup_connection_check_skipped submitted=0")
        except Exception:
            pass

    for name in (
        "_run_ai_startup_connection_check_async",
        "_schedule_ai_startup_connection_check",
    ):
        if hasattr(main_window_cls, name):
            setattr(main_window_cls, name, _skip_connection_check)

    def _skip_ai_reco_updated(self: Any, payload: Any = None, *args: Any, **kwargs: Any) -> None:
        report["ai_reco_update_skipped"] = True
        try:
            log = getattr(self, "_log", None)
            if log is not None:
                log.info("[AITS][QtSmokeHarness] ai_reco_updated_skipped submitted=0")
        except Exception:
            pass

    if hasattr(main_window_cls, "_on_ai_reco_updated"):
        setattr(main_window_cls, "_on_ai_reco_updated", _skip_ai_reco_updated)


def _build_window(report: dict[str, Any]) -> tuple[Any, Any, dict[str, str]]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("AITS_DEV_LOGIN_BYPASS", "1")
    os.environ.setdefault("AITS_QT_SMOKE_HARNESS", "1")

    import run
    from PySide6.QtWidgets import QApplication
    from app.db.trades_db import init_trades_db
    from app.ui import app_gui

    paths = run.resolve_paths()
    run.ensure_runtime_dirs(paths["data_dir"], paths["log_dir"])
    run.init_logging(paths["log_dir"])
    app_gui.init_db(os.path.join(paths["root_dir"], "data"))
    app_gui.init_prefs(paths["root_dir"], paths["data_dir"])
    init_trades_db(paths["data_dir"])

    _patch_provider_verification(app_gui.MainWindow, report)

    app = QApplication.instance() or QApplication([str(ROOT / "run.py")])
    state = app_gui.AppState()
    state.login(app_gui.AITS_DEV_LOGIN_EMAIL)
    window = app_gui.MainWindow(state, paths["root_dir"], paths["data_dir"])
    window.show()
    return app, window, paths


def _pump_events(app: Any, seconds: float = 1.0) -> None:
    deadline = time.time() + max(float(seconds), 0.0)
    while time.time() < deadline:
        try:
            app.processEvents()
        except Exception:
            pass
        time.sleep(0.05)


def _collect(window: Any, widgets: dict[str, Any]) -> dict[str, Any]:
    tabs = getattr(window, "tabs", None)
    current_tab = ""
    try:
        current_tab = tabs.tabText(tabs.currentIndex())
    except Exception:
        pass
    managed_table = widgets.get("managed_table") or getattr(window, "tbl_ai_managed", None)
    trade_log_table = widgets.get("trade_log_table")
    if trade_log_table is None:
        trade_tab = getattr(window, "tab_trades", None)
        trade_log_table = getattr(trade_tab, "tbl_records", None)
    return {
        "window_title": str(window.windowTitle() or ""),
        "current_tab": current_tab,
        "aits_power_state": _safe_text(widgets.get("power_state")),
        "aits_safety_state": _safe_text(widgets.get("safety_state")),
        "selected_engine_text": _safe_text(widgets.get("selected_engine")),
        "applied_engine_text": _safe_text(widgets.get("applied_engine")),
        "connection_state_text": _safe_text(widgets.get("connection_state")),
        "managed_row_count": _table_row_count(managed_table),
        "trade_log_row_count": _table_row_count(trade_log_table),
        "latest_trade_log_row": _table_row_text(trade_log_table, 0),
    }


def _navigate(window: Any, widgets: dict[str, Any], report: dict[str, Any]) -> None:
    tab_order = [
        "managed_tab",
        "trade_log_tab",
        "investment_tab",
        "ai_policy_tab",
        "common_settings_tab",
    ]
    visited: list[dict[str, Any]] = []
    app = window.window().windowHandle()
    for index, key in enumerate(tab_order):
        widget = widgets.get(key)
        ok = False
        try:
            if widget is not None and hasattr(widget, "clicked"):
                widget.clicked.emit()
                ok = True
            else:
                tabs = getattr(window, "tabs", None)
                if tabs is not None:
                    tabs.setCurrentIndex(index)
                    ok = True
        except Exception as exc:
            visited.append({"target": key, "ok": False, "error": type(exc).__name__})
            continue
        try:
            qapp = widget.window().windowHandle() if widget is not None else app
            del qapp
        except Exception:
            pass
        visited.append({"target": key, "ok": ok})
    report["navigation"] = visited


def run_harness(mode: str, output_dir: Path, allow_provider_calls: bool) -> dict[str, Any]:
    started_epoch = time.time()
    report: dict[str, Any] = {
        "schema": "aits_qt_smoke_harness.v1",
        "mode": mode,
        "started_at": _now_iso(),
        "provider_calls_allowed": bool(allow_provider_calls),
        "provider_call_blocked": False,
        "warnings": [],
    }
    if mode == "provider-smoke" and not allow_provider_calls:
        report["status"] = "blocked"
        report["warnings"].append("provider-smoke requires --allow-provider-calls")
        return report
    if not allow_provider_calls:
        _install_network_guards(report)

    app, window, paths = _build_window(report)
    _pump_events(app, 1.2)

    widgets: dict[str, Any] = {}
    missing: list[str] = []
    for key, (kind, value) in CORE_WIDGETS.items():
        widget = _find_widget(window, kind, value)
        if widget is None and key == "managed_table":
            widget = getattr(window, "tbl_ai_managed", None)
        if widget is None and key == "trade_log_table":
            widget = getattr(getattr(window, "tab_trades", None), "tbl_records", None)
        widgets[key] = widget
        if widget is None:
            missing.append(key)

    if mode == "dry-navigation":
        _navigate(window, widgets, report)
        _pump_events(app, 0.5)
    elif mode == "dry-read":
        pass

    report.update(_collect(window, widgets))
    report["missing_widgets"] = missing
    safety_text = f"{report.get('aits_power_state','')} {report.get('aits_safety_state','')}"
    report["submitted_detected"] = False
    report["order_risk_detected"] = any(token in safety_text for token in ("AITS ON", "Live", "실거래"))
    report["log_tail"] = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    if report["log_tail"].get("risk_hits"):
        report["order_risk_detected"] = True
    if not allow_provider_calls and report.get("provider_call_blocked"):
        report["status"] = "fail"
    elif report["order_risk_detected"]:
        report["status"] = "no_go"
    elif report["missing_widgets"]:
        report["status"] = "partial"
    else:
        report["status"] = "pass"

    try:
        window.close()
        app.processEvents()
    except Exception:
        pass
    report["finished_at"] = _now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"runtime_smoke_report_{stamp}.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="AITS Qt objectName runtime smoke harness")
    parser.add_argument("--mode", choices=("dry-read", "dry-navigation", "provider-smoke"), default="dry-read")
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "runtime_smoke_reports"))
    args = parser.parse_args()
    report = run_harness(args.mode, Path(args.output_dir), args.allow_provider_calls)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in ("pass", "partial", "blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
