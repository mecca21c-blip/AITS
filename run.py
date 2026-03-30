import os
import sys
import logging

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


def resolve_paths() -> Dict[str, str]:
    frozen = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
    if frozen:
        root_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        root_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(root_dir, "data")
    log_dir = os.path.join(data_dir, "logs")
    return {
        "root_dir": root_dir,
        "data_dir": data_dir,
        "log_dir": log_dir,
    }


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
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
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
    orchestrator = AITSOrchestrator(
        config={},
        app_state=None,
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


def launch_ui(app_context: Dict[str, Any]) -> int:
    logger = app_context["logger"]
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
    run_mode = "ui"
    if "--headless" in sys.argv:
        run_mode = "headless"
    logger: Optional[logging.Logger] = None
    try:
        paths = resolve_paths()
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
