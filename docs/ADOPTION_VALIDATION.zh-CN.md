# 采用验证

这份 checklist 用于让 reviewer 或维护者从全新 clone 验证 oh-my-Dynamic。目标是发现采用阻塞点，不是证明新的 runtime 行为。

## 范围

- 安装说明是否清楚
- Codex CLI 和插件状态是否可检查
- dry-run evidence 形状是否正确
- 真实 5-agent 仓库审查是否能跑
- adaptive replanner smoke 是否清楚
- evidence 隐私和能力边界是否明确

## Checklist

1. 全新 clone 和安装：

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m pip install -e ".[dev]"
bash install_plugin.sh
python -m doctor --json
```

2. 无 key smoke：

```bash
python examples/real_repo_review.py --dry-run --run-id adoption-dry-run
```

3. 真实 5-agent review：

```bash
codex --version
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

4. Adaptive shape check：

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dry-run
```

5. 可选真实 adaptive smoke：

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

## Reviewer 输出

请 reviewer 汇报：

- 安装在哪里失败，或哪里让人犹豫
- README 是否夸大了 App-native isolated subagents
- compact evidence 是否足够可信
- dry-run 和 real-run evidence 是否区分清楚
- raw `.orchestry/` traces 是否留在本地
- 下一版最值得修的一个问题

更深入的外部评审提示词见 `docs/REVIEW_PROMPTS.zh-CN.md`。
