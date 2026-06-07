# oh-my-Dynamic

[![tests](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![coverage](https://img.shields.io/badge/coverage-82%25-brightgreen)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[中文说明](README.zh-CN.md)

Dynamic workflow tooling for Codex: planner/replanner orchestration, Codex CLI process swarms, broker evidence, and benchmark reports.

**Boundary:** verified large-scale execution is Codex CLI process swarm. Codex App-native isolated subagents still depend on Codex App exposing that runtime. Defaults are read-only.

## Quick Start

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

Codex App skill:

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

## Run

```bash
# 5-minute no-key check
python examples/real_repo_review.py --dry-run --run-id five-minute-demo

# Real 5-agent repo review
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard

# Adaptive workflow
python -m dynamic_workflow "review this repo" --max-rounds 2 --max-agents 20 --max-parallel 5 --stream-events

# Fixed 20-agent swarm
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
```

## Measured Lift

Bilingual report: [docs/evidence/improvement_v311.md](docs/evidence/improvement_v311.md)

| Comparison | Quality Score | Evidence Completeness | Missing Requirements |
|------------|---------------|-----------------------|----------------------|
| fixed vs single | `+0.286` / `+46.6%` | `+0.229` | `-74.3%` |
| adaptive vs single | `+0.386` / `+62.9%` | `+0.329` | `-100%` |

This is controlled same-fixture scoring. Pair it with real Codex CLI evidence before making runtime claims.

## Evidence

| Evidence | Purpose |
|----------|---------|
| [benchmark_v320_real_smoke.md](docs/evidence/benchmark_v320_real_smoke.md) | v3.2 real stability smoke: single `0.537`, fixed `0.838`, adaptive `1.0` |
| [benchmark_v310.md](docs/evidence/benchmark_v310.md) | bounded real Codex CLI benchmark with failures preserved |
| [benchmark_v310_replanner_sample.md](docs/evidence/benchmark_v310_replanner_sample.md) | real planner + replanner follow-up sample |
| [swarm_100_agents_codex_cli_run_98b78a645c.md](docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | fixed 100-agent Codex CLI swarm |

## Status

| Stable | Beta | Experimental |
|--------|------|--------------|
| Codex CLI swarm, adaptive workflow, broker reducer, evidence reports | worktree patch mode, checkpoint/resume, streaming events | Codex App bridge, A2A gateway, TEA |

## Validate

```bash
python test_suite.py
python -m pytest tests -q
python -m coverage run -m pytest tests -q
python -m coverage report --fail-under=80
python -m bandit -r . -c pyproject.toml
```

## More

- Quickstart: [docs/QUICKSTART.md](docs/QUICKSTART.md)
- Docs index: [docs/README.md](docs/README.md)
- Known limits: [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md)
- Evidence rules: [docs/evidence/README.md](docs/evidence/README.md)
- Threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- v3 imports: [docs/V3_MIGRATION_GUIDE.md](docs/V3_MIGRATION_GUIDE.md)

MIT. See [LICENSE](LICENSE).
