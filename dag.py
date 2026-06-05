"""
DAG 任务图 —— Dynamic Workflows 的核心执行引擎。

来自 VMAO 论文 (arXiv 2603.11445) 的 DAG 执行模型：
  - 复杂查询被拆成有向无环图（DAG）
  - 每个节点是一个子任务，有依赖关系
  - 依赖满足的节点可以并行执行
  - 上一版 TeamEngine 的扁平列表 → 这版的 DAG

核心能力：
  1. DAGNode — 一个子任务节点（类比 VMAO 的 sub-question）
  2. DAG — 管理所有节点，验证无环，计算可执行层
  3. DAGExecutor — 依赖感知的并行执行器
"""

from __future__ import annotations
import json
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Callable, Optional, Any, Union

# 统一状态模型：复用 task.py 的 TaskStatus 枚举
from task import TaskStatus
from capability_registry import CapabilityRouter
from workflow_events import WorkflowEvent
from workflow_config import DEFAULT_COMPLETENESS_SCORE

StatusLike = Union[TaskStatus, str]

_LEGACY_TO_TASK_STATUS = {
    "pending": TaskStatus.TODO,
    "running": TaskStatus.IN_PROGRESS,
    "completed": TaskStatus.DONE,
    "failed": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
    "retrying": TaskStatus.RETRYING,
    "reviewing": TaskStatus.REVIEWING,
    "review": TaskStatus.REVIEWING,
    "todo": TaskStatus.TODO,
    "in_progress": TaskStatus.IN_PROGRESS,
    "done": TaskStatus.DONE,
}

_TASK_STATUS_TO_LEGACY = {
    TaskStatus.TODO: "pending",
    TaskStatus.IN_PROGRESS: "running",
    TaskStatus.REVIEWING: "running",
    TaskStatus.DONE: "completed",
    TaskStatus.FAILED: "failed",
    TaskStatus.RETRYING: "pending",
    TaskStatus.CANCELLED: "failed",
}


def normalize_status(status: StatusLike) -> TaskStatus:
    """Normalize TaskStatus or legacy DAG status strings to TaskStatus."""
    if isinstance(status, TaskStatus):
        return status
    text = str(status).strip()
    if text in _LEGACY_TO_TASK_STATUS:
        return _LEGACY_TO_TASK_STATUS[text]
    try:
        return TaskStatus(text)
    except ValueError as exc:
        raise ValueError(f"unknown DAG node status: {status}") from exc


def status_value(status: StatusLike) -> str:
    """Return the public legacy DAG status string for JSON and events."""
    return _TASK_STATUS_TO_LEGACY[normalize_status(status)]


@dataclass
class DAGNode:
    """
    DAG 中的一个任务节点。
    
    对标 VMAO 的 sub-question 结构：
      - id: 唯一标识
      - question: 具体可回答的问题/任务描述
      - agent_type: 该任务适合哪种 agent（builder/explorer/reviewer）
      - dependencies: 依赖的节点 ID 列表
      - priority: 1-10，越高越优先
      - context_from_deps: 是否把依赖节点的结果注入 prompt
      - verification_criteria: 完备性验证标准
    """
    id: str
    question: str                          # 任务描述
    agent_type: str = "builder"            # builder / explorer / reviewer
    dependencies: list[str] = field(default_factory=list)
    priority: int = 5                      # 1-10, 10 最高
    context_from_deps: bool = True         # 是否注入依赖结果
    verification_criteria: str = ""        # 验证标准
    required_capabilities: list[str] = field(default_factory=list)
    
    # 运行时状态
    status: StatusLike = TaskStatus.TODO
    result: str = ""                       # 执行结果
    completeness_score: float = 0.0        # 0.0-1.0
    owner: str = ""                        # 执行者 agent 名
    started_at: str = ""
    completed_at: str = ""
    duration_s: float = 0.0
    tokens_used: int = 0
    attempt: int = 0                       # 重试次数
    max_attempts: int = 2                  # 最大重试

    def __post_init__(self) -> None:
        self.status = normalize_status(self.status)
    
    @classmethod
    def create(cls, question: str, **kwargs) -> "DAGNode":
        """便捷构造方法"""
        return cls(id=f"n_{uuid.uuid4().hex[:8]}", question=question, **kwargs)


class DAG:
    """
    有向无环图 —— 管理任务依赖关系。
    
    用法：
        dag = DAG()
        n1 = dag.add_node(DAGNode.create("收集数据", priority=8))
        n2 = dag.add_node(DAGNode.create("分析数据", dependencies=[n1.id]))
        n3 = dag.add_node(DAGNode.create("生成报告", dependencies=[n2.id]))
        
        # 获取当前可执行的节点（无依赖或依赖已完成）
        ready = dag.get_ready_nodes()  # → [n1]
        
        # 执行完后
        n1.status = "completed"
        ready = dag.get_ready_nodes()  # → [n2]
    """
    
    def __init__(self):
        self.nodes: dict[str, DAGNode] = {}
        self._adj: dict[str, list[str]] = {}      # 正向邻接表 id → [下游]
        self._rev: dict[str, list[str]] = {}      # 反向邻接表 id → [上游/依赖]
    
    def add_node(self, node: DAGNode) -> DAGNode:
        """添加节点，自动建立依赖边"""
        self.nodes[node.id] = node
        self._adj.setdefault(node.id, [])
        self._rev.setdefault(node.id, [])
        
        for dep_id in node.dependencies:
            if dep_id not in self.nodes:
                raise ValueError(f"依赖节点 {dep_id} 不存在")
            self._adj[dep_id].append(node.id)
            self._rev[node.id].append(dep_id)
        
        # 验证无环
        if self._has_cycle():
            # 回滚
            del self.nodes[node.id]
            for dep_id in node.dependencies:
                if dep_id in self._adj:
                    self._adj[dep_id].remove(node.id)
            self._rev.pop(node.id, None)
            raise ValueError(f"添加节点 {node.id} 会产生环")
        
        return node
    
    def get_node(self, node_id: str) -> Optional[DAGNode]:
        return self.nodes.get(node_id)
    
    def get_ready_nodes(self) -> list[DAGNode]:
        """
        获取当前可执行的节点：
          - status == 'pending'
          - 所有依赖都已 completed
          - 按优先级排序（高优先）
        """
        ready = []
        for node in self.nodes.values():
            if normalize_status(node.status) != TaskStatus.TODO:
                continue
            # 检查依赖是否全部完成
            deps_ok = all(
                normalize_status(self.nodes[dep_id].status) == TaskStatus.DONE
                for dep_id in node.dependencies
                if dep_id in self.nodes
            )
            if deps_ok:
                ready.append(node)
        
        ready.sort(key=lambda n: n.priority, reverse=True)
        return ready
    
    def get_dependency_context(self, node_id: str) -> str:
        """
        收集节点的所有依赖结果，格式化为上下文字符串。
        这就是 VMAO 的 context_from_deps 机制。
        """
        node = self.nodes.get(node_id)
        if not node or not node.context_from_deps:
            return ""
        
        parts = []
        for dep_id in node.dependencies:
            dep = self.nodes.get(dep_id)
            if dep and dep.result:
                parts.append(f"【{dep.question}】\n{dep.result[:2000]}")
        
        return "\n\n".join(parts) if parts else ""
    
    def is_complete(self) -> bool:
        """所有节点是否都已完成"""
        return all(
            normalize_status(n.status) in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for n in self.nodes.values()
        )
    
    def completion_stats(self) -> dict:
        """统计信息"""
        nodes = list(self.nodes.values())
        total = len(nodes)
        completed = sum(1 for n in nodes if normalize_status(n.status) == TaskStatus.DONE)
        failed = sum(1 for n in nodes if normalize_status(n.status) in (TaskStatus.FAILED, TaskStatus.CANCELLED))
        running = sum(1 for n in nodes if normalize_status(n.status) in (TaskStatus.IN_PROGRESS, TaskStatus.REVIEWING))
        pending = sum(1 for n in nodes if normalize_status(n.status) in (TaskStatus.TODO, TaskStatus.RETRYING))
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "completeness": completed / total if total > 0 else 0.0,
            "avg_score": sum(n.completeness_score for n in nodes if normalize_status(n.status) == TaskStatus.DONE) / max(completed, 1),
            "total_tokens": sum(n.tokens_used for n in nodes),
        }
    
    def topological_layers(self) -> list[list[DAGNode]]:
        """
        拓扑分层 —— 同一层的节点可以并行执行。
        返回 [[layer0_nodes], [layer1_nodes], ...]
        """
        in_degree = {nid: 0 for nid in self.nodes}
        for nid in self.nodes:
            for child in self._adj.get(nid, []):
                in_degree[child] = in_degree.get(child, 0) + 1
        
        layers = []
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited = set()
        
        while queue:
            layer = []
            next_queue = deque()
            
            while queue:
                nid = queue.popleft()
                if nid in visited:
                    continue
                visited.add(nid)
                layer.append(self.nodes[nid])
                
                for child in self._adj.get(nid, []):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)
            
            if layer:
                layers.append(layer)
            queue = next_queue
        
        return layers
    
    def to_dot(self) -> str:
        """生成 Graphviz DOT 格式用于可视化"""
        lines = ["digraph DAG {", "  rankdir=TB;", "  node [shape=box, style=rounded];", ""]
        
        for node in self.nodes.values():
            color = {
                "pending": "lightgray",
                "running": "lightyellow",
                "completed": "lightgreen",
                "failed": "lightcoral",
            }.get(status_value(node.status), "white")
            label = node.question[:30].replace('"', '\\"')
            lines.append(f'  "{node.id}" [label="{label}", fillcolor="{color}", style="filled,rounded"];')
        
        lines.append("")
        for nid in self.nodes:
            for child in self._adj.get(nid, []):
                lines.append(f'  "{nid}" -> "{child}";')
        
        lines.append("}")
        return "\n".join(lines)
    
    def _has_cycle(self) -> bool:
        """DFS 检测环"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self.nodes}
        
        def dfs(node_id):
            color[node_id] = GRAY
            for child in self._adj.get(node_id, []):
                if color.get(child) == GRAY:
                    return True
                if color.get(child) == WHITE and dfs(child):
                    return True
            color[node_id] = BLACK
            return False
        
        for nid in self.nodes:
            if color[nid] == WHITE:
                if dfs(nid):
                    return True
        return False
    
    def to_dict(self) -> dict:
        """序列化"""
        nodes = {}
        for nid, node in self.nodes.items():
            payload = asdict(node)
            payload["status"] = status_value(node.status)
            nodes[nid] = payload
        return {
            "nodes": nodes,
            "edges": {nid: children for nid, children in self._adj.items()},
        }


# Executor 函数签名
ExecutorFn = Callable[[DAGNode, str], str]  # (node, context) -> result


class DAGExecutor:
    """
    DAG 并行执行器。
    
    对标 VMAO 的 DAGExecutor：
      - 迭代式获取 ready 节点
      - 并行 batch 执行（默认 k=3）
      - 依赖上下文自动注入
      - 超时和重试
    
    用法：
        def my_executor(node: DAGNode, context: str) -> str:
            # 调用 LLM
            return call_llm(system_prompt=..., user_prompt=node.question + context)
        
        executor = DAGExecutor(dag, my_executor, max_parallel=3)
        completed_dag = executor.execute()
    """
    
    def __init__(
        self,
        dag: DAG,
        executor_fn: ExecutorFn,
        max_parallel: int = 3,
        timeout_per_task: float = 300,    # 5 分钟
        verbose: bool = True,
    ):
        self.dag = dag
        self.executor_fn = executor_fn
        self.max_parallel = max_parallel
        self.timeout_per_task = timeout_per_task
        self._verbose = verbose
        self._iteration = 0
    
    def _log(self, msg: str):
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🗺️ DAG: {msg}")
    
    def execute(
        self,
        event_callback: Optional[Callable[[WorkflowEvent], None]] = None,
        run_id: str = "",
    ) -> DAG:
        """
        执行 DAG —— 反复取 ready 节点并行执行，直到全部完成。
        """
        self._log(f"开始执行 (max_parallel={self.max_parallel})")
        router = CapabilityRouter()
        
        while not self.dag.is_complete():
            ready = self.dag.get_ready_nodes()
            
            if not ready:
                # 没有 ready 节点但还没完成 → 说明有失败的依赖导致死锁
                failed = [n for n in self.dag.nodes.values() if normalize_status(n.status) == TaskStatus.FAILED]
                pending = [n for n in self.dag.nodes.values() if normalize_status(n.status) == TaskStatus.TODO]
                if pending and failed:
                    self._log(f"⚠️ {len(pending)} 个任务因依赖失败而阻塞")
                    # 标记为 failed
                    for n in pending:
                        n.status = TaskStatus.FAILED
                        n.result = "依赖任务失败"
                    break
                else:
                    break
            
            # 取一批（max_parallel 个）
            batch = ready[:self.max_parallel]
            self._iteration += 1
            self._log(f"迭代 {self._iteration}: {len(batch)} 个节点并行")
            self._emit_event(
                event_callback,
                WorkflowEvent(
                    run_id=run_id,
                    kind="batch_started",
                    subject="batch_started",
                    body=f"Starting DAG batch {self._iteration}.",
                    metadata={"iteration": self._iteration, "node_ids": [node.id for node in batch]},
                ),
            )
            
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                futures: dict[Future, DAGNode] = {}
                
                for node in batch:
                    node.status = TaskStatus.IN_PROGRESS
                    node.started_at = datetime.now().isoformat()
                    node.owner = router.pick_agent(
                        node.required_capabilities,
                        run_id=run_id,
                        node_id=node.id,
                        event_callback=event_callback,
                    )
                    context = self.dag.get_dependency_context(node.id)
                    self._emit_event(
                        event_callback,
                        WorkflowEvent(
                            run_id=run_id,
                            kind="node_started",
                            subject="node_started",
                            body=node.question,
                            node_id=node.id,
                            agent_id=node.owner,
                            status=status_value(node.status),
                            preview=node.question[:200],
                            metadata={
                                "agent_type": node.agent_type,
                                "required_capabilities": node.required_capabilities,
                                "dependencies": node.dependencies,
                            },
                        ),
                    )
                    
                    future = pool.submit(self._run_single, node, context)
                    futures[future] = node
                
                for future in as_completed(futures, timeout=self.timeout_per_task * len(batch)):
                    node = futures[future]
                    try:
                        result = future.result(timeout=self.timeout_per_task)
                        node.result = result
                        node.status = TaskStatus.DONE
                        node.completeness_score = self._extract_completeness_score(result, default=DEFAULT_COMPLETENESS_SCORE)
                        node.completed_at = datetime.now().isoformat()
                        node.duration_s = time.time() - (
                            datetime.fromisoformat(node.started_at).timestamp()
                            if node.started_at else time.time()
                        )
                        self._log(f"  ✅ {node.id}: {node.question[:35]}")
                        self._emit_event(
                            event_callback,
                            WorkflowEvent(
                                run_id=run_id,
                                kind="node_done",
                                subject="node_done",
                                body=node.result,
                                node_id=node.id,
                                agent_id=node.owner,
                                status=status_value(node.status),
                                preview=node.result[:200],
                                metadata={
                                    "duration_s": node.duration_s,
                                    "completeness_score": node.completeness_score,
                                },
                            ),
                        )
                    except Exception as e:
                        node.attempt += 1
                        if node.attempt < node.max_attempts:
                            node.status = TaskStatus.TODO
                            self._log(f"  🔄 {node.id}: 重试 ({node.attempt}/{node.max_attempts})")
                        else:
                            node.status = TaskStatus.FAILED
                            node.result = f"ERROR: {e}"
                            node.completeness_score = 0.0
                            self._log(f"  ❌ {node.id}: {e}")
                            self._emit_event(
                                event_callback,
                                WorkflowEvent(
                                    run_id=run_id,
                                    kind="node_failed",
                                    subject="node_failed",
                                    body=node.result,
                                    node_id=node.id,
                                    agent_id=node.owner,
                                    status=status_value(node.status),
                                    preview=node.result[:200],
                                    metadata={"attempt": node.attempt, "max_attempts": node.max_attempts},
                                ),
                            )
            self._emit_event(
                event_callback,
                WorkflowEvent(
                    run_id=run_id,
                    kind="batch_done",
                    subject="batch_done",
                    body=f"Finished DAG batch {self._iteration}.",
                    metadata={"iteration": self._iteration, "node_ids": [node.id for node in batch]},
                ),
            )
        
        stats = self.dag.completion_stats()
        self._log(f"完成: {stats['completed']}/{stats['total']}, "
                   f"失败: {stats['failed']}, Token: {stats['total_tokens']}")
        
        return self.dag

    def _emit_event(self, callback: Optional[Callable[[WorkflowEvent], None]], event: WorkflowEvent) -> None:
        if callback is not None:
            callback(event)

    def _extract_completeness_score(self, result: str, default: float = DEFAULT_COMPLETENESS_SCORE) -> float:
        try:
            data = json.loads(result)
            raw = data.get("completeness_score", data.get("score", default))
            score = float(raw)
        except Exception:
            score = default
        return max(0.0, min(1.0, score))
    
    def _run_single(self, node: DAGNode, context: str) -> str:
        """执行单个节点"""
        return self.executor_fn(node, context)
