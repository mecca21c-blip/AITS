# AITS Provider Comparison Stats v1

## 1. Purpose

Provider Comparison Stats exists to compare the operating tendencies of GPT, Gemini, Ollama, and Mock AI providers.

The goal is not to execute trades. The goal is to track AI judgment quality over time and prepare a future basis for ensemble, weighting, reliability, and provider selection analysis.

This document fixes the current implementation as an attach-only observation layer.

## 2. Current Connection Structure

Current structure:

```text
shadow_history
→ AIProviderComparisonStats
→ provider별 stats
→ RouterSummary attach-only 표시
```

Meaning:

- `shadow_history` keeps previous AI shadow records.
- `AIProviderComparisonStats` reads the records and aggregates provider tendencies.
- Provider stats are displayed in `RouterSummary`.
- The stats are not used for final action, confidence, order creation, or execution routing.

## 3. Statistics Input Data

Current input:

- `self.shadow_history`
- `record["ai_shadow"]`

Excluded data:

- `raw_text`
- API keys
- secrets
- full raw provider responses

Only safe, compact AI shadow fields are intended for stats calculation.

## 4. Provider Aggregation Fields

Each provider bucket includes:

- `total`
- `confirm`
- `reject`
- `skip`
- `watch`
- `buy`
- `sell`
- `hold`
- `remove`
- `avg_confidence`
- `applied_count`

Missing or invalid values are handled safely:

- Missing provider → `unknown`
- Missing suggestion → `skip`
- Missing next action → `wait`
- Invalid confidence → `0.0`
- `applied` is counted only as a boolean and is not applied to action.

## 5. RouterSummary Display Format

RouterSummary displays compact stats only.

Example:

```text
ai_stats_total=4
ai_stats=openai:t1/c1/s0/w1/a0 | gemini:t1/c0/s1/w0/a0
```

Compact field meaning:

- `t` = total
- `c` = confirm
- `s` = skip
- `w` = watch
- `a` = applied_count

This is a log-level operating signal, not an execution command.

## 6. Safety Contract

Provider comparison stats are attach-only.

Safety invariants:

- Final action must not change.
- Final confidence must not change.
- Do not pass stats to `OrderAdapter`.
- Do not pass stats to `ExecutionBridge`.
- Keep `applied=False`.
- Keep `submitted=0`.

The provider stats layer observes provider behavior. It does not decide, override, submit, or execute.

## 7. Current Limits

Current limitations:

- Not yet based on real provider live cycle results.
- Dry-run and mock-based verification are possible.
- Scoring is not yet active.
- Weighting is not yet active.
- Reliability-based provider selection is not yet active.

The current feature is a visibility layer for AI provider tendency, not an optimization engine.

## 8. Next Steps

197차:
Paper trading shadow apply design document

198차:
Paper shadow result model

199차:
Paper shadow apply skeleton

200차:
Live provider one-shot test plan
