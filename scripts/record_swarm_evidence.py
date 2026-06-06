"""Record compact manual evidence for real Codex CLI swarm runs.

Raw traces stay under .orchestry/. This script writes a redacted summary under
docs/evidence/ so the repository can show 20/50/100-agent smoke evidence without
committing prompts, stdout, stderr, or full worker output.
"""

from __future__ import annotations

from pathlib import Path
from typing import List
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

from oh_my_dynamic.broker.agent_broker import AgentBroker
from oh_my_dynamic.codex.codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime
from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload


def _commit_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _safe_sample_summaries(trace, limit: int = 5) -> List[str]:
    samples = []
    for result in trace.results[:limit]:
        summary = (result.summary or result.error or "").replace("\n", " ").strip()
        samples.append(f"- {result.agent_id} ({result.status}): {summary[:240]}")
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Record compact evidence for a real Codex CLI swarm run.")
    parser.add_argument("--agents", type=int, required=True)
    parser.add_argument("--max-parallel", type=int, required=True)
    parser.add_argument("--goal", default="Review this repository for safety, architecture, install experience, README, and test gaps.")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--cd", default=".")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--total-timeout-s", type=int, default=None)
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        default=[],
        help="Extra argument passed to every codex exec worker. Repeat for multiple args.",
    )
    args = parser.parse_args()
    if args.agents < 1:
        raise SystemExit("--agents must be at least 1")
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be at least 1")

    broker = AgentBroker(".orchestry/agent_broker_evidence")
    runtime = CodexCliSwarmRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=args.cd,
        workspace_root=".orchestry/evidence_swarm",
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        total_timeout_s=args.total_timeout_s,
        broker=broker,
    )
    specs = [
        CodexCliAgentSpec(
            id=f"agent_{index:03d}",
            role="evidence_reviewer",
            goal=f"Shard {index + 1}/{args.agents}: {args.goal}",
            context="Return concise evidence only. Do not include secrets, tokens, or full raw logs.",
            sandbox="read-only",
            extra_args=args.codex_extra_arg,
        )
        for index in range(args.agents)
    ]
    started = time.time()
    trace = runtime.run(args.goal, specs)
    duration_s = time.time() - started
    summary = trace.summary()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"swarm_{args.agents}_agents_{trace.run_id}.md"
    json_path = out_path.with_suffix(".json")
    payload = {
        "run_id": trace.run_id,
        "commit_sha": _commit_sha(),
        "agents_requested": args.agents,
        "agents_completed": summary["completed"],
        "agents_failed": summary["failed"],
        "duration_s": round(duration_s, 2),
        "max_parallel": args.max_parallel,
        "sandbox": "read-only",
        "codex_extra_args": args.codex_extra_arg,
        "trace_manifest_path": trace.manifest_path,
        "trace_path": trace.trace_path,
        "known_limitations": [
            "Manual smoke evidence; not part of default CI.",
            "Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.",
            "Sample summaries are truncated and may omit detailed findings.",
        ],
    }
    payload = sanitize_payload(payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Codex CLI Swarm Evidence: {args.agents} agents",
        "",
        f"Compact JSON: `{json_path.name}`",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Selected Anonymized Sample Summaries",
        "",
        *(_safe_sample_summaries(trace) or ["- No sample summaries captured."]),
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
