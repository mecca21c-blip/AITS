"""Minimal AI recommendation shim for UI boot (no real engine)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from app.services.basic_decision_engine import build_basic_decision

_LAST_DECISION: Dict[str, Any] = {
    "actual_engine": "",
    "selected_engine": "",
}
_LAST_ADVICE: Dict[str, Any] = {
    "source": "local",
    "fallback": False,
    "items": [],
    "decision_summary": "",
    "reason_code": "",
}
_SCHEDULER_STARTED: bool = False

_publish_fn: Optional[Callable[..., Any]] = None
_settings_getter: Optional[Callable[..., Any]] = None


def _build_basic_fallback_decision(
    market_rows: Optional[List[Dict[str, Any]]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
    max_positions: int = 3,
) -> Dict[str, Any]:
    try:
        market_rows = market_rows or []
        positions = positions or []
        return build_basic_decision(
            market_rows=market_rows,
            positions=positions,
            max_positions=max_positions,
        )
    except Exception as e:
        return {
            "decision": "STAY",
            "reason": f"기본 엔진 fallback 실패: {e}",
            "next_action": "관망 유지",
            "rotation": {
                "needed": False,
            },
        }


def _basic_dict_to_reco_payload(basic: Dict[str, Any]) -> Dict[str, Any]:
    rot = basic.get("rotation") or {}
    if not isinstance(rot, dict):
        rot = {}
    from_sym = str(rot.get("from_symbol") or rot.get("out_symbol") or "").strip()
    to_sym = str(rot.get("to_symbol") or rot.get("in_symbol") or "").strip()
    why = str(rot.get("why") or "").strip()
    if not why and rot.get("score_gap") is not None:
        why = f"score_gap={rot.get('score_gap')}"
    rot_ui = {
        "needed": bool(rot.get("needed", False)),
        "from_symbol": from_sym,
        "to_symbol": to_sym,
        "why": why,
    }
    r = basic.get("reason", "")
    if isinstance(r, list):
        reason_list = [str(x).strip() for x in r if str(x).strip()]
    else:
        reason_list = [str(r).strip()] if str(r).strip() else []
    na = basic.get("next_action", "")
    if isinstance(na, list):
        next_list = [str(x).strip() for x in na if str(x).strip()]
    else:
        next_list = [str(na).strip()] if str(na).strip() else []
    decision = str(basic.get("decision") or "").strip()
    raw_obj = {
        "decision": decision,
        "reason": reason_list,
        "next_action": next_list,
        "rotation": rot_ui,
    }
    raw_s = json.dumps(raw_obj, ensure_ascii=False)
    reason_code = reason_list[0] if reason_list else ""
    return {
        "ok": True,
        "source": "local",
        "fallback": True,
        "items": [],
        "decision_summary": decision,
        "reason_code": reason_code,
        "raw_ai_response": raw_s,
        "rotation": rot_ui,
    }


def _safe_publish(topic: str, payload: Any = None) -> None:
    fn = _publish_fn
    if fn is None:
        return
    try:
        fn(topic, payload)
    except Exception:
        try:
            fn(topic, payload=payload)
        except Exception:
            pass


def start_scheduler(settings_getter: Any = None, publish_fn: Any = None) -> bool:
    global _SCHEDULER_STARTED, _publish_fn, _settings_getter
    try:
        _settings_getter = settings_getter
        _publish_fn = publish_fn if callable(publish_fn) else None
        _SCHEDULER_STARTED = True
        return True
    except Exception:
        _SCHEDULER_STARTED = True
        return True


def update(payload: Any = None, from_boot: bool = False) -> Dict[str, Any]:
    global _LAST_ADVICE, _LAST_DECISION
    try:
        out: Dict[str, Any] = {
            "ok": True,
            "source": "local",
            "fallback": False,
            "items": [],
            "decision_summary": "",
            "reason_code": "",
        }
        if isinstance(payload, dict):
            for k in ("ok", "source", "fallback", "items", "decision_summary", "reason_code"):
                if k in payload:
                    out[k] = payload[k]
            for k in ("raw_ai_response", "rotation"):
                if k in payload:
                    out[k] = payload[k]

        use_basic = False
        market_rows: List[Dict[str, Any]] = []
        positions: List[Dict[str, Any]] = []
        max_positions = 3
        if isinstance(payload, dict):
            if payload.get("basic_fallback") or payload.get("use_basic_engine"):
                use_basic = True
            if isinstance(payload.get("market_rows"), list):
                use_basic = True
                market_rows = list(payload.get("market_rows") or [])
            if isinstance(payload.get("positions"), list):
                positions = list(payload.get("positions") or [])
            if payload.get("max_positions") is not None:
                try:
                    max_positions = int(payload.get("max_positions", 3))
                except (TypeError, ValueError):
                    max_positions = 3
        if from_boot and (payload is None or payload == {}):
            use_basic = True

        if use_basic:
            basic = _build_basic_fallback_decision(
                market_rows=market_rows,
                positions=positions,
                max_positions=max_positions,
            )
            merged = _basic_dict_to_reco_payload(basic)
            for k, v in merged.items():
                out[k] = v

        _LAST_ADVICE = dict(out)
        _LAST_DECISION = {
            "actual_engine": "",
            "selected_engine": "",
        }
        if isinstance(payload, dict):
            if "actual_engine" in payload:
                _LAST_DECISION["actual_engine"] = str(payload.get("actual_engine") or "")
            if "selected_engine" in payload:
                _LAST_DECISION["selected_engine"] = str(payload.get("selected_engine") or "")
        _safe_publish("ai.reco.updated", out)
        _safe_publish("ai.reco.items", out.get("items"))
        _safe_publish("ai.reco.strategy_suggested", out)
        return out
    except Exception:
        basic = _build_basic_fallback_decision([], [], 3)
        fallback = _basic_dict_to_reco_payload(basic)
        _LAST_ADVICE = dict(fallback)
        _safe_publish("ai.reco.updated", fallback)
        _safe_publish("ai.reco.items", fallback.get("items"))
        _safe_publish("ai.reco.strategy_suggested", fallback)
        return fallback


def get_last_decision() -> Dict[str, Any]:
    try:
        return dict(_LAST_DECISION)
    except Exception:
        return {"actual_engine": "", "selected_engine": ""}


def poll_gpt_future() -> Dict[str, Any]:
    try:
        return dict(_LAST_DECISION) if _LAST_DECISION else {}
    except Exception:
        return {}
