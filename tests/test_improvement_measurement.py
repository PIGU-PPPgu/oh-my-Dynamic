from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module():
    path = ROOT / "scripts" / "measure_improvement.py"
    spec = importlib.util.spec_from_file_location("measure_improvement_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_improvement_measurement_has_concrete_lift(tmp_path):
    module = _load_module()
    output = tmp_path / "improvement.json"
    assert module.main(["--suite", str(ROOT / "benchmarks" / "repo_review.json"), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    summaries = payload["mode_summaries"]
    lift = payload["lift"]

    assert summaries["single"]["fixtures"] == summaries["fixed"]["fixtures"] == summaries["adaptive"]["fixtures"]
    assert summaries["fixed"]["avg_quality_score"] > summaries["single"]["avg_quality_score"]
    assert summaries["adaptive"]["avg_quality_score"] > summaries["fixed"]["avg_quality_score"]
    assert summaries["adaptive"]["missing_requirement_count"] == 0
    assert lift["adaptive_vs_single"]["quality_score_absolute_lift"] > 0.3
    assert lift["adaptive_vs_single"]["missing_requirement_reduction_pct"] == 100.0

    md = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "Quality Lift" in md
    assert "controlled deterministic scoring" in md


def test_improvement_response_does_not_leak_missing_terms_into_hits():
    module = _load_module()
    suite = module.BENCHMARK._load_suite(str(ROOT / "benchmarks" / "repo_review.json"))
    item = next(task for task in suite["tasks"] if task["id"] == "security_command_surface")

    row = module._row_for(item, "single")
    assert row["quality_score"] < item["minimum_score"]
    assert row["missing_requirement_count"] > 0
    assert "secret" in row["missing"]["keywords"]
    assert "secret" not in row["response_preview"].lower()
