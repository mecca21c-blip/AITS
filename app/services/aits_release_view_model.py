from __future__ import annotations

from typing import Any


def build_release_view_model(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "aits_release_operations_user_view.v1",
        "headline": f"AITS {snapshot.get('app_version', '버전 확인 필요')} · {snapshot.get('channel_ko', '릴리스 후보')}",
        "install_type": snapshot.get("install_type_ko", "개발 환경"),
        "data_location": snapshot.get("data_root", "확인 필요"),
        "backup_location": snapshot.get("backup_root", "확인 필요"),
        "schema_status": "호환됨" if snapshot.get("schema_compatible") else "확인 필요",
        "low_resource_status": "저사양 노트북 기본 설정 사용",
        "update_status": "검증된 업데이트 패키지를 사용자가 직접 선택해 적용합니다.",
        "first_run_notice": "항상 OFF 상태로 시작하며 자동 거래를 시작하지 않습니다.",
        "operation_notice": "원본 데이터는 삭제되지 않으며 API 키와 민감정보는 포함되지 않습니다.",
        "advanced_manifest_hidden": True,
    }
