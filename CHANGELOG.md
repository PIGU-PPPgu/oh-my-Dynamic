# Changelog

## 2.0.0 - 2026-06-06

- Added a productization plan in `docs/V2_PRODUCTIZATION_PLAN.md` that defines evidence, eval, and dashboard acceptance criteria.
- Added deterministic quality evals via `eval_runner.py`, `evals/task_suite.json`, and `scripts/run_quality_eval.py`.
- Wired eval help and sample quality scoring into CI and the release checklist without requiring model credentials.
- Updated README, skills, and evidence docs around the v2.0 product path: dynamic workflow + compact evidence + static dashboard + quality eval.
- Kept real 20/50/100-agent swarm evidence as manual smoke runs so default CI stays deterministic and safe.

## 1.9.0 - 2026-06-05

- Split the Codex CLI swarm backend into model, scheduler, artifact, process, CLI, and worker helper modules while preserving `codex_cli_swarm.py` public imports and CLI behavior.
- Unified DAG internals around `TaskStatus` with legacy string input/output compatibility for existing JSON, events, and tests.
- Added static workflow observability dashboards via `workflow_observer.py` and `scripts/render_workflow_observability.py`.
- Added coverage configuration and CI coverage gate for the active v1.9 runtime surface.
- Updated README, skills, release checklist, and hygiene rules for `.codegraph/`, coverage, and v1.9 runtime boundaries.

## 1.8.1 - 2026-06-05

- Added `call_llm()` as the primary multi-provider LLM entrypoint while keeping `call_glm()` as a backward-compatible alias.
- Centralized quality scoring constants in `workflow_config.py` so replan and reducer thresholds no longer duplicate magic numbers.
- Added a visible BrokerGateway warning for unauthenticated loopback mode and documented the gateway auth boundary.
- Clarified the dynamic workflow runtime boundary: `dynamic_workflow.py` orchestrates planner/replanner/reducer rounds, while `codex_cli_swarm.py` executes Codex CLI workers.
- Added a clearer five-minute zero-config demo path in README and refreshed skill examples.

## 1.8.0 - 2026-06-05

- Added unified `WorkflowEvent` streaming for DAG execution, Codex CLI swarm batches, and dynamic workflow planner/replanner/reducer phases.
- Added checkpoint/resume support for `dynamic_workflow.py` with `--run-id`, `--resume`, `--checkpoint-dir`, and automatic batch checkpoint writes.
- Added quality-driven replan support via `completeness_score`, low-score evidence, and reducer recommendations for follow-up quality agents.
- Added lightweight capability routing for DAG nodes through `required_capabilities` and a built-in reviewer capability registry.
- Added `examples/real_repo_review.py` for a real read-only Codex CLI repo review demo, plus compact evidence docs under `docs/evidence/`.
- Updated README, skills, CI, and release gates to present Stable/Beta/Experimental product paths and the v1.8 CLI/App usage flow.

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
