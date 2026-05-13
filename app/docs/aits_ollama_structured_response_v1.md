# AITS Ollama Structured Response v1

## 1. Current Problem

Local Ollama inference can be called through the explicit gate, but the first real call returned `parsed_valid=False`.

## 2. Cause

The local model responded as a general assistant instead of returning the AITS shadow JSON schema. AITS needs strict JSON-only prompt constraints for local runtime calls.

## 3. Structured Prompt Policy

The Ollama prompt now requires:

- JSON ONLY
- no markdown
- no explanation outside JSON
- no code fences
- allowed `suggestion`: `confirm`, `reject`, `skip`
- allowed `next_action`: `buy`, `sell`, `hold`, `wait`, `watch`, `reduce`, `remove`
- required safety fields: `suggestion_only=true`, `applied_to_action=false`, `applied=false`, `submitted=0`, `real_order=false`

## 4. Required JSON Fields

The prompt requires all AITS fields including `suggestion`, `confidence`, `briefing`, `evidence`, `next_action`, `watch_minutes`, `exit_plan`, `prediction`, `pool_action`, `state_transition`, `eta`, `scenario`, `price_plan`, `ai_score`, `briefing_detail`, and safety flags.

## 5. Quality Flow

Local response quality uses:

1. `AIResponseRecovery`
2. `AIResponseParser`
3. `AIResponseSchemaValidator`
4. `AIResponseQualityScorer`

The result is attached as compact quality metadata only.

## 6. Safety Contract

The local response layer remains shadow-only:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `one_shot=True`

Prompt and full response text are not stored in the returned result.

## 7. Next Steps

- B5: Local inference response retest
- B6: UI runtime status sync
- B7: Local model packaging policy
