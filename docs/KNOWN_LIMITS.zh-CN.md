# 已知边界

这些边界是有意保留的，发布说明、评审和 benchmark claim 都应该重复说明。

## Runtime 边界

- Codex 已支持原生并行 coding-agent workflows。
- oh-my-Dynamic 不声称由本项目实现 Codex App native runtime。
- 本项目目前已验证的大规模执行路径是 Codex CLI process swarm。
- 如果未来有公开 native subagent APIs，oh-my-Dynamic 应把它作为执行后端。
- 除非 Codex App 显式开放 bridge，本地 Python runtime 不能直接调用 Codex App 内部 LLM API。

## Benchmark

- 真实 benchmark 会慢。Adaptive run 更慢，因为包含 planner、workers、replanner、follow-up workers 和 reducer。
- Controlled improvement measurement 不是真实模型质量证明。它衡量的是固定 fixture 上的确定性 rubric 覆盖率。
- 真实 Codex CLI evidence 证明的是 process-swarm 行为和证据捕获，不证明本项目拥有 Codex App-native 执行层。

## Evidence 与隐私

- raw `.orchestry/` traces、prompts、stdout、stderr 不提交。
- 公开 evidence 应该是 compact、已脱敏的 JSON/Markdown/dashboard records。
- Evidence 可以保留失败和 timeout；保留失败比隐藏不完整结果更可信。

## 写入模式

- 默认执行是 read-only。
- Worktree patch mode 必须显式开启。
- Agent worktrees 不会自动 merge。patch/diff 是供 review 的 evidence，不会自动进入 `main`。

## 采用注意事项

- 真实 Codex CLI run 需要本地安装并登录 Codex CLI。
- 插件安装使用指向 `~/.agents` 的 symlink；移动 clone 后需要重新运行 `install_plugin.sh`。
- bash/symlink 安装器面向 macOS、Linux 和 WSL；原生 Windows 尚未验证。
- 外部 provider API key 只用于本地 provider-backed Python runtime；普通 Codex App skill 使用或 Codex CLI 登录态 swarm 不需要这些 key。
