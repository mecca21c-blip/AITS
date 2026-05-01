# AITS Decision Router — v2.6 완료 선언 및 v2.7 진입 기준

## 1. v2.6 완료 선언

Decision Router v2.6 AI Verification Phase는 다음 조건을 만족하며 완료되었다.

### 완료 기준

- AI Verification = Observer 역할 유지
- applied=False 100% 유지
- final action 변경 없음
- confidence 변경 없음
- OrderAdapter mode=disabled 유지
- submitted=0 유지
- OpenAI / Gemini 실제 호출 경로 검증 완료
- API 실패 reason 명시화 완료
- RouterSummaryAI에 AI 상태 반영 완료

---

## 2. 현재 상태 정의

현재 시스템 상태:

```

AI = 관찰자 (Observer)
Router = 통제자 (Controller)
Rule Engine = 1차 판단자
Execution = 차단 상태

```id="state_v2_6"

---

## 3. v2.7 진입 목적

v2.7의 목표는 다음이다:

> "AI suggestion을 실제 판단에 미세하게 반영하기 위한 준비 단계"

단, 즉시 반영하지 않는다.

---

## 4. v2.7 핵심 개념

### 4.1 Observe → Shadow → Apply 단계 분리

```

v2.6 → Observe only
v2.7 → Shadow influence
v2.8 → Conditional apply
v3.0 → Controlled live apply

```id="phase_model"

---

### 4.2 Shadow Confidence Layer

AI suggestion은 다음 형태로만 반영된다:

- confidence_delta (미세 보정)
- action override 금지
- order 영향 금지

---

## 5. v2.7 진입 허용 조건

다음 조건을 모두 만족해야 한다:

1. API 호출 안정성 확보
2. quota / api_key / http_error 완전 분류
3. RouterSummaryAI 로그 정상 출력
4. AIVerificationDetail 정상 출력
5. AIVerificationWeight 정상 기록
6. 모든 케이스에서 applied=False 유지
7. submitted=0 유지

---

## 6. v2.7에서 절대 금지

절대 하면 안 되는 것:

- final action 변경
- BUY/SELL 직접 유도
- OrderService 호출
- approved_actions 수정
- execution_mode 변경
- UI 연결
- AI 결과를 그대로 신뢰

---

## 7. v2.7 허용 작업

허용:

- confidence delta 계산 (0.0 ~ ±0.05 수준)
- suggestion별 weight 정의
- observe-only shadow 점수 기록
- Router 내부 로그 확장

---

## 8. 설계 원칙

```

AI는 항상 틀릴 수 있다
Router는 항상 보수적으로 행동해야 한다
실거래는 마지막 단계에서만 허용된다

```id="design_principle"

---

## 9. 다음 작업 (v2.7 시작점)

다음 단계:

> 53차: AI suggestion → confidence_delta mapping 설계 (observe-only)

---

## END
