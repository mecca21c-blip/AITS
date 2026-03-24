from __future__ import annotations

"""
KMTS-v3 UI 엔트리포인트 래퍼 모듈.

- run.py 에서 이 모듈의 main()만 호출한다.
- 실제 로그인/자동로그인/메인 윈도우 생성 로직은
  검증된 기존 구현인 app.ui.app_gui.main()에 그대로 맡긴다.
- 따라서 동작은 KMTS-v2.3 시절과 100% 동일해야 한다.
"""

from app.ui.app_gui import main as _legacy_main


def main(root_dir: str, data_dir: str) -> None:
    """
    KMTS-v3 UI 진입 함수.

    - 여기서는 아무 추가 로직 없이, 기존 app_gui.main()만 호출한다.
    - 로그인창 노출/자동로그인 여부는 전적으로 app_gui.main()의
      설정값(saved_id, auto_login 등)에 따라 결정된다.
    """
    _legacy_main(root_dir=root_dir, data_dir=data_dir)
