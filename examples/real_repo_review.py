#!/usr/bin/env python3
"""Run a real Codex CLI repo review and record compact evidence.

Use --dry-run in CI or docs checks. Real runs keep raw traces under .orchestry/
and write only a compact markdown evidence file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import argparse
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_broker import AgentBroker
from broker_reducer import reduce_broker_thread
from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime


REVIEW_LANES = [
    ("security", "security_reviewer", "Review security risks, unsafe subprocess/file handling, secret leakage, and dependency risks."),
    ("architecture", "architecture_reviewer", "Review architecture boundaries, module coupling, and dynamic workflow design gaps."),
    ("install_docs", "docs_reviewer", "Review install experience, README clarity, CLI usability, and docs consistency."),
    ("tests", "test_reviewer", "Review test coverage, CI gaps, fake-vs-real evidence, and missing edge cases."),
    ("workflow_alignment", "workflow_reviewer", "Compare this repo against Claude-style dynamic workflows and VMAO-style verify/replan loops."),
]


def _commit_sha(cwd: str) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_evidence(path: Path, payload: Dict[str, object], samples: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    json_path = path.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Real Repo Review Evidence: {payload['run_id']}",
        "",
        f"Compact JSON: `{json_path.name}`",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Top Findings",
        "",
        *(samples or ["- Dry run only; no real Codex CLI findings captured."]),
        "",
        "## Human Follow-up",
        "",
        "- Review the broker reduction and decide which findings become implementation tasks.",
        "",
        "## Known Limitations",
        "",
        "- Raw prompts/stdout/stderr are intentionally not committed.",
        "- This is manual smoke evidence when run without --dry-run.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_dry(args: argparse.Namespace) -> Dict[str, object]:
    run_id = args.run_id or f"dry_repo_review_{int(time.time())}"
    return {
        "run_id": run_id,
        "goal": args.goal,
        "commit_sha": _commit_sha(args.cd),
        "agents_requested": args.agents,
        "agents_completed": args.agents,
        "agents_failed": 0,
        "duration_s": 0.0,
        "max_parallel": args.max_parallel,
        "broker_thread_id": run_id,
        "trace_path": "",
        "checkpoint_path": "",
        "dry_run": True,
    }


def run_real(args: argparse.Namespace) -> Dict[str, object]:
    broker = AgentBroker(args.broker_dir)
    runtime = CodexCliSwarmRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=args.cd,
        workspace_root=args.workspace_root,
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        total_timeout_s=args.total_timeout_s,
        broker=broker,
    )
    specs = [
        CodexCliAgentSpec(
            id=lane_id,
            role=role,
            goal=f"{args.goal}\n\nLane focus: {lane_goal}",
            context="Read-only review. Do not edit files. Return concise, evidence-oriented findings.",
            workspace_mode="shared",
            write_intent="none",
        )
        for lane_id, role, lane_goal in REVIEW_LANES[:args.agents]
    ]
    started = time.time()
    trace = runtime.run(args.goal, specs, run_id=args.run_id or None)
    reduction = reduce_broker_thread(broker, trace.run_id, args.goal)
    summary = trace.summary()
    return {
        "run_id": trace.run_id,
        "goal": args.goal,
        "commit_sha": _commit_sha(args.cd),
        "agents_requested": args.agents,
        "agents_completed": summary["completed"],
        "agents_failed": summary["failed"],
        "duration_s": round(time.time() - started, 2),
        "max_parallel": args.max_parallel,
        "broker_thread_id": trace.broker_thread_id,
        "trace_path": trace.trace_path,
        "checkpoint_path": "",
        "dry_run": False,
        "reducer_state": reduction.terminal_state,
        "risk_summary": reduction.risk_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real Codex CLI repo review and write compact evidence.")
    parser.add_argument("--agents", type=int, default=5)
    parser.add_argument("--max-parallel", type=int, default=3)
    parser.add_argument("--goal", default="Review this repository for security, architecture, install/docs, tests, and dynamic workflow alignment.")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--cd", default=".")
    parser.add_argument("--workspace-root", default=".orchestry/real_repo_review")
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker_real_repo_review")
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--total-timeout-s", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Write sample evidence without launching Codex CLI.")
    args = parser.parse_args()
    if args.agents < 1:
        raise SystemExit("--agents must be at least 1")
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be at least 1")

    payload = run_dry(args) if args.dry_run else run_real(args)
    evidence_path = Path(args.output_dir) / f"{payload['run_id']}.md"
    samples = [
        f"- {lane_id}: {lane_goal}"
        for lane_id, _role, lane_goal in REVIEW_LANES[:args.agents]
    ] if args.dry_run else []
    _write_evidence(evidence_path, payload, samples)
    print(str(evidence_path))


if __name__ == "__main__":
    main()
