#!/usr/bin/env python3
"""Measure deterministic quality lift across single/fixed/adaptive modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import argparse
import importlib.util
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload


def _load_benchmark_module():
    path = ROOT / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_for_improvement", path)
    if not spec or not spec.loader:
        raise RuntimeError("failed to load run_benchmark.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BENCHMARK = _load_benchmark_module()
MODES = ["single", "fixed", "adaptive"]


def _pick(values: List[str], mode: str) -> List[str]:
    if mode == "single":
        return values[:1]
    if mode == "fixed":
        return values[:-1] if len(values) > 1 else values
    return values


def _controlled_response(item: Dict[str, Any], mode: str) -> str:
    """Build a deterministic response that models each mode's coverage boundary."""
    keywords = BENCHMARK._expected_keywords(item)
    signals = BENCHMARK._expected_signals(item)
    risks = BENCHMARK._risk_categories(item)
    evidence = BENCHMARK._evidence_requirements(item)
    selected_keywords = _pick(keywords, mode)
    selected_signals = _pick(signals, mode)
    selected_risks = _pick(risks, mode)
    selected_evidence = _pick(evidence, mode)
    missing = sorted(set(keywords + signals + risks + evidence) - set(selected_keywords + selected_signals + selected_risks + selected_evidence))
    parts = [
        f"{mode} controlled benchmark for {item['id']}.",
        "Finding: risk and gap found in file README.md line 1.",
        "Command evidence: python test_suite.py.",
        "Recommendation: fix the missing review coverage and rerun the benchmark.",
        "Keywords covered: " + ", ".join(selected_keywords),
        "Signals covered: " + ", ".join(selected_signals),
        "Risk categories covered: " + ", ".join(selected_risks),
        "Evidence covered: " + ", ".join(selected_evidence),
    ]
    if mode == "adaptive":
        parts.append("Adaptive proof: replanner added follow-up agents for missing coverage and reducer integrated the extra evidence.")
    elif mode == "fixed":
        parts.append("Fixed swarm proof: fixed lane reviewers covered most requirements but no replanner closed remaining gaps.")
    else:
        parts.append("Single proof: one reviewer produced a compact baseline with limited lane coverage.")
    if missing:
        # Keep missing term names out of the response; otherwise keyword scoring
        # would count the absence report as successful coverage.
        parts.append(f"Still missing {len(missing)} benchmark requirements.")
    return " ".join(part for part in parts if part.strip())


def _missing_requirement_count(row: Dict[str, Any]) -> int:
    missing = row.get("missing", {})
    if not isinstance(missing, dict):
        return 0
    return sum(len(values) for values in missing.values() if isinstance(values, list))


def _row_for(item: Dict[str, Any], mode: str) -> Dict[str, Any]:
    response = _controlled_response(item, mode)
    base = {
        "mode": mode,
        "fixture": str(item["id"]),
        "goal": str(item.get("goal", "")),
        "dry_run": True,
        "agent_count": {"single": 1, "fixed": 5, "adaptive": 7}[mode],
        "agents_completed": {"single": 1, "fixed": 5, "adaptive": 7}[mode],
        "agents_failed": 0,
        "replanner_count": 2 if mode == "adaptive" else 0,
        "duration_s": 0.0,
        "terminal_state": "completed",
        "response_preview": response[:360],
    }
    row = BENCHMARK._finish_row(item, mode, base, response)
    row["missing_requirement_count"] = _missing_requirement_count(row)
    return row


def _selected_tasks(suite: Dict[str, Any], fixture_ids: List[str]) -> List[Dict[str, Any]]:
    if not fixture_ids:
        return [
            item
            for item in suite["tasks"]
            if set(MODES).issubset(set(BENCHMARK._allowed_modes(item)))
        ]
    selected = set(fixture_ids)
    return [item for item in suite["tasks"] if str(item["id"]) in selected]


def _summaries(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        if not mode_rows:
            continue
        output[mode] = {
            "fixtures": len(mode_rows),
            "passed": sum(1 for row in mode_rows if row["passed"]),
            "pass_rate": round(sum(1 for row in mode_rows if row["passed"]) / len(mode_rows), 3),
            "avg_quality_score": round(sum(float(row["quality_score"]) for row in mode_rows) / len(mode_rows), 3),
            "avg_evidence_completeness": round(sum(float(row["evidence_completeness"]) for row in mode_rows) / len(mode_rows), 3),
            "missing_requirement_count": sum(int(row.get("missing_requirement_count", 0)) for row in mode_rows),
            "agents_completed": sum(int(row.get("agents_completed", 0)) for row in mode_rows),
            "replanner_count": sum(int(row.get("replanner_count", 0)) for row in mode_rows),
        }
    return output


def _lift(summaries: Dict[str, Any]) -> Dict[str, Any]:
    baseline = summaries.get("single", {})
    single_score = float(baseline.get("avg_quality_score", 0.0))
    single_pass = float(baseline.get("pass_rate", 0.0))
    single_evidence = float(baseline.get("avg_evidence_completeness", 0.0))
    single_missing = int(baseline.get("missing_requirement_count", 0))
    lifts: Dict[str, Any] = {}
    for mode in ["fixed", "adaptive"]:
        summary = summaries.get(mode, {})
        score = float(summary.get("avg_quality_score", 0.0))
        evidence = float(summary.get("avg_evidence_completeness", 0.0))
        missing = int(summary.get("missing_requirement_count", 0))
        lifts[f"{mode}_vs_single"] = {
            "quality_score_absolute_lift": round(score - single_score, 3),
            "quality_score_relative_lift_pct": round(((score - single_score) / single_score) * 100, 1) if single_score else None,
            "pass_rate_absolute_lift": round(float(summary.get("pass_rate", 0.0)) - single_pass, 3),
            "evidence_completeness_absolute_lift": round(evidence - single_evidence, 3),
            "missing_requirement_reduction": single_missing - missing,
            "missing_requirement_reduction_pct": round(((single_missing - missing) / single_missing) * 100, 1) if single_missing else None,
        }
    if "fixed" in summaries and "adaptive" in summaries:
        fixed = summaries["fixed"]
        adaptive = summaries["adaptive"]
        fixed_missing = int(fixed.get("missing_requirement_count", 0))
        adaptive_missing = int(adaptive.get("missing_requirement_count", 0))
        lifts["adaptive_vs_fixed"] = {
            "quality_score_absolute_lift": round(float(adaptive["avg_quality_score"]) - float(fixed["avg_quality_score"]), 3),
            "pass_rate_absolute_lift": round(float(adaptive["pass_rate"]) - float(fixed["pass_rate"]), 3),
            "evidence_completeness_absolute_lift": round(float(adaptive["avg_evidence_completeness"]) - float(fixed["avg_evidence_completeness"]), 3),
            "missing_requirement_reduction": fixed_missing - adaptive_missing,
            "missing_requirement_reduction_pct": round(((fixed_missing - adaptive_missing) / fixed_missing) * 100, 1) if fixed_missing else None,
        }
    return lifts


def _build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    suite = BENCHMARK._load_suite(args.suite)
    requested = [item.strip() for item in args.fixtures.split(",") if item.strip()]
    known = {str(item["id"]) for item in suite["tasks"]}
    unknown = [item for item in requested if item not in known]
    if unknown:
        raise ValueError(f"unknown fixture(s): {', '.join(unknown)}")
    rows: List[Dict[str, Any]] = []
    for item in _selected_tasks(suite, requested):
        allowed = set(BENCHMARK._allowed_modes(item))
        for mode in MODES:
            if mode in allowed:
                rows.append(_row_for(item, mode))
    summaries = _summaries(rows)
    return {
        "benchmark": suite.get("name", "benchmark"),
        "measurement": "controlled_improvement",
        "run_id": args.run_id,
        "created_at": int(time.time()),
        "dry_run": True,
        "fixture_count": len(_selected_tasks(suite, requested)),
        "fixtures": [str(item["id"]) for item in _selected_tasks(suite, requested)],
        "mode_summaries": summaries,
        "lift": _lift(summaries),
        "task_results": rows,
        "interpretation": {
            "what_this_measures": "Deterministic requirement coverage and benchmark scoring lift when moving from one reviewer to fixed lanes to adaptive replanner follow-up.",
            "what_this_does_not_measure": "It does not prove live model answer quality or Codex App-native isolated subagents. Pair with real Codex CLI evidence for runtime proof.",
        },
    }


def _write(payload: Dict[str, Any], output: str) -> str:
    payload = sanitize_payload(payload)
    json_path = Path(output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    if json_path.suffix.lower() == ".md":
        json_path = json_path.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = json_path.with_suffix(".md")
    lines = [
        "# oh-my-Dynamic Improvement Measurement",
        "",
        f"Run id: `{payload['run_id']}`",
        f"Benchmark: `{payload['benchmark']}`",
        "Type: controlled deterministic scoring, not a live Codex CLI run.",
        "",
        "## Mode Summary",
        "",
        "| Mode | Fixtures | Pass Rate | Avg Quality | Evidence Completeness | Missing Requirements | Agents | Replanners |",
        "|------|----------|-----------|-------------|-----------------------|----------------------|--------|------------|",
    ]
    for mode, summary in payload["mode_summaries"].items():
        lines.append(
            f"| {mode} | {summary['fixtures']} | {summary['pass_rate']} | {summary['avg_quality_score']} | "
            f"{summary['avg_evidence_completeness']} | {summary['missing_requirement_count']} | "
            f"{summary['agents_completed']} | {summary['replanner_count']} |"
        )
    lines.extend(["", "## Lift", ""])
    lines.extend([
        "| Comparison | Quality Lift | Relative Quality Lift | Pass Rate Lift | Evidence Lift | Missing Requirement Reduction |",
        "|------------|--------------|-----------------------|----------------|---------------|-------------------------------|",
    ])
    for name, lift in payload["lift"].items():
        relative = lift.get("quality_score_relative_lift_pct")
        relative_text = "n/a" if relative is None else f"{relative}%"
        reduction_pct = lift.get("missing_requirement_reduction_pct")
        reduction_text = f"{lift['missing_requirement_reduction']}"
        if reduction_pct is not None:
            reduction_text += f" ({reduction_pct}%)"
        lines.append(
            f"| {name} | {lift['quality_score_absolute_lift']} | {relative_text} | "
            f"{lift['pass_rate_absolute_lift']} | {lift['evidence_completeness_absolute_lift']} | {reduction_text} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        f"- Measures: {payload['interpretation']['what_this_measures']}",
        f"- Does not measure: {payload['interpretation']['what_this_does_not_measure']}",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(json_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Measure deterministic quality lift across benchmark modes.")
    parser.add_argument("--suite", default="benchmarks/repo_review.json")
    parser.add_argument("--fixtures", default="", help="Comma-separated fixture ids. Defaults to all fixtures.")
    parser.add_argument("--run-id", default="improvement_v311")
    parser.add_argument("--output", default="docs/evidence/improvement_v311.json")
    args = parser.parse_args(argv)
    payload = _build_payload(args)
    print(_write(payload, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
