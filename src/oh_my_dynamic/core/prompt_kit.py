"""
Anthropic Cookbook 8 条 Prompt 工程原则 —— 落地模板。

来源：Anthropic 工程博客 "How we built our multi-agent research system"
https://www.anthropic.com/engineering/multi-agent-research-system

8 条原则：
  1. Orchestrator 掌握全局
  2. Worker 指令聚焦明确
  3. 结构化交接
  4. LLM-as-Judge 验证
  5. 复杂查询拆解
  6. 分层汇总
  7. 动态重规划
  8. Token 预算感知

所有 prompt 模板用中文，适配 GLM-5.1。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptPrinciple:
    """一条 prompt 工程原则"""
    name: str
    description: str
    template: str


class AnthropicPromptKit:
    """
    Anthropic Cookbook 8 条原则，落地为可复用的 prompt 模板。

    用法：
        kit = AnthropicPromptKit()

        # 原则 1：Orchestrator 系统提示
        system = kit.orchestrator_system(
            goal="设计一个数据治理方案",
            subagent_count=3
        )

        # 原则 2：Worker 系统提示
        system = kit.worker_system(
            role="数据采集员",
            context="负责收集和清洗原始数据",
            constraints=["只处理 CSV/Excel 格式", "必须去重"]
        )
    """

    # ─── 原则 1：Orchestrator 掌握全局 ───

    def orchestrator_system(self, goal: str, subagent_count: int = 3) -> str:
        """
        Orchestrator 的系统提示。

        原则：Orchestrator 看到全貌，负责拆解、分配、汇总。
        它不做具体工作，只做协调。
        """
        return f"""你是一个多智能体协调器（Orchestrator）。

【你的职责】
你管理 {subagent_count} 个工作智能体（Worker），协调它们完成以下目标：
「{goal}」

【工作流程】
1. 将目标拆解为 {subagent_count} 个独立、可并行的子任务
2. 为每个子任务指定 Worker 角色和约束
3. 收集所有 Worker 的结果
4. 汇总成连贯的最终答案

【拆解原则】
- 每个子任务必须独立可执行，不依赖其他子任务的输出
- 子任务描述要具体，不能模糊
- 按难度分配：难的任务给经验丰富的角色
- 如果任务有自然依赖关系，标明执行顺序

【输出格式】
严格按以下 JSON 格式输出：
```json
{{
  "subtasks": [
    {{
      "id": "task_1",
      "question": "具体的任务描述",
      "agent_type": "builder|explorer|reviewer",
      "priority": 1-10,
      "dependencies": [],
      "verification_criteria": "完成的判断标准"
    }}
  ]
}}
```

【约束】
- 不许自己执行任务，只负责拆解和协调
- 每个子任务描述不超过 200 字
- 优先级 1-10，10 最紧急"""

    # ─── 原则 2：Worker 指令聚焦明确 ───

    def worker_system(
        self,
        role: str,
        context: str,
        constraints: Optional[list[str]] = None
    ) -> str:
        """
        Worker 的系统提示。

        原则：每个 Worker 只看自己的任务，指令明确，边界清晰。
        不要给 Worker 全局上下文，只给它完成自己任务所需的信息。
        """
        constraints_text = ""
        if constraints:
            items = "\n".join(f"  - {c}" for c in constraints)
            constraints_text = f"""
【约束条件】
{items}"""

        return f"""你是一个专业的工作智能体。

【你的角色】{role}

【职责范围】{context}
{constraints_text}

【工作原则】
1. 专注完成分配给你的任务，不要越界
2. 输出要结构化、可直接使用
3. 如果任务描述有歧义，按最合理的理解执行
4. 标注你不确定的部分

【输出格式】
按以下结构输出：
## 结果
（你的核心输出）

## 方法说明
（简述你用了什么方法）

## 不确定性
（如有不确定的部分，在此说明）"""

    # ─── 原则 3：结构化交接 ───

    def handoff_prompt(
        self,
        from_role: str,
        to_role: str,
        artifact: str
    ) -> str:
        """
        Agent 间交接提示。

        原则：交接要结构化——做了什么、结果是什么、下一步注意什么。
        避免信息在传递中丢失。
        """
        return f"""【交接文档】

来源：{from_role}
接收：{to_role}

【已完成的工作】
{artifact}

【交接要点】
请基于以上工作成果，继续完成你的任务。注意：
1. 先阅读并理解已完成的工作
2. 如果发现问题，在输出中标注
3. 你的输出将成为下一环节的输入，请保持结构化

【输出格式】
```json
{{
  "understood": true,
  "issues_found": ["如有问题列出，没有则为空列表"],
  "my_output": "你的工作成果",
  "confidence": 0.0-1.0
}}
```"""

    # ─── 原则 4：LLM-as-Judge 验证 ───

    def verification_prompt(
        self,
        task_desc: str,
        result: str,
        criteria: Optional[list[str]] = None
    ) -> str:
        """
        验证提示 —— 让 LLM 评判另一个 LLM 的输出。

        原则：用 LLM 验证 LLM，关注正确性、完整性、相关性。
        """
        criteria_text = ""
        if criteria:
            items = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))
            criteria_text = f"""
【验证标准】
{items}"""

        return f"""你是一个质量审核员。

【原始任务】{task_desc}

【待审核的结果】
{result}
{criteria_text}

【审核维度】
1. 正确性：结果是否准确无误？
2. 完整性：是否完整回答了任务要求？
3. 相关性：是否紧扣任务，没有偏题？
4. 可操作性：结果是否可以直接使用？

【输出格式】
```json
{{
  "verdict": "PASS|MINOR_ISSUES|MAJOR_ISSUES|REJECT",
  "scores": {{
    "correctness": 0.0-1.0,
    "completeness": 0.0-1.0,
    "relevance": 0.0-1.0,
    "actionability": 0.0-1.0
  }},
  "issues": ["具体问题列表"],
  "improvement_suggestions": ["改进建议"]
}}
```"""

    # ─── 原则 5：复杂查询拆解 ───

    def decomposition_prompt(self, query: str, max_subtasks: int = 5) -> str:
        """
        查询拆解提示。

        原则：把复杂问题拆成独立的子问题，最大化并行性。
        子问题之间尽量不要有依赖关系。
        """
        return f"""将以下复杂查询拆解为 {max_subtasks} 个独立的子任务。

【原始查询】
{query}

【拆解原则】
1. 每个子任务必须能独立完成
2. 子任务之间尽量无依赖（可以并行执行）
3. 如果确实存在依赖，明确标注
4. 每个子任务有明确的完成标准
5. 子任务数量不超过 {max_subtasks} 个

【输出格式】
```json
{{
  "subtasks": [
    {{
      "id": "st_1",
      "question": "具体的子任务描述（是一个可回答的问题）",
      "agent_type": "builder|explorer|reviewer",
      "priority": 1-10,
      "dependencies": [],
      "verification_criteria": "如何判断这个子任务完成了"
    }}
  ],
  "strategy": "简述整体策略和任务间的关系"
}}
```"""

    # ─── 原则 6：分层汇总 ───

    def synthesis_prompt(
        self,
        partial_results: list[str],
        original_query: str
    ) -> str:
        """
        分层汇总提示。

        原则：先按组压缩，再整合。避免一次汇总太多信息。
        """
        results_text = "\n\n---\n\n".join(
            f"【来源 {i+1}】\n{r}"
            for i, r in enumerate(partial_results)
        )

        return f"""将以下多个部分结果整合为一个连贯的最终答案。

【原始问题】
{original_query}

【部分结果】
{results_text}

【整合原则】
1. 去重：合并重复信息
2. 互补：保留各来源的独特贡献
3. 排序：按逻辑顺序组织（问题→方法→发现→结论）
4. 标注来源：每个要点标注来自哪个部分结果
5. 一致性：确保各部分之间不矛盾

【输出格式】
## 综合回答

（结构化的最终答案，包含所有关键发现）

## 关键发现

1. （发现1）[来源: 部分N]
2. （发现2）[来源: 部分N]

## 局限性

（未覆盖的部分或不确定性）"""

    # ─── 原则 7：动态重规划 ───

    def replan_prompt(self, completed: list[str], gaps: str) -> str:
        """
        动态重规划提示。

        原则：基于已有结果，决定哪些保留、哪些新增、哪些修改。
        核心是结果保留——已完成的成果不丢弃。
        """
        completed_text = "\n".join(
            f"  {i+1}. {c[:200]}"
            for i, c in enumerate(completed)
        )

        return f"""基于当前进展，进行动态重规划。

【已完成的任务】
{completed_text}

【当前差距分析】
{gaps}

【重规划原则】
1. 已完成的结果必须保留（不要重复已完成的工作）
2. 只新增真正缺失的任务
3. 如果某个已完成任务的结果不充分，可以创建补充任务
4. 新任务的依赖应该指向已有的已完成任务

【输出格式】
```json
{{
  "keep_ids": ["保留的节点ID列表"],
  "drop_ids": ["丢弃的节点ID列表"],
  "new_tasks": [
    {{
      "question": "新任务描述",
      "agent_type": "builder|explorer|reviewer",
      "dependencies": ["依赖的节点ID"],
      "priority": 1-10
    }}
  ],
  "modified_tasks": [
    {{
      "id": "要修改的节点ID",
      "new_question": "更新后的任务描述",
      "reason": "为什么要修改"
    }}
  ]
}}
```"""

    # ─── 原则 8：Token 预算感知 ───

    def token_budget_alert(
        self,
        used: int,
        budget: int,
        remaining_tasks: int
    ) -> str:
        """
        Token 预算感知提示。

        原则：让模型知道成本约束，促使它更高效地使用 token。
        Anthropic 发现 token 预算解释了 80% 的性能差异。
        """
        percent = used / max(budget, 1) * 100
        remaining = budget - used

        return f"""⚠️ Token 预算提醒

【当前状况】
- 已使用：{used:,} tokens ({percent:.0f}%)
- 总预算：{budget:,} tokens
- 剩余：{remaining:,} tokens
- 待完成任务：{remaining_tasks} 个
- 平均每任务可用：{remaining // max(remaining_tasks, 1):,} tokens

【优化策略】
1. 优先完成高价值任务
2. 输出尽量精简，避免冗余描述
3. 如果剩余预算不足以完成所有任务，聚焦最有价值的部分
4. 考虑是否可以合并相似任务"""

    # ─── 便捷方法 ───

    def build_system_prompt(self, role: str, goal: str, **kwargs) -> str:
        """
        根据 role 自动选择合适的 prompt 模板。

        Args:
            role: orchestrator / worker / reviewer / synthesizer
            goal: 任务目标
            **kwargs: 传给对应方法的额外参数
        """
        if role == "orchestrator":
            return self.orchestrator_system(goal, **kwargs)
        elif role == "worker":
            return self.worker_system(
                role=kwargs.get("role_name", "Worker"),
                context=goal,
                constraints=kwargs.get("constraints")
            )
        elif role == "reviewer":
            return self.verification_prompt(
                task_desc=goal,
                result=kwargs.get("result", ""),
                criteria=kwargs.get("criteria")
            )
        elif role == "synthesizer":
            return self.synthesis_prompt(
                partial_results=kwargs.get("results", []),
                original_query=goal
            )
        else:
            return self.worker_system(role=role, context=goal)


# ─── 全局便捷实例 ───
kit = AnthropicPromptKit()


def build_system_prompt(role: str, goal: str, **kwargs) -> str:
    """便捷函数：根据角色构建系统提示"""
    return kit.build_system_prompt(role, goal, **kwargs)
