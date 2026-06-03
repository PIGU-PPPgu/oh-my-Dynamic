"""Demo: sandboxed fan-out with many isolated workers."""

from __future__ import annotations

import _bootstrap  # noqa: F401

from native_runtime import AgentSpec, SandboxedFanoutRuntime, ToolGrant


def mock_worker_llm(system_prompt: str, user_prompt: str) -> str:
    if "Worker results:" in user_prompt:
        completed = user_prompt.count(", completed)")
        return (
            f"Reducer synthesis: {completed} isolated workers completed. "
            "Each worker had a separate sandbox path, context prompt, and tool grant list."
        )
    agent_line = next((line for line in user_prompt.splitlines() if line.startswith("Agent id:")), "Agent id: unknown")
    role_line = next((line for line in user_prompt.splitlines() if line.startswith("Role:")), "Role: worker")
    return f"{agent_line}; {role_line}; completed isolated analysis."


def build_agents(count: int = 64) -> list[AgentSpec]:
    agents = []
    for i in range(count):
        agents.append(
            AgentSpec(
                id=f"agent_{i:03d}",
                role=["researcher", "reviewer", "builder", "risk-auditor"][i % 4],
                goal=f"Analyze shard {i} of the workflow and return concise findings.",
                context=f"Shard index={i}; this context is private to this worker.",
                tool_grants=[
                    ToolGrant("read", "sandbox", "Read only the worker sandbox."),
                    ToolGrant("notes", "write", "Write intermediate notes in the worker sandbox."),
                ],
            )
        )
    return agents


def main() -> None:
    runtime = SandboxedFanoutRuntime(mock_worker_llm, max_workers=64)
    trace = runtime.run(
        "Demonstrate dynamic workflow fan-out with isolated worker sandboxes.",
        build_agents(64),
    )
    print("=== Sandboxed Fan-out Demo ===")
    print(trace.final_answer)
    print(trace.summary())


if __name__ == "__main__":
    main()
