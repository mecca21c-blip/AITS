# AITS AI Judgment Stage Semantics v1

This note defines the user-facing meaning of AI judgment records without changing trading strategy, provider calls, Router, Execution, Order, or RiskGuard.

## Judgment Stages

- `ai_original`: the canonical AI Output Contract result produced by GPT, Gemini, or LOCAL calculation.
  - User-facing label: `AI 원판단`
- `aits_shadow_final`: an observe-only AITS simulated final judgment when a real post-processing stage exists.
  - User-facing label: `AITS 모의판정`
  - Detail label: `AITS 모의 최종판정`

Snapshot storage and UI sanitizing are not judgment stages. They must not create extra Shadow Journal rows.

## Decision Group Rule

One AI request is grouped by `decision_group_id`. Within one group, each `record_stage` may be recorded at most once.

Required safety metadata remains:

- `submitted=0`
- `order_allowed=False`
- `real_order=False`

The canonical decision content remains `aits.ai_output_contract.v1`. Stage metadata only explains Journal flow.

## Change Reason

If `AI 원판단` and `AITS 모의 최종판정` differ, the detail panel shows:

- AI original decision
- AITS simulated final decision
- whether the decision changed
- the recorded change reason

If no real change reason exists, the UI shows that the detailed reason was not recorded. It must not invent a policy reason.

## Review Mode

`재검토 필요` does not mean GPT/Gemini automatic reanalysis unless a provider reanalysis scheduler actually exists.

Current display rule:

- Basic/LOCAL monitoring may continue automatically.
- Managed-pool review queue may be built automatically.
- Cost-bearing GPT/Gemini reanalysis remains manual.

User-facing copy:

- `재검토 후보 · 자동 감시 중`
- `AI 재분석은 수동 실행 필요`

## Korean UX Terms

- Preview judgment -> `AI 원판단`
- Shadow judgment -> `AITS 모의판정`
- Shadow final detail -> `AITS 모의 최종판정`
- Action -> `판단 결과`
- Reflection -> `복기`
- Record -> `기록`
- Detail -> `상세`
- Current Condition -> `현재 상태`
- LIVE LOG -> `실시간 로그`
- MAIN ANALYSIS CENTER -> `종합 분석 센터`
- AI MANAGED CANDIDATES -> `AI 관리종목`
- AI THEME SCANNER -> `AI 후보 탐색`

Technical names such as AITS, LOCAL, GPT, Gemini, API, RSI, MACD, KRW symbols, model names, and internal schema keys are preserved.

