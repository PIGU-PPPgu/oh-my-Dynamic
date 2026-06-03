---
name: multi-agent-run
description: "Run a multi-agent workflow on any complex task. One command to decompose, parallelize, and synthesize. Triggers on: run agents, parallel analysis, multi-agent, decompose and run, orchestrate task."
---

# Multi-Agent Run — One Command to Orchestrate

This skill decomposes any complex task into parallel subtasks, executes them with multiple agents, and synthesizes a coherent answer.

## When to Trigger

- User asks to analyze something complex with multiple angles
- User wants parallel execution of subtasks
- User says "run agents on..." or "multi-agent..."
- User needs comprehensive research/analysis on a topic

## Workflow

### Step 1: Check Prerequisites

```bash
# Verify oh-my-Dynamic is available
test -f ~/Desktop/oh-my-Dynamic/pipeline.py && echo "OK" || echo "NOT_FOUND"
```

If not found, tell user: "oh-my-Dynamic needs to be installed at ~/Desktop/oh-my-Dynamic/"

### Step 2: Understand the Task

Clarify with the user:
1. What is the main goal/query?
2. How many subtasks? (default: auto-detect, max 5)
3. Any specific angles or perspectives needed?
4. Time budget? (default: 5 minutes)
5. Token budget? (default: 500K)

### Step 3: Run the Pipeline

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
4. **Offer**: "Want to see the visual dashboard?" → run visualize.py

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

- GLM-5.1 is slow (~40s/call). Warn user if query generates 5+ subtasks.
- JSON parsing can fail — pipeline has fallback but results may be less structured.
- Token budget is estimated. Keep budget generous for complex queries.
- Don't run more than 3 parallel workers — GLM rate limits.
