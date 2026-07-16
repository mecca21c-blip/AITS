# AITS LOCAL_ENGINE Level Status Operations UI v1

## 목적

AI 정책 센터의 `4. LOCAL_ENGINE 성장·운영` 영역은 LOCAL_ENGINE의 Authority, Health, Capability, 데이터, 모델 및 maintenance 상태를 사용자가 확인하고 안전하게 운영하는 제어판이다. 이 화면은 LOCAL_ENGINE에 최종 판단 권한을 부여하지 않는다.

## 상태 소유권

- Provider 선택은 `strategy.ai_provider`를 그대로 사용한다.
- Level과 Authority는 `local_engine_authority_state`가 소유한다.
- Task Level은 `local_engine_capability_matrix`가 소유한다.
- Health, continuous learning, Teacher Sync 및 model registry의 기존 상태를 읽는다.
- UI는 threshold를 계산하거나 상태 JSON을 직접 수정하지 않는다.

## 공통설정 LOCAL 표시

LOCAL 선택 버튼은 `LOCAL · LvN`과 Level 역할을 표시한다. Tooltip은 Authority, Health, 최종 판단 가능 여부, 외부 교사 확인 필요 여부와 최근 학습 시각을 제공한다. 버튼 클릭은 Provider의 세션 선택만 수행하며 Level을 변경하지 않는다.

## 운영 화면

- 종합 상태: Global/Effective Level, Authority, Health 및 현재 blocker
- Capability Matrix: 11개 task의 Level, 지원 action, Teacher/Outcome 표본과 상태
- 데이터 현황: candidate, outcome, curation, feature, distillation, calibration 요약
- Champion/Challenger: registry의 현재 pointer와 비교 metric
- 권한 작업: 강등, 중지/재개, 승격 승인/거절, 동일 Level Champion 교체, rollback
- Teacher Sync: 현재 Provider를 바꾸지 않고 요청만 기록
- Maintenance: runtime OFF에서만 별도 worker로 실행
- 상태 파일: metadata와 cached summary count만 표시
- 운영 이력: 제한된 최근 event를 한국어로 표시

## 성능 경계

`local_engine_status_snapshot`은 작은 state/summary JSON과 파일 metadata를 사용한다. UI thread에서 candidate/outcome JSONL 전체를 읽지 않는다. 새로고침과 maintenance는 중복 실행 guard를 가지며, hidden 상태에서 주기적 전체 refresh를 수행하지 않는다.

## 안전 계약

- 자동 승격 없음
- 사용자 승인 우회 없음
- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `safe_for_live_expansion=false`
- LOCAL final action 적용 없음
- source candidate/teacher/outcome 삭제·편집 UI 없음
- RiskGuard, LivePreflight, Execution 경로 변경 없음
- Ollama developer-only 및 live auto-generate 비활성 유지

## 상태 파일 작업

원본 source는 삭제·격리 대상이 아니다. 파생 파일 재생성은 OFF-only maintenance 요청으로 연결된다. 손상 파생 파일 격리는 명시적 service allowlist를 거치며, authority snapshot 백업은 별도 snapshots 디렉터리에 생성된다.
