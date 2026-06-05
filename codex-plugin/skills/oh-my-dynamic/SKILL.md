---
name: oh-my-dynamic
description: "Multi-agent orchestration engine for complex tasks. Use when you need to break a complex query into subtasks, run them in parallel with a DAG engine, and synthesize results. Triggers on: multi-agent, parallel execution, orchestrate, DAG, decompose task, dynamic workflow."
---

# oh-my-Dynamic — Multi-Agent Orchestration Engine

A self-contained multi-agent orchestration system inspired by Claude Dynamic
Workflows. It prototypes plugin-level orchestration, App-native subagent bridge
contracts, DAG-structured subtasks, parallel execution, and synthesis with
stop-condition-aware iteration.

Important positioning: when Codex App exposes native subagent runtime/tools in
the current session, this skill should use them as the preferred App execution
path for user requests that explicitly ask for dynamic workflows, real
subagents, parallel agents, or equivalent multi-agent execution. The App-native
path should spawn real Codex internal subagents, let them inherit the current
Codex App LLM/runtime, and avoid any external provider setup. If those native
subagent tools are not available, fall back to the zero-config in-chat workflow
below. If the user explicitly asks for dozens/hundreds of real Codex agents,
maximum fan-out, or a CLI swarm, use `codex_cli_swarm.py` as the second backend:
it shells out to many `codex exec` workers and ingests their JSON envelopes into
AgentBroker. The project also includes `native_runtime.py`, a local executable
prototype that can fan out many isolated workers with separate sandbox
directories, per-worker context, tool grants, trace capture, and reducer
synthesis. `agent_broker.py` provides the shared collaboration contract:
policy-governed messages, artifacts, task handoffs, review requests/responses,
inboxes, and audit traces.
`broker_gateway.py` exposes that contract as a local HTTP/SSE gateway when a
transport surface is needed.
`codex_app_bridge.py` defines the App-native bridge: dispatch specs, subagent
prompts, structured JSON envelopes, and AgentBroker ingestion.
`codex_cli_swarm.py` defines the Codex CLI swarm backend for large-scale
process-level fan-out.
`dynamic_workflow.py` defines the v1.8 planner/replanner runtime: start with a
planner, fan out Codex CLI workers, let a replanner add follow-up agents, then
run a broker-aware reducer over artifacts, failures, dependency graph, review
responses, optional worktree diff artifacts, checkpoint/resume state, and
streaming workflow events.

Boundary: the local Python `native_runtime.py` cannot directly call the Codex
App internal LLM API unless Codex App/runtime exposes an explicit bridge. Python
runtime mode still uses the `llm_fn` passed into it, or external provider APIs
when configured.

## Codex App Default: Native Subagents First

One-line App trigger:

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

Current product status:

- Stable: Codex CLI swarm, dynamic workflow planner/replanner, broker reducer,
  and the real repo review demo.
- Beta: worktree patch mode, checkpoint/resume, streaming progress events, and
  capability routing.
- Experimental: Codex App bridge, A2A gateway, and TEA protocol.

When this skill is triggered inside Codex App, the default App-mode priority is:

1. If Codex subagent runtime/tools are available and the user asks for dynamic workflows, real subagents, parallel agents, or equivalent multi-agent execution, spawn real Codex internal subagents.
2. Do **not** set a model override for spawned subagents. Let them inherit the current Codex App internal LLM/runtime.
3. Do **not** require `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ZHIPUAI_API_KEY`, or any external provider key for App-native subagent execution.
4. Use the Codex App bridge contract: create a dispatch plan, prompt each subagent to return the structured JSON envelope, then ingest envelopes into AgentBroker.
5. Coordinate subagents through the parent orchestrator and the AgentBroker contract: registered agents, explicit messages, artifacts, handoffs, review requests/responses, inboxes, and traceable synthesis. Do not rely on hidden peer-to-peer side channels.
6. If native Codex subagent runtime/tools are unavailable, use zero-config in-chat workflow execution as the fallback.
7. If the user explicitly asks for tens/hundreds of real Codex agents, prefer `codex_cli_swarm.py` over the in-chat fallback.
8. If the user explicitly asks for concurrent code writing, use worktree mode with `workspace_mode="worktree"` and `write_intent="patch"`. Do not auto-merge.
9. If the user does not clearly grant write intent, default to read-only review.

In App fallback/zero-config mode:

- Use the current Codex App assistant/model as the reasoning engine.
- Do **not** require `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ZHIPUAI_API_KEY`, or any external provider key.
- Do **not** run `llm_client.py` or the Python `DynamicPipeline` unless the user explicitly asks to use the local Python engine, a real provider, or a dashboard artifact.
- Do run `dynamic_workflow.py` when the user explicitly asks for the local planner/replanner CLI backend.
- Do run `codex_cli_swarm.py` when the user explicitly asks for large-scale Codex CLI worker fan-out.
- Use `python examples/real_repo_review.py --agents 5 --max-parallel 3` when
  the user asks for a real read-only repo review demo with compact evidence.
- Use `python examples/real_repo_review.py --dry-run --run-id five-minute-demo`
  for a zero-config demo shape check that must not launch real Codex CLI workers.
- Keep the runtime boundary clear: `dynamic_workflow.py` orchestrates planner,
  replanner, checkpoint/resume, events, and reducer; `codex_cli_swarm.py`
  executes Codex CLI workers and owns worker lifecycle details.
- Treat the modules in the installed oh-my-Dynamic repository as the reference implementation and mirror their workflow in-chat.
- Be explicit if the user asks about native parallel sandboxed subagents and no
  Codex subagent runtime/tools are available in the current session: App-native
  spawning cannot be used from this skill until the App/runtime exposes those
  tools. The local prototype can still be demonstrated with
  `python examples/sandboxed_fanout.py`.
- If the user asks whether isolated workers use Codex's internal LLM by default,
  answer precisely: App-native subagents inherit the current Codex App internal
  LLM/runtime when the App exposes subagent tools and no model override is set.
  The local Python isolated worker runtime cannot call Codex App's internal LLM
  API directly unless an explicit App/runtime bridge exists; it uses the provided
  `llm_fn` (mock by default in demos, or external provider APIs when configured).

In zero-config mode, execute this workflow directly in the conversation:

1. **Decompose** the user goal into 3-7 subtasks with clear dependencies.
2. **Build a DAG** in text form: task id, role, dependencies, expected output.
3. **Run worker passes** using your own reasoning. If independent subtasks exist, analyze them as separate worker lanes in one response.
4. **Review** each worker result for completeness, correctness, and gaps.
5. **Replan** if important gaps remain, until ready for reducer or max rounds are reached.
6. **Synthesize** a final answer that cites the task breakdown and gives actionable next steps.

Only ask a clarification question if the task cannot be reasonably scoped. Otherwise proceed.

## When to Use

- Complex research or analysis tasks that can be parallelized
- Tasks needing decomposition into independent sub-problems
- Scenarios requiring iterative refinement with stop conditions
- Multi-step workflows with dependencies between steps

## Architecture

```
Pipeline: Query → Decompose → DAG Build → Execute → Stop Check → Replan/Synthesize → Output
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `pipeline.py` | End-to-end entry point. One `run()` call. |
| `dag.py` | DAG task graph with dependency-aware parallel execution |
| `stop_conditions.py` | 5 stop conditions (completeness, confidence, diminishing returns, token budget, max iterations) |
| `prompt_kit.py` | 8 Anthropic prompt engineering principles as templates |
| `token_tracker.py` | Thread-safe token budget tracking |
| `synthesis.py` | Hierarchical result synthesis (group → condense → integrate) |
| `dynamic_replan.py` | Result-preserving replan (keeps completed work) |
| `tea_protocol.py` | Tool Evolution & Adaptation (runtime tool creation + versioning) |
| `worktree.py` | Git worktree isolation per agent |
| `agent_broker.py` | A2A-style policy, messages, artifacts, task handoff, review requests/responses, inboxes, audit trace |
| `broker_gateway.py` | Local HTTP/SSE gateway for AgentBroker task snapshots and events |
| `codex_app_bridge.py` | Codex App dispatch plans, subagent prompts, JSON envelopes, broker ingestion |
| `codex_cli_swarm.py` | Codex CLI swarm backend for large-scale process-level fan-out |
| `dynamic_workflow.py` | Codex CLI planner/replanner runtime with streaming events and checkpoint/resume |
| `workflow_events.py` | Unified JSONL-friendly workflow event schema |
| `checkpoint.py` | Atomic checkpoint save/load helpers for dynamic workflow resume |
| `capability_registry.py` | Lightweight capability routing metadata for reviewer roles |
| `visualize.py` | Generate interactive HTML dashboard |
| `test_suite.py` | Unit, integration, security, provider-routing, and stress tests |

## Step-by-Step Usage

### 0. Codex App Usage (No API Key)

In Codex App, use:

```text
$oh-my-dynamic 用多 agent 分析：学校是否应该引入 AI 作业助手？
```

Expected response shape:

```markdown
## Multi-Agent Results
Query: ...
Tasks: 5/5 completed

### DAG
...

### Worker Results
...

### Review / Replan
...

### Final Answer
...
```

This mode is fully handled by Codex App. No `.env` file or model API key is
needed. If App-native subagent runtime/tools are available and the request calls
for real/parallel agents, use those tools and spawn real Codex subagents without
setting a model override. If not, produce the same workflow directly in-chat.

### 1. Optional: Local Python Engine

```python
from pipeline import DynamicPipeline
from llm_client import call_llm

def llm_fn(system_prompt, user_prompt):
    return call_llm(system_prompt=system_prompt, user_prompt=user_prompt)

pipeline = DynamicPipeline(
    llm_fn=llm_fn,
    max_iterations=3,        # Max replan iterations
    max_tokens=500_000,      # Token budget
    max_parallel=3,          # Parallel workers
    completeness_threshold=0.80,
)

result = pipeline.run("Design a complete data governance framework for a school")
print(result["final_answer"])
print(f"DAG: {result['dag_stats']['completed']}/{result['dag_stats']['total']}")
print(f"Duration: {result['duration_s']:.0f}s, Tokens: {result['token_summary']['total']}")
```

Use this optional path only when the user asks to run the local engine, use an external provider, or generate dashboard files.

### 2. Standalone DAG Execution

```python
from dag import DAG, DAGNode, DAGExecutor

dag = DAG()
n1 = dag.add_node(DAGNode.create("Collect data", priority=8))
n2 = dag.add_node(DAGNode.create("Clean data", dependencies=[n1.id]))
n3 = dag.add_node(DAGNode.create("Analyze data", dependencies=[n1.id]))
n4 = dag.add_node(DAGNode.create("Report", dependencies=[n2.id, n3.id]))

def my_executor(node, context):
    return call_llm(node.question, context)

result_dag = DAGExecutor(dag, my_executor, max_parallel=3).execute()
```

### 3. TEA Protocol (Tool Evolution)

```python
from tea_protocol import ToolRegistry, ToolEvolver

registry = ToolRegistry(storage_dir="./tea_tools")
tool = registry.register("parser", "Parse CSV", "def parser(x): return x.split(',')", "agent1")

# Auto-evolve on failure
evolver = ToolEvolver(registry, llm_fn)
improved = evolver.auto_evolve(tool.tool_id, "Parse CSV with headers", "IndexError: list index out of range")
```

### 4. Visualization

```python
from visualize import generate_dashboard, open_dashboard

result = pipeline.run("Complex query here")
html_path = generate_dashboard(result, "output.html")
open_dashboard(html_path)
```

### 5. Run Tests

```bash
python test_suite.py              # Unit + integration
python test_suite.py --stress     # Include stress tests
python test_suite.py --e2e        # Include real API tests
```

## Key Design Decisions

- **GLM-5.1 compatible**: All prompts in Chinese, JSON output format, no tool_call dependency
- **Orchestration in code**: LLM only does text I/O, all control flow is deterministic Python
- **Result-preserving replan**: Replan never discards completed work
- **5 stop conditions**: Aligned with VMAO paper (arXiv 2603.11445)
- **Thread-safe**: TokenTracker and DAGExecutor handle concurrent access

## Paper References

- Anthropic: "How we built our multi-agent research system" (orchestrator-worker, 8 prompt principles)
- VMAO: arXiv 2603.11445 (DAG execution, 5 stop conditions, hierarchical synthesis)
- AgentOrchestra: arXiv 2506.12508 (TEA protocol, tool evolution)
- Multi-Agent Survey: arXiv 2501.06322

## Pitfalls

- In Codex App zero-config mode, do not ask for API keys.
- In Codex App native-subagent mode, do not ask for API keys and do not set a model override; spawned subagents inherit the current App internal LLM/runtime.
- In Codex App native-subagent mode, keep inter-agent collaboration explicit: route useful cross-agent context through orchestrator-mediated messages, artifacts, handoffs, review requests, and final synthesis.
- In Codex App zero-config mode, do not tell the user to use Codex CLI.
- The local Python `native_runtime.py` cannot directly call Codex App's internal LLM API unless an explicit App/runtime bridge is exposed; it uses the provided `llm_fn` or external providers.
- External provider mode needs provider API keys and may be slower; local Python runtime itself uses the `llm_fn` supplied by the caller.
- GLM-5.1 is slow (~40s/call). Keep `max_iterations` low (1-2) for quick real-provider runs.
- JSON parsing from GLM can fail. All parsers have 3-level fallback (direct → code block → brace matching).
- Token budget is estimated (chars/2). Not exact but sufficient for cost control.
- Worktree requires a git repo with at least one commit.
