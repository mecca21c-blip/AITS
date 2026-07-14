# AITS LOCAL Training Feature Pipeline v1

## Purpose

This pipeline converts curated decision-outcome records into a model-neutral feature dataset. It prepares inputs for a future LOCAL ranker, classifier, or rule calibrator. It does not train a model, connect inference to the live runtime, create an action, or authorize an order.

## Source And Outputs

Source:

- `data/ai_decision_training/curated_local_training_records.jsonl`

Atomic regenerated outputs:

- `data/ai_decision_training/local_training_features.jsonl`
- `data/ai_decision_training/local_training_features_excluded.jsonl`
- `data/ai_decision_training/local_training_feature_summary.json`

Runtime data files are not commit targets.

## Feature Record Contract

Schema: `aits_local_training_feature_record.v1`

Each record preserves source identity, task and scope, action, provider source, quality grades, grouped feature vectors, retrospective labels, risk labels, provider-value labels, outcome targets, split assignment, and explicit exclusion reasons.

Feature groups are:

- market
- indicators
- position
- portfolio
- risk
- provider
- opportunity
- time
- data quality

Only allow-listed factual context from the decision payload is retained. Missing source values remain `null`; the pipeline never synthesizes prices, indicators, valuation, PnL, provider results, or outcomes.

## Labels

Action and outcome labels describe historical decisions and measured outcomes. Risk, provider-value, and opportunity labels prepare future supervised analysis. They are not connected to the live decision router and cannot generate a buy, sell, rotate, or other execution action.

`recommended_action_label` is the observed historical final action. It is not a live recommendation.

## Feature Quality Gate

`safe_for_model_training=true` requires:

- the curated source already passed its training gate;
- valid task, scope, action, outcome label, and outcome target;
- required position or portfolio context for the applicable scope;
- provider-value evidence;
- feature quality above F.

Excluded records retain standardized reasons such as `curated_source_unsafe`, `missing_label`, `missing_outcome_target`, `critical_market_feature_missing`, `critical_position_feature_missing`, `critical_portfolio_feature_missing`, and `provider_value_missing`.

This flag is dataset readiness only. It is never an order-safety or execution flag.

## Split Policy

The pipeline uses a deterministic time-based 70/15/15 train, validation, and holdout split when at least 20 safe records exist. Below that threshold all safe rows use `unsplit_insufficient_data`. A decision id appears in only one record and therefore cannot cross split boundaries.

No model training occurs in this pipeline.

## Privacy And Safety

- Raw prompts, API keys, authorization material, and account raw data are not copied.
- Source corruption and duplicate curated ids are counted and skipped.
- No order, guard, preflight, execution, or reconciliation path is modified.
- LOCAL-only order actions remain prohibited without the established external confirmation and safety path.

## Observability

The runtime emits `[AITS][LocalTrainingFeaturePipeline]` events for build start, record build or exclusion, quality gate result, summary completion, and Korean status rendering. The status copy reports feature and exclusion counts and explains when the split is deferred for insufficient data.

Harness mode:

`--mode local-training-feature-pipeline-v1-summary --observe-only`

The summary verifies schema, extraction groups, labels, quality gate, files, split policy, leak checks, and compatibility with curation, outcome learning, LOCAL-first cost guard, and live operating cycle v1.
