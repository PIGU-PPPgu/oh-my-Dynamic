# Changelog

## 1.7.1 - 2026-06-04

- Added planner/replanner observability for `dynamic_workflow.py`: durable worker dirs, prompt/stdout/stderr capture, broker start/complete/failure traces, and failure artifacts.
- Added `--planner-timeout-s` so blocking planner/replanner `codex exec` calls fail with evidence instead of hanging silently.
- Added regression coverage for planner timeout evidence capture.

## 1.7.0 - 2026-06-04

- Added `dynamic_workflow.py` with Codex CLI planner/replanner rounds, max round/agent limits, shared broker thread tracing, and broker-aware reduction.
- Added `broker_reducer.py` so final synthesis reads artifacts, failures, dependency metadata, review responses, and worktree diff artifacts instead of summaries only.
- Added explicit worktree patch mode for Codex CLI swarm workers, including per-agent branches, isolated worktree paths, and diff artifacts without auto-merge.
- Tightened AgentBroker/A2A gateway protocol fields with artifact thread/task ids, cursor snapshots for task events, and capability discovery metadata.
- Added compact manual evidence recording for real 20/50/100 agent swarms via `scripts/record_swarm_evidence.py`.
- Updated Codex App skills and README with a one-line dynamic workflow trigger and safer default routing.
- Expanded tests for planner JSON validation, dynamic workflow limits, worktree isolation, reducer evidence, protocol compatibility, gateway cursors, and CLI help.

## 1.6.0 - 2026-06-04

- Added a real Codex CLI swarm backend that launches independent `codex exec` workers and ingests JSON envelopes into AgentBroker.
- Hardened Codex CLI swarm execution with stdin prompts, streamed stdout/stderr files, durable `manifest.json` / `trace.json`, default workdir retention, and optional total timeout.
- Unified broker workflow lifecycle events so CLI/App bridge workflows can reach terminal A2A-style states.
- Added per-agent gateway actor tokens, inbox authorization, and idempotent broker agent registration.
- Added preflight envelope validation before broker ingest to avoid partial writes on malformed artifact refs or target agents.
- Made Codex App plugin install docs portable across clone locations and changed the plugin marketplace auth policy to `NONE`.
- Added a real Codex CLI swarm review demo and release/smoke verification docs.

## 1.5.0 - 2026-06-04

- Added the Codex App subagent bridge contract and plugin skills.
