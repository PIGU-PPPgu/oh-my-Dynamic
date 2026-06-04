# Codex CLI Swarm Smoke Tests

These checks launch real `codex exec` workers using the current local Codex CLI
login/config. They do not use provider API keys from oh-my-Dynamic.

## 20-Agent Review Smoke

```bash
python3 examples/codex_cli_swarm_review.py \
  --agents 8 \
  --max-parallel 4 \
  --total-timeout-s 3600
```

For a 20-agent custom run, use the module entrypoint:

```bash
python3 -m codex_cli_swarm \
  --agents 20 \
  --max-parallel 5 \
  --total-timeout-s 3600 \
  "Review this repository for security, architecture, install experience, README accuracy, tests, observability, examples, and release readiness."
```

## Larger Manual Profiles

```bash
python3 -m codex_cli_swarm --agents 50 --max-parallel 10 --total-timeout-s 7200 "Review this repository deeply."
python3 -m codex_cli_swarm --agents 100 --max-parallel 20 --total-timeout-s 14400 "Shard this repository review across 100 Codex CLI workers."
```

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
