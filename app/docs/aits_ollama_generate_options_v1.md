# AITS Ollama Generate Options v1

## Purpose

Ollama CLI and HTTP inference are connected, but `qwen2.5:latest` did not complete within the previous 60 second HTTP test. The likely causes are cold start, model speed, and overly long generation. This layer adds explicit generate option profiles to reduce response length and improve completion speed.

## Options

- `num_predict`: caps generated tokens.
- `temperature=0.0`: makes local JSON output more deterministic.
- `top_p`: keeps sampling narrow.
- `repeat_penalty`: discourages repeated text.
- `stop`: stops markdown/code-fence style continuations.

## Profiles

- `speed`: shortest response, `num_predict=64`, for fast smoke tests.
- `json_short`: compact JSON response, `num_predict=128`.
- `json_safe`: safer longer JSON, `num_predict=256`.
- `debug_long`: diagnostic long output, `num_predict=512`.

## Gate Policy

Options do not enable inference. `/api/generate` is still called only when `explicit_enable=True`. Default provider behavior remains blocked and shadow-only.

## Safety

Prompt and response bodies are not attached to provider results or logs. This layer is not connected to `DecisionRouter`, `OrderAdapter`, `ExecutionBridge`, or any Upbit order path.

Required constants remain:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `one_shot=True`

## Next Steps

- B8: Local HTTP response retest matrix
- B9: UI runtime status sync
- B10: packaged Ollama model policy
