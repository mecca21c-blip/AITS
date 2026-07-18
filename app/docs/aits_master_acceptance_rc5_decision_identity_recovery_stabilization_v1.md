# AITS Master Acceptance RC5 Decision Identity / Recovery Stabilization v1

## Scope

This stabilization repairs `MA-20260718-007` and adjudicates `MA-20260718-008` without changing trading, provider-final, authority, guard, or execution policy. Runtime ON and trading tests are excluded. RC5 packaged verification is limited to an OFF first run.

## Canonical decision identity

After Validator success, `AITSValidatedDecisionApplication.resolve_decision_id` establishes one canonical `decision_id` before Effective Policy linkage, Intent construction, ETA/invalidation registration, or Outcome tracking. The provider copies that identity into the decision payload context, Effective Policy linkage metadata, prepared Intent, Co-Pilot metadata, and validated application.

Intent persistence is deferred until identity preflight passes. The initial runtime path requires a started application with confirmed Intent persistence before Runtime Decision or Outcome writes. A mismatched Intent is fail-closed with `intent_decision_id_mismatch`; Runtime/ETA/Invalidation/Outcome registration is not attempted.

Regression fixtures reproduce the RC4 scopes `KRW-ENSO` and `PORTFOLIO` without provider response IDs. Both fixtures prove a single generated canonical identity across Decision, Effective Policy linkage, Intent, Runtime registration, ETA, Invalidation, and Outcome. A mismatch fixture proves zero derived writes.

## Managed Pool recovery adjudication

The RC4 recovery affected only real, manageable holdings (`KRW-BERA`, `KRW-ENSO`), with dust recovery and non-holding promotion both absent. The recovery behavior is protective and remains enabled.

The pre-recovery in-memory pool was empty while persisted rows were available, so the trigger is treated as loader-order state loss rather than a reason to remove holding protection. `_ensure_managed_pool_holdings_included` now restores persisted Managed Pool rows before a non-restore recovery scan. Recovery provenance distinguishes:

- `expected_protective_recovery`: a real manageable holding absent from persisted state;
- `managed_pool_state_loss_recovery`: a persisted holding was missing in memory;
- `unsupported_recovery`: dust, non-holding, or incomplete recovery;
- `no_recovery`: no mutation was required.

## Safety contract

- LOCAL remains Lv1 / `candidate_only`.
- LOCAL final source remains disabled.
- No order is created or submitted by this patch or its regression tests.
- Provider routing and final-action policy are unchanged.
- OrderAdapter, ExecutionBridge, OrderService, DecisionRouter, RiskGuard, and LivePreflight are unchanged.
- Holding protection remains enabled; dust and non-holding promotion remain blocked.

## Acceptance boundary

Static regression PASS advances `MA-20260718-007` and the loader-order correction for `MA-20260718-008` only to `acceptance_retest_required`. Neither defect is closed until a separately approved RC5 packaged Live retest confirms the runtime path. RC5 first-run verification must remain OFF.
