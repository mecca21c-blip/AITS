from __future__ import annotations

import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler, MemoryHandler

# P0: 부트 시 KMTS_FORCE_AI_MISS=1이면 운영 안전을 위해 강제 0 적용 (테스트 시 KMTS_ALLOW_FORCED_MISS=1로 예외)
_FORCE_MISS_OVERRIDDEN = False
_force_miss_raw = os.environ.get("KMTS_FORCE_AI_MISS", "0")
if _force_miss_raw == "1" and os.environ.get("KMTS_ALLOW_FORCED_MISS", "0") != "1":
    os.environ["KMTS_FORCE_AI_MISS"] = "0"
    _FORCE_MISS_OVERRIDDEN = True

# 배포(설치형): Program Files 권한 회피 — 런타임 데이터는 LocalAppData에만 생성
_IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
if _IS_FROZEN:
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
    _base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    DATA_DIR = os.path.join(_base, "KMTS-v3", "data")
    LOG_DIR = os.path.join(DATA_DIR, "logs")
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(ROOT, "data")
    LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


class OrderTraceFilter(logging.Filter):
    """Filter to capture order-related log messages"""
    def filter(self, record):
        message = record.getMessage()
        return (
            "[ORDER-READY]" in message
            or "stage=CALL buy_market" in message
            or "buy_market" in message
        )


# PATCH 6: KMTS_DEBUG_LOG_IO=1일 때만 자세히, 기본은 핵심 태그만 INFO 유지
_INFO_ALLOWED_TAGS = (
    "[DECISION]", "[AI-FALLBACK]", "[TRADE-EN]", "[WL-TOP20]", "[WL-TOPN]", "[WL-HOLD]", "[WL-MERGE]", "[WL-WORKER-ERR]",
    "[AI-RECO]", "[AI-RECO-TICK]", "[GPT-RECO]", "[OPENAI]", "[OPENAI-CALL]", "[OPENAI-IMPORT-FAIL]",
    # 🔎 진단/원인추적 태그(패킹 exe 기본 모드에서도 INFO 통과)
    "[RUN-START]", "[RUNNER-INIT]", "[MODE-CHECK]",
    "[GPT-RAW]", "[GPT-ACTION]", "[GPT-IN]", "[GPT-OUT]", "[BUY-PRECHECK]", "[BUY-QUALITY-BLOCK]",
    "[ENGINE-UI]", "[ENGINE-SWITCH]", "[BUY-BLOCK]", "[AI-ROLE]", "[AI-TRACE]",
    "[BUILD-ID]",
    "[CAP-DOWN]", "[BUY-DOWNSCALE]",
    "[UI-PERF]", "[TIMER-CHK]", "[TOPN-REFRESH]", "[TOPN-TIMER]", "[TOPN-CACHE]",
    # 손절/경로 원인확정용 (패킹 kmts.log에 반드시 노출)
    "[PATHS]", "[TP/SL-RAW]", "[SL-CHECK]", "[SELL-SKIP-QTY]",
    "[PREFS-PATH]",
    # 로테이션 A안 (매매기록/로그 노출)
    "[ROTATION]",
    "[ROT-UI]",
    "[ROT-ENTRY]",
    "[ROT-CHECK]",
    "[ROT-DUE]", "[ROT-RUN]", "[ROT-CANDS]", "[ROT-FILTER]", "[ROT-GUARD]", "[ROT-GUARD-SAMPLE]", "[ROT-PICK]", "[ROT-ACT]",
    "[THR]",
)

_INFO_ALLOWED_PREFIXES = ("[ORDER-",)  # [ORDER-READY], [ORDER-ATTEMPT], [ORDER-FINAL] 등


class InfoTagFilter(logging.Filter):
    """기본 모드: INFO 중 핵심 태그만 통과. WARNING/ERROR 항상 통과."""
    def __init__(self, debug_io: bool = False):
        super().__init__()
        self._debug_io = debug_io

    def filter(self, record):
        if record.levelno > logging.INFO:
            return True
        if self._debug_io:
            return True
        msg = record.getMessage()
        if any(tag in msg for tag in _INFO_ALLOWED_TAGS):
            return True
        if any(p in msg for p in _INFO_ALLOWED_PREFIXES):
            return True
        return False


class ThrottleFilter(logging.Filter):
    """특정 태그([KEY-PERSIST] 등) 반복 시 interval_sec 내 동일 메시지 생략.
    debug_io=False면 해당 태그 필터(INFO→생략).
    """
    _last: dict = {}  # {msg_sig: last_ts}

    def __init__(self, tag: str = "[KEY-PERSIST]", interval_sec: float = 10.0, filter_when_not_debug: bool = False):
        super().__init__()
        self._tag = tag
        self._interval = interval_sec
        self._filter_when_not_debug = filter_when_not_debug

    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if self._tag not in msg:
            return True
        # PATCH 6: 기본 모드에서 [KEY-PERSIST] 등 반복 로그 완전 필터
        if self._filter_when_not_debug:
            return False
        now = time.time()
        sig = msg[:80]
        last_ts = ThrottleFilter._last.get(sig, 0)
        if now - last_ts >= self._interval:
            ThrottleFilter._last[sig] = now
            return True
        return False


def _init_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    debug_io = os.environ.get("KMTS_DEBUG_LOG_IO", "0") == "1"

    # Main formatter for consistent formatting
    main_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # 1) 파일 초기화 (handler 등록 전에)
    buy_final_log_path = os.path.join(LOG_DIR, "buy_order_final_only.log")
    try:
        with open(buy_final_log_path, "w", encoding="utf-8"):
            pass
    except Exception as e:
        print(f"Failed to initialize buy_order_final_only.log: {e}")

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
    ch.addFilter(ThrottleFilter("[KEY-PERSIST]", 10.0, filter_when_not_debug=not debug_io))
    if not debug_io:
        ch.addFilter(InfoTagFilter(debug_io=False))
    logger.addHandler(ch)

    # Main log file handler
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "kmts.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(main_formatter)

    # P0-1: 메인 로그 버퍼링. 진단 3종([GPT-DIAG]/[AI-DIAG]/[DECISION]) 기록 시 즉시 flush로 1회 확정 가능
    mem_capacity = 256 if debug_io else 4096
    _diag_tags = ("[GPT-DIAG]", "[AI-DIAG]", "[DECISION]")

    class FlushOnDiagMemoryHandler(MemoryHandler):
        def emit(self, record):
            try:
                msg = record.getMessage()
            except Exception:
                msg = ""
            if msg and any(tag in msg for tag in _diag_tags):
                self.flush()
            super().emit(record)

    mem_handler = FlushOnDiagMemoryHandler(
        capacity=mem_capacity,
        flushLevel=logging.ERROR,
        target=fh,
        flushOnClose=True,
    )
    mem_handler.addFilter(ThrottleFilter("[KEY-PERSIST]", 10.0, filter_when_not_debug=not debug_io))
    if not debug_io:
        mem_handler.addFilter(InfoTagFilter(debug_io=False))
    logger.addHandler(mem_handler)

    # Order trace file handler
    order_fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "order_trace.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    order_fh.setFormatter(main_formatter)
    order_fh.addFilter(OrderTraceFilter())
    # P0-1: Order trace도 버퍼링. PATCH 6: capacity 1024로 flush 빈도 감소
    order_mem_handler = MemoryHandler(
        capacity=256 if debug_io else 1024,
        flushLevel=logging.ERROR,
        target=order_fh,
        flushOnClose=True,
    )
    logger.addHandler(order_mem_handler)

    # 2) 전용 필터
    class BuyOrderFinalFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return "[BUY-FINAL]" in msg or "[ORDER-FINAL]" in msg

    # 3) 중복 핸들러 방지 후 등록
    if not any(
        isinstance(h, RotatingFileHandler) and h.baseFilename.endswith("buy_order_final_only.log")
        for h in logger.handlers
    ):
        buy_final_fh = RotatingFileHandler(buy_final_log_path, encoding="utf-8")
        buy_final_fh.setLevel(logging.INFO)
        buy_final_fh.setFormatter(main_formatter)  # 메인 로그와 동일 포맷
        buy_final_fh.addFilter(BuyOrderFinalFilter())
        # P0-1: Buy final도 버퍼링. PATCH 6: capacity 256으로 flush 빈도 감소
        buy_final_mem_handler = MemoryHandler(
            capacity=64 if debug_io else 256,
            flushLevel=logging.ERROR,
            target=buy_final_fh,
            flushOnClose=True,
        )
        logger.addHandler(buy_final_mem_handler)

    logging.info("Logging initialized (dir=%s debug_io=%s)", LOG_DIR, debug_io)

    # BUILD 스탬프: 패킹 exe가 "진단 로그 반영된 빌드"인지 로그로 즉시 판별
    # - frozen이면 __file__ mtime이 의미 없을 수 있어 exe mtime도 함께 남김
    try:
        _run_py = os.path.abspath(__file__)
        _run_mtime = int(os.path.getmtime(_run_py))
    except Exception:
        _run_py = "__unknown__"
        _run_mtime = -1

    try:
        _exe_path = os.path.abspath(sys.executable)
        _exe_mtime = int(os.path.getmtime(_exe_path))
    except Exception:
        _exe_path = os.path.abspath(sys.executable)
        _exe_mtime = -1

    logging.info(
        "[BUILD-ID] frozen=%s exe=%s exe_mtime=%s root=%s run_py=%s run_py_mtime=%s",
        _IS_FROZEN, _exe_path, _exe_mtime, ROOT, _run_py, _run_mtime
    )

    # 패킹 환경 경로 확정: prefs.json은 data_dir 아래에 생성됨
    try:
        _cwd = os.getcwd()
    except Exception:
        _cwd = "__unknown__"
    logging.info(
        "[PATHS] frozen=%s exe=%s root=%s data_dir=%s log_dir=%s cwd=%s",
        _IS_FROZEN, os.path.abspath(sys.executable), ROOT, DATA_DIR, LOG_DIR, _cwd
    )

    # PATCH: 패킹 실행에서 MemoryHandler 버퍼 때문에 부팅 직후 로그([BUILD-ID]/[PATHS])가 늦게/안 보이는 케이스 방지
    try:
        _root_logger = logging.getLogger()
        for _h in list(getattr(_root_logger, "handlers", []) or []):
            try:
                _h.flush()
            except Exception:
                pass
    except Exception:
        pass

    # 모드 확인 로그 (FORCE_SIMULATE 우선)
    force_sim = os.environ.get("KMTS_FORCE_SIMULATE", "0")
    try:
        from app.utils.prefs import load_settings
        settings = load_settings()
        prefs_live = getattr(settings, "live_trade", False)
    except Exception:
        prefs_live = False

    if force_sim == "1":
        final_mode = "SIMULATE"
    else:
        final_mode = "LIVE" if prefs_live else "SIMULATE"

    logging.info("[MODE] force_sim=%s -> FINAL=%s / prefs.live_trade=%s", force_sim, final_mode, prefs_live)


def main():
    import time as _time
    # 경로 확정: prefs는 여기서 한 번만 초기화 → 이후 load/save 모두 이 경로 사용 (패킹 시 LOCALAPPDATA 보장)
    _data_dir = os.environ.get("KMTS_DATA_DIR", "").strip() or DATA_DIR
    try:
        from app.utils.prefs import init_prefs
        init_prefs(ROOT, _data_dir)
    except Exception as _e:
        logging.warning("[BOOT] init_prefs failed: %s", getattr(_e, "message", str(_e))[:80])
    _init_logging()
    _boot_t0 = _time.perf_counter()
    logging.info("[BOOT0] start")

    # P0-ENV-AUDIT: 부트 시 env 증거 로그 (주입 근원 추적용)
    _env_audit = os.environ.get("KMTS_FORCE_AI_MISS", "__unset__")
    logging.info(
        "[BOOT-ENV] KMTS_FORCE_AI_MISS=%s (raw_at_import=%s overridden=%s)",
        _env_audit, _force_miss_raw, _FORCE_MISS_OVERRIDDEN
    )
    if _FORCE_MISS_OVERRIDDEN:
        logging.warning("[BOOT] KMTS_FORCE_AI_MISS=1 was set -> overridden to 0 (set KMTS_ALLOW_FORCED_MISS=1 for test)")

    _boot_t1 = _time.perf_counter()
    logging.info("[BOOT1] settings/logging ready elapsed_ms=%d", int((_boot_t1 - _boot_t0) * 1000))
    logging.info("KMTS-v1 starting (root=%s)", ROOT)

    try:
        from app.ui.main_window import main as ui_main
    except Exception as e:
        logging.exception("UI import failed: %s", e)
        sys.exit(1)

    ui_main(root_dir=ROOT, data_dir=_data_dir)


if __name__ == "__main__":
    main()
