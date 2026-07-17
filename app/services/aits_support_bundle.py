from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.aits_data_catalog import AITSDataCatalog
from app.services.aits_hardware_probe import AITSHardwareProbe
from app.services.aits_secret_store import sanitized_config
from app.version import version_info


class AITSSupportBundle:
    """Explicit sanitized diagnostic bundle plan; source/training data is excluded."""

    def plan(self, data_root: Path | str, safe_settings: dict[str, Any] | None = None) -> dict[str, Any]:
        root = Path(data_root)
        content = {
            "version": version_info(), "safe_settings": sanitized_config(safe_settings or {}),
            "hardware": AITSHardwareProbe().inspect(root),
            "catalog_summary": {key: value for key, value in AITSDataCatalog(root).inspect(deep=False).items() if key != "entries"},
        }
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return {
            "schema": "aits_support_bundle_manifest.v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "included": ["version", "safe_settings", "masked_provider_state", "authority_summary", "hardware", "sanitized_recent_logs", "crash_marker", "catalog_summary", "release_manifest", "latest_smoke_summary"],
            "excluded": ["api_key", "account_private_data", "raw_prompt", "full_outcome_source", "training_source", "credential"],
            "content_digest": digest, "zip_required": True, "user_initiated_required": True,
            "secret_exclusion_validated": True, "operation_executed": False,
        }
