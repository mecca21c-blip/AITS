# AITS AI Policy Operating Model & Risk Budget v1

## 1. Purpose

This document defines the final functional structure for the AITS AI Policy Center.

The Policy Center moves from a preset-first surface to three explicit policy axes:

- AI operating mode.
- Risk budget.
- LOCAL data policy.

This document is the reference for later UI implementation and any future RiskGuard integration. It does not connect policy values to Execution, Order, Router, or RiskGuard behavior.

## 2. Final AI Policy Center Structure

### A. AI 운용 방식

- AI 주도형
- 균형형
- 사용자 통제형

### B. 운용 자금 한도

- 총 운용 한도
- 1회 진입 한도
- 예비 현금
- 동시 보유 종목 수
- 일일 손실 제한

### C. LOCAL 데이터 정책

- 권장 자동 관리
- 상세 데이터 보관 기간
- 복기 데이터 보관 기간
- 자동 요약
- 검증 전 학습 차단

## 3. AI Operating Mode Contract

### 3-1. AI 주도형

Definition:

- AI actively adjusts watch, entry, and exit candidates according to market conditions.
- The user sets risk budget and safety conditions.
- AI does not bypass the order layer.
- Router, RiskGuard, and Execution conditions must still pass.
- Current scope is Preview/Shadow.

User copy candidate:

> AI가 시장 상황에 맞춰 관망·진입·청산 후보를 적극적으로 조절합니다. 운용 한도와 안전 조건은 반드시 유지됩니다.

### 3-2. 균형형

Definition:

- Recommended default mode.
- AI judgement is used as the main reference, with stronger conservative safety conditions.
- Suitable as the default for general users.
- The default policy must remain safe even when the user does not tune every field.

User copy candidate:

> AI 판단을 기본으로 사용하되, 보수적인 안전 조건을 함께 적용합니다. 기본 권장 모드입니다.

### 3-3. 사용자 통제형

Definition:

- AI provides analysis and candidates.
- The user keeps more confirmation and lower-intensity reflection into policy.
- Suitable for review-heavy Preview usage before any live trading integration.

User copy candidate:

> AI는 분석과 후보를 제시하고, 사용자의 확인과 통제를 더 우선합니다.

## 4. AI Operating Mode Safety Rules

- No operating mode means AI direct ordering.
- No operating mode means Router, RiskGuard, or Execution bypass.
- Saving policy does not execute orders.
- Live trading integration requires a separate approved and verified Goal.
- Current behavior is Shadow/Preview.
- UI copy must not use `자동 주문`, `즉시 적용`, or `실거래 적용`.

## 5. Risk Budget Contract

Risk budget values are policy settings and Preview criteria at this stage. They are not yet live order constraints.

### 5-1. 총 운용 한도

Definition:

- Maximum KRW amount AITS may treat as eligible for operation from the total KRW balance.
- Example: from 1,200,000 KRW balance, only 1,000,000 KRW is eligible.

Field candidate:

- `ai_policy.risk_budget.total_budget_krw`

UI copy candidate:

- `총 운용 한도`

Description:

> AITS가 운용 대상으로 삼을 수 있는 최대 금액입니다. 보유금 전체를 자동으로 사용하지 않습니다.

### 5-2. 1회 진입 한도

Definition:

- Maximum amount for one new entry or one symbol.
- Must be less than or equal to the total operating budget.

Field candidate:

- `ai_policy.risk_budget.max_entry_krw`

UI copy candidate:

- `1회 진입 한도`

### 5-3. 예비 현금

Definition:

- Minimum KRW amount that must always remain outside the operating target.
- This amount is excluded from the operating budget.

Field candidate:

- `ai_policy.risk_budget.reserve_cash_krw`

UI copy candidate:

- `예비 현금 유지`

### 5-4. 동시 보유 종목 수

Definition:

- Maximum number of positions that may be held at the same time.
- Prevents excessive diversification or simultaneous entries.

Field candidate:

- `ai_policy.risk_budget.max_positions`

UI copy candidate:

- `동시 보유 종목 수`

### 5-5. 일일 손실 제한

Definition:

- Daily loss threshold.
- Reaching the threshold may stop new entry candidates or show Preview warnings.
- Actual blocking belongs to a future RiskGuard integration Goal.

Field candidates:

- `ai_policy.risk_budget.daily_loss_limit_krw`
- `ai_policy.risk_budget.daily_loss_limit_pct`

UI copy candidate:

- `일일 손실 제한`

## 6. Risk Budget Safety Rules

- Risk budget is directly related to live-trading safety and must not conflict with RiskGuard SSOT.
- This document does not connect risk budget to actual order limits.
- UI values may be saved into a policy snapshot, but Execution and Order application requires a separate high-risk Goal.
- Total operating budget must not exceed the actual available balance in later UI validation.
- One-entry limit must not exceed total operating budget.
- Reserve cash cannot be negative.
- Maximum positions must be at least 1.
- Daily loss limit is a candidate for blocking new entries. It does not mean forced selling.
- `저장` means policy persistence, not order execution.

## 7. LOCAL Data Policy Contract

LOCAL data policy follows `app/docs/aits_local_data_lifecycle_policy_v1.md`.

UI items:

- 권장 자동 관리
- 상세 데이터 보관 기간
- 복기 데이터 보관 기간
- 자동 요약
- 검증 전 학습 차단

Default values:

- 권장 자동 관리: ON
- 상세 데이터 보관 기간: 30일
- 복기 데이터 보관 기간: 1년
- 자동 요약: ON
- 검증 전 학습 차단: ON
- 용량 경고: 1GB
- DB 최적화: 주 1회

Rules:

- LOCAL settings are not qwen, mistral, or Ollama model selection.
- LOCAL settings govern data lifecycle, Reflection use, and learning application policy.
- Unverified learning candidates must not be automatically reflected into an active model.

## 8. UI Layout Recommendation

The AI Policy Center should be arranged in this order:

1. Top guidance
   - Preview/Shadow area.
   - Saving does not execute orders.
   - Router, RiskGuard, and Execution are not bypassed.

2. AI 운용 방식
   - AI 주도형.
   - 균형형.
   - 사용자 통제형.

3. 운용 자금 한도
   - 총 운용 한도.
   - 1회 진입 한도.
   - 예비 현금.
   - 동시 보유 종목 수.
   - 일일 손실 제한.

4. AI 관여 수준
   - 낮음.
   - 표준.
   - 높음.
   - This is a sub-intensity of operating mode and must not imply AI direct ordering.

5. LOCAL 데이터 정책
   - More relevant when LOCAL is selected, but safe to keep in the overall Policy Center.
   - Recommended automatic management first.
   - Advanced items may be collapsed.

6. Legacy 고급 전략 설정
   - Keep collapsed.
   - Preview/condition calculation/orderless copy must remain visible.
   - Warn general users not to change it casually.

## 9. Default Values Proposal

- AI 운용 방식: 균형형.
- AI 관여 수준: 표준.
- 총 운용 한도: unset or user input required.
- 1회 진입 한도: candidate default of 10% of total operating budget.
- 예비 현금: unset or 0 KRW.
- 동시 보유 종목 수: candidate default of 3.
- 일일 손실 제한: unset or candidate default of 3% of total operating budget.
- LOCAL 권장 자동 관리: ON.
- 상세 데이터 보관: 30일.
- 복기 데이터 보관: 1년.
- 자동 요약: ON.
- 검증 전 학습 차단: ON.

These defaults must be confirmed before UI implementation.

## 10. SSOT Candidate

Current policy snapshot candidate:

- `ui_state.ai_policy_snapshot`

Future field candidates:

- `ai_policy.operating_mode`
- `ai_policy.ai_involvement_level`
- `ai_policy.risk_budget.total_budget_krw`
- `ai_policy.risk_budget.max_entry_krw`
- `ai_policy.risk_budget.reserve_cash_krw`
- `ai_policy.risk_budget.max_positions`
- `ai_policy.risk_budget.daily_loss_limit_krw`
- `ai_policy.local_data.auto_manage`
- `ai_policy.local_data.raw_retention_days`
- `ai_policy.local_data.reflection_retention_days`
- `ai_policy.local_data.auto_summary_enabled`
- `ai_policy.local_data.block_unverified_learning`

Warnings:

- A future Goal must verify that these fields do not conflict with existing RiskGuard or Execution SSOT.
- Do not create duplicate sources of truth.
- Risk budget values stay policy/Preview fields until a separate high-risk integration Goal approves runtime enforcement.

## 11. Next Patch Criteria

Follow-up Goal:

- `UI-POLICY-04 AI Policy Center Layout Implementation`

Acceptance criteria:

- AI 운용 방식 3 modes are visible.
- Existing stability/aggressive preset-first UI is reorganized around operating mode.
- Risk budget input area is visible.
- LOCAL data policy area is visible.
- Save button persists policy only.
- Order, Execution, Router, and RiskGuard remain unchanged.
- Preview/Shadow/orderless copy remains visible.
- Legacy advanced strategy settings remain collapsed.

## 12. ChatGPT Verification Summary

The AI Policy Center should be structured around three axes: AI operating mode, risk budget, and LOCAL data policy.

The default operating mode candidate is `균형형` because it uses AI judgement while preserving conservative safety conditions.

Risk budget is a high-risk future SSOT candidate that may later connect to RiskGuard. In this phase it is documentation only and must remain Preview/policy data.

LOCAL data policy is not model selection. It governs data lifecycle, Reflection retention, automatic summary, and blocking unverified learning.

Saving policy does not execute orders, does not bypass Router/RiskGuard/Execution, and does not connect risk budget to live order limits.
