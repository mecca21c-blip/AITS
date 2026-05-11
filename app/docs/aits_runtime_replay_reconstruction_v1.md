# AITS Runtime Replay & Reconstruction v1

## Scope

This layer turns runtime snapshots, events, timeline items, and incidents into
replay-only frames and reconstructed state. It does not execute replay.

It never recalls providers, reruns one-shot, writes snapshots, creates UI, or
connects to trading execution.

## Replay Frame

`app/services/ai_runtime_replay_frame.py` defines `AIRuntimeReplayFrame`.

Fields:

- `frame_id`
- `snapshot_id`
- `provider`
- `timestamp`
- `frame_type`
- `title`
- `state`
- `message`
- `metadata`

Frame types include `session`, `observation`, `quality`, `guard`,
`timeline_event`, `incident`, `ui_bundle`, and `persistence_gate`.

Metadata includes `replay_only=True`, `shadow_only=True`, `real_order=False`,
`submitted=0`, and `research_mode=True`.

## Replay Builder

`app/services/ai_runtime_replay_builder.py` builds frame sequences from a
snapshot. It emits frames for session, observation, quality, guard, incident,
timeline event, UI bundle, and persistence gate data when present.

The builder only creates data. It does not perform replay execution.

## Reconstruction

`app/services/ai_runtime_reconstruction.py` reconstructs runtime state from
replay frames.

Reconstructed fields:

- `provider`
- `session_state`
- `observation_state`
- `incident_count`
- `degraded`
- `cooldown_blocked`
- `last_quality_score`
- `last_event`
- `reconstructed_at`
- `metadata`

The reconstruction is derived from frame data only and does not mutate live
runtime state.

## Replay Timeline

`app/services/ai_runtime_replay_timeline.py` converts replay frames into
oldest-first timeline items:

- `time`
- `provider`
- `frame_type`
- `label`
- `state`
- `metadata`

## Replay Summary

`app/services/ai_runtime_replay_summary.py` builds a compact report:

- `total_frames`
- `incidents`
- `degraded`
- `cooldown_blocked`
- `final_state`
- `summary_line`
- `metadata`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` keeps the existing snapshot flow
and attaches:

- `runtime_replay_ready`
- `runtime_replay_frames`
- `runtime_replay_timeline`
- `runtime_reconstruction`
- `runtime_replay_summary`

This is attach-only. It does not recall providers, save snapshots, execute
orders, modify actions/confidence, create UI, or start background loops.

## Safety Contract

The replay layer must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

It must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order API. It
must not alter `DecisionRouter`, import PySide6, modify `app/ui/*`, auto-run
providers, perform provider failover, or execute replay side effects.
