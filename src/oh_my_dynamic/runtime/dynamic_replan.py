"""
Result-Preserving Dynamic Replanner —— 基于 VMAO 论文的结果保留重规划。

核心思想 (arXiv 2603.11445):
  当执行过程中发现计划需要调整时，不是全部推倒重来，而是：
    1. 保留已完成的、仍然有效的节点结果 (KEEP)
    2. 丢弃不再需要的节点 (DROP)
    3. 添加新的子任务节点 (NEW)
    4. 修改已有节点的任务描述 (MODIFY)
  这样已完成的有效工作不会被浪费，减少 token 消耗和重复计算。

与旧版 DynamicReplanner 的区别：
  - 旧版：基于扁平任务列表，replan 时可能丢弃已完成的结果
  - 新版：基于 DAG，明确区分 keep/drop/new/modify，已完成的节点结果始终保留
  - 旧版：直接调用 call_llm/call_glm
  - 新版：接受 llm_fn 回调，更灵活地集成不同的 LLM 后端
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from oh_my_dynamic.runtime.dag import DAG, DAGNode, normalize_status, status_value
from oh_my_dynamic.runtime.task import TaskStatus
from oh_my_dynamic.runtime.workflow_config import REPLAN_COMPLETENESS_THRESHOLD
from oh_my_dynamic.runtime.token_tracker import TokenTracker


# ---------------------------------------------------------------------------
# LLM callable signature
# ---------------------------------------------------------------------------
LLMFn = Callable[[str, str], str]
# llm_fn(system_prompt: str, user_prompt: str) -> str


# ---------------------------------------------------------------------------
# ReplanResult — 一次重规划的输出
# ---------------------------------------------------------------------------
@dataclass
class ReplanResult:
    """一次结果保留重规划的完整输出。

    Attributes:
        kept_node_ids: 结果被保留的节点 ID 列表（status='completed' 不变）。
        dropped_node_ids: 被标记为取消的节点 ID 列表。
        new_nodes: 新创建的 DAGNode 列表（已加入 DAG）。
        modified_nodes: 任务描述被更新的 DAGNode 列表。
        reason: 触发本次重规划的原因。
    """

    kept_node_ids: list[str] = field(default_factory=list)
    dropped_node_ids: list[str] = field(default_factory=list)
    new_nodes: list[DAGNode] = field(default_factory=list)
    modified_nodes: list[DAGNode] = field(default_factory=list)
    reason: str = ""

    @property
    def has_changes(self) -> bool:
        """本次重规划是否产生了任何变更。"""
        return bool(
            self.dropped_node_ids
            or self.new_nodes
            or self.modified_nodes
        )

    def summary(self) -> str:
        """人类可读的变更摘要。"""
        parts: list[str] = []
        if self.kept_node_ids:
            parts.append(f"保留 {len(self.kept_node_ids)} 个节点")
        if self.dropped_node_ids:
            parts.append(f"丢弃 {len(self.dropped_node_ids)} 个节点")
        if self.new_nodes:
            parts.append(f"新增 {len(self.new_nodes)} 个节点")
        if self.modified_nodes:
            parts.append(f"修改 {len(self.modified_nodes)} 个节点")
        return "；".join(parts) if parts else "无变更"


# ---------------------------------------------------------------------------
# System / User prompt templates (Chinese — optimized for GLM-5.1)
# ---------------------------------------------------------------------------
_GAP_ANALYSIS_SYSTEM = """\
你是一个高级项目分析专家。你的任务是对比"原始查询范围"与"已完成节点的结果"，\
找出尚未覆盖或有缺陷的部分。请用简洁的中文列出具体的差距。"""

_GAP_ANALYSIS_USER = """\
## 原始查询
{original_query}

## 已完成的节点及其结果
{completed_summary}

## 当前 DAG 整体状态
{dag_stats}

请分析：原始查询的哪些方面还没有被已完成的节点覆盖？哪些节点的结果有明显缺陷\
需要补充？请逐条列出差距。如果已完成的节点已经充分覆盖了原始查询，请回复"无差距"。"""

_REPLAN_SYSTEM = """\
你是一个动态任务规划专家。你的职责是根据差距分析结果，决定如何调整任务 DAG \
以补足差距。你必须严格输出合法 JSON。

## 决策类别
1. **keep_ids** — 结果仍然有效的已完成节点 ID 列表（保持 status='completed' 不变）。
2. **drop_ids** — 不再需要的节点 ID 列表（将被标记为 cancelled）。
3. **new_tasks** — 需要新增的子任务，每个包含：
   - "question": 具体可执行的任务描述（字符串）
   - "agent_type": 适合的 agent 类型，可选 "builder" / "explorer" / "reviewer"
   - "dependencies": 依赖的节点 ID 列表（可以引用 keep_ids 中的节点或新增任务的 question 简称）
   - "priority": 1-10 的优先级（整数，10 最高）
4. **modified_tasks** — 需要更新任务描述的已有节点，每个包含：
   - "id": 节点 ID
   - "new_question": 新的任务描述

## 输出格式
严格输出如下 JSON（不要包含任何其他文字、注释或 markdown 代码块标记）：
{
  "keep_ids": ["node_id_1", "node_id_2"],
  "drop_ids": ["node_id_3"],
  "new_tasks": [
    {
      "question": "新的任务描述",
      "agent_type": "builder",
      "dependencies": ["node_id_1"],
      "priority": 7
    }
  ],
  "modified_tasks": [
    {
      "id": "node_id_2",
      "new_question": "更新后的任务描述"
    }
  ]
}

如果某个类别为空，使用空列表。"""

_REPLAN_USER = """\
## 原始查询
{original_query}

## 当前 DAG 所有节点
{node_list}

## 已完成节点的结果摘要
{completed_results}

## 差距分析
{gap_analysis}

## 当前迭代次数
{iteration}

请根据以上信息输出调整方案的 JSON。记住：
- keep_ids 中的节点将保留其已有结果，不会被重新执行。
- drop_ids 中的节点将被取消。
- new_tasks 中的 dependencies 可以引用 keep_ids 中的节点。
- 尽量复用已有的有效结果，减少重复工作。"""


# ---------------------------------------------------------------------------
# ResultPreservingReplanner
# ---------------------------------------------------------------------------
class ResultPreservingReplanner:
    """基于 VMAO 论文的结果保留动态重规划器。

    在 DAGExecutor 每完成一批节点后，由外部调用：
      1. ``analyze_gaps`` — 分析当前结果与原始查询的差距
      2. ``replan`` — 根据差距生成结果保留的重规划方案
      3. 返回的 ``ReplanResult`` 描述了 keep / drop / new / modify 决策

    关键不变量：被标记为 *kept* 的节点，其 ``.result``、\
    ``.completeness_score``、``.status='completed'`` 全部保持不变。

    Args:
        llm_fn: 调用 LLM 的回调函数，签名为 ``(system_prompt, user_prompt) -> str``。
        token_tracker: 可选的 TokenTracker 实例，用于记录 token 消耗。
    """

    def __init__(
        self,
        llm_fn: LLMFn,
        token_tracker: Optional[TokenTracker] = None,
        verbose: bool = True,
    ) -> None:
        self._llm_fn = llm_fn
        self._tracker = token_tracker
        self._verbose = verbose
        self._replan_count: int = 0

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🔄 Replan: {msg}")

    # ------------------------------------------------------------------
    # LLM call wrapper (with optional token tracking)
    # ------------------------------------------------------------------
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 并（如果提供了 tracker）粗略记录 token 消耗。"""
        response = self._llm_fn(system_prompt, user_prompt)
        if self._tracker is not None:
            # 粗略估算：无法从回调获得精确值，按 1 token ≈ 1.5 字符估算
            est_prompt = int(len(system_prompt + user_prompt) / 1.5)
            est_completion = int(len(response) / 1.5)
            self._tracker.record(est_prompt, est_completion, "replanner")
        return response

    # ------------------------------------------------------------------
    # Public API — gap analysis
    # ------------------------------------------------------------------
    def analyze_gaps(self, dag: DAG, original_query: str) -> str:
        """分析已完成节点结果与原始查询之间的差距。

        Args:
            dag: 当前 DAG 实例。
            original_query: 用户的原始查询文本。

        Returns:
            差距分析文本（中文）。如果已完成的节点已经充分覆盖原始查询，
            返回 ``"无差距"``。
        """
        completed_nodes = [
            n for n in dag.nodes.values() if normalize_status(n.status) == TaskStatus.DONE
        ]

        if not completed_nodes:
            return "尚未有任何节点完成，需要执行全部计划。"

        # Build completed summary
        completed_parts: list[str] = []
        for node in completed_nodes:
            result_preview = node.result[:500] if node.result else "(无结果)"
            completed_parts.append(
                f"- [{node.id}] {node.question}\n  完备性: {node.completeness_score:.0%}\n"
                f"  结果摘要: {result_preview}"
            )
        completed_summary = "\n".join(completed_parts)

        stats = dag.completion_stats()
        dag_stats = (
            f"总节点: {stats['total']}, 已完成: {stats['completed']}, "
            f"失败: {stats['failed']}, 待执行: {stats['pending']}, "
            f"平均完备性: {stats['avg_score']:.0%}"
        )

        user_prompt = _GAP_ANALYSIS_USER.format(
            original_query=original_query,
            completed_summary=completed_summary,
            dag_stats=dag_stats,
        )

        try:
            response = self._call_llm(_GAP_ANALYSIS_SYSTEM, user_prompt)
            self._log(f"差距分析完成: {response[:100]}")
            return response.strip()
        except Exception as e:
            self._log(f"差距分析失败: {e}")
            return f"差距分析异常: {e}"

    # ------------------------------------------------------------------
    # Public API — result-preserving replan
    # ------------------------------------------------------------------
    def replan(
        self,
        dag: DAG,
        gap_analysis: str,
        iteration: int,
        original_query: str = "",
    ) -> ReplanResult:
        """执行一次结果保留重规划。

        Algorithm:
          a. 收集所有已完成节点的结果作为上下文
          b. 调用 LLM：给定已完成结果和差距分析，决定 keep / drop / new / modify
          c. 解析 LLM 返回的 JSON
          d. 将变更应用到 DAG：
             - dropped 节点标记为 ``status='cancelled'``
             - new 节点添加到 DAG（自动验证无环）
             - modified 节点更新 ``question`` 字段
          e. kept 节点的 ``.result``、``.completeness_score``、``.status`` 保持不变

        Args:
            dag: 当前 DAG 实例。
            gap_analysis: 由 ``analyze_gaps`` 产生的差距分析文本。
            iteration: 当前迭代编号（用于 prompt 和日志）。
            original_query: 用户的原始查询（用于提供上下文）。

        Returns:
            ``ReplanResult`` 实例，描述本次重规划的所有决策。
        """
        self._replan_count += 1
        self._log(f"第 {self._replan_count} 次重规划 (iteration={iteration})")

        # ---- (a) 收集已完成节点信息 ----
        node_list_parts: list[str] = []
        completed_results_parts: list[str] = []

        for node in dag.nodes.values():
            public_status = status_value(node.status)
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "running": "⏳",
                "pending": "⬜",
            }.get(public_status, "❓")
            node_list_parts.append(
                f"- [{node.id}] ({status_icon} {public_status}) "
                f"agent={node.agent_type}, priority={node.priority}\n"
                f"  任务: {node.question}\n"
                f"  依赖: {node.dependencies or '无'}"
            )
            if normalize_status(node.status) == TaskStatus.DONE and node.result:
                completed_results_parts.append(
                    f"- [{node.id}] {node.question}\n"
                    f"  结果: {node.result[:800]}"
                )

        node_list = "\n".join(node_list_parts)
        completed_results = (
            "\n".join(completed_results_parts)
            if completed_results_parts
            else "(暂无已完成节点)"
        )

        # ---- (b) 调用 LLM ----
        user_prompt = _REPLAN_USER.format(
            original_query=original_query or "(未提供)",
            node_list=node_list,
            completed_results=completed_results,
            gap_analysis=gap_analysis,
            iteration=iteration,
        )

        try:
            raw_response = self._call_llm(_REPLAN_SYSTEM, user_prompt)
        except Exception as e:
            self._log(f"LLM 调用失败: {e}")
            return ReplanResult(reason=f"LLM 调用失败: {e}")

        # ---- (c) 解析响应 ----
        parsed = self._parse_replan_response(raw_response)
        if parsed is None:
            self._log("无法解析 LLM 响应为有效 JSON")
            return ReplanResult(reason="无法解析 LLM 响应")

        # ---- (d) 应用变更到 DAG ----
        result = self._apply_replan(dag, parsed, gap_analysis)

        self._log(f"重规划完成: {result.summary()}")
        return result

    # ------------------------------------------------------------------
    # Parse LLM JSON response
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_replan_response(response: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON 重规划方案。

        尝试多种策略从 LLM 输出中提取有效 JSON：
          1. 直接 ``json.loads``
          2. 提取 ```json ... ``` 代码块
          3. 找到最外层 ``{ ... }`` 并尝试解析

        Args:
            response: LLM 原始输出文本。

        Returns:
            解析后的 dict，包含 keep_ids / drop_ids / new_tasks / modified_tasks。
            如果解析失败返回 ``None``。
        """
        text = response.strip()

        # Strategy 1: direct parse
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract ```json ... ``` code block
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL
        )
        if code_block_match:
            try:
                data = json.loads(code_block_match.group(1).strip())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Strategy 3: find outermost { ... }
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                data = json.loads(brace_match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        return None

    # ------------------------------------------------------------------
    # Apply parsed replan decisions to the DAG
    # ------------------------------------------------------------------
    def _apply_replan(
        self,
        dag: DAG,
        parsed: dict,
        reason: str,
    ) -> ReplanResult:
        """将解析后的 JSON 决策应用到 DAG。

        Args:
            dag: 目标 DAG 实例。
            parsed: 解析后的 JSON dict。
            reason: 触发重规划的原因。

        Returns:
            ``ReplanResult`` 实例。
        """
        kept_ids: list[str] = []
        dropped_ids: list[str] = []
        new_nodes: list[DAGNode] = []
        modified_nodes: list[DAGNode] = []

        existing_ids = set(dag.nodes.keys())

        # ---- Validate and apply drop_ids ----
        raw_drop_ids: list[str] = parsed.get("drop_ids", [])
        for nid in raw_drop_ids:
            if nid in existing_ids:
                node = dag.nodes[nid]
                # Only drop nodes that are not already completed with valuable results
                # unless explicitly requested
                node.status = TaskStatus.CANCELLED
                dropped_ids.append(nid)
                self._log(f"  丢弃节点 {nid}: {node.question[:40]}")

        # ---- Validate and apply keep_ids ----
        raw_keep_ids: list[str] = parsed.get("keep_ids", [])
        for nid in raw_keep_ids:
            if nid in existing_ids:
                node = dag.nodes[nid]
                # CRITICAL: kept nodes retain their result, completeness_score,
                # and status='completed'
                if normalize_status(node.status) == TaskStatus.DONE:
                    # Ensure status stays completed — this is the key invariant
                    kept_ids.append(nid)
                else:
                    # Non-completed nodes in keep_ids — keep them as-is
                    kept_ids.append(nid)

        # If no explicit keep_ids, treat all completed nodes not in drop_ids as kept
        if not raw_keep_ids:
            for nid, node in dag.nodes.items():
                if (
                    normalize_status(node.status) == TaskStatus.DONE
                    and nid not in dropped_ids
                ):
                    kept_ids.append(nid)

        # ---- Build a mapping for resolving new-task dependencies ----
        # New tasks may reference existing node IDs or shorthand names
        # We build a name→id map for fuzzy matching
        name_to_id: dict[str, str] = {}
        for nid, node in dag.nodes.items():
            name_to_id[nid] = nid
            # Also map lowercased question prefixes for fuzzy matching
            name_to_id[node.question[:20].lower()] = nid

        # ---- Add new tasks ----
        raw_new_tasks: list[dict] = parsed.get("new_tasks", [])
        for task_spec in raw_new_tasks:
            question = task_spec.get("question", "").strip()
            if not question:
                continue

            agent_type = task_spec.get("agent_type", "builder")
            if agent_type not in ("builder", "explorer", "reviewer"):
                agent_type = "builder"

            raw_deps = task_spec.get("dependencies", [])
            resolved_deps: list[str] = []
            for dep_ref in raw_deps:
                if dep_ref in existing_ids:
                    resolved_deps.append(dep_ref)
                elif dep_ref in name_to_id:
                    resolved_deps.append(name_to_id[dep_ref])
                # Silently skip unresolvable dependencies

            priority = task_spec.get("priority", 5)
            if not isinstance(priority, int) or not (1 <= priority <= 10):
                priority = 5

            new_node = DAGNode.create(
                question=question,
                agent_type=agent_type,
                dependencies=resolved_deps,
                priority=priority,
            )

            try:
                dag.add_node(new_node)
                new_nodes.append(new_node)
                existing_ids.add(new_node.id)
                # Register in name_to_id for subsequent new tasks
                name_to_id[new_node.id] = new_node.id
                name_to_id[question[:20].lower()] = new_node.id
                self._log(
                    f"  新增节点 {new_node.id}: {question[:40]} "
                    f"(deps={resolved_deps}, p={priority})"
                )
            except ValueError as e:
                self._log(f"  新增节点失败 (可能产生环): {e}")

        # ---- Modify existing tasks ----
        raw_modified: list[dict] = parsed.get("modified_tasks", [])
        for mod_spec in raw_modified:
            nid = mod_spec.get("id", "")
            new_question = mod_spec.get("new_question", "").strip()
            if not nid or nid not in existing_ids or not new_question:
                continue

            node = dag.nodes[nid]
            old_question = node.question
            node.question = new_question
            # If the node was pending, reset it so it gets re-executed with the new question
            # If it was completed, we keep the old result but update the question
            # (the caller can decide whether to re-execute)
            if normalize_status(node.status) == TaskStatus.TODO:
                node.status = TaskStatus.TODO
            modified_nodes.append(node)
            self._log(f"  修改节点 {nid}: '{old_question[:30]}' → '{new_question[:30]}'")

        return ReplanResult(
            kept_node_ids=kept_ids,
            dropped_node_ids=dropped_ids,
            new_nodes=new_nodes,
            modified_nodes=modified_nodes,
            reason=reason,
        )


# ---------------------------------------------------------------------------
# Integration helper — run replan after a DAGExecutor batch
# ---------------------------------------------------------------------------
def should_trigger_replan(
    dag: DAG,
    min_completed_ratio: float = 0.3,
    max_iterations: int = 10,
    current_iteration: int = 0,
) -> bool:
    """判断是否应该触发一次重规划。

    在 DAGExecutor 完成一批节点后调用，基于以下条件：
      - 至少有一定比例的节点已完成（默认 30%）
      - 未超过最大迭代次数
      - 还有未完成的节点

    Args:
        dag: 当前 DAG 实例。
        min_completed_ratio: 触发重规划的最低完成比例。
        max_iterations: 最大允许的重规划迭代次数。
        current_iteration: 当前迭代编号。

    Returns:
        ``True`` 如果建议触发重规划。
    """
    if current_iteration >= max_iterations:
        return False

    stats = dag.completion_stats()
    if stats["total"] == 0:
        return False

    low_score_nodes = [
        node for node in dag.nodes.values()
        if normalize_status(node.status) == TaskStatus.DONE and node.completeness_score < REPLAN_COMPLETENESS_THRESHOLD
    ]
    if low_score_nodes:
        return True

    completed_ratio = stats["completed"] / stats["total"]

    # Must have some progress and still have work to do
    has_pending = stats["pending"] > 0 or stats["failed"] > 0
    if not has_pending:
        return False

    # Trigger when enough nodes have completed to make gap analysis meaningful
    return completed_ratio >= min_completed_ratio


def run_replan_cycle(
    replanner: ResultPreservingReplanner,
    dag: DAG,
    original_query: str,
    iteration: int,
) -> Optional[ReplanResult]:
    """执行一次完整的重规划周期：差距分析 → 生成重规划方案。

    这是在 DAGExecutor 的执行循环中调用的便捷函数。

    Args:
        replanner: ResultPreservingReplanner 实例。
        dag: 当前 DAG 实例。
        original_query: 用户的原始查询。
        iteration: 当前迭代编号。

    Returns:
        ``ReplanResult``（如果触发了重规划），或 ``None``。
    """
    if not should_trigger_replan(dag, current_iteration=iteration):
        return None

    gap_analysis = replanner.analyze_gaps(dag, original_query)

    if "无差距" in gap_analysis:
        replanner._log("差距分析表明无需重规划")
        return None

    return replanner.replan(dag, gap_analysis, iteration, original_query)
