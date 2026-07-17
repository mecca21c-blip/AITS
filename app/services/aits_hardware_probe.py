from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
from typing import Any


class AITSHardwareProbe:
    def inspect(self, data_root: Path | str) -> dict[str, Any]:
        root = Path(data_root)
        usage = shutil.disk_usage(root if root.exists() else Path.cwd())
        cpu_count = os.cpu_count() or 1
        return {
            "schema": "aits_hardware_probe.v1", "platform": platform.platform(),
            "architecture": platform.machine(), "cpu_count": cpu_count,
            "free_disk_bytes": usage.free, "data_root_writable": root.exists() and os.access(root, os.W_OK),
            "gpu_required": False, "cpu_only_local_engine": True, "external_runtime_required": False,
            "status": "low_resource_recommended" if cpu_count <= 4 else "compatible",
            "changes_order_policy": False,
        }
