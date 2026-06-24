from __future__ import annotations

import html
import json
import re
import time
from typing import Any

SCHEMA = "aits.ai_output_contract.v1"

_RAW_ACTION_TO_CODE = {
    "ENTER": "entry_review",
    "BUY": "entry_review",
    "LONG": "entry_review",
    "SELL": "exit_review",
    "EXIT": "exit_review",
    "SHORT": "exit_review",
    "REDUCE": "risk_review",
    "RISK": "risk_review",
    "HOLD": "hold",
    "STAY": "hold",
    "WAIT": "observe",
    "WATCH": "observe",
    "OBSERVE": "observe",
    "SKIP": "blocked",
    "BLOCK": "blocked",
    "UNKNOWN": "insufficient_data",
}

_CODE_TO_DISPLAY = {
    "observe": "관망",
    "hold": "보유 유지",
    "entry_review": "진입 검토",
    "exit_review": "매도 검토",
    "risk_review": "위험 재검토",
    "blocked": "판단 보류",
    "insufficient_data": "데이터 확인 필요",
}

_INTERNAL_TOKENS = {
    "unknown": "확인 필요",
    "last_known_ai": "최근 AI 참고",
    "last_known_preview": "최근 Preview 참고",
    "USER": "사용자",
    "user": "사용자",
    "local_calculation": "LOCAL 계산 기반",
    "preview_only": "참고용",
    "submitted=0": "",
}


def normalize_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    raw = raw.replace("_", "-").replace("/", "-")
    if re.fullmatch(r"[A-Z0-9]{2,12}", raw):
        return f"KRW-{raw}"
    match = re.search(r"\bKRW-[A-Z0-9]{1,12}\b", raw)
    return match.group(0).upper() if match else raw


def decision_code_from_raw(value: Any) -> str:
    raw = str(value or "").strip()
    upper = raw.upper()
    if not upper:
        return "insufficient_data"
    if upper in _RAW_ACTION_TO_CODE:
        return _RAW_ACTION_TO_CODE[upper]
    for token, code in _RAW_ACTION_TO_CODE.items():
        if re.search(rf"\b{re.escape(token)}\b", upper):
            return code
    if any(token in raw for token in ("진입", "매수")):
        return "entry_review"
    if any(token in raw for token in ("매도", "청산", "축소")):
        return "exit_review"
    if any(token in raw for token in ("보유", "유지")):
        return "hold"
    if any(token in raw for token in ("관망", "대기", "확인")):
        return "observe"
    return "insufficient_data" if upper in {"UNKNOWN", "-", "NONE"} else "observe"


def decision_display_from_code(code: Any) -> str:
    return _CODE_TO_DISPLAY.get(str(code or "").strip(), "데이터 확인 필요")


def sanitize_user_text(value: Any, *, symbol: str = "", limit: int = 360) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^```(?:json|JSON)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)

    current = normalize_symbol(symbol)
    def _replace_symbol(match: re.Match[str]) -> str:
        found = normalize_symbol(match.group(0))
        return found if current and found == current else "현재 종목"

    text = re.sub(r"\bKRW-[A-Z0-9]{1,12}\b", _replace_symbol, text, flags=re.I)
    action_labels = {
        "ENTER": "진입 검토",
        "BUY": "진입 검토",
        "SELL": "매도 검토",
        "EXIT": "매도 검토",
        "STAY": "관망",
        "WAIT": "관망",
        "HOLD": "보유 유지",
        "WATCH": "관망",
    }
    for raw, display in action_labels.items():
        text = re.sub(rf"\b{raw}\b", display, text, flags=re.I)
    for raw, display in _INTERNAL_TOKENS.items():
        text = text.replace(raw, display)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("지금 매수하세요", "진입 검토 조건이 관찰되었습니다")
    text = text.replace("즉시 매도", "매도 검토가 필요한 상태입니다")
    text = text.replace("분할 진입 실행", "분할 진입 조건을 검토할 수 있습니다")
    if len(text) > int(limit or 360):
        text = text[: int(limit or 360) - 1].rstrip() + "…"
    return text


def _safe_list(value: Any, *, symbol: str = "", limit: int = 5) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = re.split(r"[\n|•]+", str(value))
    out: list[str] = []
    for item in raw_items:
        clean = sanitize_user_text(item, symbol=symbol, limit=220)
        if clean and clean not in out:
            out.append(clean)
        if len(out) >= max(1, int(limit or 5)):
            break
    return out


def _parse_raw_response(raw: Any) -> tuple[dict[str, Any], str]:
    if isinstance(raw, dict):
        return dict(raw), "ok"
    text = str(raw or "").strip()
    if not text:
        return {}, "empty"
    text = re.sub(r"^```(?:json|JSON)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}, "ok"
    except Exception:
        return {"briefing": text}, "parse_failed"


def normalize_ai_output_contract(
    payload: Any = None,
    *,
    raw_response: Any = None,
    requested_symbol: str = "",
    provider_selected: str = "",
    provider_actual: str = "",
    model: str = "",
    source: str = "",
    analysis_kind: str = "",
) -> dict[str, Any]:
    data = dict(payload or {}) if isinstance(payload, dict) else {}
    if data.get("output_contract", {}).get("schema") == SCHEMA:
        return dict(data.get("output_contract") or {})
    parsed, parse_status = _parse_raw_response(
        raw_response
        if raw_response is not None
        else data.get("raw_ai_response") or data.get("raw_response") or data.get("ai_raw_text") or data
    )
    if parsed:
        merged = dict(data)
        merged.update(parsed)
        data = merged

    req_symbol = normalize_symbol(
        requested_symbol
        or data.get("requested_symbol")
        or data.get("symbol")
        or data.get("market")
        or data.get("code")
    )
    out_symbol = normalize_symbol(data.get("symbol") or data.get("market") or data.get("code"))
    warnings: list[str] = []
    if not out_symbol and req_symbol:
        out_symbol = req_symbol
        warnings.append("symbol_missing_used_requested")
    elif req_symbol and out_symbol and req_symbol != out_symbol:
        warnings.append("result_symbol_mismatch")
        out_symbol = req_symbol

    selected = str(provider_selected or data.get("provider_selected") or data.get("selected_provider") or data.get("selected_engine") or data.get("source") or "").strip().lower()
    actual = str(provider_actual or data.get("provider_actual") or data.get("actual_provider") or data.get("provider") or data.get("source") or selected or "").strip().lower()
    if actual in {"gpt", "openai"}:
        actual = "gpt"
    elif actual == "gemini":
        actual = "gemini"
    elif actual in {"local", "basic", "local_ai", "base", "provider_fallback", "local_calculation"}:
        actual = "local"
    else:
        actual = "local" if str(data.get("basic_fallback") or data.get("use_basic_engine")).lower() == "true" else actual
    if selected in {"openai"}:
        selected = "gpt"
    elif selected in {"basic", "local_ai", "base"}:
        selected = "local"
    if not selected:
        selected = actual or "local"

    model_text = str(model or data.get("model") or data.get("selected_model") or data.get("actual_model") or "").strip()
    if actual == "local" and re.search(r"gpt|gemini", model_text, flags=re.I):
        warnings.append("provider_model_mismatch_removed")
        model_text = ""
    engine_label = {"gpt": "GPT", "gemini": "Gemini", "local": "LOCAL 계산 기반"}.get(actual, "엔진 확인 필요")
    if actual in {"gpt", "gemini"} and model_text:
        engine_label = f"{engine_label} · {model_text}"

    raw_decision = data.get("decision") or data.get("decision_summary") or data.get("action") or data.get("next_action") or ""
    decision_code = decision_code_from_raw(raw_decision)
    decision_display = decision_display_from_code(decision_code)
    reason_items = _safe_list(data.get("reason") or data.get("reasons") or data.get("basis"), symbol=out_symbol, limit=5)
    next_items = _safe_list(data.get("next_action") or data.get("next_actions"), symbol=out_symbol, limit=3)
    briefing = sanitize_user_text(
        data.get("briefing_summary") or data.get("briefing") or data.get("summary") or data.get("decision_summary") or decision_display,
        symbol=out_symbol,
        limit=240,
    ) or decision_display
    basis = sanitize_user_text(data.get("basis_summary") or (reason_items[0] if reason_items else ""), symbol=out_symbol, limit=240)
    if not basis:
        basis = "현재 확인 가능한 계산/응답 정보를 기준으로 한 참고 판단입니다."
    user_reason = sanitize_user_text(data.get("user_reason") or data.get("reason_text") or "", symbol=out_symbol, limit=320)
    if not user_reason or user_reason == basis:
        user_reason = f"{decision_display} 상태로 분류되었지만, 실제 주문 신호가 아니므로 추가 확인이 필요합니다."
    next_observation = sanitize_user_text(data.get("next_observation") or (next_items[0] if next_items else ""), symbol=out_symbol, limit=240)
    if not next_observation:
        next_observation = "다음 가격 흐름과 거래대금 변화를 확인합니다."

    fallback_used = bool(data.get("fallback_used") or data.get("fallback") or parse_status != "ok")
    kind = str(analysis_kind or data.get("analysis_kind") or "").strip()
    if not kind:
        kind = "local_calculation" if actual == "local" else "provider_ai"
    if fallback_used and actual == "local" and selected in {"gpt", "gemini"}:
        kind = "provider_fallback"
    generated_at = str(data.get("generated_at") or data.get("ai_briefing_generated_at") or data.get("created_at") or "").strip()
    if not generated_at:
        generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    confidence = data.get("confidence") or data.get("score") or ""
    try:
        confidence = float(confidence) if confidence not in ("", None) else None
    except Exception:
        confidence = None
    if parse_status != "ok":
        decision_code = "insufficient_data"
        decision_display = decision_display_from_code(decision_code)
        briefing = "AI 응답을 안전하게 해석하지 못해 현재 판단을 보류합니다."
        basis = "응답 형식 또는 필드가 부족해 안전 fallback을 사용했습니다."
        user_reason = "AI 응답을 안전하게 해석하지 못해 현재 판단을 보류합니다."
        next_observation = "데이터와 응답 상태를 확인한 뒤 다시 검토합니다."

    return {
        "schema": SCHEMA,
        "symbol": out_symbol,
        "requested_symbol": req_symbol,
        "provider_selected": selected,
        "provider_actual": actual or "local",
        "model": model_text,
        "engine_label": engine_label,
        "analysis_kind": kind,
        "source": str(source or data.get("source") or ("local_basic" if actual == "local" else "manual_refresh")).strip(),
        "generated_at": generated_at,
        "decision_code": decision_code,
        "decision_display": decision_display,
        "briefing_summary": briefing,
        "basis_summary": basis,
        "user_reason": user_reason,
        "next_observation": next_observation,
        "confidence": confidence,
        "is_valid": parse_status == "ok" and decision_code != "insufficient_data",
        "parse_status": parse_status,
        "fallback_used": bool(fallback_used),
        "warnings": warnings,
        "safety": {
            "is_order_signal": False,
            "is_execution_plan": False,
            "order_allowed": False,
            "submitted": 0,
            "real_order": False,
            "suggestion_only": True,
            "display_only": True,
        },
    }


def contract_to_compat_payload(contract: dict[str, Any]) -> dict[str, Any]:
    c = dict(contract or {})
    return {
        "output_contract": c,
        "decision": c.get("decision_display") or "데이터 확인 필요",
        "decision_summary": c.get("decision_display") or "데이터 확인 필요",
        "reason": [c.get("basis_summary") or "", c.get("user_reason") or ""],
        "next_action": [c.get("next_observation") or ""],
        "provider": c.get("provider_actual") or "local",
        "source": c.get("source") or "",
        "model": c.get("model") or "",
        "generated_at": c.get("generated_at") or "",
        "confidence": c.get("confidence"),
        "order_allowed": False,
        "submitted": 0,
        "real_order": False,
    }


__all__ = [
    "SCHEMA",
    "normalize_ai_output_contract",
    "contract_to_compat_payload",
    "sanitize_user_text",
    "decision_code_from_raw",
    "decision_display_from_code",
    "normalize_symbol",
]
