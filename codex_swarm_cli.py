"""Command-line entrypoint for the Codex CLI swarm façade."""

from __future__ import annotations

import argparse

from agent_broker import AgentBroker
from codex_cli_swarm import CodexCliSwarmRuntime
from codex_swarm_models import CodexCliAgentSpec


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an oh-my-Dynamic Codex CLI process swarm.")
    parser.add_argument("goal", help="Workflow goal to distribute across Codex CLI workers.")
    parser.add_argument("--agents", type=int, default=8, help="Number of Codex CLI workers to launch.")
    parser.add_argument("--max-parallel", type=int, default=4, help="Maximum concurrent codex exec processes.")
    parser.add_argument("--codex-bin", default="codex", help="Path to the codex CLI binary.")
    parser.add_argument("--cd", default=".", help="Working directory passed to codex exec --cd.")
    parser.add_argument("--workspace-root", default=".orchestry/codex_cli_swarm")
    parser.add_argument("--worktree-root", default=".orchestry/worktrees")
    parser.add_argument("--workspace-mode", choices=["shared", "worktree"], default="shared")
    parser.add_argument("--write-intent", choices=["none", "patch"], default="none")
    parser.add_argument("--sandbox", default="read-only", help="Sandbox passed to each codex exec worker.")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--total-timeout-s", type=int, default=None)
    parser.add_argument(
        "--discard-workdirs",
        action="store_true",
        help="Delete per-agent workdirs after writing durable trace files.",
    )
    parser.add_argument("--keep-workdirs", action="store_true", help="Deprecated no-op; workdirs are kept by default.")
    args = parser.parse_args()

    if args.agents < 1:
        raise SystemExit("--agents must be at least 1")

    broker = AgentBroker(args.broker_dir)
    runtime = CodexCliSwarmRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=args.cd,
        workspace_root=args.workspace_root,
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        total_timeout_s=args.total_timeout_s,
        keep_workdirs=not args.discard_workdirs,
        broker=broker,
        worktree_root=args.worktree_root,
    )
    specs = [
        CodexCliAgentSpec(
            id=f"agent_{index:03d}",
            role="codex_cli_worker",
            goal=f"Shard {index + 1}/{args.agents}: {args.goal}",
            context=(
                "Work independently. Return evidence-oriented findings for this shard. "
                "Do not edit files unless the prompt explicitly asks for implementation."
            ),
            workspace_mode=args.workspace_mode,
            write_intent=args.write_intent,
            sandbox=args.sandbox,
            base_ref=args.base_ref,
        )
        for index in range(args.agents)
    ]
    trace = runtime.run(args.goal, specs)
    print(trace.summary())
    print(f"broker_thread_id={trace.broker_thread_id}")
    print(f"swarm_root={trace.swarm_root}")


if __name__ == "__main__":
    main()
