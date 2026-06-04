"""End-to-end demo: review this repository with real Codex CLI workers."""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from agent_broker import AgentBroker
from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime


REVIEW_SHARDS = [
    ("security", "Review broker/gateway security, auth boundaries, path safety, and unsafe command surfaces."),
    ("architecture", "Review runtime/backend boundaries, dependency scheduling, and protocol layering."),
    ("install", "Review Codex App plugin installation, marketplace metadata, and zero-config usage."),
    ("readme", "Review README claims for accuracy, model/provider wording, and Claude/Codex parity boundaries."),
    ("tests", "Review unit/integration/stress test gaps and suggest concrete regression tests."),
    ("observability", "Review trace files, logs, manifests, and failure debugging ergonomics."),
    ("examples", "Review examples and demos for runnable end-to-end coverage."),
    ("release", "Review release readiness, version/tag state, changelog, and CI expectations."),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real Codex CLI swarm review demo.")
    parser.add_argument("--agents", type=int, default=8, help="Number of review agents to launch.")
    parser.add_argument("--max-parallel", type=int, default=4, help="Maximum concurrent codex exec workers.")
    parser.add_argument("--timeout-s", type=int, default=1800, help="Per-worker timeout.")
    parser.add_argument("--total-timeout-s", type=int, default=None, help="Optional total swarm timeout.")
    parser.add_argument("--codex-bin", default="codex", help="Path to Codex CLI binary.")
    parser.add_argument("--sandbox", default="read-only", help="Codex CLI sandbox mode for workers.")
    parser.add_argument("--discard-workdirs", action="store_true", help="Delete per-agent workdirs after trace files are written.")
    args = parser.parse_args()

    shard_count = min(args.agents, len(REVIEW_SHARDS))
    specs = [
        CodexCliAgentSpec(
            id=f"review_{index + 1:02d}_{role}",
            role=role,
            goal=goal,
            context="Review only. Do not edit files. Return concise, evidence-oriented findings.",
            sandbox=args.sandbox,
        )
        for index, (role, goal) in enumerate(REVIEW_SHARDS[:shard_count])
    ]

    broker = AgentBroker(".orchestry/agent_broker_demo")
    runtime = CodexCliSwarmRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=".",
        workspace_root=".orchestry/codex_cli_swarm_demo",
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        total_timeout_s=args.total_timeout_s,
        keep_workdirs=not args.discard_workdirs,
        broker=broker,
    )
    trace = runtime.run(
        "Review oh-my-Dynamic itself with real Codex CLI workers and brokered JSON envelopes.",
        specs,
    )

    print(trace.summary())
    print(f"trace_path={trace.trace_path}")
    print(f"manifest_path={trace.manifest_path}")


if __name__ == "__main__":
    main()
