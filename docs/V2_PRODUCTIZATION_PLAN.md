# v2.0 Productization Plan

Historical note: this document is the v2.0 baseline plan. For the current v2.1+
entrypoints, use `README.md`, `docs/evidence/README.md`, GitHub Release notes,
and the committed evidence records as the source of truth.

## Summary

v2.0 moves oh-my-Dynamic from "dynamic workflow runtime prototype" to a
reviewable product surface. The release goal is not to claim Codex App-native
isolated subagents. The goal is to make the current, real surfaces easy to
trust:

- Codex App skill entrypoints stay short and honest.
- Codex CLI swarm evidence is compact, reproducible, and safe to commit.
- Agent output quality can be scored by a deterministic eval harness.
- Static observability dashboards are part of the default evidence story.
- Write-capable swarm remains explicit and worktree-isolated.

## Non-Goals

- Do not fake App-native fan-out while Codex App does not expose that runtime.
- Do not commit raw prompts, stdout, stderr, or full `.orchestry/` traces.
- Do not auto-merge write-capable worker branches.
- Do not put real 20/50/100-agent smoke runs in default CI.

## Product Acceptance Criteria

- A new user can find one App skill trigger and one CLI demo command in the
  first README screen.
- CI can run a deterministic quality eval without network or model credentials.
- Manual real swarm evidence has a fixed compact markdown/JSON shape.
- Dashboard rendering can consume broker events, artifacts, traces, and
  checkpoints without needing a live server.
- Release gates include tests, coverage, CLI help, and eval help.

## v2.0 Work Items

1. Add `eval_runner.py` and `evals/` fixtures for deterministic agent-quality
   scoring.
2. Add `scripts/run_quality_eval.py` for local/CI eval reports.
3. Wire eval help into tests, CI, and release checklist.
4. Update README, skills, and evidence docs with the v2.0 one-command path.
5. Keep real 20/50/100 swarm evidence as manual smoke commands, with compact
   committed summaries only.

## Recommended Manual Evidence

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
python scripts/record_swarm_evidence.py --agents 50 --max-parallel 10
python scripts/record_swarm_evidence.py --agents 100 --max-parallel 20
python scripts/run_quality_eval.py --sample --output docs/evidence/sample_quality_eval.md
```
