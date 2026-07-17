from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any


class AITSDiskHealth:
    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)

    def inspect(self, policy: dict[str, Any] | None = None) -> dict[str, Any]:
        policy = dict(policy or {})
        total_size = 0
        if self.data_root.exists():
            for path in self.data_root.rglob("*"):
                try:
                    if path.is_file():
                        total_size += path.stat().st_size
                except OSError:
                    continue
        usage = shutil.disk_usage(self.data_root if self.data_root.exists() else Path.cwd())
        limit = max(1, int(policy.get("total_data_limit_mb") or 10_240)) * 1024 * 1024
        pct = total_size / limit * 100.0
        free_mb = usage.free / (1024 * 1024)
        critical = float(policy.get("critical_threshold_pct") or 95)
        warning = float(policy.get("warning_threshold_pct") or 80)
        minimum = float(policy.get("minimum_free_disk_mb") or 2_048)
        status = "critical" if pct >= critical or free_mb < minimum else "warning" if pct >= warning else "normal"
        return {
            "schema": "aits_disk_health.v1", "status": status,
            "total_data_size_bytes": total_size, "free_disk_bytes": usage.free,
            "quota_usage_pct": round(pct, 3), "source_auto_delete_triggered": False,
            "champion_delete_triggered": False,
            "recommended_action": "backup_or_archive_plan" if status != "normal" else "none",
        }
