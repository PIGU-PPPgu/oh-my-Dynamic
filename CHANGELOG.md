# Changelog

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
