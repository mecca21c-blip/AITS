from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class AIResponseRecoveryResult:
    recovered: bool
    raw_valid: bool
    recovered_text: str
    error_type: str | None
    metadata: dict = field(default_factory=dict)


class AIResponseRecovery:
    """Recovers JSON text boundaries without inventing fields."""

    def recover_json_text(self, raw_text: str) -> AIResponseRecoveryResult:
        raw = str(raw_text or "")
        if self._is_json_object(raw):
            return self._result(False, True, raw, None)

        fenced = self._extract_fenced_json(raw)
        if fenced and self._is_json_object(fenced):
            return self._result(True, False, fenced, None)

        sliced = self._extract_object_slice(raw)
        if sliced and self._is_json_object(sliced):
            return self._result(True, False, sliced, None)

        return self._result(False, False, "", "json_recovery_failed")

    def _extract_fenced_json(self, raw: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_object_slice(self, raw: str) -> str:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return ""
        return raw[start : end + 1].strip()

    def _is_json_object(self, text: str) -> bool:
        try:
            payload = json.loads(str(text or ""))
        except Exception:
            return False
        return isinstance(payload, dict)

    def _result(
        self,
        recovered: bool,
        raw_valid: bool,
        recovered_text: str,
        error_type: str | None,
    ) -> AIResponseRecoveryResult:
        return AIResponseRecoveryResult(
            recovered=bool(recovered),
            raw_valid=bool(raw_valid),
            recovered_text=str(recovered_text or ""),
            error_type=error_type,
            metadata={
                "shadow_only": True,
                "suggestion_only": True,
                "applied": False,
                "applied_to_action": False,
                "real_order": False,
                "submitted": 0,
            },
        )


def build_sample_recovery_result() -> AIResponseRecoveryResult:
    return AIResponseRecovery().recover_json_text('```json\n{"suggestion":"confirm"}\n```')


__all__ = [
    "AIResponseRecoveryResult",
    "AIResponseRecovery",
    "build_sample_recovery_result",
]
