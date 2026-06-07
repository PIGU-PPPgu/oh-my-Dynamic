# oh-my-Dynamic Official Brief

oh-my-Dynamic is an independent prototype for dynamic workflow orchestration around Codex. It is not an OpenAI product and does not use OpenAI, Codex, or ChatGPT marks in its branding.

## Problem

Codex is strong at local code understanding, tool use, and workspace execution. What is still missing from the public App surface is an App-native dynamic workflow fan-out runtime: a supported way for a task to spawn isolated subagents, give them bounded tools and context, stream their events, collect artifacts, and reduce the result.

## What This Project Proves

- Codex CLI process swarms can run real parallel review workers through `codex exec`.
- A planner/replanner loop can add follow-up agents from broker evidence, failures, low-score outputs, and coverage gaps.
- Broker evidence can preserve run ids, agent counts, artifacts, failures, checkpoints, dashboards, and compact public summaries without committing raw prompts/stdout/stderr.
- Adoption gates can be deterministic: `doctor`, safe dry-runs, CI safe examples, coverage, Bandit, and redaction checks.
- Controlled rubric scoring can measure evidence coverage lift, while real Codex CLI evidence separately proves process-swarm execution.

## What This Project Does Not Claim

oh-my-Dynamic does not claim App-native isolated subagents are implemented. The verified large-scale execution path today is Codex CLI process swarm. App-native isolated subagents require Codex App/runtime support for native spawn, sandbox, scheduler, context, tool-permission, event, and artifact interfaces.

## Evidence

- Adoption hardening evidence: `v3.4.0 - Adoption Hardening`
- Visibility release: `v3.5.0 - Visibility And Identity`
- Fixed 100-agent swarm evidence: `docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md`
- Real stability smoke: `docs/evidence/benchmark_v320_real_smoke.md`
- Controlled rubric lift: `docs/evidence/improvement_v311.md`
- Evidence rules: `docs/evidence/README.md`
- Known limits: `docs/KNOWN_LIMITS.md`

## Five-Minute Demo

```bash
python -m doctor --json
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

The first two commands are safe and do not launch real workers. The last two commands require Codex CLI to be installed, logged in, and configured.

## Request To Codex Runtime Owners

If Codex exposes native dynamic workflow primitives, oh-my-Dynamic can act as a concrete contract test and integration prototype. The runtime primitives that would matter most are:

- native subagent spawn with independent context windows
- sandbox and tool-permission policy per subagent
- structured event stream and artifact ownership
- dependency-aware scheduler and bounded parallelism
- reducer handoff contract with failure and checkpoint metadata

The project is designed to keep the boundary explicit: it demonstrates the desired contract without claiming unofficial access to Codex App internals.
