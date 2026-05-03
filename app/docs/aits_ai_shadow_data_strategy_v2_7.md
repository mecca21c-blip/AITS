# AITS v2.7 — AI Shadow 데이터 축적 전략

## 1. 목적

AI shadow 데이터 축적의 목적은 AI suggestion을 실제 매매 판단에 반영하기 전에,
AI 판단이 유효한지 충분한 샘플로 검증하는 것이다.

v2.7에서는 AI 결과를 절대 실제 confidence/action/order에 반영하지 않는다.

---

## 2. 현재 상태

현재 AI 관련 데이터는 `shadow_performance.json`에 다음 필드로 저장된다.

- ai_suggestion
- ai_reason
- ai_shadow_delta
- ai_shadow_policy
- ai_applied

기존 성과 필드:

- p10m
- p30m
- p60m
- signal_action
- signal_confidence
- market_regime
- candidate_count

---

## 3. 샘플 기준

v2.8 진입 전 최소 기준:

| 기준 | 값 |
|------|----|
| 최소 전체 AI shadow sample | 50 |
| 권장 전체 AI shadow sample | 100 |
| confirm 평가 가능 sample | 20 이상 권장 |
| reject_signal 평가 가능 sample | 20 이상 권장 |
| override_* 평가 | v2.7에서는 관측만 |

---

## 4. 평가 타이밍

AI suggestion의 성과는 기존 `p10m`, `p30m`, `p60m` 기준으로 평가한다.

기본 평가 우선순위:

1. p10m: 단기 반응
2. p30m: 중기 안정성
3. p60m: 늦은 추세 확인

v2.7 기본 win 판정:

```text
평가 가능한 p10m/p30m/p60m 평균 > 0 → win
평균 <= 0 → loss
````

---

## 5. suggestion별 평가 방향

### confirm

confirm은 기존 Router 판단을 지지하는 신호다.

평가 기준:

* 이후 수익률 평균이 양수면 긍정
* confirm_wr가 높을수록 confidence boost 가능성 증가

v2.8 후보 조건:

```text
confirm_n >= 20
confirm_wr >= 0.60
```

---

### reject_signal

reject_signal은 기존 신호를 거부하는 신호다.

평가 기준:

* reject 이후 해당 신호의 성과가 나쁘면 긍정
* 즉, reject_signal은 일반 winrate와 반대로 해석할 수 있다

v2.8에서는 우선 관측만 한다.

---

### override_*

override 계열은 v2.7에서 실제 반영하지 않는다.

* override_buy: 0.00 유지
* override_wait: 관측
* override_reduce: 관측
* override_sell: 관측

v2.8 전까지 action override 금지.

---

## 6. infra 실패 데이터 처리

다음 reason은 성과 평가에서 제외한다.

* api_key_missing
* api_key_invalid
* quota_exceeded
* bad_request
* http_error
* live_call_disabled
* verifier_not_implemented
* verifier_error
* unsupported_provider
* empty_response
* local_provider_no_api_call

이유:

* AI 판단 실패가 아니라 호출/환경 실패이기 때문
* confidence 반영에 사용하면 안 됨

---

## 7. 유효 데이터 기준

유효한 AI shadow record 조건:

```text
ai_applied == false
ai_suggestion in [confirm, reject_signal, override_wait, override_reduce, override_sell, skip]
ai_reason does not contain infra failure reason
at least one of p10m/p30m/p60m is numeric
```

---

## 8. v2.8 진입 조건

v2.8은 아래 조건이 충족될 때만 검토한다.

필수:

* 전체 유효 AI shadow sample >= 50
* AIShadowPerformance sample >= 30
* infra failure 비율이 과도하지 않을 것
* submitted=0 안정 검증 유지

권장:

* confirm_n >= 20
* confirm_wr >= 0.60
* avg_delta_effect > 0.00

---

## 9. v2.8에서 허용 가능한 첫 반영

v2.8 첫 반영은 반드시 micro confidence 수준으로 제한한다.

허용:

```text
max_delta = ±0.01
action override = 금지
order 영향 = 금지
applied flag = still False or shadow-applied only
```

금지:

```text
AI가 직접 buy/sell 유도
AI가 approved_actions 변경
AI가 OrderService 호출
AI suggestion만으로 final action 변경
```

---

## 10. 운영 전략

v2.7 운영 방식:

1. local 기본 실행 유지
2. Gemini/OpenAI는 live-once 또는 제한 호출
3. quota 초과 시 skip 처리
4. shadow_performance 데이터 누적
5. AIShadowStats / AIShadowPerformance 로그 관찰
6. 50샘플 이상 쌓이면 v2.8 검토

---

## 11. 판단 원칙

AI는 보조 신호다.

```text
Rule/Router 판단이 우선
AI는 검증자
Shadow 데이터는 신뢰도를 판단하는 근거
실거래 반영은 마지막 단계
```

---

## END

---

검증:

* 파일 생성 확인
* 코드 변경 없음
* git status에서 신규 문서만 확인

완료 보고:

1. 생성 파일 경로
2. 파일 생성 여부
3. 코드 변경 없음 여부
