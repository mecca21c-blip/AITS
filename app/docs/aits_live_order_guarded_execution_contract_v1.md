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
