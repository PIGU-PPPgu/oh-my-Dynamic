# Codex CLI Swarm Evidence: 20 agents

Compact JSON: `swarm_20_agents_codex_cli_run_dca4e2b75f.json`

```json
{
  "run_id": "codex_cli_run_dca4e2b75f",
  "commit_sha": "2b86dc86b9eb4d9e6691b528182d749bb29f238d",
  "agents_requested": 20,
  "agents_completed": 20,
  "agents_failed": 0,
  "duration_s": 620.52,
  "max_parallel": 5,
  "trace_manifest_path": "/Users/iguppp/Desktop/oh-my-Dynamic/.orchestry/evidence_swarm/codex_cli_run_dca4e2b75f/manifest.json",
  "trace_path": "/Users/iguppp/Desktop/oh-my-Dynamic/.orchestry/evidence_swarm/codex_cli_run_dca4e2b75f/trace.json",
  "known_limitations": [
    "Manual smoke evidence; not part of default CI.",
    "Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.",
    "Sample summaries are truncated and may omit detailed findings."
  ],
  "sandbox": "read-only",
  "codex_extra_args": [
    "-c",
    "service_tier=\"fast\"",
    "-c",
    "model_reasoning_effort=\"low\""
  ]
}
```

## Selected Anonymized Sample Summaries

- agent_000 (completed): Evidence smoke limitation: the repo's built-in test suite is not runnable to completion in this read-only shard because tests require writable temp/orchestry paths; command returned 25 pass / 30 fail, dominated by temp directory and permiss
- agent_001 (completed): CodeGraph index appears stale/incomplete for this repo: CodeGraph reports 42 indexed Python files, while `rg --files -g '*.py' | wc -l` shows 51, so structural evidence from CodeGraph may miss current modules such as swarm helper/observer s
- agent_002 (completed): Read-only smoke ran `python3 test_suite.py`; suite is not runnable under the current read-only sandbox because many tests require temp/worktree writes, yielding 25 pass and 30 fail rather than product failures.
- agent_003 (completed): CodeGraph evidence is stale/incomplete for this repo: CodeGraph reports 43 indexed files and omits live Python modules such as workflow_observer.py, codex_swarm_models.py, and codex_swarm_scheduler.py, so structural findings from this shard
- agent_004 (completed): CodeGraph index appears stale/incomplete for this repo: it reports 43 indexed files while the filesystem has additional Python/workflow files not represented in the index, so structural evidence from CodeGraph may miss current swarm modules
