from __future__ import annotations

from pathlib import Path
import json
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_llm_client_dispatch_and_retry_helpers(monkeypatch):
    from oh_my_dynamic.core import llm_client

    providers = {
        "zhipu/glm-5.1": ("zhipu", "ZHIPUAI_API_KEY"),
        "gpt-4o": ("openai", "OPENAI_API_KEY"),
        "claude-sonnet-4": ("anthropic", "ANTHROPIC_API_KEY"),
        "gemini-2.5-flash": ("google", "GOOGLE_API_KEY"),
        "openrouter/openai/gpt-5": ("openrouter", "OPENROUTER_API_KEY"),
        "deepseek-chat": ("deepseek", "DEEPSEEK_API_KEY"),
        "qwen-plus": ("qwen", "DASHSCOPE_API_KEY"),
        "moonshot-v1-8k": ("moonshot", "MOONSHOT_API_KEY"),
        "siliconflow/deepseek-ai/DeepSeek-V3": ("siliconflow", "SILICONFLOW_API_KEY"),
        "custom-model": ("openai_compatible", "OPENAI_API_KEY"),
    }
    for _, env_name in providers.values():
        monkeypatch.setenv(env_name, "test-key")

    calls = []

    def fake_call(name):
        def _inner(*args, **kwargs):
            calls.append((name, args))
            return f"{name}:ok"

        return _inner

    monkeypatch.setattr(llm_client, "_call_zhipu", fake_call("zhipu"))
    monkeypatch.setattr(llm_client, "_call_openai", fake_call("openai"))
    monkeypatch.setattr(llm_client, "_call_anthropic", fake_call("anthropic"))
    monkeypatch.setattr(llm_client, "_call_google", fake_call("google"))
    monkeypatch.setattr(llm_client, "_call_openrouter", fake_call("openrouter"))
    monkeypatch.setattr(llm_client, "_call_china_compatible", fake_call("china"))
    monkeypatch.setattr(llm_client, "_call_openai_compatible", fake_call("compatible"))

    assert llm_client._strip_provider_prefix("deepseek", "deepseek/deepseek-chat") == "deepseek-chat"
    assert llm_client._strip_provider_prefix("openai", "other/model") == "other/model"
    assert llm_client._compatible_base_url("deepseek").startswith("https://")
    assert llm_client._get_env_keys("unknown") == ("OPENAI_API_KEY",)

    for model, (provider, _) in providers.items():
        assert llm_client._detect_provider(model) == provider
        assert llm_client.call_llm("system", "user", model=model, max_retries=1, retry_delay=0).endswith(":ok")

    assert llm_client.call_glm("system", "user", model="glm-5.1", max_retries=1, retry_delay=0).endswith(":ok")
    assert llm_client.list_providers()["openai"]["env"] == "OPENAI_API_KEY"

    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    try:
        llm_client._get_api_key("zhipu")
    except ValueError as exc:
        assert "ZHIPUAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected missing key error")

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" retry ok "))]
    )
    assert llm_client._retry_call(lambda: response, max_retries=1, retry_delay=0) == "retry ok"
    assert llm_client._retry_fn(lambda: "plain ok", max_retries=1, retry_delay=0) == "plain ok"


def test_dynamic_replan_parse_apply_and_cycle(monkeypatch):
    from oh_my_dynamic.runtime.dag import DAG, DAGNode
    from oh_my_dynamic.runtime.dynamic_replan import (
        ResultPreservingReplanner,
        run_replan_cycle,
        should_trigger_replan,
    )
    from oh_my_dynamic.runtime.task import TaskStatus
    from oh_my_dynamic.runtime.token_tracker import TokenTracker

    dag = DAG()
    done = DAGNode.create(question="Audit security", agent_type="reviewer")
    done.status = TaskStatus.DONE
    done.result = "security risk found"
    done.completeness_score = 0.55
    pending = DAGNode.create(question="Audit docs", agent_type="builder")
    dag.add_node(done)
    dag.add_node(pending)

    calls = []

    def llm(system: str, user: str) -> str:
        calls.append((system, user))
        if "高级项目分析专家" in system:
            return "docs coverage gap"
        return json.dumps(
            {
                "keep_ids": [done.id],
                "drop_ids": [pending.id],
                "new_tasks": [
                    {
                        "question": "Review evidence redaction",
                        "agent_type": "unknown",
                        "dependencies": [done.id, "missing"],
                        "priority": 99,
                    }
                ],
                "modified_tasks": [{"id": done.id, "new_question": "Audit security deeply"}],
            }
        )

    tracker = TokenTracker()
    replanner = ResultPreservingReplanner(llm, token_tracker=tracker, verbose=False)
    assert should_trigger_replan(dag, current_iteration=0) is True
    result = run_replan_cycle(replanner, dag, "review repo", iteration=1)

    assert result is not None
    assert done.id in result.kept_node_ids
    assert pending.id in result.dropped_node_ids
    assert result.new_nodes[0].agent_type == "builder"
    assert result.new_nodes[0].dependencies == [done.id]
    assert result.new_nodes[0].priority == 5
    assert result.modified_nodes[0].question == "Audit security deeply"
    assert tracker.summary()["total"] > 0
    assert "新增" in result.summary()

    parser = ResultPreservingReplanner._parse_replan_response
    assert parser('```json\n{"keep_ids": []}\n```') == {"keep_ids": []}
    assert parser('prefix {"drop_ids": []} suffix') == {"drop_ids": []}
    assert parser("not json") is None

    no_gap = ResultPreservingReplanner(lambda _s, _u: "无差距", verbose=False)
    assert run_replan_cycle(no_gap, dag, "review repo", iteration=2) is None


def test_dynamic_workflow_repairs_replanner_task_type_aliases():
    from oh_my_dynamic.runtime.dynamic_workflow import parse_replan_decision

    decision = parse_replan_decision(
        {
            "agents": [
                {
                    "id": "followup_audit",
                    "type": "read_only_reviewer",
                    "lane": "benchmark_followup",
                    "task": "Audit benchmark follow-up evidence.",
                }
            ],
            "dependencies": {},
            "stop_reason": "followup_agents_added",
            "confidence": 0.8,
        },
        existing_agent_ids={"planner_agent"},
    )
    assert decision.agents[0].role == "benchmark_followup"
    assert decision.agents[0].goal == "Audit benchmark follow-up evidence."
    assert decision.stop_reason == "followup_agents_added"


def test_synthesis_grouping_single_and_hierarchical_paths():
    from oh_my_dynamic.runtime.synthesis import Synthesizer
    from oh_my_dynamic.runtime.token_tracker import TokenTracker

    calls = []

    def llm(system: str, user: str, model: str = "model") -> str:
        calls.append((system, user, model))
        if "Condense" in system:
            return "condensed group"
        return "integrated final answer"

    tracker = TokenTracker()
    synth = Synthesizer(llm, token_tracker=tracker)
    small = synth.synthesize(
        [{"agent_type": "security", "output": "risk finding"}],
        original_query="review",
    )
    assert small == "integrated final answer"

    large_results = [
        {"agent_type": "security", "output": "x" * 2000}
        for _ in range(12)
    ]
    large = synth.synthesize(large_results, max_group_size=5, original_query="review")
    assert large == "integrated final answer"
    groups = synth._group_results(large_results, max_group_size=5)
    assert set(groups) == {"security_part1", "security_part2", "security_part3"}
    assert tracker.summary()["total"] > 0

    two_arg = Synthesizer(lambda _s, _u: "two arg ok")
    assert two_arg.condense_group([{"category": "docs", "output": "install"}]) == "two arg ok"


def test_visualize_builds_dashboard_from_stats_and_nodes(tmp_path, monkeypatch):
    from oh_my_dynamic.core import visualize

    output = tmp_path / "dashboard.html"
    path = visualize.generate_dashboard(
        {
            "dag_stats": {"total": 2, "completed": 1},
            "iterations": 1,
            "token_summary": {"total_tokens": 12},
            "duration_s": 0.2,
            "stop_reason": "ready",
            "final_answer": "</script safe",
        },
        output_path=str(output),
    )
    html = Path(path).read_text(encoding="utf-8")
    assert "task_1" in html
    assert "<\\/script safe" in html

    opened = []
    monkeypatch.setattr(visualize.webbrowser, "open", lambda url: opened.append(url))
    visualize.open_dashboard(str(output))
    assert opened[0].startswith("file://")
