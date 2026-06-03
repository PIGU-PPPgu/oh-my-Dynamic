# Codex Native Dynamic Workflows Proposal

This document describes the capability gap oh-my-Dynamic is trying to close:
Codex should be able to run native dynamic workflows with sandboxed parallel
subagents, similar in spirit to Claude Code Dynamic Workflows.

## Problem

Codex App skills can guide the current assistant to decompose and reason in a
multi-agent style, but they cannot currently request the App runtime to:

- fan out into tens or hundreds of internal subagents,
- give each subagent an isolated context window,
- assign per-agent tool permissions,
- run each subagent inside an isolated sandbox,
- schedule a DAG natively,
- stream progress, artifacts, budgets, and audit traces back to the App,
- synthesize the result through a runtime-level reducer.

That difference matters. Prompt-level orchestration can improve reasoning
structure, but it cannot unlock the same throughput, isolation, observability,
or reliability as runtime-level subagents.

## Desired Runtime Capability

Codex App should expose a native workflow runtime with primitives like:

```python
workflow = codex.workflow.create(
    goal="Review this repository for security, correctness, and test gaps",
    max_agents=64,
    sandbox="isolated",
    budget={"tokens": 1_000_000, "wall_time_s": 900},
)

planner = workflow.spawn_agent(
    role="planner",
    tools=["read", "codegraph"],
    context="root task",
)

tasks = planner.decompose(dag=True)

workers = workflow.fan_out(
    tasks,
    per_agent={
        "context_window": "isolated",
        "sandbox": "worktree",
        "tools": "least_privilege",
    },
)

review = workflow.reduce(
    workers,
    reducers=["reviewer", "synthesizer"],
    require_evidence=True,
)
```

The exact API does not need to look like this. The important pieces are native
fan-out, isolated subagents, explicit tool grants, DAG scheduling, review, and
observable synthesis.

## Proposed Minimum Viable Runtime

### Phase 1: Native Subagent Spawn

- `spawn_subagent(role, prompt, tools, sandbox_policy)`
- separate context window per subagent
- structured result: `status`, `summary`, `artifacts`, `errors`, `metrics`
- hard limits: token budget, wall-clock time, tool budget

### Phase 2: DAG Execution

- runtime object for nodes and dependencies
- concurrent scheduling where dependencies permit
- failure policy: retry, skip, replan, or abort
- progress events visible in Codex App

### Phase 3: Sandboxed Tool Grants

- per-agent least-privilege tools
- per-agent filesystem scope
- optional per-agent git worktree
- trace of every tool call and artifact

### Phase 4: Review and Synthesis

- reducer agents with access to worker summaries and selected artifacts
- LLM-as-judge review pass
- final answer with source/task attribution
- exportable workflow trace

## How oh-my-Dynamic Maps to This

| Runtime target | Current prototype module |
|----------------|--------------------------|
| DAG task model | `dag.py`, `task.py` |
| parallel scheduling | `DAGExecutor`, `team_engine.py` |
| dynamic replan | `dynamic_replan.py` |
| stop conditions | `stop_conditions.py` |
| result synthesis | `synthesis.py` |
| token accounting | `token_tracker.py` |
| sandbox experiments | `worktree.py`, `tea_protocol.py` |
| ecosystem bridge | `protocol_adapters.py` |
| installable App UX | `codex-plugin/skills/*` |

oh-my-Dynamic is not claiming Codex App can already do all of this natively.
It is a working prototype and specification surface for the runtime capability
Codex should grow.

## Evaluation Criteria

A Codex native dynamic workflow implementation should be judged by:

1. **Fan-out scale**: can it safely run 10, 50, 100+ subagents?
2. **Isolation**: does each agent have separate context, tools, and sandbox?
3. **Correct scheduling**: are dependencies respected and parallel branches used?
4. **Observability**: can the user inspect DAG, status, logs, artifacts, and costs?
5. **Review quality**: does a reducer catch worker failures and contradictions?
6. **Replan behavior**: can the system add/drop/modify tasks without losing completed work?
7. **Security**: are tool grants least-privilege and auditable?
8. **User experience**: can the user trigger it from Codex App with one instruction?
9. **Portability**: can workflows expose MCP/A2A compatible surfaces?
10. **Reproducibility**: can a workflow trace be replayed or exported?

## Why This Belongs in Codex

Codex already has strong local workspace awareness, code execution, git context,
and developer-oriented interaction patterns. Native dynamic workflows would let
Codex use those strengths at scale:

- broad code review across many files,
- parallel bug investigation,
- independent security, correctness, performance, and UX passes,
- large repository migration planning,
- multi-perspective design and architecture review,
- evidence-backed synthesis instead of single-threaded exploration.

## Non-Goals

- Do not fake native parallel subagents through prompt formatting alone.
- Do not grant all tools to every worker by default.
- Do not hide worker failures behind a polished final summary.
- Do not require external model API keys for normal Codex App usage.

## Current Status

Available now:

- Codex App zero-config skill mode, using the current App model in-chat.
- Optional local Python engine with external provider APIs.
- Mock demos that run without API keys.
- MCP-style and A2A-style adapter payloads.

Not available yet:

- Codex App native runtime fan-out.
- App-managed isolated subagent sandboxes.
- Runtime-level DAG visualization and trace.
- Official subagent spawn API.

That gap is the reason this project exists.
