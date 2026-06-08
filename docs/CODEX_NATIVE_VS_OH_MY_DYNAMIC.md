# Codex Native Agents vs oh-my-Dynamic

Short version: Codex native agents are the execution runtime. oh-my-Dynamic is a workflow, evidence, benchmark, and policy harness around Codex CLI/App workflows.

Codex native subagents execute the work. oh-my-Dynamic explains, plans, measures, records, and audits the work.

## Comparison

| Dimension | Codex native agents | oh-my-Dynamic |
|-----------|---------------------|---------------|
| Core capability | First-party parallel coding agents, worktrees, cloud/app runtime, official scheduling | Planner/replanner, broker evidence, reducer, benchmark, demo validation |
| Execution isolation | Managed by the official runtime, worktrees, cloud environments, and app surfaces | Current verified path is Codex CLI process swarm; worktree write mode is explicit |
| User experience | Native app experience, fewer setup steps, smoothest direct coding loop | Skill/CLI/docs entrypoints, optimized for reproducibility and external review |
| Result evidence | Codex UI, task records, diffs, and review surfaces | Compact JSON/MD/dashboard evidence suitable for releases, reviewers, and audits |
| Dynamic replanning | Depends on what the official runtime exposes | Explicit planner/replanner rounds, missing coverage, follow-up agents, reducer output |
| Benchmarking | Official workflows do not automatically create project-specific committed benchmark evidence | Deterministic scoring, real smoke records, demo validation, redaction checks |
| Protocol direction | Strong first-party closed-loop experience | Can keep moving toward MCP/A2A-style artifacts, external LLM review, and third-party evaluation |
| Best fit | Build features, fix bugs, refactor, review code directly | Decompose complex work, compare modes, preserve evidence, productize and explain outcomes |

## Product Meaning

This project should not claim that Codex cannot run parallel agents. OpenAI describes Codex as supporting multi-agent workflows with built-in worktrees and cloud environments.

The practical value of oh-my-Dynamic is different:

- It turns a high-level goal into explicit workflow rounds.
- It records why agents were created and what evidence they produced.
- It preserves compact, sanitized artifacts instead of raw prompts or stdout.
- It gives external reviewers concrete benchmark and demo-validation reports.
- It can become a native Codex subagent orchestrator if stable public subagent APIs become available.

## Desired Future Integration

If Codex App or App Server exposes stable native subagent APIs, the best direction is:

1. Planner creates the task graph.
2. oh-my-Dynamic dispatches tasks to Codex native subagents.
3. Broker records events, artifacts, review requests, failures, and dependencies.
4. Replanner adds native follow-up agents when coverage gaps remain.
5. Reducer emits evidence reports, dashboards, and benchmark summaries.

That keeps the official runtime as the execution layer while preserving oh-my-Dynamic's unique value: explainability, measurement, auditability, and shareable proof.
