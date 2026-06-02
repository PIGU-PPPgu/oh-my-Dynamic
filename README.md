# 多 Agent 编排脚本

用 GLM-5.1 实现的多 Agent 编排系统。

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
| `task.py` | Task 状态机（todo→in_progress→review→done） |
| `agents.py` | 三种角色定义（planner/builder/reviewer） |
| `llm_client.py` | GLM-5.1 API 调用层（zhipuai SDK 或 OpenAI 兼容） |
| `orchestrator.py` | 编排引擎（核心调度器） |
| `validator.py` | 验证框架（单元/集成/端到端测试） |

## 快速开始

### 1. 安装依赖

```bash
pip install zhipuai
# 或
pip install openai
```

### 2. 设置 API Key

```bash
export ZHIPUAI_API_KEY=your_key_here
# 或使用 OpenAI 兼容接口
export OPENAI_API_KEY=your_key_here
export GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

### 3. 运行验证

```bash
# 单元测试（不需要 API Key）
python validator.py unit

# 测试 API 连通性
python validator.py api

# 端到端测试（简单场景，跳过 reviewer）
python validator.py e2e easy glm-5.1 --auto

# 端到端测试（中等难度，走完整流程含 review）
python validator.py e2e medium glm-5.1

# 自定义目标
python validator.py custom "帮我分析一下707班的成绩数据" glm-5.1
```

### 4. 在代码中使用

```python
from orchestrator import Orchestrator

engine = Orchestrator(model="glm-5.1")
result = engine.run(
    goal="设计一个学生成绩分析系统",
    context="50名学生，5个学科，3次考试数据",
)

print(result["final_output"])
print(f"完成率: {result['completed']}/{result['total']}")
```

## 验证体系

三层验证，从简到难：

### Layer 1: 单元测试
- 状态机转换是否合法
- 依赖阻塞逻辑是否正确
- Planner 输出解析器是否健壮

### Layer 2: 集成测试
- API 调用是否通畅
- 重试机制是否工作
- 超时处理是否正常

### Layer 3: 端到端测试
- 完整编排流程能否跑通
- 任务完成率
- 输出质量（人工+验证函数）

### 核心验证指标

| 指标 | 含义 | 目标 |
|------|------|------|
| 任务完成率 | completed / total | ≥ 80% |
| 一次通过率 | 首次 review 通过数 / total | ≥ 50% |
| 状态机正确性 | 无非法转换 | 100% |
| 依赖正确性 | B 总在 A 完成后执行 | 100% |
| 输出质量 | 最终结果符合预期 | 人工判断 |

## GLM-5.1 适配策略

GLM-5.1 的已知问题及应对：

| 问题 | 应对策略 |
|------|---------|
| tool_call 不稳定 | 编排逻辑全写在 Python 里，模型只做文本生成 |
| 偶尔不听 system prompt | 在 user prompt 里重复关键指令 |
| 说"我来做"但不做 | prompt 里写"直接输出结果" |
| 超时/429 | 内置指数退避重试 |
| 输出格式不规范 | 解析器容忍多种格式（中英文混合） |

## 移植到 Codex App

这套编排逻辑可以直接转写为 Codex Skill：

1. `agents.py` 里的 prompt 模板 → 写进 SKILL.md
2. `task.py` 的状态机 → Codex 的 subagent 管理器
3. `orchestrator.py` 的调度逻辑 → Skill 的工作流描述
4. `validator.py` 的验证框架 → Codex 的自动化测试
