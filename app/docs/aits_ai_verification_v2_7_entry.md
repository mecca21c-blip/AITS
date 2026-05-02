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

### 10.7 AIShadowStats 로그

AI shadow 결과는 누적 성과 파일(`shadow_performance.json`)에 저장되며,
요약 통계는 다음 로그로 출력된다.

```text
[AITS][AIShadowStats] count=... | confirm=... | skip=... | reject=... | override=... | avg_delta=... | applied=...
```

필드 의미:

| 필드        | 의미                                     |
| --------- | -------------------------------------- |
| count     | AI shadow 필드가 포함된 performance record 수 |
| confirm   | suggestion=confirm 누적 수                |
| skip      | suggestion=skip 누적 수                   |
| reject    | suggestion=reject_signal 누적 수          |
| override  | override_* suggestion 누적 수             |
| avg_delta | ai_shadow_delta 평균값                    |
| applied   | 실제 적용된 AI 결과 수. v2.7에서는 항상 0이어야 정상     |

v2.7 기준 정상 예시:

```text
[AITS][AIShadowStats] count=1 | confirm=0 | skip=1 | reject=0 | override=0 | avg_delta=0.000 | applied=0
```

주의:

* AIShadowStats는 관측용 로그다.
* confidence에 반영하지 않는다.
* final action에 반영하지 않는다.
* applied 값은 v2.7 단계에서 반드시 0이어야 한다.

---

### 10.8 AIShadowPerformance 로그

AI shadow 성과는 `shadow_performance.json`의 `p10m`, `p30m`, `p60m` 결과와 AI suggestion 기록을 비교해 관측한다.

로그 형식:

```text
[AITS][AIShadowPerformance] confirm_wr=... | confirm_n=... | reject_wr=... | reject_n=... | avg_delta_effect=... | sample=...
```

필드 의미:

| 필드               | 의미                                    |
| ---------------- | ------------------------------------- |
| confirm_wr       | suggestion=confirm 레코드의 winrate       |
| confirm_n        | confirm 평가 가능 샘플 수                    |
| reject_wr        | suggestion=reject_signal 레코드의 winrate |
| reject_n         | reject_signal 평가 가능 샘플 수              |
| avg_delta_effect | shadow_delta가 수익 방향과 얼마나 일치했는지 보는 관측값 |
| sample           | delta effect 계산에 사용된 평가 가능 샘플 수       |

v2.7 기준 정상 예시:

```text
[AITS][AIShadowPerformance] confirm_wr=0.000 | confirm_n=0 | reject_wr=0.000 | reject_n=0 | avg_delta_effect=0.000 | sample=0
```

주의:

* sample=0은 초기 단계에서 정상이다.
* p10m/p30m/p60m 중 평가 가능한 값이 없으면 성과 샘플에서 제외한다.
* win 판정은 p10m/p30m/p60m 평균이 0보다 큰 경우로 본다.
* 이 로그는 관측용이며 confidence/action/order에 반영하지 않는다.
* v2.7에서는 applied=False 및 submitted=0을 유지한다.

향후 확장:

* confirm_wr가 충분한 샘플에서 높게 유지될 때만 confidence 반영 검토
* reject_signal의 성과가 누적되면 위험 회피 weight 설계 가능
* avg_delta_effect가 양수로 안정화될 때만 v2.8 진입 검토

---

### 10.9 AIMicroAdjust 로그

AIMicroAdjust는 AI shadow 성과를 기반으로 confidence에 미세 반영할 가능성을 미리 계산하는 로그다.

v2.7 기준에서는 실제 confidence에 반영하지 않는다.

로그 형식:

```text
[AITS][AIMicroAdjust] delta=... | reason=... | base_conf=... | shadow_conf=... | applied=False
```

필드 의미:

| 필드          | 의미                               |
| ----------- | -------------------------------- |
| delta       | AI 성과 기반 micro confidence 후보값    |
| reason      | micro delta 산출 사유                |
| base_conf   | 기존 confidence 기준값                |
| shadow_conf | base_conf + delta를 가정한 preview 값 |
| applied     | 실제 반영 여부. v2.7에서는 항상 False       |

v2.7 기준 정책:

* 최소 평가 샘플: 10
* 최대 delta: ±0.01
* sample 부족 시 delta=0.0000
* no_effect 상태는 정상
* 실제 confidence에는 더하지 않는다
* RouterSummary confidence 값은 기존 로직 값을 유지한다

정상 예시:

```text
[AITS][AIMicroAdjust] delta=0.0000 | reason=no_effect | base_conf=0.0000 | shadow_conf=0.0000 | applied=False
```

주의:

* AIMicroAdjust는 적용이 아니라 preview다.
* v2.7에서는 confidence/action/order에 영향이 없어야 한다.
* applied=False가 유지되어야 한다.
* submitted=0이 유지되어야 한다.
* v2.8 진입 전까지 delta는 관측값으로만 사용한다.

향후 v2.8 검토 조건:

* AIShadowPerformance sample >= 10
* confirm_wr 또는 reject_wr이 유의미하게 안정화
* avg_delta_effect가 양수로 안정화
* max_delta=0.01 제한 유지

---

## END (Shadow Delta Section)

---

## END

---

## 11. v2.7 상태 스냅샷 (Freeze Point)

이 시점의 AITS AI Verification 상태는 다음과 같이 고정된다.

### 11.1 시스템 상태

- AI verification: 활성 (observe-only)
- shadow delta: 계산됨 (반영되지 않음)
- AI suggestion: 기록됨
- API 호출: 가능 (live-once 제한)
- 주문 영향: 없음
- applied: 항상 False
- submitted: 항상 0

---

### 11.2 로그 체계

현재 활성 로그:

- `[AITS][AIVerification]`
- `[AITS][AIVerificationDetail]`
- `[AITS][AIVerificationShadowDelta]`
- `[AITS][AIVerificationWeight]`
- `[AITS][RouterSummaryAI]`
- `[AITS][AIShadowStats]`
- `[AITS][AIShadowPerformance]`

---

### 11.3 데이터 축적 구조

- shadow_performance.json:
  - signal_action
  - signal_confidence
  - p10m / p30m / p60m
  - ai_suggestion
  - ai_reason
  - ai_shadow_delta
  - ai_shadow_policy
  - ai_applied

---

### 11.4 안전 상태

다음 조건이 유지되는 한 시스템은 안전하다:

applied=False
submitted=0
OrderAdapter mode=disabled

---

### 11.5 v2.8 진입 조건

다음 조건이 충족되면 v2.8로 진입한다:

- shadow_performance 데이터 ≥ 50 샘플
- confirm_wr / reject_wr 유의미한 값 도출
- avg_delta_effect 안정화

---

### 11.6 v2.8 목표

- shadow_delta → confidence 일부 반영 (≤ 0.01)
- suggestion 기반 weight 실험
- AI 영향 제한적 적용

---

## END (v2.7 Snapshot)
