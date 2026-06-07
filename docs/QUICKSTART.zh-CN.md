# 快速开始

这条路径先验证 oh-my-Dynamic，不会一开始就修改 Codex App 配置。首次运行平台支持 macOS、Linux 和 WSL；原生 Windows 尚未验证。

## 1. CLI-only 安全安装

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m doctor --json
```

如果没有安装 Codex CLI 或 App 插件，`doctor` 可能返回 `warn`。这对 dry-run 检查是可以接受的。

## 2. 5 分钟无 key 检查

```bash
python examples/real_repo_review.py \
  --dry-run \
  --run-id five-minute-demo \
  --output-dir /tmp/ohmy-evidence
```

这个命令不会启动 Codex CLI workers，也不会把公开 evidence 写进仓库。

## 3. 真实 Codex CLI review

前提：Codex CLI 已安装并登录。

```bash
codex --version
python -m doctor --json --strict-real-codex
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

这个命令会启动真实 `codex exec` workers。raw prompts/stdout/stderr 和 trace 保留在 `.orchestry/`；公开提交只应包含 compact evidence。

## 4. Codex App 插件安装

只有需要 App skill 入口时才运行：

```bash
bash install_plugin.sh
python -m doctor --json
```

安装器会在 `~/.agents` 下创建 symlink，并把本地插件合并进 `~/.agents/plugins/marketplace.json`。移动或删除 clone 后需要重新运行安装器。

卸载：

```bash
bash install_plugin.sh --uninstall
```

## 5. Adaptive replanner smoke

先跑 shape check：

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dry-run \
  --output-dir /tmp/ohmy-adaptive
```

确认要启动真实 Codex CLI workers 后，再跑真实 smoke：

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

## 6. 阅读 evidence

从这里开始：

- `docs/evidence/benchmark_v320_real_smoke.md`
- `docs/evidence/improvement_v311.md`
- `docs/evidence/README.md`

在对 App-native subagents、真实模型质量或 benchmark 结果做结论前，先读 `docs/KNOWN_LIMITS.zh-CN.md`。
