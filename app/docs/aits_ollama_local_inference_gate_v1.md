# AITS Ollama Local Inference Gate v1

## 1. Why The Gate Exists

BASIC(Local) inference is useful, but it must not become an accidental live provider path. The gate makes local Ollama inference opt-in and one-shot only.

## 2. `allow_live` vs `explicit_local_inference`

`allow_live=True` means the harness may consider a live provider path.

`explicit_local_inference=True` is the separate local Ollama permission. For Ollama/BASIC, `allow_live=True` alone is not enough.

## 3. Default OFF Policy

The default is blocked:

- `explicit_enable=False`
- `allowed=False`
- `reason="explicit_enable_required"`

## 4. One-Shot Shadow-Only Policy

Even when enabled, the result remains:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `one_shot=True`

## 5. Selected Model Policy

The gate uses the model inventory selector. Preferred model is `qwen2.5:7b-instruct-q4`, with fallback to installed `qwen2.5`, `qwen`, `llama`, `mistral`, or the first listed model.

## 6. Timeout Policy

Inference requires `timeout_sec > 0`. The provider applies the timeout directly to the single `ollama run` subprocess.

## 7. Prompt/Response Storage Policy

Prompt text and full response text are not logged or stored in the returned result. Parser output is converted to shadow record fields only.

## 8. Not Connected To Trading

This gate is not connected to DecisionRouter, OrderAdapter, ExecutionBridge, or UI. It does not submit orders or mutate trading state.

## 9. Next Steps

- B4: local inference response quality test
- B5: UI runtime status sync
- B6: packaged Ollama asset policy
