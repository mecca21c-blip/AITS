# AITS Ollama HTTP API Gate v1

## Purpose

The previous BASIC(Local) path used `ollama run` through the CLI. That path can time out because the CLI process has startup and terminal handling overhead. This layer adds a local HTTP API path for Ollama while keeping inference behind an explicit one-shot gate.

## HTTP Endpoints

- `/api/tags`: checks local model inventory and runtime availability.
- `/api/generate`: performs one local generation request with `stream=false`.

Only localhost URLs are allowed. The default endpoint is `http://127.0.0.1:11434`.

## Gate Policy

HTTP health checks may call `/api/tags`. Actual generation through `/api/generate` requires `explicit_enable=True`. `allow_live` is not treated as permission for local inference by itself.

Default behavior remains blocked:

- `explicit_enable=False`
- `actual_inference_called=False`
- `submitted=0`
- `real_order=False`

## Response Handling

The provider extracts the transient `response` text from the HTTP result, passes it to the Ollama response quality checker, and returns compact quality fields only. Prompt bodies and full response bodies are not logged or attached to the provider result.

## Safety Contract

This layer is not connected to `DecisionRouter`, `OrderAdapter`, `ExecutionBridge`, or any Upbit order execution path.

All generated results remain:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `one_shot=True`

## Next Steps

- B7: Local HTTP response retest
- B8: UI runtime status sync
- B9: packaged Ollama runtime policy
