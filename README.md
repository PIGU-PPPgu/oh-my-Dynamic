# oh-my-Dynamic 🔄

**多 Agent 编排引擎** —— 复刻 Anthropic Dynamic Workflows + VMAO 论文架构（arXiv 2603.11445），支持所有主流大模型。

> 串行编排 + 并行团队 + DAG 任务图 + 动态重规划 + TEA 工具进化 + 消息总线 = 一个完整的多 Agent 协作框架

## ✨ 特性

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

## 快速开始

### 1. 安装依赖

```bash
# 推荐：可编辑安装
pip install -e .

# 或按 provider 安装可选 SDK
pip install -e ".[zhipu]"      # 智谱 GLM SDK
pip install -e ".[anthropic]"  # Claude
pip install -e ".[google]"     # Gemini
pip install -e ".[all]"        # 全部可选 SDK
```

### 2. 配置 API Key

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

### 3. 选择默认模型

```bash
# 方式一：环境变量
export LLM_DEFAULT_MODEL=gpt-4o

# 方式二：代码中指定
engine = Orchestrator(model="claude-sonnet-4-20250514")
```

### 4. 运行测试

```bash
# 全部测试（不需要 API Key）
python test_suite.py

# API 连通性测试
python validator.py api

# 端到端测试
python validator.py e2e easy glm-5.1 --auto
```

### 5. 在代码中使用

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

### 6. 运行 demo（无需 API Key）

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
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `o3-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-20250514`, `claude-haiku-4-20250414` | `ANTHROPIC_API_KEY` |
| Google | `gemini-2.5-pro`, `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
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

### 与 Claude Code Dynamic Workflows 的对应关系

oh-my-Dynamic 对齐的是 Claude Code Dynamic Workflows 的核心形态：把复杂目标拆成可并行的子任务，用编排器调度多 agent 执行，并在验证/停机条件后进行动态重规划和汇总。

| Claude Code Dynamic Workflows 能力 | oh-my-Dynamic 对应模块 |
|-----------------------------------|-------------------------|
| 动态生成/运行编排流程 | `pipeline.py` + `dynamic_replan.py` |
| fan-out 到多个 subagent | `dag.py` + `team_engine.py` |
| 子任务依赖和并行执行 | `DAGExecutor` |
| 验证后继续/停止 | `stop_conditions.py` + reviewer |
| 汇总多 agent 结果 | `synthesis.py` |
| 可复用 workflow/plugin 入口 | `codex-plugin/skills/*` |

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
