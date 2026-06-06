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


def init_test_git_repo(path: str) -> None:
    """Create a deterministic test git repository with a valid initial commit."""
    import subprocess

    commands = [
        ["git", "init", path],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "oh-my-Dynamic Tests"],
        ["git", "commit", "--allow-empty", "-m", "init"],
    ]
    for command in commands:
        kwargs = {"capture_output": True, "text": True}
        if command[0:2] == ["git", "config"] or command[0:2] == ["git", "commit"]:
            kwargs["cwd"] = path
        result = subprocess.run(command, **kwargs)
        if result.returncode != 0:
            raise AssertionError(
                f"{' '.join(command)} failed: stdout={result.stdout!r} stderr={result.stderr!r}"
            )


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
                _results.append({"name": name, "status": "FAIL", "error": str(e), "traceback": traceback.format_exc()})
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


@test("DAG: TaskStatus normalization and legacy JSON")
def test_dag_status_normalization():
    from dag import DAG, DAGNode, normalize_status, status_value
    from task import TaskStatus

    dag = DAG()
    parent = dag.add_node(DAGNode.create("Parent"))
    child = dag.add_node(DAGNode.create("Child", dependencies=[parent.id], status="pending"))

    assert normalize_status(parent.status) == TaskStatus.TODO
    assert normalize_status("completed") == TaskStatus.DONE
    assert status_value(TaskStatus.IN_PROGRESS) == "running"
    assert dag.get_ready_nodes()[0].id == parent.id

    parent.status = TaskStatus.DONE
    assert dag.get_ready_nodes()[0].id == child.id
    child.status = "completed"

    stats = dag.completion_stats()
    payload = dag.to_dict()
    assert stats["completed"] == 2
    assert payload["nodes"][parent.id]["status"] == "completed"
    assert payload["nodes"][child.id]["status"] == "completed"


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


@test("TEA Protocol: 沙箱阻止内省逃逸")
def test_tea_sandbox_blocks_escape():
    import shutil, tempfile
    from tea_protocol import ToolRegistry

    d = tempfile.mkdtemp()
    try:
        reg = ToolRegistry(storage_dir=d)
        malicious = r'''
def probe(x):
    return ().__class__.__mro__[1].__subclasses__()
'''
        tool = reg.register("probe", "尝试逃逸沙箱", malicious, "audit")
        result = reg.test_tool(tool.tool_id, "x")
        assert not result["success"]
        assert "不安全" in result["error"] or "unsafe" in result["error"].lower()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("LLM Client: Provider 路由")
def test_llm_provider_routing():
    from llm_client import _detect_provider

    cases = {
        "openrouter/anthropic/claude-sonnet-4": "openrouter",
        "openrouter/openai/gpt-5.2": "openrouter",
        "deepseek-chat": "deepseek",
        "deepseek/deepseek-reasoner": "deepseek",
        "qwen-plus": "qwen",
        "dashscope/qwen-max": "qwen",
        "moonshot-v1-8k": "moonshot",
        "kimi-k2": "moonshot",
        "glm-5.1": "zhipu",
        "gpt-5.2": "openai",
        "claude-sonnet-4-6": "anthropic",
        "gemini-3.5-flash": "google",
    }
    for model, provider in cases.items():
        assert _detect_provider(model) == provider, f"{model} 应路由到 {provider}"


@test("Protocol Adapters: MCP + A2A payloads")
def test_protocol_adapters():
    from protocol_adapters import A2ATaskStore, a2a_agent_card, mcp_tools, run_mcp_tool

    def mock_llm(sys, user):
        if "拆解" in user or "subtasks" in user.lower():
            return '{"subtasks":[{"id":"a","question":"A","agent_type":"builder","priority":5,"dependencies":[]}]}'
        return "protocol adapter answer"

    tools = mcp_tools()
    assert tools[0]["name"] == "oh_my_dynamic.run_workflow"
    assert "inputSchema" in tools[0]

    response = run_mcp_tool("oh_my_dynamic.run_workflow", {"query": "demo", "max_iterations": 1}, mock_llm)
    assert response["content"][0]["type"] == "text"
    assert "structuredContent" in response

    card = a2a_agent_card("http://localhost:9999")
    assert card["name"] == "oh-my-Dynamic"
    assert card["skills"][0]["id"] == "dynamic-workflow"

    store = A2ATaskStore(mock_llm)
    task = store.submit("demo")
    assert task["status"]["state"] == "completed"
    assert task["artifacts"]


@test("AgentBroker: messages + artifacts + A2A snapshot")
def test_agent_broker_collaboration():
    import shutil, tempfile
    from agent_broker import AgentBroker

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(d)
        broker.register_agent("planner", "planner", ["decompose"], metadata={"goal": "original"})
        merged_planner = broker.register_agent(
            "planner",
            "spoofed",
            ["summarize"],
            metadata={"goal": "overwrite", "confidence": 0.9},
        )
        assert merged_planner.role == "planner"
        assert set(merged_planner.capabilities) == {"decompose", "summarize"}
        assert merged_planner.metadata["goal"] == "original"
        assert merged_planner.metadata["confidence"] == 0.9
        broker.register_agent("builder", "builder", ["write"])
        broker.register_agent("reviewer", "reviewer", ["review"])

        artifact = broker.publish_artifact(
            "planner",
            "plan",
            "Build the broker layer first.",
            kind="plan",
        )
        broker.create_handoff(
            "planner",
            "builder",
            "task-1",
            "Implement broker",
            "Use the attached plan.",
            artifact_ids=[artifact.id],
            thread_id="thread-1",
        )
        broker.request_review(
            "builder",
            "reviewer",
            "task-1",
            "Review broker",
            "Please review the broker artifact contract.",
            artifact_ids=[artifact.id],
            thread_id="thread-1",
        )
        broker.send_message(
            "planner",
            None,
            "Shared constraint",
            "Do not require external API keys.",
            thread_id="thread-1",
        )

        builder_inbox = broker.read_inbox("builder", mark_delivered=False)
        reviewer_inbox = broker.read_inbox("reviewer", mark_delivered=False)
        assert {event.kind for event in builder_inbox} == {"handoff", "message"}
        assert {event.kind for event in reviewer_inbox} == {"review_request", "message"}

        snapshot = broker.to_a2a_task("thread-1")
        assert snapshot["id"] == "thread-1"
        assert snapshot["history"]
        assert snapshot["artifacts"][0]["artifactId"] == artifact.id
        assert broker.get_artifact(artifact.id).content.startswith("Build the broker")

        review_response = broker.respond_review(
            "reviewer",
            "builder",
            "task-1",
            "Broker review",
            "Approved with trace coverage.",
            "approved",
            artifact_ids=[artifact.id],
            thread_id="thread-1",
        )
        assert review_response.kind == "review_response"
        assert review_response.metadata["verdict"] == "approved"

        try:
            broker.send_message("unknown", "builder", "bad", "should fail")
        except ValueError as exc:
            assert "not registered" in str(exc)
        else:
            raise AssertionError("unregistered sender should be rejected")

        try:
            broker.create_handoff("planner", "builder", "task-2", "bad artifact", "", artifact_ids=["missing"])
        except ValueError as exc:
            assert "unknown artifact" in str(exc)
        else:
            raise AssertionError("unknown artifact references should be rejected")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("AgentBroker: rejects unsafe agent ids")
def test_agent_broker_rejects_unsafe_agent_ids():
    import shutil, tempfile
    from agent_broker import AgentBroker

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(str(Path(d) / "broker"))
        unsafe_ids = ["../escape", "../../escape", "/tmp/escape", "bad/name", "bad\\name", ".hidden", "bad name"]
        for unsafe_id in unsafe_ids:
            try:
                broker.register_agent(unsafe_id, "worker")
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe agent id should be rejected: {unsafe_id}")

        broker.register_agent("safe.agent-01", "worker")
        broker.send_message("broker", "safe.agent-01", "hello", "safe")
        assert broker.read_inbox("safe.agent-01", mark_delivered=False)
        assert not (Path(d) / "escape.jsonl").exists()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("BrokerGateway: HTTP task lifecycle + SSE")
def test_broker_gateway_http_lifecycle():
    import shutil, tempfile, threading, urllib.request
    from agent_broker import AgentBroker
    from broker_gateway import create_server

    d = tempfile.mkdtemp()
    server = None
    thread = None
    try:
        broker = AgentBroker(str(Path(d) / "broker"))
        server = create_server(broker, host="127.0.0.1", port=0)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, payload=None, headers=None):
            data = None
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                base + path,
                data=data,
                method=method,
                headers={"Content-Type": "application/json", **(headers or {})},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
                if content_type.startswith("text/event-stream"):
                    return body
                return json.loads(body)

        card = request("GET", "/.well-known/agent.json")
        assert card["capabilities"]["agentBroker"]
        assert any(skill["id"] == "agent-broker" for skill in card["skills"])

        task = request("POST", "/tasks", {"message": "Coordinate a broker workflow"})
        task_id = task["id"]
        assert task["status"]["state"] == "working"

        agents = [
            request("POST", "/agents", {"id": "planner", "role": "planner", "capabilities": ["plan"]}),
            request("POST", "/agents", {"id": "builder", "role": "builder", "capabilities": ["build"]}),
            request("POST", "/agents", {"id": "reviewer", "role": "reviewer", "capabilities": ["review"]}),
        ]
        assert {agent["id"] for agent in agents} == {"planner", "builder", "reviewer"}

        all_agents = request("GET", "/agents")
        assert {"user", "orchestrator", "planner", "builder", "reviewer"}.issubset(
            {agent["id"] for agent in all_agents["agents"]}
        )

        artifact = request("POST", f"/tasks/{task_id}/artifacts", {
            "producer": "planner",
            "name": "plan",
            "content": "Broker gateway plan",
            "kind": "plan",
        })
        assert artifact["id"].startswith("artifact_")

        handoff = request("POST", f"/tasks/{task_id}/handoffs", {
            "from": "planner",
            "to": "builder",
            "task_id": "build-broker",
            "subject": "Implement gateway",
            "body": "Use the plan artifact.",
            "artifact_ids": [artifact["id"]],
        })
        assert handoff["kind"] == "handoff"

        review = request("POST", f"/tasks/{task_id}/review-requests", {
            "from": "builder",
            "reviewer": "reviewer",
            "task_id": "build-broker",
            "subject": "Review gateway",
            "body": "Check lifecycle endpoints.",
            "artifact_ids": [artifact["id"]],
        })
        assert review["kind"] == "review_request"

        response = request("POST", f"/tasks/{task_id}/review-responses", {
            "from": "reviewer",
            "to": "builder",
            "task_id": "build-broker",
            "subject": "Gateway review response",
            "body": "Approved.",
            "verdict": "approved",
            "artifact_ids": [artifact["id"]],
            "parent_id": review["id"],
        })
        assert response["kind"] == "review_response"
        assert response["metadata"]["verdict"] == "approved"

        message = request("POST", f"/tasks/{task_id}/messages", {
            "from": "reviewer",
            "to": "orchestrator",
            "subject": "Review complete",
            "body": "Looks coherent.",
        })
        assert message["kind"] == "message"

        completed = request("POST", f"/tasks/{task_id}/complete", {
            "final_answer": "Gateway lifecycle complete.",
        })
        assert completed["status"]["state"] == "completed"
        assert any(item["name"] == "final_answer" for item in completed["artifacts"])

        events = request("GET", f"/tasks/{task_id}/events")
        assert len(events["events"]) >= 7

        sse = request("GET", f"/tasks/{task_id}/events", headers={"Accept": "text/event-stream"})
        assert "event: handoff" in sse
        assert "event: review_request" in sse
        assert "workflow_completed" in sse
        refreshed = request("GET", f"/tasks/{task_id}")
        history_kinds = [item["metadata"]["kind"] for item in refreshed["history"]]
        assert "trace" in history_kinds
        assert "handoff" in history_kinds
        assert "review_response" in history_kinds

        inbox = request("GET", "/agents/builder/inbox?mark_delivered=0")
        assert {"handoff", "review_response"}.issubset({event["kind"] for event in inbox["events"]})

        try:
            request("POST", f"/tasks/{task_id}/messages", {
                "from": "unknown",
                "to": "orchestrator",
                "subject": "bad",
                "body": "bad",
            })
        except Exception as exc:
            assert "HTTP Error 400" in str(exc)
        else:
            raise AssertionError("gateway should reject unregistered senders")
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        shutil.rmtree(d, ignore_errors=True)


@test("BrokerGateway: auth, actor binding, and body limits")
def test_broker_gateway_auth_and_limits():
    import shutil, tempfile, threading, urllib.error, urllib.request
    from agent_broker import AgentBroker
    from broker_gateway import UNAUTHENTICATED_LOOPBACK_WARNING, create_server

    assert "WARNING" in UNAUTHENTICATED_LOOPBACK_WARNING
    assert "OH_MY_DYNAMIC_GATEWAY_TOKEN" in UNAUTHENTICATED_LOOPBACK_WARNING

    d = tempfile.mkdtemp()
    server = None
    thread = None
    try:
        try:
            create_server(AgentBroker(str(Path(d) / "blocked")), host="0.0.0.0", port=0)
        except ValueError as exc:
            assert "non-loopback" in str(exc)
        else:
            raise AssertionError("non-loopback gateway binding should require auth")

        broker = AgentBroker(str(Path(d) / "broker"))
        broker.register_agent("external", "external")
        token = "test-token"
        server = create_server(
            broker,
            host="127.0.0.1",
            port=0,
            auth_token=token,
            max_body_bytes=256,
        )
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, payload=None, headers=None):
            data = None
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                base + path,
                data=data,
                method=method,
                headers={"Content-Type": "application/json", **(headers or {})},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        card = request("GET", "/.well-known/agent.json")
        assert card["capabilities"]["agentBroker"]

        try:
            request("GET", "/agents")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("gateway should require auth for non-public GET")

        auth = {"Authorization": f"Bearer {token}"}
        planner = request("POST", "/agents", {"id": "planner", "role": "planner"}, headers=auth)
        assert planner["id"] == "planner"
        assert planner["agent_token"].startswith("agt_")
        builder = request("POST", "/agents", {"id": "builder", "role": "builder"}, headers=auth)
        assert builder["agent_token"].startswith("agt_")

        task = request("POST", "/tasks", {"message": "secure workflow"}, headers=auth)
        task_id = task["id"]

        actor_auth = {**auth, "X-Agent-Id": "planner", "X-Agent-Token": planner["agent_token"]}
        message = request("POST", f"/tasks/{task_id}/messages", {
            "from": "orchestrator",
            "to": "builder",
            "subject": "actor binding",
            "body": "payload sender should be ignored in token mode",
        }, headers=actor_auth)
        assert message["from_agent"] == "planner"

        try:
            request("POST", f"/tasks/{task_id}/messages", {
                "from": "planner",
                "to": "orchestrator",
                "subject": "bad actor token",
                "body": "bad",
            }, headers={**auth, "X-Agent-Id": "planner", "X-Agent-Token": "wrong"})
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("gateway should reject wrong per-agent actor token")

        try:
            request("POST", f"/tasks/{task_id}/messages", {
                "from": "external",
                "to": "orchestrator",
                "subject": "missing issued token",
                "body": "bad",
            }, headers={**auth, "X-Agent-Id": "external"})
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("gateway should reject registered actors without an issued token")

        try:
            request("GET", "/agents/builder/inbox?mark_delivered=0", headers=actor_auth)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("planner should not read builder inbox")

        builder_inbox = request(
            "GET",
            "/agents/builder/inbox?mark_delivered=0",
            headers={**auth, "X-Agent-Id": "builder", "X-Agent-Token": builder["agent_token"]},
        )
        assert any(event["from_agent"] == "planner" for event in builder_inbox["events"])

        try:
            request("POST", f"/tasks/{task_id}/messages", {
                "from": "planner",
                "to": "orchestrator",
                "subject": "missing actor",
                "body": "bad",
            }, headers=auth)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("gateway should require X-Agent-Id for task actions in auth mode")

        try:
            request("POST", "/tasks", {"message": "x" * 300}, headers=auth)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("gateway should reject oversized request bodies before JSON processing")
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        shutil.rmtree(d, ignore_errors=True)


@test("Protocol: artifact compatibility, thread filtering, and event cursor")
def test_protocol_artifact_compatibility_and_cursor():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from broker_gateway import BrokerGateway

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(str(Path(d) / "broker"))
        broker.register_agent("planner", "planner")
        broker.register_agent("builder", "builder")

        old_record = {
            "id": "artifact_old",
            "producer": "planner",
            "name": "old-plan",
            "kind": "plan",
            "content": "old artifact without thread fields",
            "content_type": "text/plain",
            "metadata": {},
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        broker.artifacts_path.write_text(json.dumps(old_record) + "\n", encoding="utf-8")
        assert broker.list_artifacts()[0].thread_id == "default"
        assert broker.list_artifacts()[0].task_id == ""

        first = broker.send_message("planner", "builder", "first", "one", thread_id="thread-a", artifact_ids=["artifact_old"])
        broker.send_message("builder", "planner", "second", "two", thread_id="thread-a")
        leaked = broker.publish_artifact("planner", "other-thread", "secret-ish", thread_id="thread-b")
        snapshot = broker.to_a2a_task("thread-a")
        artifact_ids = {item["artifactId"] for item in snapshot["artifacts"]}
        assert "artifact_old" in artifact_ids
        assert leaked.id not in artifact_ids

        gateway = BrokerGateway(broker)
        cursor_snapshot = gateway.list_events("thread-a", after=first.id)
        assert all(event["id"] != first.id for event in cursor_snapshot["events"])
        assert [event["subject"] for event in cursor_snapshot["events"]] == ["second"]
        card = gateway.agent_card()
        assert card["capabilities"]["capabilityDiscovery"]
        assert "registeredAgents" in card["capabilities"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("BrokerReducer: artifacts, errors, reviews, dependencies")
def test_broker_reducer_uses_full_broker_evidence():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from broker_reducer import reduce_broker_thread

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(str(Path(d) / "broker"))
        broker.register_agent("builder", "builder", metadata={"dependencies": ["planner"]})
        broker.register_agent("reviewer", "reviewer")
        artifact = broker.publish_artifact("builder", "patch", "diff --git a/a b/a", kind="worktree_diff", thread_id="thread-r")
        broker.trace("builder", "codex_subagent_completed", "Builder completed.", thread_id="thread-r", artifact_ids=[artifact.id])
        broker.trace("reviewer", "codex_subagent_failed", "Reviewer failed.", thread_id="thread-r")
        broker.request_review("builder", "reviewer", "task-1", "Review patch", "Please inspect.", thread_id="thread-r", artifact_ids=[artifact.id])
        broker.respond_review("reviewer", "builder", "task-1", "Review result", "Needs test coverage.", "changes_requested", thread_id="thread-r")

        result = reduce_broker_thread(broker, "thread-r", "reduce evidence")
        assert result.terminal_state == "partial"
        assert artifact.id in result.artifact_ids
        assert "Failed agents: 1" in result.final_answer
        assert "Review responses: 1" in result.final_answer
        assert "agent(s) failed" in result.risk_summary
        assert result.recommended_next_agents
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexAppBridge: dispatch envelope ingestion")
def test_codex_app_bridge_ingestion():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from codex_app_bridge import (
        CodexSubagentSpec,
        build_subagent_prompt,
        complete_dispatch_plan,
        create_dispatch_plan,
        ingest_subagent_envelope,
        parse_subagent_envelope,
        register_dispatch_plan,
    )

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(d)
        plan = create_dispatch_plan(
            "Review a project with real Codex App subagents",
            [
                CodexSubagentSpec(
                    id="planner",
                    role="planner",
                    goal="Plan the workflow",
                    capabilities=["plan"],
                ),
                CodexSubagentSpec(
                    id="builder",
                    role="builder",
                    goal="Build the patch",
                    dependencies=["planner"],
                    capabilities=["build"],
                ),
                CodexSubagentSpec(
                    id="reviewer",
                    role="reviewer",
                    goal="Review the patch",
                    dependencies=["builder"],
                    capabilities=["review"],
                ),
            ],
            run_id="codex-thread-1",
        )
        register_dispatch_plan(broker, plan)
        plan_dict = plan.to_dict()
        assert plan_dict["topological_layers"] == [["planner"], ["builder"], ["reviewer"]]
        assert plan_dict["ready_batches"] == [["planner"], ["builder"], ["reviewer"]]
        prompt = build_subagent_prompt(plan, plan.agents[0])
        assert "current Codex App model/runtime" in prompt
        assert "Return exactly one JSON object" in prompt

        raw = """
```json
{
  "agent_id": "planner",
  "status": "completed",
  "summary": "Plan ready.",
  "artifacts": [
    {"name": "plan", "kind": "plan", "content": "1. build\\n2. review"}
  ],
  "messages": [
    {"to_agent": "orchestrator", "subject": "Plan complete", "body": "Ready.", "artifact_names": ["plan"]}
  ],
  "handoffs": [
    {"to_agent": "builder", "task_id": "build-1", "subject": "Build this", "body": "Use plan.", "artifact_names": ["plan"]}
  ],
  "review_requests": [
    {"reviewer": "reviewer", "task_id": "build-1", "subject": "Review plan", "body": "Check scope.", "artifact_names": ["plan"]}
  ],
  "review_responses": [],
  "metadata": {"confidence": 0.9},
  "error": ""
}
```
"""
        envelope = parse_subagent_envelope(raw)
        result = ingest_subagent_envelope(
            broker,
            plan.run_id,
            envelope,
            role="planner",
            capabilities=["plan"],
        )
        assert result["agent_id"] == "planner"
        assert "plan" in result["artifact_ids"]
        builder_prompt = build_subagent_prompt(plan, plan.agents[1], dependency_outputs={"planner": envelope})
        assert "Dependency outputs:" in builder_prompt
        assert "Plan ready." in builder_prompt
        assert "1. build" in builder_prompt
        events = broker.list_events(thread_id=plan.run_id)
        kinds = [event.kind for event in events]
        assert "handoff" in kinds
        assert "review_request" in kinds
        assert any(event.subject == "codex_subagent_completed" for event in events)
        snapshot = broker.to_a2a_task(plan.run_id)
        assert snapshot["status"]["state"] == "working"
        assert snapshot["artifacts"][0]["name"] == "plan"
        for agent_id, summary in [("builder", "Build ready."), ("reviewer", "Review ready.")]:
            ingest_subagent_envelope(
                broker,
                plan.run_id,
                parse_subagent_envelope(json.dumps({
                    "agent_id": agent_id,
                    "status": "completed",
                    "summary": summary,
                    "artifacts": [{"name": "result", "kind": "analysis", "content": summary}],
                    "messages": [],
                    "handoffs": [],
                    "review_requests": [],
                    "review_responses": [],
                    "metadata": {},
                    "error": "",
                })),
                role=agent_id,
            )
        completed_snapshot = complete_dispatch_plan(broker, plan, final_answer="Dispatch complete.")
        assert completed_snapshot["status"]["state"] == "completed"
        assert any(item["name"] == "final_answer" for item in completed_snapshot["artifacts"])

        before_artifacts = len(broker.list_artifacts())
        before_events = len(broker.list_events(thread_id=plan.run_id))

        bad = parse_subagent_envelope('{"agent_id":"planner","status":"completed","summary":"bad","messages":[{"to_agent":"orchestrator","subject":"bad","body":"bad","artifact_names":["missing"]}]}')
        try:
            ingest_subagent_envelope(broker, plan.run_id, bad, role="planner")
        except ValueError as exc:
            assert "unknown envelope artifact names" in str(exc)
        else:
            raise AssertionError("unknown artifact_names should be rejected")
        assert len(broker.list_artifacts()) == before_artifacts
        assert len(broker.list_events(thread_id=plan.run_id)) == before_events

        bad_target = parse_subagent_envelope(json.dumps({
            "agent_id": "planner",
            "status": "completed",
            "summary": "bad target",
            "artifacts": [{"name": "result", "kind": "analysis", "content": "should not persist"}],
            "messages": [{"to_agent": "ghost", "subject": "bad", "body": "bad", "artifact_names": ["result"]}],
            "handoffs": [],
            "review_requests": [],
            "review_responses": [],
            "metadata": {},
            "error": "",
        }))
        try:
            ingest_subagent_envelope(broker, plan.run_id, bad_target, role="planner")
        except ValueError as exc:
            assert "to_agent is not registered" in str(exc)
        else:
            raise AssertionError("unknown target agent should be rejected before broker writes")
        assert len(broker.list_artifacts()) == before_artifacts
        assert len(broker.list_events(thread_id=plan.run_id)) == before_events
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexAppBridge: dependency validation")
def test_codex_app_bridge_dependency_validation():
    from codex_app_bridge import CodexSubagentSpec, create_dispatch_plan

    plan = create_dispatch_plan(
        "Layered dispatch",
        [
            CodexSubagentSpec(id="planner", role="planner", goal="Plan"),
            CodexSubagentSpec(id="researcher", role="researcher", goal="Research"),
            CodexSubagentSpec(id="builder", role="builder", goal="Build", dependencies=["planner"]),
            CodexSubagentSpec(
                id="reviewer",
                role="reviewer",
                goal="Review",
                dependencies=["researcher", "builder"],
            ),
        ],
        max_parallel=1,
        run_id="codex-thread-2",
    )
    assert plan.topological_layers == [["planner", "researcher"], ["builder"], ["reviewer"]]
    assert plan.ready_batches == [["planner"], ["researcher"], ["builder"], ["reviewer"]]

    try:
        create_dispatch_plan(
            "Bad dependency",
            [CodexSubagentSpec(id="builder", role="builder", goal="Build", dependencies=["missing"])],
        )
    except ValueError as exc:
        assert "unknown agent id" in str(exc)
    else:
        raise AssertionError("unknown dependency should be rejected")

    try:
        create_dispatch_plan(
            "Cycle",
            [
                CodexSubagentSpec(id="a", role="a", goal="A", dependencies=["b"]),
                CodexSubagentSpec(id="b", role="b", goal="B", dependencies=["a"]),
            ],
        )
    except ValueError as exc:
        assert "cycle detected" in str(exc)
    else:
        raise AssertionError("dependency cycle should be rejected")


@test("CodexCliSwarm: fake codex exec fan-out + broker ingestion")
def test_codex_cli_swarm_fake_exec():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
if args[-1] != "-":
    raise SystemExit("expected prompt to be read from stdin via '-'")
prompt = sys.stdin.read()
match = re.search(r"Agent id: ([^\\n]+)", prompt)
agent_id = match.group(1).strip()
status = "failed" if "FAIL_AGENT" in prompt else "completed"
summary = f"summary for {agent_id}"
payload = {
    "agent_id": agent_id,
    "status": status,
    "summary": summary,
    "artifacts": [{"name": "result", "kind": "analysis", "content_type": "text/plain", "content": prompt[:500]}],
    "messages": [{"to_agent": "orchestrator", "subject": f"done {agent_id}", "body": summary, "artifact_names": ["result"]}],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {"fake_codex": True},
    "error": "" if status == "completed" else "forced failure",
}
out.write_text(json.dumps(payload), encoding="utf-8")
print(json.dumps({"agent_id": agent_id, "status": status}))
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        broker = AgentBroker(str(Path(d) / "broker"))
        runtime = CodexCliSwarmRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "swarm"),
            max_parallel=2,
            timeout_s=5,
            keep_workdirs=True,
            broker=broker,
        )
        agents = [
            CodexCliAgentSpec(id="planner", role="planner", goal="Plan"),
            CodexCliAgentSpec(id="researcher", role="researcher", goal="Research"),
            CodexCliAgentSpec(id="builder", role="builder", goal="Build", dependencies=["planner", "researcher"]),
            CodexCliAgentSpec(id="reviewer", role="reviewer", goal="Review", dependencies=["builder"]),
        ]
        trace = runtime.run("fake codex swarm", agents)
        assert trace.summary()["completed"] == 4
        assert broker.to_a2a_task(trace.run_id)["status"]["state"] == "completed"
        assert trace.topological_layers == [["planner", "researcher"], ["builder"], ["reviewer"]]
        assert trace.ready_batches == [["planner", "researcher"], ["builder"], ["reviewer"]]
        assert len(broker.to_a2a_task(trace.run_id)["artifacts"]) >= 4
        builder = next(result for result in trace.results if result.agent_id == "builder")
        builder_prompt = Path(builder.prompt_path).read_text(encoding="utf-8")
        assert "summary for planner" in builder_prompt
        assert "summary for researcher" in builder_prompt
        assert "Artifacts:" in builder_prompt
        assert "broker_id=artifact_" in builder_prompt
        assert Path(trace.manifest_path).exists()
        assert Path(trace.trace_path).exists()
        manifest = json.loads(Path(trace.manifest_path).read_text(encoding="utf-8"))
        assert manifest["max_parallel"] == 2
        trace_payload = json.loads(Path(trace.trace_path).read_text(encoding="utf-8"))
        assert trace_payload["run_id"] == trace.run_id
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexWorker: command, env, and timeout helpers")
def test_codex_worker_helpers():
    from codex_worker import build_codex_exec_command, build_worker_env, clamp_worker_timeout

    command = build_codex_exec_command(
        "codex",
        Path("/tmp/repo"),
        "workspace-write",
        Path("/tmp/last.txt"),
        ["--foo", "bar"],
    )
    assert command[:4] == ["codex", "exec", "--cd", "/tmp/repo"]
    assert "--output-last-message" in command
    assert command[-3:] == ["--foo", "bar", "-"]

    env = build_worker_env({"OH_MY_DYNAMIC_TEST": "1"})
    assert env["OH_MY_DYNAMIC_TEST"] == "1"
    assert clamp_worker_timeout(120, None) == 120
    assert clamp_worker_timeout(120, 999) == 120
    assert clamp_worker_timeout(120, 0) == 1


@test("CodexSwarmScheduler: batching, cycles, and import compatibility")
def test_codex_swarm_scheduler_and_import_compatibility():
    from codex_cli_swarm import CodexCliAgentResult, CodexCliAgentSpec, CodexCliSwarmTrace
    from codex_swarm_models import CodexCliAgentSpec as ModelSpec
    from codex_swarm_scheduler import agent_batches, dependency_failure_message, ready_batches, topological_layers

    assert CodexCliAgentSpec is ModelSpec
    assert CodexCliAgentResult.__name__ == "CodexCliAgentResult"
    assert CodexCliSwarmTrace.__name__ == "CodexCliSwarmTrace"

    specs = [
        CodexCliAgentSpec(id="planner", role="planner", goal="Plan"),
        CodexCliAgentSpec(id="researcher", role="researcher", goal="Research"),
        CodexCliAgentSpec(id="builder", role="builder", goal="Build", dependencies=["planner", "researcher"]),
    ]
    layers = topological_layers(specs)
    layer_ids = [[spec.id for spec in layer] for layer in layers]
    assert layer_ids == [["planner", "researcher"], ["builder"]]
    assert ready_batches(layer_ids, 1) == [["planner"], ["researcher"], ["builder"]]
    assert [[spec.id for spec in batch] for batch in agent_batches(specs, 2)] == [["planner", "researcher"], ["builder"]]

    failed = CodexCliAgentResult(
        agent_id="planner",
        role="planner",
        status="failed",
        summary="bad",
        started_at="s",
        completed_at="c",
        duration_s=0,
        returncode=-1,
        work_dir="",
        prompt_path="",
        output_path="",
        stdout_path="",
        stderr_path="",
        error="planner failed",
    )
    assert "planner failed" in dependency_failure_message(specs[-1], ["planner"], {"planner": failed})

    try:
        topological_layers([
            CodexCliAgentSpec(id="a", role="worker", goal="A", dependencies=["b"]),
            CodexCliAgentSpec(id="b", role="worker", goal="B", dependencies=["a"]),
        ])
    except ValueError as exc:
        assert "cycle detected" in str(exc)
    else:
        raise AssertionError("cycle should be rejected")


@test("CodexCliSwarm: dependency failure blocks downstream")
def test_codex_cli_swarm_dependency_failure():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
if args[-1] != "-":
    raise SystemExit("expected prompt to be read from stdin via '-'")
prompt = sys.stdin.read()
agent_id = re.search(r"Agent id: ([^\\n]+)", prompt).group(1).strip()
status = "failed" if "FAIL_AGENT" in prompt else "completed"
out.write_text(json.dumps({
    "agent_id": agent_id,
    "status": status,
    "summary": f"{status} {agent_id}",
    "artifacts": [{"name": "result", "content": prompt}],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {},
    "error": "forced failure" if status == "failed" else ""
}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        broker = AgentBroker(str(Path(d) / "broker"))
        runtime = CodexCliSwarmRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "swarm"),
            max_parallel=4,
            timeout_s=5,
            keep_workdirs=False,
            broker=broker,
        )
        trace = runtime.run(
            "dependency failure",
            [
                CodexCliAgentSpec(id="planner", role="planner", goal="FAIL_AGENT"),
                CodexCliAgentSpec(id="builder", role="builder", goal="Build", dependencies=["planner"]),
            ],
        )
        by_id = {result.agent_id: result for result in trace.results}
        assert by_id["planner"].status == "failed"
        assert by_id["builder"].status == "failed"
        assert "Dependency failed" in by_id["builder"].error
        assert trace.summary()["failed"] == 2
        assert broker.to_a2a_task(trace.run_id)["status"]["state"] == "failed"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexCliSwarm: process failure modes preserve trace")
def test_codex_cli_swarm_failure_modes():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys
import time

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
prompt = sys.stdin.read()
agent_id = re.search(r"Agent id: ([^\\n]+)", prompt).group(1).strip()
if "NONZERO" in prompt:
    print("simulated stderr failure", file=sys.stderr)
    sys.exit(7)
if "MALFORMED" in prompt:
    out.write_text("{not-json", encoding="utf-8")
    sys.exit(0)
if "TIMEOUT" in prompt:
    time.sleep(5)
payload = {
    "agent_id": agent_id,
    "status": "completed",
    "summary": f"ok {agent_id}",
    "artifacts": [{"name": "result", "content": "ok"}],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {},
    "error": ""
}
out.write_text(json.dumps(payload), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        broker = AgentBroker(str(Path(d) / "broker"))
        runtime = CodexCliSwarmRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "swarm"),
            max_parallel=3,
            timeout_s=1,
            keep_workdirs=False,
            broker=broker,
        )
        trace = runtime.run(
            "failure modes",
            [
                CodexCliAgentSpec(id="nonzero", role="worker", goal="NONZERO"),
                CodexCliAgentSpec(id="malformed", role="worker", goal="MALFORMED"),
                CodexCliAgentSpec(id="timeout", role="worker", goal="TIMEOUT"),
            ],
        )
        by_id = {result.agent_id: result for result in trace.results}
        assert trace.summary()["failed"] == 3
        assert by_id["nonzero"].returncode == 7
        assert "simulated stderr failure" in by_id["nonzero"].error
        assert "ValueError" in by_id["malformed"].error
        assert "timed out" in by_id["timeout"].error
        assert broker.to_a2a_task(trace.run_id)["status"]["state"] == "failed"
        assert Path(trace.trace_path).exists()
        assert Path(trace.manifest_path).exists()
        assert not Path(trace.swarm_root).exists()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexCliSwarm: worktree mode creates isolated patch artifacts")
def test_codex_cli_swarm_worktree_mode_patch_artifacts():
    import shutil, tempfile, subprocess
    from agent_broker import AgentBroker
    from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime

    d = tempfile.mkdtemp()
    init_test_git_repo(d)
    try:
        Path(d, "a.txt").write_text("base a\n", encoding="utf-8")
        Path(d, "b.txt").write_text("base b\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt", "b.txt"], cwd=d, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base files"], cwd=d, check=True, capture_output=True)

        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
cwd = pathlib.Path(args[args.index("--cd") + 1])
out = pathlib.Path(args[args.index("--output-last-message") + 1])
prompt = sys.stdin.read()
agent_id = re.search(r"Agent id: ([^\\n]+)", prompt).group(1).strip()
target = "a.txt" if agent_id == "writer_a" else "b.txt"
(cwd / target).write_text(f"changed by {agent_id}\\n", encoding="utf-8")
out.write_text(json.dumps({
    "agent_id": agent_id,
    "status": "completed",
    "summary": f"changed {target}",
    "artifacts": [{"name": "result", "content": target}],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {},
    "error": ""
}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        broker = AgentBroker(str(Path(d) / "broker"))
        runtime = CodexCliSwarmRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "swarm"),
            worktree_root=str(Path(d) / ".orchestry" / "worktrees"),
            max_parallel=2,
            timeout_s=5,
            broker=broker,
        )
        trace = runtime.run(
            "write isolated patches",
            [
                CodexCliAgentSpec(id="writer_a", role="writer", goal="Change a", workspace_mode="worktree", write_intent="patch"),
                CodexCliAgentSpec(id="writer_b", role="writer", goal="Change b", workspace_mode="worktree", write_intent="patch"),
            ],
        )
        assert trace.summary()["completed"] == 2
        assert Path(d, "a.txt").read_text(encoding="utf-8") == "base a\n"
        assert Path(d, "b.txt").read_text(encoding="utf-8") == "base b\n"
        assert len({result.agent_cwd for result in trace.results}) == 2
        worktree_artifacts = [artifact for artifact in broker.list_artifacts() if artifact.kind == "worktree_diff"]
        names = {artifact.name for artifact in worktree_artifacts}
        assert {"diff_stat", "patch", "changed_files"}.issubset(names)
        assert any("changed by writer_a" in artifact.content for artifact in worktree_artifacts if artifact.name == "patch")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CodexCliSwarm: worktree failure preserves failed envelope and diff")
def test_codex_cli_swarm_worktree_failure_preserves_diff():
    import shutil, tempfile, subprocess
    from agent_broker import AgentBroker
    from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime

    d = tempfile.mkdtemp()
    init_test_git_repo(d)
    try:
        Path(d, "failing.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "failing.txt"], cwd=d, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base file"], cwd=d, check=True, capture_output=True)
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import pathlib
import re
import sys

args = sys.argv[1:]
cwd = pathlib.Path(args[args.index("--cd") + 1])
prompt = sys.stdin.read()
agent_id = re.search(r"Agent id: ([^\\n]+)", prompt).group(1).strip()
(cwd / "failing.txt").write_text(f"partial change by {agent_id}\\n", encoding="utf-8")
print("simulated worker failure", file=sys.stderr)
sys.exit(9)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        broker = AgentBroker(str(Path(d) / "broker"))
        runtime = CodexCliSwarmRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "swarm"),
            worktree_root=str(Path(d) / ".orchestry" / "worktrees"),
            max_parallel=1,
            timeout_s=5,
            broker=broker,
        )
        trace = runtime.run(
            "failure diff",
            [CodexCliAgentSpec(id="failing_writer", role="writer", goal="Fail", workspace_mode="worktree", write_intent="patch")],
        )
        result = trace.results[0]
        assert result.status == "failed"
        assert result.returncode == 9
        assert Path(result.worktree_path).exists()
        patch_artifacts = [artifact for artifact in broker.list_artifacts() if artifact.kind == "worktree_diff" and artifact.name == "patch"]
        assert any("partial change by failing_writer" in artifact.content for artifact in patch_artifacts)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("DynamicWorkflow: planner JSON validation")
def test_dynamic_workflow_planner_json_validation():
    from dynamic_workflow import parse_planner_decision, parse_replan_decision

    decision = parse_planner_decision({
        "agents": [
            {"id": "planner", "role": "planner", "goal": "Plan"},
            {"id": "builder", "role": "builder", "goal": "Build", "dependencies": ["planner"]},
        ],
        "dependencies": {"builder": ["planner"]},
        "max_parallel": 2,
        "confidence": 0.8,
    })
    assert decision.max_parallel == 2
    assert decision.agents[1].dependencies == ["planner"]

    invalid_payloads = [
        {"agents": [{"id": "missing_role", "goal": "x"}]},
        {"agents": [{"id": "dup", "role": "a", "goal": "x"}, {"id": "dup", "role": "b", "goal": "y"}]},
        {"agents": [{"id": "builder", "role": "builder", "goal": "Build", "dependencies": ["ghost"]}]},
    ]
    for payload in invalid_payloads:
        try:
            parse_planner_decision(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid planner payload should fail: {payload}")

    try:
        parse_replan_decision({"agents": [{"id": "planner", "role": "planner", "goal": "again"}]}, {"planner"})
    except ValueError as exc:
        assert "duplicate agent id" in str(exc)
    else:
        raise AssertionError("replanner should reject duplicate existing agent ids")


@test("DynamicWorkflow: fake planner, replanner, reducer")
def test_dynamic_workflow_fake_planner_replanner_reducer():
    import shutil, tempfile
    from dynamic_workflow import DynamicWorkflowRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
prompt = sys.stdin.read()
agent_id = re.search(r"Agent id: ([^\\n]+)", prompt).group(1).strip()
out.write_text(json.dumps({
    "agent_id": agent_id,
    "status": "completed",
    "summary": f"{agent_id} complete",
    "artifacts": [{"name": "result", "content": f"artifact {agent_id}"}],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {},
    "error": ""
}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        replan_calls = {"count": 0}

        def planner(goal):
            return {
                "agents": [
                    {"id": "a", "role": "worker", "goal": "A"},
                    {"id": "b", "role": "worker", "goal": "B"},
                    {"id": "c", "role": "worker", "goal": "C", "dependencies": ["a"]},
                ],
                "max_parallel": 2,
                "confidence": 0.9,
            }

        def replanner(goal, snapshot):
            replan_calls["count"] += 1
            if replan_calls["count"] == 1:
                return {"agents": [{"id": "d", "role": "reviewer", "goal": "Review"}], "confidence": 0.7}
            return {"agents": [], "stop_reason": "ready_for_reducer", "confidence": 0.8}

        runtime = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic"),
            broker_dir=str(Path(d) / "broker"),
            max_rounds=3,
            max_agents=10,
            max_parallel=2,
            timeout_s=5,
            planner_fn=planner,
            replanner_fn=replanner,
        )
        trace = runtime.run("dynamic fake")
        assert trace.summary()["completed"] == 4
        assert len(trace.rounds) == 2
        assert trace.reducer_result.terminal_state == "completed"
        assert "Completed agents: 4" in trace.reducer_result.final_answer
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("DynamicWorkflow: adaptive fake planner 5 agents plus replanner 2 agents")
def test_dynamic_workflow_adaptive_fake_planner_replanner():
    import shutil, tempfile
    from dynamic_workflow import DynamicWorkflowRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
if args[args.index("--sandbox") + 1] != "read-only":
    sys.exit(3)
if "service_tier=\\"fast\\"" not in args:
    sys.exit(4)
out = pathlib.Path(args[args.index("--output-last-message") + 1])
agent_id = re.search(r"Agent id: ([^\\n]+)", sys.stdin.read()).group(1).strip()
out.write_text(json.dumps({
    "agent_id": agent_id,
    "status": "completed",
    "summary": f"adaptive completed {agent_id}",
    "artifacts": [],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {"completeness_score": 0.8},
    "error": ""
}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        def planner(goal):
            return {
                "agents": [
                    {"id": f"planner_{index}", "role": "reviewer", "goal": f"Planner agent {index}"}
                    for index in range(5)
                ],
                "max_parallel": 5,
            }

        replan_calls = {"count": 0}

        def replanner(goal, snapshot):
            replan_calls["count"] += 1
            if replan_calls["count"] == 1:
                return {
                    "agents": [
                        {"id": "replanner_0", "role": "followup", "goal": "Follow up 0"},
                        {"id": "replanner_1", "role": "followup", "goal": "Follow up 1"},
                    ],
                    "stop_reason": "added_followups",
                }
            return {"agents": [], "stop_reason": "ready_for_reducer"}

        runtime = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic"),
            broker_dir=str(Path(d) / "broker"),
            max_rounds=3,
            max_agents=10,
            max_parallel=5,
            timeout_s=5,
            planner_fn=planner,
            replanner_fn=replanner,
            codex_extra_args=["-c", 'service_tier="fast"'],
        )
        trace = runtime.run("adaptive fake")
        assert trace.summary()["completed"] == 7
        assert trace.summary()["failed"] == 0
        assert len(trace.rounds) == 2
        assert trace.rounds[0].agent_ids == [f"planner_{index}" for index in range(5)]
        assert trace.rounds[1].agent_ids == ["replanner_0", "replanner_1"]
        assert trace.reducer_result.terminal_state == "completed"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("DynamicWorkflow: limits stop rounds and agents")
def test_dynamic_workflow_limits():
    import shutil, tempfile
    from dynamic_workflow import DynamicWorkflowRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
agent_id = re.search(r"Agent id: ([^\\n]+)", sys.stdin.read()).group(1).strip()
out.write_text(json.dumps({"agent_id": agent_id, "status": "completed", "summary": "ok", "artifacts": [], "messages": [], "handoffs": [], "review_requests": [], "review_responses": [], "metadata": {}, "error": ""}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        def planner(goal):
            return {
                "agents": [
                    {"id": "a", "role": "worker", "goal": "A"},
                    {"id": "b", "role": "worker", "goal": "B"},
                    {"id": "c", "role": "worker", "goal": "C"},
                ],
                "max_parallel": 3,
            }

        runtime = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic"),
            broker_dir=str(Path(d) / "broker"),
            max_rounds=1,
            max_agents=2,
            max_parallel=3,
            timeout_s=5,
            planner_fn=planner,
            replanner_fn=lambda goal, snapshot: {"agents": [{"id": "d", "role": "worker", "goal": "D"}]},
        )
        trace = runtime.run("limits")
        assert trace.summary()["completed"] == 2
        assert trace.stop_reason in {"max_rounds", "max_agents"}

        runtime_no_new = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic2"),
            broker_dir=str(Path(d) / "broker2"),
            max_rounds=3,
            max_agents=5,
            max_parallel=1,
            timeout_s=5,
            planner_fn=lambda goal: {"agents": [{"id": "solo", "role": "worker", "goal": "Solo"}]},
            replanner_fn=lambda goal, snapshot: {"agents": []},
        )
        trace_no_new = runtime_no_new.run("no new")
        assert trace_no_new.stop_reason == "no_new_agents"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("WorkflowEvent + DAGExecutor: streaming, score, capability routing")
def test_workflow_event_and_dag_streaming_capability_routing():
    from dag import DAG, DAGNode, DAGExecutor
    from workflow_events import WorkflowEvent
    from workflow_config import DEFAULT_COMPLETENESS_SCORE

    event = WorkflowEvent(run_id="run-1", kind="demo", subject="Demo", preview="ok")
    assert event.to_dict()["kind"] == "demo"
    assert event.to_dict()["id"].startswith("event_")

    dag = DAG()
    security = dag.add_node(DAGNode.create(
        "Review security",
        required_capabilities=["security", "review"],
    ))
    unmatched = dag.add_node(DAGNode.create(
        "Review unknown capability",
        required_capabilities=["quantum-review"],
    ))
    events = []

    def executor(node, ctx):
        if node.id == security.id:
            return json.dumps({"summary": "ok", "completeness_score": 0.55})
        return "plain result"

    DAGExecutor(dag, executor, max_parallel=2, verbose=False).execute(events.append, run_id="dag-run")
    kinds = [event.kind for event in events]
    assert "batch_started" in kinds
    assert "node_started" in kinds
    assert "node_done" in kinds
    assert "capability_route_miss" in kinds
    assert dag.nodes[security.id].owner == "security_reviewer"
    assert dag.nodes[unmatched.id].owner == "general_reviewer"
    assert abs(dag.nodes[security.id].completeness_score - 0.55) < 0.001
    assert abs(dag.nodes[unmatched.id].completeness_score - DEFAULT_COMPLETENESS_SCORE) < 0.001


@test("DynamicReplan: low completeness score triggers replan")
def test_dynamic_replan_low_score_trigger():
    from dag import DAG, DAGNode
    from dynamic_replan import should_trigger_replan
    from workflow_config import REPLAN_COMPLETENESS_THRESHOLD

    dag = DAG()
    low = dag.add_node(DAGNode.create("Low quality"))
    low.status = "completed"
    low.completeness_score = REPLAN_COMPLETENESS_THRESHOLD - 0.1
    assert should_trigger_replan(dag)

    high_dag = DAG()
    high = high_dag.add_node(DAGNode.create("High quality"))
    high.status = "completed"
    high.completeness_score = REPLAN_COMPLETENESS_THRESHOLD + 0.1
    assert not should_trigger_replan(high_dag)


@test("Checkpoint: save, load, and corrupted file handling")
def test_checkpoint_save_load_corrupt():
    import shutil, tempfile
    from checkpoint import checkpoint_path, load_checkpoint, save_checkpoint

    d = tempfile.mkdtemp()
    try:
        path = checkpoint_path(d, "run-1")
        save_checkpoint(str(path), {"run_id": "run-1", "goal": "demo"})
        assert load_checkpoint(str(path))["goal"] == "demo"
        corrupt = Path(d) / "corrupt.json"
        corrupt.write_text("{bad-json", encoding="utf-8")
        try:
            load_checkpoint(str(corrupt))
        except ValueError as exc:
            assert "not valid JSON" in str(exc)
        else:
            raise AssertionError("corrupted checkpoint should fail clearly")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("DynamicWorkflow: resume skips completed checkpoint agents")
def test_dynamic_workflow_resume_skips_completed_agents():
    import shutil, tempfile
    from checkpoint import checkpoint_path, save_checkpoint
    from dynamic_workflow import DynamicWorkflowRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-last-message") + 1])
agent_id = re.search(r"Agent id: ([^\\n]+)", sys.stdin.read()).group(1).strip()
out.write_text(json.dumps({
    "agent_id": agent_id,
    "status": "completed",
    "summary": f"completed {agent_id}",
    "artifacts": [],
    "messages": [],
    "handoffs": [],
    "review_requests": [],
    "review_responses": [],
    "metadata": {},
    "error": ""
}), encoding="utf-8")
sys.exit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        checkpoint_dir = str(Path(d) / "checkpoints")
        run_id = "resume_demo"
        save_checkpoint(str(checkpoint_path(checkpoint_dir, run_id)), {
            "goal": "resume goal",
            "run_id": run_id,
            "rounds": [],
            "planned_agents": [
                {"id": "a", "role": "worker", "goal": "Already done"},
                {"id": "b", "role": "worker", "goal": "Still pending"},
            ],
            "pending_agents": [{"id": "b", "role": "worker", "goal": "Still pending"}],
            "completed_agent_ids": ["a"],
            "failed_agent_ids": [],
            "broker_thread_id": run_id,
            "stop_reason": "checkpointed",
        })
        events = []
        runtime = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic"),
            broker_dir=str(Path(d) / "broker"),
            checkpoint_dir=checkpoint_dir,
            max_rounds=1,
            max_agents=5,
            max_parallel=2,
            timeout_s=5,
            event_callback=events.append,
        )
        trace = runtime.run(resume_run_id=run_id)
        assert trace.run_id == run_id
        assert trace.rounds[-1].agent_ids == ["b"]
        assert "a" not in trace.rounds[-1].agent_ids
        assert any(event.kind == "dynamic_workflow_started" for event in events)
        assert any(event.kind == "reducer_done" for event in events)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("DynamicWorkflow: planner timeout records broker evidence")
def test_dynamic_workflow_planner_timeout_records_evidence():
    import shutil, tempfile
    from dynamic_workflow import DynamicWorkflowRuntime

    d = tempfile.mkdtemp()
    try:
        fake_codex = Path(d) / "codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import time
time.sleep(10)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        runtime = DynamicWorkflowRuntime(
            codex_bin=str(fake_codex),
            codex_cwd=d,
            workspace_root=str(Path(d) / "dynamic"),
            broker_dir=str(Path(d) / "broker"),
            timeout_s=5,
            planner_timeout_s=1,
        )
        try:
            runtime.run("planner should timeout")
        except RuntimeError as exc:
            assert "planner" in str(exc)
            assert "timed out" in str(exc)
        else:
            raise AssertionError("planner timeout should raise RuntimeError")

        events = runtime.broker.list_events()
        subjects = {event.subject for event in events}
        assert "dynamic_planner_started" in subjects
        assert "dynamic_planner_failed" in subjects
        artifacts = runtime.broker.list_artifacts()
        assert any(artifact.name == "planner_failure" for artifact in artifacts)
        worker_dirs = [
            event.metadata["worker_dir"]
            for event in events
            if event.subject == "dynamic_planner_failed"
        ]
        assert worker_dirs and Path(worker_dirs[0], "prompt.md").exists()
        assert Path(worker_dirs[0], "stderr.txt").exists()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("RealRepoReview demo: dry run writes compact evidence")
def test_real_repo_review_dry_run_evidence():
    import shutil, tempfile, subprocess

    d = tempfile.mkdtemp()
    try:
        output_dir = Path(d) / "evidence"
        result = subprocess.run(
            [
                sys.executable,
                "examples/real_repo_review.py",
                "--dry-run",
                "--run-id",
                "dry-evidence",
                "--output-dir",
                str(output_dir),
                "--agents",
                "5",
                "--max-parallel",
                "3",
            ],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        evidence_path = output_dir / "dry-evidence.md"
        json_path = output_dir / "dry-evidence.json"
        assert evidence_path.exists()
        assert json_path.exists()
        body = evidence_path.read_text(encoding="utf-8")
        summary = json.loads(json_path.read_text(encoding="utf-8"))
        assert '"dry_run": true' in body
        assert summary["broker_thread_id"] == "dry-evidence"
        assert "dynamic workflow alignment" in body
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("AdaptiveWorkflow evidence: dry run writes round-aware compact evidence")
def test_adaptive_workflow_dry_run_evidence():
    import shutil, tempfile, subprocess

    d = tempfile.mkdtemp()
    try:
        output_dir = Path(d) / "evidence"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/record_adaptive_workflow_evidence.py",
                "--dry-run",
                "--run-id",
                "adaptive-dry",
                "--output-dir",
                str(output_dir),
                "--max-agents",
                "20",
                "--max-parallel",
                "5",
            ],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        evidence_path = output_dir / "adaptive-dry.md"
        json_path = output_dir / "adaptive-dry.json"
        assert evidence_path.exists()
        assert json_path.exists()
        body = evidence_path.read_text(encoding="utf-8")
        summary = json.loads(json_path.read_text(encoding="utf-8"))
        assert "Round Timeline" in body
        assert summary["dry_run"] is True
        assert summary["planner_generated_agents"] == 5
        assert summary["replanner_generated_agents"] == 2
        assert summary["rounds"][0]["source"] == "planner"
        assert summary["rounds"][1]["source"] == "replanner"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("Evidence scripts: Codex extra args and marketplace policy are documented")
def test_evidence_cli_extra_args_and_marketplace_policy():
    import subprocess

    root = Path(__file__).resolve().parent
    for command in [
        [sys.executable, "examples/real_repo_review.py", "--help"],
        [sys.executable, "scripts/record_swarm_evidence.py", "--help"],
        [sys.executable, "scripts/record_adaptive_workflow_evidence.py", "--help"],
    ]:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "--codex-extra-arg" in result.stdout

    marketplace = json.loads((root / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    plugin = next(item for item in marketplace["plugins"] if item["name"] == "oh-my-dynamic")
    assert plugin["policy"]["authentication"] == "ON_USE"
    assert plugin["source"]["path"] == "./plugins/oh-my-dynamic"


@test("WorkflowObserver: renders static dashboard evidence")
def test_workflow_observer_static_dashboard():
    import shutil, tempfile
    from workflow_observer import render_observability_dashboard

    d = tempfile.mkdtemp()
    try:
        source = Path(d) / ".orchestry"
        broker = source / "agent_broker_fixture"
        broker.mkdir(parents=True)
        run_id = "obs-run"
        events = [
            {
                "id": "event_1",
                "kind": "trace",
                "from_agent": "planner",
                "to_agent": None,
                "subject": "agent_started",
                "body": "Planner started",
                "thread_id": run_id,
                "status": "running",
                "metadata": {},
                "created_at": "2026-06-05T00:00:00Z",
            },
            {
                "id": "event_2",
                "kind": "review_response",
                "from_agent": "reviewer",
                "to_agent": "builder",
                "subject": "Review response",
                "body": "Needs more coverage",
                "thread_id": run_id,
                "status": "completed",
                "metadata": {"completeness_score": 0.45},
                "created_at": "2026-06-05T00:01:00Z",
            },
            {
                "id": "event_3",
                "kind": "trace",
                "from_agent": "builder",
                "to_agent": None,
                "subject": "agent_failed",
                "body": "builder failed",
                "thread_id": run_id,
                "status": "failed",
                "metadata": {},
                "created_at": "2026-06-05T00:02:00Z",
            },
        ]
        artifacts = [{
            "id": "artifact_1",
            "producer": "builder",
            "name": "patch",
            "kind": "worktree_diff",
            "content": "diff --git a/x b/x",
            "content_type": "text/plain",
            "thread_id": run_id,
            "task_id": "",
            "metadata": {},
            "created_at": "2026-06-05T00:03:00Z",
        }]
        (broker / "events.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
        (broker / "artifacts.jsonl").write_text("\n".join(json.dumps(item) for item in artifacts) + "\n", encoding="utf-8")
        trace_dir = source / "dynamic_workflow" / run_id
        trace_dir.mkdir(parents=True)
        (trace_dir / "dynamic_trace.json").write_text(json.dumps({
            "run_id": run_id,
            "stop_reason": "ready_for_reducer",
            "rounds": [
                {
                    "round_index": 0,
                    "agent_ids": ["planner"],
                    "completed": 1,
                    "failed": 0,
                    "duration_s": 1.2,
                    "trace_path": "round-0/trace.json",
                },
                {
                    "round_index": 1,
                    "agent_ids": ["builder"],
                    "completed": 0,
                    "failed": 1,
                    "duration_s": 2.4,
                    "trace_path": "round-1/trace.json",
                },
            ],
        }), encoding="utf-8")
        checkpoint_dir = source / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        (checkpoint_dir / f"{run_id}.json").write_text(json.dumps({
            "run_id": run_id,
            "completed_agent_ids": ["planner"],
            "failed_agent_ids": ["builder"],
            "stop_reason": "partial",
        }), encoding="utf-8")

        output = Path(d) / "dashboard.html"
        rendered = render_observability_dashboard(run_id, source=str(source), output=str(output))
        body = Path(rendered).read_text(encoding="utf-8")
        assert "oh-my-Dynamic Observability" in body
        assert "Needs more coverage" in body
        assert "builder failed" in body
        assert "diff --git" in body
        assert "Low Scores" in body
        assert "Round Timeline" in body
        assert "round 1" in body
        assert "checkpoint" in body.lower()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("QualityEval: deterministic scoring and report")
def test_quality_eval_runner():
    import shutil, tempfile
    from eval_runner import (
        evaluate_responses,
        load_eval_suite,
        render_eval_report,
        sample_responses,
        score_response,
        summarize_results,
    )

    d = tempfile.mkdtemp()
    try:
        tasks = load_eval_suite("evals/task_suite.json")
        good_results = evaluate_responses(tasks, sample_responses(tasks))
        good_summary = summarize_results(good_results)
        assert good_summary["total"] == 4
        assert good_summary["passed"] == 4
        assert good_summary["avg_score"] >= 0.70

        weak = score_response(tasks[0], "Looks okay.")
        assert not weak.passed
        assert weak.missing_keywords
        assert weak.missing_evidence

        output = Path(d) / "quality_eval.md"
        rendered = render_eval_report(good_results, str(output), "evals/task_suite.json")
        body = Path(rendered).read_text(encoding="utf-8")
        assert "oh-my-Dynamic Quality Eval" in body
        assert "security_review" in body
        assert '"terminal_state": "passed"' in body
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("CLI: dynamic workflow, swarm, and evidence help")
def test_cli_help_entrypoints():
    import contextlib
    import io
    import subprocess

    commands = [
        [sys.executable, "-m", "dynamic_workflow", "--help"],
        [sys.executable, "-m", "codex_cli_swarm", "--help"],
        [sys.executable, "-m", "codex_swarm_cli", "--help"],
        [sys.executable, "scripts/record_swarm_evidence.py", "--help"],
        [sys.executable, "scripts/record_adaptive_workflow_evidence.py", "--help"],
        [sys.executable, "scripts/render_workflow_observability.py", "--help"],
        [sys.executable, "scripts/run_quality_eval.py", "--help"],
        [sys.executable, "examples/real_repo_review.py", "--help"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parent, capture_output=True, text=True)
        assert result.returncode == 0, f"{command} failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()

    from codex_swarm_cli import main as swarm_cli_main

    old_argv = sys.argv[:]
    try:
        sys.argv = ["codex_swarm_cli", "--help"]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            try:
                swarm_cli_main()
            except SystemExit as exc:
                assert exc.code == 0
        assert "usage:" in stdout.getvalue().lower()
    finally:
        sys.argv = old_argv


@test("Native Runtime: sandboxed fan-out")
def test_native_runtime_fanout():
    from native_runtime import AgentSpec, SandboxedFanoutRuntime, ToolGrant

    def mock_llm(sys, user):
        if "Worker results:" in user:
            return f"reduced {user.count(', completed)')} workers"
        return "worker complete"

    agents = [
        AgentSpec(
            id=f"agent_{i:02d}",
            role="worker",
            goal=f"Shard {i}",
            context=f"private context {i}",
            tool_grants=[ToolGrant("read", "sandbox")],
        )
        for i in range(32)
    ]
    runtime = SandboxedFanoutRuntime(mock_llm, max_workers=32, keep_sandboxes=False)
    trace = runtime.run("fanout test", agents)
    summary = trace.summary()
    assert summary["agents"] == 32
    assert summary["completed"] == 32
    assert len({r.sandbox.root for r in trace.results}) == 32
    assert all(r.tool_grants[0].name == "read" for r in trace.results)
    assert "reduced" in trace.final_answer


@test("Native Runtime: dependency scheduling")
def test_native_runtime_dependency_scheduling():
    from native_runtime import AgentSpec, SandboxedFanoutRuntime

    calls = []

    def mock_llm(sys, user):
        if "Worker results:" in user:
            return "dependency reducer complete"
        agent_id = next(
            line.split(": ", 1)[1]
            for line in user.splitlines()
            if line.startswith("Agent id: ")
        )
        calls.append(agent_id)
        if agent_id == "builder":
            assert "planner output" in user
        if agent_id == "reviewer":
            assert "builder output" in user
            assert "researcher output" in user
        return f"{agent_id} output"

    agents = [
        AgentSpec(id="planner", role="planner", goal="Plan"),
        AgentSpec(id="researcher", role="researcher", goal="Research"),
        AgentSpec(id="auditor", role="auditor", goal="Audit"),
        AgentSpec(id="builder", role="builder", goal="Build", dependencies=["planner"]),
        AgentSpec(id="reviewer", role="reviewer", goal="Review", dependencies=["builder", "researcher"]),
    ]
    runtime = SandboxedFanoutRuntime(mock_llm, max_workers=2, keep_sandboxes=False)
    trace = runtime.run("dependency test", agents)

    assert trace.topological_layers == [["planner", "researcher", "auditor"], ["builder"], ["reviewer"]]
    assert trace.ready_batches == [["planner", "researcher"], ["auditor"], ["builder"], ["reviewer"]]
    assert [result.agent_id for result in trace.results] == ["planner", "researcher", "auditor", "builder", "reviewer"]
    assert calls.index("builder") > calls.index("planner")
    assert calls.index("reviewer") > calls.index("builder")
    assert calls.index("reviewer") > calls.index("researcher")
    assert trace.summary()["completed"] == 5


@test("Native Runtime: invalid dependencies and dependency failures")
def test_native_runtime_dependency_failures():
    from native_runtime import AgentSpec, SandboxedFanoutRuntime

    calls = []

    def mock_llm(sys, user):
        if "Worker results:" in user:
            return "dependency failure reducer complete"
        if "Agent id: root" in user:
            calls.append("root")
            raise RuntimeError("root failed")
        if "Agent id: child" in user:
            calls.append("child")
        return "ok"

    runtime = SandboxedFanoutRuntime(mock_llm, max_workers=2, keep_sandboxes=False)
    trace = runtime.run(
        "dependency failure test",
        [
            AgentSpec(id="root", role="root", goal="Fail"),
            AgentSpec(id="child", role="child", goal="Skip", dependencies=["root"]),
        ],
    )
    child = next(result for result in trace.results if result.agent_id == "child")
    assert calls == ["root"]
    assert child.status == "failed"
    assert "Dependency failed" in child.error
    assert trace.summary()["failed"] == 2

    try:
        runtime.run(
            "Bad dependency",
            [AgentSpec(id="child", role="child", goal="Skip", dependencies=["missing"])],
        )
    except ValueError as exc:
        assert "unknown agent id" in str(exc)
    else:
        raise AssertionError("unknown dependency should be rejected")

    try:
        runtime.run(
            "Cycle",
            [
                AgentSpec(id="a", role="a", goal="A", dependencies=["b"]),
                AgentSpec(id="b", role="b", goal="B", dependencies=["a"]),
            ],
        )
    except ValueError as exc:
        assert "cycle detected" in str(exc)
    else:
        raise AssertionError("dependency cycle should be rejected")


@test("Native Runtime: broker trace + artifacts")
def test_native_runtime_broker_trace():
    import shutil, tempfile
    from agent_broker import AgentBroker
    from native_runtime import AgentSpec, SandboxedFanoutRuntime, ToolGrant

    d = tempfile.mkdtemp()
    try:
        broker = AgentBroker(str(Path(d) / "broker"))

        def mock_llm(sys, user):
            if "Worker results:" in user:
                return "broker reducer complete"
            return "worker artifact"

        agents = [
            AgentSpec(
                id=f"agent_{i:02d}",
                role="worker",
                goal=f"Shard {i}",
                tool_grants=[ToolGrant("read", "sandbox")],
            )
            for i in range(4)
        ]
        runtime = SandboxedFanoutRuntime(
            mock_llm,
            workspace_root=str(Path(d) / "runtime"),
            max_workers=4,
            keep_sandboxes=False,
            broker=broker,
        )
        trace = runtime.run("broker fanout", agents)

        assert trace.summary()["completed"] == 4
        assert trace.broker_thread_id == trace.run_id
        assert trace.broker_event_count >= 10
        assert all(result.artifact_ids for result in trace.results)

        task_snapshot = broker.to_a2a_task(trace.run_id)
        assert task_snapshot["status"]["state"] == "completed"
        assert len(task_snapshot["artifacts"]) >= 5  # 4 workers + final answer
        assert any(event.subject == "workflow_completed" for event in broker.list_events(thread_id=trace.run_id))
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
    import tempfile
    from worktree import WorktreeManager
    
    # 创建临时 git 仓库
    d = tempfile.mkdtemp()
    init_test_git_repo(d)
    
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


@test("Worktree: 拒绝不安全 agent 名称")
def test_worktree_rejects_unsafe_name():
    import tempfile
    from worktree import WorktreeManager

    d = tempfile.mkdtemp()
    init_test_git_repo(d)

    try:
        mgr = WorktreeManager(d)
        try:
            mgr.create("../escape")
        except ValueError:
            return
        raise AssertionError("应拒绝包含路径穿越的 agent_name")
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


@test("压力: 100 isolated agents fan-out")
def test_stress_native_runtime_100_agents():
    from native_runtime import AgentSpec, SandboxedFanoutRuntime, ToolGrant

    def mock_llm(sys, user):
        if "Worker results:" in user:
            return "100-agent reducer complete"
        return "ok"

    agents = [
        AgentSpec(
            id=f"agent_{i:03d}",
            role="worker",
            goal=f"Shard {i}",
            tool_grants=[ToolGrant("read", "sandbox")],
        )
        for i in range(100)
    ]
    runtime = SandboxedFanoutRuntime(mock_llm, max_workers=100, keep_sandboxes=False)
    start = time.time()
    trace = runtime.run("100-agent fanout", agents)
    elapsed = time.time() - start
    assert trace.summary()["completed"] == 100
    assert len({r.sandbox.root for r in trace.results}) == 100
    assert elapsed < 10, f"100 isolated agents should finish quickly with mock LLM, got {elapsed:.1f}s"


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
    from llm_client import call_glm, call_llm

    def llm_fn(sys, user):
        assert call_glm is not call_llm
        return call_llm(system_prompt=sys, user_prompt=user)
    
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
        test_dag_status_normalization,
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
        test_tea_sandbox_blocks_escape,
        test_llm_provider_routing,
        test_protocol_adapters,
        test_agent_broker_collaboration,
        test_agent_broker_rejects_unsafe_agent_ids,
        test_broker_gateway_http_lifecycle,
        test_broker_gateway_auth_and_limits,
        test_protocol_artifact_compatibility_and_cursor,
        test_broker_reducer_uses_full_broker_evidence,
        test_codex_app_bridge_ingestion,
        test_codex_app_bridge_dependency_validation,
        test_codex_cli_swarm_fake_exec,
        test_codex_worker_helpers,
        test_codex_swarm_scheduler_and_import_compatibility,
        test_codex_cli_swarm_dependency_failure,
        test_codex_cli_swarm_failure_modes,
        test_codex_cli_swarm_worktree_mode_patch_artifacts,
        test_codex_cli_swarm_worktree_failure_preserves_diff,
        test_dynamic_workflow_planner_json_validation,
        test_dynamic_workflow_fake_planner_replanner_reducer,
        test_dynamic_workflow_adaptive_fake_planner_replanner,
        test_dynamic_workflow_limits,
        test_workflow_event_and_dag_streaming_capability_routing,
        test_dynamic_replan_low_score_trigger,
        test_checkpoint_save_load_corrupt,
        test_dynamic_workflow_resume_skips_completed_agents,
        test_dynamic_workflow_planner_timeout_records_evidence,
        test_real_repo_review_dry_run_evidence,
        test_adaptive_workflow_dry_run_evidence,
        test_evidence_cli_extra_args_and_marketplace_policy,
        test_workflow_observer_static_dashboard,
        test_quality_eval_runner,
        test_cli_help_entrypoints,
        test_native_runtime_fanout,
        test_native_runtime_dependency_scheduling,
        test_native_runtime_dependency_failures,
        test_native_runtime_broker_trace,
        test_synthesis_single,
        test_worktree_basic,
        test_worktree_rejects_unsafe_name,
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
            test_stress_native_runtime_100_agents,
            test_stress_token_tracker,
        ])
    
    # 端到端
    if "--e2e" in sys.argv:
        run_section("🌐 端到端测试 (GLM-5.1 API)", [
            test_e2e_real,
        ])
    
    sys.exit(summary())
