from __future__ import annotations

import argparse
import json
import os
import re
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
) -> dict[str, Any]:
    started_epoch = time.time()
    report: dict[str, Any] = {
        "schema": "aits_qt_smoke_harness.v1",
        "mode": mode,
        "started_at": _now_iso(),
        "provider_calls_allowed": bool(allow_provider_calls),
        "fail_on_provider_call_over_limit": bool(fail_on_provider_call_over_limit),
        "provider_call_blocked": False,
        "warnings": [],
    }
    if mode == "provider-smoke" and not allow_provider_calls:
        report["status"] = "blocked"
        report["warnings"].append("provider-smoke requires --allow-provider-calls")
        return report
    if mode == "provider-smoke" and not provider:
        report["status"] = "blocked"
        report["warnings"].append("provider-smoke requires --provider local|gpt|gemini")
        return report
    if not allow_provider_calls:
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
        widgets[key] = widget
        if widget is None:
            missing.append(key)

    if mode == "dry-navigation":
        _navigate(window, widgets, report)
        _pump_events(app, 0.5)
    elif mode == "dry-read":
        pass
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

    report.update(_collect(window, widgets))
    report["missing_widgets"] = missing
    safety_text = f"{report.get('aits_power_state','')} {report.get('aits_safety_state','')}"
    report["submitted_detected"] = False
    report["order_risk_detected"] = any(token in safety_text for token in ("AITS ON", "Live", "실거래"))
    report["log_tail"] = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    if report["log_tail"].get("risk_hits"):
        report["order_risk_detected"] = True
    if mode == "provider-smoke" and report.get("pass_status") in {"fail", "no_go"}:
        report["status"] = report.get("pass_status")
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
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="AITS Qt objectName runtime smoke harness")
    parser.add_argument("--mode", choices=("dry-read", "dry-navigation", "provider-smoke"), default="dry-read")
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
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in ("pass", "partial", "blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
