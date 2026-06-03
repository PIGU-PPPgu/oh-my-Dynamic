---
name: multi-agent-run
description: "Run a multi-agent workflow on any complex task. One command to decompose, parallelize, and synthesize. Triggers on: run agents, parallel analysis, multi-agent, decompose and run, orchestrate task."
---

# Multi-Agent Run — One Command to Orchestrate

This skill decomposes any complex task into parallel subtasks, executes them with multiple agents, and synthesizes a coherent answer.

## Codex App Default: Native Subagents First

When triggered inside Codex App, this skill must work immediately after installation:

- If Codex subagent runtime/tools are available and the user asks for dynamic workflows, real subagents, parallel agents, or equivalent multi-agent execution, spawn real Codex internal subagents by default.
- Do **not** set a model override for spawned subagents. Let them inherit the current Codex App internal LLM/runtime.
- Do **not** require provider API keys or `.env` configuration for App-native subagent execution.
- Do **not** tell the user to use Codex CLI.
- Do **not** run the Python pipeline unless the user explicitly asks for the local Python engine, real provider calls, or dashboard files.
- Coordinate subagent collaboration through explicit messages, artifacts, handoffs, review requests, and auditable synthesis. Prefer parent-orchestrated A2A-style exchange over hidden peer-to-peer communication.
- If native Codex subagent runtime/tools are unavailable, fall back to zero-config in-chat workflow execution using the current Codex App assistant/model.

Boundary: local Python runtime, including `native_runtime.py`, cannot directly
call the Codex App internal LLM API unless Codex App/runtime exposes an explicit
bridge. Python runtime mode still uses the supplied `llm_fn` or external
provider APIs when configured.

For fallback App usage, or for synthesizing after native subagents return,
present the multi-agent workflow directly in the response:

1. Decompose the request into 3-7 tasks.
2. Assign roles such as planner, researcher, builder, reviewer, synthesizer.
3. Mark dependencies and identify which tasks can run in parallel.
4. Track worker messages, artifacts, handoffs, and review requests explicitly.
5. Produce worker results for each task.
6. Review the combined result for gaps.
7. Replan once if needed.
8. Synthesize a final answer.

## When to Trigger

- User asks to analyze something complex with multiple angles
- User wants parallel execution of subtasks
- User says "run agents on..." or "multi-agent..."
- User needs comprehensive research/analysis on a topic

## Workflow

### Step 1: Codex App Execution

For ordinary Codex App usage, skip local prerequisite checks. If App-native
Codex subagent tools are available and the request calls for real/parallel
agents, use those tools to spawn real internal subagents without any model
override. Otherwise, run the workflow in-chat.

Example trigger:

```text
$multi-agent-run 用多角度分析：学校是否应该引入 AI 作业助手？
```

### Step 2: Understand the Task

Infer reasonable defaults:

1. Main goal/query from the user request.
2. Subtasks: auto-detect, usually 3-7.
3. Perspectives: choose based on domain.
4. Time budget: one concise App response unless user asks for deeper work.
5. Token budget: stay concise but complete.

Only ask for clarification when the request is ambiguous enough that execution would be misleading.

### Step 3: Optional Local Python Engine

Use this only if the user explicitly asks for local engine execution, real provider calls, JSON output, or dashboard generation.

```python
import sys
sys.path.insert(0, '/Users/iguppp/Desktop/oh-my-Dynamic')

from pipeline import DynamicPipeline
from llm_client import call_glm

def llm_fn(sys, user):
    return call_glm(system_prompt=sys, user_prompt=user)

pipeline = DynamicPipeline(
    llm_fn=llm_fn,
    max_iterations={{iterations or 2}},
    max_tokens={{token_budget or 500000}},
    max_parallel={{parallel or 3}},
    completeness_threshold={{threshold or 0.80}},
)

result = pipeline.run("""{{user_query}}""")
```

### Step 4: Present Results

Show the user:
1. **Summary stats**: tasks completed, duration, tokens used
2. **Final answer**: the synthesized result
3. **DAG structure**: which tasks ran in parallel vs sequential
4. **Optional**: Offer a visual dashboard only if local Python engine mode was used.

```python
from visualize import generate_dashboard, open_dashboard
html = generate_dashboard(result, "dashboard.html")
open_dashboard(html)
```

### Step 5: Optional Follow-ups

- **Deep dive**: "Want me to expand on any specific subtask?"
- **Replan**: "Should I iterate more? There may be gaps."
- **Export**: Save results as JSON or Markdown report
- **TEA evolve**: If a tool failed, offer to auto-evolve it

## Output Format

Always present results in this structure:

```
## 🚀 Multi-Agent Results

**Query**: [original query]
**Tasks**: X/Y completed | **Time**: Xs | **Tokens**: X

### Final Answer
[synthesized result]

### Task Breakdown
- ✅ Task 1: [name] (Xs)
- ✅ Task 2: [name] (Xs)  
- ❌ Task 3: [name] (failed: reason)
```

## Pitfalls

- Codex App native-subagent mode should not ask the user for API keys.
- Codex App native-subagent mode should not set a model override; spawned subagents inherit the current App internal LLM/runtime.
- Codex App native-subagent mode should not imply uncontrolled P2P messaging; keep collaboration explicit and auditable through the orchestrator/broker contract.
- Codex App fallback mode is zero-config and should not ask the user for API keys.
- Codex App fallback mode is an in-chat workflow implementation, not a separate CLI command.
- Local Python `native_runtime.py` cannot directly call Codex App's internal LLM API unless an explicit App/runtime bridge is exposed; it uses the supplied `llm_fn` or external providers.
- GLM-5.1 is slow (~40s/call). Warn user if local provider mode generates 5+ subtasks.
- JSON parsing can fail — pipeline has fallback but results may be less structured.
- Token budget is estimated. Keep budget generous for complex queries.
- Don't run more than 3 parallel workers — GLM rate limits.
