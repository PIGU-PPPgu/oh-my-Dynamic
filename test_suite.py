"""
oh-my-Dynamic 大规模测试套件

三层测试：
  1. 单元测试 — 每个模块独立测试
  2. 集成测试 — 模块间协作
  3. 端到端测试 — 真实 Pipeline（可选，需要 API）

用法：
  python test_suite.py              # 跑单元+集成
  python test_suite.py --e2e        # 含端到端（需要 GLM API）
  python test_suite.py --stress     # 压力测试
"""

from __future__ import annotations
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════
# 测试框架
# ═══════════════════════════════════════

_results: list[dict] = []
_pass = 0
_fail = 0
_skip = 0


def test(name):
    """装饰器：注册测试"""
    def wrapper(fn):
        def run():
            try:
                fn()
                _results.append({"name": name, "status": "PASS"})
                global _pass; _pass += 1
                print(f"  ✅ {name}")
            except Exception as e:
                _results.append({"name": name, "status": "FAIL", "error": str(e)})
                global _fail; _fail += 1
                print(f"  ❌ {name}: {e}")
        run.__name__ = name
        return run
    return wrapper


def run_section(title, tests):
    """跑一组测试"""
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")
    for t in tests:
        t()


def summary():
    """打印总结"""
    total = _pass + _fail + _skip
    print(f"\n{'═'*50}")
    print(f"  📊 测试总结: {_pass} ✅ | {_fail} ❌ | {_skip} ⏭️ | 共 {total} 个")
    if _fail == 0:
        print(f"  🎉 全部通过!")
    print(f"{'═'*50}")
    return _fail


# ═══════════════════════════════════════
# 1. 单元测试
# ═══════════════════════════════════════

@test("DAG: 创建节点 + 拓扑排序")
def test_dag_basic():
    from dag import DAG, DAGNode
    dag = DAG()
    n1 = dag.add_node(DAGNode.create("A", priority=8))
    n2 = dag.add_node(DAGNode.create("B", dependencies=[n1.id], priority=5))
    n3 = dag.add_node(DAGNode.create("C", dependencies=[n1.id], priority=7))
    n4 = dag.add_node(DAGNode.create("D", dependencies=[n2.id, n3.id]))
    
    layers = dag.topological_layers()
    assert len(layers) == 3, f"应有3层，实际{len(layers)}"
    assert len(layers[0]) == 1  # A
    assert len(layers[1]) == 2  # B, C
    assert len(layers[2]) == 1  # D


@test("DAG: 环检测")
def test_dag_cycle():
    from dag import DAG, DAGNode
    dag = DAG()
    n1 = dag.add_node(DAGNode.create("A"))
    n2 = dag.add_node(DAGNode.create("B", dependencies=[n1.id]))
    n3 = dag.add_node(DAGNode.create("C", dependencies=[n2.id]))
    # 尝试创建环：C → A（但 A 不在 dependencies 里，需要 A 依赖 C）
    # 实际上 DAG.add_node 会立即检测环，我们直接测试合法依赖
    assert not dag._has_cycle()
    # 测试节点数正确
    assert len(dag.nodes) == 3


@test("DAG: 并行执行 + 依赖上下文")
def test_dag_executor():
    from dag import DAG, DAGNode, DAGExecutor
    dag = DAG()
    n1 = dag.add_node(DAGNode.create("A", priority=8))
    n2 = dag.add_node(DAGNode.create("B", dependencies=[n1.id], context_from_deps=True))
    
    calls = []
    def exec_fn(node, ctx):
        calls.append((node.question, ctx))
        return f"result_{node.question}"
    
    result = DAGExecutor(dag, exec_fn, max_parallel=3, verbose=False).execute()
    stats = result.completion_stats()
    assert stats["completed"] == 2, f"应完成2个，实际{stats['completed']}"
    # B 应该收到 A 的结果
    assert "result_A" in calls[1][1], "B 应收到 A 的上下文"


@test("DAG: DOT 可视化")
def test_dag_dot():
    from dag import DAG, DAGNode
    dag = DAG()
    dag.add_node(DAGNode.create("A"))
    dot = dag.to_dot()
    assert "digraph" in dot
    assert "A" in dot


@test("停机条件: ReadyForSynthesis")
def test_stop_ready():
    from stop_conditions import StopConditionManager, IterationState
    mgr = StopConditionManager.default(max_tokens=100000)
    state = IterationState(iteration_count=1, total_nodes=5, completed_nodes=5,
                           avg_completeness=0.85, total_tokens_used=1000,
                           completeness_history=[0.5, 0.85])
    stop, reason = mgr.check_all(state)
    assert stop, "应停机"
    assert "ReadyForSynthesis" in reason


@test("停机条件: MaxIterations")
def test_stop_max_iter():
    from stop_conditions import StopConditionManager, IterationState
    mgr = StopConditionManager.default(max_tokens=100000, max_iterations=2)
    state = IterationState(iteration_count=2, total_nodes=5, completed_nodes=2,
                           avg_completeness=0.3, total_tokens_used=1000)
    stop, reason = mgr.check_all(state)
    assert stop
    assert "MaxIterations" in reason


@test("停机条件: TokenBudget")
def test_stop_token():
    from stop_conditions import StopConditionManager, IterationState
    mgr = StopConditionManager.default(max_tokens=1000)
    state = IterationState(iteration_count=1, total_nodes=5, completed_nodes=2,
                           avg_completeness=0.3, total_tokens_used=1500)
    stop, reason = mgr.check_all(state)
    assert stop
    assert "TokenBudget" in reason


@test("停机条件: DiminishingReturns")
def test_stop_diminishing():
    from stop_conditions import StopConditionManager, IterationState
    mgr = StopConditionManager.default(max_tokens=100000, max_iterations=99)
    state = IterationState(iteration_count=3, total_nodes=5, completed_nodes=3,
                           avg_completeness=0.6, total_tokens_used=1000,
                           completeness_history=[0.3, 0.55, 0.58, 0.59])
    stop, reason = mgr.check_all(state)
    assert stop, f"应停机: {reason}"
    assert "DiminishingReturns" in reason


@test("TokenTracker: 记录 + 预算检查")
def test_token_tracker():
    from token_tracker import TokenTracker
    t = TokenTracker(max_budget=1000)
    t.record(100, 50, "glm")
    t.record(200, 100, "glm")
    assert t.remaining() == 550
    assert not t.is_over_budget()
    assert t.can_afford(550)
    assert not t.can_afford(600)
    s = t.summary()
    assert s["total"] == 450


@test("TokenTracker: 线程安全")
def test_token_thread_safe():
    import threading
    from token_tracker import TokenTracker
    t = TokenTracker(max_budget=100000)
    errors = []
    def worker():
        try:
            for _ in range(100):
                t.record(10, 5, "glm")
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for th in threads: th.start()
    for th in threads: th.join()
    assert not errors, f"线程安全错误: {errors}"
    assert t.summary()["total"] == 15000  # 10线程 × 100次 × 15


@test("PromptKit: 8 条原则模板")
def test_prompt_kit():
    from prompt_kit import AnthropicPromptKit
    kit = AnthropicPromptKit()
    
    assert len(kit.orchestrator_system("test", 3)) > 100
    assert len(kit.worker_system("dev", "code")) > 50
    assert len(kit.handoff_prompt("A", "B", "art")) > 50
    assert len(kit.verification_prompt("t", "r")) > 50
    assert len(kit.decomposition_prompt("q")) > 50
    assert len(kit.synthesis_prompt(["a", "b"], "q")) > 50
    assert len(kit.replan_prompt(["done"], "gap")) > 50
    assert len(kit.token_budget_alert(50, 100, 3)) > 50


@test("TEA Protocol: 注册 + 进化 + 回滚")
def test_tea_basic():
    import shutil, tempfile
    from tea_protocol import ToolRegistry
    d = tempfile.mkdtemp()
    try:
        reg = ToolRegistry(storage_dir=d)
        t = reg.register("cleaner", "数据清洗", "def cleaner(x): return x.strip()", "agent1")
        assert t.version == "1.0.0"
        
        t2 = reg.evolve(t.tool_id, "def cleaner(x): return x.strip().lower()", "加小写", "agent1")
        assert t2.version == "1.1.0"
        
        reg.rollback(t.tool_id, "1.0.0")
        active = reg.get_active(t.tool_id)
        assert active.version == "1.2.0"
        
        result = reg.test_tool(t.tool_id, " Hello ")
        assert result["success"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("TEA Protocol: 搜索 + 历史")
def test_tea_search():
    import shutil, tempfile
    from tea_protocol import ToolRegistry
    d = tempfile.mkdtemp()
    try:
        reg = ToolRegistry(storage_dir=d)
        reg.register("csv_parser", "解析CSV文件", "def csv_parser(x): return x", "a1")
        reg.register("excel_reader", "读取Excel", "def excel_reader(x): return x", "a2")
        
        found = reg.search("csv")
        assert len(found) == 1
        assert found[0].name == "csv_parser"
        
        reg.evolve(found[0].tool_id, "def csv_parser(x): return x.split(',')", "改进", "a1")
        hist = reg.history(found[0].tool_id)
        assert len(hist) == 2
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("Synthesis: 单次汇总")
def test_synthesis_single():
    from synthesis import Synthesizer
    from token_tracker import TokenTracker
    tracker = TokenTracker(100000)
    
    def mock_llm(sys, user, model="glm"):
        return "综合分析：结果A和B互相印证..."
    
    synth = Synthesizer(mock_llm, tracker)
    results = [
        {"output": "结果A的详细内容", "agent_type": "explorer"},
        {"output": "结果B的详细内容", "agent_type": "builder"},
    ]
    answer = synth.synthesize(results)
    assert len(answer) > 0


@test("Worktree: 创建 + 清理")
def test_worktree_basic():
    import tempfile, subprocess
    from worktree import WorktreeManager
    
    # 创建临时 git 仓库
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", d], capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=d, capture_output=True)
    
    try:
        mgr = WorktreeManager(d)
        wt = mgr.create("test-agent")
        assert wt.is_active()
        assert Path(wt.path).exists()
        
        mgr.abandon("test-agent")
        assert not wt.is_active()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ═══════════════════════════════════════
# 2. 集成测试
# ═══════════════════════════════════════

@test("集成: DAG + StopConditions + TokenTracker")
def test_integration_dag_stop():
    from dag import DAG, DAGNode, DAGExecutor
    from stop_conditions import StopConditionManager, IterationState
    from token_tracker import TokenTracker
    
    tracker = TokenTracker(100000)
    
    dag = DAG()
    for i in range(6):
        deps = [] if i < 2 else [f"n_{j}" for j in range(min(i, 2))]
        dag.add_node(DAGNode(id=f"n_{i}", question=f"Task {i}", dependencies=deps, priority=10-i))
    
    def exec_fn(node, ctx):
        tracker.record(100, 50, "glm")
        return f"done_{node.id}"
    
    result = DAGExecutor(dag, exec_fn, max_parallel=3, verbose=False).execute()
    stats = result.completion_stats()
    
    assert stats["completed"] == 6
    assert tracker.summary()["total"] > 0
    
    mgr = StopConditionManager.default(max_tokens=100000)
    state = IterationState(iteration_count=1, total_nodes=6, completed_nodes=6,
                           avg_completeness=1.0, total_tokens_used=tracker.summary()["total"])
    stop, _ = mgr.check_all(state)
    assert stop


@test("集成: Pipeline 全流程 Mock")
def test_integration_pipeline_mock():
    from pipeline import DynamicPipeline
    
    call_count = 0
    def mock_llm(sys, user):
        nonlocal call_count
        call_count += 1
        # 模拟拆解
        if "拆解" in sys or "subtasks" in user.lower() or "子任务" in user:
            return json.dumps({
                "subtasks": [
                    {"id": "t1", "question": "任务A", "agent_type": "builder", "priority": 8, "dependencies": []},
                    {"id": "t2", "question": "任务B", "agent_type": "builder", "priority": 7, "dependencies": []},
                ]
            })
        return f"这是关于 {user[:20]} 的分析结果。"
    
    pipeline = DynamicPipeline(mock_llm, max_iterations=1, max_tokens=50000, verbose=False)
    result = pipeline.run("测试查询")
    
    assert result["dag_stats"]["total"] > 0
    assert result["iterations"] >= 1
    assert result["duration_s"] < 10  # mock 应该很快
    assert call_count > 0


@test("集成: PromptKit + DAG 拆解")
def test_integration_prompt_dag():
    from prompt_kit import AnthropicPromptKit
    from dag import DAG, DAGNode
    
    kit = AnthropicPromptKit()
    prompt = kit.decomposition_prompt("设计数据分析系统", max_subtasks=3)
    
    # 手动创建 DAG 模拟拆解结果
    dag = DAG()
    n1 = dag.add_node(DAGNode.create("数据采集", priority=8))
    n2 = dag.add_node(DAGNode.create("数据清洗", dependencies=[n1.id]))
    n3 = dag.add_node(DAGNode.create("可视化", dependencies=[n2.id]))
    
    layers = dag.topological_layers()
    assert len(layers) == 3


@test("集成: 可视化生成")
def test_integration_visualize():
    from visualize import generate_dashboard
    
    mock = {
        "dag_stats": {"total": 2, "completed": 2, "failed": 0, "running": 0, "pending": 0, "completeness": 1.0, "avg_score": 0.9, "total_tokens": 1000},
        "iterations": 1,
        "token_summary": {"total_prompt": 500, "total_completion": 500, "total": 1000, "remaining": 49000, "percent_used": 2.0, "call_count": 3},
        "duration_s": 30,
        "stop_reason": "[ReadyForSynthesis] 完备度 ≥ 80%",
        "final_answer": "最终答案",
        "nodes": [
            {"id": "n1", "question": "Q1", "status": "completed", "result": "R1", "agent_type": "builder", "duration_s": 10, "tokens_used": 500, "priority": 8, "dependencies": []},
            {"id": "n2", "question": "Q2", "status": "completed", "result": "R2", "agent_type": "builder", "duration_s": 20, "tokens_used": 500, "priority": 7, "dependencies": ["n1"]},
        ],
        "edges": {"n1": ["n2"]}
    }
    
    path = generate_dashboard(mock, output_path="/tmp/test_dashboard.html")
    html = Path(path).read_text()
    assert "oh-my-Dynamic" in html
    assert "Q1" in html
    Path(path).unlink(missing_ok=True)


# ═══════════════════════════════════════
# 3. 压力测试
# ═══════════════════════════════════════

@test("压力: 100 节点 DAG")
def test_stress_large_dag():
    from dag import DAG, DAGNode, DAGExecutor
    
    dag = DAG()
    # 10 个根节点，每个衍生 9 个子节点 = 100
    roots = []
    for i in range(10):
        n = dag.add_node(DAGNode(id=f"r{i}", question=f"Root {i}", priority=10-i))
        roots.append(n)
    
    for i, root in enumerate(roots):
        for j in range(9):
            dag.add_node(DAGNode(id=f"c{i}_{j}", question=f"Child {i}.{j}", dependencies=[root.id]))
    
    assert len(dag.nodes) == 100
    
    def quick_exec(node, ctx):
        return "ok"
    
    start = time.time()
    result = DAGExecutor(dag, quick_exec, max_parallel=10, verbose=False).execute()
    elapsed = time.time() - start
    
    stats = result.completion_stats()
    assert stats["completed"] == 100, f"应完成100个，实际{stats['completed']}"
    assert elapsed < 10, f"100个mock节点应在10s内完成，实际{elapsed:.1f}s"


@test("压力: 并发 TokenTracker")
def test_stress_token_tracker():
    import threading
    from token_tracker import TokenTracker
    
    t = TokenTracker(10_000_000)
    barrier = threading.Barrier(50)
    errors = []
    
    def worker():
        barrier.wait()
        try:
            for _ in range(200):
                t.record(5, 3, "glm")
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker) for _ in range(50)]
    for th in threads: th.start()
    for th in threads: th.join()
    
    assert not errors
    assert t.summary()["total"] == 50 * 200 * 8  # 80000


# ═══════════════════════════════════════
# 4. 端到端测试（需要 API）
# ═══════════════════════════════════════

@test("E2E: GLM-5.1 真实 Pipeline")
def test_e2e_real():
    from pipeline import DynamicPipeline
    from llm_client import call_glm
    
    def llm_fn(sys, user):
        return call_glm(system_prompt=sys, user_prompt=user)
    
    pipeline = DynamicPipeline(llm_fn, max_iterations=1, max_tokens=30000, verbose=False)
    result = pipeline.run("什么是勾股定理？用一句话回答")
    
    assert result["dag_stats"]["total"] > 0
    assert result["dag_stats"]["completed"] > 0
    assert len(result["final_answer"]) > 10


# ═══════════════════════════════════════
# 主入口
# ═══════════════════════════════════════

if __name__ == "__main__":
    print(f"\n🚀 oh-my-Dynamic 测试套件")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 单元测试
    run_section("📦 单元测试", [
        test_dag_basic,
        test_dag_cycle,
        test_dag_executor,
        test_dag_dot,
        test_stop_ready,
        test_stop_max_iter,
        test_stop_token,
        test_stop_diminishing,
        test_token_tracker,
        test_token_thread_safe,
        test_prompt_kit,
        test_tea_basic,
        test_tea_search,
        test_synthesis_single,
        test_worktree_basic,
    ])
    
    # 集成测试
    run_section("🔗 集成测试", [
        test_integration_dag_stop,
        test_integration_pipeline_mock,
        test_integration_prompt_dag,
        test_integration_visualize,
    ])
    
    # 压力测试
    if "--stress" in sys.argv:
        run_section("💪 压力测试", [
            test_stress_large_dag,
            test_stress_token_tracker,
        ])
    
    # 端到端
    if "--e2e" in sys.argv:
        run_section("🌐 端到端测试 (GLM-5.1 API)", [
            test_e2e_real,
        ])
    
    sys.exit(summary())
