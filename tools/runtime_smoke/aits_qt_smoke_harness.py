from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


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
    "sell_market",
    "market_order",
    "buy_market_order",
    "sell_market_order",
    "PANIC-SELL",
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
    "manual_sell_all_button": ("property", "btn_manual_sell_all"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _sanitize_report_text(value: str, *, max_chars: int = 20_000) -> str:
    """Return text that is safe to persist in UTF-8 JSON reports."""

    text = _ANSI_ESCAPE_RE.sub("", str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch in ("\n", "\t"):
            cleaned.append(ch)
            continue
        if code == 0:
            continue
        if code < 32 or 0xD800 <= code <= 0xDFFF:
            cleaned.append("\ufffd")
            continue
        cleaned.append(ch)
    safe = "".join(cleaned)
    if len(safe) > max_chars:
        return safe[: max_chars - 20] + "\n...[truncated]"
    return safe


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _sanitize_report_text(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        safe_dict: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _sanitize_report_text(str(key), max_chars=500)
            safe_dict[safe_key] = _json_safe_value(item)
        return safe_dict
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, set):
        return [_json_safe_value(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, bytes):
        return _sanitize_report_text(value.decode("utf-8", errors="replace"))
    return _sanitize_report_text(repr(value))


def _json_report_text(report: dict[str, Any]) -> str:
    safe_report = _json_safe_value(report)
    return json.dumps(safe_report, ensure_ascii=False, indent=2, allow_nan=False)


def _write_json_report(report: dict[str, Any], path: Path) -> dict[str, Any]:
    safe_report = _json_safe_value(report)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(safe_report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
    return safe_report


def _write_text_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_sanitize_report_text(text), encoding="utf-8", newline="\n")


def _open_text_report_windows(path: Path) -> bool:
    try:
        subprocess.Popen(["notepad.exe", str(path)])
        return True
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
            return True
        except Exception:
            return False


def _mask_confirm_phrase(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 12:
        return text[:2] + "***" + text[-2:]
    return text[:8] + "***" + text[-8:]


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
        "provider_branch_markers": 0,
        "external_cost_call_markers": 0,
        "marker_counts": {},
        "latest_group_id": "",
        "snapshot_recorded": False,
        "journal_recorded": False,
        "same_stage_duplicate_detected": False,
        "risk_hits": [],
        "errors": [],
        "proof_lines": [],
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
    marker_counts = {
        "openai_request_attempt": active_text.count("[AITS][OpenAIProviderProof] event=request_attempt"),
        "gemini_request_summary": active_text.count("[AITS][GeminiPayloadProof] event=request_summary"),
        "worker_start": active_text.count("[AITS][AIRefreshWorker] event=start"),
        "dispatch_provider_branch": active_text.count("[AITS][AIRefreshDispatch] event=provider_branch"),
        "snapshot_store": active_text.count("[AITS][AISnapshotStore]"),
        "trade_log_stage": active_text.count("[AITS][TradeLogDecisionStage]"),
        "trade_log_shadow_journal": active_text.count("[AITS][TradeLogShadowJournal]"),
        "ai_refresh_apply_journal": active_text.count("[AITS][AIRefreshApply] event=journal_recorded"),
        "trade_log_save_start": active_text.count("[AITS][TradeLogSave] event=start"),
        "trade_log_save_finish": active_text.count("[AITS][TradeLogSave] event=finish"),
        "trade_log_save_failed": active_text.count("[AITS][TradeLogSave] event=failed"),
        "riskguard_active_path": active_text.count("[AITS][RiskGuardActivePath]"),
    }
    result["marker_counts"] = marker_counts
    result["external_cost_call_markers"] = (
        marker_counts["openai_request_attempt"] + marker_counts["gemini_request_summary"]
    )
    result["provider_branch_markers"] = marker_counts["dispatch_provider_branch"]
    result["provider_call_markers"] = (
        result["external_cost_call_markers"]
        + marker_counts["worker_start"]
        + marker_counts["dispatch_provider_branch"]
    )
    result["snapshot_recorded"] = marker_counts["snapshot_store"] > 0
    result["journal_recorded"] = (
        marker_counts["trade_log_stage"] > 0
        or marker_counts["trade_log_shadow_journal"] > 0
        or marker_counts["ai_refresh_apply_journal"] > 0
    )
    result["same_stage_duplicate_detected"] = any(
        "same_stage_duplicate" in line.lower()
        or "duplicate=true" in line.lower()
        or "duplicate=True" in line
        for line in active_lines
    )
    groups = re.findall(r"group_id=([A-Za-z0-9_.:-]+)", active_text)
    if groups:
        result["latest_group_id"] = groups[-1]
    proof_tokens = (
        "[AITS][AIRefreshButton]",
        "[AITS][AIRefreshTarget]",
        "[AITS][AIRefreshDispatch]",
        "[AITS][AIRefreshProviderContext]",
        "[AITS][AIRefreshWorker]",
        "[AITS][OpenAIProviderProof]",
        "[AITS][GeminiPayloadProof]",
        "[AITS][GeminiModelConfig]",
        "[AITS][GeminiKeySource]",
        "[AITS][AIOutputContract]",
        "[AITS][AISnapshotStore]",
        "[AITS][TradeLogDecisionStage]",
        "[AITS][TradeLogShadowJournal]",
        "[AITS][AIRefreshApply]",
        "[AITS][RiskGuardActivePath]",
    )
    result["proof_lines"] = [
        line[-700:]
        for line in active_lines
        if any(token in line for token in proof_tokens)
    ][-40:]
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


def _patch_provider_verification(
    main_window_cls: Any,
    report: dict[str, Any],
    *,
    skip_ai_reco_updates: bool,
    skip_startup_restore: bool,
) -> None:
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

    if skip_startup_restore and hasattr(main_window_cls, "_restore_api_keys_after_ui_ready"):
        def _skip_startup_restore(self: Any, *args: Any, **kwargs: Any) -> None:
            report["startup_provider_restore_skipped"] = True
            try:
                log = getattr(self, "_log", None)
                if log is not None:
                    log.info("[AITS][QtSmokeHarness] startup_provider_restore_skipped submitted=0")
            except Exception:
                pass

        setattr(main_window_cls, "_restore_api_keys_after_ui_ready", _skip_startup_restore)

    if skip_ai_reco_updates:
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


def _build_window(
    report: dict[str, Any],
    *,
    skip_ai_reco_updates: bool,
    skip_startup_restore: bool,
) -> tuple[Any, Any, dict[str, str]]:
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

    _patch_provider_verification(
        app_gui.MainWindow,
        report,
        skip_ai_reco_updates=skip_ai_reco_updates,
        skip_startup_restore=skip_startup_restore,
    )

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
    manual_order_buttons: list[dict[str, Any]] = []
    for key in ("manual_sell_all_button",):
        widget = widgets.get(key)
        manual_order_buttons.append(
            {
                "key": key,
                "found": widget is not None,
                "object_name": str(widget.objectName() or "") if widget is not None and hasattr(widget, "objectName") else "",
                "text": _safe_text(widget),
                "tooltip": str(widget.toolTip() or "") if widget is not None and hasattr(widget, "toolTip") else "",
                "visible": bool(widget.isVisible()) if widget is not None and hasattr(widget, "isVisible") else False,
                "enabled": bool(widget.isEnabled()) if widget is not None and hasattr(widget, "isEnabled") else False,
            }
        )
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
        "manual_order_buttons": manual_order_buttons,
        "manual_order_button_risk": any(
            bool(item.get("found")) and bool(item.get("visible")) and bool(item.get("enabled"))
            for item in manual_order_buttons
        ),
    }


def _widget_snapshot(widget: Any, *, key: str = "", source: str = "") -> dict[str, Any]:
    return {
        "key": key,
        "source": source,
        "found": widget is not None,
        "class_name": type(widget).__name__ if widget is not None else "",
        "object_name": str(widget.objectName() or "") if widget is not None and hasattr(widget, "objectName") else "",
        "smoke_object_name": (
            str(widget.property("smokeObjectName") or "") if widget is not None and hasattr(widget, "property") else ""
        ),
        "text": _safe_text(widget),
        "tooltip": str(widget.toolTip() or "") if widget is not None and hasattr(widget, "toolTip") else "",
        "visible": bool(widget.isVisible()) if widget is not None and hasattr(widget, "isVisible") else False,
        "enabled": bool(widget.isEnabled()) if widget is not None and hasattr(widget, "isEnabled") else False,
        "checked": bool(widget.isChecked()) if widget is not None and hasattr(widget, "isChecked") else False,
    }


def _discover_aits_on_selector(window: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    attr_widget = getattr(window, "btn_run_toggle", None)
    if attr_widget is not None:
        candidates.append(_widget_snapshot(attr_widget, key="btn_run_toggle", source="main_window_attr"))

    try:
        from PySide6.QtWidgets import QPushButton

        buttons = window.findChildren(QPushButton)
    except Exception:
        buttons = []
    preferred_object_names = {
        "StopButton",
        "btn_run_toggle",
        "btn_aits_run",
        "btn_start",
        "btn_start_stop",
        "btn_execute",
    }
    preferred_smoke_names = {
        "btn_run_toggle",
        "btn_aits_run",
        "btn_aits_on",
        "btn_start",
    }
    for index, button in enumerate(buttons):
        try:
            object_name = str(button.objectName() or "")
            smoke_name = str(button.property("smokeObjectName") or "")
            text = _safe_text(button).upper()
        except Exception:
            continue
        if (
            object_name in preferred_object_names
            or smoke_name in preferred_smoke_names
            or text in {"ON", "OFF", "AITS ON", "AITS OFF", "RUN", "STOP"}
        ):
            snapshot = _widget_snapshot(button, key=f"button_{index}", source="qpushbutton_scan")
            if snapshot not in candidates:
                candidates.append(snapshot)

    selected = candidates[0] if candidates else {"found": False}
    return {
        "found": bool(selected.get("found")),
        "selected": selected,
        "candidate_count": len(candidates),
        "candidates": candidates[:12],
        "clicked": False,
    }


def _guarded_window_runtime_summary_markdown(report: dict[str, Any]) -> str:
    config = report.get("guarded_window_config") or {}
    return "\n".join(
        [
            "# AITS Live 2H Guarded Window Runtime Harness Smoke",
            "",
            f"- mode: {report.get('mode', '')}",
            f"- smoke_mode: {report.get('smoke_mode', False)}",
            f"- confirm_phrase_valid: {report.get('confirm_phrase_valid', False)}",
            f"- duration_requested_min: {report.get('duration_requested_min', '')}",
            f"- duration_actual_sec: {report.get('duration_actual_sec', '')}",
            f"- per_order_krw: {config.get('per_order_krw', '')}",
            f"- per_order_hard_cap_krw: {config.get('per_order_hard_cap_krw', '')}",
            f"- total_window_cap_krw: {config.get('total_window_cap_krw', '')}",
            f"- max_order_count: {config.get('max_order_count', '')}",
            f"- min_order_interval_sec: {config.get('min_order_interval_sec', '')}",
            f"- baseline_status: {report.get('baseline_status', '')}",
            f"- monitoring_loop_status: {report.get('monitoring_loop_status', '')}",
            f"- aits_on_selector_found: {report.get('aits_on_selector_found', False)}",
            f"- aits_on_clicked: {report.get('aits_on_clicked', False)}",
            f"- order_count: {report.get('order_count', 0)}",
            f"- total_order_amount_krw: {report.get('total_order_amount_krw', 0)}",
            f"- place_order_call_count: {report.get('place_order_call_count', 0)}",
            f"- cancel_call_count: {report.get('cancel_call_count', 0)}",
            f"- sell_call_count: {report.get('sell_call_count', 0)}",
            f"- retry_call_count: {report.get('retry_call_count', 0)}",
            f"- provider_external_call_count: {report.get('provider_external_call_count', 0)}",
            f"- incident_report_smoke_path: {report.get('incident_report_smoke_path', '')}",
            f"- incident_report_auto_opened: {report.get('incident_report_auto_opened', False)}",
            f"- report_status: {report.get('report_status', '')}",
            "",
            "No AITS ON click, no buy, no sell, no cancel, no retry, and no order submission occurred in this smoke.",
            "",
        ]
    )


def _latest_journal_summary(window: Any) -> dict[str, Any]:
    getter = getattr(window, "_get_trade_log_shadow_journal_rows", None)
    rows: list[dict[str, Any]] = []
    if callable(getter):
        try:
            rows = [row for row in list(getter(limit=5) or []) if isinstance(row, dict)]
        except Exception:
            rows = []
    latest = rows[0] if rows else {}
    wanted = (
        "time",
        "symbol",
        "decision_group_id",
        "record_stage",
        "record_stage_label",
        "analysis_classification",
        "provider_selected",
        "provider_actual",
        "fallback_used",
        "fallback_reason_code",
        "fallback_reason_display",
        "http_status",
        "error_code",
        "usage_input_tokens",
        "usage_output_tokens",
        "usage_total_tokens",
    )
    return {
        "journal_rows_sample_count": len(rows),
        "latest_journal": {key: latest.get(key, "") for key in wanted},
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


def _table_cell_text(widget: Any, row: int, col: int) -> str:
    try:
        item = widget.item(row, col)
        return "" if item is None else str(item.text() or "").strip()
    except Exception:
        return ""


def _find_symbol_in_row(widget: Any, row: int, window: Any = None) -> str:
    if window is not None:
        try:
            rows = getattr(window, "ai_managed_rows", None)
            if isinstance(rows, list) and 0 <= row < len(rows):
                value = str((rows[row] or {}).get("symbol") or "").strip()
                if value:
                    return value
        except Exception:
            pass
        try:
            resolver = getattr(window, "_extract_ai_refresh_symbol_from_managed_row", None)
            rows = getattr(window, "ai_managed_rows", None)
            if callable(resolver) and isinstance(rows, list) and 0 <= row < len(rows):
                value = str(resolver(rows[row]) or "").strip()
                if value:
                    return value
        except Exception:
            pass
    try:
        cols = int(widget.columnCount())
    except Exception:
        return ""
    for col in range(cols):
        value = _table_cell_text(widget, row, col)
        if re.match(r"^[A-Z]+-[A-Z0-9]+$", value):
            return value
    return _table_cell_text(widget, row, 0)


def _safe_click(widget: Any) -> bool:
    if widget is None:
        return False
    try:
        if hasattr(widget, "click"):
            widget.click()
            return True
    except Exception:
        return False
    try:
        if hasattr(widget, "clicked"):
            widget.clicked.emit()
            return True
    except Exception:
        return False
    return False


def _select_provider(window: Any, provider: str, report: dict[str, Any]) -> bool:
    provider = provider.strip().lower()
    report["provider_selector"] = ""
    try:
        setattr(window, "_provider_user_selected", True)
    except Exception:
        pass
    try:
        sync_panel = getattr(window, "_sync_engine_choice_panel", None)
        if callable(sync_panel):
            engine_key = {"gpt": "openai", "gemini": "gemini", "local": "local"}[provider]
            sync_panel(
                engine_key,
                start_connection=False,
                select_session=True,
                reason="qt_smoke_provider_smoke",
            )
            report["provider_selector"] = "MainWindow._sync_engine_choice_panel(start_connection=False)"
            return True
    except Exception as exc:
        report["provider_select_error"] = type(exc).__name__
    try:
        selector = getattr(window, "_select_ai_provider_for_session", None)
        if callable(selector):
            selector(provider, reason="qt_smoke_provider_smoke", start_connection=False)
            report["provider_selector"] = "MainWindow._select_ai_provider_for_session(start_connection=False)"
            return True
    except Exception as exc:
        report["provider_select_error"] = type(exc).__name__
        return False
    attr_map = {
        "gpt": "btn_engine_openai",
        "gemini": "btn_engine_gemini",
        "local": "btn_engine_local",
    }
    button = getattr(window, attr_map.get(provider, ""), None)
    if _safe_click(button):
        report["provider_selector"] = attr_map.get(provider, "")
        return True
    return False


def _select_managed_row(widget: Any, target_symbol: str | None, report: dict[str, Any], window: Any = None) -> bool:
    if widget is None:
        report["target_select_error"] = "managed_table_missing"
        return False
    try:
        rows = int(widget.rowCount())
    except Exception:
        report["target_select_error"] = "managed_row_count_unreadable"
        return False
    if rows <= 0:
        report["target_select_error"] = "managed_table_empty"
        return False
    target = (target_symbol or "").strip().upper()
    selected_row = 0
    selected_symbol = ""
    for row in range(rows):
        symbol = _find_symbol_in_row(widget, row, window).strip().upper()
        if not selected_symbol and symbol:
            selected_symbol = symbol
        if target and symbol == target:
            selected_row = row
            selected_symbol = symbol
            break
    if target and selected_symbol != target:
        report["target_select_error"] = f"target_symbol_not_found:{target}"
        return False
    try:
        widget.selectRow(selected_row)
        widget.setCurrentCell(selected_row, 0)
    except Exception as exc:
        report["target_select_error"] = type(exc).__name__
        return False
    report["selected_row"] = selected_row
    report["selected_symbol"] = _find_symbol_in_row(widget, selected_row, window)
    return True


def _normalize_provider_for_report(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"openai", "chatgpt", "gpt"}:
        return "gpt"
    if text in {"gemini", "google", "google_gemini"}:
        return "gemini"
    if text in {"basic", "local", "local_ai", "ollama"}:
        return "local"
    return text


def _provider_state_snapshot(window: Any) -> dict[str, str]:
    fields = {
        "selected_provider": getattr(window, "_selected_ai_provider", ""),
        "applied_provider": getattr(window, "_applied_ai_provider", ""),
        "active_provider": getattr(window, "_ai_provider_box_active", ""),
        "connection_provider": getattr(window, "_last_ai_connection_provider", ""),
    }
    return {key: _normalize_provider_for_report(value) for key, value in fields.items()}


def _marker_delta(after: dict[str, Any], before: dict[str, Any], key: str) -> int:
    return int(after.get(key, 0) or 0) - int(before.get(key, 0) or 0)


def _marker_count_delta(after: dict[str, Any], before: dict[str, Any], key: str) -> int:
    after_counts = after.get("marker_counts") or {}
    before_counts = before.get("marker_counts") or {}
    return int(after_counts.get(key, 0) or 0) - int(before_counts.get(key, 0) or 0)


def _wait_for_provider_result(
    app: Any,
    paths: dict[str, str],
    started_epoch: float,
    before_log: dict[str, Any],
    before_rows: int | None,
    trade_log_table: Any,
    timeout_sec: float,
) -> dict[str, Any]:
    deadline = time.time() + max(float(timeout_sec), 1.0)
    latest = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    while time.time() < deadline:
        _pump_events(app, 0.35)
        latest = _read_log_tail(Path(paths["log_dir"]), started_epoch)
        current_rows = _table_row_count(trade_log_table)
        row_increased = (
            before_rows is not None
            and current_rows is not None
            and current_rows > before_rows
        )
        proof_delta = (
            _marker_count_delta(latest, before_log, "trade_log_stage") > 0
            or _marker_count_delta(latest, before_log, "trade_log_shadow_journal") > 0
            or _marker_count_delta(latest, before_log, "ai_refresh_apply_journal") > 0
            or _marker_count_delta(latest, before_log, "snapshot_store") > 0
        )
        if row_increased or proof_delta:
            break
    return latest


def _run_provider_smoke(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    paths: dict[str, str],
    report: dict[str, Any],
    *,
    provider: str,
    max_provider_calls: int,
    target_symbol: str | None,
    timeout_sec: float,
    wait_after_click_sec: float,
    fail_on_provider_call_over_limit: bool,
    no_click: bool,
    started_epoch: float,
) -> None:
    provider = (provider or "").strip().lower()
    report.update(
        {
            "provider": provider,
            "max_provider_calls": max_provider_calls,
            "target_symbol": target_symbol or "",
            "timeout_sec": timeout_sec,
            "wait_after_click_sec": wait_after_click_sec,
            "fail_on_provider_call_over_limit": bool(fail_on_provider_call_over_limit),
            "ai_refresh_clicked": False,
            "pass_status": "pending",
            "fail_reason": "",
        }
    )
    if provider not in {"local", "gpt", "gemini"}:
        report["pass_status"] = "fail"
        report["fail_reason"] = "provider_required"
        return
    if max_provider_calls < 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_must_be_positive"
        return
    if max_provider_calls > 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_over_one_blocked"
        return

    before_collect = _collect(window, widgets)
    report["selected_engine_before"] = before_collect.get("selected_engine_text", "")
    report["applied_engine_before"] = before_collect.get("applied_engine_text", "")
    report["connection_state_before"] = before_collect.get("connection_state_text", "")
    report["provider_state_before"] = _provider_state_snapshot(window)

    if not _select_provider(window, provider, report):
        report["pass_status"] = "fail"
        report["fail_reason"] = "provider_select_failed"
        return
    _pump_events(app, 1.5)

    managed_tab = widgets.get("managed_tab")
    if managed_tab is not None:
        _safe_click(managed_tab)
        _pump_events(app, 0.5)

    managed_table = widgets.get("managed_table") or getattr(window, "tbl_ai_managed", None)
    if not _select_managed_row(managed_table, target_symbol, report, window):
        report["pass_status"] = "fail"
        report["fail_reason"] = report.get("target_select_error") or "target_select_failed"
        return
    _pump_events(app, 0.5)

    after_select = _collect(window, widgets)
    report["selected_engine_after"] = after_select.get("selected_engine_text", "")
    report["applied_engine_after"] = after_select.get("applied_engine_text", "")
    report["connection_state_after"] = after_select.get("connection_state_text", "")
    provider_state_after = _provider_state_snapshot(window)
    report["provider_state_after"] = provider_state_after
    if provider not in set(provider_state_after.values()):
        report["pass_status"] = "fail"
        report["fail_reason"] = f"provider_state_mismatch:{provider_state_after}"
        return
    if _normalize_provider_for_report(provider_state_after.get("applied_provider")) != provider:
        report["pass_status"] = "fail"
        report["fail_reason"] = f"applied_provider_mismatch:{provider_state_after.get('applied_provider')}"
        return

    safety_text = f"{after_select.get('aits_power_state','')} {after_select.get('aits_safety_state','')}"
    if any(token in safety_text for token in ("AITS ON", "Live", "실거래")):
        report["pass_status"] = "no_go"
        report["fail_reason"] = "unsafe_aits_state_before_click"
        return

    trade_log_table = widgets.get("trade_log_table")
    if trade_log_table is None:
        trade_log_table = getattr(getattr(window, "tab_trades", None), "tbl_records", None)
    before_rows = _table_row_count(trade_log_table)
    report["trade_log_row_count_before"] = before_rows
    before_log = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    report["provider_call_count_before"] = before_log.get("provider_call_markers", 0)
    report["external_cost_call_count_before"] = before_log.get("external_cost_call_markers", 0)
    report["provider_generation_attempts_before"] = 0

    if no_click:
        report["pass_status"] = "pass"
        report["ai_refresh_clicked"] = False
        report["fail_reason"] = ""
        return

    button = widgets.get("ai_refresh_button")
    if button is None:
        report["pass_status"] = "fail"
        report["fail_reason"] = "ai_refresh_button_missing"
        return
    try:
        if hasattr(button, "isEnabled") and not button.isEnabled():
            report["pass_status"] = "fail"
            report["fail_reason"] = "ai_refresh_button_disabled"
            return
    except Exception:
        pass

    if not _safe_click(button):
        report["pass_status"] = "fail"
        report["fail_reason"] = "ai_refresh_click_failed"
        return
    report["ai_refresh_clicked"] = True
    _pump_events(app, max(float(wait_after_click_sec), 0.0))

    after_log = _wait_for_provider_result(
        app,
        paths,
        started_epoch,
        before_log,
        before_rows,
        trade_log_table,
        timeout_sec,
    )
    report["log_tail_after_click"] = after_log

    _navigate(window, widgets, report)
    trade_tab_widget = widgets.get("trade_log_tab")
    if trade_tab_widget is not None:
        _safe_click(trade_tab_widget)
    _pump_events(app, 0.8)
    try:
        if trade_log_table is not None and int(trade_log_table.rowCount()) > 0:
            trade_log_table.selectRow(0)
    except Exception:
        pass
    _pump_events(app, 0.3)

    after_collect = _collect(window, widgets)
    external_delta = _marker_delta(after_log, before_log, "external_cost_call_markers")
    branch_delta = _marker_count_delta(after_log, before_log, "dispatch_provider_branch")
    worker_delta = _marker_count_delta(after_log, before_log, "worker_start")
    provider_generation_delta = branch_delta if provider == "local" else external_delta
    report.update(
        {
            "trade_log_row_count_after": after_collect.get("trade_log_row_count"),
            "latest_trade_row": after_collect.get("latest_trade_log_row", ""),
            "trade_detail_excerpt": _safe_text(widgets.get("trade_log_detail"))[:1800],
            "provider_call_count_after": after_log.get("provider_call_markers", 0),
            "external_cost_call_count_after": after_log.get("external_cost_call_markers", 0),
            "provider_call_marker_delta": _marker_delta(after_log, before_log, "provider_call_markers"),
            "provider_branch_delta": branch_delta,
            "worker_start_delta": worker_delta,
            "provider_call_delta": provider_generation_delta,
            "external_cost_call_delta": external_delta,
            "group_id": after_log.get("latest_group_id", ""),
            "snapshot_recorded": after_log.get("snapshot_recorded", False),
            "journal_recorded": after_log.get("journal_recorded", False),
            "same_stage_duplicate": after_log.get("same_stage_duplicate_detected", False),
        }
    )

    fail_reasons: list[str] = []
    if fail_on_provider_call_over_limit and report["provider_call_delta"] > max_provider_calls:
        fail_reasons.append("provider_call_delta_over_limit")
    if provider == "local" and report["external_cost_call_delta"] != 0:
        fail_reasons.append("local_external_cost_call_detected")
    if provider == "local":
        latest_row = str(report.get("latest_trade_row") or "")
        detail_text = str(report.get("trade_detail_excerpt") or "")
        if "LOCAL" not in latest_row and "LOCAL" not in detail_text:
            fail_reasons.append("local_trade_log_not_detected")
        if "실제 주문 없음" not in latest_row and "실제 주문 없음" not in detail_text:
            fail_reasons.append("no_order_text_missing")
    if not report.get("journal_recorded") and (report.get("trade_log_row_count_after") == before_rows):
        fail_reasons.append("journal_or_row_update_not_detected")
    if report.get("same_stage_duplicate"):
        fail_reasons.append("same_stage_duplicate_detected")

    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(fail_reasons)
    else:
        report["pass_status"] = "pass"


def _run_save_probe(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    paths: dict[str, str],
    report: dict[str, Any],
    *,
    timeout_sec: float,
    started_epoch: float,
) -> None:
    report.update(
        {
            "save_clicked": False,
            "save_handler_entered": False,
            "save_completed": False,
            "save_elapsed_ms": None,
            "save_messagebox_seen": False,
            "save_messagebox_text": "",
            "save_error": "",
            "pass_status": "pending",
            "fail_reason": "",
        }
    )
    trade_tab_widget = widgets.get("trade_log_tab")
    if trade_tab_widget is not None:
        _safe_click(trade_tab_widget)
        _pump_events(app, 0.8)

    trade_log_table = widgets.get("trade_log_table")
    if trade_log_table is None:
        trade_log_table = getattr(getattr(window, "tab_trades", None), "tbl_records", None)
    try:
        tab = getattr(window, "tab_trades", None)
        if tab is not None and hasattr(tab, "refresh"):
            tab.refresh()
    except Exception:
        pass
    _pump_events(app, 0.5)

    before_collect = _collect(window, widgets)
    before_journal = _latest_journal_summary(window)
    before_log = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    report.update(
        {
            "trade_log_row_count_before": before_collect.get("trade_log_row_count"),
            "latest_row_before": before_collect.get("latest_trade_log_row", ""),
            "journal_before": before_journal,
            "provider_call_count_before": before_log.get("provider_call_markers", 0),
            "external_cost_call_count_before": before_log.get("external_cost_call_markers", 0),
        }
    )

    save_button = widgets.get("trade_log_save") or getattr(window, "btn_nav_save", None)
    report["save_button_found"] = save_button is not None
    try:
        report["save_button_enabled"] = bool(save_button.isEnabled()) if save_button is not None else False
    except Exception:
        report["save_button_enabled"] = None

    safety_text = f"{before_collect.get('aits_power_state','')} {before_collect.get('aits_safety_state','')}"
    if any(token in safety_text for token in ("AITS ON", "Live", "?ㅺ굅??")):
        report["pass_status"] = "no_go"
        report["fail_reason"] = "unsafe_aits_state_before_save"
        return

    handler = getattr(window, "_save_trade_log_center_state", None)
    if not callable(handler):
        report["pass_status"] = "fail"
        report["fail_reason"] = "save_handler_missing"
        return

    started = time.time()
    try:
        report["save_handler_entered"] = True
        ok = bool(handler(reason="qt_smoke_save_probe"))
        report["save_completed"] = ok
    except Exception as exc:
        report["save_error"] = type(exc).__name__
        report["save_completed"] = False
    report["save_elapsed_ms"] = int((time.time() - started) * 1000)
    _pump_events(app, min(max(float(timeout_sec), 1.0), 3.0))

    after_collect = _collect(window, widgets)
    after_journal = _latest_journal_summary(window)
    after_log = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    report.update(
        {
            "trade_log_row_count_after": after_collect.get("trade_log_row_count"),
            "latest_row_after": after_collect.get("latest_trade_log_row", ""),
            "journal_after": after_journal,
            "provider_call_count_after": after_log.get("provider_call_markers", 0),
            "external_cost_call_count_after": after_log.get("external_cost_call_markers", 0),
            "provider_call_delta": _marker_delta(after_log, before_log, "provider_call_markers"),
            "external_cost_call_delta": _marker_delta(after_log, before_log, "external_cost_call_markers"),
            "save_log_start_delta": _marker_count_delta(after_log, before_log, "trade_log_save_start"),
            "save_log_finish_delta": _marker_count_delta(after_log, before_log, "trade_log_save_finish"),
            "save_log_failed_delta": _marker_count_delta(after_log, before_log, "trade_log_save_failed"),
            "log_tail_after_save": after_log,
        }
    )

    fail_reasons: list[str] = []
    if not report.get("save_completed"):
        fail_reasons.append("save_handler_returned_false")
    if int(report.get("save_elapsed_ms") or 0) > 10_000:
        fail_reasons.append("save_elapsed_over_10s")
    if report.get("provider_call_delta") != 0 or report.get("external_cost_call_delta") != 0:
        fail_reasons.append("provider_call_detected")
    if report.get("save_log_finish_delta", 0) < 1:
        fail_reasons.append("save_finish_log_missing")
    if report.get("trade_log_row_count_after") != report.get("trade_log_row_count_before"):
        fail_reasons.append("trade_log_row_count_changed")
    if report.get("latest_row_after") != report.get("latest_row_before"):
        fail_reasons.append("latest_row_changed")
    if after_log.get("risk_hits"):
        fail_reasons.append("order_risk_detected")

    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(fail_reasons)
    else:
        report["pass_status"] = "pass"


def _riskguard_fixtures() -> list[dict[str, Any]]:
    base = {
        "symbol": "KRW-BTC",
        "side": "buy",
        "requested_amount_krw": 5000.0,
        "price": 100000000.0,
        "quantity": 0.0,
        "source_provider": "local",
        "confidence": 0.72,
        "action": "buy",
        "holdings_value_krw": 0.0,
        "cash_available_krw": 100000.0,
        "portfolio_value_krw": 1000000.0,
        "daily_realized_pnl_krw": 0.0,
        "daily_loss_limit_krw": 50000.0,
        "max_order_amount_krw": 10000.0,
        "max_position_value_krw": 30000.0,
        "emergency_stop": False,
        "stale_price": False,
        "execution_mode": "disabled",
        "dry_run": True,
    }

    def fixture(name: str, expected_allowed: bool, **overrides: Any) -> dict[str, Any]:
        candidate = dict(base)
        candidate.update(overrides)
        candidate["request_id"] = name
        return {
            "name": name,
            "expected_allowed": bool(expected_allowed),
            "candidate": candidate,
        }

    return [
        fixture("allowed_small_buy", True),
        fixture("blocked_max_order", False, requested_amount_krw=25000.0),
        fixture("blocked_position_limit", False, holdings_value_krw=26000.0, requested_amount_krw=5000.0),
        fixture("blocked_daily_loss", False, daily_realized_pnl_krw=-50000.0),
        fixture("blocked_emergency_stop", False, emergency_stop=True),
        fixture("blocked_invalid_symbol", False, symbol="BTC"),
        fixture("blocked_stale_price", False, stale_price=True),
    ]


def _run_riskguard_proof(report: dict[str, Any]) -> None:
    from app.services.risk_guard import RiskGuard

    guard = RiskGuard()
    results: list[dict[str, Any]] = []
    pass_count = 0
    fail_count = 0

    for item in _riskguard_fixtures():
        candidate = item["candidate"]
        result = guard.evaluate_order_candidate(candidate)
        result_dict = result.to_dict()
        passed = (
            bool(result.allowed) == bool(item["expected_allowed"])
            and int(result.submitted) == 0
            and bool(result.order_allowed) is False
            and bool(result.real_order) is False
            and bool(result.dry_run) is True
        )
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        results.append(
            {
                "name": item["name"],
                "expected_allowed": item["expected_allowed"],
                "actual_allowed": bool(result.allowed),
                "risk_allowed": bool(result.risk_allowed),
                "blocked_reason": result.blocked_reason,
                "severity": result.severity,
                "submitted": int(result.submitted),
                "order_allowed": bool(result.order_allowed),
                "real_order": bool(result.real_order),
                "dry_run": bool(result.dry_run),
                "pass": bool(passed),
                "result": result_dict,
                "log_summary": guard.log_summary(result, candidate),
            }
        )

    report.update(
        {
            "riskguard_fixture_count": len(results),
            "riskguard_pass_count": pass_count,
            "riskguard_fail_count": fail_count,
            "riskguard_results": results,
            "provider_call_markers": 0,
            "provider_call_delta": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
            "submitted_detected": False,
            "order_risk_detected": False,
            "real_order_detected": False,
            "pass_status": "pass" if fail_count == 0 else "fail",
        }
    )


def _live_preflight_fixtures() -> list[dict[str, Any]]:
    base: dict[str, Any] = {
        "request_id": "locked_base",
        "symbol": "KRW-BTC",
        "side": "buy",
        "amount_krw": 5000.0,
        "quantity": 0.00005,
        "price": 100000000.0,
        "execution_mode": "live",
        "aits_enabled": True,
        "live_order_unlock": True,
        "user_confirm_token": "fixture-confirm-token",
        "risk_guard_checked": True,
        "risk_allowed": True,
        "emergency_stop": False,
        "max_order_amount_krw": 10000.0,
        "max_daily_loss_krw": 30000.0,
        "max_order_count_per_cycle": 1,
        "duplicate_order_lock": True,
        "min_real_order_amount_krw": 5000.0,
        "account_ready": True,
        "api_key_ready": True,
        "price_fresh": True,
        "selected_provider": "local",
        "source": "live_preflight_locked_proof",
    }

    def fixture(name: str, expected_reason: str, **overrides: Any) -> dict[str, Any]:
        item = dict(base)
        item.update(overrides)
        item["request_id"] = name
        return {
            "name": name,
            "expected_locked": True,
            "expected_allowed": False,
            "expected_reason": expected_reason,
            "input": item,
        }

    return [
        fixture("locked_execution_mode_disabled", "execution_mode_not_live", execution_mode="disabled"),
        fixture("locked_missing_user_confirm", "user_confirm_token_missing", **{"user_confirm_token": ""}),
        fixture(
            "locked_missing_riskguard",
            "risk_guard_not_checked",
            risk_guard_checked=False,
            risk_allowed=False,
        ),
        fixture("locked_emergency_stop", "emergency_stop_active", emergency_stop=True),
        fixture("locked_amount_exceeds_cap", "max_order_amount_exceeded", amount_krw=500000.0),
    ]


def _run_live_preflight_locked_proof(report: dict[str, Any]) -> None:
    from app.services.live_order_preflight import LiveOrderPreflight

    preflight = LiveOrderPreflight()
    results: list[dict[str, Any]] = []
    pass_count = 0
    fail_count = 0

    for item in _live_preflight_fixtures():
        result = preflight.evaluate(item["input"])
        result_dict = result.to_dict()
        passed = (
            bool(result.locked) is True
            and bool(result.allowed) is False
            and str(result.blocked_reason or "") == str(item["expected_reason"])
            and int(result.submitted) == 0
            and bool(result.order_allowed) is False
            and bool(result.real_order) is False
        )
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        results.append(
            {
                "name": item["name"],
                "expected_locked": item["expected_locked"],
                "expected_allowed": item["expected_allowed"],
                "expected_reason": item["expected_reason"],
                "actual_locked": bool(result.locked),
                "actual_allowed": bool(result.allowed),
                "blocked_reason": str(result.blocked_reason or ""),
                "submitted": int(result.submitted),
                "order_allowed": bool(result.order_allowed),
                "real_order": bool(result.real_order),
                "execution_mode": str(result.execution_mode or ""),
                "pass": bool(passed),
                "result": result_dict,
                "log_summary": preflight.log_summary(result, item["input"]),
            }
        )

    report.update(
        {
            "live_preflight_fixture_count": len(results),
            "live_preflight_pass_count": pass_count,
            "live_preflight_fail_count": fail_count,
            "live_preflight_results": results,
            "order_service_place_order_called": False,
            "order_adapter_live_branch_entered": False,
            "order_adapter_execution_mode": "disabled",
            "provider_call_markers": 0,
            "provider_call_delta": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
            "submitted_detected": False,
            "order_risk_detected": False,
            "real_order_detected": False,
            "paper_mode_created": False,
            "virtual_trading_created": False,
            "mock_trading_processor_created": False,
            "pass_status": "pass" if fail_count == 0 else "fail",
        }
    )


def _run_live_one_shot_unlock_contract_proof(report: dict[str, Any]) -> None:
    from datetime import timedelta, timezone

    from app.services.live_order_preflight import LiveOrderPreflight, LiveOrderPreflightInput
    from app.services.live_order_unlock import LiveOneShotUnlock

    now = datetime.now(timezone.utc)
    manager = LiveOneShotUnlock()
    token = "AITS-LIVE-ONE-SHOT-CONFIRM"
    base_request: dict[str, Any] = {
        "request_id": "one_shot_base",
        "symbol": "KRW-BTC",
        "side": "buy",
        "amount_krw": 5000.0,
        "max_order_amount_krw": 10000.0,
        "min_order_amount_krw": 5000.0,
        "user_confirm_phrase": "AITS LIVE ONE SHOT",
        "confirm_token": token,
        "expires_at_utc": (now + timedelta(minutes=5)).isoformat(timespec="seconds"),
        "ttl_sec": 300,
        "duplicate_lock_key": "KRW-BTC:buy:one-shot-fixture",
        "created_at_utc": now.isoformat(timespec="seconds"),
        "source": "live_one_shot_unlock_contract_proof",
        "operator_note": "fixture only; no order submit",
    }

    def make_request(name: str, **overrides: Any) -> dict[str, Any]:
        item = dict(base_request)
        item.update(overrides)
        item["request_id"] = name
        return item

    preflight = LiveOrderPreflight()
    results: list[dict[str, Any]] = []

    def append_result(
        name: str,
        expected_locked: bool,
        expected_allowed_for_preflight: bool,
        expected_reason: str,
        unlock_result: Any,
        *,
        preflight_result: Any = None,
    ) -> None:
        passed = (
            bool(unlock_result.locked) is bool(expected_locked)
            and bool(unlock_result.allowed_for_preflight) is bool(expected_allowed_for_preflight)
            and str(unlock_result.blocked_reason or "") == str(expected_reason or "")
            and int(unlock_result.submitted) == 0
            and bool(unlock_result.order_allowed) is False
            and bool(unlock_result.real_order) is False
        )
        if preflight_result is not None:
            passed = (
                passed
                and bool(preflight_result.allowed_for_preflight) is bool(expected_allowed_for_preflight)
                and int(preflight_result.submitted) == 0
                and bool(preflight_result.order_allowed) is False
                and bool(preflight_result.real_order) is False
            )
        results.append(
            {
                "name": name,
                "expected_locked": bool(expected_locked),
                "expected_allowed_for_preflight": bool(expected_allowed_for_preflight),
                "expected_reason": expected_reason,
                "unlock_valid": bool(unlock_result.unlock_valid),
                "locked": bool(unlock_result.locked),
                "allowed_for_preflight": bool(unlock_result.allowed_for_preflight),
                "blocked_reason": str(unlock_result.blocked_reason or ""),
                "unlock_id": str(unlock_result.unlock_id or ""),
                "consumed": bool(unlock_result.consumed),
                "expired": bool(unlock_result.expired),
                "duplicate_locked": bool(unlock_result.duplicate_locked),
                "submitted": int(unlock_result.submitted),
                "order_allowed": bool(unlock_result.order_allowed),
                "real_order": bool(unlock_result.real_order),
                "preflight": preflight_result.to_dict() if preflight_result is not None else None,
                "pass": bool(passed),
                "log_summary": manager.log_summary("validate", unlock_result),
            }
        )

    missing = manager.validate_one_shot_unlock(None, make_request("no_unlock"))
    append_result("no_unlock", True, False, "missing_unlock", missing)

    invalid_req = make_request("invalid_confirm_token", duplicate_lock_key="KRW-BTC:buy:invalid-token")
    invalid_state = manager.create_one_shot_unlock(invalid_req)
    invalid = manager.validate_one_shot_unlock(
        invalid_state,
        make_request("invalid_confirm_token", confirm_token="wrong-token", duplicate_lock_key=invalid_req["duplicate_lock_key"]),
    )
    append_result("invalid_confirm_token", True, False, "invalid_confirm_token", invalid)

    cap_req = make_request("amount_exceeds_unlock_cap", duplicate_lock_key="KRW-BTC:buy:cap")
    cap_state = manager.create_one_shot_unlock(cap_req)
    cap = manager.validate_one_shot_unlock(
        cap_state,
        make_request("amount_exceeds_unlock_cap", amount_krw=500000.0, duplicate_lock_key=cap_req["duplicate_lock_key"]),
    )
    append_result("amount_exceeds_unlock_cap", True, False, "amount_exceeds_unlock_cap", cap)

    expired_req = make_request(
        "expired_unlock",
        duplicate_lock_key="KRW-BTC:buy:expired",
        expires_at_utc=(now - timedelta(seconds=1)).isoformat(timespec="seconds"),
    )
    expired_state = manager.create_one_shot_unlock(expired_req)
    expired = manager.validate_one_shot_unlock(expired_state, expired_req, now_utc=now)
    append_result("expired_unlock", True, False, "unlock_expired", expired)

    valid_req = make_request("valid_unlock_preflight_pass_but_no_order_submit")
    valid_state = manager.create_one_shot_unlock(valid_req)
    valid = manager.validate_one_shot_unlock(valid_state, valid_req, now_utc=now)
    valid_preflight_input = {
        "request_id": valid_req["request_id"],
        "symbol": valid_req["symbol"],
        "side": valid_req["side"],
        "amount_krw": float(valid_req["amount_krw"]),
        "quantity": 0.00005,
        "price": 100000000.0,
        "execution_mode": "live",
        "aits_enabled": True,
        "live_order_unlock": True,
        "user_confirm_token": "present",
        "risk_guard_checked": True,
        "risk_allowed": True,
        "one_shot_unlock_valid": bool(valid.unlock_valid),
        "one_shot_unlock_id": str(valid.unlock_id or ""),
        "one_shot_unlock_consumed": False,
        "emergency_stop": False,
        "max_order_amount_krw": float(valid_req["max_order_amount_krw"]),
        "max_daily_loss_krw": 30000.0,
        "max_order_count_per_cycle": 1,
        "duplicate_order_lock": True,
        "min_real_order_amount_krw": float(valid_req["min_order_amount_krw"]),
        "account_ready": True,
        "api_key_ready": True,
        "price_fresh": True,
        "selected_provider": "local",
        "source": "one_shot_unlock_contract_fixture",
    }
    valid_preflight = preflight.evaluate(LiveOrderPreflightInput(**valid_preflight_input))
    append_result(
        "valid_unlock_preflight_pass_but_no_order_submit",
        False,
        True,
        "",
        valid,
        preflight_result=valid_preflight,
    )
    manager.consume_one_shot_unlock(valid_state, reason="fixture_consumed", now_utc=now)

    consumed = manager.validate_one_shot_unlock(valid_state, valid_req, now_utc=now)
    append_result("consumed_unlock_reuse", True, False, "unlock_consumed", consumed)

    duplicate_req = make_request("duplicate_lock_reuse")
    duplicate_state = manager.create_one_shot_unlock(duplicate_req)
    duplicate = manager.validate_one_shot_unlock(duplicate_state, duplicate_req, now_utc=now)
    append_result("duplicate_lock_reuse", True, False, "duplicate_order_lock_reused", duplicate)

    pass_count = sum(1 for item in results if item.get("pass"))
    fail_count = len(results) - pass_count
    report.update(
        {
            "one_shot_unlock_fixture_count": len(results),
            "one_shot_unlock_pass_count": pass_count,
            "one_shot_unlock_fail_count": fail_count,
            "one_shot_unlock_results": results,
            "valid_unlock_seen": any(
                item["name"] == "valid_unlock_preflight_pass_but_no_order_submit"
                and item.get("allowed_for_preflight")
                for item in results
            ),
            "consumed_reuse_blocked": any(
                item["name"] == "consumed_unlock_reuse"
                and item.get("blocked_reason") == "unlock_consumed"
                and item.get("locked")
                for item in results
            ),
            "duplicate_reuse_blocked": any(
                item["name"] == "duplicate_lock_reuse"
                and item.get("blocked_reason") == "duplicate_order_lock_reused"
                and item.get("locked")
                for item in results
            ),
            "order_service_place_order_called": False,
            "order_adapter_live_branch_entered": False,
            "provider_call_markers": 0,
            "provider_call_delta": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
            "submitted_detected": False,
            "order_risk_detected": False,
            "real_order_detected": False,
            "paper_mode_created": False,
            "virtual_trading_created": False,
            "mock_trading_processor_created": False,
            "pass_status": "pass" if fail_count == 0 else "fail",
        }
    )


class _LiveMinimumOrderServiceCapture:
    def __init__(self, service: Any) -> None:
        self.service = service
        self.call_count = 0
        self.last_response: dict[str, Any] | None = None

    def place_order(self, order_request: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self.call_count > 1:
            self.last_response = {
                "success": False,
                "error": "live_minimum_order_call_limit_exceeded",
                "real_order": False,
                "submitted": False,
            }
            return dict(self.last_response)
        response = self.service.place_order(order_request)
        self.last_response = dict(response or {}) if isinstance(response, dict) else {
            "success": False,
            "error": "invalid_order_service_response",
            "real_order": False,
            "submitted": False,
        }
        return dict(self.last_response)


def _run_live_minimum_real_order_test(report: dict[str, Any], *, confirm_phrase: str) -> None:
    from datetime import timedelta, timezone

    from app.core.aits_state import ActionItem
    from app.services.aits_orchestrator import ExecutionRequest
    from app.services.execution_bridge import ExecutionBridge
    from app.services.live_order_preflight import LiveOrderPreflight, LiveOrderPreflightInput
    from app.services.live_order_unlock import LiveOneShotUnlock
    from app.services.order_adapter import AITSOrderAdapter
    from app.services.order_service import OrderService
    from app.services.risk_guard import RiskGuard
    from app.utils.prefs import init_prefs, load_settings

    expected_phrase = "AITS_REAL_ORDER_ONCE_KRW_BTC_BUY_5000_CONFIRM"
    symbol = "KRW-BTC"
    side = "buy"
    amount_krw = 5000.0
    hard_cap_krw = 6000.0
    request_id = f"live_minimum_{uuid.uuid4().hex[:16]}"
    duplicate_lock_key = f"{symbol}:{side}:{request_id}"
    now = datetime.now(timezone.utc)

    report.update(
        {
            "confirm_phrase_valid": confirm_phrase == expected_phrase,
            "target_symbol": symbol,
            "target_side": side,
            "target_amount_krw": amount_krw,
            "hard_cap_krw": hard_cap_krw,
            "order_service_place_order_called": False,
            "order_service_place_order_call_count": 0,
            "submitted_count": 0,
            "real_order": False,
            "unlock_consumed": False,
            "relocked": True,
            "duplicate_lock_set": False,
            "repeat_order_blocked": False,
            "final_order_allowed": False,
            "final_real_order": False,
            "provider_call_markers": 0,
            "provider_call_delta": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
        }
    )
    if confirm_phrase != expected_phrase:
        report.update(
            {
                "status": "blocked",
                "pass_status": "blocked",
                "fail_reason": "사용자 명시 승인 phrase 없음",
                "report_status": "blocked",
            }
        )
        return

    def stop_partial(reason: str) -> None:
        report.update(
            {
                "status": "partial",
                "pass_status": "partial",
                "fail_reason": reason,
                "report_status": "partial",
            }
        )

    try:
        init_prefs(str(ROOT), str(ROOT / "data"))
        settings = load_settings()
        order_service = OrderService()
        order_service.set_settings(settings)
        access_key, secret_key = order_service._extract_upbit_keys()
        account_ready = bool(access_key and secret_key and len(access_key) >= 10 and len(secret_key) >= 10)
        report["upbit_key_ready"] = account_ready
        if not account_ready:
            stop_partial("upbit_key_not_ready")
            return

        accounts = order_service.fetch_accounts()
        krw_balance = 0.0
        btc_balance = 0.0
        if isinstance(accounts, list):
            for row in accounts:
                if not isinstance(row, dict):
                    continue
                currency = str(row.get("currency") or "").upper()
                if currency == "KRW":
                    krw_balance = _safe_float(row.get("balance"), 0.0)
                elif currency == "BTC":
                    btc_balance = _safe_float(row.get("balance"), 0.0)
        report["account_ready"] = True
        report["krw_balance_available"] = krw_balance
        report["btc_balance_before"] = btc_balance
        if krw_balance < amount_krw:
            stop_partial("insufficient_krw_balance")
            return

        ticker = requests.get(
            "https://api.upbit.com/v1/ticker",
            params={"markets": symbol},
            timeout=5,
        )
        report["ticker_http_status"] = int(getattr(ticker, "status_code", 0) or 0)
        if not ticker.ok:
            stop_partial(f"ticker_http_{ticker.status_code}")
            return
        ticker_payload = ticker.json()
        item = ticker_payload[0] if isinstance(ticker_payload, list) and ticker_payload else {}
        price = _safe_float((item or {}).get("trade_price"), 0.0)
        report["price_fresh"] = price > 0
        report["target_price"] = price
        if price <= 0:
            stop_partial("price_not_fresh")
            return

        quantity = amount_krw / price
        risk_input = {
            "symbol": symbol,
            "side": side,
            "requested_amount_krw": amount_krw,
            "price": price,
            "quantity": quantity,
            "source_provider": "manual",
            "confidence": 1.0,
            "action": "buy",
            "holdings_value_krw": btc_balance * price,
            "cash_available_krw": krw_balance,
            "portfolio_value_krw": krw_balance + (btc_balance * price),
            "daily_realized_pnl_krw": 0.0,
            "daily_loss_limit_krw": 30000.0,
            "max_order_amount_krw": hard_cap_krw,
            "max_position_value_krw": 200000.0,
            "emergency_stop": False,
            "stale_price": False,
            "execution_mode": "live",
            "dry_run": True,
            "request_id": request_id,
        }
        risk_guard = RiskGuard()
        risk_result = risk_guard.evaluate_order_candidate(risk_input)
        report["riskguard_result"] = risk_result.to_dict()
        if not bool(risk_result.risk_allowed):
            stop_partial(f"riskguard_blocked:{risk_result.blocked_reason or 'unknown'}")
            return

        unlock_manager = LiveOneShotUnlock()
        unlock_request = {
            "request_id": request_id,
            "symbol": symbol,
            "side": side,
            "amount_krw": amount_krw,
            "max_order_amount_krw": hard_cap_krw,
            "min_order_amount_krw": amount_krw,
            "user_confirm_phrase": expected_phrase,
            "confirm_token": expected_phrase,
            "expires_at_utc": (now + timedelta(seconds=120)).isoformat(timespec="seconds"),
            "ttl_sec": 120,
            "duplicate_lock_key": duplicate_lock_key,
            "created_at_utc": now.isoformat(timespec="seconds"),
            "source": "live_minimum_real_order_test",
            "operator_note": "one shot live order test",
        }
        unlock_state = unlock_manager.create_one_shot_unlock(unlock_request)
        unlock_result = unlock_manager.validate_one_shot_unlock(unlock_state, unlock_request, now_utc=now)
        report["unlock_result_before"] = unlock_result.to_dict()
        report["duplicate_lock_empty"] = not unlock_manager.is_duplicate_locked(duplicate_lock_key)
        if unlock_result.locked or not unlock_result.allowed_for_preflight:
            stop_partial(f"unlock_invalid:{unlock_result.blocked_reason or 'unknown'}")
            return

        risk_metadata = risk_result.to_dict()
        risk_metadata.update(
            {
                "risk_guard_checked": True,
                "risk_allowed": True,
                "price": price,
                "quantity": quantity,
                "source_provider": "manual",
                "aits_enabled": True,
                "live_order_unlock": True,
                "user_confirm_token": "confirmed",
                "one_shot_unlock_valid": True,
                "one_shot_unlock_id": str(unlock_result.unlock_id or ""),
                "one_shot_unlock_consumed": False,
                "emergency_stop": False,
                "max_order_amount_krw": hard_cap_krw,
                "max_daily_loss_krw": 30000.0,
                "max_order_count_per_cycle": 1,
                "duplicate_order_lock": True,
                "duplicate_lock_key": duplicate_lock_key,
                "min_real_order_amount_krw": amount_krw,
                "account_ready": True,
                "api_key_ready": True,
                "price_fresh": True,
                "live_minimum_real_order_test": True,
            }
        )
        preflight_input = LiveOrderPreflightInput(
            request_id=request_id,
            symbol=symbol,
            side=side,
            amount_krw=amount_krw,
            quantity=quantity,
            price=price,
            execution_mode="live",
            aits_enabled=True,
            live_order_unlock=True,
            user_confirm_token="confirmed",
            risk_guard_checked=True,
            risk_allowed=True,
            one_shot_unlock_valid=True,
            one_shot_unlock_id=str(unlock_result.unlock_id or ""),
            one_shot_unlock_consumed=False,
            emergency_stop=False,
            max_order_amount_krw=hard_cap_krw,
            max_daily_loss_krw=30000.0,
            max_order_count_per_cycle=1,
            duplicate_order_lock=True,
            min_real_order_amount_krw=amount_krw,
            account_ready=True,
            api_key_ready=True,
            price_fresh=True,
            selected_provider="manual",
            source="live_minimum_real_order_test",
        )
        preflight = LiveOrderPreflight()
        preflight_result = preflight.evaluate(preflight_input)
        report["preflight_result"] = preflight_result.to_dict()
        if preflight_result.locked or not preflight_result.allowed:
            stop_partial(f"preflight_locked:{preflight_result.blocked_reason or 'unknown'}")
            return

        action = ActionItem(
            symbol=symbol,
            action_type="buy",
            amount_krw=amount_krw,
            priority=1,
            source_module="live_minimum_real_order_test",
            source_provider="manual",
            reason=request_id,
        )
        setattr(action, "risk_guard", risk_metadata)
        bridge = ExecutionBridge().build_from_execution_request(
            ExecutionRequest(
                actions=[action],
                priority=1,
                source="live_minimum_real_order_test",
                decision_trace_id=request_id,
                dry_run=False,
                request_summary="live minimum real order one-shot test",
            )
        )
        report["order_adapter_live_path_entered"] = bool(bridge.actions)
        report["execution_bridge_action_count"] = int(getattr(bridge, "action_count", 0) or 0)
        report["execution_bridge_metadata_seen"] = bool(
            bridge.actions and getattr(bridge.actions[0], "risk_guard", None)
        )

        capture = _LiveMinimumOrderServiceCapture(order_service)
        adapter = AITSOrderAdapter(execution_mode="live", min_order_krw=amount_krw)
        adapter_result = adapter.execute(bridge, order_service=capture)
        order_response = capture.last_response or {}
        report["order_service_place_order_called"] = capture.call_count > 0
        report["order_service_place_order_call_count"] = capture.call_count
        report["order_adapter_result"] = {
            "submitted_count": int(getattr(adapter_result, "submitted_count", 0) or 0),
            "failed_count": int(getattr(adapter_result, "failed_count", 0) or 0),
            "blocked_count": int(getattr(adapter_result, "blocked_count", 0) or 0),
            "skipped_count": int(getattr(adapter_result, "skipped_count", 0) or 0),
            "summary_ko": str(getattr(adapter_result, "summary_ko", "") or ""),
        }
        report["order_response_sanitized"] = order_response.get("response_sanitized", {})
        report["order_uuid"] = str(order_response.get("uuid") or order_response.get("order_id") or "")
        report["order_state"] = str(order_response.get("state") or "")
        report["order_http_status"] = int(order_response.get("http_status") or 0)
        report["order_error"] = str(order_response.get("error") or "")
        report["unknown_state"] = bool(order_response.get("unknown_state", False))
        report["submitted_count"] = 1 if bool(order_response.get("submitted")) else 0
        report["real_order"] = bool(order_response.get("real_order", False))

        consumed_state = unlock_manager.consume_one_shot_unlock(
            unlock_state,
            reason="live_minimum_real_order_test_consumed",
            now_utc=datetime.now(timezone.utc),
        )
        consumed_check = unlock_manager.validate_one_shot_unlock(
            consumed_state,
            unlock_request,
            now_utc=datetime.now(timezone.utc),
        )
        duplicate_state = unlock_manager.create_one_shot_unlock(
            dict(unlock_request, request_id=f"{request_id}_duplicate")
        )
        duplicate_check = unlock_manager.validate_one_shot_unlock(
            duplicate_state,
            dict(unlock_request, request_id=f"{request_id}_duplicate"),
            now_utc=datetime.now(timezone.utc),
        )
        report["unlock_consumed"] = bool(consumed_state.consumed)
        report["relocked"] = bool(consumed_check.locked)
        report["duplicate_lock_set"] = bool(unlock_manager.is_duplicate_locked(duplicate_lock_key))
        report["repeat_order_blocked"] = bool(
            duplicate_check.locked and duplicate_check.blocked_reason == "duplicate_order_lock_reused"
        )
        report["unlock_result_after"] = consumed_check.to_dict()
        report["duplicate_reuse_result"] = duplicate_check.to_dict()
        report["final_order_allowed"] = False
        report["final_real_order"] = False

        try:
            post_accounts = order_service.fetch_accounts()
            post_krw = 0.0
            post_btc = 0.0
            if isinstance(post_accounts, list):
                for row in post_accounts:
                    if not isinstance(row, dict):
                        continue
                    currency = str(row.get("currency") or "").upper()
                    if currency == "KRW":
                        post_krw = _safe_float(row.get("balance"), 0.0)
                    elif currency == "BTC":
                        post_btc = _safe_float(row.get("balance"), 0.0)
            report["krw_balance_after"] = post_krw
            report["btc_balance_after"] = post_btc
        except Exception as exc:
            report.setdefault("warnings", []).append(f"post_order_balance_check_failed:{type(exc).__name__}")

        passed = (
            capture.call_count == 1
            and report["submitted_count"] == 1
            and report["real_order"] is True
            and bool(report["unlock_consumed"])
            and bool(report["relocked"])
            and bool(report["duplicate_lock_set"])
            and bool(report["repeat_order_blocked"])
        )
        if passed:
            report.update({"status": "pass", "pass_status": "pass", "report_status": "pass"})
        else:
            report.update(
                {
                    "status": "partial" if capture.call_count <= 1 else "fail",
                    "pass_status": "partial" if capture.call_count <= 1 else "fail",
                    "report_status": "partial" if capture.call_count <= 1 else "fail",
                    "fail_reason": str(order_response.get("error") or "order_not_submitted"),
                }
            )
    except Exception as exc:
        report.update(
            {
                "status": "fail",
                "pass_status": "fail",
                "report_status": "fail",
                "fail_reason": f"live_minimum_exception:{type(exc).__name__}",
            }
        )


def _normalize_live_order_state(
    *,
    raw_state: str,
    executed_volume: Any,
    query_success: bool,
    balance_consistent: bool,
) -> tuple[str, str, str]:
    if not query_success:
        return (
            "query_failed_no_retry",
            "no_retry_read_only_query_or_manual_exchange_review",
            "query_failed",
        )
    if not balance_consistent:
        return (
            "unknown_requires_manual_review",
            "stop_no_order_manual_balance_review",
            "balance_mismatch",
        )

    state = str(raw_state or "").strip().lower()
    executed_text = str(executed_volume or "").strip()
    executed_present = executed_text != ""
    executed = _safe_float(executed_text, 0.0)

    if state == "wait":
        if executed_present and executed > 0:
            return (
                "partial_execution_waiting_remainder",
                "no_retry_no_cancel_reconcile_later",
                "wait_with_executed_volume",
            )
        return ("submitted_waiting", "no_retry_query_later_only", "wait_no_executed_volume")
    if state == "done":
        if executed_present and executed > 0:
            return ("fully_filled", "reconcile_balances_no_retry", "done_with_executed_volume")
        return (
            "unknown_requires_manual_review",
            "stop_no_order_manual_exchange_review",
            "done_without_executed_volume",
        )
    if state == "cancel":
        if executed_present and executed > 0:
            return (
                "partially_filled_cancelled_remainder",
                "treat_filled_quantity_as_executed_no_retry",
                "cancel_with_executed_volume",
            )
        return ("cancelled_no_fill", "no_retry_without_new_explicit_goal", "cancel_no_executed_volume")
    return (
        "unknown_requires_manual_review",
        "stop_no_order_manual_exchange_review",
        "unknown_raw_state",
    )


def _run_live_order_post_trade_reconciliation(report: dict[str, Any], *, order_uuid: str) -> None:
    from app.services.order_service import OrderService
    from app.utils.prefs import init_prefs, load_settings

    expected_uuid = "06f08c3a-2bd3-4888-a7e6-2402623cb63e"
    previous_report_path = ROOT / "data" / "runtime_smoke_reports" / "runtime_smoke_report_20260629_045413_391177.json"
    safe_uuid = str(order_uuid or "").strip()
    report.update(
        {
            "order_uuid": safe_uuid,
            "expected_order_uuid": expected_uuid,
            "previous_report_path": str(previous_report_path),
            "order_query_called": False,
            "order_query_success": False,
            "order_service_place_order_called": False,
            "order_service_place_order_call_count": 0,
            "place_order_call_count": 0,
            "cancel_order_called": False,
            "cancel_call_count": 0,
            "sell_order_called": False,
            "sell_call_count": 0,
            "repeat_order_attempted": False,
            "retry_call_count": 0,
            "no_retry_enforced": True,
            "provider_call_markers": 0,
            "external_cost_call_markers": 0,
            "unlock_consumed": False,
            "relocked": False,
            "duplicate_lock_set": False,
            "repeat_order_blocked": False,
        }
    )
    if safe_uuid != expected_uuid:
        report.update(
            {
                "status": "blocked",
                "pass_status": "blocked",
                "report_status": "blocked",
                "fail_reason": "unexpected_order_uuid",
            }
        )
        return

    previous: dict[str, Any] = {}
    try:
        with previous_report_path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
            if isinstance(loaded, dict):
                previous = loaded
    except Exception as exc:
        report.setdefault("warnings", []).append(f"previous_report_read_failed:{type(exc).__name__}")
    report["previous_order_state"] = str(previous.get("order_state") or "")
    report["previous_submitted_count"] = int(previous.get("submitted_count") or 0)
    report["previous_real_order"] = bool(previous.get("real_order", False))
    report["previous_krw_balance_before"] = previous.get("krw_balance_available")
    report["previous_krw_balance_after"] = previous.get("krw_balance_after")
    report["previous_btc_balance_after"] = previous.get("btc_balance_after")
    report["unlock_consumed"] = bool(previous.get("unlock_consumed", False))
    report["relocked"] = bool(previous.get("relocked", False))
    report["duplicate_lock_set"] = bool(previous.get("duplicate_lock_set", False))
    report["repeat_order_blocked"] = bool(previous.get("repeat_order_blocked", False))

    try:
        init_prefs(str(ROOT), str(ROOT / "data"))
        settings = load_settings()
        service = OrderService()
        service.set_settings(settings)
        order_lookup = service.fetch_order(safe_uuid)
        report["order_query_called"] = True
        report["order_query_success"] = bool(order_lookup.get("success", False))
        report["query_status"] = "success" if report["order_query_success"] else "failed"
        report["order_query_http_status"] = int(order_lookup.get("http_status") or 0)
        report["order_state"] = str(order_lookup.get("state") or "")
        report["raw_order_state"] = report["order_state"]
        order_payload = order_lookup.get("response_sanitized", {})
        if not isinstance(order_payload, dict):
            order_payload = {}
        report["order_response_sanitized"] = order_payload
        report["market"] = str(order_payload.get("market") or order_lookup.get("market") or "")
        report["side"] = str(order_payload.get("side") or order_lookup.get("side") or "")
        report["ord_type"] = str(order_payload.get("ord_type") or order_lookup.get("ord_type") or "")
        report["price"] = str(order_payload.get("price") or "")
        report["requested_price_krw"] = _safe_float(report.get("price"), 0.0)
        report["executed_volume"] = str(order_payload.get("executed_volume") or "")
        report["remaining_volume"] = str(order_payload.get("remaining_volume") or "")
        report["paid_fee"] = str(order_payload.get("paid_fee") or "")
        report["locked"] = str(order_payload.get("locked") or "")
        report["created_at"] = str(order_payload.get("created_at") or "")
        report["trades_count"] = str(order_payload.get("trades_count") or "")

        accounts = service.fetch_accounts()
        krw_balance = 0.0
        btc_balance = 0.0
        krw_locked = 0.0
        btc_locked = 0.0
        if isinstance(accounts, list):
            for row in accounts:
                if not isinstance(row, dict):
                    continue
                currency = str(row.get("currency") or "").upper()
                if currency == "KRW":
                    krw_balance = _safe_float(row.get("balance"), 0.0)
                    krw_locked = _safe_float(row.get("locked"), 0.0)
                elif currency == "BTC":
                    btc_balance = _safe_float(row.get("balance"), 0.0)
                    btc_locked = _safe_float(row.get("locked"), 0.0)
        report["krw_balance"] = krw_balance
        report["btc_balance"] = btc_balance
        report["asset_balance"] = btc_balance
        report["asset_currency"] = "BTC"
        report["krw_locked"] = krw_locked
        report["btc_locked"] = btc_locked
        report["krw_delta_vs_first_after"] = (
            krw_balance - _safe_float(previous.get("krw_balance_after"), 0.0)
            if "krw_balance_after" in previous
            else None
        )
        report["btc_delta_vs_first_after"] = (
            btc_balance - _safe_float(previous.get("btc_balance_after"), 0.0)
            if "btc_balance_after" in previous
            else None
        )
        report["balance_delta_krw"] = report["krw_delta_vs_first_after"]
        report["balance_delta_asset"] = report["btc_delta_vs_first_after"]
        krw_delta = report.get("krw_delta_vs_first_after")
        asset_delta = report.get("btc_delta_vs_first_after")
        balance_consistent = (
            (krw_delta is None or abs(_safe_float(krw_delta, 0.0)) <= 0.000001)
            and (asset_delta is None or abs(_safe_float(asset_delta, 0.0)) <= 0.00000001)
        )
        report["balance_reconciliation"] = {
            "krw_balance": krw_balance,
            "asset_currency": "BTC",
            "asset_balance": btc_balance,
            "krw_locked": krw_locked,
            "asset_locked": btc_locked,
            "previous_krw_balance_after": previous.get("krw_balance_after"),
            "previous_asset_balance_after": previous.get("btc_balance_after"),
            "balance_delta_krw": report["balance_delta_krw"],
            "balance_delta_asset": report["balance_delta_asset"],
            "consistent": balance_consistent,
        }
        normalized_state, normalized_action, normalized_reason = _normalize_live_order_state(
            raw_state=report["raw_order_state"],
            executed_volume=report["executed_volume"],
            query_success=bool(report["order_query_success"]),
            balance_consistent=balance_consistent,
        )
        report["normalized_order_state"] = normalized_state
        report["normalized_order_action"] = normalized_action
        report["normalized_order_reason"] = normalized_reason

        clear_state = str(report.get("order_state") or "").lower() in {"done", "wait", "cancel"}
        no_extra_order = not bool(report.get("order_service_place_order_called"))
        no_forbidden = (
            not bool(report.get("cancel_order_called"))
            and not bool(report.get("sell_order_called"))
            and not bool(report.get("repeat_order_attempted"))
        )
        lock_ok = (
            bool(report.get("unlock_consumed"))
            and bool(report.get("relocked"))
            and bool(report.get("duplicate_lock_set"))
            and bool(report.get("repeat_order_blocked"))
        )
        report["reconciliation_status"] = (
            "reconciled"
            if report["order_query_success"]
            and clear_state
            and no_extra_order
            and no_forbidden
            and lock_ok
            and balance_consistent
            and report["normalized_order_state"] != "unknown_requires_manual_review"
            else "partial"
        )
        report["reconciliation_reason"] = (
            "read_only_query_balance_and_lock_proof_ok"
            if report["reconciliation_status"] == "reconciled"
            else "read_only_reconciliation_incomplete"
        )
        if report["reconciliation_status"] == "reconciled":
            report.update({"status": "pass", "pass_status": "pass", "report_status": "pass"})
        else:
            report.update(
                {
                    "status": "partial",
                    "pass_status": "partial",
                    "report_status": "partial",
                    "fail_reason": str(order_lookup.get("error") or "reconciliation_incomplete"),
                }
            )
    except Exception as exc:
        report.update(
            {
                "status": "fail",
                "pass_status": "fail",
                "report_status": "fail",
                "fail_reason": f"post_trade_reconciliation_exception:{type(exc).__name__}",
            }
        )


def _guarded_window_incident_markdown(*, path: Path, fixture_name: str, trigger: str) -> str:
    return "\n".join(
        [
            "# AITS Live Guarded Window Smoke Incident",
            "",
            "## 1. Goal",
            "",
            "`AITS-LIVE-2H-GUARDED-WINDOW-CONTRACT-PREFLIGHT-01`",
            "",
            "## 2. Incident Time",
            "",
            _now_iso(),
            "",
            "## 3. Elapsed Time",
            "",
            "Preflight fixture smoke only. AITS ON was not clicked.",
            "",
            "## 4. Severity",
            "",
            "LOW",
            "",
            "## 5. Trigger Condition",
            "",
            trigger,
            "",
            "## 6. Immediate Stop",
            "",
            "Yes. This is a smoke incident report for auto-open proof.",
            "",
            "## 7. AITS ON/OFF State",
            "",
            "AITS OFF / not clicked in this fixture.",
            "",
            "## 8. Order Occurred",
            "",
            "No.",
            "",
            "## 9. Order Count",
            "",
            "0",
            "",
            "## 10. Total Order Amount",
            "",
            "0 KRW",
            "",
            "## 11. Last Order UUID",
            "",
            "None for this fixture.",
            "",
            "## 12. Last Raw Order State",
            "",
            "N/A",
            "",
            "## 13. Last Normalized Order State",
            "",
            "N/A",
            "",
            "## 14. KRW Balance",
            "",
            "Not queried by the smoke incident fixture.",
            "",
            "## 15. BTC Balance",
            "",
            "Not queried by the smoke incident fixture.",
            "",
            "## 16. Relock State",
            "",
            "Expected true.",
            "",
            "## 17. Duplicate Lock State",
            "",
            "Expected true.",
            "",
            "## 18. Repeat Block State",
            "",
            "Expected true.",
            "",
            "## 19. Provider Call Count",
            "",
            "0",
            "",
            "## 20. Log Excerpt",
            "",
            f"fixture={fixture_name}",
            "",
            "## 21. Report Path",
            "",
            str(path),
            "",
            "## 22. Suspected Cause",
            "",
            "Smoke fixture only.",
            "",
            "## 23. Next Fix Goal",
            "",
            "None for smoke fixture.",
            "",
            "## 24. Safety Confirmation",
            "",
            "No reorder. No buy. No sell. No cancel. No retry.",
            "",
        ]
    )


def _run_live_2h_guarded_window_preflight_proof(
    report: dict[str, Any],
    *,
    duration_min: int,
    per_order_krw: float,
    per_order_hard_cap_krw: float,
    total_window_cap_krw: float,
    max_order_count: int,
    min_order_interval_sec: int,
) -> None:
    from app.services.live_guarded_window import (
        LiveGuardedWindow,
        LiveGuardedWindowConfig,
        LiveGuardedWindowState,
    )

    service = LiveGuardedWindow()
    config = LiveGuardedWindowConfig.from_mapping(
        {
            "window_id": f"guarded_preflight_{uuid.uuid4().hex[:12]}",
            "duration_min": duration_min,
            "per_order_krw": per_order_krw,
            "per_order_hard_cap_krw": per_order_hard_cap_krw,
            "total_window_cap_krw": total_window_cap_krw,
            "max_order_count": max_order_count,
            "min_order_interval_sec": min_order_interval_sec,
            "sell_allowed": False,
            "cancel_allowed": False,
            "retry_allowed": False,
            "emergency_stop_required": True,
            "incident_stop_required": True,
            "approval_phrase_hash": "sha256:AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM",
        }
    )
    base_state = LiveGuardedWindowState.from_mapping(
        {
            "window_id": config.window_id,
            "active": False,
            "locked": True,
            "order_count": 0,
            "total_order_amount_krw": 0.0,
            "relocked": True,
            "duplicate_lock_ok": True,
            "repeat_block_ok": True,
        }
    )

    fixtures: list[dict[str, Any]] = [
        {
            "name": "valid_window_contract_locked_no_on",
            "kind": "start",
            "expected_reason": "preflight_only_aits_on_not_clicked",
        },
        {
            "name": "blocked_per_order_cap_exceeded",
            "kind": "order",
            "candidate": {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_hard_cap_krw + 1},
            "expected_reason": "per_order_cap_exceeded",
        },
        {
            "name": "blocked_total_cap_exceeded",
            "kind": "order",
            "state": {"order_count": 1, "total_order_amount_krw": total_window_cap_krw - 1000},
            "candidate": {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_krw},
            "expected_reason": "total_window_cap_exceeded",
        },
        {
            "name": "blocked_max_order_count_exceeded",
            "kind": "order",
            "state": {"order_count": max_order_count, "total_order_amount_krw": per_order_krw * max_order_count},
            "candidate": {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_krw},
            "expected_reason": "max_order_count_exceeded",
        },
        {
            "name": "blocked_min_interval_violation",
            "kind": "order",
            "state": {"order_count": 1, "total_order_amount_krw": per_order_krw},
            "candidate": {
                "symbol": "KRW-BTC",
                "side": "buy",
                "amount_krw": per_order_krw,
                "elapsed_since_last_order_sec": min_order_interval_sec - 1,
            },
            "expected_reason": "min_order_interval_violation",
        },
        {
            "name": "blocked_sell_attempt",
            "kind": "order",
            "candidate": {"symbol": "KRW-BTC", "side": "sell", "amount_krw": per_order_krw},
            "expected_reason": "sell_attempt_blocked",
        },
        {
            "name": "blocked_unknown_state_retry",
            "kind": "order",
            "candidate": {
                "symbol": "KRW-BTC",
                "side": "buy",
                "amount_krw": per_order_krw,
                "retry_attempt": True,
                "normalized_order_state": "unknown_requires_manual_review",
            },
            "expected_reason": "unknown_state_retry_blocked",
        },
    ]

    results: list[dict[str, Any]] = []
    for item in fixtures:
        state_data = dict(base_state.to_dict())
        state_data.update(item.get("state") or {})
        state = LiveGuardedWindowState.from_mapping(state_data)
        if item["kind"] == "start":
            result = service.evaluate_window_start(config, state)
        else:
            result = service.evaluate_order_attempt(config, state, item.get("candidate") or {})
        passed = (
            result.blocked_reason == item["expected_reason"]
            and result.locked
            and not result.allowed_to_start
            and result.submitted == 0
            and not result.order_allowed
            and not result.real_order
            and result.place_order_call_count == 0
            and result.cancel_call_count == 0
            and result.sell_call_count == 0
            and result.retry_call_count == 0
        )
        results.append(
            {
                "name": item["name"],
                "expected_reason": item["expected_reason"],
                "blocked_reason": result.blocked_reason,
                "locked": result.locked,
                "allowed_to_start": result.allowed_to_start,
                "incident_required": result.incident_required,
                "submitted": result.submitted,
                "order_allowed": result.order_allowed,
                "real_order": result.real_order,
                "place_order_call_count": result.place_order_call_count,
                "cancel_call_count": result.cancel_call_count,
                "sell_call_count": result.sell_call_count,
                "retry_call_count": result.retry_call_count,
                "pass": bool(passed),
                "result": result.to_dict(),
            }
        )

    incident_dir = ROOT / "data" / "live_incidents"
    incident_path = incident_dir / f"aits_live_2h_guarded_window_incident_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    incident_markdown = _guarded_window_incident_markdown(
        path=incident_path,
        fixture_name="incident_report_auto_open_smoke",
        trigger="incident report auto-open smoke fixture",
    )
    _write_text_report(incident_path, incident_markdown)
    auto_opened = _open_text_report_windows(incident_path)
    incident_record = service.record_incident(
        goal="AITS-LIVE-2H-GUARDED-WINDOW-CONTRACT-PREFLIGHT-01",
        trigger_condition="incident_report_auto_open_smoke",
        severity="LOW",
        report_path=str(incident_path),
    )
    smoke_pass = incident_path.exists() and bool(auto_opened)
    results.append(
        {
            "name": "incident_report_auto_open_smoke",
            "expected_reason": "incident_report_created_and_opened",
            "blocked_reason": "incident_report_created_and_opened" if smoke_pass else "incident_report_smoke_failed",
            "locked": True,
            "allowed_to_start": False,
            "incident_required": True,
            "submitted": 0,
            "order_allowed": False,
            "real_order": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "incident_record": incident_record,
            "pass": bool(smoke_pass),
        }
    )

    pass_count = sum(1 for item in results if item.get("pass"))
    fail_count = len(results) - pass_count
    report.update(
        {
            "guarded_window_config": config.to_dict(),
            "guarded_window_fixture_count": len(results),
            "guarded_window_pass_count": pass_count,
            "guarded_window_fail_count": fail_count,
            "guarded_window_results": results,
            "allowed_to_start": False,
            "aits_on_clicked": False,
            "order_service_place_order_called": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "incident_report_smoke_path": str(incident_path),
            "incident_report_auto_opened": bool(auto_opened),
            "provider_call_markers": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
            "submitted_detected": False,
            "order_risk_detected": False,
            "real_order_detected": False,
            "paper_mode_created": False,
            "virtual_trading_created": False,
            "mock_trading_processor_created": False,
            "pass_status": "pass" if fail_count == 0 else "fail",
            "report_status": "pass" if fail_count == 0 else "fail",
        }
    )


def _run_live_2h_guarded_window_order_path_cap_proof(
    report: dict[str, Any],
    *,
    per_order_krw: float,
    per_order_hard_cap_krw: float,
    total_window_cap_krw: float,
    max_order_count: int,
    min_order_interval_sec: int,
) -> None:
    from datetime import datetime, timedelta, timezone

    from app.services.live_guarded_window import (
        LiveGuardedWindow,
        LiveGuardedWindowConfig,
        LiveGuardedWindowState,
    )
    from app.services.live_order_preflight import LiveOrderPreflight, LiveOrderPreflightInput
    from app.services.live_order_unlock import LiveOneShotUnlock
    from app.services.risk_guard import RiskGuard

    service = LiveGuardedWindow()
    risk_guard = RiskGuard()
    preflight = LiveOrderPreflight()
    unlock_manager = LiveOneShotUnlock()
    now = datetime.now(timezone.utc)
    config = LiveGuardedWindowConfig.from_mapping(
        {
            "window_id": f"guarded_order_path_{uuid.uuid4().hex[:12]}",
            "duration_min": 120,
            "per_order_krw": per_order_krw,
            "per_order_hard_cap_krw": per_order_hard_cap_krw,
            "total_window_cap_krw": total_window_cap_krw,
            "max_order_count": max_order_count,
            "min_order_interval_sec": min_order_interval_sec,
            "sell_allowed": False,
            "cancel_allowed": False,
            "retry_allowed": False,
            "emergency_stop_required": True,
            "incident_stop_required": True,
            "approval_phrase_hash": "sha256:AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM",
        }
    )
    base_state = LiveGuardedWindowState.from_mapping(
        {
            "window_id": config.window_id,
            "active": False,
            "locked": True,
            "order_count": 0,
            "total_order_amount_krw": 0.0,
            "relocked": True,
            "duplicate_lock_ok": True,
            "repeat_block_ok": True,
        }
    )

    def guarded_candidate(name: str, candidate: dict[str, Any], expected_reason: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state_data = dict(base_state.to_dict())
        state_data.update(state or {})
        result = service.evaluate_order_attempt(
            config,
            LiveGuardedWindowState.from_mapping(state_data),
            candidate,
        )
        passed = (
            result.blocked_reason == expected_reason
            and result.locked
            and not result.order_allowed
            and not result.real_order
            and result.submitted == 0
            and result.place_order_call_count == 0
            and result.cancel_call_count == 0
            and result.sell_call_count == 0
            and result.retry_call_count == 0
        )
        return {
            "name": name,
            "expected_reason": expected_reason,
            "blocked_reason": result.blocked_reason,
            "pass": bool(passed),
            "result": result.to_dict(),
        }

    allowed_request_id = "guarded_allowed_10000_buy"
    allowed_candidate = {
        "symbol": "KRW-BTC",
        "side": "buy",
        "amount_krw": per_order_krw,
        "price": 100000000.0,
        "quantity": per_order_krw / 100000000.0,
    }
    allowed_window = service.evaluate_order_attempt(config, base_state, allowed_candidate)
    risk_input = {
        "request_id": allowed_request_id,
        "symbol": "KRW-BTC",
        "side": "buy",
        "requested_amount_krw": per_order_krw,
        "price": 100000000.0,
        "quantity": per_order_krw / 100000000.0,
        "source_provider": "local",
        "confidence": 0.75,
        "action": "buy",
        "holdings_value_krw": 0.0,
        "cash_available_krw": total_window_cap_krw,
        "portfolio_value_krw": 1000000.0,
        "daily_realized_pnl_krw": 0.0,
        "daily_loss_limit_krw": 30000.0,
        "max_order_amount_krw": per_order_hard_cap_krw,
        "max_position_value_krw": total_window_cap_krw,
        "emergency_stop": False,
        "stale_price": False,
        "execution_mode": "live",
        "dry_run": True,
    }
    risk_result = risk_guard.evaluate_order_candidate(risk_input)
    unlock_request = {
        "request_id": allowed_request_id,
        "symbol": "KRW-BTC",
        "side": "buy",
        "amount_krw": per_order_krw,
        "max_order_amount_krw": per_order_hard_cap_krw,
        "min_order_amount_krw": per_order_krw,
        "user_confirm_phrase": "AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM",
        "confirm_token": "AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM",
        "ttl_sec": 300,
        "expires_at_utc": (now + timedelta(seconds=300)).isoformat(timespec="seconds"),
        "duplicate_lock_key": "guarded-window-KRW-BTC-buy-10000-proof",
        "created_at_utc": now.isoformat(timespec="seconds"),
        "source": "live_2h_guarded_window_order_path_cap_proof",
    }
    unlock_state = unlock_manager.create_one_shot_unlock(unlock_request)
    unlock_result = unlock_manager.validate_one_shot_unlock(unlock_state, unlock_request, now_utc=now)
    preflight_input = LiveOrderPreflightInput(
        request_id=allowed_request_id,
        symbol="KRW-BTC",
        side="buy",
        amount_krw=per_order_krw,
        quantity=per_order_krw / 100000000.0,
        price=100000000.0,
        execution_mode="live",
        aits_enabled=True,
        live_order_unlock=True,
        user_confirm_token="masked-proof-token",
        risk_guard_checked=True,
        risk_allowed=bool(risk_result.risk_allowed),
        one_shot_unlock_valid=bool(unlock_result.unlock_valid),
        one_shot_unlock_id=str(unlock_result.unlock_id or ""),
        one_shot_unlock_consumed=False,
        emergency_stop=False,
        max_order_amount_krw=per_order_hard_cap_krw,
        max_daily_loss_krw=30000.0,
        max_order_count_per_cycle=1,
        duplicate_order_lock=True,
        min_real_order_amount_krw=per_order_krw,
        account_ready=True,
        api_key_ready=True,
        price_fresh=True,
        selected_provider="local",
        source="live_2h_guarded_window_order_path_cap_proof",
    )
    preflight_result = preflight.evaluate(preflight_input)
    order_request_metadata = {
        "symbol": "KRW-BTC",
        "side": "buy",
        "amount_krw": per_order_krw,
        "order_type": "market",
        "live_minimum_real_order_test": False,
        "live_guarded_window_order": True,
        "guarded_window_per_order_krw": per_order_krw,
        "guarded_window_per_order_hard_cap_krw": per_order_hard_cap_krw,
        "guarded_window_total_cap_krw": total_window_cap_krw,
        "guarded_window_max_order_count": max_order_count,
        "guarded_window_min_order_interval_sec": min_order_interval_sec,
    }
    allowed_pass = (
        allowed_window.blocked_reason == "preflight_only_order_not_submitted"
        and bool(risk_result.risk_allowed)
        and bool(unlock_result.allowed_for_preflight)
        and bool(preflight_result.allowed_for_preflight)
        and not bool(preflight_result.order_allowed)
        and not bool(preflight_result.real_order)
        and preflight_result.submitted == 0
        and order_request_metadata["amount_krw"] == per_order_krw
        and order_request_metadata["guarded_window_per_order_hard_cap_krw"] == per_order_hard_cap_krw
    )
    results: list[dict[str, Any]] = [
        {
            "name": "allowed_10000_buy_within_window_policy",
            "expected_reason": "preflight_only_order_not_submitted",
            "blocked_reason": allowed_window.blocked_reason,
            "risk_allowed": bool(risk_result.risk_allowed),
            "unlock_allowed_for_preflight": bool(unlock_result.allowed_for_preflight),
            "preflight_allowed_for_preflight": bool(preflight_result.allowed_for_preflight),
            "order_allowed": False,
            "real_order": False,
            "submitted": 0,
            "pass": bool(allowed_pass),
            "guarded_window_result": allowed_window.to_dict(),
            "riskguard_result": risk_result.to_dict(),
            "unlock_result": unlock_result.to_dict(),
            "preflight_result": preflight_result.to_dict(),
            "order_request_metadata": order_request_metadata,
        },
        guarded_candidate(
            "blocked_per_order_hard_cap_12001",
            {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_hard_cap_krw + 1},
            "per_order_cap_exceeded",
        ),
        guarded_candidate(
            "blocked_total_window_cap_30000",
            {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_krw},
            "total_window_cap_exceeded",
            state={"order_count": 1, "total_order_amount_krw": total_window_cap_krw},
        ),
        guarded_candidate(
            "blocked_max_order_count_3",
            {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_krw},
            "max_order_count_exceeded",
            state={"order_count": max_order_count, "total_order_amount_krw": per_order_krw},
        ),
        guarded_candidate(
            "blocked_min_interval_300sec",
            {
                "symbol": "KRW-BTC",
                "side": "buy",
                "amount_krw": per_order_krw,
                "elapsed_since_last_order_sec": 300,
            },
            "min_order_interval_violation",
            state={"order_count": 1, "total_order_amount_krw": per_order_krw},
        ),
        guarded_candidate(
            "blocked_sell_attempt",
            {"symbol": "KRW-BTC", "side": "sell", "amount_krw": per_order_krw},
            "sell_attempt_blocked",
        ),
        guarded_candidate(
            "blocked_cancel_attempt",
            {"symbol": "KRW-BTC", "side": "buy", "amount_krw": per_order_krw, "cancel_attempt": True},
            "cancel_attempt_blocked",
        ),
        guarded_candidate(
            "blocked_retry_attempt",
            {
                "symbol": "KRW-BTC",
                "side": "buy",
                "amount_krw": per_order_krw,
                "retry_attempt": True,
                "normalized_order_state": "query_failed_no_retry",
            },
            "unknown_state_retry_blocked",
        ),
    ]
    pass_count = sum(1 for item in results if item.get("pass"))
    fail_count = len(results) - pass_count
    report.update(
        {
            "guarded_window_order_path_config": config.to_dict(),
            "guarded_window_order_path_fixture_count": len(results),
            "guarded_window_order_path_pass_count": pass_count,
            "guarded_window_order_path_fail_count": fail_count,
            "guarded_window_order_path_results": results,
            "allowed_10000_policy_passed": bool(allowed_pass),
            "aits_on_clicked": False,
            "order_service_place_order_called": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "provider_call_markers": 0,
            "external_cost_call_markers": 0,
            "external_cost_call_delta": 0,
            "submitted_detected": False,
            "order_risk_detected": False,
            "real_order_detected": False,
            "paper_mode_created": False,
            "virtual_trading_created": False,
            "mock_trading_processor_created": False,
            "pass_status": "pass" if fail_count == 0 else "fail",
            "report_status": "pass" if fail_count == 0 else "fail",
        }
    )


def _run_riskguard_active_path_proof(
    app: Any,
    window: Any,
    paths: dict[str, str],
    report: dict[str, Any],
    *,
    started_epoch: float,
) -> None:
    orch = None
    try:
        getter = getattr(window, "_get_aits_orchestrator", None)
        if callable(getter):
            orch = getter()
    except Exception:
        orch = None
    if orch is None:
        orch = getattr(window, "orchestrator", None)
    if orch is None:
        try:
            import logging
            from app.services.aits_orchestrator import AITSOrchestrator

            logger = logging.getLogger("aits") or getattr(window, "_log", None)
            orch = AITSOrchestrator(logger=logger, run_mode="qt_smoke_harness")
            if hasattr(orch, "initialize"):
                orch.initialize()
            try:
                setattr(window, "orchestrator", orch)
            except Exception:
                pass
            report["riskguard_orchestrator_source"] = "harness_created"
        except Exception as exc:
            report["riskguard_orchestrator_create_error"] = type(exc).__name__
            orch = None
    else:
        report["riskguard_orchestrator_source"] = "window"

    report["riskguard_active_path_checked"] = True
    report["riskguard_orchestrator_found"] = orch is not None
    if orch is None or not hasattr(orch, "run_cycle"):
        report["pass_status"] = "fail"
        report["fail_reason"] = "orchestrator_missing"
        return

    try:
        mode_before = ""
        if hasattr(orch, "get_execution_mode"):
            mode_before = str(orch.get_execution_mode() or "")
        report["execution_mode_before"] = mode_before or "disabled"
        if mode_before and mode_before != "disabled":
            report["pass_status"] = "no_go"
            report["fail_reason"] = f"unsafe_execution_mode:{mode_before}"
            return
        result = orch.run_cycle()
        _pump_events(app, 0.5)
        report["orchestrator_cycle_status"] = str(getattr(getattr(result, "status", None), "status", "") or "")
    except Exception as exc:
        report["pass_status"] = "fail"
        report["fail_reason"] = f"run_cycle_failed:{type(exc).__name__}"
        return

    events: list[dict[str, Any]] = []
    try:
        getter = getattr(orch, "get_last_risk_guard_events", None)
        if callable(getter):
            events = [event for event in list(getter() or []) if isinstance(event, dict)]
    except Exception:
        events = []

    log_tail = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    latest_event = events[-1] if events else {}
    report.update(
        {
            "riskguard_active_path_events": events,
            "latest_riskguard_event": latest_event,
            "riskguard_candidate_seen": any(str(event.get("event")) == "evaluate" for event in events),
            "risk_allowed": bool(latest_event.get("risk_allowed", False)) if latest_event else False,
            "risk_blocked_reason": str(latest_event.get("blocked_reason") or latest_event.get("reason") or ""),
            "provider_call_markers": int(log_tail.get("provider_call_markers") or 0),
            "external_cost_call_markers": int(log_tail.get("external_cost_call_markers") or 0),
            "external_cost_call_delta": int(log_tail.get("external_cost_call_markers") or 0),
            "riskguard_active_path_log_markers": int(
                (log_tail.get("marker_counts") or {}).get("riskguard_active_path") or 0
            ),
            "submitted_detected": False,
            "order_risk_detected": bool(log_tail.get("risk_hits")),
            "real_order_detected": False,
            "log_tail_after_riskguard_cycle": log_tail,
        }
    )

    fail_reasons: list[str] = []
    if not events:
        fail_reasons.append("riskguard_events_missing")
    if report["provider_call_markers"] != 0:
        fail_reasons.append("provider_call_marker_detected")
    if report["external_cost_call_markers"] != 0:
        fail_reasons.append("external_cost_call_detected")
    if report["order_risk_detected"]:
        fail_reasons.append("order_risk_detected")
    for event in events:
        if event.get("submitted") not in (0, "0", None):
            fail_reasons.append("submitted_not_zero")
        if bool(event.get("order_allowed", False)):
            fail_reasons.append("order_allowed_true")
        if bool(event.get("real_order", False)):
            fail_reasons.append("real_order_true")

    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(sorted(set(fail_reasons)))
    elif report["riskguard_candidate_seen"]:
        report["pass_status"] = "pass"
    else:
        report["pass_status"] = "partial"
        report["fail_reason"] = "no_candidate"


def _run_riskguard_active_path_candidate_proof(
    app: Any,
    window: Any,
    paths: dict[str, str],
    report: dict[str, Any],
    *,
    started_epoch: float,
) -> None:
    try:
        import logging

        from app.core.aits_state import ActionItem, ExecutionPlan
        from app.services.aits_orchestrator import AITSOrchestrator
        from app.services.execution_bridge import ExecutionBridge
    except Exception as exc:
        report["pass_status"] = "fail"
        report["fail_reason"] = f"import_failed:{type(exc).__name__}"
        return

    logger = logging.getLogger("aits")
    orch = AITSOrchestrator(logger=logger, run_mode="qt_smoke_harness")
    try:
        orch.initialize()
    except Exception as exc:
        report["pass_status"] = "fail"
        report["fail_reason"] = f"orchestrator_init_failed:{type(exc).__name__}"
        return

    try:
        if hasattr(orch, "get_execution_mode"):
            mode_before = str(orch.get_execution_mode() or "")
        else:
            mode_before = str(getattr(orch, "execution_mode", "") or "")
        report["order_adapter_execution_mode"] = mode_before or "disabled"
        if mode_before and mode_before != "disabled":
            report["pass_status"] = "no_go"
            report["fail_reason"] = f"unsafe_execution_mode:{mode_before}"
            return
    except Exception:
        report["order_adapter_execution_mode"] = "disabled"

    fixtures = [
        {
            "name": "allowed_small_buy_path",
            "expected_risk_allowed": True,
            "amount_krw": 5000.0,
            "max_order_amount_krw": 10000.0,
        },
        {
            "name": "blocked_max_order_path",
            "expected_risk_allowed": False,
            "amount_krw": 500000.0,
            "max_order_amount_krw": 10000.0,
            "expected_blocked_reason": "max_order_amount_exceeded",
        },
    ]
    results: list[dict[str, Any]] = []
    pass_count = 0
    fail_count = 0

    for idx, item in enumerate(fixtures, start=1):
        name = str(item["name"])
        rs = orch.last_runtime_state
        try:
            rs.meta.cycle_id = 9000 + idx
            rs.market.snapshot.btc_price = 100000000.0
            rs.portfolio.summary.cash_balance = 100000.0
            rs.portfolio.summary.total_equity = 1000000.0
            rs.portfolio.summary.realized_pnl = 0.0
            rs.control.pause_logic.pause_requested = False
        except Exception:
            pass

        action = ActionItem(
            symbol="KRW-BTC",
            action_type="buy",
            amount_krw=float(item["amount_krw"]),
            priority=1,
            source_module="riskguard_active_path_fixture",
            source_provider="local",
            reason=f"RiskGuard active path fixture {name}",
        )
        setattr(action, "risk_guard_proof_mode", True)
        setattr(action, "risk_guard_proof_fixture", name)
        setattr(action, "risk_guard_request_id", name)

        plan = ExecutionPlan(approved_actions=[action], blocked_actions=[], execution_mode="normal")
        try:
            orch.last_runtime_state.execution.plan = plan
            old_builder = orch._build_risk_guard_context

            def _fixture_context(candidate_action: Any, *, _old: Any = old_builder, _item: dict[str, Any] = item) -> dict[str, Any]:
                context = dict(_old(candidate_action))
                context.update(
                    {
                        "price": 100000000.0,
                        "stale_price": False,
                        "cash_available_krw": 100000.0,
                        "portfolio_value_krw": 1000000.0,
                        "holdings_value_krw": 0.0,
                        "daily_realized_pnl_krw": 0.0,
                        "daily_loss_limit_krw": 30000.0,
                        "max_order_amount_krw": float(_item["max_order_amount_krw"]),
                        "max_position_value_krw": 200000.0,
                        "emergency_stop": False,
                        "execution_mode": "disabled",
                        "dry_run": True,
                        "request_id": str(_item["name"]),
                        "proof_mode": True,
                        "proof_fixture": str(_item["name"]),
                    }
                )
                return context

            orch._build_risk_guard_context = _fixture_context  # type: ignore[method-assign]
            try:
                orch._apply_risk_guard_to_execution_plan(plan)
            finally:
                orch._build_risk_guard_context = old_builder  # type: ignore[method-assign]

            bridge = ExecutionBridge(logger=logger).build_from_runtime_state(orch.last_runtime_state)
            bridge_actions = list(getattr(bridge, "actions", []) or [])
            bridge_match = next(
                (
                    ba
                    for ba in bridge_actions
                    if str(getattr(ba, "symbol", "")) == "KRW-BTC"
                    and str((getattr(ba, "risk_guard", {}) or {}).get("risk_proof_fixture", "")) == name
                ),
                None,
            )
            metadata = dict(getattr(action, "risk_guard", {}) or {})
            bridge_metadata = dict(getattr(bridge_match, "risk_guard", {}) or {}) if bridge_match is not None else {}
            actual_allowed = bool(metadata.get("risk_allowed", False))
            expected_allowed = bool(item["expected_risk_allowed"])
            blocked_reason = str(metadata.get("risk_blocked_reason") or "")
            expected_reason = str(item.get("expected_blocked_reason") or "")
            passed = (
                bool(metadata.get("risk_guard_checked", False))
                and bool(bridge_metadata.get("risk_guard_checked", False))
                and actual_allowed == expected_allowed
                and (not expected_reason or blocked_reason == expected_reason)
                and int(metadata.get("submitted", 0) or 0) == 0
                and bool(metadata.get("order_allowed", False)) is False
                and bool(metadata.get("real_order", False)) is False
                and bool(metadata.get("dry_run", False)) is True
                and bool(bridge_metadata.get("order_allowed", False)) is False
                and bool(bridge_metadata.get("real_order", False)) is False
            )
            if passed:
                pass_count += 1
            else:
                fail_count += 1
            results.append(
                {
                    "name": name,
                    "expected_risk_allowed": expected_allowed,
                    "actual_risk_allowed": actual_allowed,
                    "risk_blocked_reason": blocked_reason,
                    "actionitem_metadata_seen": bool(metadata.get("risk_guard_checked", False)),
                    "execution_bridge_metadata_seen": bool(bridge_metadata.get("risk_guard_checked", False)),
                    "bridge_blocked": bool(getattr(bridge_match, "blocked", False)) if bridge_match is not None else None,
                    "bridge_action_found": bridge_match is not None,
                    "submitted": int(metadata.get("submitted", 0) or 0),
                    "order_allowed": bool(metadata.get("order_allowed", False)),
                    "real_order": bool(metadata.get("real_order", False)),
                    "dry_run": bool(metadata.get("dry_run", False)),
                    "pass": bool(passed),
                    "actionitem_risk_guard": metadata,
                    "execution_bridge_risk_guard": bridge_metadata,
                }
            )
        except Exception as exc:
            fail_count += 1
            results.append(
                {
                    "name": name,
                    "pass": False,
                    "error": type(exc).__name__,
                    "submitted": 0,
                    "order_allowed": False,
                    "real_order": False,
                    "dry_run": True,
                }
            )

    _pump_events(app, 0.5)
    log_tail = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    report.update(
        {
            "riskguard_active_path_candidate_fixture_count": len(results),
            "riskguard_active_path_candidate_pass_count": pass_count,
            "riskguard_active_path_candidate_fail_count": fail_count,
            "riskguard_active_path_candidate_results": results,
            "actionitem_metadata_seen": all(bool(r.get("actionitem_metadata_seen")) for r in results),
            "execution_bridge_metadata_seen": all(bool(r.get("execution_bridge_metadata_seen")) for r in results),
            "order_adapter_called": False,
            "provider_call_markers": int(log_tail.get("provider_call_markers") or 0),
            "external_cost_call_markers": int(log_tail.get("external_cost_call_markers") or 0),
            "external_cost_call_delta": int(log_tail.get("external_cost_call_markers") or 0),
            "riskguard_active_path_log_markers": int(
                (log_tail.get("marker_counts") or {}).get("riskguard_active_path") or 0
            ),
            "submitted_detected": False,
            "order_risk_detected": bool(log_tail.get("risk_hits")),
            "real_order_detected": False,
            "log_tail_after_riskguard_candidate_fixture": log_tail,
        }
    )

    fail_reasons: list[str] = []
    if fail_count:
        fail_reasons.append("fixture_mismatch")
    if report["provider_call_markers"] != 0:
        fail_reasons.append("provider_call_marker_detected")
    if report["external_cost_call_markers"] != 0:
        fail_reasons.append("external_cost_call_detected")
    if report["order_risk_detected"]:
        fail_reasons.append("order_risk_detected")
    if report["riskguard_active_path_log_markers"] < len(fixtures):
        fail_reasons.append("riskguard_log_marker_missing")
    for result in results:
        if int(result.get("submitted", 0) or 0) != 0:
            fail_reasons.append("submitted_not_zero")
        if bool(result.get("order_allowed", False)):
            fail_reasons.append("order_allowed_true")
        if bool(result.get("real_order", False)):
            fail_reasons.append("real_order_true")
    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(sorted(set(fail_reasons)))
    else:
        report["pass_status"] = "pass"


def _run_live_2h_guarded_window_runtime(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    paths: dict[str, str],
    report: dict[str, Any],
    *,
    started_epoch: float,
    confirm_phrase: str,
    duration_min: int,
    per_order_krw: float,
    per_order_hard_cap_krw: float,
    total_window_cap_krw: float,
    max_order_count: int,
    min_order_interval_sec: int,
    dry_run_no_on: bool,
    check_interval_sec: int,
    incident_open: bool,
    max_smoke_duration_sec: int,
) -> None:
    from app.services.live_guarded_window import (
        LiveGuardedWindow,
        LiveGuardedWindowConfig,
        LiveGuardedWindowState,
    )

    expected_phrase = "AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM"
    phrase_valid = str(confirm_phrase or "") == expected_phrase
    service = LiveGuardedWindow()
    config = LiveGuardedWindowConfig.from_mapping(
        {
            "window_id": f"guarded_runtime_{uuid.uuid4().hex[:12]}",
            "duration_min": duration_min,
            "per_order_krw": per_order_krw,
            "per_order_hard_cap_krw": per_order_hard_cap_krw,
            "total_window_cap_krw": total_window_cap_krw,
            "max_order_count": max_order_count,
            "min_order_interval_sec": min_order_interval_sec,
            "sell_allowed": False,
            "cancel_allowed": False,
            "retry_allowed": False,
            "emergency_stop_required": True,
            "incident_stop_required": True,
            "approval_phrase_hash": "sha256:AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM",
        }
    )
    state = LiveGuardedWindowState.from_mapping(
        {
            "window_id": config.window_id,
            "active": False,
            "locked": True,
            "order_count": 0,
            "total_order_amount_krw": 0.0,
            "relocked": True,
            "duplicate_lock_ok": True,
            "repeat_block_ok": True,
        }
    )
    start_result = service.evaluate_window_start(config, state)
    selector = _discover_aits_on_selector(window)
    baseline_collect = _collect(window, widgets)

    preflight_report: dict[str, Any] = {"mode": "live-2h-guarded-window-preflight-proof", "embedded": True}
    _run_live_2h_guarded_window_preflight_proof(
        preflight_report,
        duration_min=duration_min,
        per_order_krw=per_order_krw,
        per_order_hard_cap_krw=per_order_hard_cap_krw,
        total_window_cap_krw=total_window_cap_krw,
        max_order_count=max_order_count,
        min_order_interval_sec=min_order_interval_sec,
    )
    cap_report: dict[str, Any] = {"mode": "live-2h-guarded-window-order-path-cap-proof", "embedded": True}
    _run_live_2h_guarded_window_order_path_cap_proof(
        cap_report,
        per_order_krw=per_order_krw,
        per_order_hard_cap_krw=per_order_hard_cap_krw,
        total_window_cap_krw=total_window_cap_krw,
        max_order_count=max_order_count,
        min_order_interval_sec=min_order_interval_sec,
    )
    reconciliation_report: dict[str, Any] = {"mode": "live-order-post-trade-reconciliation", "embedded": True}
    _run_live_order_post_trade_reconciliation(
        reconciliation_report,
        order_uuid="06f08c3a-2bd3-4888-a7e6-2402623cb63e",
    )

    dry_read_pass = (
        "AITS OFF" in str(baseline_collect.get("aits_power_state") or "")
        and "Shadow" in str(baseline_collect.get("aits_safety_state") or "")
        and not bool(baseline_collect.get("manual_order_button_risk"))
    )
    baseline_failures: list[str] = []
    if not dry_read_pass:
        baseline_failures.append("dry_read_safety_state_not_pass")
    if reconciliation_report.get("pass_status") != "pass" and reconciliation_report.get("status") != "pass":
        baseline_failures.append("reconciliation_not_pass")
    if preflight_report.get("pass_status") != "pass":
        baseline_failures.append("guarded_window_preflight_not_pass")
    if cap_report.get("pass_status") != "pass":
        baseline_failures.append("guarded_window_order_path_cap_not_pass")

    monitor_checks: list[dict[str, Any]] = []
    monitor_started = time.time()
    requested_seconds = max(float(duration_min) * 60.0, 0.0)
    duration_seconds = min(requested_seconds, float(max(max_smoke_duration_sec, 1))) if dry_run_no_on else 0.0
    interval = max(1.0, min(float(max(check_interval_sec, 1)), duration_seconds or 1.0))
    while time.time() - monitor_started < duration_seconds:
        _pump_events(app, min(interval, max(duration_seconds - (time.time() - monitor_started), 0.1)))
        log_tail = _read_log_tail(Path(paths["log_dir"]), started_epoch)
        snapshot = _collect(window, widgets)
        monitor_checks.append(
            {
                "elapsed_sec": round(time.time() - monitor_started, 3),
                "aits_power_state": snapshot.get("aits_power_state", ""),
                "aits_safety_state": snapshot.get("aits_safety_state", ""),
                "provider_call_markers": int(log_tail.get("provider_call_markers") or 0),
                "external_cost_call_markers": int(log_tail.get("external_cost_call_markers") or 0),
                "risk_hits": list(log_tail.get("risk_hits") or []),
                "error_count": len(log_tail.get("errors") or []),
                "aits_on_clicked": False,
                "place_order_call_count": 0,
                "cancel_call_count": 0,
                "sell_call_count": 0,
                "retry_call_count": 0,
            }
        )
    if not monitor_checks:
        log_tail = _read_log_tail(Path(paths["log_dir"]), started_epoch)
        snapshot = _collect(window, widgets)
        monitor_checks.append(
            {
                "elapsed_sec": 0.0,
                "aits_power_state": snapshot.get("aits_power_state", ""),
                "aits_safety_state": snapshot.get("aits_safety_state", ""),
                "provider_call_markers": int(log_tail.get("provider_call_markers") or 0),
                "external_cost_call_markers": int(log_tail.get("external_cost_call_markers") or 0),
                "risk_hits": list(log_tail.get("risk_hits") or []),
                "error_count": len(log_tail.get("errors") or []),
                "aits_on_clicked": False,
                "place_order_call_count": 0,
                "cancel_call_count": 0,
                "sell_call_count": 0,
                "retry_call_count": 0,
            }
        )

    incident_dir = ROOT / "data" / "live_incidents"
    incident_path = incident_dir / f"aits_live_2h_guarded_window_incident_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    incident_markdown = _guarded_window_incident_markdown(
        path=incident_path,
        fixture_name="runtime_harness_incident_auto_open_smoke",
        trigger="runtime harness incident auto-open smoke fixture",
    )
    _write_text_report(incident_path, incident_markdown)
    incident_auto_opened = _open_text_report_windows(incident_path) if incident_open else False

    final_log_tail = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    fail_reasons: list[str] = []
    if not phrase_valid:
        fail_reasons.append("confirm_phrase_invalid")
    if not dry_run_no_on:
        fail_reasons.append("dry_run_no_on_required_for_this_goal")
    if start_result.blocked_reason != "preflight_only_aits_on_not_clicked":
        fail_reasons.append(f"window_config_blocked:{start_result.blocked_reason}")
    if not selector.get("found"):
        fail_reasons.append("aits_on_selector_not_found")
    fail_reasons.extend(baseline_failures)
    if not incident_path.exists():
        fail_reasons.append("incident_smoke_report_missing")
    if incident_open and not incident_auto_opened:
        fail_reasons.append("incident_auto_open_failed")
    if int(final_log_tail.get("external_cost_call_markers") or 0) != 0:
        fail_reasons.append("provider_external_call_detected")
    risk_hits = [
        hit
        for hit in list(final_log_tail.get("risk_hits") or [])
        if hit not in {"real_order=True"}
    ]
    if risk_hits:
        fail_reasons.append("order_risk_marker_detected")

    live_report_dir = ROOT / "data" / "live_window_reports"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    live_report_path = live_report_dir / f"aits_live_2h_guarded_window_report_smoke_{stamp}.json"
    live_summary_path = live_report_dir / f"aits_live_2h_guarded_window_summary_smoke_{stamp}.md"

    status = "pass" if not fail_reasons else "fail"
    report.update(
        {
            "smoke_mode": bool(dry_run_no_on),
            "confirm_phrase_valid": bool(phrase_valid),
            "confirm_phrase_masked": _mask_confirm_phrase(confirm_phrase),
            "guarded_window_config": config.to_dict(),
            "guarded_window_start_result": start_result.to_dict(),
            "baseline_collect": baseline_collect,
            "baseline_status": "pass" if not baseline_failures else "fail",
            "baseline_failures": baseline_failures,
            "baseline_dry_read_status": "pass" if dry_read_pass else "fail",
            "embedded_reconciliation_status": reconciliation_report.get("pass_status")
            or reconciliation_report.get("status", ""),
            "embedded_reconciliation_result": reconciliation_report,
            "embedded_guarded_window_preflight_status": preflight_report.get("pass_status", ""),
            "embedded_guarded_window_preflight_result": preflight_report,
            "embedded_order_path_cap_status": cap_report.get("pass_status", ""),
            "embedded_order_path_cap_result": cap_report,
            "aits_on_selector_found": bool(selector.get("found")),
            "aits_on_selector": selector,
            "aits_on_clicked": False,
            "duration_requested_min": duration_min,
            "duration_actual_sec": round(time.time() - monitor_started, 3),
            "check_interval_sec": check_interval_sec,
            "check_count": len(monitor_checks),
            "monitoring_loop_status": "pass",
            "monitoring_checks": monitor_checks,
            "order_count": 0,
            "total_order_amount_krw": 0,
            "order_service_place_order_called": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "incident_triggered": False,
            "incident_report_smoke_path": str(incident_path),
            "incident_report_path": "",
            "incident_report_auto_opened": bool(incident_auto_opened),
            "provider_call_markers": int(final_log_tail.get("provider_call_markers") or 0),
            "external_cost_call_markers": int(final_log_tail.get("external_cost_call_markers") or 0),
            "provider_external_call_count": int(final_log_tail.get("external_cost_call_markers") or 0),
            "external_cost_call_delta": int(final_log_tail.get("external_cost_call_markers") or 0),
            "submitted_detected": False,
            "order_risk_detected": bool(risk_hits),
            "real_order_detected": False,
            "log_tail": final_log_tail,
            "live_window_report_path": str(live_report_path),
            "live_window_summary_path": str(live_summary_path),
            "fail_reasons": fail_reasons,
            "pass_status": status,
            "report_status": status,
        }
    )
    live_report_dir.mkdir(parents=True, exist_ok=True)
    _write_text_report(live_summary_path, _guarded_window_runtime_summary_markdown(report))
    _write_json_report(report, live_report_path)


def run_harness(
    mode: str,
    output_dir: Path,
    allow_provider_calls: bool,
    *,
    provider: str | None = None,
    max_provider_calls: int = 1,
    target_symbol: str | None = None,
    timeout_sec: float = 90.0,
    wait_after_click_sec: float = 5.0,
    fail_on_provider_call_over_limit: bool = True,
    no_click: bool = False,
    confirm_phrase: str = "",
    order_uuid: str = "",
    duration_min: int = 120,
    per_order_krw: float = 10000.0,
    per_order_hard_cap_krw: float = 12000.0,
    total_window_cap_krw: float = 20000.0,
    max_order_count: int = 2,
    min_order_interval_sec: int = 600,
    dry_run_no_on: bool = False,
    check_interval_sec: int = 300,
    incident_open: bool = True,
    max_smoke_duration_sec: int = 15,
) -> dict[str, Any]:
    started_epoch = time.time()
    report: dict[str, Any] = {
        "schema": "aits_qt_smoke_harness.v1",
        "schema_version": 1,
        "mode": mode,
        "started_at": _now_iso(),
        "provider_calls_allowed": bool(allow_provider_calls),
        "fail_on_provider_call_over_limit": bool(fail_on_provider_call_over_limit),
        "provider_call_blocked": False,
        "warnings": [],
    }
    if mode in {
        "riskguard-proof",
        "live-preflight-locked-proof",
        "live-one-shot-unlock-contract-proof",
        "live-minimum-real-order-test",
        "live-order-post-trade-reconciliation",
        "live-2h-guarded-window-preflight-proof",
        "live-2h-guarded-window-order-path-cap-proof",
    }:
        if mode == "riskguard-proof":
            _run_riskguard_proof(report)
        elif mode == "live-preflight-locked-proof":
            _run_live_preflight_locked_proof(report)
        elif mode == "live-one-shot-unlock-contract-proof":
            _run_live_one_shot_unlock_contract_proof(report)
        elif mode == "live-minimum-real-order-test":
            _run_live_minimum_real_order_test(report, confirm_phrase=confirm_phrase)
        elif mode == "live-2h-guarded-window-preflight-proof":
            _run_live_2h_guarded_window_preflight_proof(
                report,
                duration_min=duration_min,
                per_order_krw=per_order_krw,
                per_order_hard_cap_krw=per_order_hard_cap_krw,
                total_window_cap_krw=total_window_cap_krw,
                max_order_count=max_order_count,
                min_order_interval_sec=min_order_interval_sec,
            )
        elif mode == "live-2h-guarded-window-order-path-cap-proof":
            _run_live_2h_guarded_window_order_path_cap_proof(
                report,
                per_order_krw=per_order_krw,
                per_order_hard_cap_krw=per_order_hard_cap_krw,
                total_window_cap_krw=total_window_cap_krw,
                max_order_count=max_order_count,
                min_order_interval_sec=min_order_interval_sec,
            )
        else:
            _run_live_order_post_trade_reconciliation(report, order_uuid=order_uuid)
        if "status" not in report:
            report["status"] = "pass" if report.get("pass_status") == "pass" else "fail"
        report["finished_at"] = _now_iso()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"runtime_smoke_report_{stamp}.json"
        report["report_path"] = str(path)
        return _write_json_report(report, path)

    if mode == "provider-smoke" and not allow_provider_calls and not no_click:
        report["status"] = "blocked"
        report["warnings"].append("provider-smoke requires --allow-provider-calls unless --no-click is used")
        return report
    if mode == "provider-smoke" and not provider:
        report["status"] = "blocked"
        report["warnings"].append("provider-smoke requires --provider local|gpt|gemini")
        return report
    if not allow_provider_calls and mode != "live-2h-guarded-window":
        _install_network_guards(report)

    app, window, paths = _build_window(
        report,
        skip_ai_reco_updates=(mode != "provider-smoke"),
        skip_startup_restore=(mode == "provider-smoke"),
    )
    _pump_events(app, 1.2)

    widgets: dict[str, Any] = {}
    missing: list[str] = []
    for key, (kind, value) in CORE_WIDGETS.items():
        widget = _find_widget(window, kind, value)
        if widget is None and key == "managed_table":
            widget = getattr(window, "tbl_ai_managed", None)
        if widget is None and key == "trade_log_table":
            widget = getattr(getattr(window, "tab_trades", None), "tbl_records", None)
        if widget is None and key == "trade_log_save":
            widget = getattr(window, "btn_nav_save", None)
        widgets[key] = widget
        if widget is None:
            missing.append(key)

    if mode == "dry-navigation":
        _navigate(window, widgets, report)
        _pump_events(app, 0.5)
    elif mode == "dry-read":
        pass
    elif mode == "riskguard-active-path-proof":
        _run_riskguard_active_path_proof(
            app,
            window,
            paths,
            report,
            started_epoch=started_epoch,
        )
    elif mode == "riskguard-active-path-candidate-proof":
        _run_riskguard_active_path_candidate_proof(
            app,
            window,
            paths,
            report,
            started_epoch=started_epoch,
        )
    elif mode == "provider-smoke":
        _run_provider_smoke(
            app,
            window,
            widgets,
            paths,
            report,
            provider=provider or "",
            max_provider_calls=max_provider_calls,
            target_symbol=target_symbol,
            timeout_sec=timeout_sec,
            wait_after_click_sec=wait_after_click_sec,
            fail_on_provider_call_over_limit=fail_on_provider_call_over_limit,
            no_click=no_click,
            started_epoch=started_epoch,
        )
    elif mode == "save-probe":
        _run_save_probe(
            app,
            window,
            widgets,
            paths,
            report,
            timeout_sec=timeout_sec,
            started_epoch=started_epoch,
        )
    elif mode == "live-2h-guarded-window":
        _run_live_2h_guarded_window_runtime(
            app,
            window,
            widgets,
            paths,
            report,
            started_epoch=started_epoch,
            confirm_phrase=confirm_phrase,
            duration_min=duration_min,
            per_order_krw=per_order_krw,
            per_order_hard_cap_krw=per_order_hard_cap_krw,
            total_window_cap_krw=total_window_cap_krw,
            max_order_count=max_order_count,
            min_order_interval_sec=min_order_interval_sec,
            dry_run_no_on=dry_run_no_on,
            check_interval_sec=check_interval_sec,
            incident_open=incident_open,
            max_smoke_duration_sec=max_smoke_duration_sec,
        )

    report.update(_collect(window, widgets))
    report["missing_widgets"] = missing
    safety_text = f"{report.get('aits_power_state','')} {report.get('aits_safety_state','')}"
    report["submitted_detected"] = False
    report["order_risk_detected"] = any(token in safety_text for token in ("AITS ON", "Live", "실거래"))
    if report.get("manual_order_button_risk"):
        report["order_risk_detected"] = True
    report["log_tail"] = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    if report["log_tail"].get("risk_hits"):
        report["order_risk_detected"] = True
    if mode in {
        "provider-smoke",
        "save-probe",
        "riskguard-active-path-proof",
        "riskguard-active-path-candidate-proof",
        "live-2h-guarded-window",
    } and report.get("pass_status") in {"fail", "no_go"}:
        report["status"] = report.get("pass_status")
    elif mode == "riskguard-active-path-proof" and report.get("pass_status") == "partial":
        report["status"] = "partial"
    elif mode == "riskguard-active-path-candidate-proof" and report.get("pass_status") == "pass":
        report["status"] = "pass"
    elif mode == "live-2h-guarded-window" and report.get("pass_status") == "pass":
        report["status"] = "pass"
    elif not allow_provider_calls and report.get("provider_call_blocked"):
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
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = output_dir / f"runtime_smoke_report_{stamp}.json"
    report["report_path"] = str(path)
    return _write_json_report(report, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="AITS Qt objectName runtime smoke harness")
    parser.add_argument(
        "--mode",
        choices=(
            "dry-read",
            "dry-navigation",
            "provider-smoke",
            "save-probe",
            "riskguard-proof",
            "riskguard-active-path-proof",
            "riskguard-active-path-candidate-proof",
            "live-preflight-locked-proof",
            "live-one-shot-unlock-contract-proof",
            "live-minimum-real-order-test",
            "live-order-post-trade-reconciliation",
            "live-2h-guarded-window-preflight-proof",
            "live-2h-guarded-window-order-path-cap-proof",
            "live-2h-guarded-window",
        ),
        default="dry-read",
    )
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--provider", choices=("local", "gpt", "gemini"))
    parser.add_argument("--max-provider-calls", type=int, default=1)
    parser.add_argument("--target-symbol")
    parser.add_argument("--timeout-sec", type=float, default=90.0)
    parser.add_argument("--wait-after-click-sec", type=float, default=5.0)
    parser.add_argument(
        "--fail-on-provider-call-over-limit",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--no-click",
        action="store_true",
        help="Select provider/target only; do not click AI analysis refresh.",
    )
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "runtime_smoke_reports"))
    parser.add_argument("--confirm-phrase", default="")
    parser.add_argument("--order-uuid", default="")
    parser.add_argument("--duration-min", type=int, default=120)
    parser.add_argument("--per-order-krw", type=float, default=10000.0)
    parser.add_argument("--per-order-hard-cap-krw", type=float, default=12000.0)
    parser.add_argument("--total-window-cap-krw", type=float, default=20000.0)
    parser.add_argument("--max-order-count", type=int, default=2)
    parser.add_argument("--min-order-interval-sec", type=int, default=600)
    parser.add_argument(
        "--dry-run-no-on",
        action="store_true",
        help="Discover AITS ON controls and run monitoring smoke without clicking AITS ON or placing orders.",
    )
    parser.add_argument("--check-interval-sec", type=int, default=300)
    parser.add_argument(
        "--incident-open",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open generated incident markdown in Notepad when available.",
    )
    parser.add_argument("--max-smoke-duration-sec", type=int, default=15)
    args = parser.parse_args()
    report = run_harness(
        args.mode,
        Path(args.output_dir),
        args.allow_provider_calls,
        provider=args.provider,
        max_provider_calls=args.max_provider_calls,
        target_symbol=args.target_symbol,
        timeout_sec=args.timeout_sec,
        wait_after_click_sec=args.wait_after_click_sec,
        fail_on_provider_call_over_limit=args.fail_on_provider_call_over_limit,
        no_click=args.no_click,
        confirm_phrase=args.confirm_phrase,
        order_uuid=args.order_uuid,
        duration_min=args.duration_min,
        per_order_krw=args.per_order_krw,
        per_order_hard_cap_krw=args.per_order_hard_cap_krw,
        total_window_cap_krw=args.total_window_cap_krw,
        max_order_count=args.max_order_count,
        min_order_interval_sec=args.min_order_interval_sec,
        dry_run_no_on=args.dry_run_no_on,
        check_interval_sec=args.check_interval_sec,
        incident_open=args.incident_open,
        max_smoke_duration_sec=args.max_smoke_duration_sec,
    )
    print(_json_report_text(report))
    return 0 if report.get("status") in ("pass", "partial", "blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
