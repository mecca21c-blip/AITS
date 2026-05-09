from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any


ALLOWED_SUGGESTIONS = {"confirm", "reject", "skip"}
ALLOWED_NEXT_ACTIONS = {"buy", "sell", "hold", "wait", "watch", "reduce", "remove"}
REQUIRED_FIELDS = [
    "suggestion",
    "confidence",
    "briefing",
    "evidence",
    "next_action",
    "pool_action",
    "scenario",
    "eta",
    "suggestion_only",
    "applied_to_action",
    "applied",
]


@dataclass
class AIResponseSchemaValidationResult:
    valid: bool
    missing_fields: list
    invalid_fields: list
    warnings: list
    normalized: dict
    metadata: dict = field(default_factory=dict)


class AIResponseSchemaValidator:
    """Validates and normalizes AI shadow responses without applying actions."""

    def validate(self, response: dict) -> AIResponseSchemaValidationResult:
        payload = dict(response or {}) if isinstance(response, dict) else {}
        missing_fields = [field for field in REQUIRED_FIELDS if field not in payload]
        invalid_fields: list[str] = []
        warnings: list[str] = []
        normalized = dict(payload)

        suggestion = str(payload.get("suggestion") or "skip").strip().lower()
        if suggestion not in ALLOWED_SUGGESTIONS:
            invalid_fields.append("suggestion")
            suggestion = "skip"
        normalized["suggestion"] = suggestion

        next_action = str(payload.get("next_action") or "wait").strip().lower()
        if next_action not in ALLOWED_NEXT_ACTIONS:
            invalid_fields.append("next_action")
            next_action = "wait"
        normalized["next_action"] = next_action

        normalized["confidence"] = self._clamp_confidence(
            payload.get("confidence"),
            invalid_fields,
            warnings,
        )
        normalized["briefing"] = str(payload.get("briefing") or "")
        evidence = payload.get("evidence")
        if isinstance(evidence, list):
            normalized["evidence"] = list(evidence)
        elif evidence in (None, ""):
            normalized["evidence"] = []
            warnings.append("evidence_empty")
        else:
            normalized["evidence"] = [evidence]
            warnings.append("evidence_normalized_to_list")

        normalized["pool_action"] = (
            dict(payload.get("pool_action")) if isinstance(payload.get("pool_action"), dict) else {}
        )
        normalized["scenario"] = (
            dict(payload.get("scenario")) if isinstance(payload.get("scenario"), dict) else {}
        )
        normalized["eta"] = dict(payload.get("eta")) if isinstance(payload.get("eta"), dict) else {}
        if not isinstance(payload.get("scenario"), dict):
            warnings.append("scenario_normalized_to_dict")
        if not isinstance(payload.get("eta"), dict):
            warnings.append("eta_normalized_to_dict")

        normalized["suggestion_only"] = True
        normalized["applied_to_action"] = False
        normalized["applied"] = False
        normalized["real_order"] = False
        normalized["submitted"] = 0
        normalized["shadow_only"] = True

        valid = not bool(invalid_fields)
        result = AIResponseSchemaValidationResult(
            valid=valid,
            missing_fields=missing_fields,
            invalid_fields=invalid_fields,
            warnings=warnings,
            normalized=normalized,
            metadata={
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
            },
        )
        try:
            logging.getLogger("aits").info(
                "[AITS][AIResponseSchema] schema_validated | valid=%s | missing=%s | invalid=%s",
                result.valid,
                len(result.missing_fields),
                len(result.invalid_fields),
            )
        except Exception:
            pass
        return result

    def _clamp_confidence(
        self,
        value: Any,
        invalid_fields: list,
        warnings: list,
    ) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            invalid_fields.append("confidence")
            return 0.0
        if confidence < 0.0:
            warnings.append("confidence_clamped_low")
            return 0.0
        if confidence > 1.0:
            warnings.append("confidence_clamped_high")
            return 1.0
        return confidence


def build_sample_schema_validation_result() -> AIResponseSchemaValidationResult:
    return AIResponseSchemaValidator().validate(
        {
            "suggestion": "confirm",
            "confidence": 0.72,
            "briefing": "sample",
            "evidence": ["sample"],
            "next_action": "watch",
            "pool_action": {"action": "watch"},
            "scenario": {"name": "sideways_watch"},
            "eta": {"remaining_minutes": 30},
            "suggestion_only": True,
            "applied_to_action": False,
            "applied": False,
        }
    )


__all__ = [
    "AIResponseSchemaValidationResult",
    "AIResponseSchemaValidator",
    "build_sample_schema_validation_result",
]
