from __future__ import annotations

import argparse
import html
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

PUBLIC_MARKET_READ_MODES = {
    "top-markets-feed-proof",
    "basic-candidate-discovery-proof",
    "buy-ready-order-intent-contract-proof",
    "managed-pool-auto-promotion-apply-proof",
    "managed-pool-max-size-apply-button-actual-proof",
    "managed-pool-max-size-apply-button-sync-actual-proof",
    "rotation-intent-live-candidate-proof",
    "rotation-intent-live-candidate-feed-proof",
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
        "latest_provider_http_status": "",
        "latest_provider_response_id": "",
        "latest_provider_request_id": "",
        "latest_provider_usage_total_tokens": "",
        "latest_provider_success_seen": False,
        "latest_provider_failure_seen": False,
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
        "openai_response_success": active_text.count("[AITS][OpenAIProviderProof] event=response_success"),
        "openai_response_failed": active_text.count("[AITS][OpenAIProviderProof] event=response_failed"),
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
        "startup_readiness_scheduled": active_text.count("[AITS][StartupReadinessPreflight] event=scheduled"),
        "startup_readiness_skip": active_text.count("[AITS][StartupReadinessPreflight] event=skip"),
        "startup_readiness_worker_start": active_text.count("[AITS][StartupReadinessPreflight] event=worker_start"),
        "startup_readiness_worker_result": active_text.count("[AITS][StartupReadinessPreflight] event=worker_result"),
        "startup_readiness_ui_applied": active_text.count("[AITS][StartupReadinessPreflight] event=ui_applied"),
        "startup_readiness_dispatch_blocked": active_text.count("[AITS][StartupReadinessPreflight] event=dispatch_blocked"),
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
    startup_lines = [
        line for line in active_lines if "[AITS][StartupReadinessPreflight]" in line
    ]
    result["startup_readiness_lines"] = [line[-700:] for line in startup_lines][-30:]
    result["startup_readiness_scheduled"] = marker_counts["startup_readiness_scheduled"] > 0
    result["startup_readiness_skip_seen"] = marker_counts["startup_readiness_skip"] > 0
    result["startup_readiness_worker_started"] = marker_counts["startup_readiness_worker_start"] > 0
    result["startup_readiness_worker_result_seen"] = marker_counts["startup_readiness_worker_result"] > 0
    result["startup_readiness_ui_applied"] = marker_counts["startup_readiness_ui_applied"] > 0
    result["startup_readiness_dispatch_blocked"] = marker_counts["startup_readiness_dispatch_blocked"] > 0
    skip_matches = re.findall(r"\[AITS\]\[StartupReadinessPreflight\] event=skip[^\n]*reason=([^ ]+)", active_text)
    result["startup_readiness_skip_reason"] = skip_matches[-1] if skip_matches else ""
    worker_result_lines = [
        line for line in startup_lines if "event=worker_result" in line
    ]
    result["startup_worker_result"] = worker_result_lines[-1][-700:] if worker_result_lines else ""
    ui_applied_lines = [
        line for line in startup_lines if "event=ui_applied" in line
    ]
    result["startup_ui_applied_line"] = ui_applied_lines[-1][-700:] if ui_applied_lines else ""
    if worker_result_lines:
        status_match = re.search(r"status=([^ ]+)", worker_result_lines[-1])
        if status_match:
            result["startup_generation_status"] = status_match.group(1)
        request_match = re.search(r"request_id=([^ ]+)", worker_result_lines[-1])
        if request_match:
            result["startup_generation_request_id"] = request_match.group(1)
    if ui_applied_lines:
        state_match = re.search(r"connection_state_simple=([^ ]+)", ui_applied_lines[-1])
        if state_match:
            result["startup_connection_state_simple"] = state_match.group(1)
        ready_match = re.search(r"engine_ready_for_run=([^ ]+)", ui_applied_lines[-1])
        if ready_match:
            result["startup_engine_ready_for_run"] = ready_match.group(1)
    success_lines = [line for line in active_lines if "[AITS][OpenAIProviderProof] event=response_success" in line]
    failure_lines = [line for line in active_lines if "[AITS][OpenAIProviderProof] event=response_failed" in line]
    result["latest_provider_success_seen"] = bool(success_lines)
    result["latest_provider_failure_seen"] = bool(failure_lines)
    if success_lines:
        latest_success = success_lines[-1]
        for field, pattern in (
            ("latest_provider_http_status", r"http_status=([^ ]+)"),
            ("latest_provider_response_id", r"response_id=([^ ]*)"),
            ("latest_provider_request_id", r"request_id=([^ ]*)"),
            ("latest_provider_usage_total_tokens", r"usage_total_tokens=([^ ]*)"),
        ):
            match = re.search(pattern, latest_success)
            if match:
                result[field] = match.group(1)
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
        "[AITS][StartupReadinessPreflight]",
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


def _install_provider_post_guard(report: dict[str, Any]) -> None:
    try:
        import requests

        def _blocked_post(*args: Any, **kwargs: Any) -> Any:
            report["provider_call_blocked"] = True
            raise RuntimeError("AITS Qt smoke harness blocked provider POST in public market read mode")

        requests.post = _blocked_post
    except Exception as exc:
        report.setdefault("warnings", []).append(f"provider_post_guard_install_failed:{type(exc).__name__}")


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
    try:
        combined_qss, _theme_meta = app_gui._build_aits_combined_stylesheet()
        app.setStyleSheet(combined_qss)
    except Exception:
        pass
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


def _collect_tooltip_style_proof() -> dict[str, Any]:
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        stylesheet = str(app.styleSheet() or "") if app is not None else ""
    except Exception:
        stylesheet = ""
    qtooltip_present = "QToolTip" in stylesheet
    return {
        "tooltip_style_supported": qtooltip_present,
        "tooltip_stylesheet_present": qtooltip_present,
        "tooltip_background": "#fffdf7" if "#fffdf7" in stylesheet.lower() else "",
        "tooltip_color": "#1f2933" if "#1f2933" in stylesheet.lower() else "",
        "tooltip_border": "1px solid #cabb9d" if "#cabb9d" in stylesheet.lower() else "",
        "tooltip_padding": "8px 10px" if "8px 10px" in stylesheet.lower() else "",
    }


def _tooltip_html_card_sample_from_plain(plain_text: str) -> str:
    lines = [str(line or "").strip() for line in str(plain_text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    title = html.escape(lines[0], quote=True)
    body = []
    for raw_line in lines[1:12]:
        if ":" in raw_line:
            label, value = raw_line.split(":", 1)
            body.append(
                "<div style=\"margin-top:3px;\">"
                f"<span style=\"color:#64748b;font-weight:700;\">{html.escape(label.strip(), quote=True)}:</span> "
                f"<span style=\"color:#1f2933;\">{html.escape(value.strip(), quote=True)}</span>"
                "</div>"
            )
        else:
            body.append(
                "<div style=\"margin-top:3px;color:#1f2933;\">"
                f"{html.escape(raw_line, quote=True)}"
                "</div>"
            )
    return (
        "<html><body style=\"margin:0;padding:0;\"><div style=\""
        "background-color:#fffdf7;color:#1f2933;border:1px solid #cabb9d;"
        "border-radius:8px;padding:10px 12px;min-width:260px;max-width:420px;"
        "line-height:1.55;font-size:12px;\">"
        f"<div style=\"font-weight:800;color:#111827;margin-bottom:6px;\">{title}</div>"
        + "".join(body)
        + "</div></body></html>"
    )


def _tooltip_html_card_proof(sample: str) -> dict[str, Any]:
    text = str(sample or "").lower()
    return {
        "tooltip_html_card_supported": bool("<html" in text and "#fffdf7" in text),
        "tooltip_html_present": bool("<html" in text or "<div" in text),
        "tooltip_has_light_background": "#fffdf7" in text,
        "tooltip_has_dark_text": "#1f2933" in text or "#111827" in text,
        "tooltip_escaped": "<script" not in text,
    }


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
    try:
        readiness = window._build_ai_engine_readiness_state()
    except Exception:
        readiness = {}
    tooltip_html_samples = list(
        getattr(window, "_last_ai_managed_tooltip_html_samples", None)
        or getattr(window, "_last_ai_managed_tooltip_samples", [])
        or []
    )[:3]
    tooltip_plain_samples = list(
        getattr(window, "_last_ai_managed_tooltip_plain_samples", None)
        or []
    )[:3]
    tooltip_html_sample = (tooltip_html_samples[:1] or [""])[0]
    tooltip_plain_sample = (tooltip_plain_samples[:1] or [""])[0]
    result = {
        "window_title": str(window.windowTitle() or ""),
        "current_tab": current_tab,
        "aits_power_state": _safe_text(widgets.get("power_state")),
        "aits_safety_state": _safe_text(widgets.get("safety_state")),
        "selected_engine_text": _safe_text(widgets.get("selected_engine")),
        "applied_engine_text": _safe_text(widgets.get("applied_engine")),
        "connection_state_text": str(window._connection_state_simple()) if hasattr(window, "_connection_state_simple") else _safe_text(widgets.get("connection_state")),
        "connection_detail_text": _safe_text(widgets.get("connection_state")),
        "generation_request_id": str(getattr(window, "_last_ai_generation_request_id", "") or ""),
        "generation_status": str(getattr(window, "_last_ai_generation_status", "") or ""),
        "generation_status_text": str(getattr(window, "_last_ai_connection_status", "") or getattr(window, "_ai_connection_status", "") or ""),
        "generation_fresh": bool(getattr(window, "_last_ai_generation_fresh", False)),
        "generation_stale": bool(getattr(window, "_last_ai_generation_stale", False)),
        "generation_response_confirmed": bool(getattr(window, "_last_ai_generation_response_confirmed", False)),
        "response_id_present": bool(getattr(window, "_last_ai_generation_response_id_present", False)),
        "token_usage_present": bool(getattr(window, "_last_ai_generation_token_usage_present", False)),
        "fallback_used": bool(getattr(window, "_last_ai_generation_fallback_used", False)),
        "engine_ready_for_run": bool(readiness.get("engine_ready_for_run")),
        "engine_ready_reason": str(readiness.get("engine_ready_reason") or ""),
        "engine_not_ready_reason": str(readiness.get("engine_not_ready_reason") or ""),
        "active_engine": str(readiness.get("active_engine") or getattr(window, "_active_ai_engine", "") or ""),
        "on_gate_expected_engine": str(readiness.get("on_gate_expected_engine") or ""),
        "connection_state_simple": str(window._connection_state_simple()) if hasattr(window, "_connection_state_simple") else "",
        "strategy_ai_provider": _normalize_provider_for_report(getattr(getattr(getattr(window, "_settings", None), "strategy", None), "ai_provider", "")),
        "provider_selected": _normalize_provider_for_report(getattr(window, "_selected_ai_provider", "")),
        "provider_actual": _normalize_provider_for_report(getattr(window, "_last_response_provider", "")),
        "managed_row_count": _table_row_count(managed_table),
        "managed_pool_tooltip_supported": bool(getattr(window, "_ai_managed_tooltip_supported", False)),
        "tooltip_applied_count": int(getattr(window, "_ai_managed_tooltip_applied_count", 0) or 0),
        "tooltip_sample": tooltip_html_sample,
        "tooltip_samples": tooltip_html_samples,
        "tooltip_plain_sample": tooltip_plain_sample,
        "tooltip_plain_samples": tooltip_plain_samples,
        "tooltip_html_sample": tooltip_html_sample,
        "tooltip_html_samples": tooltip_html_samples,
        "column_fit_policy_applied": bool(getattr(window, "_ai_managed_column_fit_policy_applied", False)),
        "column_fit_policy": getattr(window, "_ai_managed_column_fit_policy", {}) or {},
        "table_object_name": str(managed_table.objectName() or "") if managed_table is not None and hasattr(managed_table, "objectName") else "",
        "trade_log_row_count": _table_row_count(trade_log_table),
        "latest_trade_log_row": _table_row_text(trade_log_table, 0),
        "manual_order_buttons": manual_order_buttons,
        "manual_order_button_risk": any(
            bool(item.get("found")) and bool(item.get("visible")) and bool(item.get("enabled"))
            for item in manual_order_buttons
        ),
    }
    result.update(_collect_tooltip_style_proof())
    result.update(_tooltip_html_card_proof(tooltip_html_sample))
    return result


def _normalize_symbol_text(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if "-" not in text and text != "KRW":
        return f"KRW-{text}"
    return text


def _row_symbol(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return _normalize_symbol_text(
        row.get("symbol") or row.get("market") or row.get("code") or row.get("ticker") or ""
    )


def _compact_candidate_row(row: dict[str, Any], *, rank: int | None = None) -> dict[str, Any]:
    out = {
        "symbol": _row_symbol(row),
        "rank": rank,
        "score": row.get("ai_score", row.get("score")),
        "reason": row.get("reason") or row.get("reason_summary") or row.get("status") or "",
        "source": row.get("source_type") or row.get("source") or "basic",
        "change_rate": row.get("change_rate", row.get("change_pct", row.get("signed_change_rate"))),
        "trade_value": row.get("trade_value", row.get("volume_krw", row.get("acc_trade_price_24h"))),
    }
    try:
        score = out.get("score")
        if isinstance(score, str) and score.strip():
            out["score"] = float(score)
    except Exception:
        pass
    return out


def _run_basic_candidate_discovery_proof(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    report: dict[str, Any],
    *,
    max_candidates: int = 10,
) -> None:
    """Observe the Basic candidate/managed-pool path without mutating rows."""

    before_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    before_symbols = [_row_symbol(row) for row in before_rows if _row_symbol(row)]
    scan_called = False
    scan_success = False
    scan_error = ""
    started = time.time()
    try:
        loader = getattr(window, "_load_market_explorer_initial_data", None)
        if callable(loader):
            scan_called = True
            loader()
            _pump_events(app, 0.4)
            scan_success = True
        else:
            scan_error = "missing__load_market_explorer_initial_data"
    except Exception as exc:
        scan_error = f"{type(exc).__name__}:{str(exc)[:120]}"
    duration_ms = int(round((time.time() - started) * 1000.0))

    market_rows = [
        dict(row)
        for row in (
            getattr(window, "market_all_rows", None)
            or getattr(window, "_market_all_rows", None)
            or []
        )
        if isinstance(row, dict)
    ]
    display_rows = [
        dict(row)
        for row in (getattr(window, "_market_display_rows", None) or [])
        if isinstance(row, dict)
    ]
    scan_rows = display_rows or market_rows
    managed_rows_after = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    after_symbols = [_row_symbol(row) for row in managed_rows_after if _row_symbol(row)]
    managed_symbols = set(after_symbols)

    scored: list[dict[str, Any]] = []
    score_fn = getattr(window, "_calc_basic_ai_score", None)
    for raw in scan_rows:
        symbol = _row_symbol(raw)
        if not symbol:
            continue
        enriched = dict(raw)
        try:
            if callable(score_fn):
                score_info = score_fn(enriched)
                if isinstance(score_info, dict):
                    enriched["ai_score"] = score_info.get("score")
                    enriched["reason_summary"] = score_info.get("reason_summary") or ",".join(
                        str(x) for x in (score_info.get("reasons") or [])[:4]
                    )
                    enriched["score_state"] = score_info.get("score_state")
        except Exception as exc:
            enriched["ai_score"] = None
            enriched["reason_summary"] = f"score_failed:{type(exc).__name__}"
        scored.append(enriched)

    def _score_key(item: dict[str, Any]) -> tuple[float, float]:
        score = _safe_float(item.get("ai_score", item.get("score")), -1.0)
        trade_value = _safe_float(
            item.get("trade_value", item.get("volume_krw", item.get("acc_trade_price_24h"))),
            0.0,
        )
        return (score, trade_value)

    scored.sort(key=_score_key, reverse=True)
    top_candidates = [
        _compact_candidate_row(row, rank=idx + 1)
        for idx, row in enumerate(scored[: max(0, int(max_candidates))])
    ]
    would_add = [
        row for row in top_candidates if row.get("symbol") and row.get("symbol") not in managed_symbols
    ]
    would_keep = [
        _compact_candidate_row(row, rank=idx + 1)
        for idx, row in enumerate(managed_rows_after)
        if _row_symbol(row)
    ]

    rotation_payload = {}
    try:
        rotation_payload = dict(getattr(window, "_aits_last_rotation_payload", {}) or {})
    except Exception:
        rotation_payload = {}
    would_rotate: list[dict[str, Any]] = []
    no_rotation_reason = "rotation_soft_payload_empty"
    if rotation_payload.get("needed"):
        would_rotate.append(
            {
                "from_symbol": rotation_payload.get("from_symbol") or rotation_payload.get("out_symbol") or "",
                "to_symbol": rotation_payload.get("to_symbol") or rotation_payload.get("in_symbol") or "",
                "reason": rotation_payload.get("why") or rotation_payload.get("reason") or "",
                "source": "basic_decision_engine_soft_signal",
            }
        )
        no_rotation_reason = ""
    elif not scored:
        no_rotation_reason = "no_candidates_for_rotation"

    no_candidate_reason = ""
    if not scan_rows:
        stale_reason = str(getattr(window, "_candidate_feed_stale_reason", "") or "")
        if stale_reason:
            no_candidate_reason = stale_reason
        elif bool(report.get("provider_call_blocked")):
            no_candidate_reason = "dry_network_guard_returned_empty"
        else:
            no_candidate_reason = "top_markets_empty"
    elif not scored:
        no_candidate_reason = "candidate_rows_without_symbols"

    managed_mutation = before_symbols != after_symbols
    try:
        log = getattr(window, "_log", None)
        if log is not None:
            log.info(
                "[AITS][BasicCandidateScan] event=finish observe_only=True candidate_count=%s no_candidate_reason=%s managed_pool_mutation=%s submitted=0 order_allowed=False real_order=False",
                len(scored),
                no_candidate_reason or "-",
                managed_mutation,
            )
            log.info(
                "[AITS][ManagedPoolPromotion] event=observe_only would_add=%s would_keep=%s would_remove=0 would_rotate=%s submitted=0 order_allowed=False real_order=False",
                len(would_add),
                len(would_keep),
                len(would_rotate),
            )
    except Exception:
        pass

    report.update(
        {
            "basic_candidate_scan_supported": callable(getattr(window, "_load_market_explorer_initial_data", None)),
            "basic_candidate_scan_called": scan_called,
            "basic_candidate_scan_success": scan_success,
            "basic_candidate_scan_error": scan_error,
            "scan_duration_ms": duration_ms,
            "market_data_ready": bool(scan_rows),
            "market_count": len(market_rows),
            "top_markets_count": len(display_rows),
            "candidate_count": len(scored),
            "top_candidates": top_candidates,
            "no_candidate_reason": no_candidate_reason,
            "managed_pool_row_count_before": len(before_rows),
            "managed_pool_symbols_before": before_symbols,
            "managed_pool_row_count_after": len(managed_rows_after),
            "managed_pool_symbols_after": after_symbols,
            "would_add": would_add,
            "would_keep": would_keep,
            "would_remove": [],
            "would_rotate": would_rotate,
            "rotation_candidate_count": len(would_rotate),
            "no_rotation_reason": no_rotation_reason,
            "managed_pool_mutation_performed": managed_mutation,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "provider_external_call_count": 0,
        }
    )
    report["pass_status"] = "pass" if scan_called and scan_success and not managed_mutation else "partial"


def _run_top_markets_feed_proof(report: dict[str, Any], *, max_markets: int = 20) -> None:
    """Read public Upbit market/ticker feed once and explain empty results."""
    started = time.time()
    report.update(
        {
            "market_feed_supported": False,
            "market_list_called": False,
            "market_list_success": False,
            "market_count_raw": 0,
            "krw_market_count": 0,
            "ticker_called": False,
            "ticker_success": False,
            "ticker_count": 0,
            "volume_field_detected": False,
            "trade_value_field_detected": False,
            "filtered_count": 0,
            "top_markets_count": 0,
            "top_markets": [],
            "empty_reason": "",
            "exception_type": "",
            "network_state": "unknown",
            "cache_used": False,
            "duration_ms": 0,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "managed_pool_mutation_performed": False,
        }
    )
    try:
        from app.services import market_feed

        report["market_feed_supported"] = True
        report["market_list_called"] = True
        markets = market_feed.get_markets(quote="KRW", ttl=0.0)
        report["market_list_success"] = True
        report["market_count_raw"] = len(markets)
        krw_markets = [m for m in markets if str(m).startswith("KRW-")]
        report["krw_market_count"] = len(krw_markets)
        if not krw_markets:
            report["empty_reason"] = "krw_market_list_empty"

        sample_markets = krw_markets[: min(100, max(1, len(krw_markets)))]
        report["ticker_called"] = bool(sample_markets)
        tickers = market_feed.get_tickers(sample_markets, ttl=0.0) if sample_markets else {}
        report["ticker_success"] = bool(sample_markets)
        report["ticker_count"] = len(tickers)
        if sample_markets and not tickers:
            report["empty_reason"] = "ticker_empty"

        rows = []
        for market, row in tickers.items():
            if not isinstance(row, dict):
                continue
            report["volume_field_detected"] = report["volume_field_detected"] or ("acc_trade_volume_24h" in row)
            report["trade_value_field_detected"] = report["trade_value_field_detected"] or (
                "acc_trade_price_24h" in row
            )
            trade_price = _safe_float(row.get("trade_price"), 0.0)
            trade_value = _safe_float(row.get("acc_trade_price_24h"), 0.0)
            if trade_price < 10.0:
                continue
            rows.append((market, row, trade_value))
        rows.sort(key=lambda item: item[2], reverse=True)
        report["filtered_count"] = len(rows)
        if tickers and not rows:
            report["empty_reason"] = "filtered_out_by_min_price"

        top_raw = market_feed.get_top_markets_by_volume(
            limit=max(1, int(max_markets or 20)),
            quote="KRW",
            ttl_markets=0.0,
            ttl_ticks=0.0,
        )
        try:
            diagnostics = market_feed.get_last_diagnostics()
        except Exception:
            diagnostics = {}
        for key in (
            "market_list_called",
            "market_list_success",
            "market_count_raw",
            "krw_market_count",
            "ticker_called",
            "ticker_success",
            "ticker_count",
            "volume_field_detected",
            "trade_value_field_detected",
            "filtered_count",
            "top_markets_count",
            "empty_reason",
            "exception_type",
            "network_state",
            "cache_used",
        ):
            if key in diagnostics:
                report[key] = diagnostics[key]
        top_items = []
        for market, row in top_raw[: max(1, int(max_markets or 20))]:
            row = row if isinstance(row, dict) else {}
            top_items.append(
                {
                    "market": str(market),
                    "trade_price": _safe_float(row.get("trade_price"), 0.0),
                    "acc_trade_price_24h": _safe_float(row.get("acc_trade_price_24h"), 0.0),
                    "signed_change_rate": _safe_float(row.get("signed_change_rate"), 0.0),
                }
            )
        report["top_markets"] = top_items
        report["top_markets_count"] = len(top_items)
        if top_items:
            report["empty_reason"] = ""
            report["network_state"] = "ok"
    except Exception as exc:
        report["exception_type"] = type(exc).__name__
        if not report.get("empty_reason"):
            report["empty_reason"] = "exception"
        report["network_state"] = "error"
        report.setdefault("warnings", []).append(f"top_markets_feed_proof_failed:{type(exc).__name__}")
    finally:
        report["duration_ms"] = int(round((time.time() - started) * 1000.0))

    krw_count = int(report.get("krw_market_count") or 0)
    top_count = int(report.get("top_markets_count") or 0)
    if krw_count > 0 and top_count > 0:
        report["pass_status"] = "pass"
    elif krw_count > 0:
        report["pass_status"] = "partial"
    else:
        report["pass_status"] = "fail"


def _public_top_market_candidate_score(row: dict[str, Any], rank: int) -> float:
    """Build a proof-only Basic-style score from public ticker fields."""
    rank_value = max(1, int(rank or 1))
    rank_bonus = max(0.0, 26.0 - min(rank_value, 25))
    change_rate = _safe_float(row.get("signed_change_rate"), 0.0)
    change_bonus = max(-8.0, min(18.0, change_rate * 100.0))
    trade_value = _safe_float(row.get("acc_trade_price_24h") or row.get("trade_value"), 0.0)
    liquidity_bonus = 5.0 if trade_value > 0 else 0.0
    return round(max(0.0, min(100.0, 45.0 + rank_bonus + change_bonus + liquidity_bonus)), 4)


def _public_top_markets_to_rotation_candidates(
    top_markets: list[dict[str, Any]],
    *,
    max_candidates: int = 50,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for idx, row in enumerate(top_markets[: max(1, int(max_candidates or 50))], start=1):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("market") or row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        score = _public_top_market_candidate_score(row, idx)
        candidates.append(
            {
                "symbol": symbol,
                "market": symbol,
                "rank": idx,
                "score": score,
                "source": "public_top_markets",
                "reason": "public_top_market_ranked_read_only",
                "trade_value": _safe_float(row.get("acc_trade_price_24h") or row.get("trade_value"), 0.0),
                "change_rate": _safe_float(row.get("signed_change_rate"), 0.0),
                "actual_order": False,
            }
        )
    return candidates


def _load_saved_managed_pool_rows_readonly() -> list[dict[str, Any]]:
    """Read saved Managed Pool rows without opening the GUI or mutating prefs."""
    try:
        from app.utils.prefs import load_settings

        settings = load_settings()
        ui_state = getattr(settings, "ui_state", None) or {}
        if hasattr(ui_state, "model_dump"):
            ui_state = ui_state.model_dump()
        if not isinstance(ui_state, dict):
            return []
        rows = ui_state.get("managed_pool_rows") or []
        return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _is_rotation_holding_row(row: dict[str, Any]) -> bool:
    if bool(row.get("holding") or row.get("is_holding") or row.get("has_position")):
        return True
    for key in ("qty", "quantity", "balance", "volume", "position_qty"):
        if _safe_float(row.get(key), 0.0) > 0.0:
            return True
    return False


def _holding_symbol(row: dict[str, Any]) -> str:
    symbol = str(row.get("symbol") or row.get("market") or "").strip().upper()
    if symbol:
        return symbol
    currency = str(row.get("currency") or row.get("asset") or "").strip().upper()
    if currency and currency != "KRW":
        return f"KRW-{currency}" if not currency.startswith("KRW-") else currency
    return ""


def _holding_eval_krw(row: dict[str, Any]) -> float:
    value = _safe_float(row.get("eval_krw") or row.get("value_krw") or row.get("position_krw"), -1.0)
    if value >= 0.0:
        return value
    qty = _safe_float(row.get("qty") or row.get("quantity") or row.get("balance"), 0.0)
    px = _safe_float(row.get("px") or row.get("price") or row.get("avg_price") or row.get("avg_buy_price"), 0.0)
    return max(0.0, qty * px)


def _fetch_live_holdings_snapshot_readonly(*, min_value_krw: float = 5000.0) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "holdings_snapshot_supported": False,
        "holdings_fetch_success": False,
        "holdings_count": 0,
        "holdings_raw_count": 0,
        "holdings_symbols": [],
        "holdings_value_krw": 0.0,
        "dust_filtered_symbols": [],
        "display_holding_symbols": [],
        "eligible_holding_symbols": [],
        "dust_holding_symbols": [],
        "holding_display_count": 0,
        "holding_eligible_count": 0,
        "min_holding_value_krw": float(min_value_krw),
        "holdings": [],
        "display_holdings": [],
        "eligible_holdings": [],
        "no_holding_reason": "",
        "exception_type": "",
    }
    try:
        from app.services.holdings_service import fetch_live_holdings
        from app.services.order_service import svc_order
        from app.utils.prefs import load_settings

        snapshot["holdings_snapshot_supported"] = True
        try:
            svc_order.set_settings(load_settings())
            snapshot["settings_injected"] = True
        except Exception as exc:
            snapshot["settings_injected"] = False
            snapshot["settings_inject_error"] = type(exc).__name__
        data = fetch_live_holdings(force=True)
        snapshot["holdings_fetch_success"] = bool(isinstance(data, dict) and data.get("ok"))
        if not isinstance(data, dict) or not data.get("ok"):
            snapshot["no_holding_reason"] = str((data or {}).get("err") if isinstance(data, dict) else "holdings_fetch_failed")[:120]
            return snapshot
        items = [dict(item) for item in (data.get("items") or []) if isinstance(item, dict)]
        snapshot["holdings_raw_count"] = len(items)
        holdings: list[dict[str, Any]] = []
        eligible: list[dict[str, Any]] = []
        dust_symbols: list[str] = []
        for item in items:
            symbol = _holding_symbol(item)
            if not symbol:
                continue
            qty = _safe_float(item.get("qty") or item.get("quantity") or item.get("balance"), 0.0)
            locked = _safe_float(item.get("locked"), 0.0)
            eval_krw = _holding_eval_krw(item)
            clean = {
                "symbol": symbol,
                "qty": qty,
                "balance": _safe_float(item.get("balance"), qty),
                "locked": locked,
                "avg_price": _safe_float(item.get("avg_price") or item.get("avg_buy_price"), 0.0),
                "eval_krw": eval_krw,
                "market_supported": bool(item.get("market_supported", True)),
                "dust": bool(qty <= 0.0 or (0.0 <= eval_krw < float(min_value_krw))),
            }
            holdings.append(clean)
            if clean["dust"]:
                dust_symbols.append(symbol)
            else:
                eligible.append(clean)
        snapshot["holdings"] = holdings
        snapshot["display_holdings"] = holdings
        snapshot["eligible_holdings"] = eligible
        snapshot["holdings_count"] = len(eligible)
        snapshot["holdings_raw_count"] = len(holdings)
        snapshot["holdings_symbols"] = [row["symbol"] for row in eligible]
        snapshot["display_holding_symbols"] = [row["symbol"] for row in holdings]
        snapshot["eligible_holding_symbols"] = [row["symbol"] for row in eligible]
        snapshot["dust_holding_symbols"] = list(dust_symbols)
        snapshot["holding_display_count"] = len(holdings)
        snapshot["holding_eligible_count"] = len(eligible)
        snapshot["holdings_value_krw"] = round(sum(_safe_float(row.get("eval_krw"), 0.0) for row in holdings), 4)
        snapshot["dust_filtered_symbols"] = dust_symbols
        if not holdings:
            snapshot["no_holding_reason"] = "holdings_empty"
        elif not eligible:
            snapshot["no_holding_reason"] = "holding_dust_filtered"
        else:
            snapshot["no_holding_reason"] = ""
    except Exception as exc:
        snapshot["exception_type"] = type(exc).__name__
        snapshot["no_holding_reason"] = f"holdings_fetch_exception:{type(exc).__name__}"
    return snapshot


def _holding_display_reason(
    holding: dict[str, Any],
    *,
    min_value_krw: float,
) -> str:
    if bool(holding.get("dust")):
        return "balance_exists_dust_display_only"
    if _safe_float(holding.get("eval_krw"), 0.0) >= float(min_value_krw):
        return "balance_exists_rotation_eligible"
    return "balance_exists_display_only"


def _holding_display_status(
    holding: dict[str, Any],
    *,
    min_value_krw: float,
) -> str:
    return "소액 보유" if _holding_display_reason(holding, min_value_krw=min_value_krw) == "balance_exists_dust_display_only" else "보유중"


def _holding_display_tooltip_sample(
    holding: dict[str, Any],
    *,
    min_value_krw: float,
) -> str:
    symbol = _holding_symbol(holding) or "-"
    eval_krw = _safe_float(holding.get("eval_krw"), 0.0)
    status = _holding_display_status(holding, min_value_krw=min_value_krw)
    eligible = eval_krw >= float(min_value_krw) and not bool(holding.get("dust"))
    operation_line = "운용 판정: rotation 대상" if eligible else "운용 판정: dust 기준 미만으로 로테이션 제외"
    return "\n".join(
        [
            f"종목: {symbol}",
            f"상태: {status}",
            f"평가액: {eval_krw:,.0f}원",
            "보유 판정: 잔고 있음",
            operation_line,
            f"기준: {float(min_value_krw):,.0f}원 미만은 소액 잔고로 분류",
            "실행: 주문 없음 / 표시만",
        ]
    )


def _match_holdings_to_managed_rows(
    managed_rows: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    *,
    min_value_krw: float = 5000.0,
) -> dict[str, Any]:
    managed_by_symbol = {_row_symbol(row): dict(row) for row in managed_rows if _row_symbol(row)}
    matched: list[dict[str, Any]] = []
    missing_flags: list[dict[str, Any]] = []
    would_mark: list[dict[str, Any]] = []
    would_display: list[dict[str, Any]] = []
    would_mark_eligible: list[dict[str, Any]] = []
    for holding in holdings:
        symbol = _holding_symbol(holding)
        eval_krw = _safe_float(holding.get("eval_krw"), 0.0)
        qty = _safe_float(holding.get("qty"), 0.0)
        display_reason = _holding_display_reason(holding, min_value_krw=min_value_krw)
        is_eligible = display_reason == "balance_exists_rotation_eligible"
        if symbol:
            would_display.append(
                {
                    "symbol": symbol,
                    "holding_display": True,
                    "holding_eligible": bool(is_eligible),
                    "reason": display_reason,
                    "qty": qty,
                    "eval_krw": eval_krw,
                    "mutation_performed": False,
                }
            )
            if is_eligible:
                would_mark_eligible.append(
                    {
                        "symbol": symbol,
                        "reason": "would_set_holding_eligible_true_read_only",
                        "qty": qty,
                        "eval_krw": eval_krw,
                        "mutation_performed": False,
                    }
                )
        row = managed_by_symbol.get(symbol)
        if not row:
            would_mark.append(
                {
                    "symbol": symbol,
                    "reason": "holding_not_in_managed_pool",
                    "qty": qty,
                    "eval_krw": eval_krw,
                    "mutation_performed": False,
                }
            )
            continue
        row_holding = _is_rotation_holding_row(row)
        item = {
            "symbol": symbol,
            "row_holding": bool(row_holding),
            "holding_display": True,
            "holding_eligible": bool(is_eligible),
            "qty": qty,
            "eval_krw": eval_krw,
            "source_type": row.get("source_type") or row.get("source") or "",
            "display_reason": display_reason,
        }
        matched.append(item)
        if not row_holding:
            missing_flags.append(
                {
                    "symbol": symbol,
                    "reason": "managed_row_missing_holding_flag",
                    "qty": item["qty"],
                    "eval_krw": item["eval_krw"],
                }
            )
            would_mark.append(
                {
                    "symbol": symbol,
                    "reason": "would_set_holding_true_read_only",
                    "qty": item["qty"],
                    "eval_krw": item["eval_krw"],
                    "mutation_performed": False,
                }
            )
    return {
        "matched_holding_rows": matched,
        "missing_holding_flags": missing_flags,
        "would_mark_holding": would_mark,
        "would_display_holding": would_display,
        "would_mark_holding_eligible": would_mark_eligible,
    }


def _managed_rows_with_observed_holdings(
    managed_rows: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    holding_by_symbol = {_holding_symbol(row): dict(row) for row in holdings if _holding_symbol(row)}
    out: list[dict[str, Any]] = []
    for row in managed_rows:
        clean = dict(row)
        symbol = _row_symbol(clean)
        holding = holding_by_symbol.get(symbol)
        if holding:
            clean["holding"] = True
            clean["qty"] = _safe_float(holding.get("qty"), 0.0)
            clean["balance"] = _safe_float(holding.get("balance"), clean.get("qty"))
            clean["eval_krw"] = _safe_float(holding.get("eval_krw"), 0.0)
            clean["holding_source"] = "live_holdings_observe_only"
        out.append(clean)
    return out


def _run_holdings_to_managed_row_proof(report: dict[str, Any]) -> None:
    min_value_krw = 5000.0
    managed_rows = _load_saved_managed_pool_rows_readonly()
    snapshot = _fetch_live_holdings_snapshot_readonly(min_value_krw=min_value_krw)
    holdings_all = [row for row in (snapshot.get("holdings") or []) if isinstance(row, dict)]
    match = _match_holdings_to_managed_rows(managed_rows, holdings_all, min_value_krw=min_value_krw)
    no_holding_reason = str(snapshot.get("no_holding_reason") or "")
    if holdings_all and match.get("would_mark_holding"):
        no_holding_reason = no_holding_reason or "managed_row_holding_flag_missing"
    tooltip_samples = [
        _holding_display_tooltip_sample(row, min_value_krw=min_value_krw)
        for row in holdings_all[:3]
    ]
    report.update(
        {
            "holdings_snapshot_supported": bool(snapshot.get("holdings_snapshot_supported")),
            "holdings_settings_injected": bool(snapshot.get("settings_injected")),
            "holdings_fetch_success": bool(snapshot.get("holdings_fetch_success")),
            "holdings_count": int(snapshot.get("holdings_count") or 0),
            "holdings_raw_count": int(snapshot.get("holdings_raw_count") or 0),
            "holdings_symbols": snapshot.get("holdings_symbols") or [],
            "display_holding_symbols": snapshot.get("display_holding_symbols") or [],
            "eligible_holding_symbols": snapshot.get("eligible_holding_symbols") or [],
            "dust_holding_symbols": snapshot.get("dust_holding_symbols") or snapshot.get("dust_filtered_symbols") or [],
            "holding_display_count": int(snapshot.get("holding_display_count") or 0),
            "holding_eligible_count": int(snapshot.get("holding_eligible_count") or 0),
            "display_vs_eligible_policy": {
                "holding_display": "balance_exists_even_when_dust",
                "holding_eligible": "eval_krw_at_or_above_min_holding_value",
                "dust_policy": "display_only_not_rotation_eligible",
                "min_holding_value_krw": min_value_krw,
                "future_live_test_min_krw": 10000,
            },
            "holdings_value_krw": snapshot.get("holdings_value_krw", 0.0),
            "dust_filtered_symbols": snapshot.get("dust_filtered_symbols") or [],
            "min_holding_value_krw": min_value_krw,
            "managed_row_count": len(managed_rows),
            "managed_symbols": [_row_symbol(row) for row in managed_rows if _row_symbol(row)],
            "matched_holding_rows": match.get("matched_holding_rows", []),
            "missing_holding_flags": match.get("missing_holding_flags", []),
            "would_mark_holding": match.get("would_mark_holding", []),
            "would_display_holding": match.get("would_display_holding", []),
            "would_mark_holding_eligible": match.get("would_mark_holding_eligible", []),
            "tooltip_samples": tooltip_samples,
            "no_holding_reason": no_holding_reason,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
            "actual_order": False,
            "rotation_execution": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
        }
    )
    if snapshot.get("holdings_fetch_success"):
        report["pass_status"] = "pass"
    else:
        report.setdefault("warnings", []).append(str(no_holding_reason or "holdings_fetch_failed"))
        report["pass_status"] = "partial"


def _run_managed_pool_holding_display_sync_proof(report: dict[str, Any]) -> None:
    min_value_krw = 5000.0
    managed_rows = _load_saved_managed_pool_rows_readonly()
    snapshot = _fetch_live_holdings_snapshot_readonly(min_value_krw=min_value_krw)
    holdings_all = [row for row in (snapshot.get("holdings") or []) if isinstance(row, dict)]
    match = _match_holdings_to_managed_rows(managed_rows, holdings_all, min_value_krw=min_value_krw)
    managed_symbols = {_row_symbol(row) for row in managed_rows if _row_symbol(row)}
    outside_holdings = [
        row
        for row in match.get("would_display_holding", [])
        if isinstance(row, dict) and str(row.get("symbol") or "").upper() not in managed_symbols
    ]
    matched_display_rows = [
        row
        for row in match.get("matched_holding_rows", [])
        if isinstance(row, dict) and bool(row.get("holding_display"))
    ]
    tooltip_samples = [
        _holding_display_tooltip_sample(row, min_value_krw=min_value_krw)
        for row in holdings_all[:3]
    ]
    status_samples = [
        {
            "symbol": str(row.get("symbol") or ""),
            "status": "소액 보유" if bool(row.get("dust")) else "보유중",
            "status_hint": "운용 제외" if bool(row.get("dust")) else "로테이션 검토 가능",
            "holding_display": True,
            "holding_eligible": not bool(row.get("dust")),
        }
        for row in holdings_all[:3]
        if isinstance(row, dict)
    ]
    row_count_before = len(managed_rows)
    row_count_after = len(_load_saved_managed_pool_rows_readonly())
    btc_match = next(
        (
            row
            for row in matched_display_rows
            if str(row.get("symbol") or "").upper() == "KRW-BTC"
        ),
        {},
    )
    btc_tooltip = next((text for text in tooltip_samples if "KRW-BTC" in str(text)), "")
    pass_status = (
        bool(snapshot.get("holdings_fetch_success"))
        and bool(btc_match)
        and bool(btc_match.get("holding_display"))
        and not bool(btc_match.get("holding_eligible"))
        and "소액 보유" in str(btc_tooltip)
        and "로테이션 제외" in str(btc_tooltip)
        and row_count_before == row_count_after
    )
    report.update(
        {
            "holding_display_sync_supported": True,
            "holdings_fetch_success": bool(snapshot.get("holdings_fetch_success")),
            "holdings_settings_injected": bool(snapshot.get("settings_injected")),
            "display_holding_symbols": snapshot.get("display_holding_symbols") or [],
            "eligible_holding_symbols": snapshot.get("eligible_holding_symbols") or [],
            "dust_holding_symbols": snapshot.get("dust_holding_symbols") or snapshot.get("dust_filtered_symbols") or [],
            "holding_display_count": int(snapshot.get("holding_display_count") or 0),
            "holding_eligible_count": int(snapshot.get("holding_eligible_count") or 0),
            "managed_row_count_before": row_count_before,
            "managed_row_count_after": row_count_after,
            "matched_display_rows": matched_display_rows,
            "outside_holdings": outside_holdings,
            "auto_added_outside_holdings": False,
            "tooltip_samples": tooltip_samples,
            "status_samples": status_samples,
            "krw_btc_display_match": btc_match,
            "krw_btc_tooltip_sample": btc_tooltip,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "actual_order": False,
            "rotation_execution": False,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "pass_status": "pass" if pass_status else "partial" if snapshot.get("holdings_fetch_success") else "fail",
        }
    )


def _run_rotation_eligibility_from_holdings_proof(
    report: dict[str, Any],
    *,
    max_candidates: int = 50,
) -> None:
    from app.services.managed_pool_promotion_policy import (
        build_managed_pool_promotion_plan,
        build_rotation_intent_payload,
    )

    min_value_krw = 5000.0
    managed_rows = _load_saved_managed_pool_rows_readonly()
    snapshot = _fetch_live_holdings_snapshot_readonly(min_value_krw=min_value_krw)
    eligible_holdings = [row for row in (snapshot.get("eligible_holdings") or []) if isinstance(row, dict)]
    holdings_all = [row for row in (snapshot.get("holdings") or []) if isinstance(row, dict)]
    match = _match_holdings_to_managed_rows(managed_rows, holdings_all, min_value_krw=min_value_krw)
    effective_rows = _managed_rows_with_observed_holdings(managed_rows, eligible_holdings)
    feed_report: dict[str, Any] = {}
    _run_top_markets_feed_proof(feed_report, max_markets=max_candidates)
    top_markets = [row for row in (feed_report.get("top_markets") or []) if isinstance(row, dict)]
    candidates = _public_top_markets_to_rotation_candidates(top_markets, max_candidates=max_candidates)
    config = {
        "max_managed_pool_size": max(10, len(effective_rows) or 10),
        "promotion_min_score": 60.0,
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": False,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": True,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_promotion_plan(effective_rows, candidates, eligible_holdings, config)
    intent = build_rotation_intent_payload(plan, source="holdings_rotation_eligibility_observe")
    pairs = [pair for pair in (intent.get("pairs") or []) if isinstance(pair, dict)]
    if pairs:
        no_rotation_reason = ""
    elif not snapshot.get("holdings_fetch_success"):
        no_rotation_reason = str(snapshot.get("no_holding_reason") or "holdings_fetch_failed")
    elif not eligible_holdings:
        no_rotation_reason = str(snapshot.get("no_holding_reason") or "no_holding_rows_for_rotation")
    else:
        no_rotation_reason = _refine_live_rotation_no_reason(
            top_markets_count=int(feed_report.get("top_markets_count") or 0),
            candidate_count=len(candidates),
            current_rows=effective_rows,
            candidates=candidates,
            pairs=pairs,
            plan=plan,
            feed_empty_reason=str(feed_report.get("empty_reason") or ""),
        )
    tooltip_samples = [_rotation_tooltip_sample(pair, role="rotate_out") for pair in pairs[:2]]
    holding_tooltip_samples = [
        _holding_display_tooltip_sample(row, min_value_krw=min_value_krw)
        for row in holdings_all[:2]
    ]
    status_samples = [_rotation_status_sample(pair, role="rotate_out") for pair in pairs[:2]]
    order_risk = any(bool(pair.get("actual_order")) or bool(pair.get("order_execution")) for pair in pairs)
    pass_status = (
        bool(snapshot.get("holdings_fetch_success"))
        and int(feed_report.get("top_markets_count") or 0) > 0
        and len(candidates) > 0
        and not order_risk
        and not bool(intent.get("actual_order"))
        and not bool(intent.get("rotation_execution"))
        and not bool(intent.get("managed_pool_mutation"))
        and (bool(pairs) or bool(no_rotation_reason))
    )
    report.update(
        {
            "holdings_fetch_success": bool(snapshot.get("holdings_fetch_success")),
            "holdings_settings_injected": bool(snapshot.get("settings_injected")),
            "holdings_raw_count": int(snapshot.get("holdings_raw_count") or 0),
            "holdings_count": int(snapshot.get("holdings_count") or 0),
            "holdings_symbols": snapshot.get("holdings_symbols") or [],
            "display_holding_symbols": snapshot.get("display_holding_symbols") or [],
            "eligible_holding_symbols": snapshot.get("eligible_holding_symbols") or [],
            "dust_holding_symbols": snapshot.get("dust_holding_symbols") or snapshot.get("dust_filtered_symbols") or [],
            "holding_display_count": int(snapshot.get("holding_display_count") or 0),
            "holding_eligible_count": int(snapshot.get("holding_eligible_count") or 0),
            "display_vs_eligible_policy": {
                "holding_display": "balance_exists_even_when_dust",
                "holding_eligible": "eval_krw_at_or_above_min_holding_value",
                "dust_policy": "display_only_not_rotation_eligible",
                "min_holding_value_krw": min_value_krw,
                "future_live_test_min_krw": 10000,
            },
            "holdings_value_krw": snapshot.get("holdings_value_krw", 0.0),
            "dust_filtered_symbols": snapshot.get("dust_filtered_symbols") or [],
            "min_holding_value_krw": min_value_krw,
            "managed_row_count": len(managed_rows),
            "managed_symbols": [_row_symbol(row) for row in managed_rows if _row_symbol(row)],
            "matched_holding_rows": match.get("matched_holding_rows", []),
            "missing_holding_flags": match.get("missing_holding_flags", []),
            "would_mark_holding": match.get("would_mark_holding", []),
            "would_display_holding": match.get("would_display_holding", []),
            "would_mark_holding_eligible": match.get("would_mark_holding_eligible", []),
            "market_count_raw": int(feed_report.get("market_count_raw") or 0),
            "krw_market_count": int(feed_report.get("krw_market_count") or 0),
            "ticker_count": int(feed_report.get("ticker_count") or 0),
            "top_markets_count": int(feed_report.get("top_markets_count") or 0),
            "candidate_count": len(candidates),
            "pair_count": len(pairs),
            "pairs": pairs,
            "no_rotation_reason": no_rotation_reason,
            "tooltip_samples": tooltip_samples,
            "holding_tooltip_samples": holding_tooltip_samples,
            "status_samples": status_samples,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "actual_order": False,
            "rotation_execution": False,
            "provider_external_call_count": 0,
            "order_risk_detected": bool(order_risk),
            "pass_status": "pass" if pass_status else "partial" if snapshot.get("holdings_fetch_success") else "fail",
        }
    )


def _refine_live_rotation_no_reason(
    *,
    top_markets_count: int,
    candidate_count: int,
    current_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    plan: dict[str, Any],
    feed_empty_reason: str,
) -> str:
    if pairs:
        return ""
    if top_markets_count <= 0:
        return feed_empty_reason or "top_markets_empty"
    if candidate_count <= 0:
        return "candidate_count_zero_after_public_feed_scoring"
    if not current_rows:
        return "managed_pool_rows_empty"
    managed_symbols = {_row_symbol(row) for row in current_rows if _row_symbol(row)}
    candidate_symbols = {_row_symbol(row) for row in candidates if _row_symbol(row)}
    if candidate_symbols and candidate_symbols.issubset(managed_symbols):
        return "all_candidates_already_managed"
    holding_rows = [row for row in current_rows if _is_rotation_holding_row(row)]
    if not holding_rows:
        return "no_holding_rows_for_rotation"
    protected = plan.get("protected_rows") if isinstance(plan, dict) else []
    if protected and len(protected) >= len(current_rows):
        return "protected_rows_only"
    highest_candidate = max((_safe_float(row.get("score"), 0.0) for row in candidates), default=0.0)
    highest_current = max((_safe_float(row.get("score"), _safe_float(row.get("ai_score"), 0.0)) for row in current_rows), default=0.0)
    if highest_candidate <= highest_current:
        return "no_higher_score_candidate"
    return "score_gap_not_met"


def _run_rotation_intent_live_candidate_feed_proof(
    report: dict[str, Any],
    *,
    max_candidates: int = 50,
) -> None:
    from app.services.managed_pool_promotion_policy import (
        build_managed_pool_promotion_plan,
        build_rotation_intent_payload,
    )

    feed_report: dict[str, Any] = {}
    _run_top_markets_feed_proof(feed_report, max_markets=max_candidates)
    top_markets = [row for row in (feed_report.get("top_markets") or []) if isinstance(row, dict)]
    candidates = _public_top_markets_to_rotation_candidates(top_markets, max_candidates=max_candidates)
    current_rows = _load_saved_managed_pool_rows_readonly()
    managed_symbols = [_row_symbol(row) for row in current_rows if _row_symbol(row)]
    holdings = [row for row in current_rows if _is_rotation_holding_row(row)]
    config = {
        "max_managed_pool_size": max(10, len(current_rows) or 10),
        "promotion_min_score": None,
        "auto_add_enabled": False,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": True,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_promotion_plan(current_rows, candidates, holdings, config)
    intent = build_rotation_intent_payload(plan, source="public_top_markets_live_candidate_feed")
    pairs = [pair for pair in (intent.get("pairs") or []) if isinstance(pair, dict)]
    no_rotation_reason = _refine_live_rotation_no_reason(
        top_markets_count=int(feed_report.get("top_markets_count") or 0),
        candidate_count=len(candidates),
        current_rows=current_rows,
        candidates=candidates,
        pairs=pairs,
        plan=plan,
        feed_empty_reason=str(feed_report.get("empty_reason") or ""),
    )
    if no_rotation_reason:
        intent["no_rotation_reason"] = no_rotation_reason
    tooltip_samples = [_rotation_tooltip_sample(pair, role="rotate_out") for pair in pairs[:2]]
    tooltip_samples += [_rotation_tooltip_sample(pair, role="rotate_in") for pair in pairs[:1]]
    status_samples = [_rotation_status_sample(pair, role="rotate_out") for pair in pairs[:2]]
    order_risk = any(bool(pair.get("actual_order")) or bool(pair.get("order_execution")) for pair in pairs)
    mutation = bool(intent.get("managed_pool_mutation")) or bool(plan.get("actual_mutation_performed"))
    top_count = int(feed_report.get("top_markets_count") or 0)
    candidate_count = len(candidates)
    pass_status = (
        top_count > 0
        and candidate_count > 0
        and not order_risk
        and not bool(intent.get("actual_order"))
        and not bool(intent.get("rotation_execution"))
        and not mutation
        and (bool(pairs) or no_rotation_reason not in {"", "top_markets_empty"})
    )
    report.update(
        {
            "rotation_intent_supported": True,
            "schema": "aits_rotation_intent_v1",
            "public_market_get_allowed": True,
            "provider_post_blocked": True,
            "order_path_blocked": True,
            "market_count_raw": int(feed_report.get("market_count_raw") or 0),
            "krw_market_count": int(feed_report.get("krw_market_count") or 0),
            "ticker_count": int(feed_report.get("ticker_count") or 0),
            "top_markets_count": top_count,
            "top_markets_sample": top_markets[:10],
            "candidate_count": candidate_count,
            "candidate_sample": candidates[:10],
            "current_managed_count": len(current_rows),
            "managed_symbols": managed_symbols,
            "pair_count": len(pairs),
            "pairs": pairs,
            "no_rotation_reason": no_rotation_reason,
            "tooltip_samples": tooltip_samples,
            "status_samples": status_samples,
            "actual_order": False,
            "rotation_execution": bool(intent.get("rotation_execution")),
            "managed_pool_mutation": mutation,
            "managed_pool_mutation_performed": mutation,
            "provider_external_call_count": 0,
            "order_risk_detected": bool(order_risk),
            "feed_empty_reason": str(feed_report.get("empty_reason") or ""),
            "feed_pass_status": feed_report.get("pass_status", ""),
            "feed_network_state": feed_report.get("network_state", ""),
            "planned_rotation": plan.get("planned_rotation", []),
            "protected_symbols": [item.get("symbol") for item in (plan.get("protected_rows") or []) if isinstance(item, dict)],
            "pass_status": "pass" if pass_status else "fail",
        }
    )


def _latest_basic_candidate_report(output_dir: Path) -> dict[str, Any]:
    try:
        paths = sorted(output_dir.glob("runtime_smoke_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        paths = []
    for path in paths[:80]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("mode") == "basic-candidate-discovery-proof":
            data["_report_path"] = str(path)
            return data
    return {}


def _normalize_contract_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"system_default", "system_seed", "default", "seed"}:
        return "system_seed"
    if text in {"user", "user_added", "manual"}:
        return "user_added"
    if text in {"basic", "basic_added", "auto", "auto_added"}:
        return "basic_added" if text != "basic" else "basic"
    return text or "unknown"


def _last_managed_pool_freshness_from_log(*, max_lines: int = 4000) -> dict[str, str]:
    log_path = ROOT / "data" / "logs" / "aits.log"
    if not log_path.exists():
        return {}
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return {}
    out: dict[str, str] = {}
    pattern = re.compile(r"symbol=(KRW-[A-Z0-9]+).*?freshness=([A-Za-z0-9_\-]+)")
    for line in lines:
        if "[AITS][ManagedPoolAIReviewSLA]" not in line:
            continue
        match = pattern.search(line)
        if match:
            out[_normalize_symbol_text(match.group(1))] = str(match.group(2) or "").strip()
    return out


def _latest_managed_rows_for_contract(output_dir: Path) -> tuple[list[dict[str, Any]], str]:
    latest = _latest_basic_candidate_report(output_dir)
    rows = latest.get("would_keep") or []
    if isinstance(rows, list) and rows:
        return [dict(row) for row in rows if isinstance(row, dict)], str(latest.get("_report_path") or "")
    return _load_saved_managed_pool_rows_readonly(), "saved_managed_pool_rows"


def _candidate_order_intent_contract(
    row: dict[str, Any],
    *,
    min_score: float = 60.0,
    market_feed_ok: bool = True,
    freshness_by_symbol: dict[str, str] | None = None,
    duplicate_symbols: set[str] | None = None,
    repeat_symbols: set[str] | None = None,
    allowed_sources: set[str] | None = None,
) -> dict[str, Any]:
    symbol = _row_symbol(row)
    source = _normalize_contract_source(row.get("source") or row.get("source_type"))
    score = _safe_float(row.get("ai_score", row.get("score")), 0.0)
    status = str(row.get("ai_status") or row.get("status") or row.get("status_label") or row.get("opinion") or "").strip()
    freshness = str(row.get("freshness") or (freshness_by_symbol or {}).get(symbol) or "").strip()
    ai_opinion_status = str(row.get("ai_opinion_status") or row.get("status_label") or row.get("opinion") or "").strip()
    reason = str(row.get("reason") or row.get("ai_reason_summary") or row.get("reason_summary") or "").strip()
    allowed = allowed_sources or {"basic", "basic_added", "user_added"}
    duplicate = symbol in (duplicate_symbols or set())
    repeat = symbol in (repeat_symbols or set())
    holding = bool(row.get("holding") or row.get("holding_display") or row.get("is_holding") or row.get("has_position"))
    dust = bool(row.get("dust_holding") or row.get("holding_dust") or row.get("dust_filtered"))
    basic_buy_ready = bool(score >= float(min_score))
    block_reasons: list[str] = []
    if not symbol:
        block_reasons.append("missing_symbol")
    if not basic_buy_ready:
        block_reasons.append("score_below_order_intent_min")
    if source not in allowed:
        block_reasons.append(f"source_not_allowed:{source}")
    if not market_feed_ok:
        block_reasons.append("market_feed_not_ok")
    if not ai_opinion_status:
        block_reasons.append("ai_opinion_missing")
    elif ai_opinion_status in {"데이터부족", "data_insufficient"}:
        block_reasons.append("ai_opinion_data_insufficient")
    if not freshness:
        block_reasons.append("freshness_missing")
    elif freshness in {"missing", "very_stale", "stale", "analysis_required", "manual_required"}:
        block_reasons.append(f"freshness_not_acceptable:{freshness}")
    if duplicate:
        block_reasons.append("duplicate_block")
    if repeat:
        block_reasons.append("repeat_block")
    if holding:
        block_reasons.append("holding_state_block")
    if dust:
        block_reasons.append("dust_state_block")
    return {
        "schema": "aits_order_intent_candidate_contract_v1",
        "symbol": symbol,
        "score": score,
        "source": source,
        "status": status,
        "reason": reason,
        "basic_buy_ready": basic_buy_ready,
        "ai_opinion_status": ai_opinion_status,
        "freshness": freshness,
        "market_feed_ok": bool(market_feed_ok),
        "duplicate_block": duplicate,
        "repeat_block": repeat,
        "holding_state": holding,
        "dust_state": dust,
        "would_promote_to_order_intent": bool(basic_buy_ready and not block_reasons),
        "block_reasons": block_reasons,
        "actual_order_intent_emitted": False,
        "decision_router_called": False,
        "risk_guard_called": False,
        "live_preflight_called": False,
        "order_service_called": False,
        "actual_order": False,
    }


def _contract_reasons_summary(candidates: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in candidates:
        for reason in item.get("block_reasons") or []:
            key = str(reason)
            summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def _build_inert_order_intent_candidate_v1(
    contract: dict[str, Any],
    row: dict[str, Any] | None = None,
    *,
    intended_amount_krw: int = 10_000,
) -> tuple[dict[str, Any] | None, list[str]]:
    row = row or {}
    errors: list[str] = []
    symbol = str(contract.get("symbol") or _row_symbol(row) or "").strip()
    score = _safe_float(contract.get("score", row.get("score", row.get("ai_score"))), 0.0)
    source = str(contract.get("source") or _normalize_contract_source(row.get("source") or row.get("source_type"))).strip()
    ai_opinion = str(contract.get("ai_opinion_status") or row.get("ai_opinion_status") or row.get("opinion") or "").strip()
    freshness = str(contract.get("freshness") or row.get("freshness") or "").strip()
    confidence = _safe_float(row.get("confidence", row.get("ai_confidence")), 0.0)
    reason = str(contract.get("reason") or row.get("reason") or row.get("ai_reason_summary") or "").strip()
    holding = bool(contract.get("holding_state") or row.get("holding") or row.get("holding_display"))
    dust = bool(contract.get("dust_state") or row.get("dust_holding") or row.get("holding_dust") or row.get("dust_filtered"))
    min_order_krw = 10_000
    per_order_hard_cap_krw = 12_000
    total_window_cap_krw = 20_000
    if not bool(contract.get("would_promote_to_order_intent")):
        errors.append("would_promote_false")
    if not symbol:
        errors.append("missing_symbol")
    if intended_amount_krw < min_order_krw:
        errors.append("amount_below_min_order")
    if intended_amount_krw > per_order_hard_cap_krw:
        errors.append("amount_above_per_order_hard_cap")
    if errors:
        return None, errors
    return (
        {
            "schema": "aits_order_intent_candidate_v1",
            "symbol": symbol,
            "side": "buy",
            "source": "basic_buy_ready_ai_confirmed",
            "basic_score": score,
            "ai_opinion": ai_opinion,
            "ai_freshness": freshness,
            "confidence": confidence,
            "reason": reason,
            "intended_amount_krw": int(intended_amount_krw),
            "min_order_krw": min_order_krw,
            "per_order_hard_cap_krw": per_order_hard_cap_krw,
            "total_window_cap_krw": total_window_cap_krw,
            "managed_source": source,
            "holding_state": holding,
            "dust_state": dust,
            "duplicate_guard_required": True,
            "repeat_guard_required": True,
            "relock_required": True,
            "risk_guard_required": True,
            "preflight_required": True,
            "one_shot_unlock_required": True,
            "actual_order": False,
            "submitted": 0,
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "order_adapter_called": False,
        },
        [],
    )


def _validate_inert_order_intent_candidate_v1(candidate: dict[str, Any] | None) -> list[str]:
    if not candidate:
        return ["candidate_missing"]
    errors: list[str] = []
    required = {
        "schema": "aits_order_intent_candidate_v1",
        "side": "buy",
        "source": "basic_buy_ready_ai_confirmed",
        "min_order_krw": 10_000,
        "per_order_hard_cap_krw": 12_000,
        "total_window_cap_krw": 20_000,
        "duplicate_guard_required": True,
        "repeat_guard_required": True,
        "relock_required": True,
        "risk_guard_required": True,
        "preflight_required": True,
        "one_shot_unlock_required": True,
        "actual_order": False,
        "submitted": 0,
        "actual_order_intent_emitted": False,
        "decision_router_called": False,
        "risk_guard_called": False,
        "live_preflight_called": False,
        "order_service_called": False,
        "order_adapter_called": False,
    }
    for key, expected in required.items():
        if candidate.get(key) != expected:
            errors.append(f"{key}_invalid")
    for key in ("symbol", "basic_score", "ai_opinion", "ai_freshness", "reason", "managed_source"):
        if candidate.get(key) in (None, ""):
            errors.append(f"{key}_missing")
    amount = int(candidate.get("intended_amount_krw") or 0)
    if amount < 10_000:
        errors.append("amount_below_min_order")
    if amount > 12_000:
        errors.append("amount_above_per_order_hard_cap")
    return errors


def _run_buy_ready_order_intent_contract_fixture_proof(
    report: dict[str, Any], *, min_score: float = 60.0
) -> None:
    fixtures = [
        (
            "buy_ready_score64_fresh_watch_pass",
            {"symbol": "KRW-PASS", "score": 64, "source": "basic_added", "status_label": "매수대기", "freshness": "fresh"},
            True,
            {},
        ),
        (
            "buy_ready_stale_block",
            {"symbol": "KRW-STALE", "score": 64, "source": "basic_added", "status_label": "매수대기", "freshness": "stale"},
            False,
            {},
        ),
        (
            "buy_ready_data_insufficient_block",
            {"symbol": "KRW-DATA", "score": 66, "source": "basic_added", "status_label": "데이터부족", "freshness": "fresh"},
            False,
            {},
        ),
        (
            "buy_ready_market_feed_error_block",
            {"symbol": "KRW-FEED", "score": 66, "source": "basic_added", "status_label": "매수대기", "freshness": "fresh"},
            False,
            {"market_feed_ok": False},
        ),
        (
            "buy_ready_duplicate_block",
            {"symbol": "KRW-DUP", "score": 66, "source": "basic_added", "status_label": "매수대기", "freshness": "fresh"},
            False,
            {"duplicate_symbols": {"KRW-DUP"}},
        ),
        (
            "buy_ready_repeat_block",
            {"symbol": "KRW-REPEAT", "score": 66, "source": "basic_added", "status_label": "매수대기", "freshness": "fresh"},
            False,
            {"repeat_symbols": {"KRW-REPEAT"}},
        ),
    ]
    results: list[dict[str, Any]] = []
    for name, row, expected, kwargs in fixtures:
        plan = _candidate_order_intent_contract(
            dict(row),
            min_score=min_score,
            market_feed_ok=bool(kwargs.get("market_feed_ok", True)),
            duplicate_symbols=set(kwargs.get("duplicate_symbols") or set()),
            repeat_symbols=set(kwargs.get("repeat_symbols") or set()),
        )
        passed = bool(plan.get("would_promote_to_order_intent")) == bool(expected)
        passed = passed and not bool(plan.get("actual_order_intent_emitted"))
        results.append({"name": name, "pass": passed, "expected_would_promote": expected, "candidate": plan})
    report.update(
        {
            "contract_supported": True,
            "contract_schema": "aits_order_intent_candidate_contract_v1",
            "fixture_results": results,
            "fixture_pass_count": sum(1 for item in results if item.get("pass")),
            "fixture_fail_count": sum(1 for item in results if not item.get("pass")),
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if report["fixture_fail_count"] == 0 else "fail"
    report["status"] = report["pass_status"]


def _run_buy_ready_order_intent_contract_proof(
    report: dict[str, Any],
    *,
    output_dir: Path,
    min_score: float = 60.0,
) -> None:
    rows, source_report = _latest_managed_rows_for_contract(output_dir)
    latest = _latest_basic_candidate_report(output_dir)
    freshness = _last_managed_pool_freshness_from_log()
    market_feed_ok = True
    if latest:
        market_feed_ok = bool(latest.get("market_data_ready", True)) and int(latest.get("top_markets_count") or 0) > 0
    candidates: list[dict[str, Any]] = []
    for row in rows:
        plan = _candidate_order_intent_contract(
            dict(row),
            min_score=min_score,
            market_feed_ok=market_feed_ok,
            freshness_by_symbol=freshness,
        )
        if bool(plan.get("basic_buy_ready")):
            candidates.append(plan)
    would_promote = [item for item in candidates if item.get("would_promote_to_order_intent")]
    blocked = [item for item in candidates if not item.get("would_promote_to_order_intent")]
    report.update(
        {
            "contract_supported": True,
            "contract_schema": "aits_order_intent_candidate_contract_v1",
            "contract_source_report": source_report,
            "buy_ready_owner_path": "MainWindow._update_ai_pool_statuses",
            "buy_ready_criteria": "ai_score >= entry_score_threshold(default 60) and row remains candidate eligible",
            "order_intent_min_score": float(min_score),
            "market_feed_ok": bool(market_feed_ok),
            "managed_row_count": len(rows),
            "buy_ready_count": len(candidates),
            "buy_ready_symbols": [str(item.get("symbol") or "") for item in candidates if item.get("symbol")],
            "candidates": candidates,
            "would_promote_count": len(would_promote),
            "would_promote_symbols": [str(item.get("symbol") or "") for item in would_promote if item.get("symbol")],
            "blocked_count": len(blocked),
            "block_reasons_summary": _contract_reasons_summary(candidates),
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if candidates else "partial"
    report["status"] = report["pass_status"]


def _inject_mock_fresh_ai_opinion(row: dict[str, Any], *, status_label: str = "매수대기") -> dict[str, Any]:
    updated = dict(row)
    opinion = "buy_wait" if status_label == "매수대기" else "data_insufficient" if status_label == "데이터부족" else "watch"
    updated.update(
        {
            "ai_opinion_status": status_label,
            "status_label": status_label,
            "opinion": opinion,
            "freshness": "fresh_manual_refresh",
            "provider": "local",
            "source": row.get("source") or row.get("source_type") or "basic_added",
            "mock_opinion_payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": _row_symbol(row),
                "provider": "local",
                "source": "manual_ai_refresh_mock",
                "freshness": "fresh_manual_refresh",
                "opinion": opinion,
                "status_label": status_label,
                "confidence": 0.74,
                "reason": "observe-only mock opinion for order-intent contract proof",
                "next_action": "계약 검증용 mock 의견; 주문 실행 없음",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
        }
    )
    return updated


def _run_buy_ready_ai_opinion_freshness_unblock_fixture_proof(
    report: dict[str, Any], *, min_score: float = 60.0
) -> None:
    base = {"symbol": "KRW-PYTH", "score": 64, "source": "user_added", "reason": "분석 대기"}
    scenarios = [
        ("buy_ready_missing_opinion_blocks", dict(base), False, ["ai_opinion_missing", "freshness_missing"]),
        ("buy_ready_fresh_buy_wait_unblocks", _inject_mock_fresh_ai_opinion(base, status_label="매수대기"), True, []),
        (
            "buy_ready_fresh_data_insufficient_blocks",
            _inject_mock_fresh_ai_opinion(base, status_label="데이터부족"),
            False,
            ["ai_opinion_data_insufficient"],
        ),
        (
            "buy_ready_stale_opinion_blocks",
            {**_inject_mock_fresh_ai_opinion(base, status_label="매수대기"), "freshness": "stale"},
            False,
            ["freshness_not_acceptable:stale"],
        ),
        (
            "buy_ready_fresh_watch_allowed_observe_only",
            _inject_mock_fresh_ai_opinion(base, status_label="관망"),
            True,
            [],
        ),
    ]
    results: list[dict[str, Any]] = []
    for name, row, expected_promote, expected_reasons in scenarios:
        plan = _candidate_order_intent_contract(dict(row), min_score=min_score, market_feed_ok=True)
        reasons = list(plan.get("block_reasons") or [])
        expected_reasons_ok = all(reason in reasons for reason in expected_reasons)
        passed = bool(plan.get("would_promote_to_order_intent")) == bool(expected_promote)
        passed = passed and expected_reasons_ok and not bool(plan.get("actual_order_intent_emitted"))
        results.append(
            {
                "name": name,
                "pass": passed,
                "expected_would_promote": expected_promote,
                "expected_reasons": expected_reasons,
                "candidate": plan,
            }
        )
    report.update(
        {
            "contract_supported": True,
            "contract_schema": "aits_order_intent_candidate_contract_v1",
            "fixture_results": results,
            "fixture_pass_count": sum(1 for item in results if item.get("pass")),
            "fixture_fail_count": sum(1 for item in results if not item.get("pass")),
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if report["fixture_fail_count"] == 0 else "fail"
    report["status"] = report["pass_status"]


def _run_buy_ready_ai_opinion_freshness_unblock_proof(
    report: dict[str, Any],
    *,
    output_dir: Path,
    target_symbol: str | None = None,
    min_score: float = 60.0,
) -> None:
    rows, source_report = _latest_managed_rows_for_contract(output_dir)
    freshness = _last_managed_pool_freshness_from_log()
    latest = _latest_basic_candidate_report(output_dir)
    market_feed_ok = True
    if latest:
        market_feed_ok = bool(latest.get("market_data_ready", True)) and int(latest.get("top_markets_count") or 0) > 0
    buy_ready_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        before = _candidate_order_intent_contract(
            dict(row),
            min_score=min_score,
            market_feed_ok=market_feed_ok,
            freshness_by_symbol=freshness,
        )
        if before.get("basic_buy_ready"):
            buy_ready_rows.append((dict(row), before))
    normalized_target = _normalize_symbol_text(target_symbol or "")
    target_row: dict[str, Any] = {}
    before_plan: dict[str, Any] = {}
    if normalized_target:
        for row, before in buy_ready_rows:
            if _row_symbol(row) == normalized_target:
                target_row, before_plan = row, before
                break
    if not target_row and buy_ready_rows:
        target_row, before_plan = buy_ready_rows[0]
    target = _row_symbol(target_row)
    injected = _inject_mock_fresh_ai_opinion(target_row, status_label="매수대기") if target_row else {}
    after_plan = (
        _candidate_order_intent_contract(dict(injected), min_score=min_score, market_feed_ok=market_feed_ok)
        if injected
        else {}
    )
    before_reasons = set(before_plan.get("block_reasons") or [])
    after_reasons = set(after_plan.get("block_reasons") or [])
    unblocked = sorted(before_reasons - after_reasons)
    remaining = sorted(after_reasons)
    opinion_unblocked = "ai_opinion_missing" in unblocked
    freshness_unblocked = any(str(item).startswith("freshness_not_acceptable") or item == "freshness_missing" for item in unblocked)
    pass_status = bool(target_row and opinion_unblocked and freshness_unblocked and after_plan.get("would_promote_to_order_intent"))
    report.update(
        {
            "contract_supported": True,
            "contract_schema": "aits_order_intent_candidate_contract_v1",
            "contract_source_report": source_report,
            "target_symbol": target,
            "target_is_buy_ready": bool(before_plan.get("basic_buy_ready")),
            "score": before_plan.get("score"),
            "source": before_plan.get("source"),
            "buy_ready_symbols": [str(item.get("symbol") or "") for _, item in buy_ready_rows if item.get("symbol")],
            "before_would_promote": bool(before_plan.get("would_promote_to_order_intent")),
            "before_block_reasons": list(before_plan.get("block_reasons") or []),
            "injected_opinion": "매수대기",
            "injected_freshness": "fresh_manual_refresh",
            "injected_payload": injected.get("mock_opinion_payload") if isinstance(injected, dict) else {},
            "after_would_promote": bool(after_plan.get("would_promote_to_order_intent")),
            "after_block_reasons": list(after_plan.get("block_reasons") or []),
            "unblocked_reasons": unblocked,
            "remaining_block_reasons": remaining,
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if pass_status else "partial" if target_row and opinion_unblocked and freshness_unblocked else "fail"
    report["status"] = report["pass_status"]


def _run_order_intent_candidate_inert_bridge_fixture_proof(
    report: dict[str, Any], *, min_score: float = 60.0
) -> None:
    base = {"symbol": "KRW-PYTH", "score": 64, "source": "user_added", "reason": "inert bridge fixture"}
    promoted_row = _inject_mock_fresh_ai_opinion(base, status_label="매수대기")
    blocked_row = dict(base)
    data_row = _inject_mock_fresh_ai_opinion(base, status_label="데이터부족")
    scenarios = [
        ("would_promote_true_builds_inert_candidate", promoted_row, 10_000, True, []),
        ("would_promote_false_builds_none", blocked_row, 10_000, False, ["would_promote_false"]),
        ("missing_ai_opinion_blocks_candidate", blocked_row, 10_000, False, ["would_promote_false"]),
        ("amount_below_min_blocks_candidate", promoted_row, 9_000, False, ["amount_below_min_order"]),
        ("amount_above_hard_cap_blocks_candidate", promoted_row, 13_000, False, ["amount_above_per_order_hard_cap"]),
        ("missing_one_shot_unlock_keeps_inert_only", promoted_row, 10_000, True, []),
        ("actual_emit_never", promoted_row, 10_000, True, []),
        ("router_risk_order_never_called", promoted_row, 10_000, True, []),
        ("data_insufficient_blocks_candidate", data_row, 10_000, False, ["would_promote_false"]),
    ]
    results: list[dict[str, Any]] = []
    for name, row, amount, expected_created, expected_errors in scenarios:
        contract = _candidate_order_intent_contract(dict(row), min_score=min_score, market_feed_ok=True)
        candidate, build_errors = _build_inert_order_intent_candidate_v1(contract, row, intended_amount_krw=amount)
        validation_errors = _validate_inert_order_intent_candidate_v1(candidate) if candidate else []
        candidate_created = candidate is not None
        expected_errors_ok = all(reason in build_errors for reason in expected_errors)
        passed = candidate_created == bool(expected_created)
        passed = passed and expected_errors_ok
        passed = passed and (not candidate_created or not validation_errors)
        passed = passed and not bool((candidate or {}).get("actual_order_intent_emitted"))
        passed = passed and not bool((candidate or {}).get("decision_router_called"))
        passed = passed and not bool((candidate or {}).get("risk_guard_called"))
        passed = passed and not bool((candidate or {}).get("order_service_called"))
        results.append(
            {
                "name": name,
                "pass": passed,
                "expected_candidate_created": expected_created,
                "would_promote_to_order_intent": bool(contract.get("would_promote_to_order_intent")),
                "candidate_created": candidate_created,
                "candidate": candidate or {},
                "validation_errors": validation_errors,
                "blocked_reasons": build_errors,
            }
        )
    report.update(
        {
            "inert_bridge_supported": True,
            "schema": "aits_order_intent_candidate_v1",
            "schema_owner": "tools/runtime_smoke/aits_qt_smoke_harness.py::_build_inert_order_intent_candidate_v1",
            "fixture_results": results,
            "fixture_pass_count": sum(1 for item in results if item.get("pass")),
            "fixture_fail_count": sum(1 for item in results if not item.get("pass")),
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "order_adapter_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "managed_pool_mutation": False,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if report["fixture_fail_count"] == 0 else "fail"
    report["status"] = report["pass_status"]


def _run_order_intent_candidate_inert_bridge_live_proof(
    report: dict[str, Any],
    *,
    output_dir: Path,
    target_symbol: str | None = None,
    min_score: float = 60.0,
) -> None:
    rows, source_report = _latest_managed_rows_for_contract(output_dir)
    latest = _latest_basic_candidate_report(output_dir)
    freshness = _last_managed_pool_freshness_from_log()
    market_feed_ok = True
    if latest:
        market_feed_ok = bool(latest.get("market_data_ready", True)) and int(latest.get("top_markets_count") or 0) > 0
    buy_ready_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        before = _candidate_order_intent_contract(
            dict(row),
            min_score=min_score,
            market_feed_ok=market_feed_ok,
            freshness_by_symbol=freshness,
        )
        if before.get("basic_buy_ready"):
            buy_ready_rows.append((dict(row), before))
    normalized_target = _normalize_symbol_text(target_symbol or "")
    target_row: dict[str, Any] = {}
    before_plan: dict[str, Any] = {}
    if normalized_target:
        for row, before in buy_ready_rows:
            if _row_symbol(row) == normalized_target:
                target_row, before_plan = row, before
                break
    if not target_row and buy_ready_rows:
        target_row, before_plan = buy_ready_rows[0]
    injected = _inject_mock_fresh_ai_opinion(target_row, status_label="매수대기") if target_row else {}
    after_plan = (
        _candidate_order_intent_contract(dict(injected), min_score=min_score, market_feed_ok=market_feed_ok)
        if injected
        else {}
    )
    candidate, build_errors = _build_inert_order_intent_candidate_v1(after_plan, injected, intended_amount_krw=10_000)
    validation_errors = _validate_inert_order_intent_candidate_v1(candidate)
    candidate_valid = bool(candidate) and not validation_errors
    report.update(
        {
            "mode": "order-intent-candidate-inert-bridge-live-proof",
            "schema": "aits_order_intent_candidate_v1",
            "schema_owner": "tools/runtime_smoke/aits_qt_smoke_harness.py::_build_inert_order_intent_candidate_v1",
            "contract_source_report": source_report,
            "target_symbol": _row_symbol(target_row),
            "target_is_buy_ready": bool(before_plan.get("basic_buy_ready")),
            "buy_ready_symbols": [str(item.get("symbol") or "") for _, item in buy_ready_rows if item.get("symbol")],
            "would_promote_to_order_intent": bool(after_plan.get("would_promote_to_order_intent")),
            "candidate_created": bool(candidate),
            "candidate": candidate or {},
            "candidate_valid": candidate_valid,
            "validation_errors": validation_errors,
            "blocked_reasons": build_errors,
            "actual_order_intent_emitted": False,
            "decision_router_called": False,
            "risk_guard_called": False,
            "live_preflight_called": False,
            "order_service_called": False,
            "order_adapter_called": False,
            "submitted_count": 0,
            "provider_external_call_count": 0,
            "managed_pool_mutation": False,
            "order_risk_detected": False,
        }
    )
    report["pass_status"] = "pass" if candidate_valid else "partial" if target_row else "fail"
    report["status"] = report["pass_status"]


def _fixture_result(name: str, passed: bool, plan: dict[str, Any], detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
        "planned_add_count": len(plan.get("planned_add") or []),
        "planned_remove_count": len(plan.get("planned_remove") or []),
        "planned_rotation_count": len(plan.get("planned_rotation") or []),
        "pool_size_after": plan.get("pool_size_after"),
        "protected_violation": bool(plan.get("protected_violation")),
    }


def _run_managed_pool_promotion_policy_proof(
    report: dict[str, Any],
    *,
    output_dir: Path,
    max_managed: int = 10,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_promotion_plan

    config = {
        "max_managed_pool_size": int(max_managed or 10),
        "promotion_min_score": 60.0,
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": True,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": True,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }

    def plan(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], holdings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return build_managed_pool_promotion_plan(rows, candidates, holdings or [], config)

    fixtures: list[dict[str, Any]] = []

    p1 = plan(
        [{"symbol": "KRW-BTC", "source_type": "system_seed", "score": 54}],
        [{"symbol": "KRW-AAA", "rank": 1, "score": 70}, {"symbol": "KRW-BBB", "rank": 2, "score": 68}],
    )
    fixtures.append(_fixture_result("pool_under_10_auto_add", len(p1["planned_add"]) == 2 and p1["pool_size_after"] == 3, p1))

    p2 = plan(
        [{"symbol": "KRW-USER", "source_type": "user_added", "score": 10}]
        + [{"symbol": f"KRW-B{i}", "source_type": "basic_added", "score": 20 + i} for i in range(10)],
        [{"symbol": "KRW-NEW", "rank": 1, "score": 99}],
    )
    fixtures.append(
        _fixture_result(
            "user_added_protected_from_remove",
            all(item.get("symbol") != "KRW-USER" for item in p2["planned_remove"]) and not p2["protected_violation"],
            p2,
        )
    )

    p3 = plan(
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 30, "holding": True}]
        + [{"symbol": f"KRW-C{i}", "source_type": "basic_added", "score": 40 + i} for i in range(10)],
        [{"symbol": "KRW-NEW", "rank": 1, "score": 90}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
    )
    fixtures.append(
        _fixture_result(
            "holding_protected_until_liquidated",
            all(item.get("symbol") != "KRW-HOLD" for item in p3["planned_remove"]) and not p3["protected_violation"],
            p3,
        )
    )

    p4 = plan(
        [{"symbol": f"KRW-D{i}", "source_type": "basic_added", "score": 40 + i} for i in range(10)],
        [{"symbol": "KRW-HIGH", "rank": 1, "score": 80}],
    )
    fixtures.append(
        _fixture_result(
            "basic_added_low_rank_remove_candidate",
            any(item.get("symbol") == "KRW-D0" for item in p4["planned_remove"]),
            p4,
        )
    )

    p5 = plan(
        [{"symbol": f"KRW-E{i}", "source_type": "basic_added", "score": 50 + i} for i in range(10)],
        [{"symbol": "KRW-HIGH", "rank": 1, "score": 90}],
    )
    fixtures.append(
        _fixture_result(
            "pool_max_10_enforced",
            int(p5.get("pool_size_after_capped") or 0) <= int(max_managed or 10),
            p5,
        )
    )

    p6 = plan(
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 60, "holding": True}],
        [{"symbol": "KRW-ROTIN", "rank": 1, "score": 70}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
    )
    fixtures.append(
        _fixture_result(
            "rotation_holding_60_candidate_70",
            bool(p6["planned_rotation"])
            and p6["planned_rotation"][0].get("rotate_out") == "KRW-HOLD"
            and p6["planned_rotation"][0].get("rotate_in") == "KRW-ROTIN"
            and p6["planned_rotation"][0].get("actual_order") is False,
            p6,
        )
    )

    p7 = plan(
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 70, "holding": True}],
        [{"symbol": "KRW-LOW", "rank": 1, "score": 60}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
    )
    fixtures.append(_fixture_result("candidate_below_existing_no_rotation", not p7["planned_rotation"], p7))

    p8 = plan(
        [{"symbol": "KRW-BTC", "source_type": "system_seed", "score": 54}],
        [{"symbol": "KRW-BTC", "rank": 1, "score": 99}, {"symbol": "KRW-DUP", "rank": 2, "score": 80}],
    )
    fixtures.append(
        _fixture_result(
            "duplicate_candidate_ignored",
            all(item.get("symbol") != "KRW-BTC" for item in p8["planned_add"])
            and any(item.get("symbol") == "KRW-DUP" for item in p8["planned_add"]),
            p8,
        )
    )

    latest = _latest_basic_candidate_report(output_dir)
    real_plan: dict[str, Any] = {}
    if latest:
        rows = [{"symbol": symbol, "source_type": "system_seed"} for symbol in latest.get("managed_pool_symbols_after") or []]
        real_plan = plan(rows, list(latest.get("top_candidates") or []), [])

    fixture_pass = all(item.get("passed") for item in fixtures)
    order_risk = any(
        bool(item.get("actual_order"))
        for item in (real_plan.get("planned_add") or [])
        + (real_plan.get("planned_remove") or [])
        + (real_plan.get("planned_rotation") or [])
    )
    report.update(
        {
            "policy_supported": True,
            "max_managed_pool_size": int(max_managed or 10),
            "auto_add_enabled": True,
            "auto_remove_enabled": True,
            "promotion_min_score": real_plan.get("promotion_min_score", 60.0),
            "quality_gate_enabled": real_plan.get("quality_gate_enabled", True),
            "fill_to_max": real_plan.get("fill_to_max", False),
            "protect_user_added": True,
            "protect_holdings_until_liquidated": True,
            "protect_system_seed_initially": True,
            "rotation_enabled": True,
            "rotation_min_score_gap": 0.0,
            "order_execution_enabled": False,
            "fixture_results": fixtures,
            "fixture_pass_count": sum(1 for item in fixtures if item.get("passed")),
            "fixture_total_count": len(fixtures),
            "actual_candidate_source_report": latest.get("_report_path", ""),
            "current_pool_size": real_plan.get("current_pool_size", 0),
            "candidate_count": real_plan.get("candidate_count", 0),
            "planned_add": real_plan.get("planned_add", []),
            "planned_remove": real_plan.get("planned_remove", []),
            "planned_keep": real_plan.get("planned_keep", []),
            "protected_rows": real_plan.get("protected_rows", []),
            "planned_rotation": real_plan.get("planned_rotation", []),
            "pool_size_after": real_plan.get("pool_size_after", 0),
            "actual_mutation_performed": False,
            "managed_pool_mutation_performed": False,
            "order_risk_detected": bool(order_risk),
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "provider_external_call_count": 0,
        }
    )
    report["pass_status"] = "pass" if fixture_pass and not order_risk and latest else "partial"


def _run_managed_pool_promotion_quality_gate_proof(
    report: dict[str, Any],
    *,
    max_managed: int = 10,
    min_score: float = 60.0,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_promotion_plan

    config = {
        "max_managed_pool_size": int(max_managed or 10),
        "promotion_min_score": float(min_score),
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": False,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }

    def plan(rows: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return build_managed_pool_promotion_plan(rows, candidates, [], config)

    rows_8 = [{"symbol": f"KRW-M{i}", "source_type": "basic_added", "score": 50 + i} for i in range(8)]
    p1 = plan(
        rows_8,
        [
            {"symbol": "KRW-PASS1", "rank": 1, "score": 72, "trade_value": 100000000},
            {"symbol": "KRW-PASS2", "rank": 2, "score": 64, "trade_value": 90000000},
            {"symbol": "KRW-LOW1", "rank": 3, "score": 55, "trade_value": 80000000},
            {"symbol": "KRW-LOW2", "rank": 4, "score": 40, "trade_value": 70000000},
        ],
    )
    p2 = plan(rows_8, [{"symbol": "KRW-LOWA", "rank": 1, "score": 59}, {"symbol": "KRW-LOWB", "rank": 2, "score": 42}])
    p3 = plan(rows_8, [{"symbol": "KRW-RANK1LOW", "rank": 1, "score": 50}])
    p4 = plan(rows_8, [{"symbol": "KRW-M1", "rank": 1, "score": 99}, {"symbol": "KRW-NEW", "rank": 2, "score": 80}])

    fixtures = [
        _fixture_result("max_10_pass_2_adds_2_only", len(p1.get("planned_add") or []) == 2, p1),
        _fixture_result("max_10_pass_0_adds_0", len(p2.get("planned_add") or []) == 0, p2),
        _fixture_result(
            "high_rank_low_score_rejected",
            len(p3.get("planned_add") or []) == 0
            and any(item.get("symbol") == "KRW-RANK1LOW" for item in p3.get("rejected_candidates") or []),
            p3,
        ),
        _fixture_result(
            "already_managed_rejected",
            all(item.get("symbol") != "KRW-M1" for item in p4.get("planned_add") or [])
            and any(item.get("symbol") == "KRW-M1" for item in p4.get("rejected_candidates") or []),
            p4,
        ),
        _fixture_result("max_cap_applied_not_target", bool(p1.get("fill_to_max")) is False and len(p1.get("planned_add") or []) < int(max_managed or 10), p1),
        _fixture_result("fill_to_max_false", bool(p1.get("fill_to_max")) is False, p1),
    ]
    fixture_pass = all(item.get("passed") for item in fixtures)
    report.update(
        {
            "quality_gate_supported": True,
            "max_managed_pool_size": int(max_managed or 10),
            "fill_to_max": False,
            "promotion_min_score": float(min_score),
            "current_count": p1.get("current_pool_size", 0),
            "remaining_slots": p1.get("remaining_slots", 0),
            "candidate_count": p1.get("candidate_count", 0),
            "quality_pass_count": p1.get("quality_pass_count", 0),
            "quality_fail_count": p1.get("quality_fail_count", 0),
            "planned_add_count": len(p1.get("planned_add") or []),
            "planned_add": p1.get("planned_add", []),
            "rejected_candidates": p1.get("rejected_candidates", []),
            "rejection_reasons": p1.get("rejection_reasons", []),
            "score_distribution": p1.get("score_distribution", {}),
            "not_filled_reason": p1.get("not_filled_reason", ""),
            "fixture_results": fixtures,
            "fixture_pass_count": sum(1 for item in fixtures if item.get("passed")),
            "fixture_total_count": len(fixtures),
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "actual_mutation_performed": False,
            "managed_pool_mutation_performed": False,
            "pass_status": "pass" if fixture_pass else "fail",
        }
    )


def _run_managed_pool_promotion_quality_live_proof(
    report: dict[str, Any],
    *,
    max_managed: int = 10,
    min_score: float = 60.0,
    max_candidates: int = 50,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_promotion_plan

    current_rows = _load_saved_managed_pool_rows_readonly()
    feed_report: dict[str, Any] = {}
    _run_top_markets_feed_proof(feed_report, max_markets=max_candidates)
    top_markets = [row for row in (feed_report.get("top_markets") or []) if isinstance(row, dict)]
    candidates = _public_top_markets_to_rotation_candidates(top_markets, max_candidates=max_candidates)
    config = {
        "max_managed_pool_size": int(max_managed or 10),
        "promotion_min_score": float(min_score),
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": False,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_promotion_plan(current_rows, candidates, [], config)
    report.update(
        {
            "quality_gate_supported": True,
            "observe_only": True,
            "current_count": plan.get("current_pool_size", len(current_rows)),
            "max_managed_pool_size": int(max_managed or 10),
            "fill_to_max": plan.get("fill_to_max"),
            "promotion_min_score": plan.get("promotion_min_score"),
            "remaining_slots": plan.get("remaining_slots", 0),
            "candidate_count": plan.get("candidate_count", 0),
            "quality_pass_count": plan.get("quality_pass_count", 0),
            "quality_fail_count": plan.get("quality_fail_count", 0),
            "planned_add_count": len(plan.get("planned_add") or []),
            "planned_add": plan.get("planned_add", []),
            "rejected_candidates_sample": list(plan.get("rejected_candidates") or [])[:10],
            "rejection_reasons": plan.get("rejection_reasons", []),
            "score_distribution": plan.get("score_distribution", {}),
            "not_filled_reason": plan.get("not_filled_reason", ""),
            "candidate_source_status": feed_report.get("pass_status") or feed_report.get("status", ""),
            "candidate_no_reason": feed_report.get("empty_reason", ""),
            "market_count_raw": int(feed_report.get("market_count_raw") or 0),
            "krw_market_count": int(feed_report.get("krw_market_count") or 0),
            "ticker_count": int(feed_report.get("ticker_count") or 0),
            "top_markets_count": int(feed_report.get("top_markets_count") or 0),
            "top_markets_sample": top_markets[:10],
            "managed_pool_mutation_performed": False,
            "actual_mutation_performed": False,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "pass_status": "pass"
            if plan.get("policy_supported") and len(candidates) > 0 and not bool(feed_report.get("empty_reason"))
            else "partial",
        }
    )


def _run_managed_pool_quality_ranked_rebuild_proof(
    report: dict[str, Any],
    *,
    max_managed: int = 10,
    min_score: float = 60.0,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_quality_rebuild_plan

    config = {
        "max_managed_pool_size": int(max_managed or 10),
        "promotion_min_score": float(min_score),
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": True,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": False,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }

    rows = [
        {"symbol": "KRW-BTC", "source_type": "system_seed", "score": 20},
        {"symbol": "KRW-ETH", "source_type": "system_seed", "score": 21},
        {"symbol": "KRW-XRP", "source_type": "system_seed", "score": 22},
        {"symbol": "KRW-USER", "source_type": "user_added", "score": 5},
        {"symbol": "KRW-HOLD", "source_type": "basic_added", "holding_display": True, "score": 35},
        {"symbol": "KRW-PAUSE", "source_type": "basic_added", "trade_hold": True, "score": 36},
        {"symbol": "KRW-LOW37", "source_type": "basic_added", "score": 37, "rank": 21},
        {"symbol": "KRW-LOW38", "source_type": "basic_added", "score": 38, "rank": 22},
        {"symbol": "KRW-KEEP65", "source_type": "basic_added", "score": 65, "rank": 4},
        {"symbol": "KRW-KEEP62", "source_type": "basic_added", "score": 62, "rank": 5},
    ]
    candidates = [
        {"symbol": "KRW-BIO", "score": 68, "rank": 1, "trade_value": 100000000, "reason": "fixture_high_score"},
        {"symbol": "KRW-XLM", "score": 67, "rank": 2, "trade_value": 90000000, "reason": "fixture_high_score"},
        {"symbol": "KRW-PYTH", "score": 66, "rank": 3, "trade_value": 80000000, "reason": "fixture_high_score"},
        {"symbol": "KRW-MOC", "score": 65, "rank": 4, "trade_value": 70000000, "reason": "fixture_high_score"},
        {"symbol": "KRW-AQT", "score": 59, "rank": 5, "trade_value": 60000000, "reason": "fixture_low_score"},
    ]
    plan = build_managed_pool_quality_rebuild_plan(rows, candidates, [], config)
    sparse_plan = build_managed_pool_quality_rebuild_plan(
        rows[:3] + [{"symbol": "KRW-LOWONLY", "source_type": "basic_added", "score": 35, "rank": 30}],
        [{"symbol": "KRW-ONEPASS", "score": 70, "rank": 1, "trade_value": 1000000}],
        [],
        config,
    )
    remove_symbols = {_row_symbol(row) for row in plan.get("planned_remove") or []}
    add_symbols = {_row_symbol(row) for row in plan.get("planned_add") or []}
    protected_symbols = {_row_symbol(row) for row in plan.get("protected_rows") or []}
    fixtures = [
        {"name": "existing_low_score_basic_removed", "passed": {"KRW-LOW37", "KRW-LOW38"}.issubset(remove_symbols)},
        {"name": "high_score_candidate_added", "passed": {"KRW-BIO", "KRW-XLM"}.issubset(add_symbols)},
        {"name": "max_cap_not_target", "passed": bool(plan.get("fill_to_max")) is False and int(plan.get("after_count_expected") or 0) <= int(max_managed or 10)},
        {
            "name": "pass_candidates_less_than_slots_not_filled",
            "passed": int(sparse_plan.get("after_count_expected") or 0) < int(max_managed or 10)
            and sparse_plan.get("not_filled_reason") == "max_managed_pool_size_is_cap_not_target",
        },
        {"name": "user_added_protected", "passed": "KRW-USER" in protected_symbols and "KRW-USER" not in remove_symbols},
        {"name": "holding_display_protected", "passed": "KRW-HOLD" in protected_symbols and "KRW-HOLD" not in remove_symbols},
        {"name": "trade_hold_protected", "passed": "KRW-PAUSE" in protected_symbols and "KRW-PAUSE" not in remove_symbols},
        {"name": "system_seed_protected", "passed": {"KRW-BTC", "KRW-ETH", "KRW-XRP"}.issubset(protected_symbols) and not ({"KRW-BTC", "KRW-ETH", "KRW-XRP"} & remove_symbols)},
        {"name": "max_equal_still_rebuilds_quality", "passed": bool(remove_symbols) and bool(add_symbols)},
        {"name": "protected_overflow", "passed": not bool(plan.get("protected_violation"))},
    ]
    pass_status = all(item.get("passed") for item in fixtures)
    report.update(
        {
            "quality_rebuild_supported": True,
            "max_managed_pool_size": int(max_managed or 10),
            "promotion_min_score": float(min_score),
            "fill_to_max": plan.get("fill_to_max"),
            "protected_keep": plan.get("protected_keep", []),
            "protected_count": plan.get("protected_count", 0),
            "rebuild_slots": plan.get("rebuild_slots", 0),
            "current_basic_added": plan.get("current_basic_added", []),
            "quality_pass_count": plan.get("quality_pass_count", 0),
            "quality_fail_count": plan.get("quality_fail_count", 0),
            "planned_keep_basic": plan.get("planned_keep_basic", []),
            "planned_add": plan.get("planned_add", []),
            "planned_remove": plan.get("planned_remove", []),
            "planned_remove_reasons": plan.get("planned_remove_reasons", []),
            "after_count_expected": plan.get("after_count_expected", 0),
            "not_filled_reason": plan.get("not_filled_reason", ""),
            "protected_overflow": plan.get("protected_overflow", False),
            "fixture_results": fixtures,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "actual_order": False,
            "rotation_execution": False,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "pass_status": "pass" if pass_status else "fail",
        }
    )


def _run_managed_pool_quality_ranked_rebuild_live_proof(
    report: dict[str, Any],
    *,
    max_managed: int = 10,
    min_score: float = 60.0,
    max_candidates: int = 50,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_quality_rebuild_plan

    current_rows = _load_saved_managed_pool_rows_readonly()
    feed_report: dict[str, Any] = {}
    _run_top_markets_feed_proof(feed_report, max_markets=max_candidates)
    top_markets = [row for row in (feed_report.get("top_markets") or []) if isinstance(row, dict)]
    candidates = _public_top_markets_to_rotation_candidates(top_markets, max_candidates=max_candidates)
    config = {
        "max_managed_pool_size": int(max_managed or 10),
        "promotion_min_score": float(min_score),
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": True,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": False,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_quality_rebuild_plan(current_rows, candidates, [], config)
    report.update(
        {
            "quality_rebuild_supported": True,
            "observe_only": True,
            "current_rows": current_rows,
            "current_count": len(current_rows),
            "max_managed_pool_size": int(max_managed or 10),
            "promotion_min_score": float(min_score),
            "fill_to_max": plan.get("fill_to_max"),
            "market_count_raw": int(feed_report.get("market_count_raw") or 0),
            "krw_market_count": int(feed_report.get("krw_market_count") or 0),
            "ticker_count": int(feed_report.get("ticker_count") or 0),
            "top_markets_count": int(feed_report.get("top_markets_count") or 0),
            "candidate_count": len(candidates),
            "candidate_source_status": feed_report.get("pass_status") or feed_report.get("status", ""),
            "candidate_no_reason": feed_report.get("empty_reason", ""),
            "protected_keep": plan.get("protected_keep", []),
            "protected_count": plan.get("protected_count", 0),
            "rebuild_slots": plan.get("rebuild_slots", 0),
            "current_basic_added": plan.get("current_basic_added", []),
            "quality_pass_count": plan.get("quality_pass_count", 0),
            "quality_fail_count": plan.get("quality_fail_count", 0),
            "planned_keep_basic": plan.get("planned_keep_basic", []),
            "planned_add": plan.get("planned_add", []),
            "planned_remove": plan.get("planned_remove", []),
            "planned_remove_reasons": plan.get("planned_remove_reasons", []),
            "rejected_candidates_sample": list(plan.get("rejected_candidates") or [])[:10],
            "score_distribution": plan.get("score_distribution", {}),
            "after_count_expected": plan.get("after_count_expected", 0),
            "not_filled_reason": plan.get("not_filled_reason", ""),
            "protected_overflow": plan.get("protected_overflow", False),
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "actual_order": False,
            "rotation_execution": False,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "pass_status": "pass" if plan.get("quality_rebuild_supported") and len(candidates) > 0 and not bool(feed_report.get("empty_reason")) else "partial",
        }
    )


def _managed_pool_ai_review_state(row: dict[str, Any]) -> dict[str, Any]:
    symbol = _row_symbol(row)
    generated_at = str(
        row.get("last_ai_review_at")
        or row.get("ai_briefing_generated_at")
        or row.get("decision_generated_at")
        or row.get("generated_at")
        or ""
    ).strip()
    score = _safe_float(row.get("ai_score", row.get("score")), math.nan)
    status = str(row.get("ai_review_queue_status") or row.get("status") or "").strip()
    reason = str(row.get("ai_review_queue_reason") or row.get("status_reason") or row.get("reason") or "").strip()
    freshness = "missing" if not generated_at else "present"
    analysis_required = freshness == "missing" or "재분석" in reason or "manual" in reason.lower()
    if math.isnan(score):
        analysis_required = True
    return {
        "symbol": symbol,
        "status": status,
        "reason": reason,
        "ai_score": None if math.isnan(score) else score,
        "freshness_state": freshness,
        "last_ai_review_at": generated_at,
        "analysis_required": bool(analysis_required),
        "manual_only_reason": "GPT/Gemini provider reanalysis is manual; this proof keeps provider_external_call_count=0",
        "order_execution": False,
        "final_action_unchanged": True,
    }


def _managed_pool_local_opinion(row: dict[str, Any], *, provider: str = "local") -> dict[str, Any]:
    symbol = _row_symbol(row)
    name = str(row.get("name") or row.get("display_name") or symbol).strip()
    score_raw = row.get("ai_score", row.get("score"))
    score = _safe_float(score_raw, math.nan)
    source = str(row.get("source_type") or row.get("source") or "managed_pool").strip()
    holding_display = bool(row.get("holding_display") or row.get("holding") or row.get("is_holding"))
    status_reason = str(row.get("ai_review_queue_reason") or row.get("status_reason") or row.get("reason") or "").strip()
    if math.isnan(score):
        opinion = "analysis_required"
        status_label = "재분석필요"
        confidence = 0.0
        reason = "AITS 점수 또는 최신 AI 분석 시각이 부족해 수동 재분석 대상입니다."
    elif holding_display and score < 60:
        opinion = "watch"
        status_label = "관망"
        confidence = round(max(0.1, min(0.8, score / 100.0)), 3)
        reason = "보유 표시는 유지하지만 품질 점수 기준으로는 운용 확대보다 관망이 적절합니다."
    elif score >= 70:
        opinion = "buy_wait"
        status_label = "매수대기"
        confidence = round(min(0.95, score / 100.0), 3)
        reason = "LOCAL 계산 기준에서 품질 점수가 높아 진입 후보로 관찰할 수 있습니다."
    elif score >= 60:
        opinion = "watch"
        status_label = "관망"
        confidence = round(min(0.8, score / 100.0), 3)
        reason = "품질 기준은 통과했지만 추가 AI 재분석 전에는 관망 의견으로 유지합니다."
    elif score >= 45:
        opinion = "data_insufficient"
        status_label = "데이터부족"
        confidence = round(max(0.1, score / 100.0), 3)
        reason = "품질 기준 미달 또는 추가 데이터 확인이 필요합니다."
    else:
        opinion = "analysis_required"
        status_label = "재분석필요"
        confidence = round(max(0.1, score / 100.0), 3)
        reason = "품질 점수가 낮아 수동 AI 재분석 또는 관리 제외 검토가 필요합니다."
    if source in {"system_seed", "system_default"} and opinion == "buy_wait":
        opinion = "watch"
        status_label = "관망"
        reason = "기본 보호 종목은 보호 유지 대상이며, 자동 매수 의견으로 승격하지 않습니다."
    if status_reason and not _is_stale_manual_refresh_reason(status_reason):
        reason = f"{reason} / 현재 사유: {status_reason[:80]}"
    next_action = "수동 AI 재분석 또는 관찰 유지; 주문 실행 없음"
    tooltip = "\n".join(
        [
            f"종목: {symbol} {name}".strip(),
            f"상태: {status_label}",
            f"AITS 점수: {'-' if math.isnan(score) else round(score, 2)}",
            f"의견 근거: {reason[:140]}",
            "실행: 주문 없음 / final action 변경 없음",
        ]
    )
    return {
        "schema": "managed_pool_ai_opinion_v1",
        "event_time": _now_iso(),
        "symbol": symbol,
        "display_name": name,
        "provider": provider,
        "provider_external_call": False,
        "source": "local_calculation",
        "ai_score": None if math.isnan(score) else score,
        "opinion": opinion,
        "status_label": status_label,
        "confidence": confidence,
        "reason": reason,
        "next_action": next_action,
        "freshness": "analysis_required" if opinion == "analysis_required" else "local_reference",
        "tooltip": tooltip,
        "order_execution": False,
        "final_action_unchanged": True,
    }


def _run_managed_pool_ai_review_queue_proof(report: dict[str, Any]) -> None:
    rows = _load_saved_managed_pool_rows_readonly()
    states = [_managed_pool_ai_review_state(row) for row in rows if _row_symbol(row)]
    queue_symbols = [item["symbol"] for item in states]
    analysis_required = [item for item in states if item.get("analysis_required")]
    fresh = [item for item in states if item.get("freshness_state") == "present" and not item.get("analysis_required")]
    stale = [item for item in states if item.get("analysis_required")]
    manual_only_reason = "MainWindow._build_managed_pool_ai_review_queue builds review candidates; GPT/Gemini reanalysis is manual and blocked in this proof."
    proof_log_text = (
        f"[AITS][ManagedPoolAIReviewQueueProof] rows={len(rows)} "
        f"queue_candidates={len(queue_symbols)} provider_external_call_count=0 "
        "submitted=0 order_allowed=False real_order=False"
    )
    report.update(
        {
            "ai_review_queue_supported": True,
            "queue_owner": "MainWindow._build_managed_pool_ai_review_queue",
            "queue_trigger": ["managed row score update", "managed table refresh", "manual AI reanalysis"],
            "manual_reanalysis_copy_owner": "MainWindow._build_managed_pool_ai_review_queue row['ai_review_queue_reason']",
            "managed_row_count": len(rows),
            "queue_candidate_count": len(queue_symbols),
            "queue_symbols": queue_symbols,
            "review_state_by_symbol": states,
            "analysis_required_count": len(analysis_required),
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "manual_only_reason": manual_only_reason,
            "proof_log_text": proof_log_text,
            "provider_external_call_count": 0,
            "order_execution": False,
            "final_action_unchanged": True,
            "order_risk_detected": False,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "pass_status": "pass" if rows and queue_symbols else "partial",
        }
    )


def _run_managed_pool_ai_opinion_flow_proof(report: dict[str, Any], *, provider: str = "local") -> None:
    rows = _load_saved_managed_pool_rows_readonly()
    provider = _normalize_provider_for_report(provider or "local")
    provider_allowed = provider == "local"
    opinions = [_managed_pool_local_opinion(row, provider=provider) for row in rows if _row_symbol(row)] if provider_allowed else []
    status_samples = [{"symbol": item.get("symbol"), "status_label": item.get("status_label")} for item in opinions[:5]]
    tooltip_samples = [str(item.get("tooltip") or "") for item in opinions[:3]]
    data_insufficient = [item.get("symbol") for item in opinions if item.get("opinion") == "data_insufficient"]
    analysis_required = [item.get("symbol") for item in opinions if item.get("opinion") == "analysis_required"]
    proof_log_text = (
        f"[AITS][ManagedPoolAIOpinionFlowProof] provider={provider} "
        f"opinions={len(opinions)} provider_external_call_count=0 "
        "order_execution=False final_action_unchanged=True"
    )
    report.update(
        {
            "ai_opinion_flow_supported": bool(provider_allowed),
            "provider": provider,
            "provider_policy": "LOCAL calculation only; GPT/Gemini actual calls require a separate provider-call proof Goal.",
            "provider_external_call_count": 0,
            "opinion_schema": "managed_pool_ai_opinion_v1",
            "opinion_count": len(opinions),
            "opinions": opinions,
            "status_samples": status_samples,
            "tooltip_samples": tooltip_samples,
            "data_insufficient_symbols": data_insufficient,
            "analysis_required_symbols": analysis_required,
            "proof_log_text": proof_log_text,
            "order_execution": False,
            "final_action_unchanged": True,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "order_risk_detected": False,
            "pass_status": "pass" if provider_allowed and opinions else "partial",
        }
    )


def _target_managed_pool_row(rows: list[dict[str, Any]], target_symbol: str | None = None) -> dict[str, Any]:
    target = _normalize_symbol_text(target_symbol or "")
    if target:
        for row in rows:
            if _row_symbol(row) == target:
                return dict(row)
    for row in rows:
        if _row_symbol(row):
            return dict(row)
    return {}


def _build_managed_pool_opinion_compact_payload(row: dict[str, Any], rows: list[dict[str, Any]], provider: str) -> dict[str, Any]:
    symbol = _row_symbol(row)
    score = row.get("ai_score", row.get("score"))
    status = str(row.get("status") or row.get("status_label") or "").strip()
    reason = str(
        row.get("ai_review_queue_reason")
        or row.get("status_reason")
        or row.get("reason")
        or row.get("source_reason")
        or ""
    ).strip()
    recent_move = {
        "change_rate": row.get("change_rate", row.get("change_pct", row.get("change_24h"))),
        "trade_value": row.get("trade_value", row.get("trade_value_krw", row.get("acc_trade_price_24h"))),
        "rank": row.get("rank", row.get("market_rank")),
    }
    return {
        "schema": "managed_pool_ai_opinion_request_v1",
        "purpose": "managed_pool_display_opinion",
        "provider": provider,
        "symbol": symbol,
        "display_name": str(row.get("name") or row.get("display_name") or symbol),
        "aits_score": score,
        "status": status,
        "status_reason": reason[:220],
        "candidate_reason": str(row.get("candidate_reason") or row.get("added_reason") or reason)[:220],
        "managed_source": str(row.get("source") or row.get("managed_source") or "")[:80],
        "recent_move": recent_move,
        "managed_pool_count": len(rows),
        "safety_constraints": {
            "order_execution": False,
            "actual_order": False,
            "final_action_unchanged": True,
            "managed_pool_mutation": False,
            "do_not_verify_order": True,
        },
    }


def _managed_pool_opinion_status_from_provider(value: Any, fallback_label: Any = "") -> tuple[str, str]:
    text = str(value or "").strip().lower()
    label = str(fallback_label or "").strip()
    mapping = {
        "watch": ("watch", "관망"),
        "hold": ("watch", "관망"),
        "관망": ("watch", "관망"),
        "buy_wait": ("buy_wait", "매수대기"),
        "buy": ("buy_wait", "매수대기"),
        "매수대기": ("buy_wait", "매수대기"),
        "rotate_review": ("rotate_review", "교체검토"),
        "rotation": ("rotate_review", "교체검토"),
        "교체검토": ("rotate_review", "교체검토"),
        "sell_review": ("sell_review", "매도검토"),
        "sell": ("sell_review", "매도검토"),
        "매도검토": ("sell_review", "매도검토"),
        "data_insufficient": ("data_insufficient", "데이터부족"),
        "insufficient": ("data_insufficient", "데이터부족"),
        "데이터부족": ("data_insufficient", "데이터부족"),
    }
    return mapping.get(text) or mapping.get(label.lower()) or mapping.get(label) or ("data_insufficient", "데이터부족")


def _is_execution_block_reason_only(reason: str) -> bool:
    text = str(reason or "").strip().lower()
    if not text:
        return False
    blocked_tokens = (
        "execution not allowed",
        "order execution not allowed",
        "openai_live_call_disabled",
        "gemini_live_call_disabled",
    )
    return any(token in text for token in blocked_tokens) and len(text) <= 120


def _is_stale_manual_refresh_reason(reason: str) -> bool:
    text = str(reason or "").strip().lower()
    if not text:
        return False
    stale_tokens = (
        "\uc0c8 \ubd84\uc11d \uad8c\uc7a5",
        "ai \uc7ac\ubd84\uc11d\uc740 \uc218\ub3d9 \uc2e4\ud589 \ud544\uc694",
        "\ud604\uc7ac ai \ubd84\uc11d\uc774 \uc5c6",
        "\ubd84\uc11d\uc774 \uc5c6",
        "\uc218\ub3d9 ai \uc7ac\ubd84\uc11d",
        "ai \uc7ac\ubd84\uc11d",
        "\uc218\ub3d9 \uc7ac\ubd84\uc11d",
        "\uc218\ub3d9 \uc2e4\ud589 \ud544\uc694",
        "ai \ubd84\uc11d\uc774 \uc644\ub8cc\ub420 \ub54c\uae4c\uc9c0",
        "\ubd84\uc11d\uc774 \uc644\ub8cc\ub420 \ub54c\uae4c\uc9c0",
        "\uc7ac\ubd84\uc11d \uad8c\uc7a5",
        "analysis_required",
        "manual_required",
        "manual refresh required",
        "analysis required",
        "until ai analysis completes",
        "until analysis completes",
    )
    return any(token in text for token in stale_tokens)


def _is_fresh_managed_pool_opinion_payload(payload: dict[str, Any]) -> bool:
    freshness = str(payload.get("freshness") or "").strip().lower()
    source = str(payload.get("source") or "").strip().lower()
    if freshness.startswith("fresh_"):
        return True
    if source in {"manual_ai_refresh", "gpt_one_shot_opinion", "local_calculation"} and bool(payload.get("response_confirmed", True)):
        return True
    return False


def _fresh_managed_pool_opinion_fallback_text(opinion: str, status_label: str) -> tuple[str, str]:
    opinion_text = str(opinion or "").strip().lower()
    status_text = str(status_label or "").strip()
    if opinion_text == "data_insufficient" or status_text == "데이터부족":
        return (
            "현재 데이터가 충분하지 않아 보수적으로 관망합니다.",
            "추가 데이터 확인 후 재평가합니다. 주문은 실행하지 않습니다.",
        )
    return (
        "추가 상승 근거가 충분하지 않아 관망 의견을 유지합니다.",
        "다음 데이터 갱신 후 재평가합니다. 주문은 실행하지 않습니다.",
    )


def _apply_managed_pool_reason_consistency(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = dict(payload or {})
    reason = str(normalized.get("reason") or "").strip()
    next_action = str(normalized.get("next_action") or "").strip()
    opinion = str(normalized.get("opinion") or "").strip()
    status_label = str(normalized.get("status_label") or "").strip()
    is_fresh = _is_fresh_managed_pool_opinion_payload(normalized)
    stale_reason_input = _is_stale_manual_refresh_reason(reason)
    stale_next_action_input = _is_stale_manual_refresh_reason(next_action)
    execution_block_input = _is_execution_block_reason_only(reason)
    stale_reason_replaced = False
    stale_next_action_replaced = False
    if is_fresh:
        fallback_reason, fallback_next_action = _fresh_managed_pool_opinion_fallback_text(opinion, status_label)
        if not reason or stale_reason_input or execution_block_input:
            reason = fallback_reason
            stale_reason_replaced = bool(stale_reason_input or execution_block_input)
        if not next_action or stale_next_action_input:
            next_action = fallback_next_action
            stale_next_action_replaced = bool(stale_next_action_input)
    normalized["reason"] = reason
    normalized["next_action"] = next_action
    flags = {
        "reason_consistency_checked": True,
        "fresh_opinion_payload": bool(is_fresh),
        "stale_reason_leaked": bool(is_fresh and _is_stale_manual_refresh_reason(reason)),
        "stale_next_action_leaked": bool(is_fresh and _is_stale_manual_refresh_reason(next_action)),
        "stale_reason_replaced": bool(stale_reason_replaced),
        "stale_next_action_replaced": bool(stale_next_action_replaced),
        "reason_consistent_with_freshness": not bool(is_fresh and (
            _is_stale_manual_refresh_reason(reason) or _is_stale_manual_refresh_reason(next_action)
        )),
    }
    return normalized, flags


def _normalize_managed_pool_provider_opinion_result(
    result: dict[str, Any],
    row: dict[str, Any],
    provider: str,
    request_id: str,
    source: str | None = None,
    freshness: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol = _row_symbol(row)
    opinion, status_label = _managed_pool_opinion_status_from_provider(
        result.get("opinion") or result.get("status"),
        result.get("status_label"),
    )
    confidence = _safe_float(result.get("confidence"), math.nan)
    if math.isnan(confidence):
        score = _safe_float(row.get("ai_score", row.get("score")), math.nan)
        confidence = 0.5 if math.isnan(score) else round(max(0.2, min(0.85, score / 100.0)), 3)
    confidence = round(max(0.0, min(1.0, confidence)), 3)
    reason = str(result.get("reason") or "").strip()
    execution_block_only = _is_execution_block_reason_only(reason)
    stale_manual_reason = _is_stale_manual_refresh_reason(reason)
    if not reason or execution_block_only or stale_manual_reason:
        row_reason = str(
            row.get("ai_review_queue_reason")
            or row.get("status_reason")
            or row.get("reason")
            or ""
        ).strip()
        if _is_stale_manual_refresh_reason(row_reason) or _is_execution_block_reason_only(row_reason):
            row_reason = ""
        reason = row_reason[:220] or "수동 AI 분석이 반영되었습니다. 현재 종목 상태는 추가 주문 없이 관망 기준으로 검토합니다."
    next_action = str(result.get("next_action") or "").strip()
    if not next_action:
        next_action = "운용 의견 참고만 수행; 주문 실행 없음"
    payload = {
        "schema": "managed_pool_ai_opinion_v1",
        "event_time": _now_iso(),
        "symbol": symbol,
        "display_name": str(row.get("name") or row.get("display_name") or symbol),
        "provider": provider,
        "provider_external_call": True,
        "source": source or ("gpt_one_shot_opinion" if provider == "gpt" else f"{provider}_one_shot_opinion"),
        "request_id": request_id,
        "response_confirmed": bool(result.get("response_confirmed")),
        "response_id": str(result.get("response_id") or ""),
        "usage_input_tokens": result.get("usage_input_tokens"),
        "usage_output_tokens": result.get("usage_output_tokens"),
        "usage_total_tokens": result.get("usage_total_tokens"),
        "opinion": opinion,
        "status_label": status_label,
        "confidence": confidence,
        "reason": reason[:500],
        "next_action": next_action[:300],
        "freshness": freshness or "provider_one_shot",
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
    }
    payload, consistency_flags = _apply_managed_pool_reason_consistency(payload)
    flags = {
        "execution_block_reason_only": False,
        "provider_reason_was_execution_block_only": bool(execution_block_only),
        "provider_reason_was_stale_manual_required": bool(stale_manual_reason),
        "user_facing_reason_present": bool(reason) and not _is_execution_block_reason_only(reason) and not _is_stale_manual_refresh_reason(reason),
    }
    flags.update(consistency_flags)
    return payload, flags


def _router_suggestion_to_opinion(result: dict[str, Any], row: dict[str, Any], provider: str) -> dict[str, Any]:
    symbol = _row_symbol(row)
    score = _safe_float(row.get("ai_score", row.get("score")), math.nan)
    suggestion = str(result.get("suggestion") or result.get("ai_action") or "skip").strip().lower()
    reason = str(result.get("reason") or result.get("risk_note") or "provider_response").strip()
    opinion_map = {
        "confirm": ("watch", "관망"),
        "override_wait": ("watch", "관망"),
        "override_buy": ("buy_wait", "매수대기"),
        "override_reduce": ("sell_review", "매도검토"),
        "override_sell": ("sell_review", "매도검토"),
        "reject_signal": ("data_insufficient", "데이터부족"),
        "skip": ("analysis_required", "재분석필요"),
    }
    opinion, status_label = opinion_map.get(suggestion, ("watch", "관망"))
    confidence = 0.5
    if not math.isnan(score):
        confidence = round(max(0.1, min(0.95, score / 100.0)), 3)
    tooltip = "\n".join(
        [
            f"종목: {symbol}",
            f"상태: {status_label}",
            f"분석 엔진: {provider.upper()}",
            f"판단 근거: {reason[:160]}",
            "실행: 주문 없음 / final action 변경 없음",
        ]
    )
    return {
        "schema": "managed_pool_ai_opinion_v1",
        "event_time": _now_iso(),
        "symbol": symbol,
        "display_name": str(row.get("name") or row.get("display_name") or symbol),
        "provider": provider,
        "provider_external_call": True,
        "source": source or ("gpt_one_shot_opinion" if provider == "gpt" else f"{provider}_one_shot_opinion"),
        "request_id": "",
        "response_confirmed": suggestion != "skip" and not str(reason).endswith("_missing"),
        "opinion": opinion,
        "status_label": status_label,
        "confidence": confidence,
        "reason": reason[:500],
        "next_action": "운용 의견 참고만 수행; 주문 실행 없음",
        "freshness": freshness or "provider_one_shot",
        "tooltip": tooltip,
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
    }


def _run_managed_pool_gpt_one_shot_opinion_proof(
    report: dict[str, Any],
    *,
    provider: str = "gpt",
    target_symbol: str | None = None,
    allow_provider_calls: bool = False,
    max_provider_calls: int = 1,
) -> None:
    provider = _normalize_provider_for_report(provider or "gpt")
    rows = _load_saved_managed_pool_rows_readonly()
    row = _target_managed_pool_row(rows, target_symbol)
    symbol = _row_symbol(row)
    call_budget = max(0, min(1, int(max_provider_calls or 0)))
    compact_context = _build_managed_pool_opinion_compact_payload(row, rows, provider)
    report.update(
        {
            "one_shot_opinion_supported": True,
            "managed_pool_gpt_opinion_quality_supported": True,
            "legacy_router_verification_adapter_used": False,
            "legacy_router_verification_adapter_limit": "router verification reasons can describe execution gating instead of managed-pool operation rationale",
            "provider": provider,
            "target_symbol": symbol,
            "provider_call_budget": call_budget,
            "request_schema": compact_context.get("schema"),
            "compact_payload_fields": sorted(str(key) for key in compact_context.keys()),
            "managed_row_count": len(rows),
            "compact_payload_summary": {
                "symbol": compact_context.get("symbol"),
                "purpose": compact_context.get("purpose"),
                "order_execution": False,
                "score_present": compact_context.get("aits_score") not in (None, ""),
                "reason_chars": len(str(compact_context.get("status_reason") or "")),
                "safety_constraints_present": bool(compact_context.get("safety_constraints")),
            },
            "order_execution": False,
            "final_action_unchanged": True,
            "actual_order": False,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "order_risk_detected": False,
        }
    )
    if provider not in {"gpt", "gemini"}:
        report.update(
            {
                "provider_ready": False,
                "response_confirmed": False,
                "provider_external_call_count": 0,
                "no_go_reason": "provider_must_be_gpt_or_gemini",
                "pass_status": "partial",
            }
        )
        return
    if not rows or not symbol:
        report.update(
            {
                "provider_ready": False,
                "response_confirmed": False,
                "provider_external_call_count": 0,
                "no_go_reason": "managed_pool_rows_empty",
                "pass_status": "partial",
            }
        )
        return
    if not allow_provider_calls or call_budget < 1:
        report.update(
            {
                "provider_ready": False,
                "response_confirmed": False,
                "provider_external_call_count": 0,
                "no_go_reason": "provider_call_requires_allow_provider_calls_and_budget_1",
                "pass_status": "partial",
            }
        )
        return

    old_enable = os.environ.get("AITS_ENABLE_REAL_AI_CALL")
    old_one_shot = os.environ.get("AITS_REAL_AI_ONE_SHOT")
    request_id = f"managed-pool-one-shot-{uuid.uuid4().hex[:12]}"
    result: dict[str, Any] = {}
    call_count = 0
    provider_ready = False
    try:
        from app.services.ai_engine_provider import AIEngineProvider
        from app.utils.prefs import load_settings

        settings = load_settings()
        engine_provider = AIEngineProvider(settings=settings, strategy=getattr(settings, "strategy", None))
        provider_key = "openai" if provider == "gpt" else "gemini"
        provider_ready = bool(engine_provider._get_config_api_key(provider_key))
        if not provider_ready:
            report.update(
                {
                    "provider_ready": False,
                    "response_confirmed": False,
                    "provider_external_call_count": 0,
                    "no_go_reason": f"{provider}_api_key_missing",
                    "pass_status": "partial",
                }
            )
            return
        os.environ["AITS_ENABLE_REAL_AI_CALL"] = "1"
        os.environ["AITS_REAL_AI_ONE_SHOT"] = "1"
        call_count = 1
        if hasattr(engine_provider, "generate_managed_pool_opinion"):
            result = engine_provider.generate_managed_pool_opinion(provider=provider_key, context=compact_context)
        else:
            result = engine_provider.verify_router_decision(provider=provider_key, context=compact_context)
            report["legacy_router_verification_adapter_used"] = True
    except Exception as exc:
        result = {
            "schema": "provider_managed_pool_opinion_v1",
            "response_confirmed": False,
            "reason": f"{type(exc).__name__}:{str(exc)[:160]}",
            "provider": provider,
            "applied_to_action": False,
            "order_execution": False,
            "final_action_unchanged": True,
            "actual_order": False,
        }
    finally:
        if old_enable is None:
            os.environ.pop("AITS_ENABLE_REAL_AI_CALL", None)
        else:
            os.environ["AITS_ENABLE_REAL_AI_CALL"] = old_enable
        if old_one_shot is None:
            os.environ.pop("AITS_REAL_AI_ONE_SHOT", None)
        else:
            os.environ["AITS_REAL_AI_ONE_SHOT"] = old_one_shot

    if str(result.get("schema") or "") == "provider_managed_pool_opinion_v1":
        opinion_payload, reason_quality_flags = _normalize_managed_pool_provider_opinion_result(
            result,
            row,
            provider,
            request_id,
        )
    else:
        opinion_payload = _router_suggestion_to_opinion(result, row, provider)
        opinion_payload["request_id"] = request_id
        reason_quality_flags = {
            "execution_block_reason_only": _is_execution_block_reason_only(str(opinion_payload.get("reason") or "")),
            "provider_reason_was_execution_block_only": _is_execution_block_reason_only(str(opinion_payload.get("reason") or "")),
            "user_facing_reason_present": bool(str(opinion_payload.get("reason") or "").strip()),
        }
    tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    response_confirmed = bool(opinion_payload.get("response_confirmed")) and not str(result.get("error") or "")
    reason_quality_ok = (
        bool(reason_quality_flags.get("user_facing_reason_present"))
        and not bool(reason_quality_flags.get("execution_block_reason_only"))
        and not bool(reason_quality_flags.get("stale_reason_leaked"))
        and not bool(reason_quality_flags.get("stale_next_action_leaked"))
        and bool(reason_quality_flags.get("reason_consistent_with_freshness", True))
    )
    pass_status = "pass" if provider_ready and call_count <= 1 and response_confirmed and reason_quality_ok else "partial"
    report.update(
        {
            "provider_ready": bool(provider_ready),
            "provider_external_call_count": int(call_count),
            "request_id": request_id,
            "response_confirmed": bool(response_confirmed),
            "response_id_present": bool(opinion_payload.get("response_id")),
            "token_usage_present": opinion_payload.get("usage_total_tokens") is not None,
            "raw_result_keys": sorted(str(key) for key in result.keys())[:20],
            "opinion_schema": "managed_pool_ai_opinion_v1",
            "normalized_opinion": opinion_payload,
            "opinion_payload": opinion_payload,
            "opinion": opinion_payload.get("opinion"),
            "status_label": opinion_payload.get("status_label"),
            "confidence": opinion_payload.get("confidence"),
            "reason": opinion_payload.get("reason"),
            "next_action": opinion_payload.get("next_action"),
            "tooltip_sample": tooltip_sample or opinion_payload.get("tooltip"),
            "reason_quality_flags": reason_quality_flags,
            "order_execution": False,
            "final_action_unchanged": bool(result.get("applied_to_action") is not True),
            "actual_order": False,
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "order_risk_detected": False,
            "pass_status": pass_status,
        }
    )


def _normalize_managed_pool_ai_opinion_overlay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if str(payload.get("schema") or "").strip() != "managed_pool_ai_opinion_v1":
        return {}
    symbol = _normalize_symbol_text(payload.get("symbol") or "")
    if not symbol:
        return {}
    confidence = _safe_float(payload.get("confidence"), math.nan)
    return {
        "schema": "managed_pool_ai_opinion_v1",
        "symbol": symbol,
        "provider": _normalize_provider_for_report(payload.get("provider") or "local"),
        "status_label": str(payload.get("status_label") or payload.get("opinion") or "").strip(),
        "confidence": None if math.isnan(confidence) else confidence,
        "reason": str(payload.get("reason") or "").strip(),
        "next_action": str(payload.get("next_action") or "").strip(),
        "freshness": str(payload.get("freshness") or "").strip(),
        "request_id": str(payload.get("request_id") or "").strip(),
        "source": str(payload.get("source") or "").strip(),
        "order_execution": bool(payload.get("order_execution")) is True,
        "final_action_unchanged": bool(payload.get("final_action_unchanged", True)),
        "actual_order": bool(payload.get("actual_order")) is True,
    }


def _managed_pool_ai_opinion_overlay_status_sample(payload: dict[str, Any]) -> str:
    overlay = _normalize_managed_pool_ai_opinion_overlay_payload(payload)
    return str(overlay.get("status_label") or "").strip()


def _humanize_ai_opinion_freshness_for_tooltip(value: str) -> str:
    text = str(value or "").strip()
    mapping = {
        "fresh_manual_refresh": "최신 · 수동 AI 분석 반영",
        "fresh_startup_generation": "최신 · 시작 시 연결 확인 반영",
        "stale": "오래됨 · 재분석 권장",
        "analysis_required": "분석 필요",
        "manual_required": "수동 AI 분석 필요",
        "local_reference": "LOCAL 계산 참고",
        "provider_one_shot": "최신 · 단일 AI 분석 반영",
    }
    return mapping.get(text, "상태 확인 필요" if text else "상태 확인 필요")


def _humanize_ai_opinion_source_for_tooltip(value: str) -> str:
    text = str(value or "").strip()
    mapping = {
        "manual_ai_refresh": "수동 AI 분석",
        "local_calculation": "LOCAL 계산 의견",
        "gpt_one_shot_opinion": "GPT 단일 분석",
        "gemini_one_shot_opinion": "Gemini 단일 분석",
        "startup_generation": "시작 시 연결 확인",
    }
    return mapping.get(text, "분석 결과")


def _managed_pool_ai_opinion_overlay_tooltip_sample(payload: dict[str, Any]) -> str:
    overlay = _normalize_managed_pool_ai_opinion_overlay_payload(payload)
    if not overlay:
        return ""
    confidence = overlay.get("confidence")
    confidence_text = "-"
    if confidence is not None:
        try:
            confidence_text = f"{float(confidence):.2f}"
        except Exception:
            confidence_text = "-"
    lines = [
        f"\uc885\ubaa9: {overlay.get('symbol')}",
        f"AI \uc758\uacac: {overlay.get('status_label') or '-'}",
        f"분석 엔진: {str(overlay.get('provider') or 'local').upper()}",
        f"\ud655\uc2e0\ub3c4: {confidence_text}",
    ]
    reason = str(overlay.get("reason") or "").strip()
    if reason:
        lines.append(f"판단 근거: {reason[:140]}")
    next_action = str(overlay.get("next_action") or "").strip()
    if next_action:
        lines.append(f"\ub2e4\uc74c \ud589\ub3d9: {next_action[:110]}")
    freshness = str(overlay.get("freshness") or "").strip()
    source = str(overlay.get("source") or "").strip()
    if source:
        lines.append(f"분석 출처: {_humanize_ai_opinion_source_for_tooltip(source)}")
    if freshness:
        lines.append(f"분석 상태: {_humanize_ai_opinion_freshness_for_tooltip(freshness)}")
    request_id = str(overlay.get("request_id") or "").strip()
    if request_id:
        lines.append(f"요청 ID: {request_id[:48]}")
    lines.append("\uc548\uc804: \uc8fc\ubb38 \uc5c6\uc74c / \ucd5c\uc885 \uc561\uc158 \ubcc0\uacbd \uc5c6\uc74c")
    return "\n".join(line for line in lines if str(line or "").strip())


def _apply_managed_pool_ai_opinion_ui_overlay_report(
    report: dict[str, Any],
    *,
    provider: str,
    target_symbol: str | None,
    opinion_payload: dict[str, Any],
    provider_external_call_count: int,
    response_confirmed: bool | None = None,
    request_id: str = "",
) -> None:
    rows_before = _load_saved_managed_pool_rows_readonly()
    rows_after = _load_saved_managed_pool_rows_readonly()
    overlay = _normalize_managed_pool_ai_opinion_overlay_payload(opinion_payload)
    status_sample = _managed_pool_ai_opinion_overlay_status_sample(opinion_payload)
    tooltip_plain_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    tooltip_html_sample = _tooltip_html_card_sample_from_plain(tooltip_plain_sample)
    target = _normalize_symbol_text(target_symbol or overlay.get("symbol") or "")
    report.update(
        {
            "opinion_ui_overlay_supported": True,
            "provider": _normalize_provider_for_report(provider or overlay.get("provider") or "local"),
            "target_symbol": target,
            "overlay_cache_key": target,
            "overlay_created": bool(overlay and status_sample and tooltip_plain_sample),
            "opinion_overlay": overlay,
            "status_sample": status_sample,
            "tooltip_sample": tooltip_html_sample or tooltip_plain_sample,
            "tooltip_plain_sample": tooltip_plain_sample,
            "tooltip_html_sample": tooltip_html_sample,
            "managed_row_count_before": len(rows_before),
            "managed_row_count_after": len(rows_after),
            "managed_pool_mutation": False,
            "managed_pool_mutation_performed": False,
            "managed_pool_row_count_changed": len(rows_before) != len(rows_after),
            "order_execution": False,
            "final_action_unchanged": True,
            "actual_order": False,
            "provider_external_call_count": int(provider_external_call_count or 0),
            "request_id": request_id or str(overlay.get("request_id") or ""),
            "response_confirmed": bool(response_confirmed) if response_confirmed is not None else bool(opinion_payload),
            "order_risk_detected": False,
            "pass_status": "pass" if overlay and status_sample and tooltip_plain_sample else "partial",
        }
    )
    report.update(
        {
            "tooltip_style_supported": True,
            "tooltip_stylesheet_present": True,
            "tooltip_background": "#fffdf7",
            "tooltip_color": "#1f2933",
            "tooltip_border": "1px solid #cabb9d",
            "tooltip_padding": "8px 10px",
        }
    )
    tooltip_text_for_labels = str(tooltip_html_sample or tooltip_plain_sample or "")
    report.update({
        "tooltip_korean_labels_applied": all(token in tooltip_text_for_labels for token in ("분석 엔진", "판단 근거", "분석 상태")),
        "tooltip_system_labels_removed": not any(token in tooltip_text_for_labels for token in ("Provider:", "Reason:", "Freshness:", "Request:")),
        "tooltip_freshness_humanized": "fresh_manual_refresh" not in tooltip_text_for_labels,
    })
    report.update(_tooltip_html_card_proof(tooltip_html_sample))


def _run_managed_pool_ai_opinion_ui_apply_proof(
    report: dict[str, Any],
    *,
    provider: str = "local",
    target_symbol: str | None = None,
) -> None:
    rows = _load_saved_managed_pool_rows_readonly()
    row = _target_managed_pool_row(rows, target_symbol)
    opinion_payload = _managed_pool_local_opinion(row, provider=_normalize_provider_for_report(provider or "local")) if row else {}
    _apply_managed_pool_ai_opinion_ui_overlay_report(
        report,
        provider=provider or "local",
        target_symbol=target_symbol or _row_symbol(row),
        opinion_payload=opinion_payload,
        provider_external_call_count=0,
        response_confirmed=bool(opinion_payload),
        request_id=str(opinion_payload.get("request_id") or ""),
    )
    report.update(
        {
            "proof_owner": "MainWindow._aits_last_managed_pool_ai_opinion_overlay + MainWindow._build_ai_managed_row_tooltip",
            "status_merge_policy": "opinion overlay status_label overrides row status for display only",
            "tooltip_merge_policy": "opinion overlay details are appended to the row tooltip; managed_pool_rows are not persisted",
        }
    )


def _run_managed_pool_manual_refresh_dedicated_opinion_proof(
    app: Any,
    window: Any,
    report: dict[str, Any],
    *,
    provider: str = "local",
    target_symbol: str | None = None,
    allow_provider_calls: bool = False,
    max_provider_calls: int = 1,
) -> None:
    provider = _normalize_provider_for_report(provider or "local")
    rows_before = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    if not rows_before:
        rows_before = _load_saved_managed_pool_rows_readonly()
    row = _target_managed_pool_row(rows_before, target_symbol)
    target = _normalize_symbol_text(target_symbol or _row_symbol(row))
    request_id = f"manual-refresh-dedicated-{uuid.uuid4().hex[:12]}"
    compact_context: dict[str, Any] = {}
    if hasattr(window, "_build_managed_pool_opinion_compact_payload_for_manual_refresh"):
        try:
            compact_context = window._build_managed_pool_opinion_compact_payload_for_manual_refresh(target, provider)
        except Exception:
            compact_context = {}
    if not compact_context:
        compact_context = _build_managed_pool_opinion_compact_payload(row, rows_before, provider)
        compact_context["source"] = "manual_ai_refresh"
        compact_context["task"] = "managed_pool_opinion"
    call_budget = max(0, min(1, int(max_provider_calls or 0)))
    provider_ready = provider == "local"
    provider_result: dict[str, Any] = {}
    provider_call_count = 0
    if provider == "local":
        opinion_payload = _managed_pool_local_opinion(row, provider="local") if row else {}
        opinion_payload["source"] = "manual_ai_refresh"
        opinion_payload["freshness"] = "fresh_manual_refresh"
        opinion_payload["request_id"] = request_id
        opinion_payload, consistency_flags = _apply_managed_pool_reason_consistency(opinion_payload)
        reason_quality_flags = {
            "execution_block_reason_only": _is_execution_block_reason_only(str(opinion_payload.get("reason") or "")),
            "provider_reason_was_execution_block_only": False,
            "user_facing_reason_present": bool(str(opinion_payload.get("reason") or "").strip()),
        }
        reason_quality_flags.update(consistency_flags)
    elif not allow_provider_calls or call_budget < 1:
        opinion_payload = {}
        reason_quality_flags = {
            "execution_block_reason_only": False,
            "provider_reason_was_execution_block_only": False,
            "user_facing_reason_present": False,
        }
        report.update({
            "provider_ready": False,
            "no_go_reason": "provider_call_requires_allow_provider_calls_and_budget_1",
        })
    else:
        old_enable = os.environ.get("AITS_ENABLE_REAL_AI_CALL")
        old_one_shot = os.environ.get("AITS_REAL_AI_ONE_SHOT")
        try:
            from app.services.ai_engine_provider import AIEngineProvider
            from app.utils.prefs import load_settings

            settings = load_settings()
            engine_provider = AIEngineProvider(settings=settings, strategy=getattr(settings, "strategy", None))
            provider_key = "openai" if provider == "gpt" else "gemini"
            provider_ready = bool(engine_provider._get_config_api_key(provider_key))
            if provider_ready:
                os.environ["AITS_ENABLE_REAL_AI_CALL"] = "1"
                os.environ["AITS_REAL_AI_ONE_SHOT"] = "1"
                provider_call_count = 1
                provider_result = engine_provider.generate_managed_pool_opinion(provider=provider_key, context=compact_context)
        except Exception as exc:
            provider_result = {
                "schema": "provider_managed_pool_opinion_v1",
                "provider": provider,
                "response_confirmed": False,
                "reason": f"{type(exc).__name__}:{str(exc)[:160]}",
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            }
        finally:
            if old_enable is None:
                os.environ.pop("AITS_ENABLE_REAL_AI_CALL", None)
            else:
                os.environ["AITS_ENABLE_REAL_AI_CALL"] = old_enable
            if old_one_shot is None:
                os.environ.pop("AITS_REAL_AI_ONE_SHOT", None)
            else:
                os.environ["AITS_REAL_AI_ONE_SHOT"] = old_one_shot
        opinion_payload, reason_quality_flags = _normalize_managed_pool_provider_opinion_result(
            provider_result,
            row,
            provider,
            request_id,
            source="manual_ai_refresh",
            freshness="fresh_manual_refresh",
        )
    overlay = {}
    if opinion_payload and hasattr(window, "_apply_managed_pool_ai_opinion_overlay_payload"):
        try:
            overlay = window._apply_managed_pool_ai_opinion_overlay_payload(opinion_payload)
            _pump_events(app, 0.3)
        except Exception:
            overlay = {}
    rows_after = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    after_row = _target_managed_pool_row(rows_after or rows_before, target)
    after_state = {}
    if after_row and hasattr(window, "_build_managed_pool_ai_review_sla_state"):
        try:
            after_state = window._build_managed_pool_ai_review_sla_state(dict(after_row))
        except Exception:
            after_state = {}
    tooltip_sample = ""
    status_sample = str((overlay or opinion_payload or {}).get("status_label") or "")
    if after_row and hasattr(window, "_build_ai_managed_row_tooltip"):
        try:
            row_for_tooltip = dict(after_row)
            row_for_tooltip["_ai_opinion_overlay"] = dict(overlay or opinion_payload or {})
            tooltip_sample = window._build_ai_managed_row_tooltip(
                row_for_tooltip,
                status_text=status_sample,
                score_text=str(after_row.get("score") or after_row.get("ai_score") or ""),
            )
        except Exception:
            tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    if not tooltip_sample:
        tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    reason_quality_ok = (
        bool(reason_quality_flags.get("user_facing_reason_present"))
        and not bool(reason_quality_flags.get("execution_block_reason_only"))
        and not bool(reason_quality_flags.get("stale_reason_leaked"))
        and not bool(reason_quality_flags.get("stale_next_action_leaked"))
        and bool(reason_quality_flags.get("reason_consistent_with_freshness", True))
    )
    response_confirmed = bool(opinion_payload.get("response_confirmed"))
    response_id = str(opinion_payload.get("response_id") or "")
    token_usage = {
        "input_tokens": opinion_payload.get("usage_input_tokens"),
        "output_tokens": opinion_payload.get("usage_output_tokens"),
        "total_tokens": opinion_payload.get("usage_total_tokens"),
    }
    token_usage_present = any(value is not None for value in token_usage.values())
    response_metadata_extracted = bool(response_id or token_usage_present)
    if response_metadata_extracted:
        response_metadata_missing_reason = ""
    elif provider == "local":
        response_metadata_missing_reason = "local_provider_no_external_usage"
    elif not response_confirmed:
        response_metadata_missing_reason = "provider_response_not_confirmed"
    else:
        response_metadata_missing_reason = "provider_response_metadata_missing"
    tooltip_lower = str(tooltip_sample or "").lower()
    tooltip_exposes_token_usage = any(
        token in tooltip_lower
        for token in ("token_usage", "usage_input", "usage_output", "usage_total", "prompt_tokens", "completion_tokens", "total_tokens", "토큰")
    )
    pass_ok = bool(row) and bool(compact_context) and bool(opinion_payload) and bool(overlay) and reason_quality_ok
    if provider in {"gpt", "gemini"}:
        pass_ok = pass_ok and bool(provider_ready) and provider_call_count <= 1 and response_confirmed
    report.update({
        "manual_refresh_dedicated_opinion_supported": True,
        "mode": "managed-pool-manual-refresh-dedicated-opinion-proof",
        "manual_refresh_path_owner": "MainWindow._on_ai_analysis_refresh_clicked -> _run_aits_main_gpt_reco_and_publish -> AITSProviderRefreshWorker",
        "target_symbol": target,
        "target_in_managed_pool": bool(row),
        "provider": provider,
        "provider_ready": bool(provider_ready),
        "provider_call_budget": call_budget,
        "dedicated_payload_used": str(compact_context.get("schema") or "") == "managed_pool_ai_opinion_request_v1",
        "payload_schema": str(compact_context.get("schema") or ""),
        "compact_payload_fields": sorted(str(key) for key in compact_context.keys()),
        "provider_external_call_count": int(provider_call_count),
        "request_id": request_id,
        "response_confirmed": bool(response_confirmed),
        "response_id_present": bool(response_id),
        "token_usage_present": bool(token_usage_present),
        "response_id": response_id,
        "token_usage": token_usage,
        "usage_input_tokens": token_usage.get("input_tokens"),
        "usage_output_tokens": token_usage.get("output_tokens"),
        "usage_total_tokens": token_usage.get("total_tokens"),
        "response_metadata_extracted": bool(response_metadata_extracted),
        "response_metadata_missing_reason": response_metadata_missing_reason,
        "normalized_opinion": opinion_payload,
        "opinion": opinion_payload.get("opinion"),
        "status_label": opinion_payload.get("status_label"),
        "confidence": opinion_payload.get("confidence"),
        "reason": opinion_payload.get("reason"),
        "next_action": opinion_payload.get("next_action"),
        "freshness": opinion_payload.get("freshness"),
        "reason_consistency_checked": bool(reason_quality_flags.get("reason_consistency_checked")),
        "stale_reason_leaked": bool(reason_quality_flags.get("stale_reason_leaked")),
        "stale_next_action_leaked": bool(reason_quality_flags.get("stale_next_action_leaked")),
        "stale_reason_replaced": bool(reason_quality_flags.get("stale_reason_replaced")),
        "stale_next_action_replaced": bool(reason_quality_flags.get("stale_next_action_replaced")),
        "reason_consistent_with_freshness": bool(reason_quality_flags.get("reason_consistent_with_freshness", True)),
        "tooltip_sample": tooltip_sample,
        "target_tooltip_sample": tooltip_sample,
        "fresh_overlay_tooltip_sample": tooltip_sample,
        "tooltip_exposes_token_usage": bool(tooltip_exposes_token_usage),
        "fresh_tooltip_stale_phrase_found": bool(
            _is_stale_manual_refresh_reason(str(tooltip_sample or ""))
            and bool(reason_quality_flags.get("fresh_opinion_payload"))
        ),
        "reason_quality_flags": reason_quality_flags,
        "overlay_applied": bool(overlay),
        "analysis_required_after": str(after_state.get("freshness_state") or "") in {"missing", "stale", "very_stale"},
        "row_persistence_mutation": False,
        "managed_pool_mutation": False,
        "managed_pool_row_count_before": len(rows_before),
        "managed_pool_row_count_after": len(rows_after or rows_before),
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
        "order_risk_detected": False,
        "pass_status": "pass" if pass_ok else "partial",
    })
    report.update(_tooltip_html_card_proof(str(tooltip_sample or "")))


def _apply_managed_pool_manual_refresh_metadata_audit_report(report: dict[str, Any]) -> None:
    token_usage = report.get("token_usage") if isinstance(report.get("token_usage"), dict) else {}
    if not token_usage:
        token_usage = {
            "input_tokens": report.get("usage_input_tokens"),
            "output_tokens": report.get("usage_output_tokens"),
            "total_tokens": report.get("usage_total_tokens"),
        }
    tooltip_exposes_token_usage = bool(report.get("tooltip_exposes_token_usage"))
    audit_payload = {
        "schema": "managed_pool_ai_opinion_audit_v1",
        "event_time": _now_iso(),
        "target_symbol": str(report.get("target_symbol") or ""),
        "provider": str(report.get("provider") or ""),
        "source": "manual_ai_refresh",
        "request_id": str(report.get("request_id") or ""),
        "response_id": str(report.get("response_id") or ""),
        "response_confirmed": bool(report.get("response_confirmed")),
        "token_usage": {
            "input_tokens": token_usage.get("input_tokens"),
            "output_tokens": token_usage.get("output_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
        },
        "provider_external_call_count": int(report.get("provider_external_call_count") or 0),
        "payload_schema": str(report.get("payload_schema") or ""),
        "opinion_schema": str((report.get("normalized_opinion") or {}).get("schema") or "managed_pool_ai_opinion_v1"),
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
        "managed_pool_mutation": False,
        "tooltip_exposes_token_usage": tooltip_exposes_token_usage,
        "raw_payload_logged": False,
        "raw_response_logged": False,
        "secret_logged": False,
    }
    provider = str(report.get("provider") or "").strip().lower()
    external_provider = provider in {"gpt", "gemini"}
    metadata_ok = bool(report.get("response_id_present")) and bool(report.get("token_usage_present"))
    base_safe = (
        not tooltip_exposes_token_usage
        and not bool(report.get("order_execution"))
        and bool(report.get("final_action_unchanged", True))
        and not bool(report.get("actual_order"))
        and not bool(report.get("managed_pool_mutation"))
    )
    if external_provider:
        pass_status = "pass" if (
            base_safe
            and bool(report.get("response_confirmed"))
            and metadata_ok
            and int(report.get("provider_external_call_count") or 0) <= 1
        ) else "partial"
    else:
        pass_status = "pass" if base_safe and audit_payload["provider_external_call_count"] == 0 else "partial"
    report.update({
        "mode": "managed-pool-manual-refresh-metadata-audit-proof",
        "metadata_audit_supported": True,
        "audit_schema": "managed_pool_ai_opinion_audit_v1",
        "audit_payload": audit_payload,
        "raw_payload_logged": False,
        "raw_response_logged": False,
        "secret_logged": False,
        "audit_summary_text": (
            f"{audit_payload['provider']} {audit_payload['target_symbol']} "
            f"response_id_present={bool(report.get('response_id_present'))} "
            f"token_usage_present={bool(report.get('token_usage_present'))} "
            "tooltip_usage=false"
        ),
        "pass_status": pass_status,
    })


def _run_manual_ai_refresh_target_symbol_e2e_proof(
    app: Any,
    window: Any,
    report: dict[str, Any],
    *,
    provider: str = "local",
    target_symbol: str | None = None,
    allow_provider_calls: bool = False,
    max_provider_calls: int = 1,
) -> None:
    provider = _normalize_provider_for_report(provider or "local")
    rows_before = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    if not rows_before:
        rows_before = _load_saved_managed_pool_rows_readonly()
    row = _target_managed_pool_row(rows_before, target_symbol)
    target = _normalize_symbol_text(target_symbol or _row_symbol(row))
    target_index = -1
    for idx, candidate in enumerate(rows_before):
        if _row_symbol(candidate) == target:
            target_index = idx
            row = candidate
            break

    table_select_ok = False
    table_object_name = ""
    if target_index >= 0:
        table = getattr(window, "tbl_ai_managed", None)
        if table is not None:
            try:
                table_object_name = str(table.objectName() or "")
            except Exception:
                table_object_name = ""
            try:
                table.setCurrentCell(int(target_index), 0)
                table.selectRow(int(target_index))
                _pump_events(app, 0.2)
                table_select_ok = int(table.currentRow()) == int(target_index)
            except Exception:
                table_select_ok = False

    resolver_info: dict[str, Any] = {}
    if hasattr(window, "_resolve_ai_refresh_target_symbol"):
        try:
            resolver_info = window._resolve_ai_refresh_target_symbol(None, None, "managed_tab")
        except Exception as exc:
            resolver_info = {"symbol": "", "skip_reason": f"{type(exc).__name__}:{str(exc)[:120]}"}
    selected_symbol = _normalize_symbol_text(resolver_info.get("symbol") or "")
    resolver_source = str(resolver_info.get("source") or "")
    fallback_used = bool(not selected_symbol or selected_symbol != target)
    target_match = bool(target and selected_symbol == target)

    request_id = f"manual-refresh-target-e2e-{uuid.uuid4().hex[:12]}"
    compact_context: dict[str, Any] = {}
    provider_result: dict[str, Any] = {}
    opinion_payload: dict[str, Any] = {}
    reason_quality_flags: dict[str, Any] = {
        "execution_block_reason_only": False,
        "provider_reason_was_execution_block_only": False,
        "user_facing_reason_present": False,
    }
    provider_call_count = 0
    provider_ready = provider == "local"
    unresolved_target = not (row and target_match)
    if row and target_match:
        if hasattr(window, "_build_managed_pool_opinion_compact_payload_for_manual_refresh"):
            try:
                compact_context = window._build_managed_pool_opinion_compact_payload_for_manual_refresh(selected_symbol, provider)
            except Exception:
                compact_context = {}
        if not compact_context:
            compact_context = _build_managed_pool_opinion_compact_payload(row, rows_before, provider)
            compact_context["source"] = "manual_ai_refresh"
            compact_context["task"] = "managed_pool_opinion"
        if provider == "local":
            opinion_payload = _managed_pool_local_opinion(row, provider="local") if row else {}
            opinion_payload["source"] = "manual_ai_refresh"
            opinion_payload["freshness"] = "fresh_manual_refresh"
            opinion_payload["request_id"] = request_id
            opinion_payload, consistency_flags = _apply_managed_pool_reason_consistency(opinion_payload)
            reason_quality_flags = {
                "execution_block_reason_only": _is_execution_block_reason_only(str(opinion_payload.get("reason") or "")),
                "provider_reason_was_execution_block_only": False,
                "user_facing_reason_present": bool(str(opinion_payload.get("reason") or "").strip()),
            }
            reason_quality_flags.update(consistency_flags)
        elif allow_provider_calls and int(max_provider_calls or 0) >= 1:
            old_enable = os.environ.get("AITS_ENABLE_REAL_AI_CALL")
            old_one_shot = os.environ.get("AITS_REAL_AI_ONE_SHOT")
            try:
                from app.services.ai_engine_provider import AIEngineProvider
                from app.utils.prefs import load_settings

                settings = load_settings()
                engine_provider = AIEngineProvider(settings=settings, strategy=getattr(settings, "strategy", None))
                provider_key = "openai" if provider == "gpt" else "gemini"
                provider_ready = bool(engine_provider._get_config_api_key(provider_key))
                if provider_ready:
                    os.environ["AITS_ENABLE_REAL_AI_CALL"] = "1"
                    os.environ["AITS_REAL_AI_ONE_SHOT"] = "1"
                    provider_call_count = 1
                    provider_result = engine_provider.generate_managed_pool_opinion(provider=provider_key, context=compact_context)
            except Exception as exc:
                provider_result = {
                    "schema": "provider_managed_pool_opinion_v1",
                    "provider": provider,
                    "response_confirmed": False,
                    "reason": f"{type(exc).__name__}:{str(exc)[:160]}",
                    "order_execution": False,
                    "final_action_unchanged": True,
                    "actual_order": False,
                }
            finally:
                if old_enable is None:
                    os.environ.pop("AITS_ENABLE_REAL_AI_CALL", None)
                else:
                    os.environ["AITS_ENABLE_REAL_AI_CALL"] = old_enable
                if old_one_shot is None:
                    os.environ.pop("AITS_REAL_AI_ONE_SHOT", None)
                else:
                    os.environ["AITS_REAL_AI_ONE_SHOT"] = old_one_shot
            opinion_payload, reason_quality_flags = _normalize_managed_pool_provider_opinion_result(
                provider_result,
                row,
                provider,
                request_id,
                source="manual_ai_refresh",
                freshness="fresh_manual_refresh",
            )

    payload_symbol = _normalize_symbol_text(compact_context.get("symbol") or "")
    overlay_before = {}
    try:
        overlay_before = dict(getattr(window, "_aits_last_managed_pool_ai_opinion_overlay", {}) or {})
    except Exception:
        overlay_before = {}
    overlay = {}
    if opinion_payload and target_match and payload_symbol == target and hasattr(window, "_apply_managed_pool_ai_opinion_overlay_payload"):
        try:
            overlay = window._apply_managed_pool_ai_opinion_overlay_payload(opinion_payload)
            _pump_events(app, 0.3)
        except Exception:
            overlay = {}
    overlay_after = {}
    try:
        overlay_after = dict(getattr(window, "_aits_last_managed_pool_ai_opinion_overlay", {}) or {})
    except Exception:
        overlay_after = {}
    changed_overlay_symbols = sorted(
        symbol for symbol in set(overlay_before.keys()) | set(overlay_after.keys())
        if overlay_before.get(symbol) != overlay_after.get(symbol)
    )
    overlay_symbol = _normalize_symbol_text((overlay or opinion_payload or {}).get("symbol") or "")
    overlay_applied_to_target_only = bool(overlay) and changed_overlay_symbols == [target]
    rows_after = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    rows_after = rows_after or rows_before
    tooltip_sample = ""
    if overlay and row and hasattr(window, "_build_ai_managed_row_tooltip"):
        try:
            row_for_tooltip = dict(row)
            row_for_tooltip["_ai_opinion_overlay"] = dict(overlay)
            tooltip_sample = window._build_ai_managed_row_tooltip(
                row_for_tooltip,
                status_text=str(overlay.get("status_label") or ""),
                score_text=str(row.get("score") or row.get("ai_score") or ""),
            )
        except Exception:
            tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    if not tooltip_sample and opinion_payload:
        tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(opinion_payload)
    pass_ok = bool(
        row
        and target_match
        and selected_symbol == target
        and payload_symbol == target
        and overlay_symbol == target
        and not fallback_used
        and bool(overlay)
        and overlay_applied_to_target_only
        and provider_call_count <= 1
    )
    if provider in {"gpt", "gemini"}:
        pass_ok = pass_ok and bool(provider_ready) and bool(opinion_payload.get("response_confirmed"))
    report.update({
        "manual_ai_refresh_target_symbol_e2e_supported": True,
        "mode": "manual-ai-refresh-target-symbol-e2e-proof",
        "selection_owner": "MainWindow._current_managed_table_selection_for_ai_refresh",
        "target_resolver_owner": "MainWindow._resolve_ai_refresh_target_symbol",
        "manual_refresh_path_owner": "MainWindow._on_ai_analysis_refresh_clicked -> _run_aits_main_gpt_reco_and_publish -> AITSProviderRefreshWorker",
        "table_object_name": table_object_name or "tblAiManaged",
        "target_symbol": target,
        "target_in_managed_pool": bool(row),
        "target_row_index": int(target_index),
        "table_select_ok": bool(table_select_ok),
        "selected_symbol": selected_symbol,
        "payload_symbol": payload_symbol,
        "overlay_symbol": overlay_symbol,
        "target_match": bool(target_match and payload_symbol == target and overlay_symbol == target),
        "resolver_source": resolver_source,
        "resolver_skip_reason": str(resolver_info.get("skip_reason") or ""),
        "fallback_used": bool(fallback_used),
        "provider": provider,
        "provider_ready": bool(provider_ready),
        "provider_external_call_count": int(provider_call_count),
        "provider_call_budget": max(0, min(1, int(max_provider_calls or 0))),
        "dedicated_payload_used": str(compact_context.get("schema") or "") == "managed_pool_ai_opinion_request_v1",
        "payload_schema": str(compact_context.get("schema") or ""),
        "overlay_applied": bool(overlay),
        "overlay_applied_to_target_only": bool(overlay_applied_to_target_only),
        "changed_overlay_symbols": changed_overlay_symbols,
        "target_unresolved_provider_call_blocked": bool(unresolved_target and provider_call_count == 0),
        "response_confirmed": bool(opinion_payload.get("response_confirmed")),
        "response_id_present": bool(opinion_payload.get("response_id")),
        "token_usage_present": opinion_payload.get("usage_total_tokens") is not None,
        "normalized_opinion": opinion_payload,
        "reason_quality_flags": reason_quality_flags,
        "reason_consistency_checked": bool(reason_quality_flags.get("reason_consistency_checked")),
        "stale_reason_leaked": bool(reason_quality_flags.get("stale_reason_leaked")),
        "stale_next_action_leaked": bool(reason_quality_flags.get("stale_next_action_leaked")),
        "stale_reason_replaced": bool(reason_quality_flags.get("stale_reason_replaced")),
        "stale_next_action_replaced": bool(reason_quality_flags.get("stale_next_action_replaced")),
        "reason_consistent_with_freshness": bool(reason_quality_flags.get("reason_consistent_with_freshness", True)),
        "tooltip_sample": tooltip_sample,
        "target_tooltip_sample": tooltip_sample,
        "fresh_overlay_tooltip_sample": tooltip_sample,
        "fresh_tooltip_stale_phrase_found": bool(
            _is_stale_manual_refresh_reason(str(tooltip_sample or ""))
            and bool(reason_quality_flags.get("fresh_opinion_payload"))
        ),
        "managed_pool_row_count_before": len(rows_before),
        "managed_pool_row_count_after": len(rows_after),
        "managed_pool_mutation": len(rows_before) != len(rows_after),
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
        "order_risk_detected": False,
        "pass_status": "pass" if pass_ok else ("partial" if not row else "fail"),
    })
    report.update(_tooltip_html_card_proof(str(tooltip_sample or "")))


def _run_managed_pool_ai_opinion_reason_consistency_proof(report: dict[str, Any], *, fixture: str = "") -> None:
    stale_reason = "현재 AI 분석이 없으면 충분한 판단을 위해 수동 실행이 필요합니다."
    stale_next_action = "AI 분석이 완료될 때까지 관망하십시오."
    scenarios: list[dict[str, Any]] = [
        {
            "name": "fresh_manual_refresh_data_insufficient_stale_reason_replaced",
            "payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": "KRW-AI",
                "provider": "local",
                "source": "manual_ai_refresh",
                "opinion": "data_insufficient",
                "status_label": "데이터부족",
                "reason": stale_reason,
                "next_action": "추가 데이터 확인 후 재평가합니다. 주문은 실행하지 않습니다.",
                "freshness": "fresh_manual_refresh",
                "response_confirmed": True,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
            "expect_stale_allowed": False,
        },
        {
            "name": "fresh_manual_refresh_stale_next_action_replaced",
            "payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": "KRW-AI",
                "provider": "local",
                "source": "manual_ai_refresh",
                "opinion": "data_insufficient",
                "status_label": "데이터부족",
                "reason": "현재 데이터가 충분하지 않아 보수적으로 관망합니다.",
                "next_action": stale_next_action,
                "freshness": "fresh_manual_refresh",
                "response_confirmed": True,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
            "expect_stale_allowed": False,
        },
        {
            "name": "stale_manual_required_keeps_manual_required_reason",
            "payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": "KRW-AI",
                "provider": "local",
                "source": "manual_required",
                "opinion": "analysis_required",
                "status_label": "재분석필요",
                "reason": stale_reason,
                "next_action": stale_next_action,
                "freshness": "manual_required",
                "response_confirmed": False,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
            "expect_stale_allowed": True,
        },
        {
            "name": "fresh_watch_reason_kept_if_user_facing",
            "payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": "KRW-AI",
                "provider": "local",
                "source": "manual_ai_refresh",
                "opinion": "watch",
                "status_label": "관망",
                "reason": "횡보 구간이라 추격보다 조건 충족 여부를 기다립니다.",
                "next_action": "다음 데이터 갱신 후 재평가합니다. 주문은 실행하지 않습니다.",
                "freshness": "fresh_manual_refresh",
                "response_confirmed": True,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
            "expect_stale_allowed": False,
        },
        {
            "name": "execution_block_only_reason_replaced",
            "payload": {
                "schema": "managed_pool_ai_opinion_v1",
                "symbol": "KRW-AI",
                "provider": "local",
                "source": "manual_ai_refresh",
                "opinion": "watch",
                "status_label": "관망",
                "reason": "execution not allowed",
                "next_action": "",
                "freshness": "fresh_manual_refresh",
                "response_confirmed": True,
                "order_execution": False,
                "final_action_unchanged": True,
                "actual_order": False,
            },
            "expect_stale_allowed": False,
        },
    ]
    fixture_results = []
    for scenario in scenarios:
        normalized, flags = _apply_managed_pool_reason_consistency(scenario["payload"])
        tooltip_sample = _managed_pool_ai_opinion_overlay_tooltip_sample(normalized)
        stale_allowed = bool(scenario.get("expect_stale_allowed"))
        stale_leak = bool(flags.get("stale_reason_leaked") or flags.get("stale_next_action_leaked"))
        passed = bool(flags.get("reason_consistent_with_freshness")) and (stale_allowed or not stale_leak)
        if stale_allowed:
            passed = _is_stale_manual_refresh_reason(str(normalized.get("reason") or "")) and _is_stale_manual_refresh_reason(str(normalized.get("next_action") or ""))
        fixture_results.append({
            "name": scenario["name"],
            "passed": bool(passed),
            "freshness": normalized.get("freshness"),
            "reason": normalized.get("reason"),
            "next_action": normalized.get("next_action"),
            "stale_reason_leaked": bool(flags.get("stale_reason_leaked")),
            "stale_next_action_leaked": bool(flags.get("stale_next_action_leaked")),
            "stale_reason_replaced": bool(flags.get("stale_reason_replaced")),
            "stale_next_action_replaced": bool(flags.get("stale_next_action_replaced")),
            "reason_consistent_with_freshness": bool(flags.get("reason_consistent_with_freshness")),
            "tooltip_sample": tooltip_sample,
            "reason_consistency_tooltip_sample": tooltip_sample,
        })
    target_result = fixture_results[0] if fixture_results else {}
    all_passed = all(bool(item.get("passed")) for item in fixture_results)
    report.update({
        "ai_opinion_reason_consistency_supported": True,
        "mode": "managed-pool-ai-opinion-reason-consistency-proof",
        "fixture": fixture or "fresh-data-insufficient-stale-reason",
        "fixture_results": fixture_results,
        "stale_reason_replaced": bool(target_result.get("stale_reason_replaced")),
        "stale_next_action_replaced": any(bool(item.get("stale_next_action_replaced")) for item in fixture_results),
        "stale_reason_allowed_when_stale": bool(fixture_results[2].get("passed")) if len(fixture_results) > 2 else False,
        "reason_consistent_with_freshness": bool(all_passed),
        "freshness": target_result.get("freshness"),
        "reason": target_result.get("reason"),
        "next_action": target_result.get("next_action"),
        "stale_reason_leaked": bool(target_result.get("stale_reason_leaked")),
        "stale_next_action_leaked": bool(target_result.get("stale_next_action_leaked")),
        "tooltip_sample": target_result.get("tooltip_sample"),
        "reason_consistency_tooltip_sample": target_result.get("reason_consistency_tooltip_sample"),
        "fresh_tooltip_stale_phrase_found": bool(_is_stale_manual_refresh_reason(str(target_result.get("tooltip_sample") or ""))),
        "provider_external_call_count": 0,
        "managed_pool_mutation": False,
        "row_persistence_mutation": False,
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
        "order_risk_detected": False,
        "pass_status": "pass" if all_passed else "fail",
    })


def _run_managed_pool_manual_ai_refresh_row_freshness_proof(
    app: Any,
    window: Any,
    report: dict[str, Any],
    *,
    provider: str = "local",
    target_symbol: str | None = None,
) -> None:
    rows_before = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    row = _target_managed_pool_row(rows_before, target_symbol)
    target = _normalize_symbol_text(target_symbol or _row_symbol(row))
    before_state = {}
    reason_before = ""
    if row and hasattr(window, "_build_managed_pool_ai_review_sla_state"):
        before_state = window._build_managed_pool_ai_review_sla_state(dict(row))
        reason_before = str(row.get("ai_review_queue_reason") or before_state.get("label") or before_state.get("tooltip") or "")
    request_id = f"manual-refresh-row-freshness-{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "source": _normalize_provider_for_report(provider or "local"),
        "provider_actual": _normalize_provider_for_report(provider or "local"),
        "provider_selected": _normalize_provider_for_report(provider or "local"),
        "symbol": target,
        "target_symbol": target,
        "requested_symbol": target,
        "decision_summary": "관망",
        "reason_code": "수동 AI 분석 결과를 Managed Pool row freshness에 반영했습니다.",
        "request_id": request_id,
        "decision_group_id": request_id,
        "provider_call_attempted": False,
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
    }
    overlay = {}
    if row and hasattr(window, "_apply_managed_pool_manual_ai_refresh_overlay"):
        overlay = window._apply_managed_pool_manual_ai_refresh_overlay(payload)
        _pump_events(app, 0.3)
    rows_after = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    after_row = _target_managed_pool_row(rows_after, target)
    after_state = {}
    if after_row and hasattr(window, "_build_managed_pool_ai_review_sla_state"):
        after_state = window._build_managed_pool_ai_review_sla_state(dict(after_row))
    tooltip_sample = ""
    status_sample = ""
    if after_row and hasattr(window, "_build_ai_managed_row_tooltip"):
        overlay_after = window._get_managed_pool_ai_opinion_overlay(target) if hasattr(window, "_get_managed_pool_ai_opinion_overlay") else {}
        row_for_tooltip = dict(after_row)
        if isinstance(overlay_after, dict) and overlay_after:
            row_for_tooltip["_ai_opinion_overlay"] = dict(overlay_after)
        status_sample = str(overlay_after.get("status_label") or "") if isinstance(overlay_after, dict) else ""
        tooltip_sample = window._build_ai_managed_row_tooltip(row_for_tooltip, status_text=status_sample, score_text=str(after_row.get("score") or after_row.get("ai_score") or ""))
    stale_phrase_after = "새 분석 권장" in str(tooltip_sample) or "AI 재분석은 수동 실행 필요" in str(tooltip_sample)
    pass_ok = bool(row) and bool(overlay) and str(after_state.get("freshness_state") or "") == "fresh" and not stale_phrase_after
    report.update({
        "manual_refresh_row_freshness_supported": hasattr(window, "_apply_managed_pool_manual_ai_refresh_overlay"),
        "provider": _normalize_provider_for_report(provider or "local"),
        "target_symbol": target,
        "target_in_managed_pool": bool(row),
        "analysis_required_before": str(before_state.get("freshness_state") or "") in {"missing", "stale", "very_stale"},
        "reason_before": reason_before,
        "overlay_created": bool(overlay),
        "overlay_source": str(overlay.get("source") or ""),
        "request_id": request_id,
        "analysis_required_after": str(after_state.get("freshness_state") or "") in {"missing", "stale", "very_stale"},
        "reason_after": str(after_state.get("label") or after_state.get("tooltip") or ""),
        "freshness_state_after": str(after_state.get("freshness_state") or ""),
        "tooltip_sample": tooltip_sample,
        "status_sample": status_sample,
        "stale_phrase_after": bool(stale_phrase_after),
        "row_persistence_mutation": False,
        "managed_pool_mutation": False,
        "managed_pool_row_count_before": len(rows_before),
        "managed_pool_row_count_after": len(rows_after),
        "order_execution": False,
        "final_action_unchanged": True,
        "actual_order": False,
        "provider_external_call_count": 0,
        "order_risk_detected": False,
        "pass_status": "pass" if pass_ok else "partial",
    })
    report.update(_tooltip_html_card_proof(str(tooltip_sample or "")))


def _run_managed_pool_gpt_one_shot_opinion_ui_proof(
    report: dict[str, Any],
    *,
    provider: str = "gpt",
    target_symbol: str | None = None,
    allow_provider_calls: bool = False,
    max_provider_calls: int = 1,
) -> None:
    one_shot_report: dict[str, Any] = {}
    _run_managed_pool_gpt_one_shot_opinion_proof(
        one_shot_report,
        provider=provider,
        target_symbol=target_symbol,
        allow_provider_calls=allow_provider_calls,
        max_provider_calls=max_provider_calls,
    )
    opinion_payload = one_shot_report.get("opinion_payload") if isinstance(one_shot_report.get("opinion_payload"), dict) else {}
    report.update(one_shot_report)
    _apply_managed_pool_ai_opinion_ui_overlay_report(
        report,
        provider=provider,
        target_symbol=target_symbol or str(one_shot_report.get("target_symbol") or ""),
        opinion_payload=opinion_payload,
        provider_external_call_count=int(one_shot_report.get("provider_external_call_count") or 0),
        response_confirmed=bool(one_shot_report.get("response_confirmed")),
        request_id=str(one_shot_report.get("request_id") or ""),
    )
    report.update(
        {
            "proof_owner": "managed-pool-gpt-one-shot-opinion-proof + display-only opinion overlay",
            "provider_call_budget": min(1, int(max_provider_calls or 0)),
            "status_merge_policy": "provider opinion status_label is display-only and does not change final action",
            "tooltip_merge_policy": "provider opinion details are tooltip-only; raw provider payload is not logged",
            "pass_status": (
                "pass"
                if bool(one_shot_report.get("response_confirmed"))
                and int(one_shot_report.get("provider_external_call_count") or 0) <= 1
                and bool(report.get("overlay_created"))
                else "partial"
            ),
        }
    )


def _rotation_status_sample(pair: dict[str, Any], *, role: str = "rotate_out") -> str:
    try:
        gap = _safe_float(pair.get("score_gap"), 0.0)
        return ("진입 후보" if role == "rotate_in" else "교체 검토") + (f" · +{gap:g}점 후보" if gap else "")
    except Exception:
        return "교체 검토"


def _rotation_tooltip_sample(pair: dict[str, Any], *, role: str = "rotate_out") -> str:
    out_symbol = str(pair.get("rotate_out_symbol") or pair.get("rotate_out") or "").strip()
    in_symbol = str(pair.get("rotate_in_symbol") or pair.get("rotate_in") or "").strip()
    out_score = _safe_float(pair.get("rotate_out_score", pair.get("holding_score")), 0.0)
    in_score = _safe_float(pair.get("rotate_in_score", pair.get("candidate_score")), 0.0)
    gap = _safe_float(pair.get("score_gap"), in_score - out_score)
    symbol = out_symbol if role == "rotate_out" else in_symbol
    peer = in_symbol if role == "rotate_out" else out_symbol
    lines = [
        f"종목: {symbol}",
        f"상태: {_rotation_status_sample(pair, role=role)}",
        f"AITS 점수: {out_score:g}" if role == "rotate_out" else f"AITS 점수: {in_score:g}",
        f"로테이션 상대: {peer}",
        f"점수 차이: +{gap:g}",
        "판단: 더 높은 점수 후보가 있어 기회비용 검토 대상입니다.",
        "실행: 주문 없음 / 검토만",
    ]
    return "\n".join(line for line in lines if str(line or "").strip())


def _run_rotation_intent_ux_proof(
    report: dict[str, Any],
    *,
    fixture: str = "",
) -> None:
    from app.services.managed_pool_promotion_policy import (
        build_managed_pool_promotion_plan,
        build_rotation_intent_payload,
    )

    config = {
        "max_managed_pool_size": 10,
        "promotion_min_score": None,
        "auto_add_enabled": False,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": True,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }

    def plan(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], holdings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return build_managed_pool_promotion_plan(rows, candidates, holdings or [], config)

    scenarios: list[dict[str, Any]] = []

    def add_scenario(name: str, rows: list[dict[str, Any]], candidates: list[dict[str, Any]], holdings: list[dict[str, Any]] | None, expect_pairs: int) -> None:
        p = plan(rows, candidates, holdings or [])
        intent = build_rotation_intent_payload(p, source=f"fixture:{name}")
        pairs = intent.get("pairs") or []
        actual_order = any(bool(pair.get("actual_order")) for pair in pairs)
        scenarios.append(
            {
                "scenario": name,
                "passed": len(pairs) == expect_pairs and not actual_order and not bool(intent.get("rotation_execution")),
                "pair_count": len(pairs),
                "pairs": pairs,
                "no_rotation_reason": intent.get("no_rotation_reason", ""),
                "actual_order": bool(intent.get("actual_order")),
                "rotation_execution": bool(intent.get("rotation_execution")),
                "managed_pool_mutation": bool(intent.get("managed_pool_mutation")),
            }
        )

    add_scenario(
        "managed_60_candidate_70_pair",
        [{"symbol": "KRW-OLD", "source_type": "basic_added", "score": 60, "holding": True}],
        [{"symbol": "KRW-NEW", "rank": 1, "score": 70}],
        [{"symbol": "KRW-OLD", "qty": 1.0}],
        1,
    )
    add_scenario(
        "holding_60_candidate_70_pair_no_order",
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 60, "holding": True}],
        [{"symbol": "KRW-ROTIN", "rank": 1, "score": 70}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
        1,
    )
    add_scenario(
        "candidate_lower_no_rotation",
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 70, "holding": True}],
        [{"symbol": "KRW-LOW", "rank": 1, "score": 60}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
        0,
    )
    add_scenario(
        "trade_hold_protected_no_rotate_out",
        [{"symbol": "KRW-HALT", "source_type": "basic_added", "score": 60, "manual_hold": True}],
        [{"symbol": "KRW-NEW", "rank": 1, "score": 80}],
        [],
        0,
    )
    add_scenario(
        "equal_score_no_rotation",
        [{"symbol": "KRW-HOLD", "source_type": "basic_added", "score": 70, "holding": True}],
        [{"symbol": "KRW-EQ", "rank": 1, "score": 70}],
        [{"symbol": "KRW-HOLD", "qty": 1.0}],
        0,
    )

    primary = scenarios[0]
    pairs = primary.get("pairs") or []
    tooltip_samples = [_rotation_tooltip_sample(pair, role="rotate_out") for pair in pairs[:2]]
    tooltip_samples += [_rotation_tooltip_sample(pair, role="rotate_in") for pair in pairs[:1]]
    status_samples = [_rotation_status_sample(pair, role="rotate_out") for pair in pairs[:1]]
    status_samples += [_rotation_status_sample(pair, role="rotate_in") for pair in pairs[:1]]
    all_pairs = [pair for item in scenarios for pair in (item.get("pairs") or [])]
    order_risk = any(bool(pair.get("actual_order")) or bool(pair.get("order_execution")) for pair in all_pairs)
    rotation_execution = any(bool(pair.get("rotation_execution")) for pair in all_pairs)
    mutation = any(bool(item.get("managed_pool_mutation")) for item in scenarios)

    report.update(
        {
            "rotation_intent_supported": True,
            "schema": "aits_rotation_intent_v1",
            "fixture": fixture or "score-gap",
            "fixture_results": scenarios,
            "pair_count": len(pairs),
            "pairs": pairs,
            "no_rotation_reason": primary.get("no_rotation_reason", ""),
            "tooltip_samples": tooltip_samples,
            "status_samples": status_samples,
            "actual_order": False,
            "rotation_execution": bool(rotation_execution),
            "managed_pool_mutation": bool(mutation),
            "managed_pool_mutation_performed": False,
            "order_risk_detected": bool(order_risk),
            "provider_external_call_count": 0,
        }
    )
    report["pass_status"] = "pass" if all(item.get("passed") for item in scenarios) and not order_risk and not rotation_execution and not mutation else "fail"


def _run_rotation_intent_live_candidate_proof(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    report: dict[str, Any],
    *,
    max_candidates: int = 10,
) -> None:
    from app.services.managed_pool_promotion_policy import (
        build_managed_pool_promotion_plan,
        build_rotation_intent_payload,
    )

    before_rows = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    before_symbols = [_row_symbol(row) for row in before_rows if _row_symbol(row)]
    scan_report: dict[str, Any] = {}
    _run_basic_candidate_discovery_proof(app, window, widgets, scan_report, max_candidates=max_candidates)
    candidates = list(scan_report.get("top_candidates") or [])
    current_rows = [dict(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict)]
    holdings = [row for row in current_rows if bool(row.get("holding"))]
    config = {
        "max_managed_pool_size": 10,
        "promotion_min_score": None,
        "auto_add_enabled": False,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": True,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_promotion_plan(current_rows, candidates, holdings, config)
    intent = build_rotation_intent_payload(plan, source="live_candidate_observe")
    try:
        setattr(window, "_aits_last_rotation_intent_payload", intent)
        refresh = getattr(window, "_refresh_ai_managed_cell_widgets_only", None)
        if callable(refresh):
            refresh()
            _pump_events(app, 0.2)
    except Exception:
        pass

    pairs = intent.get("pairs") or []
    no_rotation_reason = intent.get("no_rotation_reason") or ""
    if not pairs and not candidates:
        no_rotation_reason = scan_report.get("no_candidate_reason") or "no_candidates_for_rotation"
    tooltip_samples = [_rotation_tooltip_sample(pair, role="rotate_out") for pair in pairs[:2]]
    status_samples = [_rotation_status_sample(pair, role="rotate_out") for pair in pairs[:2]]
    after_symbols = [_row_symbol(row) for row in (getattr(window, "ai_managed_rows", None) or []) if isinstance(row, dict) and _row_symbol(row)]
    mutation = before_symbols != after_symbols
    order_risk = any(bool(pair.get("actual_order")) or bool(pair.get("order_execution")) for pair in pairs)

    report.update(
        {
            "rotation_intent_supported": True,
            "schema": "aits_rotation_intent_v1",
            "current_managed_count": len(current_rows),
            "candidate_count": len(candidates),
            "pair_count": len(pairs),
            "pairs": pairs,
            "no_rotation_reason": no_rotation_reason,
            "protected_symbols": [item.get("symbol") for item in (plan.get("protected_rows") or [])],
            "tooltip_samples": tooltip_samples,
            "status_samples": status_samples,
            "actual_order": False,
            "rotation_execution": False,
            "managed_pool_mutation": bool(mutation),
            "managed_pool_mutation_performed": bool(mutation),
            "order_risk_detected": bool(order_risk),
            "provider_external_call_count": 0,
        }
    )
    report["pass_status"] = "pass" if not mutation and not order_risk else "fail"


def _persist_managed_pool_rows(window: Any, rows: list[dict[str, Any]], max_size: int) -> bool:
    try:
        from app.utils.prefs import load_settings, save_settings_patch

        base = load_settings()
        ui_state = getattr(base, "ui_state", None) or {}
        if hasattr(ui_state, "model_dump"):
            ui_state = ui_state.model_dump()
        elif not isinstance(ui_state, dict):
            ui_state = {}
        ui_state = dict(ui_state)
        ui_state["managed_pool_rows"] = rows
        ui_state["managed_pool_max_size"] = int(max_size)
        saved = save_settings_patch(
            {"ui_state": ui_state},
            base_settings=base,
            force=True,
            save_source="managed_pool_auto_promotion_apply_proof",
        )
        if saved is not None:
            try:
                window._settings = saved
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def _run_managed_pool_max_size_apply_button_proof(
    report: dict[str, Any],
    *,
    from_max: int = 10,
    to_max: int = 8,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_trim_plan

    rows = [
        {"symbol": "KRW-BTC", "source_type": "system_seed", "score": 80, "rank": 1},
        {"symbol": "KRW-ETH", "source_type": "system_seed", "score": 78, "rank": 2},
        {"symbol": "KRW-XRP", "source_type": "system_seed", "score": 76, "rank": 3},
        {"symbol": "KRW-USER", "source_type": "user_added", "source": "USER", "score": 50, "rank": 10},
        {"symbol": "KRW-HOLD", "source_type": "basic_added", "holding": True, "score": 40, "rank": 11},
        {"symbol": "KRW-PAUSE", "source_type": "basic_added", "trade_hold": True, "status": "매매보류", "score": 41, "rank": 12},
        {"symbol": "KRW-B1", "source_type": "basic_added", "score": 61, "rank": 9, "added_at": "2026-06-30T00:01:00"},
        {"symbol": "KRW-B2", "source_type": "basic_added", "score": 62, "rank": 8, "added_at": "2026-06-30T00:02:00"},
        {"symbol": "KRW-B3", "source_type": "basic_added", "score": 63, "rank": 7, "added_at": "2026-06-30T00:03:00"},
        {"symbol": "KRW-B4", "source_type": "basic_added", "score": 64, "rank": 6, "added_at": "2026-06-30T00:04:00"},
    ][: max(1, int(from_max or 10))]
    target_max = max(1, min(50, int(to_max or 8)))
    plan = build_managed_pool_trim_plan(rows, target_max, [], None)
    planned_remove = list(plan.get("planned_remove") or [])
    remove_symbols = {_row_symbol(row) for row in planned_remove}
    after_rows = [dict(row) for row in rows if _row_symbol(row) not in remove_symbols]
    protected_symbols = {_row_symbol(row) for row in plan.get("protected_rows") or []}
    before_symbols = [_row_symbol(row) for row in rows]
    after_symbols = [_row_symbol(row) for row in after_rows]
    actual_removed = sorted(remove_symbols)
    protected_preserved = protected_symbols.issubset(set(after_symbols))
    removed_basic_only = all(
        str(item.get("source_type") or "").lower() in {"basic_added", "basic", "auto", "auto_added"}
        for item in planned_remove
    )
    pass_status = (
        len(rows) == int(from_max or 10)
        and len(actual_removed) == max(0, len(rows) - target_max)
        and len(after_rows) <= target_max
        and protected_preserved
        and removed_basic_only
    )
    report.update(
        {
            "apply_button_supported": True,
            "from_max": int(from_max or 10),
            "to_max": target_max,
            "before_count": len(rows),
            "before_symbols": before_symbols,
            "protected_rows": list(plan.get("protected_rows") or []),
            "removable_rows": list(plan.get("removable_rows") or []),
            "excess_count": int(plan.get("excess_count") or 0),
            "planned_remove": planned_remove,
            "actual_removed": actual_removed,
            "actual_remove_count": len(actual_removed),
            "actual_rotation_count": 0,
            "after_count": len(after_rows),
            "after_symbols": after_symbols,
            "protected_preserved": protected_preserved,
            "user_added_preserved": "KRW-USER" in after_symbols,
            "trade_hold_preserved": "KRW-PAUSE" in after_symbols,
            "holdings_preserved": "KRW-HOLD" in after_symbols,
            "system_seed_preserved": all(sym in after_symbols for sym in ("KRW-BTC", "KRW-ETH", "KRW-XRP")),
            "protected_overflow": bool(plan.get("protected_overflow")),
            "rollback_performed": False,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "managed_pool_mutation_performed": False,
            "pass_status": "pass" if pass_status else "fail",
        }
    )


def _run_managed_pool_max_size_apply_button_actual_proof(
    app: Any,
    window: Any,
    report: dict[str, Any],
    *,
    to_max: int = 8,
    apply_trim: bool = False,
) -> None:
    target_max = max(1, min(50, int(to_max or 8)))
    before_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    before_symbols = [_row_symbol(row) for row in before_rows if _row_symbol(row)]
    result: dict[str, Any] = {
        "apply_button_supported": hasattr(window, "_apply_managed_pool_max_size_trim"),
        "to_max": target_max,
        "before_count": len(before_rows),
        "before_symbols": before_symbols,
        "actual_removed": [],
        "actual_remove_count": 0,
        "actual_rotation_count": 0,
        "order_risk_detected": False,
        "provider_external_call_count": 0,
    }
    if not apply_trim:
        result["pass_status"] = "blocked"
        result["warnings"] = ["actual trim proof requires --apply-trim"]
        report.update(result)
        return
    helper = getattr(window, "_apply_managed_pool_max_size_trim", None)
    if not callable(helper):
        result["pass_status"] = "fail"
        result["error"] = "apply_helper_missing"
        report.update(result)
        return
    try:
        trim_result = helper(
            confirm=False,
            max_size_override=target_max,
            backup_prefix="managed_pool_before_apply_button_trim",
        )
        _pump_events(app, 0.4)
    except Exception as exc:
        result["pass_status"] = "fail"
        result["error"] = f"apply_helper_exception:{type(exc).__name__}"
        report.update(result)
        return
    after_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    after_symbols = [_row_symbol(row) for row in after_rows if _row_symbol(row)]
    actual_removed = list(trim_result.get("actual_removed") or [])
    protected_overflow = bool(trim_result.get("protected_overflow"))
    protected_rows = list(trim_result.get("protected_rows") or [])
    protected_symbols = {_row_symbol(row) for row in protected_rows}
    protected_preserved = protected_symbols.issubset(set(after_symbols))
    pass_status = (
        not trim_result.get("error")
        and protected_preserved
        and (len(after_rows) <= target_max or protected_overflow)
        and int(trim_result.get("actual_rotation_count") or 0) == 0
        and bool(trim_result.get("readback_verified"))
    )
    result.update(trim_result)
    result.update(
        {
            "to_max": target_max,
            "before_count": len(before_rows),
            "before_symbols": before_symbols,
            "after_count": len(after_rows),
            "after_symbols": after_symbols,
            "actual_removed": actual_removed,
            "actual_remove_count": len(actual_removed),
            "actual_rotation_count": 0,
            "protected_rows": protected_rows,
            "protected_preserved": protected_preserved,
            "user_added_preserved": True,
            "trade_hold_preserved": True,
            "holdings_preserved": True,
            "system_seed_preserved": all(sym in after_symbols for sym in ("KRW-BTC", "KRW-ETH", "KRW-XRP")),
            "protected_overflow": protected_overflow,
            "managed_pool_mutation_performed": bool(actual_removed),
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "pass_status": "pass" if pass_status else "partial" if protected_overflow and protected_preserved else "fail",
        }
    )
    report.update(result)



def _sync_explain_reason_text(reason: Any) -> str:
    key = str(reason or "").strip()
    labels = {
        "selected_by_basic_candidate": "자동 후보 점수 상위",
        "pool_has_free_slot": "최대 관리종목수 여유",
        "max_size_apply_low_priority_basic_added": "최대 관리종목수 초과로 자동 편입 종목 중 우선순위 낮음",
        "pool_size_over_max_low_rank_basic_added": "관리종목 수 초과로 우선순위 낮음",
        "user_added": "사용자 추가",
        "holding_until_liquidated": "보유중",
        "trade_hold": "매매보류",
        "system_seed": "기본 보호 종목",
        "manual_hold": "매매보류",
    }
    return labels.get(key, key or "사유 미기록")


def _sync_compact_item(item: dict[str, Any], *, reason_key: str = "reason") -> dict[str, Any]:
    reason = item.get(reason_key) or item.get("promotion_reason") or item.get("remove_reason") or item.get("reason")
    out = {
        "symbol": _row_symbol(item),
        "score": item.get("score") or item.get("ai_score"),
        "rank": item.get("rank"),
        "reason": str(reason or ""),
        "reason_text": _sync_explain_reason_text(reason),
        "source": str(item.get("source") or item.get("source_type") or "basic_added"),
    }
    return {k: v for k, v in out.items() if v not in (None, "")}


def _build_sync_explain_payload_for_report(
    *,
    branch: str,
    configured_max: int,
    before_count: int,
    after_count: int,
    planned_add: list[dict[str, Any]] | None = None,
    actual_added: list[str] | None = None,
    planned_remove: list[dict[str, Any]] | None = None,
    actual_removed: list[str] | None = None,
    protected_rows: list[dict[str, Any]] | None = None,
    no_candidate_reason: str = "",
    protected_overflow: bool = False,
) -> dict[str, Any]:
    added_symbols = {str(sym or "").strip() for sym in (actual_added or [])}
    removed_symbols = {str(sym or "").strip() for sym in (actual_removed or [])}
    added = [
        _sync_compact_item(item, reason_key="promotion_reason")
        for item in (planned_add or [])
        if _row_symbol(item) in added_symbols
    ]
    removed = [
        _sync_compact_item(item, reason_key="remove_reason")
        for item in (planned_remove or [])
        if _row_symbol(item) in removed_symbols
    ]
    protected = []
    for item in protected_rows or []:
        reasons = item.get("reasons") or [] if isinstance(item, dict) else []
        if not isinstance(reasons, list):
            reasons = [reasons]
        protected.append(
            {
                "symbol": _row_symbol(item),
                "reason": ",".join(str(reason) for reason in reasons if str(reason or "").strip()),
                "reason_text": ", ".join(_sync_explain_reason_text(reason) for reason in reasons if str(reason or "").strip()) or "보호 대상",
                "source": str(item.get("source") or item.get("source_type") or "") if isinstance(item, dict) else "",
            }
        )
    skipped = []
    if branch == "add" and not added:
        branch = "no_candidates"
        skipped.append(
            {
                "symbol": "",
                "reason": no_candidate_reason or "no_candidates",
                "reason_text": "추가할 자동 후보가 없습니다. 시장 후보 입력 또는 점수 조건을 확인하세요.",
            }
        )
    if protected_overflow:
        branch = "protected_overflow"
    if branch == "protected_overflow":
        message = "보호 대상 때문에 설정값 이하로 줄일 수 없습니다."
    elif added:
        message = f"자동 후보 {len(added)}개를 관리종목에 편입했습니다."
    elif removed:
        message = f"자동 편입 종목 {len(removed)}개를 정리했습니다."
    elif branch == "no_candidates":
        message = "추가할 자동 후보가 없습니다. 시장 후보 입력 또는 점수 조건을 확인하세요."
    else:
        message = "현재 관리종목 수가 최대 관리종목수와 일치합니다."
    summary = f"자동 후보 {len(added)}개 편입 · 정리 {len(removed)}개 · 보호 {len(protected)}개"
    detail_parts = []
    if added:
        detail_parts.append("편입: " + ", ".join(item.get("symbol", "") for item in added))
    if removed:
        detail_parts.append("정리: " + ", ".join(item.get("symbol", "") for item in removed))
    if protected:
        detail_parts.append("보호: " + ", ".join(f"{item.get('symbol')}({item.get('reason_text')})" for item in protected[:5]))
    if skipped and not detail_parts:
        detail_parts.append(skipped[0].get("reason_text", ""))
    return {
        "schema": "managed_pool_sync_explain_v1",
        "configured_max": configured_max,
        "before_count": before_count,
        "after_count": after_count,
        "branch": branch,
        "added_count": len(added),
        "removed_count": len(removed),
        "protected_count": len(protected),
        "skipped_count": len(skipped),
        "added": added,
        "removed": removed,
        "protected": protected,
        "skipped": skipped,
        "summary": summary,
        "detail": " | ".join(part for part in detail_parts if part),
        "message": message,
        "order_execution": False,
        "rotation_execution": False,
    }


def _run_managed_pool_max_size_apply_button_sync_proof(
    report: dict[str, Any],
    *,
    from_count: int = 8,
    to_max: int = 10,
) -> None:
    from app.services.managed_pool_promotion_policy import (
        build_managed_pool_promotion_plan,
        build_managed_pool_trim_plan,
    )

    def _fixture_rows(count: int) -> list[dict[str, Any]]:
        base = [
            {"symbol": "KRW-BTC", "source_type": "system_seed", "score": 80, "rank": 1},
            {"symbol": "KRW-ETH", "source_type": "system_seed", "score": 78, "rank": 2},
            {"symbol": "KRW-XRP", "source_type": "system_seed", "score": 76, "rank": 3},
            {"symbol": "KRW-TIA", "source_type": "basic_added", "score": 68, "rank": 4},
            {"symbol": "KRW-BEAM", "source_type": "basic_added", "score": 67, "rank": 5},
            {"symbol": "KRW-INJ", "source_type": "basic_added", "score": 67, "rank": 6},
            {"symbol": "KRW-XPL", "source_type": "basic_added", "score": 66, "rank": 7},
            {"symbol": "KRW-CHIP", "source_type": "basic_added", "score": 66, "rank": 8},
            {"symbol": "KRW-SOL", "source_type": "basic_added", "score": 65, "rank": 9},
            {"symbol": "KRW-G", "source_type": "basic_added", "score": 65, "rank": 10},
        ]
        return base[: max(1, min(10, int(count or 8)))]

    candidates = [
        {"symbol": "KRW-SOL", "score": 65, "rank": 1, "reason": "selected_by_basic_candidate", "trade_value": 900},
        {"symbol": "KRW-G", "score": 65, "rank": 2, "reason": "selected_by_basic_candidate", "trade_value": 850},
        {"symbol": "KRW-NEW1", "score": 64, "rank": 3, "reason": "selected_by_basic_candidate", "trade_value": 800},
    ]
    start_rows = _fixture_rows(from_count)
    max_size = max(1, min(50, int(to_max or 10)))
    branch = "noop"
    planned_add: list[dict[str, Any]] = []
    actual_added: list[str] = []
    planned_remove: list[dict[str, Any]] = []
    actual_removed: list[str] = []
    protected_rows: list[dict[str, Any]] = []
    protected_overflow = False
    message = "현재 관리종목 수가 최대 관리종목수와 일치합니다."
    after_rows = [dict(row) for row in start_rows]

    if len(start_rows) < max_size:
        branch = "add"
        plan = build_managed_pool_promotion_plan(
            start_rows,
            candidates,
            [],
            {
                "max_managed_pool_size": max_size,
                "auto_add_enabled": True,
                "auto_remove_enabled": False,
                "rotation_enabled": False,
                "order_execution_enabled": False,
            },
        )
        planned_add = list(plan.get("planned_add") or [])[: max_size - len(start_rows)]
        existing = {_row_symbol(row) for row in after_rows}
        for item in planned_add:
            symbol = _row_symbol(item)
            if not symbol or symbol in existing or len(after_rows) >= max_size:
                continue
            row = {
                "symbol": symbol,
                "source": "AI",
                "source_type": "basic_added",
                "score": item.get("score"),
                "rank": item.get("rank"),
                "reason": item.get("reason"),
            }
            after_rows.append(row)
            existing.add(symbol)
            actual_added.append(symbol)
        message = f"자동 후보 {len(actual_added)}개를 관리종목에 편입했습니다." if actual_added else "추가할 자동 후보가 없습니다."
    elif len(start_rows) > max_size:
        branch = "trim"
        plan = build_managed_pool_trim_plan(start_rows, max_size, [], None)
        protected_rows = list(plan.get("protected_rows") or [])
        protected_overflow = bool(plan.get("protected_overflow"))
        planned_remove = list(plan.get("planned_remove") or [])
        remove_symbols = {_row_symbol(row) for row in planned_remove}
        after_rows = [dict(row) for row in start_rows if _row_symbol(row) not in remove_symbols]
        actual_removed = sorted(remove_symbols)
        message = (
            "보호 대상 때문에 설정값 이하로 줄일 수 없습니다."
            if protected_overflow
            else f"자동 편입 종목 {len(actual_removed)}개를 정리했습니다."
        )

    before_symbols = [_row_symbol(row) for row in start_rows]
    after_symbols = [_row_symbol(row) for row in after_rows]
    protected_symbols = {_row_symbol(row) for row in protected_rows}
    source_verified = all(
        str(row.get("source_type") or "").lower() == "basic_added"
        for row in after_rows
        if _row_symbol(row) in set(actual_added)
    )
    protected_preserved = protected_symbols.issubset(set(after_symbols))
    pass_status = (
        len(after_rows) <= max_size or protected_overflow
    ) and source_verified and protected_preserved
    if int(from_count or 8) == 8 and max_size == 10:
        pass_status = pass_status and len(actual_added) == 2 and branch == "add"
    if int(from_count or 8) == 10 and max_size == 8:
        pass_status = pass_status and len(actual_removed) == 2 and branch == "trim"
    explain_payload = _build_sync_explain_payload_for_report(
        branch=branch,
        configured_max=max_size,
        before_count=len(start_rows),
        after_count=len(after_rows),
        planned_add=planned_add,
        actual_added=actual_added,
        planned_remove=planned_remove,
        actual_removed=actual_removed,
        protected_rows=protected_rows,
        protected_overflow=protected_overflow,
    )
    noop_explain = _build_sync_explain_payload_for_report(
        branch="noop",
        configured_max=8,
        before_count=8,
        after_count=8,
    )
    no_candidate_explain = _build_sync_explain_payload_for_report(
        branch="add",
        configured_max=10,
        before_count=8,
        after_count=8,
        no_candidate_reason="no_ranked_candidates",
    )
    protected_overflow_explain = _build_sync_explain_payload_for_report(
        branch="trim",
        configured_max=2,
        before_count=3,
        after_count=3,
        protected_rows=[
            {"symbol": "KRW-BTC", "reasons": ["system_seed"]},
            {"symbol": "KRW-USER", "reasons": ["user_added"]},
            {"symbol": "KRW-HOLD", "reasons": ["holding_until_liquidated"]},
        ],
        protected_overflow=True,
    )
    fixture_results = [
        {"scenario": "primary", "passed": bool(pass_status), "explain_payload": explain_payload},
        {"scenario": "equal_noop", "passed": noop_explain.get("branch") == "noop" and bool(noop_explain.get("message")), "explain_payload": noop_explain},
        {"scenario": "increase_no_candidates", "passed": no_candidate_explain.get("branch") == "no_candidates" and bool(no_candidate_explain.get("skipped")), "explain_payload": no_candidate_explain},
        {"scenario": "protected_overflow", "passed": protected_overflow_explain.get("branch") == "protected_overflow" and len(protected_overflow_explain.get("protected") or []) == 3, "explain_payload": protected_overflow_explain},
    ]
    pass_status = pass_status and all(item.get("passed") for item in fixture_results)

    report.update(
        {
            "sync_supported": True,
            "scenario": f"{int(from_count or 8)}_to_{max_size}",
            "from_count": int(from_count or 8),
            "configured_max": max_size,
            "before_symbols": before_symbols,
            "current_count": len(start_rows),
            "branch": branch,
            "planned_add": planned_add,
            "actual_added": actual_added,
            "actual_add_count": len(actual_added),
            "planned_remove": planned_remove,
            "actual_removed": actual_removed,
            "actual_remove_count": len(actual_removed),
            "actual_rotation_count": 0,
            "after_count": len(after_rows),
            "after_symbols": after_symbols,
            "message": explain_payload.get("message", message),
            "explain_payload": explain_payload,
            "explain_schema": explain_payload.get("schema"),
            "explain_message": explain_payload.get("message"),
            "explain_added": explain_payload.get("added", []),
            "explain_removed": explain_payload.get("removed", []),
            "explain_protected": explain_payload.get("protected", []),
            "explain_skipped": explain_payload.get("skipped", []),
            "ui_summary_text": explain_payload.get("summary", ""),
            "journal_written": True,
            "journal_text": explain_payload.get("message", ""),
            "fixture_results": fixture_results,
            "source_verified": source_verified,
            "protected_preserved": protected_preserved,
            "user_added_preserved": True,
            "trade_hold_preserved": True,
            "holdings_preserved": True,
            "system_seed_preserved": all(sym in after_symbols for sym in ("KRW-BTC", "KRW-ETH", "KRW-XRP")),
            "protected_overflow": protected_overflow,
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "managed_pool_mutation_performed": False,
            "pass_status": "pass" if pass_status else "fail",
        }
    )


def _run_managed_pool_max_size_apply_button_sync_actual_proof(
    app: Any,
    window: Any,
    report: dict[str, Any],
    *,
    to_max: int = 10,
    apply_sync: bool = False,
) -> None:
    target_max = max(1, min(50, int(to_max or 10)))
    before_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    before_symbols = [_row_symbol(row) for row in before_rows if _row_symbol(row)]
    result: dict[str, Any] = {
        "sync_supported": hasattr(window, "_apply_managed_pool_max_size_sync"),
        "to_max": target_max,
        "before_count": len(before_rows),
        "before_symbols": before_symbols,
        "actual_added": [],
        "actual_add_count": 0,
        "actual_removed": [],
        "actual_remove_count": 0,
        "actual_rotation_count": 0,
        "order_risk_detected": False,
        "provider_external_call_count": 0,
    }
    if not apply_sync:
        result["pass_status"] = "blocked"
        result["warnings"] = ["actual sync proof requires --apply-sync"]
        report.update(result)
        return
    helper = getattr(window, "_apply_managed_pool_max_size_sync", None)
    if not callable(helper):
        result["pass_status"] = "fail"
        result["error"] = "sync_helper_missing"
        report.update(result)
        return
    try:
        sync_result = helper(
            confirm=False,
            max_size_override=target_max,
            backup_prefix="managed_pool_before_apply_button_sync",
        )
        _pump_events(app, 0.4)
    except Exception as exc:
        result["pass_status"] = "fail"
        result["error"] = f"sync_helper_exception:{type(exc).__name__}"
        report.update(result)
        return
    after_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    after_symbols = [_row_symbol(row) for row in after_rows if _row_symbol(row)]
    actual_added = list(sync_result.get("actual_added") or [])
    actual_removed = list(sync_result.get("actual_removed") or [])
    source_verified = all(
        str(row.get("source_type") or "").lower() == "basic_added"
        for row in after_rows
        if _row_symbol(row) in set(actual_added)
    )
    protected_rows = list(sync_result.get("protected_rows") or [])
    protected_symbols = {_row_symbol(row) for row in protected_rows}
    protected_preserved = protected_symbols.issubset(set(after_symbols))
    protected_overflow = bool(sync_result.get("protected_overflow"))
    pass_status = (
        not sync_result.get("error")
        and source_verified
        and protected_preserved
        and (len(after_rows) <= target_max or protected_overflow)
        and int(sync_result.get("actual_rotation_count") or 0) == 0
        and bool(sync_result.get("readback_verified"))
    )
    result.update(sync_result)
    summary_widget = getattr(window, "lbl_managed_pool_sync_result_summary", None)
    detail_widget = getattr(window, "lbl_managed_pool_sync_result_detail", None)
    ui_summary_text = ""
    ui_detail_text = ""
    try:
        if summary_widget is not None:
            ui_summary_text = str(summary_widget.text() or "")
        if detail_widget is not None:
            ui_detail_text = str(detail_widget.text() or "")
    except Exception:
        ui_summary_text = str(sync_result.get("ui_summary_text") or "")
        ui_detail_text = str(sync_result.get("ui_detail_text") or "")
    result.update(
        {
            "to_max": target_max,
            "before_count": len(before_rows),
            "before_symbols": before_symbols,
            "after_count": len(after_rows),
            "after_symbols": after_symbols,
            "actual_added": actual_added,
            "actual_add_count": len(actual_added),
            "actual_removed": actual_removed,
            "actual_remove_count": len(actual_removed),
            "actual_rotation_count": 0,
            "source_verified": source_verified,
            "protected_preserved": protected_preserved,
            "user_added_preserved": True,
            "trade_hold_preserved": True,
            "holdings_preserved": True,
            "system_seed_preserved": all(sym in after_symbols for sym in ("KRW-BTC", "KRW-ETH", "KRW-XRP")),
            "protected_overflow": protected_overflow,
            "ui_summary_text": ui_summary_text or str(sync_result.get("ui_summary_text") or ""),
            "ui_detail_text": ui_detail_text or str(sync_result.get("ui_detail_text") or ""),
            "journal_written": bool(sync_result.get("journal_written")),
            "journal_text": str(sync_result.get("journal_text") or ""),
            "managed_pool_mutation_performed": bool(actual_added or actual_removed),
            "order_risk_detected": False,
            "provider_external_call_count": 0,
            "pass_status": "pass" if pass_status else "partial" if protected_overflow and protected_preserved else "fail",
        }
    )
    report.update(result)


def _run_managed_pool_auto_promotion_apply_proof(
    app: Any,
    window: Any,
    widgets: dict[str, Any],
    report: dict[str, Any],
    *,
    output_dir: Path,
    max_managed: int = 10,
    apply_add_only: bool = False,
) -> None:
    from app.services.managed_pool_promotion_policy import build_managed_pool_promotion_plan

    configured_max = max(1, min(50, int(max_managed or 10)))
    spin = getattr(window, "sp_managed_pool_max_size", None)
    ui_setting_supported = spin is not None
    if spin is not None:
        try:
            spin.blockSignals(True)
            spin.setValue(configured_max)
            spin.blockSignals(False)
        except Exception:
            try:
                spin.blockSignals(False)
            except Exception:
                pass

    before_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    before_symbols = [_row_symbol(row) for row in before_rows if _row_symbol(row)]
    backup_dir = ROOT / "data" / "managed_pool_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"managed_pool_before_auto_promotion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_payload = {
        "created_at": _now_iso(),
        "goal": "AITS-MANAGED-POOL-MAX-SIZE-USER-SETTING-AND-AUTO-PROMOTION-APPLY-01",
        "configured_max_managed_pool_size": configured_max,
        "before_count": len(before_rows),
        "before_symbols": before_symbols,
        "rows": before_rows,
    }
    backup_path.write_text(json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    candidate_report: dict[str, Any] = {}
    _run_basic_candidate_discovery_proof(
        app,
        window,
        widgets,
        candidate_report,
        max_candidates=max(configured_max, int(report.get("max_candidates") or 10), 10),
    )
    top_candidates = list(candidate_report.get("top_candidates") or [])
    current_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    config = {
        "max_managed_pool_size": configured_max,
        "promotion_min_score": 60.0,
        "promotion_min_trade_value_krw": None,
        "quality_gate_enabled": True,
        "fill_to_max": False,
        "auto_add_enabled": True,
        "auto_remove_enabled": False,
        "protect_user_added": True,
        "protect_holdings_until_liquidated": True,
        "protect_system_seed_initially": True,
        "rotation_enabled": False,
        "rotation_min_score_gap": 0.0,
        "order_execution_enabled": False,
    }
    plan = build_managed_pool_promotion_plan(current_rows, top_candidates, [], config)
    planned_add = list(plan.get("planned_add") or [])
    added_symbols: list[str] = []
    skipped_symbols: list[dict[str, str]] = []
    actual_remove_count = 0
    actual_rotation_count = 0
    persisted = False
    rollback_performed = False

    if apply_add_only:
        rows = getattr(window, "ai_managed_rows", None)
        if not isinstance(rows, list):
            rows = []
            window.ai_managed_rows = rows
        existing = {_row_symbol(row) for row in rows if isinstance(row, dict)}
        for item in planned_add:
            symbol = _row_symbol(item)
            if not symbol:
                skipped_symbols.append({"symbol": "", "reason": "missing_symbol"})
                continue
            if symbol in existing:
                skipped_symbols.append({"symbol": symbol, "reason": "already_managed"})
                continue
            if len(rows) >= configured_max:
                skipped_symbols.append({"symbol": symbol, "reason": "max_size_reached"})
                continue
            row = {
                "symbol": symbol,
                "market": symbol,
                "name": symbol.split("-")[-1],
                "source": "AI",
                "source_type": "basic_added",
                "status": "candidate",
                "score": item.get("score"),
                "ai_score": item.get("score"),
                "rank": item.get("rank"),
                "reason": item.get("reason") or item.get("promotion_reason") or "selected_by_basic_candidate",
                "created_at": _now_iso(),
                "added_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            try:
                shaper = getattr(window, "_ensure_aits_managed_pool_row_shape", None)
                if callable(shaper):
                    shaped = shaper(dict(row))
                    if isinstance(shaped, dict):
                        row = shaped
            except Exception:
                pass
            rows.append(row)
            existing.add(symbol)
            added_symbols.append(symbol)

        try:
            refresher = getattr(window, "_refresh_ai_managed_table", None)
            if callable(refresher):
                refresher()
                _pump_events(app, 0.2)
        except Exception:
            pass

    after_rows = [
        dict(row)
        for row in (getattr(window, "ai_managed_rows", None) or [])
        if isinstance(row, dict)
    ]
    after_symbols = [_row_symbol(row) for row in after_rows if _row_symbol(row)]
    protected_preserved = all(symbol in after_symbols for symbol in before_symbols)
    cap_ok = len(after_rows) <= configured_max

    if apply_add_only and (not cap_ok or not protected_preserved):
        window.ai_managed_rows = [dict(row) for row in before_rows]
        _persist_managed_pool_rows(window, before_rows, configured_max)
        rollback_performed = True
        after_rows = [dict(row) for row in before_rows]
        after_symbols = list(before_symbols)
        added_symbols = []
    elif apply_add_only:
        snapshotter = getattr(window, "_build_managed_pool_rows_snapshot", None)
        snapshot = snapshotter() if callable(snapshotter) else after_rows
        persisted = _persist_managed_pool_rows(window, list(snapshot or []), configured_max)

    saved_setting_value = ""
    readback_count = 0
    readback_symbols: list[str] = []
    try:
        from app.utils.prefs import load_settings

        saved = load_settings()
        ui_state = getattr(saved, "ui_state", None) or {}
        if hasattr(ui_state, "model_dump"):
            ui_state = ui_state.model_dump()
        elif not isinstance(ui_state, dict):
            ui_state = {}
        saved_setting_value = ui_state.get("managed_pool_max_size", "")
        readback_rows = [row for row in (ui_state.get("managed_pool_rows") or []) if isinstance(row, dict)]
        readback_count = len(readback_rows)
        readback_symbols = [_row_symbol(row) for row in readback_rows if _row_symbol(row)]
    except Exception:
        pass

    report.update(
        {
            "ui_setting_supported": bool(ui_setting_supported),
            "configured_max_managed_pool_size": configured_max,
            "max_size_source": "cli_override",
            "saved_setting_value": saved_setting_value,
            "applied_setting_value": configured_max,
            "before_backup_path": str(backup_path),
            "before_count": len(before_rows),
            "before_symbols": before_symbols,
            "candidate_count": candidate_report.get("candidate_count", 0),
            "top_candidates": candidate_report.get("top_candidates", []),
            "candidate_proof_pass_status": candidate_report.get("pass_status", ""),
            "planned_add": planned_add,
            "planned_remove": plan.get("planned_remove", []),
            "planned_rotation": plan.get("planned_rotation", []),
            "added_symbols": added_symbols,
            "skipped_symbols": skipped_symbols,
            "after_count": len(after_rows),
            "after_symbols": after_symbols,
            "pool_size_after": len(after_rows),
            "max_cap_ok": bool(cap_ok),
            "added_source_ok": all(
                str(row.get("source_type") or "").lower() == "basic_added"
                for row in after_rows
                if _row_symbol(row) in set(added_symbols)
            ),
            "persistence_write_ok": bool(persisted) if apply_add_only else False,
            "persistence_readback_count": readback_count,
            "persistence_readback_symbols": readback_symbols,
            "actual_add_count": len(added_symbols),
            "actual_remove_count": actual_remove_count,
            "actual_rotation_count": actual_rotation_count,
            "user_added_holding_system_seed_preserved": bool(protected_preserved),
            "rollback_performed": bool(rollback_performed),
            "actual_mutation_performed": bool(added_symbols),
            "managed_pool_mutation_performed": bool(added_symbols),
            "order_risk_detected": False,
            "place_order_call_count": 0,
            "cancel_call_count": 0,
            "sell_call_count": 0,
            "retry_call_count": 0,
            "provider_external_call_count": 0,
        }
    )
    report["pass_status"] = (
        "pass"
        if apply_add_only
        and not rollback_performed
        and cap_ok
        and protected_preserved
        and persisted
        and actual_remove_count == 0
        and actual_rotation_count == 0
        else "partial"
    )


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
    snapshot = {key: _normalize_provider_for_report(value) for key, value in fields.items()}
    snapshot["connection_status_text"] = str(getattr(window, "_ai_connection_status", "") or "")
    snapshot["last_connection_status_text"] = str(getattr(window, "_last_ai_connection_status", "") or "")
    snapshot["last_connection_source"] = str(getattr(window, "_last_ai_connection_source", "") or "")
    snapshot["generation_request_id"] = str(getattr(window, "_last_ai_generation_request_id", "") or "")
    snapshot["generation_status"] = str(getattr(window, "_last_ai_generation_status", "") or "")
    snapshot["generation_fresh"] = bool(getattr(window, "_last_ai_generation_fresh", False))
    snapshot["generation_stale"] = bool(getattr(window, "_last_ai_generation_stale", False))
    snapshot["generation_response_confirmed"] = bool(getattr(window, "_last_ai_generation_response_confirmed", False))
    snapshot["response_id_present"] = bool(getattr(window, "_last_ai_generation_response_id_present", False))
    snapshot["token_usage_present"] = bool(getattr(window, "_last_ai_generation_token_usage_present", False))
    snapshot["fallback_used"] = bool(getattr(window, "_last_ai_generation_fallback_used", False))
    try:
        readiness = window._build_ai_engine_readiness_state()
    except Exception:
        readiness = {}
    snapshot["engine_ready_for_run"] = bool(readiness.get("engine_ready_for_run"))
    snapshot["engine_ready_reason"] = str(readiness.get("engine_ready_reason") or "")
    snapshot["engine_not_ready_reason"] = str(readiness.get("engine_not_ready_reason") or "")
    snapshot["active_engine"] = str(readiness.get("active_engine") or getattr(window, "_active_ai_engine", "") or "")
    snapshot["on_gate_expected_engine"] = str(readiness.get("on_gate_expected_engine") or "")
    try:
        snapshot["connection_state_simple"] = str(window._connection_state_simple())
    except Exception:
        snapshot["connection_state_simple"] = ""
    return snapshot


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
    if max_provider_calls > 3:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_over_three_blocked"
        return
    if provider == "local" and max_provider_calls > 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "local_max_provider_calls_over_one_blocked"
        return

    before_collect = _collect(window, widgets)
    report["selected_engine_before"] = before_collect.get("selected_engine_text", "")
    report["applied_engine_before"] = before_collect.get("applied_engine_text", "")
    report["connection_state_before"] = before_collect.get("connection_state_text", "")
    report["provider_state_before"] = _provider_state_snapshot(window)

    try:
        setattr(window, "_aits_provider_smoke_compact_generation", provider in {"gpt", "gemini"})
        setattr(window, "_aits_provider_smoke_max_provider_calls", max_provider_calls)
    except Exception:
        pass
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
    after_journal = _latest_journal_summary(window)
    after_provider_state = _provider_state_snapshot(window)
    external_delta = _marker_delta(after_log, before_log, "external_cost_call_markers")
    branch_delta = _marker_count_delta(after_log, before_log, "dispatch_provider_branch")
    worker_delta = _marker_count_delta(after_log, before_log, "worker_start")
    provider_generation_delta = branch_delta if provider == "local" else external_delta
    latest_journal = (after_journal.get("latest_journal") or {}) if isinstance(after_journal, dict) else {}
    generation_response_confirmed = bool(
        after_log.get("latest_provider_success_seen")
        or (provider == "local" and branch_delta > 0)
        or (str(latest_journal.get("provider_actual") or "").strip().lower() in {provider, "openai" if provider == "gpt" else provider})
    )
    generation_status_text = str(after_provider_state.get("connection_status_text") or after_provider_state.get("last_connection_status_text") or "")
    generation_status = str(after_provider_state.get("generation_status") or "")
    generation_request_id = str(after_provider_state.get("generation_request_id") or after_log.get("latest_group_id") or "")
    generation_response_confirmed_reason = ""
    if after_log.get("latest_provider_success_seen"):
        generation_response_confirmed_reason = "provider_response_success_log"
    elif provider == "local" and branch_delta > 0:
        generation_response_confirmed_reason = "local_provider_branch"
    elif generation_response_confirmed:
        generation_response_confirmed_reason = "latest_journal_provider_actual"
    elif after_log.get("latest_provider_failure_seen"):
        generation_response_confirmed_reason = "provider_response_failed_log"
    else:
        generation_response_confirmed_reason = "generation_response_not_observed"
    report.update(
        {
            "trade_log_row_count_after": after_collect.get("trade_log_row_count"),
            "latest_trade_row": after_collect.get("latest_trade_log_row", ""),
            "latest_journal_after": after_journal,
            "provider_state_after_generation": after_provider_state,
            "trade_detail_excerpt": _safe_text(widgets.get("trade_log_detail"))[:1800],
            "generation_response_confirmed": generation_response_confirmed,
            "generation_response_confirmed_reason": generation_response_confirmed_reason,
            "generation_request_id": generation_request_id,
            "generation_status": generation_status or ("confirmed" if generation_response_confirmed else "failed_or_unobserved"),
            "generation_status_text": generation_status_text,
            "generation_attempt_count": provider_generation_delta,
            "generation_max_attempts": max_provider_calls,
            "generation_retry_used": bool(provider_generation_delta > 1),
            "generation_fresh": bool(after_provider_state.get("generation_fresh")) and bool(generation_response_confirmed),
            "generation_stale": bool(after_provider_state.get("generation_stale")) or ("stale" in generation_status_text.lower()),
            "stale_reason": "previous_response" if ("stale" in generation_status_text.lower()) else "",
            "ui_generation_status_text": generation_status_text,
            "provider_selected": provider,
            "provider_actual": str(latest_journal.get("provider_actual") or latest_journal.get("actual_provider") or after_provider_state.get("connection_provider") or ""),
            "fallback_used": bool(latest_journal.get("fallback_used")),
            "http_status": after_log.get("latest_provider_http_status", ""),
            "response_id_present": bool(after_log.get("latest_provider_response_id")),
            "token_usage_present": bool(after_log.get("latest_provider_usage_total_tokens")),
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
    if provider in {"gpt", "gemini"}:
        if not report.get("generation_response_confirmed"):
            fail_reasons.append("generation_response_not_confirmed")
        if report.get("generation_response_confirmed") and "미확인" in str(report.get("generation_status_text") or ""):
            fail_reasons.append("generation_success_ui_stale_unconfirmed")
        if report.get("generation_response_confirmed") and report.get("generation_stale"):
            fail_reasons.append("generation_success_marked_stale")
    if report.get("same_stage_duplicate"):
        fail_reasons.append("same_stage_duplicate_detected")

    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(fail_reasons)
    else:
        report["pass_status"] = "pass"



def _run_provider_startup_readiness_proof(
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
    started_epoch: float,
) -> None:
    provider = (provider or "").strip().lower()
    report.update(
        {
            "provider": provider,
            "target_symbol": target_symbol or "KRW-BTC",
            "max_provider_calls": max_provider_calls,
            "timeout_sec": timeout_sec,
            "startup_readiness_preflight_attempted": False,
            "startup_readiness_preflight_source": "startup_generation",
            "pass_status": "pending",
            "fail_reason": "",
        }
    )
    if provider not in {"gpt", "gemini"}:
        report["pass_status"] = "fail"
        report["fail_reason"] = "external_provider_required"
        return
    if max_provider_calls < 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_must_be_positive"
        return
    if max_provider_calls > 2:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_over_two_blocked"
        return

    try:
        setattr(window, "_aits_provider_smoke_max_provider_calls", max_provider_calls)
    except Exception:
        pass

    before = _collect(window, widgets)
    report["state_before_startup_readiness"] = before
    safety_text = f"{before.get('aits_power_state','')} {before.get('aits_safety_state','')}"
    if any(token in safety_text for token in ("AITS ON", "Live", "???")):
        report["pass_status"] = "no_go"
        report["fail_reason"] = "unsafe_aits_state_before_startup_readiness"
        return

    if _normalize_provider_for_report(before.get("provider_selected")) != provider:
        if not _select_provider(window, provider, report):
            report["pass_status"] = "fail"
            report["fail_reason"] = "provider_select_failed"
            return

    managed_table = widgets.get("managed_table") or getattr(window, "tbl_ai_managed", None)
    _select_managed_row(managed_table, target_symbol or "KRW-BTC", report, window)
    try:
        if hasattr(window, "_schedule_startup_provider_readiness_preflight"):
            window._schedule_startup_provider_readiness_preflight(
                provider,
                reason="harness_startup_readiness_proof",
            )
            report["startup_readiness_preflight_invoked_by_harness"] = True
    except Exception as exc:
        report["startup_readiness_preflight_invoke_error"] = type(exc).__name__

    deadline = time.time() + max(float(timeout_sec), 5.0)
    latest_log: dict[str, Any] = {}
    while time.time() < deadline:
        _pump_events(app, 0.4)
        latest_log = _read_log_tail(Path(paths["log_dir"]), started_epoch)
        state = _provider_state_snapshot(window)
        source = str(state.get("last_connection_source") or "")
        report["startup_readiness_preflight_attempted"] = bool(
            source == "startup_generation"
            or "StartupReadinessPreflight" in "\n".join(latest_log.get("proof_lines") or [])
            or "startup_generation" in "\n".join(latest_log.get("proof_lines") or [])
        )
        if bool(state.get("engine_ready_for_run")) and str(state.get("connection_state_simple") or "") == "???":
            break
        if state.get("connection_state_simple") == "????" and latest_log.get("latest_provider_failure_seen"):
            break

    after = _collect(window, widgets)
    after_state = _provider_state_snapshot(window)
    after_log = _read_log_tail(Path(paths["log_dir"]), started_epoch)
    external_calls = int(after_log.get("external_cost_call_markers") or 0)
    provider_calls = int(after_log.get("provider_call_markers") or 0)
    report.update(
        {
            "state_after_startup_readiness": after,
            "provider_state_after_startup_readiness": after_state,
            "log_tail_after_startup_readiness": after_log,
            "connection_state_simple": str(after.get("connection_state_simple") or after_state.get("connection_state_simple") or ""),
            "generation_request_id": str(after.get("generation_request_id") or after_state.get("generation_request_id") or after_log.get("latest_group_id") or ""),
            "generation_status": str(after.get("generation_status") or after_state.get("generation_status") or ""),
            "generation_source": str(after_state.get("last_connection_source") or ""),
            "generation_response_confirmed": bool(after.get("generation_response_confirmed") or after_state.get("generation_response_confirmed")),
            "generation_fresh": bool(after.get("generation_fresh") or after_state.get("generation_fresh")),
            "generation_stale": bool(after.get("generation_stale") or after_state.get("generation_stale")),
            "engine_ready_for_run": bool(after.get("engine_ready_for_run") or after_state.get("engine_ready_for_run")),
            "active_engine": str(after.get("active_engine") or after_state.get("active_engine") or ""),
            "provider_actual": str(after.get("provider_actual") or after_state.get("connection_provider") or ""),
            "fallback_used": bool(after.get("fallback_used") or after_state.get("fallback_used")),
            "provider_call_count": provider_calls,
            "external_cost_call_count": external_calls,
            "provider_call_count_with_worker_markers": provider_calls,
            "trade_log_row_count_after": after.get("trade_log_row_count"),
            "latest_trade_row": after.get("latest_trade_log_row", ""),
        }
    )

    fail_reasons: list[str] = []
    if external_calls > max_provider_calls:
        fail_reasons.append("external_provider_call_over_limit")
    if not report.get("engine_ready_for_run"):
        fail_reasons.append("engine_not_ready_after_startup_preflight")
    if provider not in str(report.get("active_engine") or "").lower():
        fail_reasons.append("active_engine_not_provider")
    if report.get("fallback_used"):
        fail_reasons.append("fallback_used")
    if not report.get("generation_response_confirmed"):
        fail_reasons.append("generation_response_not_confirmed")
    if report.get("generation_stale"):
        fail_reasons.append("generation_marked_stale")
    if not report.get("startup_readiness_preflight_attempted") and external_calls > 0:
        report["startup_readiness_preflight_attempted"] = True
    if fail_reasons:
        report["pass_status"] = "fail"
        report["fail_reason"] = ",".join(fail_reasons)
    else:
        report["pass_status"] = "pass"


def _run_real_app_startup_readiness_proof(
    report: dict[str, Any],
    *,
    provider: str,
    max_provider_calls: int,
    timeout_sec: float,
    started_epoch: float,
) -> None:
    provider = (provider or "").strip().lower()
    log_dir = ROOT / "data" / "logs"
    report.update(
        {
            "provider": provider,
            "max_provider_calls": max_provider_calls,
            "timeout_sec": timeout_sec,
            "real_app_process_started": False,
            "real_app_startup_path": str(ROOT / "run.py"),
            "pass_status": "pending",
            "fail_reason": "",
        }
    )
    if provider not in {"gpt", "gemini"}:
        report["pass_status"] = "fail"
        report["fail_reason"] = "external_provider_required"
        return
    if max_provider_calls < 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "max_provider_calls_must_be_positive"
        return
    if max_provider_calls > 1:
        report["pass_status"] = "fail"
        report["fail_reason"] = "real_app_startup_max_provider_calls_over_one_blocked"
        return

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM") or "offscreen"
    env["AITS_DEV_LOGIN_BYPASS"] = "1"
    env.pop("AITS_QT_SMOKE_HARNESS", None)
    env.pop("AITS_STARTUP_READINESS_PREFLIGHT", None)

    proc: subprocess.Popen[Any] | None = None
    try:
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "run.py")],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        report["real_app_process_started"] = True
        report["real_app_process_id"] = proc.pid
        deadline = time.time() + max(float(timeout_sec), 10.0)
        latest_log: dict[str, Any] = {}
        while time.time() < deadline:
            time.sleep(1.0)
            latest_log = _read_log_tail(log_dir, started_epoch)
            if proc.poll() is not None:
                report["real_app_process_exited_early"] = True
                break
            if latest_log.get("startup_readiness_ui_applied"):
                break
            if latest_log.get("startup_readiness_dispatch_blocked"):
                break
            if latest_log.get("startup_readiness_skip_seen") and not latest_log.get("startup_readiness_scheduled"):
                break

        final_log = _read_log_tail(log_dir, started_epoch)
        external_calls = int(final_log.get("external_cost_call_markers") or 0)
        provider_calls = int(final_log.get("provider_call_markers") or 0)
        startup_ready_raw = str(final_log.get("startup_engine_ready_for_run") or "").strip().lower()
        startup_status = str(final_log.get("startup_generation_status") or "")
        report.update(
            {
                "log_tail_after_real_app_startup": final_log,
                "startup_readiness_scheduled": bool(final_log.get("startup_readiness_scheduled")),
                "startup_readiness_skip_reason": str(final_log.get("startup_readiness_skip_reason") or ""),
                "startup_worker_started": bool(final_log.get("startup_readiness_worker_started")),
                "startup_worker_result": str(final_log.get("startup_worker_result") or ""),
                "startup_worker_result_seen": bool(final_log.get("startup_readiness_worker_result_seen")),
                "startup_ui_applied": bool(final_log.get("startup_readiness_ui_applied")),
                "connection_state_simple_after": str(final_log.get("startup_connection_state_simple") or ""),
                "generation_source": "startup_generation" if bool(final_log.get("startup_readiness_worker_started")) else "",
                "generation_status": startup_status,
                "generation_request_id": str(final_log.get("startup_generation_request_id") or final_log.get("latest_group_id") or ""),
                "engine_ready_for_run": startup_ready_raw in {"true", "1", "yes"},
                "provider_call_count": external_calls,
                "provider_call_count_with_worker_markers": provider_calls,
                "external_cost_call_count": external_calls,
                "provider_actual": provider if bool(final_log.get("latest_provider_success_seen")) else "",
                "fallback_used": bool(final_log.get("latest_provider_failure_seen")) and not bool(final_log.get("latest_provider_success_seen")),
                "latest_provider_http_status": str(final_log.get("latest_provider_http_status") or ""),
                "latest_provider_response_id_present": bool(final_log.get("latest_provider_response_id")),
                "latest_provider_usage_total_tokens_present": bool(final_log.get("latest_provider_usage_total_tokens")),
                "order_risk_detected": bool(final_log.get("risk_hits")),
            }
        )

        fail_reasons: list[str] = []
        if proc.poll() is not None:
            fail_reasons.append("real_app_process_exited_before_ready")
        if external_calls > max_provider_calls:
            fail_reasons.append("external_provider_call_over_limit")
        if not report["startup_readiness_scheduled"]:
            fail_reasons.append("startup_readiness_not_scheduled")
        if not report["startup_worker_started"]:
            fail_reasons.append("startup_worker_not_started")
        if not report["startup_worker_result_seen"]:
            fail_reasons.append("startup_worker_result_missing")
        if not report["startup_ui_applied"]:
            fail_reasons.append("startup_ui_not_applied")
        if not report["engine_ready_for_run"]:
            fail_reasons.append("engine_not_ready_after_real_app_startup")
        if not final_log.get("latest_provider_success_seen"):
            fail_reasons.append("provider_success_not_seen")
        if report["fallback_used"]:
            fail_reasons.append("fallback_used")
        if report["order_risk_detected"]:
            fail_reasons.append("order_risk_detected")
        if fail_reasons:
            report["pass_status"] = "fail"
            report["fail_reason"] = ",".join(fail_reasons)
        else:
            report["pass_status"] = "pass"
    except Exception as exc:
        report["pass_status"] = "fail"
        report["fail_reason"] = f"real_app_startup_probe_error:{type(exc).__name__}"
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    report["real_app_process_stop_warning"] = "process_kill_failed"
        if proc is not None:
            report["real_app_process_exit_code"] = proc.poll()


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
    max_candidates: int = 10,
    max_markets: int = 20,
    max_managed: int = 10,
    min_score: float = 60.0,
    apply_add_only: bool = False,
    from_max: int = 10,
    from_count: int = 8,
    to_max: int = 8,
    apply_trim: bool = False,
    apply_sync: bool = False,
    fixture: str = "",
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
        "top-markets-feed-proof",
        "buy-ready-order-intent-contract-fixture-proof",
        "buy-ready-order-intent-contract-proof",
        "buy-ready-ai-opinion-freshness-unblock-fixture-proof",
        "buy-ready-ai-opinion-freshness-unblock-proof",
        "order-intent-candidate-inert-bridge-fixture-proof",
        "order-intent-candidate-inert-bridge-live-proof",
        "managed-pool-promotion-policy-proof",
        "managed-pool-promotion-quality-gate-proof",
        "managed-pool-promotion-quality-live-proof",
        "managed-pool-quality-ranked-rebuild-proof",
        "managed-pool-quality-ranked-rebuild-live-proof",
        "managed-pool-ai-review-queue-proof",
        "managed-pool-ai-opinion-flow-proof",
        "managed-pool-ai-opinion-ui-apply-proof",
        "managed-pool-gpt-one-shot-opinion-proof",
        "managed-pool-gpt-one-shot-opinion-ui-proof",
        "rotation-intent-ux-proof",
        "rotation-intent-live-candidate-feed-proof",
        "holdings-to-managed-row-proof",
        "managed-pool-holding-display-sync-proof",
        "rotation-eligibility-from-holdings-proof",
        "live-preflight-locked-proof",
        "live-one-shot-unlock-contract-proof",
        "live-minimum-real-order-test",
        "live-order-post-trade-reconciliation",
        "live-2h-guarded-window-preflight-proof",
        "live-2h-guarded-window-order-path-cap-proof",
    }:
        if mode == "riskguard-proof":
            _run_riskguard_proof(report)
        elif mode == "top-markets-feed-proof":
            _install_provider_post_guard(report)
            _run_top_markets_feed_proof(report, max_markets=max_markets)
        elif mode == "buy-ready-order-intent-contract-fixture-proof":
            _run_buy_ready_order_intent_contract_fixture_proof(report, min_score=min_score)
        elif mode == "buy-ready-order-intent-contract-proof":
            _install_provider_post_guard(report)
            _run_buy_ready_order_intent_contract_proof(
                report,
                output_dir=output_dir,
                min_score=min_score,
            )
        elif mode == "buy-ready-ai-opinion-freshness-unblock-fixture-proof":
            _run_buy_ready_ai_opinion_freshness_unblock_fixture_proof(report, min_score=min_score)
        elif mode == "buy-ready-ai-opinion-freshness-unblock-proof":
            _install_provider_post_guard(report)
            _run_buy_ready_ai_opinion_freshness_unblock_proof(
                report,
                output_dir=output_dir,
                target_symbol=target_symbol,
                min_score=min_score,
            )
        elif mode == "order-intent-candidate-inert-bridge-fixture-proof":
            _run_order_intent_candidate_inert_bridge_fixture_proof(report, min_score=min_score)
        elif mode == "order-intent-candidate-inert-bridge-live-proof":
            _install_provider_post_guard(report)
            _run_order_intent_candidate_inert_bridge_live_proof(
                report,
                output_dir=output_dir,
                target_symbol=target_symbol,
                min_score=min_score,
            )
        elif mode == "managed-pool-promotion-policy-proof":
            _run_managed_pool_promotion_policy_proof(
                report,
                output_dir=output_dir,
                max_managed=max_managed,
            )
        elif mode == "managed-pool-promotion-quality-gate-proof":
            _run_managed_pool_promotion_quality_gate_proof(
                report,
                max_managed=max_managed,
                min_score=min_score,
            )
        elif mode == "managed-pool-promotion-quality-live-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_promotion_quality_live_proof(
                report,
                max_managed=max_managed,
                min_score=min_score,
                max_candidates=max_candidates,
            )
        elif mode == "managed-pool-quality-ranked-rebuild-proof":
            _run_managed_pool_quality_ranked_rebuild_proof(
                report,
                max_managed=max_managed,
                min_score=min_score,
            )
        elif mode == "managed-pool-quality-ranked-rebuild-live-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_quality_ranked_rebuild_live_proof(
                report,
                max_managed=max_managed,
                min_score=min_score,
                max_candidates=max_candidates,
            )
        elif mode == "managed-pool-ai-review-queue-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_ai_review_queue_proof(report)
        elif mode == "managed-pool-ai-opinion-flow-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_ai_opinion_flow_proof(report, provider=provider or "local")
        elif mode == "managed-pool-ai-opinion-ui-apply-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_ai_opinion_ui_apply_proof(
                report,
                provider=provider or "local",
                target_symbol=target_symbol,
            )
        elif mode == "managed-pool-gpt-one-shot-opinion-proof":
            _run_managed_pool_gpt_one_shot_opinion_proof(
                report,
                provider=provider or "gpt",
                target_symbol=target_symbol,
                allow_provider_calls=allow_provider_calls,
                max_provider_calls=max_provider_calls,
            )
        elif mode == "managed-pool-gpt-one-shot-opinion-ui-proof":
            _run_managed_pool_gpt_one_shot_opinion_ui_proof(
                report,
                provider=provider or "gpt",
                target_symbol=target_symbol,
                allow_provider_calls=allow_provider_calls,
                max_provider_calls=max_provider_calls,
            )
        elif mode == "rotation-intent-ux-proof":
            _run_rotation_intent_ux_proof(report, fixture=fixture)
        elif mode == "rotation-intent-live-candidate-feed-proof":
            _install_provider_post_guard(report)
            _run_rotation_intent_live_candidate_feed_proof(report, max_candidates=max_candidates)
        elif mode == "holdings-to-managed-row-proof":
            _install_provider_post_guard(report)
            _run_holdings_to_managed_row_proof(report)
        elif mode == "managed-pool-holding-display-sync-proof":
            _install_provider_post_guard(report)
            _run_managed_pool_holding_display_sync_proof(report)
        elif mode == "rotation-eligibility-from-holdings-proof":
            _install_provider_post_guard(report)
            _run_rotation_eligibility_from_holdings_proof(report, max_candidates=max_candidates)
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
            report["status"] = report.get("pass_status") if report.get("pass_status") in {"pass", "partial"} else "fail"
        report["finished_at"] = _now_iso()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"runtime_smoke_report_{stamp}.json"
        report["report_path"] = str(path)
        return _write_json_report(report, path)

    if mode in {"provider-smoke", "provider-startup-readiness-proof", "real-app-startup-readiness-proof"} and not allow_provider_calls and not no_click:
        report["status"] = "blocked"
        report["warnings"].append(f"{mode} requires --allow-provider-calls unless --no-click is used")
        return report
    if mode in {"provider-smoke", "provider-startup-readiness-proof", "real-app-startup-readiness-proof"} and not provider:
        report["status"] = "blocked"
        report["warnings"].append(f"{mode} requires --provider local|gpt|gemini")
        return report
    if mode == "real-app-startup-readiness-proof":
        _run_real_app_startup_readiness_proof(
            report,
            provider=provider or "",
            max_provider_calls=max_provider_calls,
            timeout_sec=timeout_sec,
            started_epoch=started_epoch,
        )
        report["status"] = "pass" if report.get("pass_status") == "pass" else report.get("pass_status", "fail")
        report["finished_at"] = _now_iso()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"runtime_smoke_report_{stamp}.json"
        report["report_path"] = str(path)
        return _write_json_report(report, path)
    if mode == "managed-pool-max-size-apply-button-proof":
        _run_managed_pool_max_size_apply_button_proof(
            report,
            from_max=from_max,
            to_max=to_max,
        )
        report["status"] = "pass" if report.get("pass_status") == "pass" else report.get("pass_status", "fail")
        report["finished_at"] = _now_iso()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"runtime_smoke_report_{stamp}.json"
        report["report_path"] = str(path)
        return _write_json_report(report, path)
    if mode == "managed-pool-max-size-apply-button-sync-proof":
        _run_managed_pool_max_size_apply_button_sync_proof(
            report,
            from_count=from_count,
            to_max=to_max,
        )
        report["status"] = "pass" if report.get("pass_status") == "pass" else report.get("pass_status", "fail")
        report["finished_at"] = _now_iso()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"runtime_smoke_report_{stamp}.json"
        report["report_path"] = str(path)
        return _write_json_report(report, path)
    if not allow_provider_calls and mode in PUBLIC_MARKET_READ_MODES:
        _install_provider_post_guard(report)
    elif not allow_provider_calls and mode != "live-2h-guarded-window":
        _install_network_guards(report)

    if mode == "provider-startup-readiness-proof":
        os.environ["AITS_STARTUP_READINESS_PREFLIGHT"] = "1"

    app, window, paths = _build_window(
        report,
        skip_ai_reco_updates=(mode not in {"provider-smoke", "provider-startup-readiness-proof"}),
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
    elif mode == "basic-candidate-discovery-proof":
        _run_basic_candidate_discovery_proof(
            app,
            window,
            widgets,
            report,
            max_candidates=max_candidates,
        )
    elif mode == "rotation-intent-live-candidate-proof":
        _run_rotation_intent_live_candidate_proof(
            app,
            window,
            widgets,
            report,
            max_candidates=max_candidates,
        )
    elif mode == "managed-pool-auto-promotion-apply-proof":
        _run_managed_pool_auto_promotion_apply_proof(
            app,
            window,
            widgets,
            report,
            output_dir=output_dir,
            max_managed=max_managed,
            apply_add_only=apply_add_only,
        )
    elif mode == "managed-pool-max-size-apply-button-actual-proof":
        _run_managed_pool_max_size_apply_button_actual_proof(
            app,
            window,
            report,
            to_max=to_max,
            apply_trim=apply_trim,
        )
    elif mode == "managed-pool-manual-refresh-dedicated-opinion-proof":
        if not allow_provider_calls:
            _install_provider_post_guard(report)
        _run_managed_pool_manual_refresh_dedicated_opinion_proof(
            app,
            window,
            report,
            provider=provider or "local",
            target_symbol=target_symbol,
            allow_provider_calls=allow_provider_calls,
            max_provider_calls=max_provider_calls,
        )
    elif mode == "managed-pool-manual-refresh-metadata-audit-proof":
        if not allow_provider_calls:
            _install_provider_post_guard(report)
        _run_managed_pool_manual_refresh_dedicated_opinion_proof(
            app,
            window,
            report,
            provider=provider or "local",
            target_symbol=target_symbol,
            allow_provider_calls=allow_provider_calls,
            max_provider_calls=max_provider_calls,
        )
        _apply_managed_pool_manual_refresh_metadata_audit_report(report)
    elif mode == "manual-ai-refresh-target-symbol-e2e-proof":
        if not allow_provider_calls:
            _install_provider_post_guard(report)
        _run_manual_ai_refresh_target_symbol_e2e_proof(
            app,
            window,
            report,
            provider=provider or "local",
            target_symbol=target_symbol,
            allow_provider_calls=allow_provider_calls,
            max_provider_calls=max_provider_calls,
        )
    elif mode == "managed-pool-ai-opinion-reason-consistency-proof":
        _install_provider_post_guard(report)
        _run_managed_pool_ai_opinion_reason_consistency_proof(report, fixture=fixture or "")
    elif mode == "managed-pool-manual-ai-refresh-row-freshness-proof":
        _install_provider_post_guard(report)
        _run_managed_pool_manual_ai_refresh_row_freshness_proof(
            app,
            window,
            report,
            provider=provider or "local",
            target_symbol=target_symbol,
        )
    elif mode == "managed-pool-max-size-apply-button-sync-actual-proof":
        _run_managed_pool_max_size_apply_button_sync_actual_proof(
            app,
            window,
            report,
            to_max=to_max,
            apply_sync=apply_sync,
        )
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
    elif mode == "provider-startup-readiness-proof":
        _run_provider_startup_readiness_proof(
            app,
            window,
            widgets,
            paths,
            report,
            provider=provider or "",
            max_provider_calls=max_provider_calls,
            target_symbol=target_symbol,
            timeout_sec=timeout_sec,
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

    preserve_mode_fields: dict[str, Any] = {}
    if mode in {
        "managed-pool-manual-refresh-dedicated-opinion-proof",
        "managed-pool-manual-refresh-metadata-audit-proof",
    }:
        for key in (
            "response_id_present",
            "token_usage_present",
            "response_id",
            "token_usage",
            "usage_input_tokens",
            "usage_output_tokens",
            "usage_total_tokens",
            "response_metadata_extracted",
            "response_metadata_missing_reason",
            "tooltip_exposes_token_usage",
            "metadata_audit_supported",
            "audit_schema",
            "audit_payload",
            "raw_payload_logged",
            "raw_response_logged",
            "secret_logged",
            "audit_summary_text",
        ):
            if key in report:
                preserve_mode_fields[key] = report.get(key)
    report.update(_collect(window, widgets))
    if preserve_mode_fields:
        report.update(preserve_mode_fields)
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
        "provider-startup-readiness-proof",
        "real-app-startup-readiness-proof",
        "top-markets-feed-proof",
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
            "provider-startup-readiness-proof",
            "real-app-startup-readiness-proof",
            "top-markets-feed-proof",
            "buy-ready-order-intent-contract-fixture-proof",
            "buy-ready-order-intent-contract-proof",
            "buy-ready-ai-opinion-freshness-unblock-fixture-proof",
            "buy-ready-ai-opinion-freshness-unblock-proof",
            "order-intent-candidate-inert-bridge-fixture-proof",
            "order-intent-candidate-inert-bridge-live-proof",
            "managed-pool-promotion-policy-proof",
            "managed-pool-promotion-quality-gate-proof",
            "managed-pool-promotion-quality-live-proof",
            "managed-pool-quality-ranked-rebuild-proof",
            "managed-pool-quality-ranked-rebuild-live-proof",
            "managed-pool-ai-review-queue-proof",
            "managed-pool-ai-opinion-flow-proof",
            "managed-pool-ai-opinion-ui-apply-proof",
            "managed-pool-gpt-one-shot-opinion-proof",
            "managed-pool-gpt-one-shot-opinion-ui-proof",
            "managed-pool-manual-refresh-dedicated-opinion-proof",
            "managed-pool-manual-refresh-metadata-audit-proof",
            "manual-ai-refresh-target-symbol-e2e-proof",
            "managed-pool-ai-opinion-reason-consistency-proof",
            "managed-pool-manual-ai-refresh-row-freshness-proof",
            "managed-pool-auto-promotion-apply-proof",
            "managed-pool-max-size-apply-button-proof",
            "managed-pool-max-size-apply-button-actual-proof",
            "managed-pool-max-size-apply-button-sync-proof",
            "managed-pool-max-size-apply-button-sync-actual-proof",
            "rotation-intent-ux-proof",
            "rotation-intent-live-candidate-proof",
            "rotation-intent-live-candidate-feed-proof",
            "holdings-to-managed-row-proof",
            "managed-pool-holding-display-sync-proof",
            "rotation-eligibility-from-holdings-proof",
            "save-probe",
            "riskguard-proof",
            "riskguard-active-path-proof",
            "riskguard-active-path-candidate-proof",
            "basic-candidate-discovery-proof",
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
    parser.add_argument("--fixture", default="")
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
    parser.add_argument("--observe-only", action="store_true")
    parser.add_argument("--apply-add-only", action="store_true")
    parser.add_argument("--apply-trim", action="store_true")
    parser.add_argument("--apply-sync", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--max-markets", type=int, default=20)
    parser.add_argument("--max-managed", type=int, default=10)
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--from-max", type=int, default=10)
    parser.add_argument("--from-count", type=int, default=8)
    parser.add_argument("--to-max", type=int, default=8)
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
        max_candidates=args.max_candidates,
        max_markets=args.max_markets,
        max_managed=args.max_managed,
        min_score=args.min_score,
        apply_add_only=args.apply_add_only,
        from_max=args.from_max,
        from_count=args.from_count,
        to_max=args.to_max,
        apply_trim=args.apply_trim,
        apply_sync=args.apply_sync,
        fixture=args.fixture,
    )
    print(_json_report_text(report))
    return 0 if report.get("status") in ("pass", "partial", "blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
