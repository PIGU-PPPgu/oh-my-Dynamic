# Demo Validation

This page explains what oh-my-Dynamic can improve in concrete adoption
scenarios. The current v3.6 demo validation is deterministic: it measures
workflow coverage, evidence completeness, parallel review throughput, and
gap-driven replanning. It does not claim live model quality improves.

## What Improves

| Dimension | Meaning |
|-----------|---------|
| Workflow coverage | More required lanes get explicit reviewer coverage. |
| Evidence completeness | More outputs cite artifacts, commands, checks, and known limits. |
| Parallel throughput | Multiple specialist lanes run as a swarm instead of one serial reviewer. |
| Gap-driven replanning | Adaptive mode adds follow-up agents when requirements remain uncovered. |
| Handoff quality | Reports preserve missing requirements and next steps for humans. |

## Demo Scenarios

| Scenario | Why It Matters |
|----------|----------------|
| Frontend build | Shows how UI layout, state/data, a11y, responsive review, tests, and docs can be split into specialist lanes. |
| Harness engineering | Shows how eval fixtures, scoring, redaction, CI, evidence schema, and failure preservation can be covered together. |
| Repo productization | Shows adoption hardening: install, doctor, quickstart, tests, coverage, release checklist, and evidence. |
| Security / trust | Shows command surface, gateway auth, artifact poisoning, redaction, raw-output boundaries, and threat model coverage. |

## Run The Demo

All commands below are safe deterministic dry-runs. They do not launch Codex CLI
workers.

```bash
python scripts/run_demo_validation.py --output /tmp/ohmy-demo-validation/demo_validation_v360.json
python examples/frontend_build_demo.py --output /tmp/ohmy-demo-validation/frontend_build.json
python examples/harness_engineering_demo.py --output /tmp/ohmy-demo-validation/harness_engineering.json
```

Committed evidence:

- [evidence/demo_validation_v360.md](evidence/demo_validation_v360.md)
- [evidence/demo_validation_v360.json](evidence/demo_validation_v360.json)

## Current v3.6 Numbers

| Mode | Avg Quality | Evidence | Parallel Speedup | Missing Requirements | Replanner Agents |
|------|-------------|----------|------------------|----------------------|------------------|
| single | `0.56` | `0.48` | `1.0x` | `20` | `0` |
| fixed | `0.74` | `0.78` | `3.48x` | `8` | `0` |
| adaptive | `0.88` | `0.94` | `3.5x` | `0` | `8` |

The most important claim is not "the model is smarter." The claim is:

> oh-my-Dynamic improves workflow coverage, evidence completeness, parallel
> review throughput, and gap-driven replanning under the same task rubric.

Pair these deterministic demo numbers with real Codex CLI evidence before
making runtime claims.
