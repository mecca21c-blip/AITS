# AITS AI Runtime Guard Layer v1

## 1. Purpose

The AI Runtime Guard Layer protects live provider one-shot diagnostics from unstable runtime conditions before they can affect research output.

It covers:
- timeout policy
- retry policy
- cooldown state
- provider health state
- compact guard report
- one-shot harness attach-only integration

This is not a real trading connection.

## 2. Safety Contract

Always fixed:
- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`

Never allowed:
- OrderAdapter calls
- ExecutionBridge calls
- Upbit order API calls
- DecisionRouter action changes
- automatic live provider loops
- background trading loops
- multi-provider auto-run
- automatic paid-provider failover

## 3. Timeout Guard

`ProviderTimeoutGuard` defines policy only.

Default total timeout:
- openai: 20 seconds
- gemini: 20 seconds
- ollama: 45 seconds
- unknown: 10 seconds

The guard does not sleep, wait, or call providers.

## 4. Retry Policy

`ProviderRetryPolicy` decides whether retry would be allowed.

Rules:
- Auth, Permission, InvalidKey: no retry
- Timeout, RateLimit, Temporary: limited retry allowed
- JSON parse or schema errors: recovery first, no provider retry
- attempts at or above max retries: no retry

The policy does not execute retries.

## 5. Cooldown Manager

`ProviderCooldownManager` is memory-only.

It can:
- mark provider failure
- clear cooldown
- check blocked state
- return cooldown state
- build summary

It does not persist files or call external APIs.

## 6. Health Monitor

`ProviderHealthMonitor` tracks recent provider status in memory.

Rules:
- success sets healthy=True
- failure can set healthy=False
- failure_count >= 3 sets degraded=True
- no automatic failover is performed

## 7. Guard Report

`ProviderGuardReportBuilder` compacts timeout, retry, cooldown, and health into:
- provider
- runtime_allowed
- cooldown_blocked
- retry_allowed
- degraded
- timeout_sec
- reason

The report is attach-only and must not alter action, confidence, or order flow.

## 8. One-shot Harness

`LiveProviderOneShotHarness` attaches:
- timeout_policy
- retry_decision
- cooldown_state
- health_status
- guard_report
- guard_ready
- runtime_allowed
- cooldown_blocked
- degraded
- retry_allowed
- timeout_sec
- guard_reason

If cooldown or degradation blocks runtime, live calls are not allowed and dry-run or safety fallback is used.

## 9. Current Limits

The layer does not:
- run providers automatically
- retry calls automatically
- fail over to another provider
- persist runtime state
- submit orders

## 10. Roadmap

- Guard event history
- Provider degradation timeline
- Cooldown UI indicator
- One-shot CLI diagnostics
- Manual live one-shot audit logs
