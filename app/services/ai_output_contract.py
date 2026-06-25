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

    invoked_model = str(data.get("invoked_model") or "").strip()
    model_text = str(invoked_model or model or data.get("model") or data.get("selected_model") or data.get("actual_model") or "").strip()
    ollama_invoked = bool(data.get("ollama_invoked"))
    model_invoked = bool(data.get("model_invoked") or invoked_model or (actual in {"gpt", "gemini"} and model_text))
    if actual == "local" and not ollama_invoked:
        if model_text and re.search(r"gpt|gemini|qwen|llama|mistral", model_text, flags=re.I):
            warnings.append("provider_model_mismatch_removed")
        model_text = ""
        invoked_model = ""
        model_invoked = False
    elif actual == "local" and ollama_invoked and model_text:
        invoked_model = model_text
        model_invoked = True
    elif actual in {"gpt", "gemini"} and model_text:
        invoked_model = model_text
        model_invoked = True
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

    fallback_used = bool(_truthy(data.get("fallback_used")) or _truthy(data.get("fallback")) or parse_status != "ok")
    fallback_reason = resolve_ai_fallback_reason(data if isinstance(data, dict) else {})
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
        "invoked_model": invoked_model if model_invoked else "",
        "model_invoked": bool(model_invoked),
        "ollama_invoked": bool(ollama_invoked),
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
        "fallback_reason_code": fallback_reason.get("fallback_reason_code") or "",
        "fallback_reason_display": fallback_reason.get("fallback_reason_display") or "",
        "fallback_error_class": fallback_reason.get("fallback_error_class") or "",
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
        "invoked_model": c.get("invoked_model") or "",
        "model_invoked": bool(c.get("model_invoked")),
        "ollama_invoked": bool(c.get("ollama_invoked")),
        "fallback_used": bool(c.get("fallback_used")),
        "fallback_reason_code": c.get("fallback_reason_code") or "",
        "fallback_reason_display": c.get("fallback_reason_display") or "",
        "fallback_error_class": c.get("fallback_error_class") or "",
        "provider_selected": c.get("provider_selected") or "",
        "provider_actual": c.get("provider_actual") or "",
        "engine_label": c.get("engine_label") or "",
        "generated_at": c.get("generated_at") or "",
        "confidence": c.get("confidence"),
        "order_allowed": False,
        "submitted": 0,
        "real_order": False,
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on", "applied"}


def _canonical_provider(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"openai", "gpt", "chatgpt"}:
        return "gpt"
    if text in {"gemini", "google"}:
        return "gemini"
    if text in {"local", "basic", "base", "local_ai", "local_calculation"}:
        return "local"
    return text


def provider_display_label(provider: Any) -> str:
    code = _canonical_provider(provider)
    if code == "gpt":
        return "GPT"
    if code == "gemini":
        return "Gemini"
    if code == "local":
        return "LOCAL"
    return str(provider or "").strip() or "-"


def resolve_ai_fallback_reason(metadata: dict[str, Any] | None = None) -> dict[str, str]:
    data = metadata if isinstance(metadata, dict) else {}
    existing_code = str(data.get("fallback_reason_code") or "").strip().lower()
    existing_display = str(data.get("fallback_reason_display") or "").strip()
    if existing_code and existing_display:
        return {
            "fallback_reason_code": existing_code,
            "fallback_reason_display": existing_display,
            "fallback_error_class": str(data.get("fallback_error_class") or existing_code).strip(),
        }
    raw = " ".join(
        str(data.get(key) or "")
        for key in (
            "fallback_reason",
            "fallback_error_summary",
            "error_summary",
            "error",
            "reason",
            "reason_code",
            "status",
            "parse_status",
        )
    ).strip()
    low = raw.lower()
    code = existing_code or "provider_failed"
    if any(token in low for token in ("timeout", "timed out", "deadline", "watchdog")):
        code = "timeout"
        display = "AI 응답 시간이 초과되어 LOCAL 계산 기반으로 대체했습니다."
    elif any(token in low for token in ("429", "quota", "resource_exhausted", "resource exhausted", "limit")):
        code = "quota_exceeded"
        display = "AI 사용 한도를 초과해 LOCAL 계산 기반으로 대체했습니다."
    elif any(token in low for token in ("401", "403", "auth", "permission", "unauthorized", "forbidden")):
        code = "auth_failed"
        display = "AI 인증 또는 권한 문제로 LOCAL 계산 기반으로 대체했습니다."
    elif any(token in low for token in ("404", "not_found", "not found", "model_not_found", "model unavailable")):
        code = "model_unavailable"
        display = "선택한 AI 모델을 사용할 수 없어 LOCAL 계산 기반으로 대체했습니다."
    elif any(token in low for token in ("parse", "invalid_json", "invalid json", "malformed")):
        code = "response_parse_failed"
        display = "AI 응답을 안전하게 해석하지 못해 LOCAL 계산 기반으로 대체했습니다."
    elif any(token in low for token in ("connection", "connect", "network", "unavailable", "dns", "ssl", "http 5")):
        code = "connection_failed"
        display = "AI 서비스 연결에 실패해 LOCAL 계산 기반으로 대체했습니다."
    else:
        display = existing_display or "AI 응답을 받지 못해 LOCAL 계산 기반으로 안전하게 대체했습니다."
    return {
        "fallback_reason_code": code,
        "fallback_reason_display": display,
        "fallback_error_class": str(data.get("fallback_error_class") or code).strip(),
    }


def classify_ai_analysis_record(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    data = metadata if isinstance(metadata, dict) else {}
    contract = data.get("output_contract") if isinstance(data.get("output_contract"), dict) else {}
    selected = _canonical_provider(
        data.get("provider_selected")
        or contract.get("provider_selected")
        or data.get("selected_provider")
        or data.get("selected_engine")
    )
    actual = _canonical_provider(
        data.get("provider_actual")
        or contract.get("provider_actual")
        or data.get("actual_provider")
        or data.get("provider")
        or data.get("source")
    )
    source_event = str(data.get("source_event") or contract.get("source") or data.get("source") or "").strip().lower()
    analysis_kind = str(data.get("analysis_kind") or contract.get("analysis_kind") or "").strip().lower()
    fallback_used = bool(_truthy(data.get("fallback_used")) or _truthy(contract.get("fallback_used")))
    fallback_confirmed = bool(_truthy(data.get("provider_fallback_confirmed")) or analysis_kind == "provider_fallback")
    manual_source = source_event in {
        "manual_refresh",
        "detail_chart_manual_refresh",
        "detail_chart_button",
        "main_ai_refresh",
        "provider_fallback",
    } or str(data.get("source") or "").strip().lower() == "manual_refresh"
    provider_fallback = (
        selected in {"gpt", "gemini"}
        and actual == "local"
        and fallback_used
        and fallback_confirmed
        and manual_source
    )
    if provider_fallback:
        classification = "provider_fallback"
    elif manual_source and selected == "local" and actual == "local":
        classification = "manual_local_analysis"
    elif manual_source and selected in {"gpt", "gemini"} and actual in {"gpt", "gemini"} and not fallback_used:
        classification = "manual_provider_success"
    elif actual == "local" and analysis_kind == "local_calculation":
        classification = "automatic_local_monitor"
    elif str(data.get("record_stage") or "").strip() == "aits_shadow_final" and not manual_source:
        classification = "automatic_local_monitor"
    elif not source_event and not analysis_kind:
        classification = "restored_legacy"
    else:
        classification = "unknown_safe"

    if classification == "provider_fallback":
        reason = resolve_ai_fallback_reason({**data, **contract})
        return {
            "analysis_classification": classification,
            "record_type_display": "안전 대체판정",
            "analysis_source_display": "사용자가 실행",
            "selected_engine_display": provider_display_label(selected),
            "actual_engine_display": "LOCAL 계산 기반",
            "fallback_status_display": "적용됨",
            "fallback_reason_code": reason.get("fallback_reason_code") or "",
            "fallback_reason_display": reason.get("fallback_reason_display") or "",
            "is_provider_fallback": True,
            "is_automatic_monitor": False,
        }
    if classification == "automatic_local_monitor":
        return {
            "analysis_classification": classification,
            "record_type_display": "AITS 모의판정",
            "analysis_source_display": "자동 감시",
            "selected_engine_display": "자동 감시",
            "actual_engine_display": "LOCAL 계산 기반",
            "fallback_status_display": "해당 없음",
            "fallback_reason_code": "",
            "fallback_reason_display": "대체 사유 없음",
            "is_provider_fallback": False,
            "is_automatic_monitor": True,
        }
    if classification == "manual_local_analysis":
        return {
            "analysis_classification": classification,
            "record_type_display": "AI 원판단",
            "analysis_source_display": "사용자가 실행",
            "selected_engine_display": "LOCAL",
            "actual_engine_display": "LOCAL 계산 기반",
            "fallback_status_display": "아님",
            "fallback_reason_code": "",
            "fallback_reason_display": "대체 사유 없음",
            "is_provider_fallback": False,
            "is_automatic_monitor": False,
        }
    if classification == "manual_provider_success":
        engine = provider_display_label(actual)
        model = str(data.get("invoked_model") or contract.get("invoked_model") or data.get("model") or contract.get("model") or "").strip()
        if model:
            engine = f"{engine} · {model}"
        return {
            "analysis_classification": classification,
            "record_type_display": "AI 원판단",
            "analysis_source_display": "사용자가 실행",
            "selected_engine_display": provider_display_label(selected),
            "actual_engine_display": engine,
            "fallback_status_display": "아님",
            "fallback_reason_code": "",
            "fallback_reason_display": "대체 사유 없음",
            "is_provider_fallback": False,
            "is_automatic_monitor": False,
        }
    return {
        "analysis_classification": classification,
        "record_type_display": "이전 AI 판단 기록" if classification == "restored_legacy" else "AI 판단 기록",
        "analysis_source_display": "이전 기록" if classification == "restored_legacy" else "출처 확인 필요",
        "selected_engine_display": data.get("selected_engine") or provider_display_label(selected) or "-",
        "actual_engine_display": data.get("actual_engine") or provider_display_label(actual) or "-",
        "fallback_status_display": "대체 사유 기록 없음" if fallback_used else "아님",
        "fallback_reason_code": "",
        "fallback_reason_display": "대체 사유 기록 없음" if fallback_used else "",
        "is_provider_fallback": False,
        "is_automatic_monitor": False,
    }


__all__ = [
    "SCHEMA",
    "normalize_ai_output_contract",
    "contract_to_compat_payload",
    "sanitize_user_text",
    "decision_code_from_raw",
    "decision_display_from_code",
    "normalize_symbol",
    "resolve_ai_fallback_reason",
    "classify_ai_analysis_record",
    "provider_display_label",
]
