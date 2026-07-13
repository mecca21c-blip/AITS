# AITS Local Provider Outcome Learning v1

## 1. Purpose

Every validated AI decision is registered by `decision_id` for later factual evaluation. The tracker compares LOCAL, external-provider, and final decisions with observed 5-minute, 15-minute, and 1-hour results. It does not create an action, alter an action, or grant execution permission.

## 2. Tracking Contract

Tracked tasks cover position and portfolio management, redecision, buy, sell, rotation, and managed-pool promotion decisions. Tracked actions are wait, hold, buy, add, sell, reduce, rotate, take profit, and stop loss.

Each record preserves canonical task and scope, session, parent decision, payload and feature-manifest hashes, LOCAL and external decisions, final provider source, reason, confidence, ETA, execution metadata, and checkpoint state. Registration is idempotent by `decision_id`.

## 3. Checkpoint Scheduler

The runtime scheduler registers 5-minute, 15-minute, and 1-hour checkpoints when a validated decision is recorded. Due checkpoints use only current market, normalized-holdings, and portfolio SSOT values supplied by the runtime. A checkpoint missed while the app is closed may be evaluated late after restart. Missing factual sources produce `data_unavailable`; no price, valuation, PnL, fill, or provider result is invented.

Checkpoint states are `pending`, `evaluated`, `skipped`, or `expired`. Final outcome is produced only after all scheduled checkpoints leave pending state.

## 4. Retrospective Classification

Outcome labels are retrospective learning evidence, never trading thresholds. Buy and add outcomes measure post-decision movement. Sell, reduce, take-profit, and stop-loss outcomes measure post-decision avoidance or early-exit evidence. Wait and hold outcomes distinguish stable waiting, avoided loss, and possible opportunity cost. Rotation outcomes require both held-symbol and candidate observations; otherwise they remain inconclusive.

## 5. Provider Comparison

Provider comparison records whether LOCAL and external actions agreed, which provider the final decision followed, whether an external call changed action or risk level, and whether observed evidence suggests that call was useful or possibly unnecessary. These fields support later route-policy research; they do not automatically change provider routing.

## 6. Opportunity Cost

When actual candidate and held-symbol sources are available, records retain candidate movement, held-symbol movement, opportunity-gap change, missed-move evidence, and avoided-drawdown evidence. Not buying is not automatically a failure. The original AI reason and data quality remain part of the learning record.

## 7. Dataset Writers

Runtime state is stored under `data/ai_decision_training/outcome_tracking_state.json`. Evaluated checkpoint records append to `outcome_records.jsonl`; provider comparisons append to `provider_comparison_outcomes.jsonl`. These are runtime data and are not commit targets.

`safe_for_local_training` requires a payload hash, final action, usable outcome label, and acceptable factual source quality. `data_unavailable` records remain audit evidence but are not marked safe for training.

## 8. Execution Link

When a real submitted order is reconciled, the post-order coordinator links request status, actual submission, reflected position, and portfolio after-state to the matching decision. The tracker does not submit orders and does not modify Router, RiskGuard, LivePreflight, ExecutionBridge, OrderService, or OrderAdapter behavior.

## 9. User Visibility

`OutcomeReasonTimeline` writes safe Korean result summaries to LIVE LOG and the status surface. It exposes checkpoint meaning and evaluation reasons without raw prompts, account bodies, provider secrets, or snake-case event dictionaries.

## 10. Completion Summary

`local-provider-outcome-learning-v1-summary --observe-only` checks tracking, scheduler, provider comparison, classifiers, opportunity cost, writers, UI visibility, safety boundaries, and compatibility with LOCAL-first cost guard and Live Operating Cycle v1. Runtime event counts are reported separately from structural readiness so a newly started session is not mistaken for missing implementation.
