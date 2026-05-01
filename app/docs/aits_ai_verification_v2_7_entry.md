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

## 10. v2.7 Shadow Confidence Delta 정책 (Observe-Only)

v2.7에서는 AI suggestion을 실제 판단에 반영하지 않고,
shadow_confidence_delta 형태로만 기록한다.

### 10.1 기본 원칙

- 모든 delta는 observe-only
- final confidence에는 반영하지 않는다
- action 변경 금지
- applied=False 유지

---

### 10.2 suggestion → delta 매핑

| suggestion        | delta  | policy                                |
|------------------|--------|----------------------------------------|
| confirm          | +0.02  | confirm_small_shadow_boost              |
| reject_signal    | -0.04  | reject_signal_shadow_penalty            |
| override_wait    | -0.03  | override_wait_shadow_penalty            |
| override_reduce  | -0.02  | override_reduce_shadow_penalty          |
| override_sell    | -0.04  | override_sell_shadow_penalty            |
| override_buy     | 0.00   | override_buy_blocked_observe_only       |
| skip             | 0.00   | skip_no_shadow_effect                   |
| unknown          | 0.00   | unknown_suggestion_no_shadow_effect     |

---

### 10.3 Infra / API 실패 처리

아래 조건에서는 delta를 강제로 0으로 설정한다:

- api_key_missing
- api_key_invalid
- quota_exceeded
- bad_request
- http_error
- live_call_disabled
- verifier_not_implemented
- verifier_error
- unsupported_provider
- empty_response
- local_provider_no_api_call

결과:

```

delta = 0.000
policy = infra_failure_no_shadow_effect

```id="infra_policy"

---

### 10.4 Local Provider 처리

local provider는 항상:

```

delta = 0.000
policy = local_skip_no_shadow_effect

```id="local_policy"

---

### 10.5 로그 구조

Shadow delta는 다음 로그로 기록된다:

```

[AITS][AIVerificationShadowDelta]

```id="shadow_log"

RouterSummaryAI에는 다음 형태로 포함된다:

```

ai=...
ai_delta=...
ai_reason=...
shadow_delta=...
shadow_policy=...
applied=False

```id="shadow_summary"

---

### 10.6 향후 확장 방향

v2.8 이상에서:

- shadow_delta → confidence 반영 검토
- suggestion별 weight 동적 조정
- multi-AI ensemble 반영 가능

단, 반드시 단계적으로 진행:

```

observe → shadow → partial_apply → guarded_apply → live

```id="shadow_phase"

---

## END (Shadow Delta Section)

---

## END
