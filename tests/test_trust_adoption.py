from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_evidence_sanitizer_marks_and_redacts_repo_paths():
    from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload

    payload = sanitize_payload({"trace_path": f"{ROOT}/.orchestry/run/trace.json"}, root=str(ROOT))
    assert payload["sanitized"] is True
    assert payload["repo_root_label"] == "$REPO_ROOT"
    assert payload["trace_path"] == "$REPO_ROOT/.orchestry/run/trace.json"


def test_doctor_reports_gateway_auth_failure(tmp_path):
    from oh_my_dynamic.evals.doctor import run_doctor

    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins":[{"name":"oh-my-dynamic"}]}', encoding="utf-8")
    skill = tmp_path / "skill"
    skill.mkdir()
    args = argparse.Namespace(
        codex_bin="definitely-not-codex",
        cd=str(ROOT),
        marketplace_json=str(marketplace),
        skill_path=str(skill),
        orchestry_dir=str(tmp_path / ".orchestry"),
        gateway_host="0.0.0.0",
        gateway_token="",
        evidence_glob=str(tmp_path / "evidence" / "*"),
        strict_real_codex=False,
        codex_exec_timeout_s=1,
    )
    result = run_doctor(args)
    checks = {check["name"]: check for check in result["checks"]}
    assert result["status"] == "fail"
    assert checks["gateway_auth"]["status"] == "fail"
    assert result["ready_for_real_codex_cli"] is False


def test_benchmark_dry_run_writes_compact_json(tmp_path):
    output = tmp_path / "benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_benchmark.py",
            "--suite",
            "benchmarks/repo_review.json",
            "--mode",
            "single,fixed,adaptive",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["mode_summaries"]["adaptive"]["replanner_count"] >= 2
    assert payload["fixture_count"] >= 12
    first = payload["task_results"][0]
    assert "quality_score" in first
    assert "evidence_completeness" in first
    assert "risk_hits" in first


def test_v3_package_imports_match_compatibility_facades():
    from agent_broker import AgentBroker as OldBroker
    from codex_cli_swarm import CodexCliSwarmRuntime as OldSwarmRuntime
    from dynamic_workflow import DynamicWorkflowRuntime as OldDynamicRuntime

    from oh_my_dynamic.broker.agent_broker import AgentBroker
    from oh_my_dynamic.codex.codex_cli_swarm import CodexCliSwarmRuntime
    from oh_my_dynamic.runtime.dynamic_workflow import DynamicWorkflowRuntime

    assert AgentBroker is OldBroker
    assert CodexCliSwarmRuntime is OldSwarmRuntime
    assert DynamicWorkflowRuntime is OldDynamicRuntime
