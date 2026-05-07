# AITS Local AI(Ollama) Engine Plan v1

## 1. 목적

AITS Local AI는 기존 GPT/Gemini 기반 AI 판단 구조를 유지하면서, 로컬에서 실행 가능한 보조 AI 엔진을 추가하기 위한 설계이다. Local AI는 Ollama Runtime과 Qwen2.5 7B Instruct Q4 모델을 기준으로 정의한다.

Local AI가 필요한 이유는 다음과 같다.

- 토큰 절약: 반복적인 요약, 후보 해석, 시장 코멘트 생성 등은 로컬 모델에서 처리해 외부 API 사용량을 줄인다.
- Fallback: GPT/Gemini 장애, quota 제한, 네트워크 문제 발생 시 로컬 판단 보조 엔진으로 최소 기능을 유지한다.
- SaaS형 배포: 고객 환경별로 외부 AI 사용 여부를 선택할 수 있게 하고, 로컬 AI 포함 배포 옵션을 제공한다.
- 개인정보/로컬 처리: 민감한 관심종목, 매매 메모, 사용자 전략 context를 외부로 보내지 않고 로컬에서 해석할 수 있다.

## 2. 엔진 구조

### A. 기본엔진

기본엔진은 AITS의 AI 판단 요청을 추상화하는 공통 계층이다. UI 또는 서비스 계층은 특정 AI 공급자를 직접 호출하지 않고, AIEngineProvider를 통해 현재 선택된 provider로 요청을 전달한다.

기본엔진의 책임은 다음과 같다.

- provider 선택
- 공통 request/response 형식 유지
- suggestion-only 원칙 강제
- provider 장애 시 fallback 판단
- UI에 모델 상태와 응답 상태 전달

### B. GPT

GPT는 고성능 추론, 복잡한 시장 해석, 긴 context 기반 분석에 사용하는 외부 AI provider이다. 기존 구조는 변경하지 않는다.

GPT provider는 다음 역할을 유지한다.

- 고난도 reasoning
- 긴 문맥 기반 전략 검토
- 복합 뉴스/시장 해석
- 사용자 질의 응답

### C. Gemini

Gemini는 기존 대체 외부 AI provider로 유지한다. GPT와 동일한 provider 인터페이스를 따르며, 구조와 실행 로직은 변경하지 않는다.

Gemini provider는 다음 역할을 유지한다.

- 외부 AI fallback
- 빠른 요약
- 시장 context 보조 해석
- 멀티 provider 비교 판단

### D. Local AI (Ollama)

Local AI는 Ollama Runtime 위에서 Qwen2.5 7B Instruct Q4를 실행하는 로컬 provider이다. 외부 API 호출 없이 로컬 모델을 사용하며, AITS 내부 판단 흐름에서는 GPT/Gemini와 동일한 provider 후보로 취급한다.

Local AI provider는 직접 주문, 자동 제출, OrderAdapter 제어에 관여하지 않는다. 모든 응답은 suggestion-only로 제한한다.

## 3. Local AI 역할

Local AI는 실시간 주문 실행 엔진이 아니라, context 기반 판단과 제안 생성을 담당하는 보조 엔진이다.

주요 역할은 다음과 같다.

- context 기반 판단: 현재 포지션, watchlist, 관심 섹터, 시장 상태를 읽고 요약 판단을 제공한다.
- 뉴스/시장 해석: 뉴스 headline, 시장 지표, 섹터 흐름을 간단히 해석한다.
- opportunity cost: 현재 후보를 유지할 때의 기회비용과 대체 후보의 상대 매력을 비교한다.
- rotation 보조: 섹터/테마/종목 간 rotation 가능성을 보조적으로 판단한다.
- suggestion 생성: 매수/매도/관망/비중축소/비중확대 등 사람이 검토할 수 있는 제안을 만든다.

## 4. 모델 확정

Local AI 기본 모델은 다음으로 확정한다.

```text
Qwen2.5 7B Instruct Q4
```

선정 이유는 다음과 같다.

- 한국어: 한국어 질의, 국내 종목 메모, 사용자 전략 문맥 처리에 강점이 있다.
- reasoning: 7B급 경량 모델 중 instruction following과 reasoning 균형이 좋다.
- JSON 안정성: provider 공통 응답 형식에 맞춘 structured output 생성에 적합하다.
- CPU 성능: GPU가 없는 로컬 환경에서도 제한적으로 운영 가능하다.
- 경량화: Q4 quantization 기준으로 저장 공간과 메모리 부담을 낮출 수 있다.

## 5. 배포 구조

Local AI는 AITS 애플리케이션 코드와 분리된 runtime 영역에 배치한다. 설치 자동화는 이 문서 범위에 포함하지 않는다.

예상 디렉터리 구조는 다음과 같다.

```text
AITS/
  runtime/
    ollama/
      bin/
      config/
      logs/
    models/
      qwen2.5-7b-instruct-q4/
```

배포 원칙은 다음과 같다.

- `runtime/ollama/`: Ollama 실행 파일, 설정, 로그 위치
- `runtime/models/`: 로컬 모델 파일 또는 모델 캐시 위치
- 애플리케이션 코드는 runtime을 직접 포함하지 않고 provider 설정을 통해 접근
- GPT/Gemini provider 구조와 독립적으로 배치
- 모델 다운로드, 설치, 업데이트 자동화는 후속 단계에서 별도 설계

## 6. 실행 구조

Local AI 실행 흐름은 다음과 같다.

```text
UI
  -> AIEngineProvider
  -> LocalProvider
  -> Ollama Runtime
  -> Qwen2.5 7B Instruct Q4
```

실행 책임은 다음과 같이 나눈다.

- UI: provider 선택, 상태 표시, suggestion 표시
- AIEngineProvider: 공통 요청 생성, provider 선택, 공통 응답 검증
- LocalProvider: Ollama API 호출, timeout 처리, response normalization
- Ollama Runtime: 로컬 모델 실행
- Qwen2.5: context 기반 suggestion 생성

## 7. Provider 인터페이스

Local AI는 GPT/Gemini와 동일한 provider 응답 형식을 따른다.

공통 응답 형식은 다음과 같다.

```json
{
  "provider": "local",
  "model": "qwen2.5-7b-instruct-q4",
  "suggestion": "hold",
  "confidence": 0.62,
  "summary": "현재 context 기준으로 관망이 적절합니다.",
  "suggestion_only": true,
  "applied_to_action": false
}
```

필드 정의는 다음과 같다.

- `provider`: `gpt`, `gemini`, `local` 중 하나
- `model`: 실제 응답 생성에 사용된 모델명
- `suggestion`: 사람이 검토할 제안
- `confidence`: 0.0에서 1.0 사이의 보조 신뢰도
- `summary`: 판단 요약
- `suggestion_only`: 항상 `true`
- `applied_to_action`: 항상 `false`

## 8. UI 방향

UI는 기존 GPT/Gemini 선택 구조를 유지하면서 Local AI를 추가 provider로 노출한다.

UI 방향은 다음과 같다.

- GPT/Gemini/Local AI 선택
- 현재 선택된 provider 표시
- 모델 상태 표시
- runtime 상태 표시
- model loaded 표시
- Local AI 응답 지연 또는 실패 시 명확한 상태 표시
- suggestion과 실제 주문 실행 UI를 분리

표시 예시는 다음과 같다.

```text
AI Provider: Local AI
Model: Qwen2.5 7B Instruct Q4
Runtime: Ollama running
Model Loaded: true
Mode: suggestion-only
```

## 9. 안전 원칙

Local AI는 어떤 상황에서도 직접 주문을 실행하지 않는다.

안전 원칙은 다음과 같다.

- suggestion-only 유지
- `applied_to_action=False` 유지
- `submitted=0` 유지
- Local AI 직접 주문 금지
- OrderAdapter 수정 금지
- OrderAdapter 호출 금지
- 자동 매수/매도 제출 금지
- provider 응답은 UI/로그/검토 대상으로만 사용
- 사용자가 명시적으로 실행하기 전까지 action으로 변환하지 않음

## 10. 단계별 로드맵

149차부터 155차까지의 계획은 다음과 같다.

```text
149차: Local AI provider 상세 인터페이스 설계
150차: Ollama runtime 연결 방식 설계
151차: Qwen2.5 응답 JSON schema 설계
152차: UI provider 선택/상태 표시 설계
153차: fallback 정책 설계
154차: local suggestion audit/log 설계
155차: Local AI 통합 검증 계획 수립
```

각 단계의 범위는 다음과 같다.

- 149차: 기존 GPT/Gemini provider와 충돌하지 않는 LocalProvider 계약 정의
- 150차: Ollama endpoint, timeout, health check, model loaded 상태 정의
- 151차: suggestion-only 응답 schema와 validation 기준 정의
- 152차: UI에서 provider, runtime, model 상태를 표시하는 방향 정리
- 153차: GPT/Gemini/Local AI 간 fallback 우선순위와 실패 조건 정의
- 154차: Local AI 판단 결과를 주문과 분리해 기록하는 audit 구조 설계
- 155차: 직접 주문 금지, submitted=0, applied_to_action=false 검증 계획 수립

## 11. 최종 목표

최종 목표는 AITS를 Hybrid AI Trading OS로 확장하는 것이다.

```text
AITS = Hybrid AI Trading OS
```

Hybrid AI Trading OS의 의미는 다음과 같다.

- GPT: 고성능 외부 reasoning 엔진
- Gemini: 외부 fallback 및 보조 해석 엔진
- Local AI: 로컬 privacy-first suggestion 엔진
- AITS Core: 주문 실행과 리스크 관리를 통제하는 중심 시스템

Local AI는 AITS의 자동 주문 엔진이 아니라, 로컬에서 안전하게 동작하는 판단 보조 계층이다. 모든 최종 주문 판단과 실행은 기존 안전 구조와 사용자 검토 흐름을 따른다.
