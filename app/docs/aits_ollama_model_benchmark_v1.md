# AITS Ollama Model Benchmark v1

## Purpose

This layer diagnoses whether local Ollama models can produce a minimal response quickly enough for the BASIC(Local) runtime. It is not connected to AITS decision, routing, order, or UI flows.

## Target Models

- `qwen2.5:latest`
- `llama3.1:latest`
- `mistral:latest`

## Benchmark Prompt

The benchmark uses only:

```text
Return JSON: {"ok": true}
```

Generate options:

- `num_predict=16`
- `temperature=0.0`
- `top_p=0.8`
- `repeat_penalty=1.1`
- `timeout=45`

## Measurements

Each model is tested once and records:

- `completed`
- `timed_out`
- `elapsed_sec`
- `response_chars`
- `first_response_available`
- `error_type`

## Runtime Candidate Rule

If a model returns `response_chars > 0` within 45 seconds, it is usable as a BASIC(Local) candidate. If it returns zero characters within that window, it is not suitable for real-time BASIC inference.

The fastest usable model becomes `selected_runtime_model`.

## Safety

This benchmark is local-only and benchmark-only:

- No provider API calls
- No orders
- No UI updates
- No DecisionRouter attachment
- No OrderAdapter or ExecutionBridge attachment
- `submitted=0`
- `real_order=False`

## Next Decision

If a non-qwen model is faster and usable, BASIC(Local) should move from fixed `qwen2.5` selection to the fastest usable local model policy.
