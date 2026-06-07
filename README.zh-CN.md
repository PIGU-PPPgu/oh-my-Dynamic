<div align="center">
  <img src="assets/icon.svg" alt="oh-my-Dynamic" width="112" height="112">
  <h1>oh-my-Dynamic</h1>
  <p><strong>面向 Codex 的 dynamic workflow 工具。</strong></p>
  <p><a href="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml"><img src="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg" alt="tests"></a> <a href="https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml"><img src="https://img.shields.io/badge/coverage-82%25-brightgreen" alt="coverage"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a></p>
  <p><a href="README.md">English</a></p>
  <a href="assets/oh-my-dynamic-showcase.mp4"><img src="assets/showcase-preview.gif" alt="oh-my-Dynamic 动态展示预览" width="760"></a>
  <p><a href="assets/oh-my-dynamic-showcase.mp4">打开完整 75 秒 MP4</a> · <a href="docs/VIDEO_SHOWCASE.zh-CN.md">渲染源码</a></p>
</div>

**边界：** 目前已验证的大规模执行后端是 Codex CLI process swarm。Codex App-native isolated subagents 仍取决于 Codex App 是否开放对应 runtime。默认只读。

## 快速开始

CLI-only 安全路径：

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

真实 Codex CLI workers：

```bash
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

Codex App 插件安装：

```bash
bash install_plugin.sh
```

插件安装会修改本地 `~/.agents` symlink 和 marketplace JSON。runtime workers 默认仍只读。

Codex App skill 触发句：

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务；App runtime 可用时使用内部 Codex subagents，否则走 in-chat fallback；大规模走 Codex CLI swarm。
```

## 运行

```bash
# Safe: 无 key、无真实 workers、写到仓库外
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence

# Real: 启动 Codex CLI workers
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard

# 真实 adaptive workflow
python -m dynamic_workflow "review this repo" --max-rounds 2 --max-agents 20 --max-parallel 5 --stream-events

# 成本更高的固定 swarm
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
```

## 受控 Rubric 提升

中英双语报告：[docs/evidence/improvement_v311.md](docs/evidence/improvement_v311.md)

这是受控同题 rubric 评分，不是真实模型质量证明。涉及 runtime 能力时，应同时引用真实 Codex CLI evidence。

| 对比 | 质量分 | 证据完整度 | 缺失要求 |
|------|--------|------------|----------|
| fixed vs single | `+0.286` / `+46.6%` | `+0.229` | `-74.3%` |
| adaptive vs single | `+0.386` / `+62.9%` | `+0.329` | `-100%` |

## 证据

| 证据 | 用途 |
|------|------|
| [benchmark_v320_real_smoke.md](docs/evidence/benchmark_v320_real_smoke.md) | v3.2 真实稳定性 smoke：single `0.537`，fixed `0.838`，adaptive `1.0` |
| [benchmark_v310.md](docs/evidence/benchmark_v310.md) | 有失败保留的真实 Codex CLI benchmark |
| [benchmark_v310_replanner_sample.md](docs/evidence/benchmark_v310_replanner_sample.md) | 真实 planner + replanner follow-up 样例 |
| [swarm_100_agents_codex_cli_run_98b78a645c.md](docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | 固定 100-agent Codex CLI swarm |

## 状态

Stable：Codex CLI swarm、adaptive workflow、broker reducer、证据报告。Experimental：App-native bridge、A2A gateway、TEA。完整 gates 见 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)。

## 更多

- 快速开始：[docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md)
- 故障排查/卸载：[docs/TROUBLESHOOTING.zh-CN.md](docs/TROUBLESHOOTING.zh-CN.md)
- 官方 brief / demo / 视频 / outreach：[brief](docs/OFFICIAL_BRIEF.zh-CN.md)、[demo](docs/DEMO_SCRIPT.zh-CN.md)、[video](docs/VIDEO_SHOWCASE.zh-CN.md)、[outreach](docs/OUTREACH.zh-CN.md)
- 文档索引：[docs/README.md](docs/README.md)
- 已知边界：[docs/KNOWN_LIMITS.zh-CN.md](docs/KNOWN_LIMITS.zh-CN.md)
- 证据规则：[docs/evidence/README.md](docs/evidence/README.md)
- 威胁模型：[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- v3 import 迁移：[docs/V3_MIGRATION_GUIDE.md](docs/V3_MIGRATION_GUIDE.md)

MIT. 见 [LICENSE](LICENSE)。
