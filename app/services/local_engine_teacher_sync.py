from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AITSLocalEngineTeacherSync:
    SCHEMA = "aits_local_engine_teacher_sync_state.v1"
    STATES = {
        "teacher_not_connected", "teacher_connected", "collecting_recent_data",
        "enough_recent_data", "training_challenger", "evaluating",
        "promotion_ready", "completed", "blocked",
    }

    @classmethod
    def inspect(
        cls,
        *,
        provider: str = "",
        required: bool = False,
        recent_data_count: int = 0,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized = str(provider or "").lower()
        connected = normalized in {"openai", "gpt", "gemini"}
        if not connected:
            status = "teacher_not_connected"
        elif recent_data_count >= 25:
            status = "enough_recent_data"
        else:
            status = "collecting_recent_data"
        return {
            "schema": cls.SCHEMA,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "teacher_sync_required": bool(required),
            "teacher_sync_reasons": list(reasons or []),
            "teacher_provider": normalized if connected else None,
            "provider_ssot": "strategy.ai_provider",
            "recent_data_count": int(recent_data_count),
            "retraining_ready": connected and recent_data_count >= 25,
            "recovery_evaluation_ready": True,
            "authority_expansion_performed": False,
            "user_message_ko": (
                "LOCAL_ENGINE이 최근 시장 적응력을 다시 학습하려면 GPT 또는 Gemini 교사 연결이 필요합니다."
                if required and not connected else ""
            ),
        }
