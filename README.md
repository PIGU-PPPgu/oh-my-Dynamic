# oh-my-Dynamic 🔄

[![tests](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml/badge.svg)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![coverage](https://img.shields.io/badge/coverage-81%25-brightgreen)](https://github.com/PIGU-PPPgu/oh-my-Dynamic/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**多 Agent 编排引擎 / Codex Dynamic Workflows 原型** —— 对齐 Anthropic Dynamic Workflows + VMAO 论文架构（arXiv 2603.11445），支持 Codex App skill、Codex CLI swarm、adaptive planner/replanner 和主流大模型。

> 核心边界：当前可验证的大规模真实能力是 **Codex CLI process swarm**，不是 Codex App-native isolated subagents；App-native isolated subagents 仍取决于 Codex App runtime 是否暴露该能力。默认 read-only，并通过 broker/evidence/dashboard 留证。

## Use It Now

| 入口 | 命令 | 证明什么 |
|------|------|----------|
| 5 分钟 dry-run | `python examples/real_repo_review.py --dry-run --run-id five-minute-demo` | 安装、JSON/Markdown evidence 形状、无 API key 路径 |
| 真实 5-agent repo review | `python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard` | 真实 Codex CLI workers、broker reducer、dashboard |
| v2.2 adaptive replanner proof | `python scripts/record_adaptive_workflow_evidence.py --required-coverage security,tests,docs,replanner-proof --force-missing-coverage replanner-proof --max-rounds 2 --max-agents 12 --max-parallel 4 --dashboard` | planner 生成 agents，trigger policy 发现缺口，replanner 追加 follow-up agents |

Latest release and committed evidence: <https://github.com/PIGU-PPPgu/oh-my-Dynamic/releases/latest>

Codex App skill 触发句仍可用：

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

## Trust Gates

| Gate | Command |
|------|---------|
| Test + coverage | `python test_suite.py && python -m coverage run test_suite.py && python -m coverage report --fail-under=70` |
| Security scan | `python -m bandit -r . -c pyproject.toml` |
| Local install doctor | `python -m doctor --json` |
| Deterministic benchmark | `python scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output /tmp/benchmark.json` |
| Evidence redaction | `! grep -R "/Users/" docs/evidence` |

Committed benchmark baseline: [`docs/evidence/benchmark_v240.md`](docs/evidence/benchmark_v240.md). It is a deterministic dry-run shape check, not a real Codex CLI quality benchmark.

## ✨ 特性

- 🎯 **明确目标**：不是只做 prompt 技巧，而是为 Codex Native Dynamic Workflows 提供可验证原型和接口提案
- 🧠 **Codex App internal subagent backend**：在 Codex App 暴露 subagent tools/runtime 时，默认使用真实 Codex subagents，并继承当前 App 内部 LLM；无需 API key
- 📨 **A2A / Agent Broker**：受控 message、artifact、handoff、review request/response 和 audit trace，让 subagents 不只是并行跑，还能有证据链地协作
- 🧭 **Dynamic Workflow v2.2**：Codex CLI planner/replanner 先拆任务、运行后由 deterministic trigger policy 发现 missing coverage / low score / failed agents 并继续派生 follow-up agents；由 broker-aware reducer 汇总 evidence，支持 round-aware dashboard、流式事件、checkpoint/resume、coverage gate 和质量 eval
- 🌿 **Worktree 写入隔离**：显式开启写代码并发时，每个 Codex CLI worker 使用独立 git worktree，默认只产出 patch/diff artifacts，不自动 merge
- 🤖 **多模型支持**：GLM、OpenAI GPT、Claude、Gemini、DeepSeek、通义千问/Qwen、Moonshot/Kimi、硅基流动…… 自动识别模型名选择对应 provider
- 🔗 **串行编排**（Orchestrator）：Planner → Builder → Reviewer 流水线，含自动重试和 review 打回
- 👥 **并行团队**（TeamEngine）：多 agent 并行抢任务，消息总线通信
- 🧪 **Sandboxed Fan-out Runtime**：本地原型可并发启动 10/50/100+ isolated workers，每个 worker 有独立 sandbox、context 和 tool grants
- 🕸️ **DAG 任务图**：依赖感知的并行执行，自动拓扑排序
- 🔄 **动态重规划**（Dynamic Replan）：运行中根据中间结果调整计划
- 🧬 **TEA 工具进化**：LLM 驱动的工具自动分析、改进和回滚
- 📊 **可视化**：自动生成 DAG 的 DOT/SVG 图
- 🛡️ **安全**：TEA 工具 AST 校验 + 子进程隔离、线程安全消息总线、循环超时保护

## 能力状态

| 状态 | 能力 |
|------|------|
| Stable | Codex CLI swarm、adaptive dynamic workflow、broker reducer、真实 repo review demo、静态 observability dashboard、deterministic quality eval |
| Beta | worktree patch mode、checkpoint/resume、streaming progress events、capability routing |
| Experimental | Codex App bridge、A2A gateway、TEA protocol |

主线产品路径是 **Codex CLI dynamic workflow**。Codex App bridge、A2A gateway 和 TEA protocol 保留为 experimental contract / research track，不作为当前默认落地路径。

## v2.2 结构边界

```text
dynamic_workflow.py
  planner / replanner / checkpoint / reducer / stream events
        │
        ▼
codex_cli_swarm.py
  public facade + runtime coordinator
        │
        ├─ codex_swarm_cli.py         CLI parsing / default shard specs
        ├─ codex_swarm_models.py      dataclasses / public trace shape
        ├─ codex_swarm_process.py     single codex exec worker lifecycle
        ├─ codex_swarm_scheduler.py   dependency validation / layers / batches
        ├─ codex_swarm_artifacts.py   prompts / manifests / traces / broker artifacts
        └─ codex_worker.py            codex exec argv / env / timeout
```

新增调度策略优先进入 `dynamic_workflow.py`；新增 worker 生命周期、trace、artifact 或 process 细节优先进入 swarm 执行层 helper。

## 架构

```
用户目标 → [Planner] → 子任务列表
                          ↓
                    拓扑排序 + 依赖检查
                          ↓
                    [Builder] 逐个执行 ←── 上下文注入（依赖任务的输出）
                          ↓
                    [Reviewer] 审查质量
                       ↙      ↘
                   通过 → done  打回 → 重试(最多N次)
                          ↓
                    最终输出汇总
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `task.py` | Task 状态机（TaskStatus 枚举 + 合法转换表） |
| `agents.py` | 三种角色定义（planner/builder/reviewer） |
| `llm_client.py` | **通用 LLM 客户端**（`call_llm()` 自动识别模型选择 provider，`call_glm()` 保留兼容） |
| `orchestrator.py` | 串行编排引擎（核心调度器） |
| `team_engine.py` | 并行团队引擎（多 agent 协作） |
| `dag.py` | DAG 任务图 + 并行执行器 |
| `dynamic_replan.py` | 动态重规划（运行中调整策略） |
| `tea_protocol.py` | TEA 工具进化协议（LLM 驱动的工具改进） |
| `message_bus.py` | Agent 间消息总线（文件系统队列，线程安全） |
| `agent_broker.py` | A2A-style 协作 broker：policy、messages、artifacts、handoff、review request/response、audit trace |
| `broker_gateway.py` | 本地 HTTP/SSE gateway：Agent Card、agents/inbox、task snapshot、events、messages、artifacts、handoffs、review requests/responses |
| `broker_reducer.py` | Broker-aware reducer：读取 artifacts、失败、依赖图、review responses 和 worktree diff artifacts |
| `codex_app_bridge.py` | Codex App subagent bridge：dispatch plan、subagent prompt、JSON envelope、broker ingestion |
| `codex_cli_swarm.py` | Codex CLI swarm façade：保留 public imports 和 runtime coordinator |
| `codex_swarm_cli.py` | Codex CLI swarm 命令行解析与默认 shard spec 生成；`python -m codex_cli_swarm` 仍兼容 |
| `codex_swarm_models.py` | Codex CLI swarm dataclasses：agent spec、worker result、trace |
| `codex_swarm_process.py` | 单个 `codex exec` worker 生命周期：prompt、process、envelope、result event |
| `codex_swarm_scheduler.py` | Codex CLI swarm 依赖校验、拓扑层和 batch helper |
| `codex_swarm_artifacts.py` | Codex CLI swarm prompt、manifest、trace、broker/worktree artifact helper |
| `codex_worker.py` | Codex CLI worker 命令、环境和 timeout helper，隔离执行层细节 |
| `dynamic_workflow.py` | Planner/replanner dynamic workflow runtime：多轮派生 Codex CLI agents 并最终 reducer |
| `workflow_config.py` | Dynamic workflow 质量阈值与默认评分配置 |
| `workflow_observer.py` | 从 broker/trace/checkpoint 生成静态 observability dashboard |
| `eval_runner.py` | deterministic quality eval：按任务 fixture、关键词、证据项和最低分评估 agent 输出 |
| `native_runtime.py` | sandboxed fan-out runtime 原型（isolated worker、tool grants、trace、reducer） |
| `pipeline.py` | 端到端 Pipeline（组合所有组件） |
| `stop_conditions.py` | 停止条件（迭代上限 / token 预算 / 收敛检测） |
| `synthesis.py` | 结果汇总 |
| `token_tracker.py` | Token 预算追踪 |
| `validator.py` | 验证框架（单元/集成/端到端） |
| `prompt_kit.py` | Prompt 工程工具包 |
| `visualize.py` | DAG 可视化（DOT/SVG） |
| `worktree.py` | Git worktree 管理 |
| `protocol_adapters.py` | MCP/A2A 风格协议适配层（tool descriptor、Agent Card、Task payload） |
| `examples/` | 无需 API Key 的端到端 demo |
| `docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md` | Codex 原生 dynamic workflows 能力提案 |

## 快速开始

### 1. 安装 Codex App 插件

在 Codex App 里使用前，先把插件安装到个人 `.agents` 目录：

```bash
cd /path/to/oh-my-Dynamic
bash install_plugin.sh
```

安装完成后，重启 Codex App，或至少新开一个 thread，让插件与 skills 重新加载。

可用这些路径验证安装结果：

```bash
ls -l ~/.agents/skills/oh-my-dynamic
ls -l ~/.agents/skills/multi-agent-run
python -m json.tool ~/.agents/plugins/marketplace.json >/dev/null
```

`~/.agents/plugins/marketplace.json` 中应包含 `oh-my-dynamic`，并指向当前 clone 的 `codex-plugin` 目录。安装脚本会保留 marketplace 中的其他插件条目；如果需要修改已有 JSON，会先创建 `.bak.<timestamp>` 备份。当前安装方式使用符号链接，移动或删除这个仓库会让已安装插件失效；移动后重新运行 `bash install_plugin.sh` 即可刷新路径。

### 2. Codex App 零配置使用

安装插件后，重启 Codex App 或新开一个 thread，直接输入：

```text
[$oh-my-dynamic:multi-agent-run] 用 dynamic workflow 处理这个任务，必要时自动 planner/replanner，默认内部 Codex，若我要求大规模则用 Codex CLI swarm。
```

或：

```text
[$oh-my-dynamic:multi-agent-run] 用 Codex CLI swarm 启动 20 个真实 Codex agents，max_parallel=5，审查这个仓库。
```

默认模式会优先使用 **Codex App internal subagent backend**：只要 Codex App 当前环境提供 subagent tools/runtime，插件/skill 就应启动真实 Codex subagents 来执行拆解、worker 分析、review、replan 和 synthesis。这些 subagents 默认继承当前 Codex App 内部 LLM，不需要配置 `.env`，也不需要外部 provider API key。

如果当前 Codex App 环境没有暴露 subagent tools/runtime，则退回到插件级 dynamic-workflow-style 编排：仍使用当前 Codex App 会话做结构化拆解、分 lane 分析和汇总，但这不是 runtime 级 isolated subagents。需要几十/几百真实 workers 时，使用 Codex CLI swarm。

只有当你明确要运行本地 Python engine、接外部模型、生成 dashboard 文件时，才需要下面的可选配置。

#### 5 分钟零配置 demo

不配置任何模型 API key，也不启动真实 Codex CLI worker 时，可以先跑 deterministic demo 验证安装和输出形状：

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/real_repo_review.py --dry-run --run-id five-minute-demo
```

如果你已经登录 Codex CLI，再跑真实 5-agent repo review：

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"'
```

#### LLM 执行模式说明

| 模式 | 默认 LLM | 是否需要外部 API Key | 是否是真 isolated workers |
|------|----------|----------------------|---------------------------|
| Codex App internal subagent backend | Codex App 当前内部 LLM，由 App-native subagents 继承 | 否 | 是，前提是 Codex runtime 提供 subagent tools/runtime、isolated sandboxes、tool permissions 和 scheduler |
| Codex App 插件级编排 fallback | Codex App 当前会话的内部 LLM | 否 | 否；是在当前会话中执行 dynamic-workflow-style 编排 |
| `codex_cli_swarm.py` backend | 本机 `codex exec` 登录态/配置 | 否（使用已有 Codex CLI 登录态） | 是，进程级独立上下文；可并发几十到上百个 Codex CLI workers，结果进入 AgentBroker |
| 本地 `native_runtime.py` fan-out | 调用传入的 `llm_fn`，demo 默认 mock | 否（mock）/ 是（真实外部模型） | 是本地 isolated worker runtime：独立 sandbox 目录、独立 context、tool grants、trace |
| 本地 Python engine + 外部模型 | `llm_client.py` 路由到配置的 provider | 是 | 可并发 worker，但不是 Codex App 内部 subagents |

也就是说：**装上插件后，在 Codex App 里默认不需要 API Key；当 App-native subagent backend 可用时，应使用真实 Codex subagents。** 本地 Python runtime 不会伪造 App-native runtime；真实大规模 evidence 由本机 `codex exec` process swarm 提供。

Dynamic Workflow v2.2 可直接运行：

```bash
python -m dynamic_workflow "review and improve this repo" \
  --max-rounds 3 \
  --max-agents 50 \
  --max-parallel 5 \
  --planner-timeout-s 120 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --stream-events \
  --checkpoint-dir .orchestry/checkpoints

# 记录 adaptive planner/replanner compact evidence，可选 dashboard
python scripts/record_adaptive_workflow_evidence.py \
  --goal "review and improve this repo with adaptive planner/replanner agents" \
  --required-coverage security,tests,docs,observability \
  --max-agents 50 \
  --max-parallel 5 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --dashboard

# 控制型 replanner proof：故意留下 required coverage 缺口，让 replanner 追加 follow-up agents
python scripts/record_adaptive_workflow_evidence.py \
  --goal "Prove real planner plus replanner follow-up generation for this repo." \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"' \
  --codex-extra-arg=-c --codex-extra-arg='model_reasoning_effort="low"' \
  --dashboard

# 从 checkpoint 续跑
python -m dynamic_workflow --resume RUN_ID

# 真实 5-agent repo review demo，输出 compact evidence 到 docs/evidence/
python examples/real_repo_review.py --agents 5 --max-parallel 3

# 渲染静态 observability dashboard
python scripts/render_workflow_observability.py \
  --run-id RUN_ID \
  --source .orchestry \
  --output docs/evidence/RUN_ID-dashboard.html

# deterministic agent-quality eval，不需要 API key
python scripts/run_quality_eval.py --sample --output docs/evidence/sample_quality_eval.md
```

Runtime 边界：`dynamic_workflow.py` 是编排层，负责 planner/replanner 轮次、checkpoint/resume、streaming events 和 reducer；`codex_cli_swarm.py` 是执行层，负责 worker 生命周期、`codex exec` 子进程、worktree patch artifacts、stdout/stderr/trace。新增调度策略应优先进入编排层，新增 worker 启动/回收能力应优先进入执行层。

Codex CLI swarm 可直接运行：

```bash
oh-my-dynamic-codex-swarm --agents 50 --max-parallel 10 "并行审查这个仓库的安全、架构、测试和文档"

# 未安装 console script 时也可：
python -m codex_cli_swarm --agents 50 --max-parallel 10 "并行审查这个仓库"

# 给整个 swarm 设置总时间上限；默认保留每个 worker 的 prompt/stdout/stderr/last_message 和 trace
python -m codex_cli_swarm --agents 20 --max-parallel 5 --total-timeout-s 3600 "并行审查这个仓库"

# 显式丢弃 per-agent workdirs 时，仍会在 workspace root 留下 compact manifest/trace
python -m codex_cli_swarm --agents 20 --max-parallel 5 --discard-workdirs "并行审查这个仓库"

# 端到端 repo review demo
python examples/codex_cli_swarm_review.py --agents 8 --max-parallel 4

# 显式开启并发写代码隔离：每个 worker 进入独立 git worktree，只产出 patch/diff artifacts，不自动 merge
python -m codex_cli_swarm --agents 8 --max-parallel 4 \
  --workspace-mode worktree \
  --write-intent patch \
  "并发实现这些小修复，输出每个 agent 的 patch artifact"

# 手动记录 20/50/100 agent compact evidence；raw trace 留在 .orchestry/，不提交
python scripts/record_swarm_evidence.py --agents 20 --max-parallel 5 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"'
python scripts/record_swarm_evidence.py --agents 50 --max-parallel 10 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"'
python scripts/record_swarm_evidence.py --agents 100 --max-parallel 20 \
  --codex-extra-arg=-c --codex-extra-arg='service_tier="fast"'
```

### 3. 可选：安装本地 Python engine 依赖

```bash
# 推荐：可编辑安装
pip install -e .

# 或按 provider 安装可选 SDK
pip install -e ".[zhipu]"      # 智谱 GLM SDK
pip install -e ".[anthropic]"  # Claude
pip install -e ".[google]"     # Gemini
pip install -e ".[all]"        # 全部可选 SDK
```

### 4. 可选：配置外部 LLM API Key

复制示例配置文件：

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

或直接设置环境变量：

```bash
# 智谱 GLM（默认）
export ZHIPUAI_API_KEY=your_zhipu_key

# OpenAI GPT
export OPENAI_API_KEY=your_openai_key

# Anthropic Claude
export ANTHROPIC_API_KEY=your_anthropic_key

# Google Gemini
export GOOGLE_API_KEY=your_google_key

# OpenRouter（聚合多模型）
export OPENROUTER_API_KEY=your_openrouter_key

# DeepSeek（中国模型，OpenAI 兼容）
export DEEPSEEK_API_KEY=your_deepseek_key

# 通义千问 / Qwen / DashScope
export DASHSCOPE_API_KEY=your_dashscope_key

# Moonshot / Kimi
export MOONSHOT_API_KEY=your_moonshot_key

# 硅基流动
export SILICONFLOW_API_KEY=your_siliconflow_key

# 通用回退 key（任何未匹配的 provider 都会尝试这个）
export LLM_API_KEY=your_fallback_key
```

### 5. 可选：选择默认外部模型

```bash
# 方式一：环境变量
export LLM_DEFAULT_MODEL=gpt-4o

# 方式二：代码中指定
engine = Orchestrator(model="claude-sonnet-4-20250514")
```

### 6. 运行测试

```bash
# 全部测试（不需要 API Key）
python test_suite.py

# API 连通性测试
python validator.py api

# 端到端测试
python validator.py e2e easy glm-5.1 --auto
```

### 7. 可选：在代码中使用本地 Python engine

```python
from orchestrator import Orchestrator

# 使用默认模型
engine = Orchestrator()
result = engine.run(
    goal="设计一个学生成绩分析系统",
    context="50名学生，5个学科，3次考试数据",
)

# 指定模型
engine = Orchestrator(model="gpt-4o")
result = engine.run(goal="...", context="...")

print(result["final_output"])
print(f"完成率: {result['completed']}/{result['total']}")
```

### 8. 运行 demo（无需 API Key）

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/protocol_preview.py
python examples/sandboxed_fanout.py
```

Demo 使用 deterministic mock LLM，适合快速验证端到端编排链路：

- `research_analysis.py`：研究分析场景
- `code_review.py`：代码审查场景
- `data_processing.py`：数据处理场景
- `protocol_preview.py`：MCP-style tool 和 A2A-style Agent Card / Task 预览
- `sandboxed_fanout.py`：64 个 isolated workers 的 fan-out/reduce demo

## 支持的模型

模型名会按前缀/命名规则匹配 provider；具体可用模型会随厂商更新，请以各 provider 官方模型文档为准。下表是路由示例，不承诺这些模型永远可用：

| Provider | 模型示例 | 环境变量 |
|----------|---------|----------|
| 智谱 GLM | `glm-5.1`, `glm-4-flash`, `glm-4-plus` | `ZHIPUAI_API_KEY` |
| OpenAI | `gpt-*`, `o*` 系列模型名，例如 `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-*` 官方模型 ID，例如 `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| Google | `gemini-*` 官方模型 ID，例如 `gemini-2.5-pro`, `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| OpenRouter | `openrouter/<provider>/<model>`，例如 `openrouter/anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| DeepSeek | `deepseek-chat`, `deepseek-reasoner` | `DEEPSEEK_API_KEY` |
| 通义千问 / Qwen | `qwen-plus`, `qwen-max`, `dashscope/qwen-turbo` | `DASHSCOPE_API_KEY` |
| Moonshot / Kimi | `moonshot-v1-8k`, `kimi-k2` | `MOONSHOT_API_KEY` |
| 硅基流动 | `siliconflow/deepseek-ai/DeepSeek-V3` | `SILICONFLOW_API_KEY` |
| OpenAI 兼容自定义网关 | 任意模型名 | `OPENAI_API_KEY` + `LLM_BASE_URL` |

### 使用 OpenAI 兼容接口（DeepSeek、通义千问等）

```bash
export DEEPSEEK_API_KEY=your_deepseek_key
```

然后在代码中用 `model="deepseek-chat"` 即可。

也可以显式写 provider 前缀：

```python
engine = Orchestrator(model="qwen/qwen-plus")
engine = Orchestrator(model="moonshot/moonshot-v1-32k")
engine = Orchestrator(model="siliconflow/deepseek-ai/DeepSeek-V3")
```

### 与 Claude Code Dynamic Workflows 的差距和目标

oh-my-Dynamic 的默认定位是：在 Codex App 里，如果 subagent tools/runtime 可用，就走 **Codex App internal subagent backend**，用真实 Codex subagents 执行 dynamic workflows；这些 subagents 继承当前 Codex App 内部 LLM，不要求外部 API key。若该 backend 不可用，插件仍可提供零配置 dynamic-workflow-style 编排，本地 Python engine 也可运行 DAG、多 worker、replan 和 synthesis 原型。

需要精确区分三层能力：

1. **Codex App internal subagent backend**：真实 App-native subagents、内部 LLM 继承、API key free，由 Codex runtime 管理。
2. **插件级编排**：skill/plugin 在当前会话中组织拆解、worker lane、review 和 synthesis，不等同于 isolated runtime subagents。
3. **Codex CLI swarm backend**：`codex_cli_swarm.py` 可批量启动真实 `codex exec` worker，适合用户明确要求几十/几百 Codex agents 的场景；它是外部进程 swarm，不是 App 原生 runtime。
4. **本地 Python runtime 原型**：可测试 sandboxed fan-out、tool grants 和 reducer 形状，但本地 Python 进程不能直接调用 Codex App 内部 LLM；真实 App-native isolated sandboxes、tool permissions、scheduler 仍属于 Codex runtime。

我们希望推动 Codex 官方支持这些能力：

| 目标能力 | 当前 Codex App 状态 | oh-my-Dynamic 当前做法 | 期望官方 runtime |
|----------|---------------------|------------------------|------------------|
| App 原生 fan-out | subagent tools/runtime 可用时应默认使用；能力由 Codex runtime 提供 | 插件选择 App backend；否则用 `native_runtime.py` 本地 fan-out 原型 | `spawn_subagents()` 原生调度 |
| 几十到上百个 isolated subagents | App backend 可用时由 Codex runtime 管理 | `codex_cli_swarm.py` 可批量启动真实 `codex exec` workers；`SandboxedFanoutRuntime` 可跑 100+ mock/外部模型 workers 原型 | 每个 subagent 独立上下文窗口 |
| 每个 agent 独立工具权限和沙箱 | App-native 权限/沙箱由 Codex runtime 提供 | `AgentSandbox` + `ToolGrant` + worktree / subprocess 原型 | per-agent sandbox + least privilege tools |
| 原生 DAG 调度与汇总 | App-native scheduler/trace 由 Codex runtime 提供 | `dag.py` + `native_runtime.py` + `synthesis.py` | runtime 级 DAG execution graph |
| Agent 间受控沟通 | App subagents 通过父 orchestrator 协调；直接 P2P 取决于 runtime | `codex_app_bridge.py` + `agent_broker.py` 提供 envelope ingestion、message、artifact、handoff、review、A2A snapshot | runtime 原生 A2A broker + audit policy |
| 进度、预算、审计日志 | 部分依赖会话文本 | `token_tracker.py` + `agent_broker.py` trace + dashboard | App 原生可视化 trace |

详细提案见 [Codex Native Dynamic Workflows Proposal](docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md)。

### MCP / A2A 协议适配

`protocol_adapters.py` 提供 transport-agnostic 的生态适配层，`agent_broker.py` 提供可运行的本地协作 broker，`broker_gateway.py` 把 broker 暴露成 HTTP/SSE 入口：

- MCP-style：`mcp_tools()` 暴露 `oh_my_dynamic.run_workflow` 工具描述；`run_mcp_tool()` 可执行 workflow 并返回 text + structured content。
- A2A-style：`a2a_agent_card()` 返回 Agent Card；`A2ATaskStore` 提供轻量 Task submit/get 结构，可用于后续 HTTP、SSE 或网关封装。
- AgentBroker：`AgentBroker` 可注册 agents，发送 direct/broadcast message，发布 artifacts，创建 task handoff，发起 review request/response，并导出 A2A-style task snapshot。
- BrokerPolicy：默认要求 agent 注册，校验 sender/receiver、artifact 引用、消息/工件大小和 content type，避免无约束上下文串流。
- Gateway auth：启用 `--auth-token` 后，非系统 agent 通过 `/agents` 注册会获得 `agent_token`；之后以该 agent 身份执行 task actions 或读取 inbox 时需要同时发送 `X-Agent-Id` 和 `X-Agent-Token`，避免共享 gateway token 被用来冒充任意 worker。未设置 token 时只允许 loopback 绑定，CLI 会打印 WARNING；不要把无 token gateway 暴露到 localhost 之外。共享或远程访问必须设置 `--auth-token` 或 `OH_MY_DYNAMIC_GATEWAY_TOKEN`。
- Codex App bridge：`codex_app_bridge.py` 生成 App-native subagent dispatch plan 和 prompt，要求真实 Codex subagents 返回 JSON envelope，再把 envelope ingest 到 `AgentBroker`。下游 prompt 可注入 dependency outputs；envelope 会先预校验 artifact refs、target agents、大小和 content type，再写入 broker，避免半成功状态。parent orchestrator 可调用 `complete_dispatch_plan()` 写入 canonical `workflow_completed/workflow_failed`，让 A2A-style task snapshot 进入 terminal state。
- Codex CLI swarm：`CodexCliSwarmRuntime` 生成每个 worker 的 prompt，经 stdin 调用 `codex exec --output-last-message`，把 stdout/stderr 流式写入文件，解析 JSON envelope，并把 artifacts/messages/review trace ingest 到同一个 `AgentBroker`。每次 run 会写 `manifest.json` 和 `trace.json` 方便复盘。
- Native runtime 集成：`SandboxedFanoutRuntime(..., broker=AgentBroker(...))` 会把 worker started/completed、worker artifacts、final answer 和 workflow completion 写入 broker trace。
- Gateway：`python broker_gateway.py --host 127.0.0.1 --port 8765` 会提供 `/.well-known/agent.json`、`GET/POST /agents`、`GET /agents/{id}/inbox`、`POST /tasks`、`GET /tasks/{id}`、`GET /tasks/{id}/events`、`POST /tasks/{id}/messages`、`/artifacts`、`/handoffs`、`/review-requests`、`/review-responses` 和 `/complete`。

当前实现已包含本地 HTTP/SSE gateway，但还不是托管服务或官方 App-native runtime。这样可以先稳定核心协作语义，再按部署目标接入 MCP stdio、远程 HTTP、SSE 或托管网关。

## 验证体系

三层验证，从简到难：

```bash
python3 test_suite.py
python3 -m coverage run test_suite.py
python3 -m coverage report --fail-under=70
python3 scripts/run_quality_eval.py --sample --output /tmp/ohmy-quality-eval.md
```

### Layer 1: 单元测试
- 状态机转换是否合法
- 依赖阻塞逻辑是否正确
- DAG 拓扑排序和环检测

### Layer 2: 集成测试
- 组件间协作是否正常
- Pipeline 全流程（Mock）

### Layer 3: 端到端测试
- 完整编排流程 + 真实 API 调用

发布和真实 Codex CLI swarm 验证：

- [Release Checklist](docs/RELEASE_CHECKLIST.md)
- [Codex CLI Swarm Smoke Tests](docs/CODEX_CLI_SWARM_SMOKE.md)
- [Changelog](CHANGELOG.md)

## 贡献

欢迎 PR！请确保：

1. 新增功能附带测试
2. 运行 `python test_suite.py` 全部通过
3. 不提交 API Key 等敏感信息

## License

MIT

## References

- [Claude Code Dynamic Workflows](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code)
- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)
- [VMAO paper: arXiv 2603.11445](https://arxiv.org/abs/2603.11445)
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification/2025-06-18)
- [Agent2Agent Protocol specification](https://a2a-protocol.org/latest/specification/)
