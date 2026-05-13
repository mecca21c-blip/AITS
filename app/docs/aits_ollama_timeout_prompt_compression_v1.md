# AITS Ollama Timeout & Prompt Compression v1

## 1. Purpose

The first structured Ollama prompt improved schema instructions but timed out at 30 seconds. B5 adds prompt profiles and timing records so AITS can tune local inference safely.

## 2. Prompt Profiles

- `full`: full AITS JSON schema prompt.
- `compact`: core decision, scenario, eta, pool action, and safety fields.
- `ultra_compact`: small schema for slower local models.
- `speed_test`: minimal JSON object for measuring local model latency.

All profiles include `suggestion_only=true`, `applied=false`, `applied_to_action=false`, `submitted=0`, and `real_order=false`.

## 3. Timeout Profile

`generate_local_one_shot` defaults to `prompt_profile="compact"` and `timeout_sec=60`. Test callers can explicitly use `speed_test`, `ultra_compact`, or `compact`.

## 4. Timing Result

Each explicit inference returns `prompt_profile`, `elapsed_sec`, `timed_out`, and `timing`. Raw prompt and full response text are not returned or logged.

## 5. Safety

Inference is still blocked unless `explicit_enable=True`. This layer is not connected to DecisionRouter, OrderAdapter, ExecutionBridge, or UI.
