# Five-Minute Demo Script

This script is for a short live walkthrough. It separates safe commands from real Codex CLI worker commands.

## 0. Setup

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## 1. Safe Readiness Check

```bash
python -m doctor --json
```

Expected: JSON status is `pass` or `warn`. A Codex CLI warning is acceptable for dry-run mode.

## 2. Safe Dry-Run Evidence

```bash
python examples/real_repo_review.py \
  --dry-run \
  --run-id five-minute-demo \
  --output-dir /tmp/ohmy-evidence
```

This does not launch real workers.

Show:

```bash
ls -la /tmp/ohmy-evidence
sed -n '1,120p' /tmp/ohmy-evidence/five-minute-demo.md
python -m json.tool /tmp/ohmy-evidence/five-minute-demo.json | head -80
```

## 3. Optional Real Codex CLI Readiness

```bash
python -m doctor --json --strict-real-codex
```

This launches a minimal read-only `codex exec` smoke. Run it only when Codex CLI is installed, logged in, and configured.

## 4. Optional Real 5-Agent Review

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

This launches real Codex CLI workers. Raw prompts/stdout/stderr remain under `.orchestry/`. Commit only compact sanitized evidence.

## 5. Closing Message

State the boundary explicitly:

- Verified path: Codex CLI process swarm.
- Not claimed: App-native isolated subagents are already implemented.
- Request: native Codex runtime primitives for subagent spawn, sandbox/tool policy, events, artifacts, scheduler, and reducer handoff.
