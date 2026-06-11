# AITS AI Reflection Event Schema v1

Status: Current Reflection Event Schema Definition  
Scope: Post-decision review candidates, opportunity-cost candidates, outcome enrichment, and future learning labels

---

## 1. 문서 목적

AI Reflection Event는 AITS의 AI 운용 판단 이후 발생한 결과, 추가 손실, 놓친 매도 타이밍, 로테이션 기회비용, 판단 오차 가능성, 잘한 대기, 회피한 위험을 구조적으로 기록하기 위한 보조 이벤트다.

이 문서는 다음 작업의 기반을 정의한다.

- Local AI 학습용 결과/복기 후보
- GPT/Gemini teacher 평가 후보
- 사용자 복기와 오답노트
- Unified Trading Journal outcome/review 보강
- missed exit, opportunity cost, good wait, risk avoided 분석

Reflection Event는 Unified Trading Journal의 원 판단 기록을 대체하지 않는다. 원 판단과 그 시점의 정보는 Journal에 유지하고, Reflection Event는 일정 관찰 구간 이후 추가되는 결과/복기 후보로 연결한다.

---

## 2. 개념 정의

### AI Reflection Event

AI 또는 Basic Preview를 포함한 운용 판단 이후의 결과를 되돌아보기 위한 구조화 이벤트다. 최초 생성 시 확정 평가가 아니라 후보 상태다.

### Missed Exit Candidate

매도 또는 비중 축소를 검토할 수 있었던 구간 이후 추가 하락이 발생한 복기 후보다.

### Delayed Sell Loss Candidate

보유/관망 유지 이후 손실 또는 drawdown이 추가로 커진 후보다.

### Missed Rotation Opportunity

현재 종목을 유지하거나 대기하는 동안 당시 후보군의 다른 종목이 더 큰 상대 수익을 기록한 기회비용 후보다.

### False Hold Candidate

hold/wait 판단 이후 시장 결과가 불리하게 진행되어 판단 품질 검토가 필요한 후보다.

### False Buy Candidate

buy/recommendation 후보 이후 손실 또는 위험이 커진 복기 후보다.

### Good Wait Event

대기/비진입으로 손실, 과열 진입 또는 불리한 변동성을 피한 것으로 보이는 후보 이벤트다.

### Risk Avoided Event

매수하지 않거나 비중을 줄이거나 Router/Risk Guard가 제한하여 큰 하락 또는 변동성을 피한 것으로 보이는 후보 이벤트다.

### Opportunity Cost Event

선택한 행동과 당시 실행 가능한 대안 사이의 상대 성과 차이를 기록하는 후보 이벤트다.

### Review Candidate

관찰 구간은 종료되었으나 사용자 또는 시스템 검토가 끝나지 않은 이벤트다.

### Learning Label Candidate

outcome, observation window, leakage check가 준비되어 향후 학습 label로 전환할 수 있는 후보 이벤트다. `label_ready=true`와 동일한 의미가 아니다.

---

## 3. 핵심 원칙

- Reflection Event는 주문 신호가 아니다.
- Reflection Event는 AI가 틀렸다는 확정 판정이 아니다.
- 초기 상태는 `candidate`, review 의미는 `review_candidate` 또는 `learning_candidate`로 다룬다.
- 결과론적 단정을 금지한다.
- 일정 관찰 시간과 outcome/review가 준비된 뒤에만 학습 가능성을 평가한다.
- 같은 결과라도 당시 가용 정보, 시장 변동성, 유동성, Router/Risk Guard 제한을 함께 검토한다.
- Router, Risk Guard, Execution, Order를 우회하거나 변경할 수 없다.
- 실거래에 자동 반영하지 않는다.
- Basic Preview는 AI 판단으로 저장하지 않는다.
- future outcome과 opportunity cost는 inference feature가 아니다.

---

## 4. 최상위 Schema

```json
{
  "schema": "aits_ai_reflection_event.v1",
  "event_id": "reflection-...",
  "created_at": "2026-06-11T00:00:00+00:00",
  "source_journal_id": "journal-...",
  "session_id": "session-...",
  "symbol": "KRW-BTC",
  "asset_name": "BTC",
  "timeframe": "5m",
  "provider": "openai/gemini/local_ai/basic_preview",
  "engine_role": "preview/recommendation/validated/executed/review",
  "event_type": "missed_exit_candidate/missed_rotation_opportunity/delayed_sell_loss_candidate/false_hold_candidate/good_wait/risk_avoided",
  "event_status": "candidate/confirmed/rejected/expired",
  "decision_context": {},
  "market_after_decision": {},
  "opportunity_context": {},
  "loss_context": {},
  "comparison_context": {},
  "reflection_summary": {},
  "user_visible_message": {},
  "review": {},
  "learning_label": {},
  "safety": {},
  "meta": {}
}
```

### 필수 식별 필드

- `schema`: 반드시 `aits_ai_reflection_event.v1`
- `event_id`: Reflection Event 고유 ID
- `created_at`: UTC ISO timestamp
- `source_journal_id`: 원 판단 Journal record 참조
- `session_id`: 원 운용 세션 참조
- `symbol`, `timeframe`: 평가 대상과 관찰 단위
- `provider`: 원 판단 출처. `basic_preview`는 AI provider가 아님
- `engine_role`: 원 기록이 preview/recommendation/validated/executed/review 중 어디에 해당하는지 표시
- `event_type`: 복기 후보 유형
- `event_status`: candidate/confirmed/rejected/expired 상태

---

## 5. event_type 정의

### `missed_exit_candidate`

매도/축소 가능 구간 이후 추가 하락이 발생한 후보다. 당시 매도 가능성, 유동성, 거래 비용, Risk Guard 상태가 함께 검토되어야 한다.

### `delayed_sell_loss_candidate`

관망 또는 보유 유지 이후 추가 손실이 발생한 후보다. 단순 하락만으로 확정 실패 처리하지 않는다.

### `missed_rotation_opportunity`

현재 종목 대기 중 당시 후보군의 다른 종목이 더 크게 상승한 기회비용 후보다. 사후에 새로 등장한 종목은 비교 대안으로 사용하지 않는다.

### `false_hold_candidate`

AI 또는 recommendation이 hold/wait를 유지했으나 관찰 구간 결과가 불리한 후보다.

### `false_buy_candidate`

AI가 buy/recommendation 후보를 생성했으나 이후 손실, drawdown 또는 위험이 커진 후보다. 실행되지 않은 recommendation과 executed trade는 분리 평가한다.

### `good_wait`

대기 판단으로 손실 또는 불리한 진입을 피한 것으로 보이는 후보다.

### `risk_avoided`

비진입, 비중 축소, Router/Risk Guard 제한으로 큰 하락 또는 변동성을 피한 것으로 보이는 후보다.

### `early_exit_candidate`

매도 또는 축소 이후 가격이 의미 있게 상승하여 너무 이른 exit 가능성을 검토하는 후보다.

### 확장 후보

- `opportunity_cost_candidate`
- `missed_take_profit_candidate`
- `stop_loss_near_miss_candidate`
- `correct_hold_candidate`
- `rotation_avoided_loss`

확장 값도 주문 지시가 아닌 review taxonomy로만 사용한다.

---

## 6. decision_context

원 판단 시점에 이미 알려져 있던 compact context를 저장한다.

```json
{
  "ai_action": "observe",
  "router_action": "wait",
  "basic_score": 0.62,
  "ai_confidence": null,
  "intent_summary": null,
  "scenario_summary": null,
  "eta": null,
  "holding_state": "holding",
  "position_pnl_at_decision": -0.3,
  "decision_price": 100000000,
  "decision_time": "...",
  "whether_executed": false
}
```

규칙:

- `provider=basic_preview`이면 `ai_action`, `ai_confidence`, AI narrative를 생성한 것처럼 채우지 않는다.
- AI Output Contract가 없으면 intent/scenario/why/eta는 `null` 또는 빈 값으로 유지한다.
- API key, account secret, private account detail을 저장하지 않는다.
- 원본 prompt, raw logs, raw OHLCV 대량 배열을 저장하지 않는다.

---

## 7. market_after_decision

관찰 구간 종료 후 계산되는 outcome 성격의 값이다.

```json
{
  "price_after_5m_pct": null,
  "price_after_15m_pct": null,
  "price_after_1h_pct": null,
  "max_favorable_excursion_pct": null,
  "max_adverse_excursion_pct": null,
  "drawdown_after_decision_pct": null,
  "rebound_after_exit_pct": null,
  "observation_window_minutes": 60
}
```

규칙:

- inference input으로 사용하지 않는다.
- 관찰 구간이 끝나기 전에 확정값으로 기록하지 않는다.
- future candle 전체를 저장하지 않고 요약 결과만 저장한다.
- Feature leakage 차단 대상이다.

---

## 8. opportunity_context

```json
{
  "best_alternative_symbol": "KRW-XRP",
  "best_alternative_return_pct": 3.2,
  "candidate_pool_size": 20,
  "rotation_opportunity_pct": 2.8,
  "opportunity_cost_pct": 2.8,
  "rank_at_decision": 6,
  "alternative_rank_at_decision": 2
}
```

규칙:

- 대안 종목은 판단 시점 후보군 안에 존재했던 종목만 사용한다.
- 미래 정보로 후보군을 재구성하지 않는다.
- 거래 비용, 유동성, 교체 가능 비중을 고려하지 않은 단순 수익률은 `candidate` 근거일 뿐 확정 opportunity cost가 아니다.

---

## 9. loss_context

```json
{
  "additional_loss_pct": 0.5,
  "avoided_loss_pct": null,
  "missed_profit_pct": null,
  "realized_pnl_pct": null,
  "unrealized_pnl_pct": -0.8,
  "stop_loss_near_miss": false,
  "take_profit_missed": false
}
```

`additional_loss_pct`, `avoided_loss_pct`, `missed_profit_pct`는 비교 기준과 observation window를 함께 기록해야 한다.

---

## 10. comparison_context

```json
{
  "selected_symbol_return_pct": -0.5,
  "alternative_symbol_return_pct": 3.2,
  "benchmark_return_pct": 0.4,
  "market_average_return_pct": 0.2,
  "relative_underperformance_pct": -3.7
}
```

비교 기준은 동일한 시작 시점과 관찰 구간을 사용한다. benchmark 또는 market average가 없으면 값을 추정하지 않고 `null`로 둔다.

---

## 11. reflection_summary

```json
{
  "title": "매도 지연 복기 후보",
  "short_summary": "관망 유지 후 추가 하락이 관찰되었습니다.",
  "severity": "warning",
  "confidence": 0.65,
  "interpretation": "delayed_sell_loss_candidate",
  "caveat": "결과론적 후보이며 당시 정보와 실행 가능성에 대한 추가 검토가 필요합니다.",
  "review_required": true
}
```

`severity` 후보:

- `info`: 정보성 후보 또는 긍정적 복기
- `warning`: 판단 품질 또는 기회비용 검토 필요
- `critical`: 큰 추가 손실, 반복 오류, 데이터 품질 문제 등 우선 검토 필요

`confidence`는 Reflection 분류의 신뢰도이며 주문 confidence가 아니다. 근거가 부족하면 `null`로 둔다.

---

## 12. user_visible_message

UI용 메시지는 짧고 명확해야 하며 결과론적 확정 표현과 주문 지시를 금지한다.

```json
{
  "title": "AI 복기 후보",
  "message": "관망 유지 후 -0.5% 추가 하락이 발생했습니다. 매도 지연 복기 후보로 기록합니다.",
  "tone": "warning",
  "disclaimer": "결과론적 후보이며 추가 검토가 필요합니다. 주문 신호가 아닙니다."
}
```

표현 원칙:

- “AI가 틀렸다” 대신 “판단 오차 후보”, “복기 후보”를 사용한다.
- “매도해야 한다” 대신 “매도 지연 복기 후보”를 사용한다.
- “XRP로 교체해야 했다” 대신 “로테이션 기회비용 후보”를 사용한다.
- positive event도 확정 칭찬보다 “도움이 된 것으로 보입니다”로 표현한다.
- 주문 버튼, 실행 버튼, auto-trade 상태와 시각적으로 분리한다.

허용 예:

- “관망 유지 후 -0.5% 추가 하락이 발생했습니다. 매도 지연 복기 후보로 기록합니다.”
- “대기 중 후보 종목 XRP가 +3.2% 상승했습니다. 로테이션 기회비용 후보입니다.”
- “이번 대기는 손실 회피에 도움이 된 것으로 보입니다. Good Wait 후보입니다.”

---

## 13. review

```json
{
  "review_status": "pending",
  "reviewed_at": null,
  "reviewer": "system/user",
  "review_note": null,
  "outcome_ready": false,
  "hindsight_bias_warning": true
}
```

규칙:

- `pending`: 후보 생성, 검토 전
- `confirmed`: 정의된 기준과 당시 정보 검토 후 후보 채택
- `rejected`: 데이터 오류, 비교 불가, 결과론 편향 등으로 기각
- `hindsight_bias_warning=true`를 기본 권장한다.
- system review와 user review를 구분한다.

---

## 14. learning_label

```json
{
  "label_ready": false,
  "label_type": null,
  "label_value": null,
  "usable_for_training": false,
  "teacher_signal": null,
  "student_signal": null,
  "leakage_checked": false,
  "excluded_reason": "observation_window_not_complete"
}
```

원칙:

- `label_ready=true` 전까지 supervised learning에 사용하지 않는다.
- observation window가 끝나기 전에는 label을 확정하지 않는다.
- outcome 없는 Reflection Event는 supervised learning에서 제외한다.
- `review.review_status=confirmed` 또는 명시된 자동 검증 기준 통과가 필요하다.
- `leakage_checked=true`가 아니면 training dataset에 포함하지 않는다.
- GPT/Gemini 결과는 teacher signal 후보가 될 수 있다.
- Local AI 결과는 student signal 후보가 될 수 있다.
- Basic Preview는 teacher/student AI signal로 저장하지 않는다.
- preview, shadow, validated, executed 결과는 분리 평가한다.

### label_ready 권장 조건

아래 조건을 모두 충족해야 한다.

1. source Journal record가 존재한다.
2. observation window가 종료되었다.
3. 필요한 outcome 요약값이 존재한다.
4. 비교 시작 시점과 horizon이 일치한다.
5. candidate pool과 alternative가 당시 가용 정보로 재현 가능하다.
6. review가 confirmed이거나 문서화된 자동 확인 기준을 통과했다.
7. hindsight bias warning이 검토되었다.
8. leakage check가 통과했다.
9. 데이터 품질과 missing field가 허용 범위다.

---

## 15. safety

```json
{
  "order_signal": false,
  "router_connected": false,
  "execution_connected": false,
  "auto_trade_allowed": false,
  "model_update_allowed": false,
  "learning_auto_apply": false
}
```

추가 원칙:

- Reflection Event 생성은 Router action을 변경하지 않는다.
- confirmed event도 live trading 승인 또는 model promotion 승인이 아니다.
- Reflection label은 자동으로 active model을 변경하지 않는다.
- `model_auto_approved`는 허용하지 않는다.

---

## 16. Unified Trading Journal 연결

Reflection Event는 `source_journal_id`로 원 판단 Journal record를 참조한다.

연결 후보:

1. `journal_records.record_json` 안에 `reflection_events` 배열로 append
2. 별도 `journal_reflection_events` table로 확장
3. Journal record에는 event ID 목록만 두고 별도 저장소에서 상세 조회

권장 방향:

- v1은 schema만 정의한다.
- writer 연결은 AI-REFLECT-04에서 별도 수행한다.
- 원 Journal record는 append-only 원칙을 유지한다.
- outcome/review enrichment만 제한적으로 허용한다.
- 이벤트가 많아질 경우 별도 table이 조회, 중복 방지, 상태 전환 관리에 유리하다.

---

## 17. LightGBM / Local AI 연결

Reflection Event는 Feature Schema의 `outcome_features`, `review_features`, `learning_label` 생성 후보로 사용할 수 있다.

연결 원칙:

- Reflection Event 자체를 실시간 inference feature로 직접 사용하지 않는다.
- `price_after_*`, MFE, MAE, drawdown, missed profit, opportunity cost는 future outcome이며 inference 입력 금지다.
- observation window 이후 training label 또는 sample weight 후보로 변환할 수 있다.
- `missed_rotation_opportunity`는 ranker target 또는 opportunity cost proxy 후보가 될 수 있다.
- `false_buy_candidate`, `false_hold_candidate`, `missed_exit_candidate`는 classifier label 후보가 될 수 있다.
- `good_wait`, `risk_avoided`는 risk-quality 또는 action-quality label 후보가 될 수 있다.
- 학습 변환은 AI-REFLECT-05 Label Builder에서 별도 구현한다.

---

## 18. UI 연결 원칙

초기 UI 후보는 AI 운영센터 또는 메인 우측의 독립된 `AI 복기 후보` 카드다.

원칙:

- 주문/실행 버튼과 분리한다.
- `복기 후보`, `기회비용 후보`, `추가 손실 후보`, `Good Wait 후보`처럼 비단정적 표현을 사용한다.
- 사용자가 원 판단, 관찰 구간, 결과, caveat를 확인할 수 있어야 한다.
- AI가 무엇을 학습 후보로 수집하는지 투명하게 보여준다.
- Reflection Event를 현재 행동 추천이나 실시간 주문 신호로 표시하지 않는다.
- UI 연결은 AI-REFLECT-03 이후 별도 Goal에서 수행한다.

---

## 19. 다음 Sprint 순서

1. AI-REFLECT-01 Reflection Event Schema
2. UI-MAIN-01 Main AI Output Contract & Copy Fix
3. AI-REFLECT-02 Reflection Event Preview Builder
4. AI-REFLECT-03 Reflection Card UI
5. AI-REFLECT-04 Reflection Journal Writer
6. AI-REFLECT-05 Reflection Label Builder

현재 UI-MAIN-01은 완료되었으므로 실제 후속 구현 순서는 AI-REFLECT-02부터 진행할 수 있다.

---

## 20. 금지사항

- Router action 변경 금지
- Order/Execution 연결 금지
- Risk Guard 우회 금지
- 자동 매수/매도 연결 금지
- Reflection Event 기반 실거래 자동 반영 금지
- `model_auto_approved` 금지
- `active_model` 자동 설정 금지
- 결과론적 “AI가 틀렸다” 단정 금지
- Basic 계산값을 AI 판단처럼 저장 금지
- Reflection Event를 실거래 신호로 사용 금지
- observation window 전 label 확정 금지
- outcome/review 값을 inference feature로 사용 금지
- API key, secret, token, raw private account detail 저장 금지
- raw Journal dump 및 raw OHLCV 대량 저장 금지

---

## 21. v1 현재 미연결 상태

- Journal writer 연결 없음
- UI 연결 없음
- Router 연결 없음
- Risk Guard 연결 없음
- Execution 연결 없음
- Order 연결 없음
- 자동 학습 연결 없음
- Model Registry 자동 반영 없음
- active model 자동 설정 없음
- live trading 영향 없음

