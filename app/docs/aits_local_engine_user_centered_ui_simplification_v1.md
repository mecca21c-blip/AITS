# LOCAL_ENGINE 사용자 중심 운영 UI V1

## 목적

LOCAL_ENGINE 운영 화면은 Authority, Capability, 모델 registry, 교사 AI 및 학습 상태의 기존 SSOT를 읽어 일반 사용자가 이해할 수 있는 한국어 상태로 표현한다. 이 화면은 판단 권한을 계산하지 않으며 주문 또는 최종 판단 경로에 개입하지 않는다.

## 기본 화면

기본 화면은 다음 다섯 영역만 노출한다.

1. LOCAL_ENGINE 한눈에 보기
2. 현재 가능한 역할
3. 성장 현황
4. 새 모델 안내
5. 지금 필요한 작업

Level은 한국어 역할과 함께 표시한다. 종합 상태는 runtime/model integrity를 뜻하며, 기능별 상태는 개별 task의 학습 수준을 뜻한다. 따라서 전체 상태가 안정이어도 일부 기능은 학습 중 또는 데이터 부족일 수 있다.

## 새 모델과 Level 승격

- `새 모델 적용`은 동일 Level에서 현재 사용 모델만 교체한다. 판단 권한은 변하지 않는다.
- `Level 승격 승인`은 판단 권한 확대 절차다. 실제 승격 후보가 있고 사용자가 승인할 때만 표시·실행할 수 있다.
- 이전 모델 복구는 rollback 가능한 상태에서만 상세 관리에 표시한다.
- 자동 승격은 허용하지 않는다.

## 모델 갱신 상태

backend 상태와 모델 비교 결과를 snapshot 계층에서 결합해 사용자 문구를 만든다. 예를 들어 `evaluating_challenger` 상태에서 비교가 완료되고 새 모델이 우수하면 `모델 갱신 · 새 모델 평가 완료`로 표시한다. raw 상태 문자열은 화면에 노출하지 않는다.

## 상세 관리

다음 기능은 기본적으로 접혀 있다.

- 기술 성능 지표
- GPT/Gemini 최신 시장 학습
- OFF 전용 모델 갱신
- Level·판단 권한 관리
- 데이터·복구
- 최근 운영 이력
- 데이터 보관 정책

상태 파일은 친숙한 데이터 이름을 우선 표시하고 원본 파일명은 tooltip에만 제공한다. 원본 후보 판단, 교사 판단, outcome 기록의 삭제·편집 기능은 제공하지 않는다.

## 성능과 안전

- UI snapshot worker가 작은 state/summary 파일과 파일 metadata를 읽는다.
- UI thread에서 JSONL 전체 스캔과 heavy learning을 실행하지 않는다.
- Live ON에서는 모델 갱신 버튼을 비활성화한다.
- 모든 권한·모델 변경은 service action과 확인 dialog를 통과한다.
- `strategy.ai_provider`, Authority state, Capability Matrix, 모델 registry는 기존 SSOT를 유지한다.
- `safe_for_live_decision`, `live_decision_enabled`, `safe_for_live_expansion`은 모두 false로 유지한다.

## Closeout UI 규칙

- 기본 화면의 주요 작업은 새 모델 안내 카드의 `새 모델 적용` 한 개만 사용한다.
- 기본 화면은 학습 날짜 기반 모델 이름을 표시하고 raw model ID는 `모델 성능 자세히`에서만 제공한다.
- 공통설정의 주문 없는 provider 응답 점검은 `AI 연결 진단`으로 표시한다.
- 역할 및 데이터 표의 행 번호는 숨기며 상세 관리 진입 시 첫 행으로 이동한다.
- Level 관련 사용자 문구는 `Lv1 · 학습자`처럼 한국어 역할을 함께 표시한다.
