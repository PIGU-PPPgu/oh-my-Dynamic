# Codex Native Dynamic Workflows Proposal

This document describes the capability gap oh-my-Dynamic is trying to close:
Codex should be able to run native dynamic workflows with sandboxed parallel
subagents, similar in spirit to Claude Code Dynamic Workflows.

Important default for Codex App: when Codex App exposes subagent tools/runtime
to a plugin or skill, oh-my-Dynamic should use that **Codex App internal
subagent backend** by default. Those subagents should inherit the current Codex
App internal LLM, so normal App usage does not require `OPENAI_API_KEY` or any
other external provider key.

## Problem

Codex App skills can guide the current assistant to decompose and reason in a
multi-agent style. When App-native subagent tools/runtime are available, the
right behavior is to use real Codex subagents instead of prompt-only worker
simulation. The runtime-level capabilities that matter are:

- fan out into tens or hundreds of internal subagents,
- give each subagent an isolated context window,
- assign per-agent tool permissions,
- run each subagent inside an isolated sandbox,
- schedule a DAG natively,
- let subagents collaborate through a controlled message/artifact broker,
- stream progress, artifacts, budgets, and audit traces back to the App,
- synthesize the result through a runtime-level reducer.

That difference matters. Prompt-level orchestration can improve reasoning
structure, but it cannot unlock the same throughput, isolation, observability,
or reliability as runtime-level subagents. A local Python process also should
not be described as directly calling the Codex App internal LLM; App-native LLM
inheritance, isolated sandboxes, tool permissions, scheduling, and trace capture
belong to the Codex runtime.

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
fan-out, isolated subagents, internal LLM inheritance from the current Codex App
session, explicit tool grants, DAG scheduling, review, and observable synthesis.
From a plugin/skill user's perspective, this path should be API-key free.

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

### Phase 5: Controlled A2A Broker

- direct and broadcast messages with explicit sender/receiver metadata
- artifact publication and durable artifact references
- task handoff events between agents
- review request / review response events
- append-only audit trace exportable as an A2A-style task snapshot
- parent orchestrator policy over what can be shared, reviewed, or forwarded

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
| A2A/message broker | `agent_broker.py` |
| ecosystem bridge | `protocol_adapters.py`, `agent_broker.py` |
| installable App UX | `codex-plugin/skills/*` |

oh-my-Dynamic separates three layers:

1. **Codex App internal subagent backend**: when Codex App provides subagent
   tools/runtime, the plugin/skill should default to real App-native subagents.
   These subagents inherit the current Codex App internal LLM and do not need
   external API keys.
2. **Plugin-level orchestration**: when that backend is not available, the skill
   can still structure the current Codex App conversation into planner, worker,
   reviewer, replan, and synthesis passes. This is useful, but it is not
   runtime-level isolated subagents.
3. **Local Python runtime prototype**: `native_runtime.py` gives executable
   fan-out, sandbox directory, tool grant, trace, and reducer behavior for
   testing the proposed contract. It does not directly call Codex App's internal
   LLM; it uses the `llm_fn` passed by the caller, usually mock demos or
   configured external providers.

`agent_broker.py` is the bridge between these layers. Codex App subagents should
normally collaborate through the parent orchestrator and this broker contract:
messages, artifacts, handoffs, review requests, and traces are explicit and
auditable. Local isolated workers can write the same broker events during
`native_runtime.py` execution. Direct peer-to-peer subagent messaging is a
runtime concern; the project contract prefers controlled A2A-style collaboration
over hidden side channels.

The project is therefore both an App plugin UX and a working specification
surface for capabilities that should remain owned by the Codex runtime.

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
11. **Inter-agent communication**: can agents hand off work, reference artifacts,
    request review, and leave an audit trail without uncontrolled context bleed?

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
- Do not route around an available Codex App internal subagent backend; if the
  App provides subagent tools/runtime, use real Codex subagents by default.
- Do not grant all tools to every worker by default.
- Do not hide worker failures behind a polished final summary.
- Do not require external model API keys for normal Codex App usage.
- Do not claim that a local Python process can directly call the Codex App
  internal LLM.
- Do not claim the local runtime prototype provides App-native isolated
  sandboxes, tool permissions, or scheduler semantics; those are Codex runtime
  responsibilities.

## Current Status

Available now:

- Codex App zero-config skill mode.
- Codex App internal subagent backend selection, when the App environment
  exposes subagent tools/runtime to the plugin or skill. In that mode, real
  Codex subagents inherit the current Codex App internal LLM and do not require
  external API keys.
- Plugin-level fallback orchestration using the current App model in-chat when
  the App-native backend is unavailable.
- Optional local Python engine with external provider APIs.
- Local `native_runtime.py` prototype for sandboxed fan-out with 10/50/100+
  isolated workers, per-worker context, sandbox directories, tool grants, trace,
  and reducer synthesis.
- Local `agent_broker.py` for A2A-style messages, artifacts, task handoffs,
  review requests, and audit trace snapshots.
- `native_runtime.py` can write worker outputs, final answers, and completion
  events into `AgentBroker`.
- Mock demos that run without API keys.
- MCP-style and A2A-style adapter payloads.

Not available yet:

- A project-owned way for local Python code to call the Codex App internal LLM
  directly.
- App-native isolated subagent sandboxes, per-agent tool permissions, scheduler,
  visualization, and trace unless Codex runtime exposes those facilities in the
  current App environment.
- A standalone replacement for the official Codex subagent spawn API.
- App-native peer-to-peer subagent messaging independent of parent orchestrator
  policy, unless Codex runtime exposes and governs that capability.

That gap is the reason this project exists.

## Local Runtime Prototype

The local prototype is intentionally close to the desired native runtime shape:

```python
from agent_broker import AgentBroker
from native_runtime import AgentSpec, SandboxedFanoutRuntime, ToolGrant

broker = AgentBroker(".orchestry/demo-broker")
runtime = SandboxedFanoutRuntime(llm_fn, max_workers=100, broker=broker)
trace = runtime.run(
    "Review a large codebase from many independent angles.",
    [
        AgentSpec(
            id=f"agent_{i:03d}",
            role="reviewer",
            goal=f"Review shard {i}",
            context=f"Private shard context {i}",
            tool_grants=[ToolGrant("read", "sandbox")],
        )
        for i in range(100)
    ],
)

a2a_snapshot = broker.to_a2a_task(trace.run_id)
```

This gives the project executable behavior for:

- worker fan-out,
- isolated worker context,
- per-worker sandbox directories,
- explicit tool grant recording,
- concurrent scheduling,
- reducer synthesis,
- trace export.
- artifact publication,
- task snapshots that can be served through an A2A-style gateway.

The local Python prototype still does not make a standalone Python process spawn
Codex App internal isolated subagents or call the App internal LLM. That requires
runtime support from Codex. The prototype exists so the desired runtime contract
can be tested before or alongside such an App-native API. When that API is
available inside Codex App, it should be preferred over the local prototype for
normal plugin/skill execution.
