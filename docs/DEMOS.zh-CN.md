# Demo 验证

这页说明 oh-my-Dynamic 在具体采用场景中提升了什么。当前 v3.6 demo
validation 是确定性的：它衡量任务覆盖、证据完整度、并行审查吞吐和基于缺口的
重规划，不声称真实模型质量提升。

## 提升什么

| 维度 | 含义 |
|------|------|
| 任务覆盖 | 更多需求 lane 被明确分配给 reviewer。 |
| 证据完整度 | 输出更常包含 artifact、命令、检查项和 known limits。 |
| 并行吞吐 | 多个 specialist lanes 以 swarm 形式运行，而不是单 reviewer 串行处理。 |
| 缺口驱动重规划 | adaptive 模式在需求未覆盖时追加 follow-up agents。 |
| 交接质量 | 报告保留缺失要求和下一步动作，方便人类决策。 |

## Demo 场景

| 场景 | 意义 |
|------|------|
| 前端建设 | 展示如何把 UI layout、state/data、a11y、响应式审查、测试和文档拆成 specialist lanes。 |
| Harness 工程 | 展示如何同时覆盖 eval fixtures、scoring、redaction、CI、evidence schema 和失败保留。 |
| 项目产品化 | 展示 adoption hardening：安装、doctor、quickstart、测试、coverage、release checklist、evidence。 |
| 安全与可信 | 展示 command surface、gateway auth、artifact poisoning、redaction、raw-output boundary 和 threat model 覆盖。 |

## 运行 Demo

下面都是安全的确定性 dry-run，不启动 Codex CLI workers。

```bash
python scripts/run_demo_validation.py --output /tmp/ohmy-demo-validation/demo_validation_v360.json
python examples/frontend_build_demo.py --output /tmp/ohmy-demo-validation/frontend_build.json
python examples/harness_engineering_demo.py --output /tmp/ohmy-demo-validation/harness_engineering.json
```

已提交证据：

- [evidence/demo_validation_v360.md](evidence/demo_validation_v360.md)
- [evidence/demo_validation_v360.json](evidence/demo_validation_v360.json)

## 当前 v3.6 数值

| Mode | 平均质量 | 证据完整度 | 并行加速估计 | 缺失要求 | Replanner Agents |
|------|----------|------------|--------------|----------|------------------|
| single | `0.56` | `0.48` | `1.0x` | `20` | `0` |
| fixed | `0.74` | `0.78` | `3.48x` | `8` | `0` |
| adaptive | `0.88` | `0.94` | `3.5x` | `0` | `8` |

最重要的 claim 不是“模型更聪明了”，而是：

> oh-my-Dynamic 在同一任务 rubric 下提升任务覆盖、证据完整度、并行审查吞吐，
> 以及基于缺口的自动重规划能力。

涉及 runtime claim 时，应把这些确定性 demo 数值和真实 Codex CLI evidence
一起引用。
