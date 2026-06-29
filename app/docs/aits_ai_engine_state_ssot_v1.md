# AITS AI Engine State SSOT v1

## Purpose

This document defines the user-facing AI engine state contract for AITS run
control. It separates engine selection, applied preview, actual response
provider, active engine, and run readiness.

This policy does not enable orders, AITS ON, live windows, or provider calls by
itself.

## User-Facing Engines

Only these engine names are user-facing:

- `LOCAL`
- `GPT`
- `GEMINI`

`BASIC` is an internal calculation/runtime layer name and must not be shown as a
user active engine. It maps to `LOCAL` for display.

## User-Facing Connection State

The main connection state surface is limited to:

- `연결중`
- `연결됨`
- `연결오류`

Detailed generation proof such as response id, token usage, freshness, fallback,
timeout, or stale status belongs in report/log/detail fields, not the main
connection state label.

## SSOT Layers

- Selected engine: `strategy.ai_provider` and the current session selected
  provider.
- Applied engine: current session preview provider/model.
- Actual provider: provider that produced the latest fresh generation response.
- Active engine for ON gate: derived from the readiness contract.

For GPT/GEMINI, a fresh confirmed provider response keeps active engine equal to
the selected provider. LOCAL is shown as the active engine only when LOCAL is
selected or an explicit fallback occurred.

## ON Gate Contract

The ON gate must use `engine_ready_for_run` and related readiness fields, not
free-form UI text.

Ready for GPT/GEMINI requires:

- selected provider is GPT/GEMINI.
- actual provider matches selected provider.
- fresh current generation is confirmed.
- response id or token usage proof exists.
- fallback is false.

Not ready:

- key/auth only.
- waiting, timeout, failed, stale, or missing generation.
- selected GPT/GEMINI with LOCAL fallback.

ON gate readiness is not order permission. RiskGuard, LiveOrderPreflight,
Unlock, duplicate lock, and guarded-window caps remain mandatory separate gates.

