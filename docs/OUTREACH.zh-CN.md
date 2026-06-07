# 对外传播包

用于把 oh-my-Dynamic 发给外部 reviewer、Codex/OpenAI runtime 团队或技术社区。不要暗示官方关联。

## 150 字简介

oh-my-Dynamic 是一个围绕 Codex 的独立 dynamic workflow 原型。它展示了 planner/replanner 编排、Codex CLI process swarm、broker evidence、严格 readiness checks 和 controlled evaluation reports。当前已验证的大规模路径是 `codex exec` process fan-out，不是 App-native isolated subagents。项目刻意明确这个边界：它不声称拥有 Codex App 内部的非官方访问能力。它提供的是一个具体、可测试的 contract：如果 Codex runtime 暴露 isolated subagent spawn、per-agent sandbox/tool policy、event streams、artifact ownership、checkpoint metadata 和 reducer handoff，这套项目可以作为验证样例。

## 500 字技术简介

oh-my-Dynamic 探索的是：如果 Codex runtime 暴露 native subagent orchestration primitives，dynamic workflows 可以是什么样。当前实现不依赖私有 Codex App API。它已验证的大规模后端是 Codex CLI process swarm：orchestrator 启动多个 `codex exec` workers，捕获 worker 输出，把结构化 envelopes 写入 broker，然后把 evidence reducer 成 compact summaries。

项目围绕三个概念。第一，planner/replanner orchestration：初始 planner 把高层目标拆成 agents，replanner 根据 failures、low-score outputs、missing coverage lanes 和 broker evidence 追加 follow-up agents。第二，evidence discipline：worker traces、artifacts、failures、dashboards、checkpoints 和 compact Markdown/JSON records 与 raw prompts/stdout/stderr 分离。公开 evidence 会脱敏并保持 compact。第三，adoption hardening：新用户可以先跑不启动真实 workers 的 safe dry-run，再用 `doctor --strict-real-codex` 验证本地 `codex exec` 是否可用，最后再启动真实 workers。

项目不声称已经实现 Codex App-native isolated subagents。它把这项能力明确标记为 runtime-gated 和 experimental。如果 Codex App 暴露 native spawn、sandbox、scheduler、tool permission、event 和 artifact primitives，oh-my-Dynamic 可以作为这个 surface 的具体 contract test。在此之前，真实可扩展路径是 Codex CLI process fan-out。

相关证据包括 v3.4 adoption hardening release、100-agent fixed swarm evidence、real stability smoke、controlled rubric lift reports，以及 known-limits/threat-model docs。对 runtime owners 最相关的请求不是背书，而是一个清晰的 native workflow contract，让 plugin authors 可以安全地 fan out isolated subagents 并 reducer 它们的 artifacts。

## GitHub Issue / Discussion

标题：Proposal: native dynamic workflow primitives for Codex App

正文：

oh-my-Dynamic 是一个独立原型，展示了今天如何通过 Codex CLI process swarm 实现 planner/replanner workflow、bounded fan-out、broker evidence 和 reducer handoff。它不声称已经实现 App-native isolated subagents。

真正的请求是 Codex App/runtime 提供 native contract：

- isolated subagent spawn
- per-agent sandbox and tool permissions
- event streams and artifact ownership
- dependency-aware bounded parallelism
- reducer handoff with failure/checkpoint metadata

参考 brief：`docs/OFFICIAL_BRIEF.md`

## Email

Subject: Independent Codex dynamic workflow prototype and runtime contract proposal

Hi,

I built oh-my-Dynamic as an independent prototype for dynamic workflow orchestration around Codex. It uses Codex CLI process swarms for verified large-scale execution and keeps App-native isolated subagents clearly marked as runtime-gated, not implemented.

The project may be useful as a concrete contract test for future Codex runtime primitives: isolated subagent spawn, sandbox/tool policy, event streams, artifact ownership, scheduler semantics, and reducer handoff.

Brief: `docs/OFFICIAL_BRIEF.md`
Repo: https://github.com/PIGU-PPPgu/oh-my-Dynamic

## X Thread

1. 做了一个独立 Codex dynamic workflow 原型：oh-my-Dynamic。
2. 当前已验证的大规模路径：通过 `codex exec` 启动 Codex CLI process swarms。
3. 核心 loop：planner -> parallel workers -> broker evidence -> replanner -> reducer。
4. 边界明确：不声称已经实现 App-native isolated subagents。
5. 请求：Codex runtime 暴露 subagent spawn、sandbox/tool policy、events、artifacts、scheduler、reducer handoff。
6. Brief：`docs/OFFICIAL_BRIEF.md`

## Hacker News 风格

Show HN: oh-my-Dynamic, an independent dynamic workflow prototype for Codex

I built a prototype that explores planner/replanner workflows around Codex using Codex CLI process swarms. It focuses on evidence discipline, strict readiness checks, and clear boundaries. It does not claim to implement Codex App-native isolated subagents; instead it documents what runtime primitives would be needed.

## 发给 OpenAI/Codex 团队的材料

建议发送：

- `docs/OFFICIAL_BRIEF.md`
- `docs/DEMO_SCRIPT.md`
- `docs/KNOWN_LIMITS.md`
- `docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md`
- `v3.5.0` release link

不要发送 raw `.orchestry/` traces、prompts、stdout、stderr 或私有本地路径。
