# Codex 原生 Agents vs oh-my-Dynamic

一句话：Codex 原生 agents 是执行 runtime；oh-my-Dynamic 是围绕 Codex CLI/App workflows 的 workflow、evidence、benchmark 和 policy harness。

Codex 原生 subagents 负责真正执行；oh-my-Dynamic 负责解释、规划、测量、记录和审计。

## 对比

| 维度 | Codex 原生 agents | oh-my-Dynamic |
|------|-------------------|---------------|
| 核心能力 | 官方并行 coding agents、worktrees、cloud/app runtime、官方调度 | planner/replanner、broker evidence、reducer、benchmark、demo validation |
| 执行隔离 | 由官方 runtime、worktrees、cloud environments 和 app surface 管理 | 当前已验证路径是 Codex CLI process swarm；worktree 写入模式需显式开启 |
| 用户体验 | App 原生体验，配置更少，直接开发循环最顺滑 | Skill/CLI/docs 入口，偏复现、评测和外部 review |
| 结果证据 | Codex UI、任务记录、diff 和 review surface | 可提交的 JSON/MD/dashboard evidence，适合 release、reviewer、audit |
| 动态重规划 | 取决于官方 runtime 暴露程度 | 显式记录 planner/replanner rounds、missing coverage、follow-up agents、reducer output |
| Benchmark | 官方 workflow 不一定为你的项目自动生成可提交 benchmark evidence | deterministic scoring、real smoke、demo validation、redaction checks |
| 协议方向 | 官方闭环体验更强 | 可继续靠近 MCP/A2A-style artifacts、外部 LLM review、第三方评测 |
| 最适合 | 直接开发、修 bug、重构、代码 review | 复杂任务拆解、模式对比、证据保留、产品化和对外说明 |

## 产品实际意义

这个项目不应该声称 Codex 不能并行 agents。OpenAI 已经把 Codex 描述为支持 multi-agent workflows、built-in worktrees 和 cloud environments 的产品方向。

oh-my-Dynamic 的实际价值不同：

- 把高层目标拆成可解释的 workflow rounds。
- 记录为什么创建某些 agents，以及它们产出了什么证据。
- 保存 sanitized compact artifacts，而不是提交 raw prompts 或 stdout。
- 给外部 reviewer 提供具体 benchmark 和 demo validation 报告。
- 如果未来有稳定公开的 native subagent APIs，它可以变成 Codex native subagent orchestrator。

## 未来最好的接入方式

如果 Codex App 或 App Server 暴露稳定 native subagent APIs，最好的方向是：

1. planner 生成任务图。
2. oh-my-Dynamic 把任务派发给 Codex native subagents。
3. broker 记录 events、artifacts、review requests、failures 和 dependencies。
4. replanner 根据 coverage gaps 追加 native follow-up agents。
5. reducer 输出 evidence reports、dashboards 和 benchmark summaries。

这样官方 runtime 继续负责执行层，同时保留 oh-my-Dynamic 的独特价值：可解释、可测量、可审计、可传播。
