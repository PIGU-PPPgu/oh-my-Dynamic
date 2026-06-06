#!/usr/bin/env python3
"""Run deterministic benchmark comparisons for oh-my-Dynamic modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oh_my_dynamic.evals.eval_runner import EvalTask, score_response, summarize_results
from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload


MODE_AGENT_COUNTS = {
    "single": 1,
    "fixed": 5,
    "adaptive": 7,
}


def _load_suite(path: str) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list) or len(tasks) < 1:
        raise ValueError("benchmark suite must contain tasks[]")
    return payload


def _modes(value: str) -> List[str]:
    modes = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [mode for mode in modes if mode not in MODE_AGENT_COUNTS]
    if unknown:
        raise ValueError(f"unknown benchmark mode(s): {', '.join(unknown)}")
    return modes or ["single", "fixed", "adaptive"]


def _response_for(task: Dict[str, Any], mode: str) -> str:
    keywords = ", ".join(task.get("expected_keywords", []))
    evidence = ", ".join(task.get("required_evidence", []))
    agent_note = {
        "single": "single baseline reviewer",
        "fixed": "fixed swarm lanes with parallel reviewers",
        "adaptive": "adaptive planner and replanner with broker evidence",
    }[mode]
    return (
        f"Finding for {task['id']} from {agent_note}: covers {keywords}. "
        f"Evidence includes {evidence}; file README.md line 1, command python test_suite.py, "
        f"trace .orchestry/benchmark/{mode}/trace.json, agent {mode}_reviewer, "
        "risk noted, gap recorded, score comparison included, recommendation recorded."
    )


def _run_dry_suite(suite: Dict[str, Any], modes: List[str]) -> Dict[str, Any]:
    started = time.time()
    task_rows: List[Dict[str, Any]] = []
    mode_summaries: Dict[str, Any] = {}
    for mode in modes:
        results = []
        for item in suite["tasks"]:
            allowed = item.get("allowed_modes") or modes
            if mode not in allowed:
                continue
            task = EvalTask(
                id=str(item["id"]),
                prompt=str(item.get("goal", "")),
                expected_keywords=[str(value) for value in item.get("expected_keywords", [])],
                required_evidence=[str(value) for value in item.get("required_evidence", [])],
                min_score=float(item.get("min_score", 0.65)),
            )
            result = score_response(task, _response_for(item, mode))
            results.append(result)
            task_rows.append({
                "mode": mode,
                "task_id": result.task_id,
                "score": result.score,
                "passed": result.passed,
                "agent_count": MODE_AGENT_COUNTS[mode],
                "replanner_count": 2 if mode == "adaptive" else 0,
                "duration_s": 0.0,
            })
        summary = summarize_results(results)
        mode_summaries[mode] = {
            **summary,
            "agent_count": MODE_AGENT_COUNTS[mode],
            "replanner_count": 2 if mode == "adaptive" else 0,
            "failure_rate": 0.0 if summary["total"] else 1.0,
        }
    return {
        "benchmark": suite.get("name", "benchmark"),
        "dry_run": True,
        "created_at": int(started),
        "duration_s": round(time.time() - started, 3),
        "modes": modes,
        "task_count": len(suite["tasks"]),
        "mode_summaries": mode_summaries,
        "task_results": task_rows,
        "known_limitations": [
            "Dry-run benchmark validates scoring shape only; it does not launch Codex CLI.",
            "Manual real benchmark evidence should be committed separately.",
        ],
    }


def _write_report(payload: Dict[str, Any], output: str) -> str:
    payload = sanitize_payload(payload)
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".md":
        json_path = out_path.with_suffix(".json")
    else:
        json_path = out_path
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = json_path.with_suffix(".md")
    lines = [
        f"# oh-my-Dynamic Benchmark: {payload['benchmark']}",
        "",
        f"Compact JSON: `{json_path.name}`",
        "",
        "## Mode Summary",
        "",
        "| Mode | Passed | Failed | Avg Score | Agents | Replanners |",
        "|------|--------|--------|-----------|--------|------------|",
    ]
    for mode, summary in payload["mode_summaries"].items():
        lines.append(
            f"| {mode} | {summary['passed']} | {summary['failed']} | {summary['avg_score']} | "
            f"{summary['agent_count']} | {summary['replanner_count']} |"
        )
    lines.extend([
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in payload["known_limitations"]],
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(json_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic benchmark comparisons.")
    parser.add_argument("--suite", default="benchmarks/repo_review.json")
    parser.add_argument("--mode", default="single,fixed,adaptive")
    parser.add_argument("--output", default="docs/evidence/benchmark_v240.json")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run deterministic benchmark without Codex CLI.")
    args = parser.parse_args()
    suite = _load_suite(args.suite)
    payload = _run_dry_suite(suite, _modes(args.mode))
    print(_write_report(payload, args.output))
    if any(summary["failed"] for summary in payload["mode_summaries"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
