"""
oh-my-Dynamic 端到端 Pipeline

把所有模块串成一条完整流水线：
  用户查询 → Decompose → DAG 构建 → DAG 执行 → 停机检查 → Replan/合成 → 输出

对标 VMAO 论文的 Plan-Execute-Verify-Replan 循环：
  Plan:     prompt_kit.decomposition_prompt → DAG
  Execute:  DAGExecutor + worker_system prompt
  Verify:   stop_conditions + verification_prompt
  Replan:   dynamic_replan (结果保留式)
  Synthesize: synthesis.py (分层汇总)
"""

from __future__ import annotations
import json
import time
from datetime import datetime
from typing import Optional

from oh_my_dynamic.runtime.dag import DAG, DAGNode, DAGExecutor, normalize_status
from oh_my_dynamic.runtime.task import TaskStatus
from oh_my_dynamic.runtime.stop_conditions import StopConditionManager, IterationState
from oh_my_dynamic.runtime.token_tracker import TokenTracker
from oh_my_dynamic.runtime.synthesis import Synthesizer
from oh_my_dynamic.runtime.dynamic_replan import ResultPreservingReplanner, ReplanResult, should_trigger_replan
from oh_my_dynamic.core.prompt_kit import AnthropicPromptKit


class DynamicPipeline:
    """
    oh-my-Dynamic 完整流水线。

    用法：
        pipeline = DynamicPipeline(
            llm_fn=call_llm,
            max_iterations=3,
            max_tokens=100000,
        )

        result = pipeline.run("设计一个班级数据分析系统的完整方案")
        print(result["final_answer"])
    """

    def __init__(
        self,
        llm_fn,                              # (system_prompt, user_prompt) -> str
        max_iterations: int = 3,
        max_tokens: int = 500_000,
        max_parallel: int = 3,
        completeness_threshold: float = 0.80,
        verbose: bool = True,
    ):
        self.llm_fn = llm_fn
        self.max_iterations = max_iterations
        self.max_parallel = max_parallel

        # 子系统
        self.token_tracker = TokenTracker(max_budget=max_tokens)
        self.stop_manager = StopConditionManager.default(
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            completeness_threshold=completeness_threshold,
        )
        self.replanner = ResultPreservingReplanner(llm_fn, self.token_tracker)
        self.synthesizer = Synthesizer(llm_fn, self.token_tracker)
        self.prompt_kit = AnthropicPromptKit()

        self._verbose = verbose

    def _log(self, msg: str):
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🚀 {msg}")

    def _llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 并追踪 token"""
        result = self.llm_fn(system_prompt, user_prompt)
        # 粗略估算 token（中文约 1.5 字/token）
        self.token_tracker.record(
            prompt_tokens=len(system_prompt + user_prompt) // 2,
            completion_tokens=len(result) // 2,
            model="glm-5.1",
        )
        return result

    # ─── Step 1: Decompose ───

    def decompose(self, query: str) -> DAG:
        """将查询拆解为 DAG"""
        self._log(f"拆解查询: {query[:50]}...")

        prompt = self.prompt_kit.decomposition_prompt(query, max_subtasks=5)
        response = self._llm("你是任务拆解专家。", prompt)

        # 解析 JSON
        subtasks = self._parse_subtasks(response)

        # 构建 DAG
        dag = DAG()
        id_map = {}

        for st in subtasks:
            node = DAGNode.create(
                question=st.get("question", ""),
                agent_type=st.get("agent_type", "builder"),
                priority=st.get("priority", 5),
                verification_criteria=st.get("verification_criteria", ""),
            )

            # 解析依赖
            dep_ids = st.get("dependencies", [])
            node.dependencies = [id_map[d] for d in dep_ids if d in id_map]

            dag.add_node(node)
            id_map[st.get("id", node.id)] = node.id

        self._log(f"拆解完成: {len(dag.nodes)} 个节点, {sum(1 for n in dag.nodes.values() if n.dependencies)} 个有依赖")
        return dag

    def _parse_subtasks(self, response: str) -> list[dict]:
        """从 LLM 响应中解析子任务 JSON"""
        # 尝试提取 JSON
        try:
            # 方法1: 直接解析
            data = json.loads(response)
            if "subtasks" in data:
                return data["subtasks"]
        except json.JSONDecodeError:
            pass

        # 方法2: 提取 ```json ``` 块
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    data = json.loads(response[start:end].strip())
                    if "subtasks" in data:
                        return data["subtasks"]
                except json.JSONDecodeError:
                    pass

        # 方法3: 找最外层花括号
        start = response.find("{")
        end = response.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(response[start:end+1])
                if "subtasks" in data:
                    return data["subtasks"]
            except json.JSONDecodeError:
                pass

        # Fallback: 按行拆分
        self._log("⚠️ JSON 解析失败，按行拆分")
        lines = [l.strip().lstrip("0123456789.-) ") for l in response.split("\n") if l.strip() and not l.strip().startswith("#")]
        return [{"question": l, "agent_type": "builder", "priority": 5, "dependencies": []} for l in lines[:10]]

    # ─── Step 2: Execute DAG ───

    def execute_dag(self, dag: DAG) -> DAG:
        """执行 DAG"""

        def executor_fn(node: DAGNode, context: str) -> str:
            # 选择 prompt 模板
            if node.agent_type == "reviewer":
                system = self.prompt_kit.verification_prompt(
                    task_desc=node.question,
                    result=context,
                )
                user_prompt = f"请验证以下任务的结果：\n{context}"
            else:
                system = self.prompt_kit.worker_system(
                    role=node.agent_type,
                    context=node.question,
                    constraints=[node.verification_criteria] if node.verification_criteria else None,
                )
                user_prompt = node.question
                if context:
                    user_prompt += f"\n\n【上下文信息】\n{context}"

            return self._llm(system, user_prompt)

        executor = DAGExecutor(dag, executor_fn, max_parallel=self.max_parallel, verbose=self._verbose)
        return executor.execute()

    # ─── Step 3: Check Stop + Replan ───

    def check_and_replan(self, dag: DAG, query: str, iteration: int) -> tuple[bool, DAG]:
        """
        检查停机条件，决定继续还是停止。
        如果继续且有 gap，触发 replan。

        Returns:
            (should_stop, updated_dag)
        """
        stats = dag.completion_stats()

        state = IterationState(
            iteration_count=iteration,
            total_nodes=stats["total"],
            completed_nodes=stats["completed"],
            avg_completeness=stats["avg_score"] if stats["avg_score"] > 0 else stats["completeness"],
            avg_confidence=stats["avg_score"],
            total_tokens_used=stats["total_tokens"],
            completeness_history=[stats["completeness"]],  # 简化
        )

        should_stop, reason = self.stop_manager.check_all(state)

        if should_stop:
            self._log(f"🛑 停机: {reason}")
            return True, dag

        # 检查是否需要 replan
        if should_trigger_replan(dag, iteration, max_iterations=self.max_iterations):
            self._log(f"🔄 触发 Replan (迭代 {iteration})...")

            try:
                replan_result = self.replanner.replan(
                    dag=dag,
                    gap_analysis=f"迭代 {iteration} 后，完备度 {stats['completeness']:.0%}，"
                                 f"已完成 {stats['completed']}/{stats['total']}",
                    iteration=iteration,
                    original_query=query,
                )
                self._log(f"Replan: 保留 {len(replan_result.kept_node_ids)}, "
                          f"新增 {len(replan_result.new_nodes)}, "
                          f"修改 {len(replan_result.modified_nodes)}")
            except Exception as e:
                self._log(f"Replan 失败: {e}")

        return False, dag

    # ─── Step 4: Synthesize ───

    def synthesize(self, dag: DAG, query: str) -> str:
        """汇总所有节点结果"""
        results = []
        for node in dag.nodes.values():
            if normalize_status(node.status) == TaskStatus.DONE and node.result:
                results.append({
                    "source": node.question,
                    "output": node.result,        # synthesis.py 期望 "output" 键
                    "agent_type": node.agent_type,
                })

        if not results:
            return "无有效结果"

        self._log(f"汇总 {len(results)} 个结果...")
        return self.synthesizer.synthesize(results)

    # ─── Main Entry ───

    def run(self, query: str) -> dict:
        """
        运行完整 Pipeline。

        Returns:
            {
                "final_answer": str,
                "dag_stats": dict,
                "iterations": int,
                "token_summary": dict,
                "duration_s": float,
                "stop_reason": str,
            }
        """
        start_time = time.time()
        self._log(f"{'='*50}")
        self._log(f"查询: {query}")
        self._log(f"{'='*50}")

        # Step 1: 拆解
        dag = self.decompose(query)

        if not dag.nodes:
            return {
                "final_answer": "拆解失败：无法生成子任务",
                "dag_stats": {},
                "iterations": 0,
                "token_summary": self.token_tracker.summary(),
                "duration_s": time.time() - start_time,
                "stop_reason": "decompose_failed",
            }

        # Step 2-3: 迭代执行
        iteration = 0
        stop_reason = "max_iterations"

        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"--- 迭代 {iteration}/{self.max_iterations} ---")

            # 执行 DAG
            dag = self.execute_dag(dag)

            # 检查停机 + 可能的 Replan
            should_stop, dag = self.check_and_replan(dag, query, iteration)

            if should_stop:
                stop_reason = "stop_condition"
                break

        # Step 4: 汇总
        final_answer = self.synthesize(dag, query)

        duration = time.time() - start_time
        stats = dag.completion_stats()
        token_summary = self.token_tracker.summary()

        self._log(f"{'='*50}")
        self._log(f"完成! {stats['completed']}/{stats['total']} 任务, "
                   f"{duration:.0f}s, {token_summary['total']} tokens")
        self._log(f"{'='*50}")

        return {
            "final_answer": final_answer,
            "dag_stats": stats,
            "iterations": iteration,
            "token_summary": token_summary,
            "duration_s": duration,
            "stop_reason": stop_reason,
            "dag_dot": dag.to_dot(),
        }


# ─── 便捷运行函数 ───

def run_pipeline(query: str, llm_fn=None, **kwargs) -> dict:
    """
    一行运行 Pipeline。

    Args:
        query: 查询文本
        llm_fn: LLM 调用函数 (system_prompt, user_prompt) -> str
        **kwargs: 传给 DynamicPipeline 的参数
    """
    if llm_fn is None:
        # 默认使用 llm_client
        from oh_my_dynamic.core.llm_client import call_llm
        llm_fn = lambda sys, user: call_llm(system_prompt=sys, user_prompt=user)

    pipeline = DynamicPipeline(llm_fn=llm_fn, **kwargs)
    return pipeline.run(query)
