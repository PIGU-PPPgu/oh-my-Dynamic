"""Record compact evidence for adaptive planner/replanner dynamic workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
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

from oh_my_dynamic.runtime.dynamic_workflow import DynamicWorkflowRuntime, DynamicWorkflowTrace
from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload
from oh_my_dynamic.runtime.replan_trigger_policy import ReplanTriggerPolicy
from oh_my_dynamic.evals.workflow_observer import render_observability_dashboard


def _commit_sha(cwd: str) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _round_rows(trace: DynamicWorkflowTrace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for round_trace in trace.rounds:
        source = "planner" if round_trace.round_index == 0 else "replanner"
        rows.append({
            "round_index": round_trace.round_index,
            "source": source,
            "agent_ids": list(round_trace.agent_ids),
            "agent_count": len(round_trace.agent_ids),
            "completed": round_trace.completed,
            "failed": round_trace.failed,
            "duration_s": round(round_trace.duration_s, 2),
            "trace_path": round_trace.trace_path,
        })
    return rows


def _payload_from_trace(args: argparse.Namespace, trace: DynamicWorkflowTrace, duration_s: float) -> Dict[str, Any]:
    summary = trace.summary()
    rounds = _round_rows(trace)
    trigger_summary = _trigger_summary(trace.replan_trigger_records)
    trigger_summary["followup_agents_generated"] = sum(round_item["agent_count"] for round_item in rounds[1:])
    return {
        "run_id": trace.run_id,
        "goal": args.goal,
        "commit_sha": _commit_sha(args.cd),
        "dry_run": False,
        "workflow_kind": "adaptive_dynamic_workflow",
        "agents_requested": args.max_agents,
        "agents_completed": summary["completed"],
        "agents_failed": summary["failed"],
        "agents_total": summary["agents"],
        "rounds": rounds,
        **trigger_summary,
        "planner_generated_agents": rounds[0]["agent_count"] if rounds else 0,
        "replanner_generated_agents": sum(round_item["agent_count"] for round_item in rounds[1:]),
        "duration_s": round(duration_s, 2),
        "max_rounds": args.max_rounds,
        "max_agents": args.max_agents,
        "max_parallel": args.max_parallel,
        "sandbox": args.sandbox,
        "planner_sandbox": args.planner_sandbox,
        "codex_extra_args": args.codex_extra_arg,
        "required_coverage": _csv_items(args.required_coverage),
        "force_missing_coverage": _csv_items(args.force_missing_coverage),
        "broker_thread_id": trace.broker_thread_id,
        "stop_reason": trace.stop_reason,
        "terminal_state": trace.reducer_result.terminal_state,
        "reducer_recommended_next_agents": trace.reducer_result.recommended_next_agents,
        "reducer_artifact_ids": trace.reducer_result.artifact_ids,
        "dynamic_trace_path": str(
            (
                Path(args.workspace_root)
                if Path(args.workspace_root).is_absolute()
                else Path(args.cd).resolve() / args.workspace_root
            ) / trace.run_id / "dynamic_trace.json"
        ),
        "known_limitations": [
            "Manual smoke evidence; not part of default CI.",
            "Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.",
            "This is Codex CLI process-swarm fan-out, not App-native isolated subagents.",
        ],
    }


def _dry_payload(args: argparse.Namespace) -> Dict[str, Any]:
    run_id = args.run_id or f"dry_adaptive_workflow_{int(time.time())}"
    planner_agents = [f"planner_agent_{index:02d}" for index in range(5)]
    replanner_agents = [f"replanner_agent_{index:02d}" for index in range(2)]
    return {
        "run_id": run_id,
        "goal": args.goal,
        "commit_sha": _commit_sha(args.cd),
        "dry_run": True,
        "workflow_kind": "adaptive_dynamic_workflow",
        "agents_requested": args.max_agents,
        "agents_completed": len(planner_agents) + len(replanner_agents),
        "agents_failed": 0,
        "agents_total": len(planner_agents) + len(replanner_agents),
        "rounds": [
            {
                "round_index": 0,
                "source": "planner",
                "agent_ids": planner_agents,
                "agent_count": len(planner_agents),
                "completed": len(planner_agents),
                "failed": 0,
                "duration_s": 0.0,
                "trace_path": "",
            },
            {
                "round_index": 1,
                "source": "replanner",
                "agent_ids": replanner_agents,
                "agent_count": len(replanner_agents),
                "completed": len(replanner_agents),
                "failed": 0,
                "duration_s": 0.0,
                "trace_path": "",
            },
        ],
        "replan_triggers": [
            {
                "kind": "missing_coverage",
                "lanes": _csv_items(args.force_missing_coverage) or ["docs"],
                "reason": "Dry-run controlled trigger fixture.",
            }
        ],
        "missing_coverage": _csv_items(args.force_missing_coverage) or ["docs"],
        "low_score_agents": [],
        "followup_agents_requested": 2,
        "followup_agents_generated": len(replanner_agents),
        "replan_trigger_records": [
            {
                "round_index": 0,
                "replan_triggers": [
                    {
                        "kind": "missing_coverage",
                        "lanes": _csv_items(args.force_missing_coverage) or ["docs"],
                        "reason": "Dry-run controlled trigger fixture.",
                    }
                ],
                "missing_coverage": _csv_items(args.force_missing_coverage) or ["docs"],
                "low_score_agents": [],
                "failed_agents": [],
                "open_questions": [],
                "followup_agent_budget": 2,
            }
        ],
        "planner_generated_agents": len(planner_agents),
        "replanner_generated_agents": len(replanner_agents),
        "duration_s": 0.0,
        "max_rounds": args.max_rounds,
        "max_agents": args.max_agents,
        "max_parallel": args.max_parallel,
        "sandbox": args.sandbox,
        "planner_sandbox": args.planner_sandbox,
        "codex_extra_args": args.codex_extra_arg,
        "required_coverage": _csv_items(args.required_coverage),
        "force_missing_coverage": _csv_items(args.force_missing_coverage),
        "broker_thread_id": run_id,
        "stop_reason": "dry_run",
        "terminal_state": "completed",
        "reducer_recommended_next_agents": [
            {"id": "quality_followup", "role": "quality_reviewer", "goal": "Inspect low-confidence or missing evidence."}
        ],
        "reducer_artifact_ids": [],
        "dynamic_trace_path": "",
        "known_limitations": [
            "Dry run only; no Codex CLI workers were launched.",
            "Use a real run for release evidence.",
        ],
    }


def _write_evidence(output_dir: str, payload: Dict[str, Any]) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = sanitize_payload(payload)
    md_path = out_dir / f"{payload['run_id']}.md"
    json_path = md_path.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Adaptive Dynamic Workflow Evidence: {payload['run_id']}",
        "",
        f"Compact JSON: `{json_path.name}`",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Round Timeline",
        "",
    ]
    for round_item in payload["rounds"]:
        lines.append(
            "- round {round_index} ({source}): {completed}/{agent_count} completed, "
            "{failed} failed, agents={agents}".format(
                agents=", ".join(round_item["agent_ids"][:12]),
                **round_item,
            )
        )
    triggers = payload.get("replan_triggers", [])
    lines.extend([
        "",
        "## Replan Triggers",
        "",
    ])
    if triggers:
        for trigger in triggers:
            detail = trigger.get("lanes") or trigger.get("agents") or []
            lines.append(f"- {trigger.get('kind', 'trigger')}: {', '.join(str(item) for item in detail)}")
    else:
        lines.append("- No deterministic replan triggers recorded.")
    lines.extend([
        f"- follow-up requested: {payload.get('followup_agents_requested', 0)}",
        f"- follow-up generated: {payload.get('followup_agents_generated', payload.get('replanner_generated_agents', 0))}",
    ])
    recommendations = [
        f"- {item.get('id', item.get('role', 'agent'))}: {item.get('goal', item)}"
        for item in payload.get("reducer_recommended_next_agents", [])
    ] or ["- No recommended next agents."]
    lines.extend([
        "",
        "## Reducer Recommendations",
        "",
        *recommendations,
        "",
        "## Known Limitations",
        "",
        *[f"- {item}" for item in payload["known_limitations"]],
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def _csv_items(value: str) -> List[str]:
    return [item.strip().lower() for item in str(value or "").split(",") if item.strip()]


def _trigger_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    triggers: List[Dict[str, Any]] = []
    missing: List[str] = []
    low_score: List[str] = []
    requested = 0
    for record in records:
        triggers.extend(record.get("replan_triggers", []) or [])
        missing.extend(str(item) for item in record.get("missing_coverage", []) or [])
        low_score.extend(str(item) for item in record.get("low_score_agents", []) or [])
        requested += int(record.get("followup_agent_budget", 0) or 0)
    return {
        "replan_triggers": triggers,
        "missing_coverage": sorted(set(missing)),
        "low_score_agents": sorted(set(low_score)),
        "followup_agents_requested": requested,
        "followup_agents_generated": 0,
        "replan_trigger_records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record compact adaptive dynamic workflow evidence.")
    parser.add_argument("--goal", default="Use adaptive planner/replanner agents to review this repo and identify productization gaps.")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--cd", default=".")
    parser.add_argument("--workspace-root", default=".orchestry/adaptive_workflow")
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker_adaptive")
    parser.add_argument("--checkpoint-dir", default=".orchestry/checkpoints")
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--max-agents", type=int, default=50)
    parser.add_argument("--max-parallel", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--total-timeout-s", type=int, default=None)
    parser.add_argument("--planner-timeout-s", type=int, default=None)
    parser.add_argument("--sandbox", default="read-only")
    parser.add_argument("--planner-sandbox", default="read-only")
    parser.add_argument(
        "--required-coverage",
        default="",
        help="Comma-separated coverage lanes that completed planner agents should represent.",
    )
    parser.add_argument(
        "--force-missing-coverage",
        default="",
        help="Comma-separated lanes treated as missing for controlled replanner smoke runs.",
    )
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        default=[],
        help="Extra argument passed to planner/replanner and every worker. Repeat for multiple args.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write deterministic evidence without launching Codex CLI.")
    parser.add_argument("--dashboard", action="store_true", help="Also render a static round-aware dashboard for real runs.")
    args = parser.parse_args()

    if args.dry_run:
        payload = _dry_payload(args)
    else:
        runtime = DynamicWorkflowRuntime(
            codex_bin=args.codex_bin,
            codex_cwd=args.cd,
            workspace_root=args.workspace_root,
            broker_dir=args.broker_dir,
            max_rounds=args.max_rounds,
            max_agents=args.max_agents,
            max_parallel=args.max_parallel,
            timeout_s=args.timeout_s,
            total_timeout_s=args.total_timeout_s,
            planner_timeout_s=args.planner_timeout_s,
            checkpoint_dir=args.checkpoint_dir,
            sandbox=args.sandbox,
            planner_sandbox=args.planner_sandbox,
            codex_extra_args=args.codex_extra_arg,
            replan_trigger_policy=ReplanTriggerPolicy(
                required_coverage=_csv_items(args.required_coverage),
                force_missing_coverage=_csv_items(args.force_missing_coverage),
            ),
        )
        started = time.time()
        trace = runtime.run(args.goal, run_id=args.run_id or None)
        payload = _payload_from_trace(args, trace, time.time() - started)

    md_path = _write_evidence(args.output_dir, payload)
    if args.dashboard and not args.dry_run:
        dashboard_path = Path(args.output_dir) / f"{payload['run_id']}-dashboard.html"
        render_observability_dashboard(str(payload["run_id"]), source=".orchestry", output=str(dashboard_path))
    print(str(md_path))


if __name__ == "__main__":
    main()
