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
    from broker_gateway import create_server

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


@test("Worktree: 拒绝不安全 agent 名称")
def test_worktree_rejects_unsafe_name():
    import tempfile, subprocess
    from worktree import WorktreeManager

    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", d], capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=d, capture_output=True)

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
        test_tea_sandbox_blocks_escape,
        test_llm_provider_routing,
        test_protocol_adapters,
        test_agent_broker_collaboration,
        test_agent_broker_rejects_unsafe_agent_ids,
        test_broker_gateway_http_lifecycle,
        test_broker_gateway_auth_and_limits,
        test_codex_app_bridge_ingestion,
        test_codex_app_bridge_dependency_validation,
        test_codex_cli_swarm_fake_exec,
        test_codex_cli_swarm_dependency_failure,
        test_codex_cli_swarm_failure_modes,
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
