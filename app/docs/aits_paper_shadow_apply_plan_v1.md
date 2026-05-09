# AITS Paper Shadow Apply Plan v1

## 1. Purpose

Paper Shadow Apply is a design for applying AI Shadow results only to virtual positions.

The purpose is to:

- Verify AI judgment quality.
- Compare provider tendencies.
- Validate AI strategy behavior before any real order path.
- Analyze long-term AI reliability.

Paper Shadow Apply is not live trading. It is a virtual evaluation layer.

## 2. Core Principles

Core rules:

- Never place real orders.
- Never call Upbit order APIs.
- `applied_to_action=False` may remain unchanged.
- Shadow apply changes only virtual state.
- Keep `submitted=0`.

The system may observe what would have happened, but it must not submit, route, or execute a real order.

## 3. Current Structure

Current AI shadow visibility structure:

```text
AI Shadow
→ State Machine
→ Shadow History
→ Provider Stats
→ RouterSummary
```

This structure observes AI output and provider tendencies without applying them to action or confidence.

## 4. Planned Additional Structure

Planned paper trading structure:

```text
AI Shadow
→ Paper Shadow Apply Engine
→ Virtual Position
→ Virtual PnL
→ Shadow Performance Stats
```

The Paper Shadow Apply Engine will interpret AI Shadow output into virtual position changes only.

## 5. Paper Position Model Draft

Required fields:

- `symbol`
- `provider`
- `entry_price`
- `current_price`
- `qty_virtual`
- `entry_time`
- `exit_time`
- `pnl_pct`
- `pnl_krw`
- `state`
- `scenario`
- `eta_minutes`
- `closed`

This model represents a simulated position. It must not be confused with real holdings or exchange balances.

## 6. Shadow Apply Rules

Initial virtual apply rules:

- `next_action=buy` → virtual entry
- `hold/watch` → virtual hold
- `sell/remove` → virtual close
- `reduce` → virtual partial reduce
- `long_watch` → monitoring only

These rules update paper state only. They do not create buy/sell requests and do not alter live router decisions.

## 7. Safety Contract

Safety contract:

- Real orders are forbidden.
- Do not pass paper shadow output to `OrderAdapter`.
- Do not pass paper shadow output to `ExecutionBridge`.
- `applied=False` may remain unchanged.
- `dry_run` can coexist with paper shadow apply.

Paper Shadow Apply is an analysis mechanism. It is not an execution mechanism.

## 8. Future Expansion

Possible future analysis:

- Provider-level virtual winrate
- Scenario-level performance
- Confidence reliability
- Ensemble backtesting
- AI survival analysis

The long-term goal is to understand which providers and scenarios produce durable virtual performance before considering any live use.

## 9. Implementation Roadmap

198차:
Paper shadow result model

199차:
Paper shadow apply skeleton

200차:
Live provider one-shot test plan

201차:
Virtual PnL tracker

202차:
Provider reliability score
