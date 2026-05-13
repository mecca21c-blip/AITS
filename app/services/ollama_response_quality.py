from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ai_response_parser import AIResponseParser
from app.services.ai_response_quality_score import AIResponseQualityScorer
from app.services.ai_response_recovery import AIResponseRecovery
from app.services.ai_response_schema_validator import AIResponseSchemaValidator


def _metadata() -> dict:
    return {
        "provider": "ollama",
        "submitted": 0,
        "real_order": False,
        "shadow_only": True,
        "suggestion_only": True,
        "applied": False,
        "applied_to_action": False,
        "inference_only": True,
    }


@dataclass
class OllamaResponseQualityResult:
    parsed_valid: bool
    schema_valid: bool
    quality_score: float
    recovery_used: bool
    warnings: list
    metadata: dict = field(default_factory=_metadata)


class OllamaResponseQualityChecker:
    """Evaluates local Ollama response structure without storing raw text."""

    def check(self, raw_text: str, provider: str = "ollama") -> OllamaResponseQualityResult:
        recovery = AIResponseRecovery().recover_json_text(raw_text)
        parse_text = recovery.recovered_text if (recovery.raw_valid or recovery.recovered) else raw_text
        parsed = AIResponseParser().parse_json_response(parse_text, provider=provider)
        shadow_record = parsed.to_shadow_record()
        shadow_record.update(
            {
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
            }
        )
        validation = AIResponseSchemaValidator().validate(shadow_record)
        score = AIResponseQualityScorer().score(shadow_record, validation)
        warnings = list(validation.warnings or []) + list(score.warnings or [])
        if recovery.error_type:
            warnings.append(recovery.error_type)
        metadata = _metadata()
        metadata.update(
            {
                "provider": provider,
                "recovery_error_type": recovery.error_type,
                "raw_valid": recovery.raw_valid,
            }
        )
        return OllamaResponseQualityResult(
            parsed_valid=bool(parsed.valid),
            schema_valid=bool(validation.valid),
            quality_score=float(score.quality_score),
            recovery_used=bool(recovery.recovered),
            warnings=list(dict.fromkeys(warnings)),
            metadata=metadata,
        )


def build_sample_ollama_response_quality() -> OllamaResponseQualityResult:
    sample = """{"suggestion":"confirm","confidence":0.72,"briefing":"sample","evidence":["sample"],"next_action":"watch","watch_minutes":30,"exit_plan":{"mode":"shadow_only"},"prediction":{"direction":"neutral"},"pool_action":{"action":"keep"},"state_transition":{"from":"idle","to":"watching"},"eta":{"remaining_minutes":30},"scenario":{"name":"sample"},"price_plan":{"entry":"wait"},"ai_score":{"total":72},"briefing_detail":{"summary":"sample"},"suggestion_only":true,"applied_to_action":false,"applied":false,"submitted":0,"real_order":false}"""
    return OllamaResponseQualityChecker().check(sample)


__all__ = [
    "OllamaResponseQualityResult",
    "OllamaResponseQualityChecker",
    "build_sample_ollama_response_quality",
]
