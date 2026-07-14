# AITS Local Training Dataset Curation v1

## 1. Purpose

The curation layer converts factual decision-outcome evidence into an allow-listed dataset contract for later LOCAL training work. It does not train a model, change provider routing, create an AI action, or authorize an order.

## 2. Source Contract

The curator reads `outcome_tracking_state.json`, `outcome_records.jsonl`, and `provider_comparison_outcomes.jsonl`. It groups evidence by `decision_id`, merges evaluated checkpoints, and keeps one stable curated record per source decision. Exact duplicate JSONL lines are skipped and counted. Malformed lines are skipped and counted without stopping the remaining dataset.

No prompt body, provider request body, account response, credential, or unrestricted source dictionary is copied. Curated records are assembled from an explicit field allow-list.

## 3. Curated Schema

The record schema is `aits_local_training_curated_record.v1`. It preserves canonical task/scope, payload provenance, provider route, decisions and confidence, risk and safety blockers, actual execution evidence, observed checkpoints, final outcome, learning tags, training gate result, exclusions, and future-route research metadata.

The output files are runtime data:

- `curated_local_training_records.jsonl`
- `excluded_local_training_records.jsonl`
- `curated_local_training_summary.json`

They are not source-control targets.

## 4. Safe-For-Training Gate

A training candidate requires decision and payload identity, valid canonical task/scope/action, final provider provenance, payload quality above D/F, at least one evaluated checkpoint, and a usable factual market, holding, or portfolio source. Submitted orders additionally require reconciliation evidence.

Records are excluded for missing identity, low payload quality, unevaluated or unavailable outcomes, invalid scope/action, missing provider context, unresolved valuation mismatch, missing reconciliation, stale-only evidence, or manual/forced/test provenance. Inconclusive outcomes remain audit evidence and are separated from action learning.

`can_be_used_for` independently identifies eligibility for action, risk, provider routing, opportunity cost, wait/hold, buy/sell, and portfolio research.

## 5. Learning Tags

Action tags distinguish useful waiting, missed opportunity, avoided loss, entry/exit quality, take-profit and stop-loss quality, rotation value, and portfolio waiting. Provider tags distinguish agreement, disagreement, useful external confirmation, unnecessary external calls, LOCAL sufficiency, and blocked-call outcomes. Opportunity tags retain only measured candidate, held-symbol, and portfolio movements.

Tags and scores are retrospective labels derived from observed outcomes. They are not trading thresholds and are never sent directly to Router or execution.

## 6. Dataset Quality Summary

The summary reports source, curated, excluded, duplicate, and corrupted counts; task/action/provider/outcome/tag/exclusion distributions; payload and outcome averages; LOCAL/external agreement; external-call usefulness; cost-guard blocking; and action-group counts.

An empty source produces valid zero-count output files. It does not create a training record or inferred outcome.

## 7. Writer Policy

Curation deterministically rebuilds the two JSONL outputs through temporary files and atomic replacement. This keeps one canonical record per source decision and makes repeated curation idempotent. Record IDs remain stable; `curated_at` and the summary timestamp identify the current build.

## 8. Runtime Integration

The existing outcome scheduler invokes curation after checkpoint events or when the summary does not yet exist. LIVE LOG and the status surface show Korean curated/excluded counts. The curation path does not touch Managed Pool policy, RiskGuard, LivePreflight, DecisionRouter, ExecutionBridge, OrderService, or OrderAdapter.

## 9. Completion Summary

`local-training-dataset-curation-v1-summary --observe-only` checks schema, writers, gate, exclusions, action/provider/opportunity tags, quality summary, leak guards, source contracts, and compatibility with the preceding outcome, provider-cost, and live-cycle Sprints. The summary reads existing files and does not curate or invoke a provider.
