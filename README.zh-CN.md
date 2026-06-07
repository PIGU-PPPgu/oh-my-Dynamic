# oh-my-Dynamic

[![tests](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![coverage](https://img.shields.io/badge/coverage-82%25-brightgreen)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[English](README.md)

面向 Codex 的 dynamic workflow 工具：planner/replanner 编排、Codex CLI 进程级 swarm、broker 证据链和测评报告。

**边界：** 目前已验证的大规模执行后端是 Codex CLI process swarm。Codex App-native isolated subagents 仍取决于 Codex App 是否开放对应 runtime。默认只读。

## 快速开始

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

Codex App skill 触发句：

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

## 运行

```bash
# 5 分钟无 key 检查
python examples/real_repo_review.py --dry-run --run-id five-minute-demo

# 真实 5-agent 仓库审查
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard

# Adaptive workflow
python -m dynamic_workflow "review this repo" --max-rounds 2 --max-agents 20 --max-parallel 5 --stream-events

# 固定 20-agent swarm
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
```

## 测评提升

中英双语报告：[docs/evidence/improvement_v311.md](docs/evidence/improvement_v311.md)

| 对比 | 质量分 | 证据完整度 | 缺失要求 |
|------|--------|------------|----------|
| fixed vs single | `+0.286` / `+46.6%` | `+0.229` | `-74.3%` |
| adaptive vs single | `+0.386` / `+62.9%` | `+0.329` | `-100%` |

这是受控同题评分。涉及 runtime 能力时，应同时引用真实 Codex CLI evidence。

## 证据

| 证据 | 用途 |
|------|------|
| [benchmark_v320_real_smoke.md](docs/evidence/benchmark_v320_real_smoke.md) | v3.2 真实稳定性 smoke：single `0.537`，fixed `0.838`，adaptive `1.0` |
| [benchmark_v310.md](docs/evidence/benchmark_v310.md) | 有失败保留的真实 Codex CLI benchmark |
| [benchmark_v310_replanner_sample.md](docs/evidence/benchmark_v310_replanner_sample.md) | 真实 planner + replanner follow-up 样例 |
| [swarm_100_agents_codex_cli_run_98b78a645c.md](docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | 固定 100-agent Codex CLI swarm |

## 状态

| Stable | Beta | Experimental |
|--------|------|--------------|
| Codex CLI swarm、adaptive workflow、broker reducer、证据报告 | worktree patch mode、checkpoint/resume、streaming events | Codex App bridge、A2A gateway、TEA |

## 验证

```bash
python test_suite.py
python -m pytest tests -q
python -m coverage run -m pytest tests -q
python -m coverage report --fail-under=80
python -m bandit -r . -c pyproject.toml
```

## 更多

- 快速开始：[docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md)
- 文档索引：[docs/README.md](docs/README.md)
- 已知边界：[docs/KNOWN_LIMITS.zh-CN.md](docs/KNOWN_LIMITS.zh-CN.md)
- 证据规则：[docs/evidence/README.md](docs/evidence/README.md)
- 威胁模型：[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- v3 import 迁移：[docs/V3_MIGRATION_GUIDE.md](docs/V3_MIGRATION_GUIDE.md)

MIT. 见 [LICENSE](LICENSE)。
