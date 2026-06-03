---
name: oh-my-dynamic
description: "Multi-agent orchestration engine for complex tasks. Use when you need to break a complex query into subtasks, run them in parallel with a DAG engine, and synthesize results. Triggers on: multi-agent, parallel execution, orchestrate, DAG, decompose task, dynamic workflow."
---

# oh-my-Dynamic — Multi-Agent Orchestration Engine

A self-contained multi-agent orchestration system that replicates Claude Dynamic Workflows. It decomposes complex queries into DAG-structured subtasks, executes them in parallel, and synthesizes results with stop-condition-aware iteration.

Important positioning: Codex App currently does not expose a native runtime API
for spawning tens or hundreds of isolated internal subagents. This skill gives a
zero-config dynamic-workflow-style experience in App, and the project documents
the target native runtime capability in `docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md`.

## Codex App Default: Zero-Config Mode

When this skill is triggered inside Codex App, the default mode is **zero-config**:

- Use the current Codex App assistant/model as the reasoning engine.
- Do **not** require `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ZHIPUAI_API_KEY`, or any external provider key.
- Do **not** run `llm_client.py` or the Python `DynamicPipeline` unless the user explicitly asks to use the local Python engine, a real provider, or a dashboard artifact.
- Treat the modules in `~/Desktop/oh-my-Dynamic` as the reference implementation and mirror their workflow in-chat.
- Be explicit if the user asks about native parallel sandboxed subagents: Codex
  App does not currently expose that capability to skills; it is the project's
  roadmap target, not the current App-mode behavior.

In zero-config mode, execute this workflow directly in the conversation:

1. **Decompose** the user goal into 3-7 subtasks with clear dependencies.
2. **Build a DAG** in text form: task id, role, dependencies, expected output.
3. **Run worker passes** using your own reasoning. If independent subtasks exist, analyze them as separate worker lanes in one response.
4. **Review** each worker result for completeness, correctness, and gaps.
5. **Replan once** if important gaps remain.
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

This mode is fully handled by Codex App. No `.env` file or model API key is needed.

### 1. Optional: Local Python Engine

```python
from pipeline import DynamicPipeline
from llm_client import call_glm

def llm_fn(system_prompt, user_prompt):
    return call_glm(system_prompt=system_prompt, user_prompt=user_prompt)

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
- In Codex App zero-config mode, do not tell the user to use Codex CLI.
- External Python engine mode needs provider API keys and may be slower.
- GLM-5.1 is slow (~40s/call). Keep `max_iterations` low (1-2) for quick real-provider runs.
- JSON parsing from GLM can fail. All parsers have 3-level fallback (direct → code block → brace matching).
- Token budget is estimated (chars/2). Not exact but sufficient for cost control.
- Worktree requires a git repo with at least one commit.
