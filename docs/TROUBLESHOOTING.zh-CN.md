# 故障排查与卸载

## 平台

- 首次运行支持：macOS、Linux、WSL。
- 原生 Windows 尚未验证。bash 安装器和 symlink 型 Codex App 插件路径建议在 WSL 中使用。

## Doctor

安全 dry-run 准备度：

```bash
python -m doctor --json
```

真实 Codex CLI worker 准备度：

```bash
python -m doctor --json --strict-real-codex
```

`--strict-real-codex` 会运行一个最小只读 `codex exec` smoke。如果 Codex CLI 缺失、未登录、本地配置阻塞，或 sandbox 不可用，它可能失败。

## Codex CLI 问题

检查：

```bash
codex --version
python -m doctor --json --strict-real-codex
```

如果 strict doctor 失败，先修复 Codex CLI 登录/配置，再跑真实 swarm 命令。dry-run 不需要 Codex CLI。

## 插件安装与卸载

只有需要 Codex App skills 时才安装：

```bash
bash install_plugin.sh
```

这个命令会在 `~/.agents/skills` 和 `~/.agents/plugins` 下创建 symlink，并把 `oh-my-dynamic` 条目合并进 `~/.agents/plugins/marketplace.json`。

卸载：

```bash
bash install_plugin.sh --uninstall
```

卸载流程只会移除指向当前 clone 的 symlink，并在备份 JSON 后移除 marketplace 条目。非 symlink 路径会跳过，避免删除用户内容。

## 清理生成文件

raw traces 和 worker 输出：

```bash
rm -rf .orchestry
```

新用户 dry-run 建议写到仓库外：

```bash
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence
```

只有为 release 明确生成的 compact sanitized evidence 才应该提交。

## 常见失败

| 现象 | 可能原因 | 修复 |
|------|----------|------|
| `doctor` 对 `codex_cli` 返回 `warn` | 没有 Codex CLI | dry-run 可忽略；真实 workers 需要安装并登录 Codex CLI |
| `--strict-real-codex` 失败 | CLI 登录、配置或 sandbox 问题 | 先手动跑通 Codex CLI，再重试 strict doctor |
| `unknown variant ... service_tier` | Codex CLI config 使用了不支持的 service tier | 把本地 Codex CLI config 改成支持的值，例如 `fast` 或 `flex` |
| 安装器提示目标存在且不是 symlink | 已有用户 skill/plugin 路径 | 手动备份，或换 profile |
| 移动 clone 后插件失效 | symlink target 移动 | 重新运行 `bash install_plugin.sh` |
| dry-run 弄脏 `docs/evidence` | 漏了 `--output-dir` | 首次检查使用 `/tmp/ohmy-evidence` |
