# AITS Master Acceptance RC6 Review Lifecycle Stabilization V1

## Scope

This stabilization closes MA-20260718-009 in the derived AI Review layer. It does not change runtime Outcome writers, provider decisions, orders, risk gates, Authority, Champion, Policy, or Intent.

## Root cause

The generic data-source resolver deduplicates records by `decision_id`. Outcome checkpoints intentionally share a decision identity, so Review generation received the first appended checkpoint while later 15-minute and 1-hour checkpoints were removed before stage selection.

## Contract

- Review generation reads Outcome segments without generic decision-level deduplication.
- `ai_review_checkpoint_selector.py` owns the canonical stage ranks: pending, 5 minutes, 15 minutes, 1 hour, final.
- Selection uses exact decision grouping, valid/evaluated state, stage rank, evaluation time, and deterministic record identity.
- A final Review is created only from an explicit final source.
- Existing higher Review stages cannot be overwritten by a lower stage.
- One active Review remains per canonical Review ID; the atomic repository index points to that record.
- Learning Journal entries record the Review ID, revision, and stage. Existing policy-suggestion user state remains preserved during rebuild.
- Learning eligibility and weight use the selected Review stage. A 1-hour Review uses weight `0.8`.

## RC5 regression evidence

The actual RC5 decision `chatcmpl-E2vkI1yrAKTtP57qJvEXRUVyW7vrw` has evaluated 5-minute, 15-minute, and 1-hour Outcome records. Before the repair its Review was `partial_5m`; deterministic regeneration selects the 1-hour checkpoint and produces `partial_1h` while preserving all three checkpoint identities.

Observe-only regeneration changes the aggregate lifecycle from 856 five-minute and zero one-hour Reviews to 10 five-minute, 32 fifteen-minute, and 817 one-hour Reviews. It creates no final Review without a final source.

## Acceptance boundary

The RC6 packaged test must start OFF, rebuild Review and Learning Journal against an isolated copy of the actual RC5 sources, run OFF Maintenance, and preserve source hashes and Authority/Champion/Policy/Intent. No new live ON run is required or permitted for MA-20260718-009.
