# AITS Internal LOCAL_ENGINE v1

## Purpose

`AITS_LOCAL_ENGINE` is the in-process decision candidate engine that learns from
validated GPT/Gemini decisions and observed outcomes. It is independent from an
Ollama server, CLI process, model download, or local HTTP port.

This version establishes contracts and offline data recovery only. It does not
grant live authority, submit orders, or replace RiskGuard or LivePreflight.

## Decision Candidate Contract

Schema: `aits_local_engine_decision_candidate.v1`

Required fields:

- identity: `schema`, `engine`, `engine_version`, `task`, `scope`, `created_at`
- decision: `action`, `confidence`, `confidence_calibrated`, `reason_ko`
- safety: `risk_level`, `blockers`, `safe_for_live_decision`, `live_decision_enabled`
- routing: `escalation_required`, `escalation_reason`
- cadence: `eta_seconds`, `eta_policy`, `invalidation_conditions`
- provenance: `evidence`, `teacher_reference`, `training_source`
- gates: `trained_model_required`, `calibration_required`, `fake_decision`

The default and recovery policy remains:

- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `trained_model_required=true`
- `calibration_required=true`
- `fake_decision=false`

An unavailable model returns unavailable metadata. It must not manufacture a
wait decision, confidence, teacher reference, or outcome.

## Head Contracts

- `action_head`: recommends wait, hold, buy, add, sell, reduce, rotate,
  take_profit, or stop_loss from trained evidence.
- `confidence_head`: emits calibrated confidence only when calibration exists.
- `risk_head`: emits risk level and blockers from observed safety evidence.
- `escalation_head`: recommends GPT/Gemini review; it grants no execution right.
- `eta_head`: emits the next review cadence from observed timing evidence.
- `invalidation_head`: emits factual feature conditions requiring redecision.
- `reason_composer`: explains structured evidence in Korean without free-form
  model claims.

Order-like actions require external confirmation until a separately approved
live-authority Goal changes policy. RiskGuard and LivePreflight remain mandatory.

## Teacher Distillation

GPT/Gemini records are teacher evidence, not automatically correct labels. The
distillation key is `decision_id` and links payload hash, LOCAL/external/final
decisions, provider routing, execution result, and evaluated outcome checkpoints.

Only records passing curation and feature quality gates may reach offline
training. Teacher disagreement and external call value remain explicit fields.

## Data Integrity And Recovery

Source data:

- `outcome_records.jsonl`
- `provider_comparison_outcomes.jsonl`
- `outcome_tracking_state.json`

Source files are never deleted or quarantined by recovery. A JSONL line containing
NUL bytes is cleaned in memory only when the remaining bytes decode as one valid
JSON object. Unrecoverable lines are excluded and counted.

Derived datasets, summaries, registry, and calibration files may be regenerated.
Invalid derived files are moved to a timestamped `.corrupt` file before rewrite.
JSON, JSONL, and model artifacts use flush, filesystem sync, validation where
applicable, and atomic replace.

The offline sequence is:

`integrity scan -> curation -> features -> training -> registry -> calibration`

It does not run automatically during live ON operation.

## Ollama Boundary

Ollama adapters are developer-only manual experiments. They are not the internal
LOCAL_ENGINE and are excluded from default live automatic decisions.

- `local_ollama_developer_only=true`
- `local_ollama_auto_generate_enabled=false`
- `local_ollama_auto_generate_on_live_enabled=false`

Changing either auto-generate flag does not remove the developer-only live gate.
Ollama activation requires a separate explicit Goal and stability review.

## Manual Verification

Run:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode internal-local-engine-data-recovery-v1-summary --observe-only
```

This command may regenerate derived offline training artifacts. It does not start
the app, activate live runtime, call providers, or submit orders.

## Curation Provenance Repair v1

The original curation gate treated every payload-manifest critical field as a
training requirement for every task. That incorrectly required
`candidates.opportunity_gap` for position and portfolio decisions. The repaired
contract keeps strict gates but evaluates factual evidence by task:

- Position: quantity, current price, valuation, PnL, portfolio value, and the
  valuation-unit risk observation.
- Portfolio: total assets, available KRW, exposure, remaining cap, and position
  count.
- Candidate/rotation/promotion: opportunity gap plus portfolio and cash context.

Historical outcome source files are read-only. Existing factual state records may
be reclassified by the corrected task contract, but missing values are never
invented or backfilled. Outcome-only orphan records remain excluded when payload
quality or feature context was not persisted.

Future outcome registrations persist the decision task/scope, provider and teacher
source, contract schemas, payload quality, factual evidence summary, task-specific
required/present/missing fields, and a non-authoritative training eligibility
precheck. Checkpoint JSONL output carries the same metadata so state rotation does
not sever provenance again.

Manual verification:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode local-engine-curation-provenance-repair-v1-summary --observe-only
```

## Candidate Observation v1

`aits_local_engine_candidate_observation.v1` records a prediction produced from
the real provider decision payload by the trained in-process LOCAL_ENGINE. It is
an observation record, not a decision authority or alternate order path.

The provider route evaluates the existing LOCAL_MODEL candidate and, only after
the normal final provider decision is selected, stores the candidate with:

- prediction, decision, task, scope, model artifact, and outcome linkage IDs;
- action, confidence, risk, escalation, ETA, invalidation, evidence, and Korean
  reason;
- teacher/final provider, final action/confidence, final reason digest, and cost
  guard result;
- `candidate_only=true`, `applied_to_final_action=false`,
  `safe_for_live_decision=false`, and `live_decision_enabled=false`.

Only successful predictions from a real trained artifact are appended to
`data/local_engine/local_engine_candidate_observations.jsonl`. Unavailable or
rejected predictions produce metadata blockers but no fabricated candidate row.
The append is validated, single-line, flushed, and filesystem-synced.

Future outcome tracking carries `local_engine_prediction_id` and
`local_engine_outcome_linkage_key`. Historical outcome sources are unchanged.
Observation failure cannot fail the provider route or change its final action.

Manual structural verification does not generate a prediction:

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode local-engine-candidate-observation-v1-summary --observe-only
```

### Candidate Schema Preservation

- The original `aits_local_engine_decision_candidate.v1` object remains intact through observation persistence.
- Generic AI validation produces a separate normalized routing decision and `validator_metadata`; it does not replace the LOCAL_ENGINE candidate.
- Writer contract `v2` records attempted/success status, structured blockers, safe error type, prediction ID, and outcome linkage metadata.
- Missing directories are created only when a real candidate is durably appended. No self-test or placeholder observation is generated.
- Runtime summaries fail when a `v2` prediction succeeds but no observation is written; pre-repair gaps remain visible as historical diagnostics.
