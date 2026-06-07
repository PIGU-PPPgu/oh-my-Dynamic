# Outreach Pack

Use this when sharing oh-my-Dynamic with external reviewers, Codex/OpenAI runtime owners, or technical communities. Do not imply official affiliation.

## 150-Word Summary

oh-my-Dynamic is an independent dynamic workflow prototype for Codex. It demonstrates planner/replanner orchestration, Codex CLI process swarms, broker evidence, strict readiness checks, and controlled evaluation reports. The verified large-scale path is `codex exec` process fan-out, not App-native isolated subagents. The project is intentionally explicit about that boundary: it does not claim unofficial access to Codex App internals. Instead, it gives a concrete, testable contract for what a native Codex dynamic workflow runtime could expose: isolated subagent spawn, per-agent sandbox/tool policy, event streams, artifact ownership, checkpoint metadata, and reducer handoff.

## 500-Word Technical Summary

oh-my-Dynamic explores what dynamic workflows could look like in Codex if the runtime exposed native subagent orchestration primitives. The current implementation does not depend on private Codex App APIs. Its verified large-scale backend is a Codex CLI process swarm: the orchestrator launches multiple `codex exec` workers, captures worker output, ingests structured envelopes into a broker, and reduces evidence into compact summaries.

The project is built around three concepts. First, planner/replanner orchestration: an initial planner decomposes a high-level goal into agents, and a replanner can add follow-up agents based on failures, low-score outputs, missing coverage lanes, and broker evidence. Second, evidence discipline: worker traces, artifacts, failures, dashboards, checkpoints, and compact Markdown/JSON records are separated from raw prompts/stdout/stderr. Public evidence is sanitized and bounded. Third, adoption hardening: new users can run safe dry-runs without Codex CLI workers, then use `doctor --strict-real-codex` to verify local `codex exec` readiness before launching real workers.

The project is not claiming that Codex App-native isolated subagents are implemented. It documents that capability as runtime-gated and experimental. If Codex App exposes native spawn, sandbox, scheduler, tool permission, event, and artifact primitives, oh-my-Dynamic can serve as a concrete contract test for that surface. Until then, the real scalable path is Codex CLI process fan-out.

Useful evidence includes the v3.4 adoption hardening release, 100-agent fixed swarm evidence, a real stability smoke, controlled rubric lift reports, and the known-limits/threat-model docs. The most relevant ask for runtime owners is not endorsement, but a clear native workflow contract that lets plugin authors safely fan out isolated subagents and reduce their artifacts.

## GitHub Issue / Discussion

Title: Proposal: native dynamic workflow primitives for Codex App

Body:

oh-my-Dynamic is an independent prototype showing how planner/replanner workflows, bounded fan-out, broker evidence, and reducer handoff can work around Codex today using Codex CLI process swarms. It does not claim App-native isolated subagents are implemented.

The useful request is a native Codex App/runtime contract for:

- isolated subagent spawn
- per-agent sandbox and tool permissions
- event streams and artifact ownership
- dependency-aware bounded parallelism
- reducer handoff with failure/checkpoint metadata

Reference brief: `docs/OFFICIAL_BRIEF.md`.

## Email

Subject: Independent Codex dynamic workflow prototype and runtime contract proposal

Hi,

I built oh-my-Dynamic as an independent prototype for dynamic workflow orchestration around Codex. It uses Codex CLI process swarms for verified large-scale execution and keeps App-native isolated subagents clearly marked as runtime-gated, not implemented.

The project may be useful as a concrete contract test for future Codex runtime primitives: isolated subagent spawn, sandbox/tool policy, event streams, artifact ownership, scheduler semantics, and reducer handoff.

Brief: `docs/OFFICIAL_BRIEF.md`
Repo: https://github.com/PIGU-PPPgu/oh-my-Dynamic

## X Thread

1. Built an independent Codex dynamic workflow prototype: oh-my-Dynamic.
2. Verified large-scale path today: Codex CLI process swarms via `codex exec`.
3. Core loop: planner -> parallel workers -> broker evidence -> replanner -> reducer.
4. Boundary is explicit: this does not claim App-native isolated subagents are implemented.
5. The ask: native Codex runtime primitives for subagent spawn, sandbox/tool policy, events, artifacts, scheduler, reducer handoff.
6. Brief: `docs/OFFICIAL_BRIEF.md`

## Hacker News Style

Show HN: oh-my-Dynamic, an independent dynamic workflow prototype for Codex

I built a prototype that explores planner/replanner workflows around Codex using Codex CLI process swarms. It focuses on evidence discipline, strict readiness checks, and clear boundaries. It does not claim to implement Codex App-native isolated subagents; instead it documents what runtime primitives would be needed.

## What To Send To OpenAI/Codex Team

Send:

- `docs/OFFICIAL_BRIEF.md`
- `docs/DEMO_SCRIPT.md`
- `docs/KNOWN_LIMITS.md`
- `docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md`
- Release link for `v3.5.0`

Do not send raw `.orchestry/` traces, prompts, stdout, stderr, or private local paths.
