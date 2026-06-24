# AITS AI Judgment Stage Semantics v1

This note defines AI judgment record stages and provenance. It does not change trading strategy, provider call conditions, Router, Execution, Order, or RiskGuard behavior.

## Judgment Stages

- `ai_original`: the canonical AI Output Contract result produced by GPT, Gemini, or LOCAL calculation.
  - User-facing label: `AI 원판단`
- `aits_shadow_final`: an observe-only AITS simulated final judgment when a real post-processing stage exists.
  - User-facing label: `AITS 모의판정`
  - Detail label: `AITS 모의 최종판정`

Snapshot storage, restore, freshness refresh, and UI sanitizing are not judgment stages. They must not create extra Shadow Journal rows.

## Decision Group Lifecycle

`decision_group_id` is created once when an AI analysis request starts. The same id is carried through worker result, canonical contract metadata, `ai.reco.updated`, snapshot metadata, and Shadow Journal records.

Within one `decision_group_id`, each `record_stage` and symbol pair has a single Journal row. Later events may update richer metadata on the existing row, but they must not append another row for the same group/stage/symbol.

The canonical decision content remains `aits.ai_output_contract.v1`. Stage metadata only explains Journal flow.

## Pairing And Orphans

`AITS 모의판정` pairs only with `AI 원판단` that has the same `decision_group_id` and symbol. Timestamp proximity, provider name, or model name alone must not create a pairing.

If a legacy or orphan shadow row has no linked original row, the detail panel displays:

- `AI 원판단`: `연결된 기록 없음`
- `판단 변경 여부`: `비교 불가`
- `판단 변경 이유`: `원판단 연결 정보가 없는 이전 기록입니다`

## Change Reason

Change comparison uses canonical `decision_code`, not display text.

- If original and shadow decision codes match: `변경 없음`.
- If they differ and `change_reason` exists: show the recorded reason.
- If they differ and no reason exists: show that the post-processing detail reason was not recorded.
- If no original exists: show `비교 불가`; never show `변경 없음`.

Stage-specific basis and reason must come from that stage's own contract. If a shadow stage has no reliable basis, the UI displays `AITS 모의판정 근거가 별도로 기록되지 않았습니다` rather than reusing mismatched original-stage text.

## Engine Provenance

Engine provenance separates:

- `selected_engine`: the engine selected by the user.
- `original_generation_engine`: the engine that generated the original judgment.
- `shadow_processing_method`: the method that produced the AITS simulated final judgment.
- `model_invoked`, `invoked_model`, `ollama_invoked`: proof of an actual model invocation.

LOCAL Basic calculation displays as `LOCAL 계산 기반`. A configured local model name such as `qwen2.5` is not displayed as the judgment engine unless `ollama_invoked=True` and `invoked_model` is recorded.

## Review Mode

`재검토 필요` does not mean GPT/Gemini automatic reanalysis unless a provider reanalysis scheduler actually exists.

Current display rule:

- Basic/LOCAL monitoring may continue automatically.
- Managed-pool review queue may be built automatically.
- Cost-bearing GPT/Gemini reanalysis remains manual.

User-facing copy includes `재검토 후보 · 자동 감시 중` and `AI 재분석은 수동 실행 필요`.

## Trading Safety

All judgment stage records are observe-only unless they are existing actual trade records. Required safety metadata remains:

- `submitted=0`
- `order_allowed=False`
- `real_order=False`

This semantics layer is unrelated to Router, Execution, Order, or RiskGuard.
