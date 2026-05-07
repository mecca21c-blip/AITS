# AITS AI Operating Status v2

## 1. Current Definition

AITS = AI Trading Operating System.

AITS is not a simple automatic trading bot. The current direction is a state-based AI operating platform that observes symbols, keeps operational context, explains its state, and prepares downstream decisions without directly applying orders.

Core interpretation:

- AI is not a one-shot analyzer.
- AI remembers a symbol and continues judgment from the previous operating state.
- ETA is an expression of observation state, not a fixed countdown command.
- The user should feel that AI is acting as an operator, not just emitting isolated signals.

## 2. Current Pipeline

The current AI operating pipeline is:

```text
Context
→ Prompt
→ Provider Router
→ Shadow Record
→ State Machine
→ State Snapshot
→ UI-ready dict
→ Main UI / Detail Popup
```

Meaning of each stage:

- Context: builds compact market, symbol, position, and operating context.
- Prompt: converts context into provider-facing AI instructions.
- Provider Router: routes the dry-run provider cycle and normalizes provider output.
- Shadow Record: stores suggestion-only AI analysis output.
- State Machine: converts shadow analysis into an operating state.
- State Snapshot: preserves the current and previous AI operating state.
- UI-ready dict: formats state for Korean UI display.
- Main UI / Detail Popup: displays the operating language without applying orders.

## 3. Implemented Modules

Current implemented modules:

- `AIContextBuilder`
- `AIPromptBuilder`
- `AIResponseParser`
- `AIProviderRouter`
- `GPTProviderBridge`
- `GeminiProviderBridge`
- `OllamaProviderBridge`
- `AIStateMachine`
- `format_state_snapshot_for_ui`

State Machine responsibilities:

- Normalize AI operation states.
- Convert `shadow_record.next_action` into state.
- Preserve `previous_state`.
- Produce `AIStateSnapshot`.
- Keep safety metadata such as `suggestion_only=True` and `applied_to_action=False`.

## 4. UI Reflection Status

MAIN ANALYSIS CENTER currently reflects:

- Briefing
- Evidence
- Next action
- ETA
- Scenario
- Operating state

DETAIL POPUP currently reflects:

- AI judgment
- Evidence
- ETA
- Scenario
- Target price
- Risk price
- State line

The main panel is the summary operating briefing. The detail popup is the deeper operating briefing. Both are intended to share the same AI operating language.

## 5. ETA Philosophy

ETA is not a countdown timer.

ETA is a display tool for the current AI observation state. It can change when market conditions change, when confidence changes, or when the AI state transitions.

Examples:

- `관찰 유지 · 30분`
- `관찰 유지 · 1시간 30분`
- `관찰 유지 · 장기 관찰`

The ETA value should be understood as a dynamic observation horizon, not an execution deadline.

## 6. Safety Structure

Current safety defaults:

- `suggestion_only=True`
- `applied_to_action=False`
- `dry_run=True`
- No order application

The current pipeline is display and shadow-state oriented. It does not execute trades, does not apply decisions to orders, and does not connect the state machine to execution.

## 7. Current Disconnected Areas

Currently not connected:

- DecisionRouter real connection
- OrderAdapter real connection
- Real provider live cycle
- Real state persistence

These are intentionally disconnected at this stage. The current implementation prepares operating state language and UI visibility before any execution path is introduced.

## 8. Roadmap

184차:
State persistence skeleton

185차:
AI state history manager

186차:
State-aware provider prompt

187차:
DecisionRouter shadow integration

188차:
Paper trading shadow apply

189차:
Real provider live cycle

190차:
AI autonomous operating cycle

## 9. Operating Philosophy

AITS should feel like an AI operator.

The AI does not merely say buy, sell, or wait. It maintains an operating stance:

- Which symbol is being observed.
- What state it is in.
- Why it is in that state.
- What scenario it expects.
- How long the current observation horizon is.
- Whether the state has changed from the previous state.

This is the difference between a signal bot and an AI operating platform.

The key philosophy:

- AI is not a single-response analyzer.
- AI remembers symbols and continues judgment.
- ETA expresses observation state.
- The user should perceive the AI as an operator.
