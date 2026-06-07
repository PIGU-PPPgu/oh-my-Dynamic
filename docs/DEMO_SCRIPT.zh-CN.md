# 5 分钟演示脚本

这份脚本用于短演示，明确区分 safe commands 和真实 Codex CLI worker commands。

## 0. Setup

```bash
git clone https://github.com/PIGU-PPPgu/oh-my-Dynamic.git
cd oh-my-Dynamic
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## 1. 安全 readiness check

```bash
python -m doctor --json
```

预期：JSON status 是 `pass` 或 `warn`。如果只是 dry-run，Codex CLI warning 可以接受。

## 2. 安全 dry-run evidence

```bash
python examples/real_repo_review.py \
  --dry-run \
  --run-id five-minute-demo \
  --output-dir /tmp/ohmy-evidence
```

这个命令不会启动真实 workers。

展示：

```bash
ls -la /tmp/ohmy-evidence
sed -n '1,120p' /tmp/ohmy-evidence/five-minute-demo.md
python -m json.tool /tmp/ohmy-evidence/five-minute-demo.json | head -80
```

## 3. 可选真实 Codex CLI readiness

```bash
python -m doctor --json --strict-real-codex
```

这个命令会启动一个最小只读 `codex exec` smoke。只有在 Codex CLI 已安装、已登录且配置可用时运行。

## 4. 可选真实 5-agent review

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

这个命令会启动真实 Codex CLI workers。raw prompts/stdout/stderr 保留在 `.orchestry/`。只提交 compact sanitized evidence。

## 5. 结束说明

明确边界：

- 已验证路径：Codex CLI process swarm。
- 不声称：已经实现 App-native isolated subagents。
- 请求：Codex runtime 暴露 subagent spawn、sandbox/tool policy、events、artifacts、scheduler 和 reducer handoff。
