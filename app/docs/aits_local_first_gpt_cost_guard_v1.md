# AITS LOCAL-First GPT/GEMINI Cost Guard v1

## Purpose

AITS asks a configured localhost AI provider for every supported decision before considering an external provider. BASIC remains a fact and payload builder; it is not the LOCAL AI decision maker.

The common decision path is:

1. BASIC builds the position, portfolio, candidate, constraint, and runtime context.
2. LOCAL evaluates the same validated decision contract first.
3. The escalation policy evaluates actionability, confidence, payload quality, safety blockers, post-order context, and the selected provider policy.
4. The external provider cost guard evaluates availability, cooldowns, duplicate payloads, hourly and daily limits, order-related hourly limits, and estimated daily cost.
5. An allowed GPT or GEMINI response is validated before it can become the final AI decision.
6. Router, RiskGuard, LivePreflight, and Execution remain mandatory downstream boundaries.

## LOCAL Decision Contract

LOCAL inference uses the configured localhost URL and model. It records availability, action, confidence, Korean reason, ETA, risk notes, invalidation conditions, payload hash, quality, blockers, and generation time. A deterministic BASIC fallback is not represented as a LOCAL AI response.

LOCAL `wait`, `hold`, and non-actionable review results may be retained without an external call when confidence and payload quality are sufficient. LOCAL order-capable actions require a valid external confirmation in v1. Without that confirmation, the final decision is a safe wait with an explicit blocker and no execution amount.

## Escalation Policy

Escalation is considered for low LOCAL confidence, order-capable actions, user-selected external provider policy, and post-order replanning. It is blocked when critical payload quality or a live safety blocker makes external confirmation inappropriate. The original LOCAL result is retained for comparison even when an external result becomes final.

## Cost Guard

Each external provider has an enabled state and API key check. Shared settings provide request cooldown, duplicate payload cooldown, hourly and daily call limits, order-related hourly call limit, estimated token ceiling, and estimated daily cost limit. Provider-specific environment overrides may tighten these values.

The guard records only safe metadata: provider, task, scope, payload hash, counts, cooldown remaining, estimated cost, limit, and blocker. It never logs an API key or raw prompt.

## Decision Routing

A validated external response may become the final provider source. If an external request is blocked or fails, a safe LOCAL wait/hold may remain final. A LOCAL order-capable action cannot remain executable without external confirmation. Neither LOCAL nor an external provider bypasses the AI validator, Router, RiskGuard, LivePreflight, or Execution boundary.

## Provider Comparison Training

Decision training records keep LOCAL action/confidence/reason, escalation reason, external requested/called/blocked state, cost guard result, external action/confidence, final provider source, and final decision reason. Existing execution and outcome placeholders remain linked so later LOCAL-versus-external value analysis can be added without changing the live decision contract.

## Operator Visibility

LIVE LOG and the status summary use Korean reason messages for LOCAL-first selection, external confirmation, disagreement, and cost-guard blocking. They do not display raw event dictionaries, snake_case fields, API keys, or prompts.

## Completion Check

Use `--mode local-first-gpt-cost-guard-v1-summary --observe-only`. The summary is read-only: it scopes runtime evidence to the target app PID/session, verifies source contracts, and reuses the live operating cycle safety checklist. It does not invoke a provider or trading control.
