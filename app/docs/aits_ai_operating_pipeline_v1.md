# AITS AI Operating Pipeline v1

## 1. 현재 AI Operating Pipeline

AITS AI Operating Pipeline은 자동 주문 실행 구조가 아니라, AI 운용 판단을 생성하고 shadow 기록으로 남기기 위한 분석 파이프라인이다.

현재 구성 요소는 다음과 같다.

- `AIContextBuilder`: 시장, 포트폴리오, 기회, 리스크, 뉴스 context pack 생성
- `AIPromptBuilder`: compact context dict를 provider 입력 prompt로 변환
- `AIProviderRouter`: provider 문자열을 정규화하고 GPT/Gemini/Ollama bridge 선택
- `GPTProviderBridge`: GPT 기반 shadow cycle 준비
- `GeminiProviderBridge`: Gemini 기반 shadow cycle 준비
- `OllamaProviderBridge`: Ollama/Qwen local shadow cycle 준비
- `AIResponseParser`: provider JSON 응답을 안전한 parsed response로 변환
- `ShadowRecord`: parsed response를 DecisionRouter shadow 기록에 적합한 dict로 변환

## 2. 현재 완성된 흐름

현재 완성된 skeleton 흐름은 다음과 같다.

```text
Context Builder
  -> Prompt Builder
  -> Provider Router
  -> GPT/Gemini/Ollama Bridge
  -> Response Parser
  -> Shadow Record
```

이 흐름은 shadow-only 검증용 구조이며, 실제 주문 실행 또는 DecisionRouter 반영은 포함하지 않는다.

## 3. 현재 미연결 영역

현재 의도적으로 연결하지 않은 영역은 다음과 같다.

- UI 분석 결과 패널
- DecisionRouter shadow history
- 실제 provider API live call
- Ollama runtime
- OrderAdapter
- 실제 주문

이 미연결 상태는 안전을 위한 설계 단계 구분이다. AI 판단 구조가 안정화되기 전에는 주문 계층과 연결하지 않는다.

## 4. provider별 역할

Provider별 역할은 다음과 같다.

- GPT: 고급 추론/시나리오/브리핑
- Gemini: 빠른 분석/비용 효율/대체 엔진
- Ollama(Qwen2.5): 로컬 상시 판단/비용 절감/오프라인 fallback

Provider별 역할은 다르지만 입력과 출력 계약은 동일하게 유지한다.

## 5. shadow-only 안전 원칙

현재 AI Operating Pipeline은 shadow-only 안전 원칙을 따른다.

필수 안전 필드는 다음과 같다.

```json
{
  "suggestion_only": true,
  "applied_to_action": false,
  "applied": false
}
```

안전 원칙은 다음과 같다.

- `suggestion_only=True`
- `applied_to_action=False`
- `applied=False`
- no direct order
- AI provider는 OrderAdapter를 호출하지 않음
- AI 응답은 실제 주문으로 자동 변환하지 않음

## 6. Ollama 내장 구축 계획

Ollama 내장 구축은 Local AI를 AITS의 3번째 선택 엔진으로 제공하기 위한 장기 계획이다. 이 문서는 계획만 다루며 runtime 실행, 설치 자동화, 패키징 구현은 포함하지 않는다.

### 6-1. 목표

Ollama 내장 구축 목표는 다음과 같다.

- 사용자가 별도 설치하지 않음
- AITS 배포 폴더에 runtime 포함
- Qwen2.5 7B Instruct Q4 기본 모델
- 로컬 AI를 3번째 선택 엔진으로 제공

### 6-2. 예상 폴더 구조

예상 폴더 구조는 다음과 같다.

```text
runtime/
  ollama/
    ollama.exe
    models/
    config/
app/
  services/
    ollama_runtime_manager.py
```

### 6-3. 단계별 구축

Ollama 내장 구축 단계는 다음과 같다.

```text
A. runtime path detector
B. ollama.exe 존재 확인
C. local port 상태 확인
D. runtime start/stop manager
E. model existence check
F. model load/ping
G. shadow inference
H. packaging inclusion
```

각 단계는 runtime 확인과 shadow inference까지 분리해 진행한다. 실제 주문 실행과 연결하지 않는다.

### 6-4. 리스크

Ollama 내장 구축 리스크는 다음과 같다.

- 배포 용량 증가
- CPU 속도
- Windows Defender 오탐
- 포트 충돌
- 모델 파일 용량
- 라이선스 확인 필요

### 6-5. 모델 정책

기본 모델은 다음과 같다.

```text
Qwen2.5 7B Instruct Q4
```

후보 모델은 다음과 같다.

- Mistral 7B Instruct Q4
- Gemma 2 9B Q4

선정 기준은 다음과 같다.

- 한국어
- JSON 안정성
- CPU 속도
- reasoning
- 메모리

## 7. 다음 구현 순서

다음 구현 순서는 다음과 같다.

```text
165차: UI provider router dry-run 테스트 버튼
166차: AI 분석 결과 UI 표시
167차: DecisionRouter shadow-only 연결
168차: Ollama runtime manager skeleton
169차: Ollama runtime path/ping UI
170차: Ollama inference dry-run/live 준비
```

각 단계는 shadow-only 안전 원칙을 유지하면서 진행한다.

## 8. 최종 목표

최종 목표는 AITS를 Hybrid AI Trading Operating System으로 확장하는 것이다.

```text
AITS = Hybrid AI Trading Operating System
```

AITS는 단순 자동매매 앱이 아니라, context를 만들고 provider를 선택하며 AI 분석 결과를 shadow 기록으로 검증하는 운용 플랫폼이다. 실제 주문 계층은 AI 분석 계층과 분리되어 보호된다.
