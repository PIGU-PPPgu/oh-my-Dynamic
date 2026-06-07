# Quickstart

This path is for first-time users who want to verify installation, run a safe demo, and understand where evidence is written.

## 1. Install

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

Expected result: `doctor` returns `pass` or clear `warn` items. Fix `fail` items before running real Codex CLI workers.

## 2. Five-minute no-key check

```bash
python examples/real_repo_review.py --dry-run --run-id five-minute-demo
```

This does not launch Codex CLI workers. It verifies compact JSON/Markdown evidence shape and sanitizer behavior.

Evidence is written under `docs/evidence/` unless you pass a different output path.

## 3. Real 5-agent repo review

Prerequisite: Codex CLI is installed and logged in.

```bash
codex --version
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

This launches real `codex exec` workers. Raw prompts/stdout/stderr and traces stay in `.orchestry/`; only compact evidence should be committed.

## 4. Adaptive replanner smoke

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

This proves planner/replanner flow. It is slower than the dry-run and may launch multiple real Codex CLI workers.

## 5. Read the evidence

Start here:

- `docs/evidence/benchmark_v320_real_smoke.md`
- `docs/evidence/improvement_v311.md`
- `docs/evidence/README.md`

Use `docs/KNOWN_LIMITS.md` before making claims about App-native subagents, live model quality, or benchmark results.
