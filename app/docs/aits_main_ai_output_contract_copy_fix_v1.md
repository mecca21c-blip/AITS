# AITS Main AI Output Contract Copy Fix v1

## 1. Goal

메인 화면의 AI 판단/브리핑/근거/다음행동/ETA/confidence 문구가 Basic 계산 결과나 fallback을 AI 판단처럼 보이게 만드는 문제를 줄인다.

이번 변경은 UI copy와 display contract 정리만 수행한다. Router, Execution, Order, RiskGuard, provider 호출, 실거래 로직은 수정하지 않는다.

## 2. 기존 문제

UI-AUDIT-01에서 확인된 문제는 다음과 같다.

- AI Output Contract가 없을 때도 `AI 판단`, `AI 점수`, `AI 시나리오`, `신뢰도`, `ETA`, `다음행동` 같은 강한 표현이 노출될 수 있었다.
- Basic Engine 계산값과 fallback 표시가 AI Engine 판단처럼 보일 수 있었다.
- `다음행동` 표현이 주문 실행 지시처럼 읽힐 여지가 있었다.
- detail popup 기본값이 `AI 기본값`, `신뢰도 55%`, `진입 전 관찰 시나리오`처럼 과신을 유도할 수 있었다.

## 3. AI Output Contract 있음/없음 구분 정책

메인 화면은 `aits_ai_output_contract.v1` 형태의 normalized contract가 있고 `available=True`일 때만 AI 판단 계열 표현을 사용할 수 있다.

AI Output Contract가 있으면:

- AI 판단/AI 점수/AI 운용 시나리오 표현 사용 가능.
- 단, preview-only이며 Router/RiskGuard 검증 전 주문 실행 신호가 아님을 유지한다.

AI Output Contract가 없으면:

- `AI 판단 없음`
- `계산 기반 상태`
- `Basic Engine 계산 기반 참고`
- `주문 신호 아님`
- `AI 확신도 없음`
- `AI 예상 시간 없음`

으로 낮춰 표시한다.

## 4. Basic/fallback 표시 정책

Basic/fallback 상태는 AI Engine의 판단이 아니라 계산 기반 참고 정보로 표시한다.

변경 후 Basic/fallback 표시 예:

- `계산 기반 상태: AI 판단 없음 · 관망 참고`
- `Basic Preview ... 주문 신호 아님`
- `다음 관찰 항목`
- `거래대금 변화 · 추세 전환 · AI 응답 수신 여부`
- `AI Output Contract가 없으면 예상 시간은 표시하지 않습니다.`

## 5. 변경 파일

- `app/ui/app_gui.py`
- `app/docs/aits_main_ai_output_contract_copy_fix_v1.md`

`app/ui/tabs/config_tabs.py`는 분석 대상이었지만 이번 Goal에서는 수정하지 않았다.

## 6. 변경 문구 예시

메인 Intent fallback:

- Before: AI 판단 대기, 행동 조건, 전환 후보 등 강한 표현 혼재
- After: 계산 기반 상태, 다음 관찰 항목, 상태 전환 기준

대시보드 판단 배지:

- Before: contract가 없어도 AI 판단: BUY/SELL/STAY처럼 보일 수 있음
- After: contract가 없으면 계산 기반 상태: 관망 참고 · 주문 신호 아님

상세 팝업:

- Before: AI 판단, 판단 근거, AI 점수, AI 시나리오, 유지 예상 / ETA, 기준: AI 기본값
- After: 상태 판단, 근거 요약, 계산 점수, 관찰 시나리오, 예상 시간, 기준: 계산 기반 참고

## 7. Router/Execution 미변경 확인

이번 변경은 UI label/copy와 display helper에 한정된다.

수정하지 않은 계층:

- `app/services/decision_router.py`
- `app/services/aits_orchestrator.py`
- `app/services/execution_bridge.py`
- `app/services/order_adapter.py`
- `app/services/order_service.py`
- Risk Guard 계층

## 8. Safety

- 실거래 동작 변경 없음.
- 주문 action 결정 로직 변경 없음.
- submitted/order/live_trade 관련 로직 변경 없음.
- AI provider 호출 로직 변경 없음.
- OpenAI/Gemini API 호출 추가 없음.
- Local AI trainer 자동 실행 없음.
- PyInstaller/package build 실행 없음.
- requirements 변경 없음.

## 9. 검증 결과

검증 항목:

- `python -m py_compile app/ui/app_gui.py`
- `python run.py --headless` 개발 모드 startup smoke
- 금지 계층 diff 확인
- requirements diff 확인

결과:

- `app/ui/app_gui.py` py_compile 통과.
- `run.py --headless` startup smoke 통과.
- smoke 로그에서 `OrderAdapterResult(mode=disabled, submitted=0, blocked=0, failed=0, skipped=1)` 확인.
- requirements diff 없음.
- Router/Execution/Order 관련 금지 계층 diff 없음.
- PyInstaller build 및 packaged exe 실행 없음.

## 10. 남은 이슈

- `config_tabs.py`에는 아직 전략/TP-SL/AI 판단 모드 문구가 남아 있다. 이는 `UI-SAFETY-01`에서 별도 정리하는 것이 안전하다.
- 메인 화면의 일부 내부 프롬프트/로그/legacy helper에는 `AI 판단` 문자열이 남아 있다. 사용자가 보는 표면과 내부 contract/prompt를 분리해서 후속 정리해야 한다.
- 실제 화면 시각 검증은 사용자 스크린샷 또는 별도 UI smoke Goal에서 이어가는 것이 좋다.
