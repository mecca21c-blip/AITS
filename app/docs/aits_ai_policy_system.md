# AITS AI Policy System

## 1. 핵심 철학

AITS는 단순 자동매매 봇이 아니다.

사용자는 전략 작성자가 아니라, "운용 철학 관리자"이다.

AI는 실제 시장 상태를 분석하고, 사용자가 설정한 운용 철학에 맞춰 운용 판단을 수행한다.

---

## 2. 기존 구조의 한계

기존 전략설정 기반 구조:

- RSI
- MACD
- 고정 손절/익절
- 룰 기반 조건식

은 기존 자동매매 봇 철학에 가깝다.

이 방식은:

- 설정 복잡도 증가
- 유지보수 어려움
- AI Runtime 철학과 충돌
- GPT/Gemini/Local AI 존재감 감소

문제를 만든다.

---

## 3. 새로운 구조

AITS는 다음 구조를 목표로 한다.

사용자:

- 투자 철학 설정
- 리스크 성향 설정
- 관망 성향 설정
- AI 자율도 설정

AI:

- Runtime 분석
- Reasoning
- Shadow Preview
- DecisionRouter Preview
- 실제 운용 판단

---

## 4. 정책 계층 구조

### [A] 전역 정책

위치:

- AI 정책 센터 탭

역할:

- 전체 AI 운용 철학 설정

예:

- 안정형
- 균형형
- 공격형
- AI 자율형

---

### [B] 개별 종목 정책

위치:

- 관리종목 상세 차트 창

역할:

- 특정 종목에 대한 override 정책

예:

- BTC = 안정형
- DOGE = 공격형

---

## 5. UX 철학

초보 사용자:

- 스타일만 선택

중급 사용자:

- 슬라이더 조정

고급 사용자:

- 고급 정책 펼치기 사용

AITS는 "설정앱"이 아니라 "AI 운용 시스템"처럼 동작해야 한다.

---

## 6. 메인 정책 요소

현재 핵심 정책:

- 운용 스타일
- 리스크 수준
- 관망 성향
- AI 자율도

향후 확장 가능:

- 회전 허용
- 추가매수 허용
- 최대 비중
- 손실 방어
- 신규진입 제한

---

## 7. Preview System과의 연결

정책 시스템은 다음 Preview 계층과 연결된다.

- Runtime Input
- Reasoning Preview
- Shadow Preview
- DecisionRouter Preview

예:

- "현재 BTC는 안정형 정책입니다."
- "AI는 관망을 우선합니다."

---

## 8. 안전 원칙

정책 시스템은:

- preview-only
- read-only
- no apply
- no order
- no inference trigger

원칙을 유지한다.

실제 order/apply 연결은 후기 고위험 단계에서만 수행한다.

---

## 9. 금지 사항

다음을 메인 UX로 사용하지 않는다:

- RSI 직접 입력 중심 UI
- MACD 직접 설정 중심 UI
- 복잡한 룰봇 스타일 조건식

이들은 "고급 정책" 영역으로만 제한 가능하다.

---

## 10. 최종 목표

AITS는 "사용자가 전략을 만드는 앱"이 아니라, "사용자가 투자 철학을 설정하고 AI가 실제 운용 판단을 수행하는 AI 자산운용 운영체제"를 목표로 한다.

---

## 11. 저장/복원 정책

AI 정책 센터의 전역 정책은 앱 재실행 후 유지한다.

저장 대상은 다음 네 가지이다.

- 운용 스타일
- 리스크 수준
- 관망 성향
- AI 자율도

저장된 정책 snapshot은 현재 단계에서 preview-only 데이터이다.

즉, 저장/복원은 UI 상태 유지 목적이며 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에는 적용하지 않는다.

정책을 실제 Runtime 판단이나 주문 적용 흐름에 연결하는 작업은 별도 Sprint에서 고위험 단계로 다룬다.

---

## 12. 개별 종목 정책 저장/복원

개별 종목 정책은 관리종목 상세차트 창에서 설정한다.

저장 단위는 종목 symbol이다.

저장 위치는 기존 설정 저장 흐름의 `AppSettings.ui_state["asset_policy_snapshots"]`이다.

현재 단계에서는 preview-only이며 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에는 적용하지 않는다.

전역 정책보다 개별 종목 정책이 우선될 수 있으나, 실제 적용은 별도 Sprint에서 진행한다.

---

## 13. 정책 Preview 연계

- 전역 정책과 종목별 정책은 Runtime, Reasoning, Shadow Preview에 read-only로 표시된다.
- 이 단계에서는 실제 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 주문 판단에는 적용하지 않는다.
- 종목별 정책이 "전역 정책 따름"이면 전역 정책을 effective policy로 표시한다.
- 종목별 정책이 지정되면 override로 표시한다.
- 모든 표시는 `preview_only=True` 원칙을 유지한다.

---

## 14. AI 운용 프로필 Preset 시스템

- 사용자는 slider를 직접 조정하지 않아도 preset 기반으로 AI 운용 성향을 선택할 수 있다.
- preset은 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에 직접 적용되지 않는다.
- 현재 단계의 preset은 UI 저장/복원 및 preview/reference 용도이다.
- slider 또는 정책 combo를 직접 변경하면 preset 상태는 "사용자 커스텀"으로 전환된다.
- 전역 preset과 종목별 preset은 독립적으로 존재할 수 있다.
- 종목별 preset도 현재는 preview-only이며 실제 Runtime/Router/Order 판단에는 적용하지 않는다.

---

## 15. Detail Chart Information Architecture

- 상세차트는 `차트 확인 → AI 현황 이해 → 필요 시 운용 조정` 흐름으로 구성한다.
- AI 판단, 판단 근거, 다음 행동, 시나리오, ETA는 "현재 AI 상태" 영역에 배치한다.
- 핵심 수치는 현재가, 목표가, 리스크 기준을 compact row로 표시해 우측 패널 과밀을 줄인다.
- 운용 프로필은 "사용자의 선택적 개입" 영역으로 분리한다.
- 운용 조정 영역은 접기/펼치기를 지원해 작은 화면에서 차트와 AI 현황을 우선 표시한다.
- 운용 조정 값은 preview-only 정책 시스템이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 16. Hidden Intervention UX

- AITS는 기본적으로 AI 자율 운용 구조를 지향한다.
- 사용자는 "운용 철학 관리자"이며 지속적 수동 조작자가 아니다.
- 상세차트의 운용 조정 영역은 기본적으로 collapsed 상태로 유지된다.
- 사용자는 필요 시에만 운용 조정 drawer를 펼쳐 개입한다.
- 상세차트 UX 흐름은 `차트 확인 → AI 상태 이해 → 필요 시 운용 개입` 순서를 따른다.
- Hidden intervention 구조는 차트 가시성과 AI 현황 우선순위를 높이기 위한 UI 정책이다.
- 운용 조정 값은 계속 preview-only이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 17. Right Drawer Intervention Architecture

- 상세차트에서 AI 현황과 사용자 개입 영역은 물리적으로 분리된다.
- AI 현황은 AI reasoning, 시나리오, ETA를 이해하는 상태 영역이다.
- 운용 조정은 사용자가 필요할 때만 여는 intervention 영역이다.
- intervention은 우측 side drawer 방식으로 제공된다.
- drawer open 여부와 관계없이 AI 현황 column은 독립적으로 유지된다.
- collapsed drawer는 차트 dominance와 작은 화면 가시성을 우선한다.
- 향후 고급 종목 정책은 drawer 내부 확장으로 처리한다.
- drawer 내부 정책 값은 계속 preview-only이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 18. Resizable Detail Layout Persistence

- AITS의 화면 관련 설정은 마지막 사용 상태를 복원한다.
- 상세차트는 차트 | AI 현황 | AI 조정 3영역으로 구성된다.
- 각 영역은 사용자가 splitter로 폭을 조정할 수 있다.
- 창 크기/위치/splitter 폭/drawer 상태는 AppSettings.ui_state에 저장된다.
- 해상도별 고정값을 찾기보다 사용자 환경에 맞춰 조정 가능한 구조를 우선한다.

---

## 19. Detail Status Card Resize Safety

- 상세차트의 AI 현황 영역은 내부 카드를 세로 splitter로 조정할 수 있다.
- AI 판단, 판단 근거, 다음 행동, AI 시나리오, AI ETA 카드는 각각 최소 높이를 유지한다.
- 긴 판단 근거와 시나리오 설명은 word wrap과 텍스트 선택을 허용해 잘림 위험을 줄인다.
- AI 현황 카드 높이 정보는 AppSettings.ui_state["detail_chart_layout_state"]["ai_status_splitter_sizes"]에 저장된다.
- 이 구조는 AI 판단/ETA/점수 계산과 주문/Runtime 적용 경로를 변경하지 않는다.

---

## 20. AI Reasoning Narrative Layer

- AITS는 AI의 판단 근거를 사람이 이해 가능한 문장으로 설명한다.
- Narrative Layer는 Runtime, Router, Order, apply 경로에 영향을 주지 않는다.
- Narrative는 AI 상태 설명용 브리핑 계층이며 preview-only 원칙을 유지한다.
- 판단 근거, 다음 행동, 시나리오, ETA는 불릿 나열보다 자연어 설명을 우선한다.
- 사용자는 AI가 무엇을 관찰하고 왜 기다리는지 이해할 수 있어야 한다.

---

## 21. Narrative Writing Guidelines

- Narrative는 운영자 브리핑이다.
- 장황한 설명보다 짧고 명확한 해석을 우선한다.
- AI 자기소개 표현을 사용하지 않는다.
- 상태 설명 → 해석 → 운용 계획 순서로 작성한다.
- Runtime Preview에는 요약형만 표시한다.

---

## 22. AI Briefing Center

- AI 브리핑 센터는 현재 AI가 보고 있는 시장 상황을 요약한다.
- 사용자는 AI의 상태를 10초 이내에 이해할 수 있어야 한다.
- 브리핑 센터는 Intent / Review / Learning 시스템의 상위 계층이다.
- ETA는 다음 평가 시간이 아니라 현재 운용 시나리오 유지 예상 시간이다.

---

## 23. AI Intent System

- AI Intent System은 현재 AI가 관찰 중인 운용 전략을 설명하는 UI 계층이다.
- Intent는 주문 약속이 아니며 Runtime, Router, Order, apply 경로에 영향을 주지 않는다.
- 브리핑 센터는 현재 목표, 관찰 포인트, 행동 조건을 표시한다.
- 현재 목표는 지금 우선 확인하는 방향을 요약한다.
- 관찰 포인트는 거래량, 시장 강도, 방향성처럼 판단 전 확인할 항목을 보여준다.
- 행동 조건은 어떤 조건이 충족되어야 다음 검토가 가능한지 설명한다.
- Intent는 preview-only/read-only이며 실제 판단 계산, confidence, ETA 계산을 변경하지 않는다.

---

## 24. AI Intent Reasoning Layer

- Intent는 상태 설명이 아니라 운용 의도이다.
- Intent는 현재 목표, 관찰 포인트, 행동 조건, 전환 후보로 구성된다.
- 현재 목표는 AI가 지금 기다리는 운용 방향을 설명한다.
- 관찰 포인트는 AI가 계속 확인 중인 조건을 2~4개 항목으로 공개한다.
- 행동 조건은 조건 충족 시 어떤 판단 후보로 재평가될 수 있는지 설명한다.
- Intent는 주문 약속이 아니며 매수/매도/주문 확정 표현을 사용하지 않는다.
- Intent는 Runtime, Router, Order, apply 경로에 적용되지 않는 preview-only 계층이다.
- 사용자는 Intent를 통해 AI가 무엇을 기다리고 어떤 조건을 중요하게 보는지 이해할 수 있어야 한다.

---

## 25. AI Intent UI Hierarchy

- AI 브리핑 센터 상단은 현재 요약을 담당한다.
- 상단 브리핑에는 상태 헤드라인과 1~2문장 요약만 둔다.
- AI Intent 영역은 별도 시각 블록으로 분리한다.
- Intent 블록은 현재 목표, 관찰 포인트, 행동 조건, 전환 후보를 구분해 표시한다.
- Review/Learning은 P17/P18 영역이며 P16에서는 보조 placeholder로만 작게 표시한다.
- Intent는 주문 약속이 아니라 현재 관찰 전략을 설명하는 preview-only 계층이다.

---

## 26. Detail Chart Role Separation

- AI 현황 column은 판단, 시장 해석, 운용 계획, Intent를 담당한다.
- AI 조정 column은 AI 시나리오, 유지 예상/ETA, 사용자 조정을 담당한다.
- 시나리오와 ETA는 AI가 제안하는 기본 운용값으로 표시한다.
- 사용자가 조정하면 향후 사용자 override 값으로 표시할 수 있다.
- 현재 단계에서는 preview-only이며 Runtime, Router, Order, apply 경로에 적용하지 않는다.
- 역할 분리는 우측 패널 과밀을 줄이고 판단/의도와 조정 영역을 분리하기 위한 UI 구조다.

---

## 27. Detail Chart Intent-first Layout

- AI 브리핑 센터는 AI Intent Center로 승격된다.
- 중앙 AI 현황 column은 Intent, AI 판단, 판단 근거만 담당한다.
- 시장 해석과 운용 계획은 별도 중복 카드로 유지하지 않고 판단 근거와 Intent에 흡수한다.
- 우측 AI 운영센터는 시나리오, 유지 예상/ETA, 사용자 조정, 고급 종목 정책을 담당한다.
- AI 조정은 종목별 사용자 개입 영역으로 상시 노출된다.
- 모든 내용은 preview-only이며 Runtime, Router, Order, apply 경로에 적용하지 않는다.

---

## 28. AI Operations Center Recovery

- 상세차트 우측 column은 Drawer가 아니라 고정 AI 운영센터로 사용한다.
- AI 운영센터는 AI 시나리오, 유지 예상/ETA, AI 조정, 고급 종목 정책 순서로 표시한다.
- AI 조정 영역에는 운용 프로필, 종목 성향, AI 자율도, 최대 투자비중, 기본값 복원을 상시 노출한다.
- 요약 박스는 현재 상태를 빠르게 확인하는 보조 정보이며 설정 UI를 대체하지 않는다.
- 이 구조는 preview-only이며 Runtime, Router, Order, Execution 경로에 적용하지 않는다.

---

### Intent Human Language Layer

- AI Intent는 개발자 용어가 아니라 사용자가 바로 이해할 수 있는 운용 언어로 표시한다.
- "거래대금 기준 회복"은 "매수세 회복" 또는 "매수세가 다시 살아나는지 확인"으로 표현한다.
- "RSI 회복 흐름"은 "회복 흐름 지속" 또는 "과매도 이후 회복 흐름이 이어지는지 확인"으로 표현한다.
- "단기 추세 전환"은 "단기 상승 흐름으로 전환되는지 확인"으로 표현한다.
- Intent 문구는 주문 약속이 아니라 현재 관찰 전략을 설명하는 preview-only 언어다.

---

## 29. Why Not Action Explanation Layer

- AI�� �ൿ�ϴ� ������ �ƴ϶� ���� �ൿ���� �ʴ� ������ �����ؾ� �Ѵ�.
- ������ ���ൿ�� �ƴ϶� ���� Ȯ�� ���� ��� ���´�.
- Why Not Buy / Why Not Sell ������ �ֹ� ����� �ƴϴ�.
- �� ������ Intent ���� �ȿ��� ��� ����, �ʿ� Ȯ��, blocker ��ȣ�� ª�� �����Ѵ�.
- ���� Sprint������ preview-only/read-only UI �����̸� Runtime, Router, Order, Execution ��ο� �������� �ʴ´�.
- ���� ǥ��: �ż� ����, �ŵ� ����, �ֹ� ����, Ȯ�� �ż�, Ȯ�� �ŵ�.
- ��� ǥ��: ���� �ĺ��� ����, ��� ����, ���� ��� �ĺ� ����, ���� �ĺ� ����, �߰� Ȯ�� �ʿ�, ����, ����.

---

## 30. Scenario Dynamic Builder

- Scenario�� �ֹ� ���� ������ �ƴϴ�.
- Scenario�� ���� AI�� ��Ʈ ���¸� � ��� �������� ���� �ִ��� �����ϴ� Preview Layer��.
- Scenario Dynamic Builder�� RSI, �̵����, �ŷ���, ��ǥ�� �Ÿ�, ������ ���� �̹� ���� ��Ʈ ���¸� read-only�� �����Ѵ�.
- ǥ�� �ĺ��� ��� ��ȯ ������, ��� ������, Ⱦ�� Ȯ����, ��ǥ ���� ������, ������ ������̴�.
- Scenario snapshot schema�� aits_ai_scenario.v2�� ����Ѵ�.
- Scenario�� Runtime, Router, Order, Execution, RiskGuard�� �������� �ʴ´�.


---

## AI Output Source Separation

- Basic Engine is the Fact, Candidate, Risk, and Portfolio calculation layer.
- AI Engine is the Decision, Reasoning, Intent, Scenario, and Why generation layer.
- Basic Preview is not AI judgement; it is calculation-based observation context only.
- When no AI Engine output is available, AI Intent, AI Scenario, and Why areas must show a waiting state.
- Only GPT/OpenAI, Gemini, and Local AI/Ollama outputs may be displayed as AI judgement.
- Local AI is an independent AI Engine that can operate without an external API; it is not the Basic Engine.
- Until the Local AI Provider path is ready, Basic calculations must not be presented as Local AI judgement.
- This policy does not affect Runtime, Router, Order, Execution, or RiskGuard paths.


---

## AI Output Slot Contract

- UI must read AI Engine results through a shared contract, not ad-hoc Basic Preview text.
- Contract schema: aits_ai_output_contract.v1.
- Allowed providers are openai, gemini, and local_ai. Ollama is a local_ai runtime, not a provider.
- Disallowed sources such as basic, local, rule, chart, and fallback must produce available=false.
- Contract slots are intent, scenario, why, eta, and safety.
- Basic Preview is not an AI Output Contract and must remain calculation-based reference only.
- If no AI Output Contract is available, the UI must keep AI judgement, scenario, why, and eta in a waiting state.
- This Sprint defines the slots only; it does not add GPT, Gemini, Ollama, Runtime, Router, Order, Execution, or RiskGuard calls.

---

## AI Output Provider Normalization

- Official AI providers are openai, gemini, and local_ai.
- Ollama is not a provider; it is a runtime inside local_ai.
- qwen, mistral, gemma, and similar names are local_ai models.
- AI Output Contract normalizes raw source=ollama to provider=local_ai and runtime=ollama.
- Basic Engine is not an AI provider.
- Basic Preview is not AI Output and must not be promoted into provider output.
- UI may display Local AI or Local AI / Ollama/model, but the contract provider remains local_ai.

---

## GPT Input Contract

- GPT uses compact Fact, Candidate, Risk, Portfolio, policy, and recent-context data prepared by Basic/UI preview layers.
- GPT Input Contract defines what the AI engine may inspect before generating Intent, Scenario, Why, ETA, and Confidence output.
- Contract schema: aits_gpt_input_contract.v1.
- The contract passes summary context only; it must not include full OHLCV arrays, raw logs, full portfolio dumps, API keys, account secrets, or order permissions.
- Basic Engine remains a Fact Provider, not the Decision Engine.
- GPT output is expected to map back into the AI Output Contract slots.
- This Sprint defines the input contract helper only; it does not add GPT, Gemini, Ollama, Runtime, Router, Order, Execution, or RiskGuard calls.

---

## GPT Preview Call

- GPT Preview connects GPT Input Contract to AI Output Contract for UI preview only.
- GPT Preview prompt role is AI Asset Management Analyst.
- The call is attempted only when strategy.ai_provider is openai/gpt and an OpenAI API key is available.
- GPT Preview may fill Intent, Scenario, and Why slots only.
- GPT Preview must not generate order execution, action apply, Runtime changes, Router changes, ETA calculation changes, or confidence calculation changes.
- UI displays GPT Preview as the output source badge when a preview response is available.
- Logs must stay compact and must not include payload bodies, API keys, raw responses, account data, or private information.
- On timeout, missing key, provider mismatch, or invalid response, the UI keeps the AI waiting state.

---

## OpenAI Provider Persistence

- The provider SSOT is strategy.ai_provider.
- Selecting or successfully testing OpenAI must persist strategy.ai_provider=openai.
- The OpenAI key is stored only in the official prefs/settings strategy.ai_openai_api_key field.
- UI widgets may display masked/password key state, but logs must only report key presence, never key contents.
- GPT Preview remains preview-only and still does not affect Runtime, Router, Order, Execution, confidence, or ETA.

---

## OpenAI Key Preservation Guard

- OpenAI and Gemini API keys are preserved by the central prefs save path unless a real replacement key is supplied.
- Empty fields or masked UI strings must not overwrite existing saved keys.
- Key deletion requires an explicit delete flow; ordinary settings, UI-state, close, and layout saves must retain existing AI keys.
- Logs may report key_present/key_len only and must never include key contents.
---

## Runtime Path Diagnostic

- Settings persistence issues must first confirm the actual runtime path, data directory, and prefs file used by the running app.
- Startup diagnostics may log run_mode, cwd, root_dir, data_dir, prefs_path, prefs_exists, provider, openai_key_present, and openai_key_len.
- API key contents, prefixes, suffixes, payloads, and account data must never be logged.
- Provider/key diagnostics are read-only and must not change GPT Preview, Runtime, Router, Order, Execution, confidence, or ETA behavior.
---

## GPT Preview Responses Request Format

- GPT Preview uses the OpenAI Responses API with `instructions` plus a compact string `input`.
- The preview prompt requests plain JSON and the UI parses that JSON into `aits_ai_output_contract.v1`.
- GPT Preview does not use order/action/runtime fields and does not apply the response outside the UI preview layer.
- Unsupported or legacy OpenAI preview model values fall back to `gpt-4o-mini` for Preview only.
- Logs may include endpoint, model, error_type, and a short error summary, but must never include API keys, payload bodies, raw responses, account data, or private information.
---

## API Key / Provider Persistence Separation

- Provider selection remains in `strategy.ai_provider` as the SSOT.
- OpenAI, Gemini, and Upbit key bodies are stored outside general prefs in `data/secrets.json`.
- `prefs.json` stores only non-secret settings and key presence flags, never API key bodies.
- `save_settings()` extracts real key values into the secrets store before writing prefs.
- Empty fields or masked UI strings must not clear existing secrets.
- Key deletion requires an explicit delete flow; ordinary UI state, layout, policy, and file saves must not remove secrets.
- `load_settings()` merges the secrets store back into runtime settings for provider clients while keeping persistence separated.
- Logs may report provider, key_present, and key_len only; key contents, prefixes, suffixes, and payload bodies are forbidden.

---

## Save Responsibility Map

- The bottom save button is a settings save button, not a file export/save button.
- `prefs.json` stores provider selection, UI state, policies, and general settings.
- `secrets.json` stores OpenAI, Gemini, and Upbit key bodies only.
- `ui_state` stores window, tab, splitter, detail chart layout, and policy snapshot UI state.
- API keys must not be overwritten by general prefs saves.
- A tab-specific save dispatcher is reserved for a later Sprint.

---

## Tab Save Dispatcher

- The bottom save button is not a global file export action.
- It will evolve into a dispatcher that saves changes for the currently active tab.
- The current Sprint keeps the existing settings save path as a safe fallback while defining tab boundaries.
- `prefs.json`, `secrets.json`, `ui_state`, and policy snapshots remain separate responsibilities.
- API keys are managed only through `secrets.json`; tab saves must not overwrite key bodies.

### Tab Save Responsibility Draft

- AITS managed assets: managed-pool UI state, splitter/column/selection state, last selected symbol, filter/sort state.
- Trade history: date filter, search/filter state, column widths, sort state.
- Portfolio: view mode, column widths, sort state, chart/summary display options.
- AI Policy Center: global policy snapshot, asset policy snapshots, preset, autonomy, risk, wait preference, preview-only policy state.
- Common settings: `strategy.ai_provider`, model selection, polling settings, login/runtime settings, and API key presence flags only.

### Dispatcher Principle

- Active-tab saves should be preferred over broad settings writes.
- Common settings continues to use `_on_save_settings()`.
- Tabs without a dedicated handler currently use the existing settings-save fallback and emit a compact dispatcher log.
- Dedicated tab save helpers will be implemented incrementally in later Sprints.

---

## Session Restore Layer

- AITS restores the last user workspace state after restart.
- `ui_state.session_restore` is a screen-state snapshot, not a provider/key SSOT.
- Session restore stores the active tab, last selected managed symbol, last detail chart symbol, provider/model display context, window geometry summary, splitter sizes, and detail chart layout state.
- Provider and model values remain governed by the existing strategy SSOT fields.
- API key bodies are never stored in `session_restore`; `secrets.json` remains the only API key store.
- The bottom save dispatcher can refresh `session_restore` before running the existing settings save fallback.
- Startup, app close, and delayed tab changes refresh `session_restore` without touching API key storage.
- Window geometry restoration continues to use the existing window restore path while `session_restore` records a compact geometry summary.

---

## UI State Save Reliability

- Explicit save actions and app close saves must not be throttled.
- Automatic UI state saves may use debounce/throttle only when the caller explicitly opts in.
- `save_settings_patch` uses a patch-first signature: `save_settings_patch({"ui_state": ...}, base_settings=settings)`.
- Tab UI state saves are patch-only and must not rewrite unrelated settings payloads.
- `ui_state.session_restore` is saved through the same patch path and must be written to disk when the bottom save button or close path runs.
- API key bodies remain separated from UI state persistence and are managed only by the secrets store.
- Provider SSOT remains `strategy.ai_provider`; `session_restore.last_ai_provider` is display context only.

---

## AI Provider and Secret Restore

- The last selected AI engine is restored from `strategy.ai_provider`.
- OpenAI and Gemini API keys are restored from the secrets store, not from `prefs.json` key bodies.
- Key input fields show only a masked saved state; the key body is not displayed.
- An empty or masked key input is not treated as key deletion.
- Connection tests use the current UI key only when it is a real value; otherwise they fall back to the stored secret.
- `session_restore.last_ai_provider` is display context only and must not override `strategy.ai_provider`.
- `prefs.json` may keep provider/model/key-present metadata, while `secrets.json` owns key bodies.

---

## Common Settings Save Verification

- After the secrets split, `prefs.json` does not store OpenAI/Gemini/Upbit API key bodies.
- Common settings save verification must use key-present metadata and secrets-loaded settings, not raw key bodies in `prefs.json`.
- An empty API key body in `prefs.json` is normal when the matching `*_present` flag or loaded secret confirms the key exists.
- Save failure popups should appear only for actual prefs/secrets write or verification failures.
- API key bodies, prefixes, suffixes, and request payloads must never be logged.

---

## AI Provider UI Restore

- Provider SSOT is `strategy.ai_provider`.
- Engine cards, provider combo boxes, and legacy AI engine selectors are restored from `strategy.ai_provider`.
- `session_restore` may record provider display context, but it must not override the strategy provider SSOT.
- When OpenAI/Gemini secrets exist, key inputs are restored to a masked saved state.
- Masked key text is never treated as the actual key body and empty input is not interpreted as deletion.
- Connection tests may use the current real UI value, otherwise they fall back to the saved secret.

---

## AI Startup Connection Check

- The last selected engine is restored from `strategy.ai_provider`.
- If a saved OpenAI or Gemini key exists, AITS may run a lightweight startup connection check after the UI is ready.
- Startup connection checks are not GPT/Gemini Preview calls and must not affect Runtime, Router, Order, action, confidence, or ETA.
- Failure never blocks app startup; the UI should show that connection confirmation is needed.
- Saved key inputs use placeholder/status text such as `API Key saved`; fixed-length star text is avoided to prevent key-length confusion.
- API key bodies, prefixes, suffixes, and request payloads must never be logged.
