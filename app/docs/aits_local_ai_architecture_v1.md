# AITS Local AI Architecture v1

Status: Current Local AI Architecture Lock
Scope: Local AI internal components, runtime policy, provider/runtime/model separation

---

## 1. Local AI Definition

Local AI is not a single model.

Local AI is an AITS internal AI system composed of:

- Memory Engine
- Learning Journal
- ML Engine
- Reason Runtime

Local AI is designed to become the user-specific asset management AI inside AITS.

---

## 2. ML Engine

The ML Engine uses LightGBM.

Roles:

- Predict success probability
- Predict risk score
- Assist entry/hold/reduce candidate judgement

LightGBM is an ML component, not the whole Local AI.

---

## 3. Memory

Memory uses SQLite.

Roles:

- Store historical judgements
- Store outcomes
- Store failure/success patterns

Memory is the long-term context layer for Local AI.

---

## 4. Unified Trading Journal

All engine judgements and outcomes are stored in one shared format.

GPT and Gemini judgements also become Local AI learning data.

The Unified Trading Journal is the official learning source for Local AI.

---

## 5. Reason Runtime

The Reason Runtime generates:

- User-facing explanations
- Why
- Reviews
- Summaries

Qwen-family models are the primary model candidates.

Important principles:

- AITS must not require users to install external Ollama as a mandatory dependency.
- The distributable app should use an embeddable local runtime where possible.
- Ollama is treated only as an optional development/verification backend.
- The final goal is a `local_ai` provider running inside the AITS app boundary.

---

## 6. Runtime Candidates

Candidate runtime paths:

- Embedded llama.cpp-based runtime
- ONNX Runtime candidate
- Future lightweight Qwen model bundling
- Ollama as optional development backend only

Ollama can be useful for development and validation, but it is not a required runtime for user distribution.

---

## 7. Local AI Provider

The provider name is:

```text
provider=local_ai
```

Runtime name is managed as a separate field.

Production-oriented example:

```text
provider=local_ai
runtime=embedded_llm
model=qwen
```

Development example:

```text
provider=local_ai
runtime=ollama_dev
model=qwen3
```

Provider, runtime, and model must not be collapsed into one value.

---

## 8. Prohibited Directions

Do not treat Local AI as the Basic Engine.

Do not describe Joblib or LightGBM alone as Local AI.

Do not document external Ollama installation as a mandatory user requirement.

Do not describe Basic calculation results as AI judgement.

---

## 9. Future Sprints

AI-ARCH-03:

Unified Trading Journal Schema

AI-ARCH-04:

Local AI Model Registry

AI-ARCH-05:

LightGBM Training Pipeline

AI-ARCH-06:

Embedded Reason Runtime Research

AI-ARCH-07:

Local AI Provider Skeleton
