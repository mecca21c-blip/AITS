# AITS AI 복기·학습 일지 v1

## 목적

AI 복기는 판단 당시의 정보, 최종 판단, 실행 여부와 5분·15분·1시간 실제 결과를 exact identity로 연결해 사용자가 읽을 수 있는 파생 기록을 만든다. 학습 일지는 복기에서 확인된 반복 패턴, 모델·Level·교사 AI 상태 변화와 정책 개선 제안을 보존한다.

이 계층은 설명·복기·제안 전용이다. 최종 판단, 주문, Managed Pool, Provider Router, RiskGuard, LivePreflight, LOCAL_ENGINE Level 또는 Champion pointer를 변경하지 않는다.

## 저장 계약

- 복기 schema: `aits_ai_review_record.v1`
- 일지 schema: `aits_ai_learning_journal_entry.v1`
- 정책 제안 schema: `aits_ai_policy_suggestion.v1`
- 복기: `data/ai_review/ai_review_records.jsonl`
- 복기 summary/state: `data/ai_review/ai_review_summary.json`, `ai_review_state.json`
- 학습 일지: `data/learning_journal/learning_journal.jsonl`
- 반복 패턴: `data/learning_journal/repeated_patterns.json`
- 정책 제안: `data/learning_journal/policy_suggestions.jsonl`

모든 파일은 파생 데이터다. 원본 decision, outcome, candidate, teacher, order/reconciliation record는 수정하거나 삭제하지 않는다. 파생 파일은 atomic replace, fsync, NUL/partial/corrupt 방어, ID index와 재생성을 지원한다.

## Exact join

연결 우선순위는 `decision_id`, `prediction_id`, `outcome_linkage_key`, order/reconciliation identity, `parent_decision_id`다. symbol과 시각만을 이용한 fuzzy join은 금지한다. 연결 근거가 부족하면 pending, inconclusive 또는 data unavailable로 남기며 사실을 추정하지 않는다.

## 복기 lifecycle

- `pending`: 평가 가능한 결과 대기
- `partial_5m`: 5분 결과 확인
- `partial_15m`: 15분 결과 확인
- `partial_1h`: 1시간 결과 확인
- `final`: 정책상 충분한 최종 결과 확인
- `inconclusive`: 연결 또는 근거 부족
- `data_unavailable`: 결과 source 없음

`review_id`는 decision identity에서 안정적으로 생성한다. 같은 판단의 checkpoint가 늘어나면 같은 ID의 파생 record를 갱신하므로 stage별 중복 append를 만들지 않는다.

## 판단 품질과 결과 품질

판단 품질은 당시 reason, evidence, payload/feature 품질, confidence, validator와 blocker만 사용한다. 결과 품질은 checkpoint의 실제 outcome만 사용한다. 이 두 계산을 분리한 뒤 good decision/good result 등 matrix를 구성한다.

수익률 하나, 교사 AI와의 불일치 또는 사후 정보만으로 판단 품질을 결정하지 않는다. 한국어 composer는 source에 있는 사실과 명시된 한계만 설명하며 raw prompt나 추정 인과를 사용하지 않는다.

## 반복 패턴과 정책 제안

반복 패턴은 최소 3개의 서로 다른 review evidence가 있을 때만 만든다. 단발 사건은 반복 패턴으로 승격하지 않는다. 정책 제안은 supporting review ID와 기대 효과·위험을 포함하고 항상 사용자 검토를 요구한다.

승인은 `approved_for_validation`까지만 진행한다. 즉시 적용 버튼과 자동 runtime 적용은 없으며 `runtime_policy_applied=false`를 유지한다.

## 실행 경계

Live ON 중에는 outcome append와 pending marker만 허용한다. 전체 복기 생성, 패턴 scan, 일지 rebuild는 OFF 상태의 명시적 `복기 업데이트` worker에서만 실행한다. UI thread는 summary/cache만 읽고 상세 record는 offset index로 lazy load한다.

Observe-only summary는 source와 파생 파일을 쓰지 않는다. 명시적 generation만 복기·일지 파생 파일을 갱신한다.

## 사용자 UI

기존 AI 브리핑 영역의 `AI 복기·학습 일지` 진입점에서 하나의 dialog를 연다.

- AI 복기: 요약 카드, 기간·종목·판단·상태·품질 필터, 목록, 사실 기반 상세
- 학습 일지: 일별/주간 요약, 반복 패턴, timeline, 정책 제안
- 정책 제안 작업: 자세히 보기, 검증 승인, 보류, 거절
- 적용 작업은 제공하지 않는다.

사용자 화면은 한국어 용어를 사용하고 raw snake_case, API key, raw prompt를 표시하지 않는다. 숨겨진 화면의 주기적 full scan은 없고 명시 refresh와 worker만 사용한다.

## 검증

전용 mode:

`aits_qt_smoke_harness.py --mode ai-review-learning-journal-v1-summary --observe-only`

검증은 exact join, source hash 보존, 판단/결과 품질 분리, factual composer, dedupe, pattern threshold, 정책 자동 적용 금지, UI lightweight 경계, 금지 계층 diff와 주문/Managed Pool mutation 0을 확인한다.
