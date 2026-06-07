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
- `sanitized: true`
- `repo_root_label: "$REPO_ROOT"`

Public evidence must not contain local absolute paths such as a real home
directory. Evidence writers normalize repository paths to
`$REPO_ROOT/...`, home paths to `$HOME/...`, and raw trace locations to compact
`.orchestry/...` references when possible.

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
python scripts/record_adaptive_workflow_evidence.py --dry-run --run-id adaptive-demo
python scripts/record_adaptive_workflow_evidence.py --required-coverage security,tests,docs --force-missing-coverage replanner-proof --max-rounds 2 --max-agents 12 --max-parallel 4 --dashboard
python examples/real_repo_review.py --agents 5 --max-parallel 3
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
python scripts/record_swarm_evidence.py --agents 50 --max-parallel 10
python scripts/record_swarm_evidence.py --agents 100 --max-parallel 20
python scripts/run_quality_eval.py --sample --output docs/evidence/sample_quality_eval.md
python scripts/run_demo_validation.py --output docs/evidence/demo_validation_v360.json
python scripts/measure_improvement.py --suite benchmarks/repo_review.json --output docs/evidence/improvement_v311.json
python scripts/run_benchmark.py --real --allow-failures --suite benchmarks/repo_review.json --mode single,fixed,adaptive --fixtures install_five_minute --timeout-s 240 --planner-timeout-s 180 --total-timeout-s 1200 --max-parallel 2 --adaptive-max-agents 5 --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"' --output docs/evidence/benchmark_v320_real_smoke.json
python scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output docs/evidence/benchmark_v320_dry.json
python scripts/run_benchmark.py --real --allow-failures --suite benchmarks/repo_review.json --mode single,fixed,adaptive --fixtures security_command_surface,install_five_minute,tests_dynamic_workflow,evidence_redaction,docs_boundary_claims --timeout-s 60 --planner-timeout-s 60 --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"' --output docs/evidence/benchmark_v310.json
```

`improvement_v311` is a bilingual controlled same-fixture measurement, not a
live Codex CLI run. It uses the benchmark scoring rubric to compare three
coverage models: single reviewer, fixed lane swarm, and adaptive replanner
follow-up. Report it as a concrete scoring/coverage lift, then pair it with real
Codex CLI evidence before making runtime claims.

`--dry-run` evidence is only a deterministic shape check. It can prove that the
markdown/JSON/dashboard schema renders, but it does not prove real agents,
planner quality, replanner behavior, Codex CLI login health, or sandbox
behavior.

The v3.1 bounded benchmark is intentionally failure-preserving: short timeouts
make it suitable as release smoke evidence, and timeout/failure rows are kept
instead of hidden. `benchmark_v310_replanner_sample.md` records a separate
compact adaptive sample where the replanner created 2 real follow-up Codex CLI
agents after planner-generated evidence.

The v2.1 real adaptive smoke can be reproduced with:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --run-id adaptive_v210_real_$(date +%Y%m%d_%H%M%S) \
  --goal "Release smoke for oh-my-Dynamic: run a real adaptive planner/replanner repo review with read-only Codex CLI agents, compact evidence, and no raw output committed." \
  --max-rounds 3 \
  --max-agents 20 \
  --max-parallel 5 \
  --planner-timeout-s 300 \
  --timeout-s 600 \
  --total-timeout-s 3600 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"' \
  --dashboard
```

The v2.2 real replanner proof should leave a controlled coverage gap and verify
`replanner_generated_agents > 0`:

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --run-id adaptive_v220_replanner_real_$(date +%Y%m%d_%H%M%S) \
  --goal "Release smoke for oh-my-Dynamic v2.2: create 8 narrow planner agents for security, architecture, tests, broker, observability, evidence, release, and docs-adjacent review; then use the deterministic trigger policy to add 2 to 5 replanner follow-up agents for the forced replanner-proof coverage lane. Keep all work read-only and return compact evidence only." \
  --required-coverage security,architecture,tests,broker,observability,evidence,release,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --planner-timeout-s 300 \
  --timeout-s 600 \
  --total-timeout-s 3600 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"' \
  --dashboard
```

For Codex CLI installations that require explicit config overrides, pass the
same extra args to every worker and let the evidence JSON record them:

```bash
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"'
```

Dashboards may embed compact broker snapshots, event previews, artifact
previews, trace paths, and checkpoint paths. Before publishing dashboard HTML,
scan it for secrets, credentials, personal data, raw prompts, stdout/stderr, and
environment-specific paths that should not be public.

Recommended scan before committing evidence:

```bash
! grep -R "$HOME" docs/evidence
python -m doctor --json
```
