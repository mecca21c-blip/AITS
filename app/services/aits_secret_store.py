from __future__ import annotations

from typing import Any


SENSITIVE_KEYS = {"access_key", "secret_key", "api_key", "ai_openai_api_key", "ai_gemini_api_key", "password", "token"}


def sanitized_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("<excluded>" if key.lower() in SENSITIVE_KEYS or "secret" in key.lower() else sanitized_config(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized_config(item) for item in value]
    return value


class AITSSecretStore:
    """Windows secure-storage abstraction; existing encrypted store remains the runtime backend."""

    backend = "existing_fernet_store"
    plaintext_allowed = False
    optional_backup_encryption_supported = False

    def inspect(self) -> dict[str, Any]:
        return {
            "schema": "aits_secret_store_contract.v1", "backend": self.backend,
            "plaintext_settings_storage": False, "sanitized_export_ready": True,
            "optional_backup_encryption_supported": self.optional_backup_encryption_supported,
            "encryption_default_enabled": False, "plaintext_fallback_allowed": False,
        }
