# AITS Decision Router v2.6 — AI Verification Phase (SSOT)

## 1. 목적

AI Verification Phase는 **의사결정 개입이 아닌 “관측(Observer)” 역할**이다.

절대 원칙:

- AI는 주문을 실행하지 않는다
- AI는 final action을 변경하지 않는다
- AI는 confidence를 변경하지 않는다 (현재 단계)
- AI는 suggestion만 기록한다
- 모든 결과는 applied=False 유지

---

## 2. 전체 흐름

```

Rule Engine
→ Decision Router (passthrough)
→ AI Verification (Observer)
→ Risk Guard
→ Execution Bridge
→ Order Service

```

현재 상태:
- final = passthrough 유지
- OrderAdapter mode=disabled
- submitted=0

---

## 3. Provider 구조

지원 provider:

- local (기본)
- openai
- gemini

선택 경로:

```

strategy.ai_provider
→ orchestrator meta 주입
→ DecisionRouter raw/meta 전달
→ provider_source 로그
→ provider_route 진입

```

---

## 4. Verifier 구조

Orchestrator에서 verifier pool 생성:

```

local → LocalProvider
openai → AIEngineProvider (조건부 생성)
gemini → AIEngineProvider (조건부 생성)

```

선택 로그:

```

[AITS][Orchestrator] verifier_select | provider=... | selected=...

```

Router 주입:

```

[AITS][AIVerification] verifier_resolved | attached=True | type=...

```

---

## 5. AI Verification 실행 단계

### 5.1 진입

```

provider_route | phase=enter

```

### 5.2 verifier lookup

```

provider_route | phase=verifier_lookup

```

### 5.3 readiness 체크

```

[AITS][AIProviderReadiness]

```

가능 상태:

- ready
- api_key_missing
- api_key_invalid
- quota_exceeded
- live_call_disabled

---

## 6. HTTP 호출 단계

로그:

```

[AITS][GeminiHTTP]
[AITS][OpenAIHTTP]

```

포함:

- step=before_request
- status=XXX
- body preview
- error type
- classified_error

---

## 7. Error 분류 체계

Gemini:

- gemini_quota_exceeded
- gemini_api_key_invalid
- gemini_api_key_missing
- gemini_bad_request

OpenAI:

- openai_quota_exceeded
- openai_api_key_invalid
- openai_bad_request

공통:

- *_verifier_error:RuntimeError

---

## 8. Suggestion 처리

AI raw → Router 처리:

```

original=confirm → corrected=skip

```

조건:

- 에러 발생 시 무조건 skip
- LocalProvider 사용 시 skip
- unsupported provider 시 skip

---

## 9. Weight (observe-only)

로그:

```

[AITS][AIVerificationWeight]

```

현재 상태:

- delta=0.000 (반영 없음)
- applied=False 유지

---

## 10. Detail 로그

```

[AITS][AIVerificationDetail]

```

포함:

- suggestion
- reason
- risk_note
- raw_preview

---

## 11. RouterSummaryAI

최종 요약:

```

[AITS][RouterSummaryAI]
ai=...
ai_delta=...
ai_reason=...
applied=False

```

개선 사항:

- ai_reason = 실제 API 실패 reason 반영
- 예:
  - gemini_quota_exceeded:error
  - openai_api_key_invalid:error

---

## 12. Safety 보장

항상 유지:

```

final action 변경 없음
confidence 변경 없음
OrderAdapter disabled
submitted=0
buy_order_request 없음
sell_order_request 없음

```

---

## 13. 현재 상태 요약

AI Verification Phase는:

- 완전한 Observer
- 완전한 로그 기반 분석 도구
- 실거래 영향 0

---

## 14. 다음 단계 (v2.7+)

향후 확장:

1. confidence weight 적용 (조건부)
2. 특정 suggestion만 soft override 허용
3. risk_note 활용 강화
4. multi-AI voting 구조

단, 반드시 단계별 적용:

```

observe → shadow → dry-run → limited apply → live

```

---

## END
