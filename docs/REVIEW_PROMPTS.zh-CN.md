# 外部评审提示词

这些提示词可交给 GPT Pro、GLM、Claude Code、Codex 或其他 reviewer。只提交 compact summary，不提交 raw prompts/stdout/stderr。

## 采用体验评审

```text
请从外部采用者视角评审 oh-my-Dynamic v3.3。

重点关注：
- 安装失败点
- README 或 Quickstart 是否容易误解
- Codex App-native 与 Codex CLI process-swarm 边界
- evidence 可信度
- benchmark 解读
- 安全或采用阻碍
- examples 是否按文档可运行

输出：
1. Top risks
2. Missing adoption blockers
3. Docs confusion
4. Evidence or benchmark concerns
5. Recommended next release
```

## 安全边界评审

```text
请评审 oh-my-Dynamic v3.3 的安全边界。

重点关注：
- worker environment handling
- codex exec args 和 sandbox 假设
- broker artifact poisoning
- evidence redaction
- raw .orchestry retention
- gateway/auth boundaries
- worktree patch mode 和 no-auto-merge 行为

输出：
1. High severity findings
2. Medium severity findings
3. False-positive or already-mitigated risks
4. Concrete tests or docs to add
```

## Benchmark 评审

```text
请评审 oh-my-Dynamic v3.3 的 benchmark claims。

重点关注：
- controlled improvement measurement 与 real Codex CLI evidence 的区别
- single/fixed/adaptive 对比是否公平
- timeout/failure handling
- evidence completeness scoring
- 哪些 claim 被支持，哪些 claim 还不被支持

输出：
1. Supported claims
2. Unsupported or overstated claims
3. Missing measurements
4. Recommended benchmark changes
```
