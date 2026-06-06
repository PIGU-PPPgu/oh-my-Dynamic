# Codex CLI Swarm Evidence: 100 agents

Compact JSON: `swarm_100_agents_codex_cli_run_98b78a645c.json`

```json
{
  "run_id": "codex_cli_run_98b78a645c",
  "commit_sha": "2b86dc86b9eb4d9e6691b528182d749bb29f238d",
  "agents_requested": 100,
  "agents_completed": 100,
  "agents_failed": 0,
  "duration_s": 1049.35,
  "max_parallel": 20,
  "sandbox": "read-only",
  "codex_extra_args": [
    "-c",
    "service_tier=\"fast\"",
    "-c",
    "model_reasoning_effort=\"low\""
  ],
  "trace_manifest_path": "/Users/iguppp/Desktop/oh-my-Dynamic/.orchestry/evidence_swarm/codex_cli_run_98b78a645c/manifest.json",
  "trace_path": "/Users/iguppp/Desktop/oh-my-Dynamic/.orchestry/evidence_swarm/codex_cli_run_98b78a645c/trace.json",
  "known_limitations": [
    "Manual smoke evidence; not part of default CI.",
    "Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.",
    "Sample summaries are truncated and may omit detailed findings."
  ]
}
```

## Selected Anonymized Sample Summaries

- agent_000 (completed): Reducer scalability limitation: the deterministic broker reduction reports total counts but only includes the first 20 completed findings, first 20 failures, and first 20 review responses, so a 100-shard evidence smoke can silently omit mos
- agent_001 (completed): Productization limitation: read-only/default review posture is not enforced at the Codex CLI execution layer. `CodexCliAgentSpec` defaults to `sandbox="workspace-write"` while `write_intent="none"`, and dynamic planner/replanner JSON worker
- agent_002 (completed): Productization limitation: real 20/50/100-agent Codex CLI swarm evidence is explicitly manual smoke evidence, not default CI coverage, so release confidence for large dynamic workflows still depends on out-of-band runs rather than automated
- agent_003 (completed): Evidence schema drift: the evidence README says compact run artifacts should include broker thread id, top findings, and human follow-up, but scripts/record_swarm_evidence.py only writes run/count/timing/path/limitations plus sample summari
- agent_004 (completed): Productization limitation: read-only evidence/review shards are not least-privilege by default; CodexCliAgentSpec defaults sandbox to workspace-write even when write_intent is none, so a smoke/review worker can still be launched with reposi
