# Evidence Records

This directory stores compact, reviewable evidence from manual dynamic workflow
smoke runs. Raw prompts, stdout, stderr, and full traces stay under
`.orchestry/` and should not be committed.

Each run should write a human-readable `{run_id}.md` and a compact
machine-readable `{run_id}.json`. Together they should include:

- goal
- commit sha
- run id
- broker thread id
- agent count
- completed and failed counts
- duration
- max parallelism
- trace or checkpoint path
- top findings
- human follow-up
- known limitations

Quality eval reports are deterministic and can be committed when they are
generated from sample or redacted responses. They should include:

- eval suite id or suite path
- total/passed/failed counts
- average score
- per-task keyword hits and evidence hits
- missing criteria
- short response previews only

Recommended manual smoke commands:

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
python scripts/record_swarm_evidence.py --agents 50 --max-parallel 10
python scripts/record_swarm_evidence.py --agents 100 --max-parallel 20
python scripts/run_quality_eval.py --sample --output docs/evidence/sample_quality_eval.md
```

For Codex CLI installations that require explicit config overrides, pass the
same extra args to every worker and let the evidence JSON record them:

```bash
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"'
```
