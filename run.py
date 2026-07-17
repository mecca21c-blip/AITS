import os
import sys
import logging
import threading


def _configure_release_environment() -> None:
    """Apply laptop-safe thread/Qt defaults before importing numerical or Qt modules."""
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(name, "2")
    os.environ.setdefault("QT_OPENGL", "software")


_configure_release_environment()

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict, Optional

from app.utils.prefs import init_prefs
from app.core.aits_state import AITSRuntimeState
from app.services.aits_orchestrator import AITSOrchestrator
from app.services.aits_path_resolver import AITSPathResolver


def resolve_paths() -> Dict[str, str]:
    paths = AITSPathResolver.resolve(module_file=__file__)
    data_dir = AITSPathResolver.runtime_data_dir(paths)
    return {**paths.as_strings(), "root_dir": str(paths.app_root), "data_dir": str(data_dir), "log_dir": str(paths.user_data_root / "logs")}


def ensure_runtime_dirs(data_dir: str, log_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)


def init_logging(log_dir: str) -> logging.Logger:
    logger = logging.getLogger("aits")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    log_path = os.path.join(log_dir, "aits.log")
    fh = RotatingFileHandler(
        log_path,
        maxBytes=16 * 1024 * 1024,
        backupCount=12,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def init_app_context(
    root_dir: str,
    data_dir: str,
    log_dir: str,
    logger: logging.Logger,
    run_mode: str,
) -> Dict[str, Any]:
    try:
        init_prefs(root_dir, data_dir)
    except Exception:
        logger.exception("init_prefs failed")
        raise
    runtime_state = AITSRuntimeState()
    runtime_state.meta.run_mode = run_mode
    runtime_state.system.initialized = False
    runtime_state.system.running = False
    runtime_state.system.paused = False
    return {
        "root_dir": root_dir,
        "data_dir": data_dir,
        "log_dir": log_dir,
        "logger": logger,
        "run_mode": run_mode,
        "runtime_state": runtime_state,
        "started_at": datetime.now(),
    }


def init_aits(app_context: Dict[str, Any]) -> AITSOrchestrator:
    logger = app_context["logger"]
    run_mode = app_context["run_mode"]
    # [AITS-103] Load persisted settings for orchestrator/provider context.
    # - Keep safe fallback if settings loading fails.
    # - Never log API keys or full settings payload.
    aits_settings = None
    aits_config = {}

    try:
        from app.utils.prefs import _get_prefs_path, load_settings

        aits_settings = load_settings()
        if aits_settings is not None and hasattr(aits_settings, "model_dump"):
            aits_config = aits_settings.model_dump()
        elif aits_settings is not None and hasattr(aits_settings, "dict"):
            aits_config = aits_settings.dict()
        else:
            aits_config = {}

        print("[AITS][run] settings_loaded_for_orchestrator | ok=1")
        try:
            strategy = getattr(aits_settings, "strategy", None)
            provider = str(getattr(strategy, "ai_provider", "") or "")
            openai_key = str(getattr(strategy, "ai_openai_api_key", "") or "")
            prefs_path = _get_prefs_path()
            logger.info(
                "[AITS][RuntimePathDiagnostic] run_mode=%s | cwd=%s | root_dir=%s | data_dir=%s | prefs_path=%s | prefs_exists=%s | provider=%s | openai_key_present=%s | openai_key_len=%s",
                run_mode,
                os.getcwd(),
                app_context.get("root_dir", ""),
                app_context.get("data_dir", ""),
                prefs_path,
                os.path.exists(prefs_path),
                provider,
                bool(openai_key.strip()),
                len(openai_key.strip()),
            )
        except Exception as diag_exc:
            logger.info(
                "[AITS][RuntimePathDiagnostic] status=failed | error_type=%s",
                type(diag_exc).__name__,
            )
    except Exception as exc:
        aits_settings = None
        aits_config = {}
        print(f"[AITS][run] settings_loaded_for_orchestrator | ok=0 | reason={type(exc).__name__}")
        try:
            logger.info(
                "[AITS][RuntimePathDiagnostic] run_mode=%s | cwd=%s | root_dir=%s | data_dir=%s | prefs_path=%s | prefs_exists=%s | provider=%s | openai_key_present=%s | openai_key_len=%s",
                run_mode,
                os.getcwd(),
                app_context.get("root_dir", ""),
                app_context.get("data_dir", ""),
                "",
                False,
                "",
                False,
                0,
            )
        except Exception:
            pass

    orchestrator = AITSOrchestrator(
        config=aits_config,
        app_state=aits_settings,
        logger=logger,
        run_mode=run_mode,
    )
    ok = orchestrator.initialize()
    if not ok:
        logger.error("AITSOrchestrator.initialize() returned False")
        raise RuntimeError("AITSOrchestrator initialization failed")
    app_context["orchestrator"] = orchestrator
    app_context["runtime_state"] = orchestrator.get_runtime_state()
    logger.info("AITS orchestrator initialized")
    return orchestrator


def _install_smoke_exit_hook(logger: logging.Logger, timeout_ms: int = 4000) -> None:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog
    except Exception:
        logger.exception("[AITS][SmokeExit] hook_import_failed")
        return

    try:
        original_exec = QApplication.exec
        if getattr(original_exec, "_aits_smoke_exit_wrapped", False):
            return
        original_dialog_exec = QDialog.exec
        smoke_state = {"done": False}

        def _flush_logs():
            try:
                for handler in logger.handlers:
                    try:
                        handler.flush()
                    except Exception:
                        pass
            except Exception:
                pass

        def _mark_quit_logged():
            if smoke_state.get("done"):
                return False
            smoke_state["done"] = True
            try:
                logger.info("[AITS][SmokeExit] quit")
                _flush_logs()
            except Exception:
                pass
            return True

        def _force_quit():
            if _mark_quit_logged():
                os._exit(0)

        logger.info("[AITS][SmokeExit] scheduled")
        _flush_logs()
        watchdog = threading.Timer(max(float(timeout_ms) / 1000.0, 1.0), _force_quit)
        watchdog.daemon = True
        watchdog.start()

        def _smoke_exec(self, *args, **kwargs):
            try:
                def _quit():
                    if _mark_quit_logged():
                        try:
                            app = QApplication.instance()
                            if app is not None:
                                app.quit()
                        except Exception:
                            pass

                QTimer.singleShot(int(timeout_ms), _quit)
            except Exception:
                logger.exception("[AITS][SmokeExit] schedule_failed")
            return original_exec(self, *args, **kwargs)

        def _smoke_dialog_exec(self, *args, **kwargs):
            try:
                QTimer.singleShot(500, self.accept)
            except Exception:
                pass
            return original_dialog_exec(self, *args, **kwargs)

        setattr(_smoke_exec, "_aits_smoke_exit_wrapped", True)
        setattr(_smoke_dialog_exec, "_aits_smoke_exit_wrapped", True)
        QApplication.exec = _smoke_exec
        QDialog.exec = _smoke_dialog_exec
    except Exception:
        logger.exception("[AITS][SmokeExit] hook_failed")


def _install_smoke_runtime_stubs(logger: logging.Logger) -> None:
    try:
        class _SmokeResponse:
            status_code = 200
            text = "[]"

            def json(self):
                return []

            def raise_for_status(self):
                return None

        def _empty_list(*args, **kwargs):
            return []

        def _empty_dict(*args, **kwargs):
            return {}

        def _holdings_stub(*args, **kwargs):
            return {"ok": True, "items": [], "krw": 0.0, "err": ""}

        try:
            import requests

            requests.get = lambda *args, **kwargs: _SmokeResponse()
        except Exception:
            pass

        try:
            from app.services import market_feed

            market_feed.get_markets = _empty_list
            market_feed.get_markets_with_names = _empty_list
            market_feed.get_tickers = _empty_dict
            market_feed.get_top_markets_by_volume = _empty_list
            market_feed.get_candle_minute = _empty_list
        except Exception:
            pass

        try:
            from app.services import upbit

            upbit.get_tickers = _empty_list
            upbit.get_top_markets_by_volume = _empty_list
            upbit.get_all_markets = _empty_list
        except Exception:
            pass

        try:
            from app.services import holdings_service

            holdings_service.fetch_live_holdings = _holdings_stub
        except Exception:
            pass

        try:
            from app.services.order_service import OrderService

            OrderService.fetch_accounts = lambda self: []
        except Exception:
            pass

        logger.info("[AITS][SmokeExit] runtime_stubs_installed")
    except Exception:
        logger.exception("[AITS][SmokeExit] runtime_stubs_failed")


def launch_ui(app_context: Dict[str, Any]) -> int:
    logger = app_context["logger"]
    if app_context.get("smoke_exit"):
        _install_smoke_runtime_stubs(logger)
        _install_smoke_exit_hook(logger)
    try:
        from app.ui.main_window import main as ui_main
    except Exception:
        logger.exception("UI import failed (app.ui.main_window)")
        return 1
    logger.info("UI launched via legacy-compatible entry")
    try:
        ret = ui_main(
            root_dir=app_context["root_dir"],
            data_dir=app_context["data_dir"],
        )
        if isinstance(ret, int):
            return ret
        return 0
    except Exception:
        logger.exception("UI main() failed")
        return 1


def run_headless(app_context: Dict[str, Any]) -> int:
    orchestrator = app_context["orchestrator"]
    logger = app_context["logger"]
    logger.info("AITS headless mode start")
    result = orchestrator.run_cycle()
    logger.info(result.summary_text())
    return 0 if result.is_success() else 1


def main() -> int:
    if __name__ == "__main__":
        try:
            import multiprocessing
            multiprocessing.freeze_support()
        except Exception:
            pass
    run_mode = "ui"
    if "--headless" in sys.argv:
        run_mode = "headless"
    elif "--smoke-exit" in sys.argv:
        run_mode = "smoke_exit"
    logger: Optional[logging.Logger] = None
    try:
        paths = resolve_paths()
        resolved = AITSPathResolver.resolve(module_file=__file__)
        AITSPathResolver.ensure_writable_roots(resolved)
        ensure_runtime_dirs(paths["data_dir"], paths["log_dir"])
        logger = init_logging(paths["log_dir"])
        logger.info("AITS bootstrap start")
        app_context = init_app_context(
            paths["root_dir"],
            paths["data_dir"],
            paths["log_dir"],
            logger,
            run_mode,
        )
        app_context["smoke_exit"] = run_mode == "smoke_exit"
        init_aits(app_context)
        if run_mode == "headless":
            return run_headless(app_context)
        return launch_ui(app_context)
    except Exception:
        if logger is not None:
            logger.exception("AITS bootstrap failed")
        else:
            print("AITS bootstrap failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
