from __future__ import annotations

import argparse
import json
import math
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
        "schema_version": 1,
        "mode": mode,
        "started_at": _now_iso(),
        "provider_calls_allowed": bool(allow_provider_calls),
        "fail_on_provider_call_over_limit": bool(fail_on_provider_call_over_limit),
        "provider_call_blocked": False,
        "warnings": [],
    }
    if mode == "riskguard-proof":
        _run_riskguard_proof(report)
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
    if mode in {"provider-smoke", "save-probe", "riskguard-active-path-proof"} and report.get("pass_status") in {"fail", "no_go"}:
        report["status"] = report.get("pass_status")
    elif mode == "riskguard-active-path-proof" and report.get("pass_status") == "partial":
        report["status"] = "partial"
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
    print(_json_report_text(report))
    return 0 if report.get("status") in ("pass", "partial", "blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
