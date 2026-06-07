#!/usr/bin/env python3
"""Generate deterministic demo validation evidence for oh-my-Dynamic.

The demo model compares single-agent, fixed-swarm, and adaptive workflow
coverage for concrete adoption scenarios. It is intentionally deterministic:
it proves measurement shape and workflow-coverage claims, not live model
quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import argparse
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload


MODES = ("single", "fixed", "adaptive")


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    title: str
    zh_title: str
    goal: str
    requirements: List[str]
    coverage_lanes: List[str]
    expected_artifacts: List[str]
    live_guardrail: str


SCENARIOS: Dict[str, DemoScenario] = {
    "frontend_build": DemoScenario(
        scenario_id="frontend_build",
        title="Frontend Build Demo",
        zh_title="前端建设 Demo",
        goal="Add a dashboard/report page to a small React/Vite app and validate it before handoff.",
        requirements=[
            "layout",
            "state",
            "data-contract",
            "accessibility",
            "responsive",
            "visual-regression",
            "tests",
            "docs",
        ],
        coverage_lanes=[
            "ui-layout",
            "state-data",
            "a11y",
            "responsive-review",
            "visual-review",
            "test-authoring",
            "docs-handoff",
            "replanner-gap-fix",
        ],
        expected_artifacts=[
            "implementation plan",
            "component checklist",
            "a11y findings",
            "responsive findings",
            "test plan",
            "handoff notes",
        ],
        live_guardrail="This measures workflow coverage for frontend construction, not visual taste or model creativity.",
    ),
    "harness_engineering": DemoScenario(
        scenario_id="harness_engineering",
        title="Harness Engineering Demo",
        zh_title="Harness 工程 Demo",
        goal="Design an evaluation harness with fixtures, scoring, redaction, CI gates, and evidence reports.",
        requirements=[
            "fixtures",
            "scoring-rubric",
            "redaction",
            "ci-gate",
            "dry-run",
            "real-run-boundary",
            "evidence-schema",
            "failure-preservation",
        ],
        coverage_lanes=[
            "fixture-designer",
            "rubric-reviewer",
            "redaction-reviewer",
            "ci-integrator",
            "evidence-writer",
            "failure-triage",
            "replanner-gap-fix",
        ],
        expected_artifacts=[
            "fixture matrix",
            "scoring rubric",
            "redaction checklist",
            "CI command list",
            "compact evidence JSON",
            "known limitations",
        ],
        live_guardrail="This measures harness completeness and reproducibility, not benchmark generality.",
    ),
    "repo_productization": DemoScenario(
        scenario_id="repo_productization",
        title="Repo Productization Demo",
        zh_title="项目产品化 Demo",
        goal="Turn a research prototype into an externally adoptable repository.",
        requirements=[
            "install",
            "doctor",
            "quickstart",
            "known-limits",
            "tests",
            "coverage",
            "release-checklist",
            "evidence",
        ],
        coverage_lanes=[
            "install-review",
            "doctor-review",
            "docs-review",
            "test-review",
            "release-review",
            "evidence-review",
            "replanner-gap-fix",
        ],
        expected_artifacts=[
            "doctor output",
            "quickstart commands",
            "release checklist",
            "coverage gate",
            "public evidence",
        ],
        live_guardrail="This measures adoption readiness, not package popularity.",
    ),
    "security_trust": DemoScenario(
        scenario_id="security_trust",
        title="Security / Trust Demo",
        zh_title="安全与可信 Demo",
        goal="Review command surface, broker artifacts, gateway auth, evidence redaction, and raw-output boundaries.",
        requirements=[
            "command-surface",
            "gateway-auth",
            "artifact-poisoning",
            "secret-redaction",
            "path-redaction",
            "raw-output-boundary",
            "threat-model",
            "bandit",
        ],
        coverage_lanes=[
            "command-review",
            "gateway-review",
            "artifact-review",
            "redaction-review",
            "threat-model-review",
            "bandit-review",
            "replanner-gap-fix",
        ],
        expected_artifacts=[
            "threat model mapping",
            "bandit result",
            "doctor result",
            "redaction scan",
            "risk summary",
        ],
        live_guardrail="This measures review coverage and evidence discipline, not a formal security audit.",
    ),
}


MODE_PROFILES: Dict[str, Dict[str, Any]] = {
    "single": {
        "agent_count": 1,
        "replanner_generated_agents": 0,
        "coverage_ratio": 0.42,
        "evidence_completeness": 0.48,
        "quality_score": 0.56,
        "test_success_ratio": 0.55,
        "worker_duration_s": [46.0],
        "wall_clock_duration_s": 46.0,
        "artifact_ratio": 0.50,
    },
    "fixed": {
        "agent_count": 5,
        "replanner_generated_agents": 0,
        "coverage_ratio": 0.76,
        "evidence_completeness": 0.78,
        "quality_score": 0.74,
        "test_success_ratio": 0.78,
        "worker_duration_s": [28.0, 24.0, 22.0, 18.0, 16.0],
        "wall_clock_duration_s": 31.0,
        "artifact_ratio": 0.78,
    },
    "adaptive": {
        "agent_count": 7,
        "replanner_generated_agents": 2,
        "coverage_ratio": 1.0,
        "evidence_completeness": 0.94,
        "quality_score": 0.88,
        "test_success_ratio": 0.92,
        "worker_duration_s": [24.0, 21.0, 19.0, 17.0, 14.0, 13.0, 11.0],
        "wall_clock_duration_s": 34.0,
        "artifact_ratio": 1.0,
    },
}


def _commit_sha(cwd: str) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _scenario_ids(value: str) -> List[str]:
    if not value.strip():
        return list(SCENARIOS)
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in requested if item not in SCENARIOS]
    if unknown:
        raise ValueError(f"unknown scenario(s): {', '.join(unknown)}")
    return requested


def _modes(value: str) -> List[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in requested if item not in MODES]
    if unknown:
        raise ValueError(f"unknown mode(s): {', '.join(unknown)}")
    return requested or list(MODES)


def _pick(items: List[str], ratio: float) -> List[str]:
    count = max(1, min(len(items), round(len(items) * ratio)))
    return items[:count]


def _row_for(scenario: DemoScenario, mode: str) -> Dict[str, Any]:
    profile = MODE_PROFILES[mode]
    coverage_hit = _pick(scenario.coverage_lanes, float(profile["coverage_ratio"]))
    requirements_hit = _pick(scenario.requirements, float(profile["coverage_ratio"]))
    artifacts_hit = _pick(scenario.expected_artifacts, float(profile["artifact_ratio"]))
    worker_duration = [float(value) for value in profile["worker_duration_s"]]
    wall_clock = float(profile["wall_clock_duration_s"])
    missing_requirements = [item for item in scenario.requirements if item not in requirements_hit]
    return {
        "scenario": scenario.scenario_id,
        "mode": mode,
        "goal": scenario.goal,
        "agent_count": int(profile["agent_count"]),
        "agents_completed": int(profile["agent_count"]),
        "agents_failed": 0,
        "replanner_generated_agents": int(profile["replanner_generated_agents"]),
        "coverage_lanes_hit": coverage_hit,
        "coverage_lane_count": len(scenario.coverage_lanes),
        "requirements_hit": requirements_hit,
        "missing_requirements": missing_requirements,
        "missing_requirement_count": len(missing_requirements),
        "expected_artifacts_hit": artifacts_hit,
        "quality_score": float(profile["quality_score"]),
        "evidence_completeness": float(profile["evidence_completeness"]),
        "test_success_ratio": float(profile["test_success_ratio"]),
        "wall_clock_duration_s": wall_clock,
        "sum_worker_duration_s": round(sum(worker_duration), 2),
        "parallel_speedup_estimate": round(sum(worker_duration) / wall_clock, 2),
        "terminal_state": "completed" if not missing_requirements else "partial",
        "interpretation": _interpretation(mode, scenario, missing_requirements),
    }


def _interpretation(mode: str, scenario: DemoScenario, missing: List[str]) -> str:
    if mode == "single":
        return (
            f"Single baseline covers the first-pass path for {scenario.scenario_id}, "
            f"but leaves {len(missing)} requirement(s) without explicit evidence."
        )
    if mode == "fixed":
        return (
            f"Fixed swarm increases specialist coverage for {scenario.scenario_id}, "
            f"but cannot create follow-up agents for {', '.join(missing) or 'new gaps'}."
        )
    return (
        f"Adaptive workflow closes the planned coverage lanes for {scenario.scenario_id} "
        "by adding replanner-generated follow-up agents."
    )


def _summaries(rows: List[Dict[str, Any]], modes: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        mode_rows = [row for row in rows if row["mode"] == mode]
        if not mode_rows:
            continue
        summary[mode] = {
            "scenarios": len(mode_rows),
            "avg_quality_score": round(sum(row["quality_score"] for row in mode_rows) / len(mode_rows), 3),
            "avg_evidence_completeness": round(sum(row["evidence_completeness"] for row in mode_rows) / len(mode_rows), 3),
            "avg_parallel_speedup_estimate": round(sum(row["parallel_speedup_estimate"] for row in mode_rows) / len(mode_rows), 3),
            "missing_requirement_count": sum(int(row["missing_requirement_count"]) for row in mode_rows),
            "agent_count": sum(int(row["agent_count"]) for row in mode_rows),
            "replanner_generated_agents": sum(int(row["replanner_generated_agents"]) for row in mode_rows),
            "terminal_state": "completed" if all(row["terminal_state"] == "completed" for row in mode_rows) else "partial",
        }
    return summary


def _lift(summary: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    single = summary.get("single", {})
    output: Dict[str, Dict[str, float]] = {}
    for mode in ("fixed", "adaptive"):
        current = summary.get(mode)
        if not current or not single:
            continue
        missing_single = max(float(single.get("missing_requirement_count", 0)), 1.0)
        output[f"{mode}_vs_single"] = {
            "quality_score_absolute_lift": round(float(current["avg_quality_score"]) - float(single["avg_quality_score"]), 3),
            "evidence_completeness_absolute_lift": round(
                float(current["avg_evidence_completeness"]) - float(single["avg_evidence_completeness"]),
                3,
            ),
            "missing_requirement_reduction_pct": round(
                (float(single["missing_requirement_count"]) - float(current["missing_requirement_count"]))
                / missing_single
                * 100,
                1,
            ),
            "parallel_speedup_lift": round(
                float(current["avg_parallel_speedup_estimate"]) - float(single["avg_parallel_speedup_estimate"]),
                3,
            ),
        }
    return output


def _build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    scenario_ids = _scenario_ids(args.scenarios)
    modes = _modes(args.mode)
    rows = [_row_for(SCENARIOS[scenario_id], mode) for scenario_id in scenario_ids for mode in modes]
    summary = _summaries(rows, modes)
    return {
        "report": "demo_validation_v360",
        "run_id": args.run_id,
        "created_at": int(time.time()),
        "commit_sha": _commit_sha(args.cd),
        "dry_run": True,
        "scenario_count": len(scenario_ids),
        "scenarios": scenario_ids,
        "modes": modes,
        "mode_summaries": summary,
        "lift": _lift(summary),
        "rows": rows,
        "claim_boundary": (
            "This deterministic demo measures workflow coverage, evidence completeness, "
            "parallel review throughput, and gap-driven replanning. It does not prove live model quality."
        ),
        "claim_boundary_zh": (
            "这个确定性 demo 衡量的是任务覆盖、证据完整度、并行审查吞吐和基于缺口的重规划；"
            "它不证明真实模型质量提升。"
        ),
        "known_limitations": [
            "Deterministic dry-run evidence; no Codex CLI workers are launched.",
            "Numbers are scenario fixtures for external explanation, not a live benchmark.",
            "Pair this report with real Codex CLI evidence before making runtime claims.",
        ],
        "known_limitations_zh": [
            "这是确定性 dry-run 证据，不启动 Codex CLI workers。",
            "数值用于场景化解释，不是真实 benchmark。",
            "涉及 runtime claim 时，应同时引用真实 Codex CLI evidence。",
        ],
    }


def _write_report(payload: Dict[str, Any], output: str) -> str:
    payload = sanitize_payload(payload, root=str(ROOT))
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_path.with_suffix(".json") if out_path.suffix.lower() == ".md" else out_path
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = json_path.with_suffix(".md")
    lines = [
        "# Demo Validation v3.6 / Demo 验证 v3.6",
        "",
        f"Run id: `{payload['run_id']}`",
        f"Dry run: `{str(payload['dry_run']).lower()}`",
        f"Compact JSON: `{json_path.name}`",
        "",
        "## Claim Boundary / 声明边界",
        "",
        payload["claim_boundary"],
        "",
        payload["claim_boundary_zh"],
        "",
        "## Mode Summary",
        "",
        "| Mode | Scenarios | Avg Quality | Evidence | Speedup | Missing Requirements | Replanner Agents |",
        "|------|-----------|-------------|----------|---------|----------------------|------------------|",
    ]
    for mode, summary in payload["mode_summaries"].items():
        lines.append(
            f"| {mode} | {summary['scenarios']} | {summary['avg_quality_score']} | "
            f"{summary['avg_evidence_completeness']} | {summary['avg_parallel_speedup_estimate']}x | "
            f"{summary['missing_requirement_count']} | {summary['replanner_generated_agents']} |"
        )
    lines.extend(["", "## Lift vs Single", ""])
    lines.extend([
        "| Comparison | Quality Lift | Evidence Lift | Missing Requirement Reduction | Speedup Lift |",
        "|------------|--------------|---------------|-------------------------------|--------------|",
    ])
    for name, lift in payload["lift"].items():
        lines.append(
            f"| {name} | {lift['quality_score_absolute_lift']} | "
            f"{lift['evidence_completeness_absolute_lift']} | "
            f"{lift['missing_requirement_reduction_pct']}% | {lift['parallel_speedup_lift']}x |"
        )
    lines.extend(["", "## Scenario Results", ""])
    lines.extend([
        "| Scenario | Mode | Quality | Evidence | Speedup | Missing | Replanners | Interpretation |",
        "|----------|------|---------|----------|---------|---------|------------|----------------|",
    ])
    for row in payload["rows"]:
        lines.append(
            f"| {row['scenario']} | {row['mode']} | {row['quality_score']} | "
            f"{row['evidence_completeness']} | {row['parallel_speedup_estimate']}x | "
            f"{row['missing_requirement_count']} | {row['replanner_generated_agents']} | "
            f"{row['interpretation']} |"
        )
    lines.extend(["", "## Scenarios / 场景", ""])
    for scenario_id in payload["scenarios"]:
        scenario = SCENARIOS[scenario_id]
        lines.extend([
            f"### {scenario.title} / {scenario.zh_title}",
            "",
            f"- Goal: {scenario.goal}",
            f"- Requirements: {', '.join(scenario.requirements)}",
            f"- Coverage lanes: {', '.join(scenario.coverage_lanes)}",
            f"- Guardrail: {scenario.live_guardrail}",
            "",
        ])
    lines.extend(["## Limitations / 限制", ""])
    lines.extend(f"- {item}" for item in payload["known_limitations"])
    lines.extend(f"- {item}" for item in payload["known_limitations_zh"])
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(json_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic demo validation evidence.")
    parser.add_argument("--scenarios", default="", help="Comma-separated scenario ids. Defaults to all scenarios.")
    parser.add_argument("--mode", default="single,fixed,adaptive")
    parser.add_argument("--output", default="docs/evidence/demo_validation_v360.json")
    parser.add_argument("--run-id", default="demo_validation_v360")
    parser.add_argument("--cd", default=".")
    args = parser.parse_args(argv)
    payload = _build_payload(args)
    print(_write_report(payload, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
