from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_benchmark_module():
    path = ROOT / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_v31", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v31_benchmark_defaults_real_to_fixed_fixtures_and_filters(tmp_path):
    benchmark = _load_benchmark_module()
    suite = benchmark._load_suite(str(ROOT / "benchmarks" / "repo_review.json"))

    assert benchmark._fixture_ids("", suite, real=True) == benchmark.V31_REAL_FIXTURES
    assert "security_command_surface" in benchmark._fixture_ids(
        "security_command_surface", suite, real=False
    )

    args = argparse.Namespace(
        real=False,
        cd=str(ROOT),
        run_id="pytest_v31",
        output=str(tmp_path / "benchmark.json"),
    )
    payload = benchmark._run_suite(
        args,
        suite,
        ["single", "fixed", "adaptive"],
        ["security_command_surface", "install_five_minute"],
    )
    assert payload["fixture_count"] == 2
    assert payload["mode_summaries"]["adaptive"]["replanner_count"] >= 2
    assert payload["mode_summaries"]["fixed"]["avg_evidence_completeness"] >= 0.9
    assert all("quality_score" in row for row in payload["task_results"])


def test_v31_benchmark_scoring_requires_more_than_keywords():
    benchmark = _load_benchmark_module()
    suite = benchmark._load_suite(str(ROOT / "benchmarks" / "repo_review.json"))
    item = next(task for task in suite["tasks"] if task["id"] == "evidence_redaction")
    row = {
        "agent_count": 1,
        "agents_completed": 1,
        "agents_failed": 0,
        "replanner_count": 0,
    }

    keyword_only = " ".join(item["expected_keywords"])
    weak = benchmark._score_response(item, "single", keyword_only, row)
    strong_text = benchmark._synthetic_response_for(item, "single")
    strong = benchmark._score_response(item, "single", strong_text, row)

    assert weak.quality_score < item["minimum_score"]
    assert strong.quality_score >= item["minimum_score"]
    assert strong.risk_hits
    assert strong.evidence_hits


def test_v31_benchmark_real_exception_becomes_failed_row(monkeypatch):
    benchmark = _load_benchmark_module()
    suite = benchmark._load_suite(str(ROOT / "benchmarks" / "repo_review.json"))
    item = next(task for task in suite["tasks"] if task["id"] == "security_command_surface")

    def fail_swarm(*_args, **_kwargs):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(benchmark, "_run_real_swarm", fail_swarm)
    args = argparse.Namespace(real=True, sandbox="read-only", codex_extra_arg=[])
    row = benchmark._run_real_task(args, item, "single", "pytest-run")

    assert row["terminal_state"] == "failed"
    assert row["agents_failed"] == 1
    assert row["passed"] is False
    assert "worker exploded" in row["error"]


def test_evidence_sanitizer_recursive_file_and_sensitive_hits(tmp_path):
    from oh_my_dynamic.evals.evidence_sanitizer import (
        dumps_public_json,
        sanitize_file,
        sanitize_payload,
        sanitize_value,
        sensitive_hits,
    )

    raw_file = tmp_path / "evidence.md"
    raw_file.write_text(
        f"path={ROOT}/.orchestry/run token='sk-abcdefghijklmnopqrstuvwxyz'\n",
        encoding="utf-8",
    )
    assert sensitive_hits(str(raw_file))
    sanitize_file(str(raw_file), root=str(ROOT))
    body = raw_file.read_text(encoding="utf-8")
    assert "$REPO_ROOT/.orchestry/run" in body
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in body
    assert "$REDACTED_VALUE" in body

    payload = sanitize_payload(
        {"nested": (f"{ROOT}/docs", [f"{Path.home()}/secret"])},
        root=str(ROOT),
    )
    assert payload["nested"][0] == "$REPO_ROOT/docs"
    assert payload["nested"][1][0].startswith("$HOME")
    assert '"sanitized": true' in dumps_public_json({"path": str(ROOT)}, root=str(ROOT))
    assert isinstance(sanitize_value(("a", "b"), root=str(ROOT)), list)


def test_doctor_reports_marketplace_git_evidence_and_loopback_states(tmp_path):
    from oh_my_dynamic.evals.doctor import run_doctor

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "bad.json").write_text(
        '{"path": "/Users/someone/private", "api_key": "sk-abcdefghijklmnopqrstuvwxyz"}',
        encoding="utf-8",
    )
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text("{not-json", encoding="utf-8")
    skill = tmp_path / "skill"

    args = argparse.Namespace(
        codex_bin="definitely-not-codex",
        cd=str(tmp_path),
        marketplace_json=str(marketplace),
        skill_path=str(skill),
        orchestry_dir=str(tmp_path / ".orchestry"),
        gateway_host="127.0.0.1",
        gateway_token="",
        evidence_glob=str(evidence_dir / "*"),
    )
    result = run_doctor(args)
    checks = {check["name"]: check for check in result["checks"]}

    assert result["status"] == "fail"
    assert checks["codex_cli"]["status"] == "warn"
    assert checks["git_repo"]["status"] == "fail"
    assert checks["marketplace_json"]["status"] == "fail"
    assert checks["skill_link"]["status"] == "warn"
    assert checks["gateway_auth"]["status"] == "pass"
    assert checks["evidence_redaction"]["status"] == "fail"


def test_workflow_observer_renders_rounds_triggers_and_checkpoint(tmp_path):
    from oh_my_dynamic.evals.workflow_observer import collect_observability_data, render_observability_dashboard

    run_id = "pytest-observer"
    broker_dir = tmp_path / "agent_broker" / run_id
    broker_dir.mkdir(parents=True)
    (broker_dir / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "thread_id": run_id,
                        "kind": "node_failed",
                        "subject": "agent failed",
                        "from_agent": "worker-a",
                        "metadata": {"completeness_score": 0.2},
                    }
                ),
                "{not-json",
            ]
        ),
        encoding="utf-8",
    )
    (broker_dir / "artifacts.jsonl").write_text(
        json.dumps(
            {
                "thread_id": run_id,
                "name": "summary",
                "kind": "markdown",
                "producer": "worker-a",
                "content": "Needs more coverage",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "completed_agent_ids": ["a"],
                "failed_agent_ids": ["b"],
                "stop_reason": "ready_for_reducer",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "dynamic_trace.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "rounds": [
                    {"round_index": 0, "agent_ids": ["a"], "completed": 1, "failed": 0},
                    {"round_index": 1, "agent_ids": ["b"], "completed": 0, "failed": 1},
                ],
                "replan_trigger_records": [
                    {
                        "round_index": 0,
                        "replan_triggers": [{"kind": "missing_coverage", "lanes": ["docs"]}],
                        "missing_coverage": ["docs"],
                        "low_score_agents": ["worker-a"],
                        "followup_agent_budget": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    data = collect_observability_data(run_id, tmp_path)
    assert data["summary"]["failed_count"] == 1
    assert data["summary"]["low_score_count"] == 1
    assert data["summary"]["artifact_count"] == 1
    assert data["summary"]["workflow_round_count"] == 2

    output = tmp_path / "dashboard.html"
    rendered = render_observability_dashboard(run_id, source=str(tmp_path), output=str(output))
    html = Path(rendered).read_text(encoding="utf-8")
    assert "Round Timeline" in html
    assert "missing_coverage" in html
    assert "Needs more coverage" in html


def test_package_cli_entrypoints_import_and_parse_help():
    modules = [
        "oh_my_dynamic.cli.dynamic_workflow",
        "oh_my_dynamic.cli.codex_swarm",
        "oh_my_dynamic.cli.doctor",
        "oh_my_dynamic.cli.quality_eval",
        "oh_my_dynamic.cli.gateway",
    ]
    for name in modules:
        module = __import__(name, fromlist=["main"])
        assert callable(module.main)
