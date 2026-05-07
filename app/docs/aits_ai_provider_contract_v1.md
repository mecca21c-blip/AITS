# AITS AI Provider Contract v1

## 1. 목적

AITS AI Provider Contract는 GPT, Gemini, Ollama provider가 반드시 따라야 하는 공통 입출력 계약이다. 이 계약의 목적은 provider를 교체 가능하게 만들면서 AITS Core Engine과 주문 안전 구조를 보호하는 것이다.

핵심 목적은 다음과 같다.

- provider 교체 가능 구조: GPT/Gemini/Ollama를 동일한 방식으로 호출하고 교체할 수 있게 한다.
- AITS Core 보호: provider별 차이를 Core Engine 밖에서 흡수해 내부 운용 구조를 안정적으로 유지한다.
- 동일 입출력 계약: 모든 provider는 같은 context, prompt, response, shadow record 규칙을 따른다.

Provider는 AI 판단 보조 계층이며, 주문 실행 계층이 아니다. 모든 provider 응답은 suggestion-only 흐름으로 제한한다.

## 2. 입력 계약

Provider bridge는 다음 입력을 받는 구조를 기준으로 한다.

```json
{
  "context_dict": {},
  "system_prompt": "...",
  "user_prompt": "...",
  "provider": "gpt",
  "model": "model-name",
  "timeout": 30
}
```

입력 필드 정의는 다음과 같다.

- `context_dict`: `AIContextPack.to_compact_dict()` 결과
- `system_prompt`: `AIPromptBuilder.build_system_prompt()` 결과
- `user_prompt`: `AIPromptBuilder.build_user_prompt(context_dict)` 결과
- `provider`: `gpt`, `gemini`, `ollama` 중 하나
- `model`: 실제 사용할 provider별 모델명
- `timeout`: provider 응답 제한 시간

입력에는 API key, secret, token, credential을 포함하지 않는다.

## 3. 출력 계약

Provider bridge는 다음 3단계 출력을 유지한다.

```json
{
  "raw_text": "...",
  "parsed_response": {},
  "shadow_record": {}
}
```

출력 필드 정의는 다음과 같다.

- `raw_text`: provider가 반환한 원문 텍스트. 저장과 로그 출력은 제한한다.
- `parsed_response`: `AIResponseParser.parse_json_response()` 결과
- `shadow_record`: `AIParsedResponse.to_shadow_record()` 결과

운영 로그에는 raw full response를 출력하지 않는다. 필요한 경우에도 parsed 요약과 안전 필드만 남긴다.

## 4. 필수 safety

모든 provider는 아래 safety 계약을 반드시 지켜야 한다.

```json
{
  "suggestion_only": true,
  "applied_to_action": false,
  "applied": false
}
```

필수 safety 원칙은 다음과 같다.

- `suggestion_only=True`
- `applied_to_action=False`
- `applied=False`
- no direct order
- provider는 주문 실행, 주문 제출, OrderAdapter 호출을 수행하지 않음
- AI 응답은 DecisionRouter shadow 기록 또는 UI 검토 자료로만 사용

## 5. 응답 JSON 필드

Provider는 JSON ONLY 응답을 반환해야 한다. 응답 JSON의 필수 필드는 다음 15개이다.

```json
{
  "suggestion": "confirm",
  "confidence": 0.71,
  "briefing": "...",
  "evidence": [],
  "next_action": "watch",
  "watch_minutes": 30,
  "exit_plan": {},
  "prediction": {},
  "pool_action": {},
  "state_transition": {},
  "eta": {},
  "scenario": {},
  "price_plan": {},
  "ai_score": {},
  "briefing_detail": {}
}
```

필드 정의는 다음과 같다.

- `suggestion`: `confirm`, `reject`, `skip`
- `confidence`: 0.0에서 1.0 사이의 신뢰도
- `briefing`: UI 요약 브리핑
- `evidence`: 판단 근거 목록
- `next_action`: `buy`, `sell`, `hold`, `wait`, `watch`, `reduce`, `remove`
- `watch_minutes`: 관찰 또는 재평가까지의 시간
- `exit_plan`: 이탈 조건 또는 리스크 해소 계획
- `prediction`: 방향성, 확률, 시나리오 예측
- `pool_action`: 후보군 유지/제외/승격/강등 판단
- `state_transition`: 관리종목 상태 전이 정보
- `eta`: 다음 검토 또는 타이머 정보
- `scenario`: 현재 판단 시나리오
- `price_plan`: 진입, 손절, 목표, 무효화 조건
- `ai_score`: 종합 점수와 하위 점수
- `briefing_detail`: 상세 분석 패널용 구조화 설명

## 6. Provider별 역할

Provider별 역할은 다음과 같이 정의한다.

- GPT: 고급 추론, 긴 context 분석, 복잡한 opportunity cost 판단
- Gemini: 빠른 분석, 요약, 비용 효율적인 보조 판단
- Ollama(Qwen2.5): 로컬 상시 판단, 개인정보 친화적 처리, 저비용 반복 판단

Provider 역할은 다르지만 입출력 계약은 동일하다.

## 7. 실패 처리

Provider bridge는 실패 상황을 안전하게 fallback해야 한다.

처리 대상은 다음과 같다.

- timeout
- invalid json
- auth fail
- model not found
- fallback skip

실패 처리 원칙은 다음과 같다.

- JSON 파싱 실패 시 `suggestion="skip"`으로 정규화
- confidence는 `0.0`
- next_action은 `wait`
- pool_action은 `{"action":"watch","reason":"parse_failed"}` 또는 실패 유형별 안전 기본값
- valid는 `False`
- applied는 항상 `False`
- 실패 원인은 예외 타입 또는 안전한 reason code로만 기록

## 8. 금지 사항

Provider bridge 구현 시 다음을 금지한다.

- key 출력 금지
- raw full response 로그 금지
- raw prompt 전문 로그 금지
- 주문 직접 실행 금지
- OrderAdapter 직접 호출 금지
- provider 응답을 자동 주문으로 변환 금지
- secret, token, credential 저장 또는 출력 금지

Provider는 판단 보조만 수행하며, 주문 실행 권한을 갖지 않는다.

## 9. 다음 구현 순서

다음 구현 순서는 아래와 같다.

```text
1. GPT bridge
2. Gemini bridge
3. Ollama bridge
4. DecisionRouter shadow 연결
```

각 bridge는 이 문서의 입력 계약, 출력 계약, safety 계약, 실패 처리 규칙을 동일하게 따른다. DecisionRouter 연결은 shadow 기록 흐름부터 시작하며, 실제 주문 실행 연결은 이 계약 범위에 포함하지 않는다.
