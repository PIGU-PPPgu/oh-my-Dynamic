# Quickstart

Use this path to verify oh-my-Dynamic without changing Codex App configuration first. Supported first-run platforms are macOS, Linux, and WSL; native Windows is not verified.

## 1. CLI-only safe install

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m doctor --json
```

`doctor` may return `warn` when Codex CLI or the App plugin is not installed. That is acceptable for dry-run checks.

## 2. Five-minute no-key check

```bash
python examples/real_repo_review.py \
  --dry-run \
  --run-id five-minute-demo \
  --output-dir /tmp/ohmy-evidence
```

This does not launch Codex CLI workers and does not write public evidence into the repository.

## 3. Real Codex CLI review

Prerequisite: Codex CLI is installed and logged in.

```bash
codex --version
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

This launches real `codex exec` workers. Raw prompts/stdout/stderr and traces stay in `.orchestry/`; only compact evidence should be committed.

## 4. Codex App plugin install

Run this only if you want the App skill entrypoints:

```bash
bash install_plugin.sh
python -m doctor --json
```

The installer creates symlinks under `~/.agents` and merges the local plugin into `~/.agents/plugins/marketplace.json`. Moving or deleting the clone requires rerunning the installer.

Uninstall:

```bash
bash install_plugin.sh --uninstall
```

## 5. Adaptive replanner smoke

Start with a shape check:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dry-run \
  --output-dir /tmp/ohmy-adaptive
```

Then run the real smoke when you are ready to launch Codex CLI workers:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

## 6. Read the evidence

Start here:

- `docs/evidence/benchmark_v320_real_smoke.md`
- `docs/evidence/improvement_v311.md`
- `docs/evidence/README.md`

Use `docs/KNOWN_LIMITS.md` before making claims about App-native subagents, live model quality, or benchmark results.
