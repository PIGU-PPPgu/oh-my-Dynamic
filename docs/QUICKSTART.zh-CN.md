# 快速开始

这条路径适合第一次安装、验证、跑安全 demo，并了解 evidence 写到哪里。

## 1. 安装

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

预期结果：`doctor` 返回 `pass`，或给出明确的 `warn`。如果有 `fail`，先修好再跑真实 Codex CLI workers。

## 2. 5 分钟无 key 检查

```bash
python examples/real_repo_review.py --dry-run --run-id five-minute-demo
```

这个命令不会启动 Codex CLI workers。它只验证 compact JSON/Markdown evidence 的形状和脱敏行为。

默认 evidence 写到 `docs/evidence/`，除非你传入其他输出路径。

## 3. 真实 5-agent 仓库审查

前提：Codex CLI 已安装并登录。

```bash
codex --version
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

这个命令会启动真实 `codex exec` workers。raw prompts/stdout/stderr 和 trace 保留在 `.orchestry/`；公开提交只应包含 compact evidence。

## 4. Adaptive replanner smoke

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

这个命令用于证明 planner/replanner 流程。它比 dry-run 慢，并可能启动多个真实 Codex CLI workers。

## 5. 阅读 evidence

从这里开始：

- `docs/evidence/benchmark_v320_real_smoke.md`
- `docs/evidence/improvement_v311.md`
- `docs/evidence/README.md`

在对 App-native subagents、真实模型质量或 benchmark 结果做结论前，先读 `docs/KNOWN_LIMITS.zh-CN.md`。
