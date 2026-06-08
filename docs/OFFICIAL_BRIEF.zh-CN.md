# oh-my-Dynamic 官方可读 Brief

oh-my-Dynamic 是围绕 Codex 的 dynamic workflow 编排独立原型。它不是 OpenAI 官方产品，也不在品牌中使用 OpenAI、Codex 或 ChatGPT 的官方标志。

## 问题

Codex 已支持原生并行 coding-agent workflows。独立 workflow 工具真正需要的是可集成官方 runtime 的稳定公开 contract：受支持的 subagent dispatch、受限工具和上下文、structured events、artifact ownership、dependency metadata 和 reducer handoff。

## 这个项目证明了什么

- Codex CLI process swarm 可以通过 `codex exec` 运行真实并行 review workers。
- planner/replanner loop 可以根据 broker evidence、失败、低分输出和 coverage gap 追加 follow-up agents。
- broker evidence 可以保存 run id、agent counts、artifacts、failures、checkpoints、dashboards 和 compact public summaries，同时不提交 raw prompts/stdout/stderr。
- adoption gates 可以确定性验证：`doctor`、safe dry-runs、CI safe examples、coverage、Bandit、redaction checks。
- controlled rubric scoring 可以衡量 evidence coverage lift；真实 Codex CLI evidence 单独证明 process-swarm 执行路径。

## 这个项目不声称什么

oh-my-Dynamic 不声称由本项目实现了 Codex App-native isolated subagents。这里当前已验证的大规模执行路径是 Codex CLI process swarm。Codex native execution 应继续作为 runtime layer；oh-my-Dynamic 是围绕它的 planning、replanning、evidence、benchmark 和 audit harness。

## 证据

- adoption hardening evidence：`v3.4.0 - Adoption Hardening`
- visibility release：`v3.5.0 - Visibility And Identity`
- 固定 100-agent swarm evidence：`docs/evidence/swarm_100_agents_codex_cli_run_98b78a645c.md`
- 真实稳定性 smoke：`docs/evidence/benchmark_v320_real_smoke.md`
- controlled rubric lift：`docs/evidence/improvement_v311.md`
- evidence 规则：`docs/evidence/README.md`
- 已知边界：`docs/KNOWN_LIMITS.zh-CN.md`

## 5 分钟演示

```bash
python -m doctor --json
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

前两个命令安全，不启动真实 workers。后两个命令要求 Codex CLI 已安装、已登录，并且本地配置可用。

## 对 Codex Runtime 的请求

如果 Codex 向 extensions 或 external harnesses 暴露 public native dynamic workflow primitives，oh-my-Dynamic 可以作为具体 contract test 和 integration prototype。最关键的 runtime primitives 是：

- native subagent spawn，并拥有独立 context windows
- 每个 subagent 的 sandbox 和 tool-permission policy
- structured event stream 和 artifact ownership
- dependency-aware scheduler 和 bounded parallelism
- reducer handoff contract，包含 failure 和 checkpoint metadata

这个项目刻意保持边界清晰：它展示期望的 contract，但不声称拥有非官方的 Codex App 内部访问能力。
