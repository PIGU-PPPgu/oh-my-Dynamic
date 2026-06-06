# Codex CLI Swarm Smoke Tests

These checks launch real `codex exec` workers using the current local Codex CLI
login/config. They do not use provider API keys from oh-my-Dynamic.

## 20-Agent Review Smoke

```bash
python3 -m codex_cli_swarm \
  --agents 20 \
  --max-parallel 5 \
  --total-timeout-s 3600 \
  "Review this repository for security, architecture, install experience, README accuracy, tests, observability, examples, and release readiness."
```

The convenience repo-review example defaults to a smaller smoke profile unless
you pass a larger `--agents` value:

```bash
python3 examples/codex_cli_swarm_review.py \
  --agents 20 \
  --max-parallel 5 \
  --total-timeout-s 3600
```

## Fixed Swarm vs Adaptive Workflow

`codex_cli_swarm` is a fixed shard runner: the user chooses the number of
workers up front, and the runtime fans out that static list with dependency
handling.

`scripts/record_adaptive_workflow_evidence.py` is the adaptive dynamic workflow
path: a planner generates the initial agents, the replanner can add follow-up
agents after broker evidence is available, and the reducer writes compact
round-aware evidence.

## Larger Manual Profiles

```bash
python3 -m codex_cli_swarm --agents 50 --max-parallel 10 --total-timeout-s 7200 "Review this repository deeply."
python3 -m codex_cli_swarm --agents 100 --max-parallel 20 --total-timeout-s 14400 "Shard this repository review across 100 Codex CLI workers."
```

The v2.0.1 release includes committed compact evidence for real read-only
Codex CLI runs:

| Run | Completed | Failed | Max parallel | Evidence |
|-----|-----------|--------|--------------|----------|
| 20-agent fixed swarm | 20 | 0 | 5 | `docs/evidence/swarm_20_agents_codex_cli_run_98b78a645c.md` |
| 50-agent fixed swarm | 50 | 0 | 10 | `docs/evidence/swarm_50_agents_codex_cli_run_98b78a645c.md` |
| 100-agent fixed swarm | 100 | 0 | 20 | `docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md` |

## Expected Evidence

Each run prints:

- `broker_thread_id`
- `swarm_root`
- `trace_path`
- `manifest_path`

When workdirs are kept, inspect per-agent files under `swarm_root`:

- `prompt.md`
- `stdout.txt`
- `stderr.txt`
- `last_message.txt`

When `--discard-workdirs` is used, inspect the compact trace and manifest files
left under the workspace root.
