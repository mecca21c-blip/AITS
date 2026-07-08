# AITS Live Order Guarded Execution Contract v1

## Purpose

`GuardedExecutionContract` is the observe-only boundary after `LivePreflightPreview`.
It explains why the runtime has not entered ExecutionBridge, OrderService, or
OrderAdapter even though RouterValidation and RiskGuardPreview passed.

## Log Boundary

Prefix:

```text
[AITS][GuardedExecutionContract] event=contract_preview
```

Schema:

```text
aits_guarded_execution_contract_preview.v1
```

Required safety fields:

- `confirm_phrase_required=True`
- `confirm_phrase_matched=False`
- `unlock_required=True`
- `unlock_performed=False`
- `execution_allowed=False`
- `execution_called=False`
- `order_service_called=False`
- `order_adapter_called=False`
- `submitted=0`
- `actual_order=False`
- `next_required_user_action=explicit_live_order_approval_required`

## Classification

If LivePreflightPreview is blocked and GuardedExecutionContract exists, summaries
classify the state as:

```text
first_blocker=live_order_approval_required
next_fix_target=await explicit user approval for guarded 10000 KRW live order goal
```

If LivePreflightPreview is blocked but the contract is missing, summaries report:

```text
first_blocker=guarded_execution_contract_missing
```

## Safety Boundary

This contract must not:

- perform unlock
- auto-match a confirm phrase
- call ExecutionBridge
- call OrderService submit
- call OrderAdapter
- set `order_allowed=True`
- set `real_order=True`
- create actual orders

The next live-order Goal must require explicit user approval before any guarded
execution path can be considered.

## Normal UX Approval Flow

The header ON/OFF area is reserved for runtime state only. Guarded live-order
approval must not add a permanent header button next to ON.

Immediately after ON preflight passes, the UI must show that live monitoring is
active and that the app is waiting for order information. The user must not be
left staring at an unchanged screen while the runtime is waiting for a buy-ready
candidate, AI freshness, Router/RiskGuard/LivePreflight preview, or the guarded
approval contract.

When a `GuardedExecutionContract` preview is available, the app presents the
approval in a separate confirmation dialog or clearly scoped approval panel.
That surface shows the symbol, side, amount, required phrase, phrase input
field, current blocker/status, and the fact that no actual order has been
submitted yet.

The approve action remains disabled until the entered phrase exactly matches the
required phrase. Cancel closes the dialog without unlock or submit.

If no contract is available yet, the visible status must explain the current
waiting reason. This is still a no-submit state: `actual_order=false` and
`submitted=0`.

## 10,000 KRW Guarded One-Shot Execution

The only live submit path opened by this contract is a single market buy for
the current guarded candidate with `amount_krw=10000`.

Required gates:

- exact confirm phrase: `AITS LIVE ORDER {symbol} {SIDE} {amount_krw}`
- one-shot unlock with a short TTL
- RouterValidation preview passed
- RiskGuard preview passed
- LivePreflight apply passed
- `submit_attempt_count=0` and `submitted_count=0`
- per-order hard cap `12000 KRW`
- guarded window cap `20000 KRW`

The UI exposes this through the guarded approval dialog after a
`GuardedExecutionContract` preview is available. Codex validation must not
approve the dialog or run the submit mode automatically.

After one submit attempt, successful or failed, the runtime enters a locked
state. There is no retry, repeat order, automatic averaging down, or loss-based
re-entry in this contract.
