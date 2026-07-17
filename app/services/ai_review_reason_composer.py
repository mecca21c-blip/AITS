from __future__ import annotations

from typing import Any


GOOD_DECISIONS = {"good", "acceptable"}
WEAK_DECISIONS = {"weak", "poor"}


def evaluate_decision_quality(decision: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Evaluate only evidence available at decision time; outcomes are intentionally absent."""
    success: list[str] = []
    failure: list[str] = []
    reason = str(decision.get("final_reason_ko") or decision.get("ai_reason_ko") or "").strip()
    missing = list(decision.get("missing_critical_features") or [])
    stale = list(decision.get("stale_features") or [])
    validator = decision.get("validator_result")
    quality = str(decision.get("payload_quality_grade") or "").lower()
    confidence = decision.get("final_confidence")
    if reason:
        success.append("evidence_aligned")
    else:
        failure.append("insufficient_data")
    if missing or bool(decision.get("ai_reason_mentions_insufficient_data")):
        failure.append("insufficient_data")
    if stale:
        failure.append("stale_data")
    if bool(decision.get("model_prediction_vs_external") == "disagree"):
        failure.append("teacher_disagreement")
    if isinstance(validator, dict) and validator.get("valid") is False:
        failure.append("evidence_conflicted")
    if confidence is not None:
        try:
            if float(confidence) >= 0.9 and (missing or stale):
                failure.append("confidence_overestimated")
        except (TypeError, ValueError):
            pass
    if not reason and not quality:
        return "inconclusive", sorted(set(success)), sorted(set(failure))
    if "evidence_conflicted" in failure or len(missing) >= 3:
        decision_quality = "poor"
    elif failure:
        decision_quality = "weak"
    elif quality in {"a", "good", "high", "complete"} and reason:
        decision_quality = "good"
    else:
        decision_quality = "acceptable"
    return decision_quality, sorted(set(success)), sorted(set(failure))


def evaluate_result_quality(outcomes: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    usable = []
    for row in outcomes:
        checkpoint = dict(row.get("checkpoint") or {})
        label = str(checkpoint.get("outcome_label") or row.get("outcome_label") or "")
        status = str(checkpoint.get("status") or "")
        if label == "data_unavailable" or status in {"skipped", "unavailable"}:
            continue
        score = checkpoint.get("outcome_score", row.get("outcome_score"))
        try:
            usable.append((float(score), row, checkpoint))
        except (TypeError, ValueError):
            continue
    if not usable:
        return "unavailable", {}
    score, row, checkpoint = usable[-1]
    if score > 0.15:
        quality = "positive"
    elif score < -0.15:
        quality = "negative"
    else:
        quality = "neutral"
    return quality, {
        "score": score,
        "label": checkpoint.get("outcome_label") or row.get("outcome_label"),
        "price_change_pct": checkpoint.get("price_change_pct"),
        "pnl_change_pct": checkpoint.get("pnl_change_pct"),
        "portfolio_change_pct": checkpoint.get("portfolio_change_pct"),
        "reason_ko": checkpoint.get("outcome_reason_ko"),
        "checkpoint_name": checkpoint.get("checkpoint_name"),
    }


def decision_result_matrix(decision_quality: str, result_quality: str) -> str:
    if decision_quality in {"inconclusive"} or result_quality in {"unavailable", "neutral"}:
        return "inconclusive"
    if decision_quality in GOOD_DECISIONS and result_quality == "positive":
        return "good_decision_good_result"
    if decision_quality in GOOD_DECISIONS and result_quality == "negative":
        return "good_decision_bad_result"
    if decision_quality in WEAK_DECISIONS and result_quality == "positive":
        return "bad_decision_good_result"
    if decision_quality in WEAK_DECISIONS and result_quality == "negative":
        return "bad_decision_bad_result"
    return "inconclusive"


def classify_result_reasons(decision: dict[str, Any], result: dict[str, Any]) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failure: list[str] = []
    action = str(decision.get("final_action") or decision.get("ai_action") or "").lower()
    price = result.get("price_change_pct")
    try:
        price_value = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_value = None
    if action in {"wait", "hold"}:
        if bool(decision.get("ai_wait_due_to_data_gap")):
            success.append("wait_due_to_data_gap")
        elif price_value is not None and price_value < 0:
            success.extend(("good_wait", "avoided_loss"))
        elif price_value is not None and price_value > 0:
            failure.extend(("unnecessary_wait", "missed_opportunity"))
    if price_value is not None:
        if price_value > 0:
            success.append("trend_continued")
        elif price_value < 0:
            failure.append("trend_reversed")
    requested = bool(decision.get("order_requested") or decision.get("order_result"))
    submitted = bool(decision.get("submitted"))
    if requested and submitted:
        success.append("execution_clean")
    elif requested and not submitted:
        failure.append("order_not_submitted")
    return sorted(set(success)), sorted(set(failure))


def compose_review_ko(
    decision: dict[str, Any], result: dict[str, Any], decision_quality: str,
    result_quality: str, success_reasons: list[str], failure_reasons: list[str],
) -> dict[str, str]:
    action_names = {
        "wait": "대기", "hold": "보유", "buy": "매수", "add": "추가 매수",
        "sell": "매도", "reduce": "축소", "take_profit": "익절",
        "stop_loss": "손절", "rotate": "교체",
    }
    quality_names = {"good": "좋음", "acceptable": "타당", "weak": "개선 필요", "poor": "취약", "inconclusive": "판단 불가"}
    result_names = {"positive": "긍정적", "neutral": "중립", "negative": "부정적", "unavailable": "확인 불가"}
    action = str(decision.get("final_action") or decision.get("ai_action") or "").lower()
    reason = str(decision.get("final_reason_ko") or decision.get("ai_reason_ko") or "").strip()
    result_reason = str(result.get("reason_ko") or "").strip()
    if not reason:
        reason = "당시 판단 근거가 충분히 구조화되어 기록되지 않았습니다."
    if not result_reason:
        result_reason = "확인 가능한 checkpoint 결과만 사용했으며 추가 결과는 아직 없거나 불충분합니다."
    went_well = " · ".join({
        "evidence_aligned": "당시 근거가 기록됨",
        "good_wait": "대기 판단과 이후 하락이 일치",
        "avoided_loss": "추가 하락 구간 진입을 피함",
        "execution_clean": "주문 처리 기록이 일관됨",
        "trend_continued": "관찰 구간의 상승 흐름 확인",
        "wait_due_to_data_gap": "데이터 부족을 명시하고 대기",
    }.get(code, "확인된 긍정 근거") for code in success_reasons) or "확인된 긍정 근거가 아직 충분하지 않습니다."
    went_wrong = " · ".join({
        "insufficient_data": "당시 핵심 데이터가 부족함",
        "stale_data": "일부 데이터가 오래됨",
        "confidence_overestimated": "불충분한 데이터에 비해 확신이 높음",
        "teacher_disagreement": "교사 AI와 판단이 달랐음",
        "unnecessary_wait": "대기 중 상승 기회가 발생함",
        "missed_opportunity": "관찰 구간의 상승 기회를 놓침",
        "order_not_submitted": "주문 요청과 제출 기록이 이어지지 않음",
        "trend_reversed": "관찰 구간에서 가격이 하락함",
    }.get(code, "추가 검토가 필요한 근거") for code in failure_reasons) or "명확한 개선 원인이 확인되지 않았습니다."
    return {
        "what_went_well_ko": went_well,
        "what_went_wrong_ko": went_wrong,
        "what_was_unknown_ko": "복기는 당시 기록과 checkpoint 결과만 사용하며 기록되지 않은 시장 원인은 단정하지 않습니다.",
        "lesson_ko": f"{action_names.get(action, '판단')} 판단은 판단 품질 {quality_names.get(decision_quality, '확인 필요')}, 결과 품질 {result_names.get(result_quality, '확인 필요')}으로 분리해 학습합니다.",
        "decision_summary_ko": f"{action_names.get(action, '확인 필요')} 판단 · {reason}",
        "result_summary_ko": result_reason,
        "review_summary_ko": f"판단 품질은 {quality_names.get(decision_quality, '확인 필요')}, 실제 결과는 {result_names.get(result_quality, '확인 필요')}으로 평가했습니다.",
    }
