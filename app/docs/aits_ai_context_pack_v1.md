# AITS AI Context Pack v1

## 1. 목적

AITS AI Context Pack은 AITS를 단순 자동매매 앱이 아니라 AI 운용 플랫폼으로 전환하기 위한 핵심 입력 구조이다. AI가 좋은 판단을 하려면 모델 성능만으로는 부족하며, 현재 시장과 포트폴리오 상태를 정확하게 압축한 context가 필요하다.

Context Pack이 핵심인 이유는 다음과 같다.

- AI가 판단할 수 있는 시장 상황을 구조화한다.
- 매수/매도 신호가 아니라 운용 상황을 설명한다.
- GPT/Gemini/Ollama provider가 같은 기준으로 판단하게 만든다.
- provider별 응답 차이를 비교할 수 있는 공통 입력을 제공한다.
- 향후 self-learning, shadow learning, ensemble 구조의 기반이 된다.

단순 RSI/지표봇과의 차이는 다음과 같다.

- RSI/지표봇은 특정 조건 충족 여부를 계산한다.
- AITS Context Pack은 시장 regime, 포트폴리오 상태, 기회비용, 리스크, 뉴스 이벤트를 함께 설명한다.
- 지표봇은 rule 실행에 가깝고, AITS는 AI가 운용 판단을 보조할 수 있는 운영 context를 만든다.

이 설계의 기본 정의는 다음과 같다.

```text
AI 성능보다 Context 품질이 더 중요하다.
```

AI 모델이 아무리 강해도 입력 context가 빈약하면 판단은 얕아진다. 반대로 잘 정리된 Context Pack은 상대적으로 가벼운 모델도 일관된 suggestion을 생성하게 만든다.

## 2. AITS Core Engine 역할

AITS Core Engine은 시장 OS 역할을 수행한다. 개별 지표 계산기나 주문 실행기가 아니라, 시장과 포트폴리오 상태를 운영 가능한 형태로 정리하는 중심 계층이다.

Core Engine의 역할은 다음과 같다.

- 시장 OS 역할: 시장 regime, 위험 상태, 기회 후보를 통합 관리한다.
- AI 입력 생성기: provider가 이해할 수 있는 Context Pack을 생성한다.
- AI 운용 보조 시스템: AI suggestion을 운용 판단 보조 자료로 연결한다.
- 안전 통제 계층: AI 판단과 실제 주문 실행을 분리한다.
- 상태 기록 계층: suggestion, shadow performance, provider 비교 결과를 누적한다.

Core Engine은 AI보다 앞단에 위치한다. AI가 시장을 직접 수집하고 주문을 실행하는 구조가 아니라, Core Engine이 정제된 context를 만들고 AI는 그 위에서 판단한다.

## 3. Context Pack 구조

Context Pack은 다섯 가지 category로 구성한다.

### A. Market Context

Market Context는 전체 시장 상태를 설명한다. AI가 개별 종목 판단을 하기 전에 현재 시장이 공격적인 환경인지, 방어적인 환경인지 이해하도록 돕는다.

포함 항목은 다음과 같다.

- BTC dominance
- 변동성
- 거래량
- 상승/하락 비율
- Fear/Greed
- regime

예상 구조는 다음과 같다.

```json
{
  "market_context": {
    "btc_dominance": 52.4,
    "volatility": "high",
    "volume_state": "expanding",
    "advance_decline_ratio": 0.74,
    "fear_greed": 41,
    "regime": "risk_off"
  }
}
```

### B. Portfolio Context

Portfolio Context는 현재 계좌와 보유 상태를 설명한다. AI는 시장만 보는 것이 아니라, 현재 사용자의 포지션과 손익 구조를 함께 고려해야 한다.

포함 항목은 다음과 같다.

- 현재 보유
- 수익률
- drawdown
- exposure
- 현금 비율
- 기회비용

예상 구조는 다음과 같다.

```json
{
  "portfolio_context": {
    "positions": [],
    "return_rate": 0.0,
    "drawdown": 0.0,
    "exposure": 0.35,
    "cash_ratio": 0.65,
    "opportunity_cost": "medium"
  }
}
```

### C. Opportunity Context

Opportunity Context는 현재 보유 또는 관심 후보 대비 더 나은 선택지가 있는지 설명한다. AITS가 단순 보유 판단을 넘어 rotation과 기회비용을 다루기 위해 필요한 category이다.

포함 항목은 다음과 같다.

- rotation 후보
- 강한 종목
- 약한 종목
- AI 추천 history
- shadow performance

예상 구조는 다음과 같다.

```json
{
  "opportunity_context": {
    "rotation_candidates": [],
    "strong_symbols": [],
    "weak_symbols": [],
    "ai_recommendation_history": [],
    "shadow_performance": []
  }
}
```

### D. Risk Context

Risk Context는 AI가 suggestion을 만들 때 반드시 참고해야 하는 제한 조건이다. 수익 기회보다 먼저 계좌 방어와 과열 위험을 고려하게 만든다.

포함 항목은 다음과 같다.

- max exposure
- volatility risk
- 급락 위험
- liquidity
- cooldown

예상 구조는 다음과 같다.

```json
{
  "risk_context": {
    "max_exposure": 0.6,
    "volatility_risk": "high",
    "crash_risk": "medium",
    "liquidity": "normal",
    "cooldown": false
  }
}
```

### E. News/Event Context

News/Event Context는 정량 지표만으로 설명되지 않는 외부 이벤트를 AI 입력에 포함한다. 이벤트성 변동, 공포 확산, 거래소 이슈는 시장 regime과 리스크 판단에 직접 영향을 줄 수 있다.

포함 항목은 다음과 같다.

- 뉴스 요약
- 이벤트
- 공포 이벤트
- 거래소 이슈

예상 구조는 다음과 같다.

```json
{
  "news_event_context": {
    "news_summary": [],
    "events": [],
    "fear_events": [],
    "exchange_issues": []
  }
}
```

## 4. AI 입력 흐름

AI 입력 흐름은 Core Engine이 context를 만들고 provider가 suggestion을 생성하는 구조로 정의한다.

```text
Core Engine
  -> Context Pack
  -> AIEngineProvider
  -> GPT/Gemini/Ollama
  -> suggestion
  -> DecisionRouter
```

각 계층의 책임은 다음과 같다.

- Core Engine: 시장, 포트폴리오, 기회, 리스크, 뉴스 이벤트 상태 수집과 정리
- Context Pack: AI가 읽을 수 있는 표준 입력 구조
- AIEngineProvider: GPT/Gemini/Ollama provider 선택과 공통 인터페이스 유지
- GPT/Gemini/Ollama: suggestion 생성
- DecisionRouter: suggestion을 운용 판단 흐름으로 전달하되 직접 주문으로 연결하지 않음

## 5. AI 역할 정의

AITS에서 AI는 주문 실행자가 아니라 운용 판단 보조자이다.

AI 역할은 다음과 같다.

- 판단자: Context Pack을 기반으로 현재 상황을 해석하고 suggestion을 생성한다.
- 전략 적응: 시장 regime 변화에 따라 공격/방어/관망 관점을 조정한다.
- regime 대응: risk-on, risk-off, high-volatility, low-liquidity 등 상태에 맞춰 판단한다.
- opportunity cost 계산: 현재 보유를 유지할 때와 rotation 후보로 이동할 때의 상대 비용을 비교한다.

AI의 출력은 사람 또는 상위 정책 계층이 검토할 수 있는 suggestion이다. AI 판단은 실행 명령이 아니다.

## 6. 금지 사항

Context Pack 기반 AI 구조에서도 안전 원칙은 유지한다.

금지 사항은 다음과 같다.

- AI 직접 주문 금지
- `applied_to_action=False` 유지
- suggestion-only 유지
- OrderAdapter 수정 금지
- OrderAdapter 직접 호출 금지
- GPT/Gemini/Ollama 로직 변경 금지
- 실행 로직 변경 금지
- AI 응답을 자동 주문으로 변환 금지

## 7. 장기 목표

Context Pack은 장기적으로 AITS의 AI 운용 학습 기반이 된다.

장기 목표는 다음과 같다.

- Self-learning: 누적 context와 결과를 기반으로 운용 판단 품질을 개선한다.
- shadow learning: 실제 주문 없이 AI suggestion의 가상 성과를 추적한다.
- provider 비교: GPT/Gemini/Ollama가 같은 Context Pack에 대해 어떤 차이를 보이는지 비교한다.
- AI ensemble: 여러 provider의 suggestion을 결합해 더 안정적인 판단을 만든다.
- dynamic routing: 상황별로 적합한 provider를 자동 선택한다.

이 목표들은 직접 주문 자동화를 의미하지 않는다. 학습과 비교의 대상은 suggestion 품질이며, 실행 안전 원칙은 별도로 유지한다.

## 8. Hybrid AI 구조

AITS의 Hybrid AI 구조는 provider별 강점을 역할로 분리한다.

```text
GPT = 고급 추론
Gemini = 빠른 분석
Local AI = 저비용 상시 판단
Core Engine = 운영체제
```

역할 정의는 다음과 같다.

- GPT: 복잡한 reasoning, 긴 문맥 분석, 고급 전략 해석
- Gemini: 빠른 분석, 요약, 외부 AI fallback
- Local AI: 저비용 상시 판단, 개인정보 친화적 로컬 해석, 반복 suggestion 생성
- Core Engine: 시장 OS, Context Pack 생성, 안전 통제, provider routing

Hybrid AI 구조의 핵심은 AI provider가 중심이 아니라 Core Engine이 중심이라는 점이다. Provider는 교체 가능하지만, Context Pack과 Core Engine은 AITS 운용 플랫폼의 기반으로 유지된다.

## 9. 최종 정의

AITS의 최종 정의는 다음과 같다.

```text
AITS = AI Trading Operating System
```

AITS는 단순 자동매매 앱이 아니다. 시장 context를 만들고, portfolio 상태를 해석하며, opportunity cost와 risk를 비교하고, GPT/Gemini/Ollama provider를 통해 suggestion을 생성하는 AI 운용 플랫폼이다.

최종 구조에서 AI는 실행자가 아니라 판단 보조자이고, Core Engine은 AI가 올바르게 판단할 수 있도록 context를 제공하는 운영체제이다.
