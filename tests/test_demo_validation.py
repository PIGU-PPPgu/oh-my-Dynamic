from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _load_demo_module():
    path = ROOT / "scripts" / "run_demo_validation.py"
    spec = importlib.util.spec_from_file_location("run_demo_validation_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_demo_validation_reports_adaptive_lift(tmp_path):
    module = _load_demo_module()
    output = tmp_path / "demo_validation.json"

    assert module.main(["--output", str(output), "--run-id", "pytest_demo_validation"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["dry_run"] is True
    assert payload["scenario_count"] == 4
    assert payload["mode_summaries"]["single"]["missing_requirement_count"] > 0
    assert payload["mode_summaries"]["adaptive"]["missing_requirement_count"] == 0
    assert payload["mode_summaries"]["adaptive"]["replanner_generated_agents"] == 8
    assert payload["lift"]["adaptive_vs_single"]["missing_requirement_reduction_pct"] == 100.0
    assert payload["lift"]["adaptive_vs_single"]["quality_score_absolute_lift"] > 0.3
    assert "does not prove live model quality" in payload["claim_boundary"]

    md = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "Demo Validation v3.6" in md
    assert "Demo 验证 v3.6" in md
    assert "Frontend Build Demo" in md
    assert "Harness 工程 Demo" in md


def test_demo_validation_frontend_example_smoke(tmp_path):
    output = tmp_path / "frontend.json"
    result = subprocess.run(
        [
            sys.executable,
            "examples/frontend_build_demo.py",
            "--output",
            str(output),
            "--run-id",
            "pytest_frontend_demo",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scenarios"] == ["frontend_build"]
    assert payload["mode_summaries"]["adaptive"]["missing_requirement_count"] == 0


def test_demo_validation_harness_example_smoke(tmp_path):
    output = tmp_path / "harness.json"
    result = subprocess.run(
        [
            sys.executable,
            "examples/harness_engineering_demo.py",
            "--output",
            str(output),
            "--run-id",
            "pytest_harness_demo",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scenarios"] == ["harness_engineering"]
    assert payload["mode_summaries"]["fixed"]["avg_evidence_completeness"] > payload["mode_summaries"]["single"]["avg_evidence_completeness"]
