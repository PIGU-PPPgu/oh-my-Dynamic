# Codex CLI Swarm Evidence: 50 agents

Compact JSON: `swarm_50_agents_codex_cli_run_0cb382d124.json`

```json
{
  "run_id": "codex_cli_run_0cb382d124",
  "commit_sha": "2b86dc86b9eb4d9e6691b528182d749bb29f238d",
  "agents_requested": 50,
  "agents_completed": 50,
  "agents_failed": 0,
  "duration_s": 923.04,
  "max_parallel": 10,
  "sandbox": "read-only",
  "codex_extra_args": [
    "-c",
    "service_tier=\"fast\"",
    "-c",
    "model_reasoning_effort=\"low\""
  ],
  "trace_manifest_path": "$REPO_ROOT/.orchestry/evidence_swarm/codex_cli_run_0cb382d124/manifest.json",
  "trace_path": "$REPO_ROOT/.orchestry/evidence_swarm/codex_cli_run_0cb382d124/trace.json",
  "known_limitations": [
    "Manual smoke evidence; not part of default CI.",
    "Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.",
    "Sample summaries are truncated and may omit detailed findings."
  ],
  "sanitized": true,
  "repo_root_label": "$REPO_ROOT"
}
```

## Selected Anonymized Sample Summaries

- agent_000 (completed): Dynamic workflow resume drops persisted failed_agent_ids: on resume it restores completed_agent_ids but sets failed_ids to an empty set, so downstream max_agents accounting and dependency context can under-report prior failures until failed
- agent_001 (completed): Productization limitation: worktree-mode swarm agents publish full raw `git diff` patches into AgentBroker without size/redaction limits, which can overload reducer context and risk exposing sensitive local changes in dynamic workflow evide
- agent_002 (completed): Productization limitation: the dynamic workflow surface is intentionally a Codex CLI process-swarm, not Codex App-native fan-out; the release plan explicitly says not to fake App-native fan-out until the App exposes that runtime.
- agent_003 (completed): Committed swarm smoke evidence is not self-contained for release review: docs/evidence/README.md says each run should include goal, broker thread id, top findings, human follow-up, and known limitations, but docs/evidence/swarm_20_agents_co
- agent_004 (completed): Resume loses failed-agent state: dynamic workflow reloads completed IDs from checkpoint but resets failed_ids to an empty set, only using checkpoint failed IDs to seed pending when pending is empty. This can undercount max_agents and drop f
