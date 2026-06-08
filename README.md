<div align="center">
  <img src="assets/icon.svg" alt="oh-my-Dynamic" width="112" height="112">
  <h1>oh-my-Dynamic</h1>
  <p><strong>Dynamic workflow tooling for Codex.</strong></p>
  <p><a href="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml"><img src="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg" alt="tests"></a> <a href="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml"><img src="https://img.shields.io/badge/coverage-82%25-brightgreen" alt="coverage"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a></p>
  <p><a href="README.zh-CN.md">中文说明</a></p>
</div>

https://github.com/user-attachments/assets/a48d5943-620f-4eac-bd36-a4ea02b4cec6

**Positioning:** Codex supports native parallel coding agents. oh-my-Dynamic does not compete with that runtime; it adds planning, replanning, broker evidence, benchmark reports, and adoption validation around Codex CLI/App workflows. The verified large-scale backend here is Codex CLI process swarm; defaults are read-only.

## Why It Exists

Codex native subagents execute the work. oh-my-Dynamic explains, plans, measures, records, and audits the work.

| Layer | Codex native agents | oh-my-Dynamic |
|-------|---------------------|---------------|
| Execution | First-party parallel agents, worktrees, cloud/app runtime | Uses Codex CLI process swarm today; can later target native APIs |
| Workflow | Great direct coding UX | Planner/replanner rounds, reducers, missing-coverage follow-up |
| Evidence | Codex task UI and diffs | Compact JSON/MD/dashboard evidence for reviewers and releases |
| Best fit | Build, fix, refactor, review code | Complex task decomposition, audit trails, benchmarks, external proof |

## Quick Start

CLI-only safe path:

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m doctor --json
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence
```

Real Codex CLI workers:

```bash
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

Codex App plugin install:

```bash
bash install_plugin.sh
```

Plugin install mutates local `~/.agents` symlinks and marketplace JSON. Runtime workers remain read-only by default.

Codex App skill trigger:

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务；App runtime 可用时使用内部 Codex subagents，否则走 in-chat fallback；大规模走 Codex CLI swarm。
```

## Demo Validation

Report: [docs/evidence/demo_validation_v360.md](docs/evidence/demo_validation_v360.md)

Deterministic scenario validation across frontend build, harness engineering, repo productization, and security/trust. It measures workflow coverage and evidence completeness, not live model quality.

| Mode | Avg Quality | Evidence | Speedup | Missing Requirements | Replanner Agents |
|------|-------------|----------|---------|----------------------|------------------|
| single | `0.56` | `0.48` | `1.0x` | `20` | `0` |
| fixed | `0.74` | `0.78` | `3.48x` | `8` | `0` |
| adaptive | `0.88` | `0.94` | `3.5x` | `0` | `8` |

Controlled rubric lift report: [docs/evidence/improvement_v311.md](docs/evidence/improvement_v311.md).

## Evidence

| Evidence | Purpose |
|----------|---------|
| [benchmark_v320_real_smoke.md](docs/evidence/benchmark_v320_real_smoke.md) | v3.2 real stability smoke: single `0.537`, fixed `0.838`, adaptive `1.0` |
| [benchmark_v310.md](docs/evidence/benchmark_v310.md) | bounded real Codex CLI benchmark with failures preserved |
| [benchmark_v310_replanner_sample.md](docs/evidence/benchmark_v310_replanner_sample.md) | real planner + replanner follow-up sample |
| [swarm_100_agents_codex_cli_run_98b78a645c.md](docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | fixed 100-agent Codex CLI swarm |

## Status

Stable: Codex CLI swarm, adaptive workflow, broker reducer, evidence reports. Experimental: App-native bridge, A2A gateway, TEA. Full gates are in [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

## More

- Quickstart: [docs/QUICKSTART.md](docs/QUICKSTART.md)
- Troubleshooting/uninstall: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Brief / demos / video / outreach: [brief](docs/OFFICIAL_BRIEF.md), [demos](docs/DEMOS.md), [video](docs/VIDEO_SHOWCASE.md), [outreach](docs/OUTREACH.md)
- Comparison / limits / evidence / threat model / imports: [comparison](docs/CODEX_NATIVE_VS_OH_MY_DYNAMIC.md), [limits](docs/KNOWN_LIMITS.md), [evidence](docs/evidence/README.md), [threat model](docs/THREAT_MODEL.md), [v3 imports](docs/V3_MIGRATION_GUIDE.md)

MIT. See [LICENSE](LICENSE).
