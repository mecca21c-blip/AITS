from __future__ import annotations

from typing import Any


def build_data_governance_view_model(snapshot: dict[str, Any]) -> dict[str, Any]:
    disk = dict(snapshot.get("disk") or {})
    catalog = dict(snapshot.get("catalog") or {})
    status = str(disk.get("status") or "normal")
    status_ko = {"normal": "정상", "watch": "관찰 필요", "warning": "공간 확인 필요", "critical": "공간 부족", "blocked": "관리 작업 차단"}.get(status, "확인 필요")
    total_mb = float(disk.get("total_data_size_bytes") or 0) / (1024 * 1024)
    free_gb = float(disk.get("free_disk_bytes") or 0) / (1024 * 1024 * 1024)
    return {
        "schema": "aits_data_governance_user_view.v1",
        "headline": f"데이터 상태 · {status_ko}",
        "summary": f"AITS 데이터 {total_mb:.1f}MB · 여유 디스크 {free_gb:.1f}GB",
        "source_notice": "원본 판단 기록은 자동으로 삭제되지 않습니다.",
        "backup_notice": "최근 백업이 없습니다." if not snapshot.get("last_backup_at") else f"최근 백업 · {snapshot['last_backup_at']}",
        "archive_notice": "오래된 기록은 검증 후 압축 보관할 수 있습니다.",
        "catalog_rows": [
            {"name": row.get("display_name_ko"), "category": row.get("category"), "status": "정상" if row.get("valid") else "아직 없음", "size_bytes": row.get("size_bytes"), "records": row.get("record_count")}
            for row in catalog.get("entries") or []
        ],
        "heavy_operations_off_only": True,
        "low_resource_mode_compatible": True,
    }
