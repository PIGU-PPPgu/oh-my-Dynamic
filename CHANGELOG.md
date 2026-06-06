# Changelog

## 3.0.0 - 2026-06-07

- Migrated implementation modules from root-level `py-modules` into the standard `src/oh_my_dynamic/` package layout.
- Grouped package modules by responsibility: `broker`, `codex`, `runtime`, `protocol`, `evals`, `core`, and `cli`.
- Preserved root-level compatibility facades so imports like `from dynamic_workflow import DynamicWorkflowRuntime` and commands like `python -m dynamic_workflow` keep working for one major version.
- Updated console scripts to point at package CLI entrypoints and moved coverage source tracking to `src/oh_my_dynamic`.
- Added package import/facade compatibility checks, package module help checks, and install-from-target smoke gates for release validation.
- Updated README, skills, CI, and release checklist to document preferred package imports and deprecated root-level shims.

## 2.4.0 - 2026-06-06

- Added public evidence sanitization with `$REPO_ROOT` / `$HOME` normalization and `sanitized: true` metadata for compact evidence outputs and dashboards.
- Added `oh-my-dynamic-doctor` / `python -m doctor` for local install, Codex CLI, marketplace, writable workspace, gateway auth, and evidence redaction checks.
- Added MIT `LICENSE`, `docs/THREAT_MODEL.md`, README trust gates, and release checklist gates for Bandit, doctor, benchmark dry-run, LICENSE, and evidence path scans.
- Added deterministic benchmark fixtures and `scripts/run_benchmark.py` to compare single, fixed swarm, and adaptive workflow modes without launching Codex CLI in CI.
- Added pytest smoke tests under `tests/` while keeping `python test_suite.py` as the compatibility test entrypoint.
- CI now runs pytest smoke, Bandit, benchmark dry-run, doctor, and evidence redaction scans in addition to existing test, coverage, help, and quality eval gates.

## 2.2.0 - 2026-06-06

- Added `ReplanTriggerPolicy`, a deterministic replanner trigger layer for missing coverage, low-score agents, and failed agents.
- Extended `DynamicWorkflowRuntime` traces and checkpoints with `replan_trigger_records` so replanner prompts receive structured trigger evidence.
- Added `--required-coverage` and `--force-missing-coverage` to `scripts/record_adaptive_workflow_evidence.py` for controlled real replanner smoke runs.
- Extended adaptive evidence JSON/Markdown with `replan_triggers`, `missing_coverage`, `low_score_agents`, `followup_agents_requested`, and `followup_agents_generated`.
- Enhanced static observability dashboards with replan trigger summaries, missing coverage, low-score agents, and follow-up budgets.
- Added fake coverage-gap and no-gap regression tests for adaptive replanning behavior.
- Recorded real v2.2 replanner-proof evidence: 8 planner-generated Codex CLI agents completed, trigger policy detected the forced `replanner-proof` coverage gap, and 2 replanner-generated follow-up agents completed with 0 failures.

## 2.1.1 - 2026-06-06

- Shortened the README first screen with a `Use It Now` entry table for App skill, CLI adaptive workflow, fixed swarm, and GitHub Releases.
- Clarified the core App-native boundary: Codex App native isolated subagents depend on Codex App runtime exposure, while the current proven large-scale path is Codex CLI process swarm.
- Fixed the 20-agent Codex CLI smoke command and documented the fixed swarm versus adaptive workflow distinction.
- Expanded evidence docs with a reproducible real adaptive workflow command, dry-run limitations, and dashboard sensitivity guidance.
- Marked the v2 productization plan as historical so reviewers use README, evidence docs, and release notes for current v2.1+ entrypoints.

## 2.1.0 - 2026-06-06

- Added adaptive dynamic workflow evidence recording via `scripts/record_adaptive_workflow_evidence.py`, with dry-run and real Codex CLI modes.
- Made `dynamic_workflow.py` default to read-only sandboxing for planner, replanner, and worker agents while supporting reproducible `--codex-extra-arg` overrides.
- Changed the lower-level Codex CLI swarm agent default sandbox to read-only and exposed `--sandbox` on the swarm CLI.
- Added round-aware evidence fields that distinguish planner-generated agents, replanner-generated agents, reducer recommendations, stop reason, and terminal state.
- Enhanced static observability dashboards with a round timeline for dynamic workflow traces and checkpoints.
- Updated README, skills, evidence docs, and release checklist for the v2.1 adaptive workflow path and GitHub Release requirements.

## 2.0.1 - 2026-06-06

- Recorded real Codex CLI smoke evidence for 5-agent repo review plus 20/50/100-agent read-only swarms, including compact JSON summaries and a static dashboard for the 5-agent run.
- Added `--codex-extra-arg` support to the real repo review and swarm evidence scripts so local Codex CLI config overrides such as `service_tier="fast"` and `model_reasoning_effort="low"` can be captured reproducibly.
- Hardened evidence scripts to launch review workers in read-only sandbox mode and to keep raw prompts/stdout/stderr under `.orchestry/`.
- Fixed real repo review evidence so real runs include actual sample findings and separate Codex CLI trace risk from reducer risk.
- Updated the plugin marketplace template and installer for Codex CLI 0.128 compatibility with `authentication: "ON_USE"` and a relative local plugin path.

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
