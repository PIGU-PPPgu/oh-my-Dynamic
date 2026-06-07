# Adoption Validation

Use this checklist when a reviewer or maintainer validates oh-my-Dynamic from a fresh clone. The goal is to find adoption blockers, not to prove new runtime behavior.

## Scope

- Install clarity
- Codex CLI and plugin readiness
- Dry-run evidence shape
- Real 5-agent repo review
- Adaptive replanner smoke
- Evidence privacy and claim boundaries

## Checklist

1. Fresh clone and install:

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

2. No-key smoke:

```bash
python examples/real_repo_review.py --dry-run --run-id adoption-dry-run
```

3. Real 5-agent review:

```bash
codex --version
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

4. Adaptive shape check:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dry-run
```

5. Optional real adaptive smoke:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

## Reviewer Output

Ask reviewers to report:

- where installation failed or felt ambiguous
- whether the README overclaims App-native isolated subagents
- whether compact evidence is enough to trust the result
- whether dry-run and real-run evidence are clearly separated
- whether raw `.orchestry/` traces stayed local
- one recommended fix for the next release

For deeper external review prompts, see `docs/REVIEW_PROMPTS.md`.
