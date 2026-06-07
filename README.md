# oh-my-Dynamic

[![tests](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![coverage](https://img.shields.io/badge/coverage-82%25-brightgreen)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Codex dynamic workflow toolkit: planner/replanner orchestration, Codex CLI process swarms, broker evidence, benchmark artifacts, and App skills.

Core boundary: the verified large-scale backend today is **Codex CLI process swarm**, not Codex App-native isolated subagents. App-native isolated subagents still depend on Codex App runtime exposing that capability. Defaults are read-only; write/worktree patch mode must be explicitly enabled.

Latest release: [GitHub Releases](https://github.com/PIGU-PPPgu/oh-my-Dynamic/releases/latest)

## Use It Now

| Need | Command |
|------|---------|
| 5-minute no-key shape check | `python examples/real_repo_review.py --dry-run --run-id five-minute-demo` |
| Real 5-agent repo review | `python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard` |
| Adaptive planner/replanner proof | `python scripts/record_adaptive_workflow_evidence.py --required-coverage security,tests,docs,replanner-proof --force-missing-coverage replanner-proof --max-rounds 2 --max-agents 12 --max-parallel 4 --dashboard` |
| Fixed 20-agent swarm evidence | `python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5` |
| Improvement measurement | `python scripts/measure_improvement.py --suite benchmarks/repo_review.json --output docs/evidence/improvement_v311.json` |
| Deterministic benchmark shape check | `python scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output /tmp/benchmark.json` |

Codex App skill trigger:

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

## What Works

| Status | Capability |
|--------|------------|
| Stable | Codex CLI swarm, adaptive dynamic workflow, broker reducer, real repo review demo, static dashboard, deterministic quality eval |
| Beta | Worktree patch mode, checkpoint/resume, streaming JSONL events, capability routing |
| Experimental | Codex App bridge, A2A gateway, TEA protocol |

Main product path: **Codex CLI dynamic workflow**. App bridge, A2A gateway, and TEA stay as experimental contracts until the surrounding runtime/protocol surface is stable enough to rely on.

## Install

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

After installing the plugin, restart Codex App or open a new thread so skills are reloaded.

## Run

Adaptive workflow:

```bash
python -m dynamic_workflow "review this repo" \
  --max-rounds 2 \
  --max-agents 20 \
  --max-parallel 5 \
  --stream-events
```

Fixed swarm:

```bash
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
```

Real repo review:

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

Resume a checkpoint:

```bash
python -m dynamic_workflow --resume RUN_ID
```

## Evidence

| Evidence | What it proves |
|----------|----------------|
| [`docs/evidence/benchmark_v310.md`](docs/evidence/benchmark_v310.md) | v3.1 bounded real Codex CLI benchmark across single / fixed / adaptive modes, including failures and timeouts |
| [`docs/evidence/improvement_v311.md`](docs/evidence/improvement_v311.md) | Bilingual controlled same-fixture measurement: adaptive improves avg quality score by `+0.386` over single, evidence completeness by `+0.329`, and reduces missing requirements by `100%` |
| [`docs/evidence/benchmark_v310_replanner_sample.md`](docs/evidence/benchmark_v310_replanner_sample.md) | Real adaptive run where planner generated agents and replanner generated follow-up agents |
| [`docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md`](docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | Fixed 100-agent Codex CLI swarm evidence |
| [`docs/evidence/README.md`](docs/evidence/README.md) | Evidence format, redaction rules, and reproduction notes |

Controlled improvement evidence measures scoring/coverage lift on fixed fixtures. Real evidence proves runtime behavior. Both are compact and sanitized; raw prompts, stdout, stderr, and `.orchestry/` traces are not committed.

## Trust Gates

```bash
python test_suite.py
python -m pytest tests -q
python -m coverage run -m pytest tests -q
python -m coverage report --fail-under=80
python -m bandit -r . -c pyproject.toml
python -m doctor --json
```

Release evidence should also pass a path/sensitive-output scan:

```bash
! grep -R "/Users/" docs/evidence
! grep -R "raw prompt\\|stdout\\|stderr" docs/evidence
```

## Package Imports

Preferred v3 imports:

```python
from oh_my_dynamic.runtime.dynamic_workflow import DynamicWorkflowRuntime
from oh_my_dynamic.codex.codex_cli_swarm import CodexCliSwarmRuntime, CodexCliAgentSpec
from oh_my_dynamic.broker.agent_broker import AgentBroker
from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload
```

Root-level imports such as `from dynamic_workflow import DynamicWorkflowRuntime` still work for one major version, but they are compatibility façades. New code should use package imports. See [V3 Migration Guide](docs/V3_MIGRATION_GUIDE.md).

## Docs

Start with [docs/README.md](docs/README.md). Useful direct links:

| Topic | Link |
|-------|------|
| Codex CLI swarm smoke and scale notes | [docs/CODEX_CLI_SWARM_SMOKE.md](docs/CODEX_CLI_SWARM_SMOKE.md) |
| Native dynamic workflow proposal | [docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md](docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md) |
| Threat model | [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) |
| Release checklist | [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) |
| v3 migration | [docs/V3_MIGRATION_GUIDE.md](docs/V3_MIGRATION_GUIDE.md) |

## License

MIT. See [LICENSE](LICENSE).
