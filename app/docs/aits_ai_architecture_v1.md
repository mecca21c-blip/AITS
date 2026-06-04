# AITS AI Architecture v1

Status: Current AI Architecture Lock
Scope: AI engine roles, responsibilities, data flow, learning structure

---

## 1. AITS Philosophy

AITS is not a simple automated trading bot.

AITS is an AI Asset Management System.

Goals:

- Market analysis
- Asset management
- Risk management
- Self-learning
- Cost optimization

---

## 2. AI Engine Slot

AITS uses a single primary engine structure.

The user selects one of the following engines:

- GPT
- Gemini
- Local AI

In the default mode, only the selected engine performs operating judgement.

Multi-engine cross verification is separated into a future Advanced Verification Mode.

---

## 3. Basic Engine

Role:

The Basic Engine calculates market data.

Responsibilities:

- RSI
- MACD
- Volume
- Trend
- Volatility
- Score
- Risk

The Basic Engine does not make operating judgements.

The Basic Engine is a calculator.

The Basic Engine is not AI.

---

## 4. GPT

Implementation:

OpenAI API

Role:

Advanced market interpretation engine.

Responsibilities:

- Intent
- Scenario
- Why
- ETA
- Strategy Analysis

Characteristics:

- Incurs cost
- High reasoning capability
- External API dependency

---

## 5. Gemini

Implementation:

Gemini API

Role:

Advanced market interpretation engine.

Responsibilities:

- Intent
- Scenario
- Why
- ETA
- Strategy Analysis

Characteristics:

- May incur cost
- High reasoning capability
- External API dependency

Note:

GPT and Gemini are AI Engines in the same UI position.

---

## 6. Local AI

Implementation:

AITS internal engine.

Composition:

Local AI =
Memory Engine
+
ML Engine
+
Reason Engine
+
Learning Journal

Role:

User-specific asset management AI.

Characteristics:

- Zero API cost
- Offline-capable
- Evolves per user

Local AI may use local runtimes or models in future implementations, but Local AI is the provider-level AI Engine.

---

## 7. Memory Engine

Role:

Stores historical judgement records.

Data:

- Intent
- Scenario
- Why
- ETA
- Outcome

---

## 8. Unified Trading Journal

All engines write records in the same format.

Fields:

- timestamp
- symbol
- provider
- market_snapshot
- intent
- scenario
- why
- eta
- decision
- outcome

This structure is AITS' official learning data.

---

## 9. ML Engine

Candidates:

- LightGBM
- XGBoost
- RandomForest

Important:

RandomForest alone is not defined as Local AI.

The ML Engine is one part of Local AI.

---

## 10. Reason Engine

Role:

Generates judgement reasons.

Example:

"Recent volume growth and RSI recovery occurred together, increasing the likelihood of a positive flow."

---

## 11. Knowledge Distillation

GPT/Gemini judgement results are recorded in the Trading Journal.

Local AI learns from the Journal.

Goal:

Local AI absorbs the knowledge accumulated by cloud AI.

---

## 12. Cost Strategy

Initial phase:

Use GPT/Gemini.

Middle phase:

Use GPT/Gemini + Local AI.

Late phase:

Use Local AI as the center.

Goal:

Minimize cost.

---

## 13. Prohibited Directions

Do not describe the Basic Engine as AI.

Do not describe rule-based calculation results as AI judgement.

Do not generate Intent/Scenario without an AI Output Contract.

Do not generate fake AI Narrative.

---

## 14. Future Sprints

AI-ARCH-02:

Local AI Architecture

AI-ARCH-03:

Unified Trading Journal Schema

AI-ARCH-04:

AI Output Contract v2

AI-ARCH-05:

Knowledge Distillation Pipeline
