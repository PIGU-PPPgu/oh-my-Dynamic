# oh-my-Dynamic 🔄

**多 Agent 编排引擎 / Codex Native Dynamic Workflows 提案原型** —— 对齐 Anthropic Dynamic Workflows + VMAO 论文架构（arXiv 2603.11445），支持所有主流大模型。

> 当前：Codex App 零配置 workflow-style 编排 + 可选本地 Python engine。  
> 目标：推动 Codex runtime 原生支持 sandboxed fan-out、几十到上百个 isolated subagents、独立上下文/工具权限/沙箱、原生调度与汇总。

## ✨ 特性

- 🎯 **明确目标**：不是只做 prompt 技巧，而是为 Codex Native Dynamic Workflows 提供可验证原型和接口提案
- 🤖 **多模型支持**：GLM、OpenAI GPT、Claude、Gemini、DeepSeek、通义千问/Qwen、Moonshot/Kimi、硅基流动…… 自动识别模型名选择对应 provider
- 🔗 **串行编排**（Orchestrator）：Planner → Builder → Reviewer 流水线，含自动重试和 review 打回
- 👥 **并行团队**（TeamEngine）：多 agent 并行抢任务，消息总线通信
- 🕸️ **DAG 任务图**：依赖感知的并行执行，自动拓扑排序
- 🔄 **动态重规划**（Dynamic Replan）：运行中根据中间结果调整计划
- 🧬 **TEA 工具进化**：LLM 驱动的工具自动分析、改进和回滚
- 📊 **可视化**：自动生成 DAG 的 DOT/SVG 图
- 🛡️ **安全**：TEA 工具 AST 校验 + 子进程隔离、线程安全消息总线、循环超时保护

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
| `llm_client.py` | **通用 LLM 客户端**（自动识别模型选择 provider） |
| `orchestrator.py` | 串行编排引擎（核心调度器） |
| `team_engine.py` | 并行团队引擎（多 agent 协作） |
| `dag.py` | DAG 任务图 + 并行执行器 |
| `dynamic_replan.py` | 动态重规划（运行中调整策略） |
| `tea_protocol.py` | TEA 工具进化协议（LLM 驱动的工具改进） |
| `message_bus.py` | Agent 间消息总线（文件系统队列，线程安全） |
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

### 1. Codex App 零配置使用

安装插件后，重启 Codex App 或新开一个 thread，直接输入：

```text
$oh-my-dynamic 用多 agent 分析：学校是否应该引入 AI 作业助手？
```

或：

```text
$multi-agent-run review a Python change for security, correctness, and missing tests
```

默认模式会使用 **Codex App 当前会话的内部 LLM** 执行拆解、worker 分析、review、replan 和 synthesis，不需要配置 `.env`，也不需要 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 或其他外部模型 key。

只有当你明确要运行本地 Python engine、接外部模型、生成 dashboard 文件时，才需要下面的可选配置。

### 2. 可选：安装本地 Python engine 依赖

```bash
# 推荐：可编辑安装
pip install -e .

# 或按 provider 安装可选 SDK
pip install -e ".[zhipu]"      # 智谱 GLM SDK
pip install -e ".[anthropic]"  # Claude
pip install -e ".[google]"     # Gemini
pip install -e ".[all]"        # 全部可选 SDK
```

### 3. 可选：配置外部 LLM API Key

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

### 4. 可选：选择默认外部模型

```bash
# 方式一：环境变量
export LLM_DEFAULT_MODEL=gpt-5.2

# 方式二：代码中指定
engine = Orchestrator(model="claude-sonnet-4-6")
```

### 5. 运行测试

```bash
# 全部测试（不需要 API Key）
python test_suite.py

# API 连通性测试
python validator.py api

# 端到端测试
python validator.py e2e easy glm-5.1 --auto
```

### 6. 可选：在代码中使用本地 Python engine

```python
from orchestrator import Orchestrator

# 使用默认模型
engine = Orchestrator()
result = engine.run(
    goal="设计一个学生成绩分析系统",
    context="50名学生，5个学科，3次考试数据",
)

# 指定模型
engine = Orchestrator(model="gpt-5.2")
result = engine.run(goal="...", context="...")

print(result["final_output"])
print(f"完成率: {result['completed']}/{result['total']}")
```

### 7. 运行 demo（无需 API Key）

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/protocol_preview.py
```

Demo 使用 deterministic mock LLM，适合快速验证端到端编排链路：

- `research_analysis.py`：研究分析场景
- `code_review.py`：代码审查场景
- `data_processing.py`：数据处理场景
- `protocol_preview.py`：MCP-style tool 和 A2A-style Agent Card / Task 预览

## 支持的模型

模型名会自动匹配 provider，无需额外配置：

| Provider | 模型示例 | 环境变量 |
|----------|---------|----------|
| 智谱 GLM | `glm-5.1`, `glm-4-flash`, `glm-4-plus` | `ZHIPUAI_API_KEY` |
| OpenAI | `gpt-5.2`, `gpt-5.2-pro`, `gpt-5-mini`, `gpt-5-nano` | `OPENAI_API_KEY` |
| Anthropic | `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5` | `ANTHROPIC_API_KEY` |
| Google | `gemini-3.5-flash`, `gemini-3.1-pro-preview`, `gemini-flash-latest` | `GOOGLE_API_KEY` |
| OpenRouter | `openrouter/openai/gpt-5.2`, `openrouter/anthropic/claude-sonnet-4.6`, `openrouter/google/gemini-3.5-flash` | `OPENROUTER_API_KEY` |
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

oh-my-Dynamic 当前可以在 Codex App 里提供零配置 dynamic-workflow-style 编排，也可以用本地 Python engine 运行 DAG、多 worker、replan 和 synthesis。但 Codex App 目前还没有公开的 native runtime 能力来真正复刻 Claude Code Dynamic Workflows 的核心特性。

我们希望推动 Codex 官方支持这些能力：

| 目标能力 | 当前 Codex App 状态 | oh-my-Dynamic 当前做法 | 期望官方 runtime |
|----------|---------------------|------------------------|------------------|
| App 原生 fan-out | 暂无公开插件 API | in-chat 拆解 + 本地 engine 可选 | `spawn_subagents()` 原生调度 |
| 几十到上百个 isolated subagents | 暂无公开能力 | Python `DAGExecutor` / `TeamEngine` | 每个 subagent 独立上下文窗口 |
| 每个 agent 独立工具权限和沙箱 | 暂无公开能力 | worktree / subprocess / TEA sandbox 原型 | per-agent sandbox + least privilege tools |
| 原生 DAG 调度与汇总 | 暂无公开能力 | `dag.py` + `synthesis.py` | runtime 级 DAG execution graph |
| 进度、预算、审计日志 | 部分依赖会话文本 | `token_tracker.py` + dashboard | App 原生可视化 trace |

详细提案见 [Codex Native Dynamic Workflows Proposal](docs/CODEX_NATIVE_DYNAMIC_WORKFLOWS.md)。

### MCP / A2A 协议适配

`protocol_adapters.py` 提供 transport-agnostic 的生态适配层：

- MCP-style：`mcp_tools()` 暴露 `oh_my_dynamic.run_workflow` 工具描述；`run_mcp_tool()` 可执行 workflow 并返回 text + structured content。
- A2A-style：`a2a_agent_card()` 返回 Agent Card；`A2ATaskStore` 提供轻量 Task submit/get 结构，可用于后续 HTTP、SSE 或网关封装。

当前实现是协议对象和调用契约，不内置常驻 HTTP/MCP server。这样可以先稳定核心 payload，再按部署目标接入 stdio、HTTP 或托管网关。

## 验证体系

三层验证，从简到难：

### Layer 1: 单元测试
- 状态机转换是否合法
- 依赖阻塞逻辑是否正确
- DAG 拓扑排序和环检测

### Layer 2: 集成测试
- 组件间协作是否正常
- Pipeline 全流程（Mock）

### Layer 3: 端到端测试
- 完整编排流程 + 真实 API 调用

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
