# AITS Ollama Model Inventory v1

## 1. Purpose

The Ollama Model Inventory layer checks which local Ollama models are installed and selects the best candidate for AITS BASIC(Local) runtime readiness.

This is inventory only. It does not run local inference.

## 2. `ollama list` vs Inference

`ollama list` reads model inventory metadata. It is different from:

- `ollama run`
- `ollama generate`
- `ollama chat`
- model pull/download commands

Those commands remain forbidden in this step.

## 3. Model Selection Policy

Selection order:

1. Exact preferred model: `qwen2.5:7b-instruct-q4`
2. `qwen2.5` family
3. `qwen` family
4. `llama` family
5. `mistral` family
6. First listed model
7. No selection if inventory is empty

## 4. Preferred Model Policy

AITS currently prefers `qwen2.5:7b-instruct-q4` because it fits the BASIC(Local) role: repeated local reasoning, low-cost state classification, and local strategy compression.

## 5. Fallback Model Policy

Fallback is allowed only as a candidate selection result. It does not execute the model. A fallback result should be shown to runtime status and later UI layers as “selected candidate,” not as proof of inference readiness.

## 6. Model Directory vs `ollama list`

The packaged model directory can be missing while the user’s installed Ollama runtime still has models available through PATH. Therefore:

- `model_dir_exists=False` means packaged/user asset path is missing.
- `ollama list` can still return installed models from the active Ollama runtime.

Both facts are useful and should be reported separately.

## 7. Next Steps

- B3: Local inference gate
- B4: UI runtime status sync
- B5: packaged Ollama asset policy
