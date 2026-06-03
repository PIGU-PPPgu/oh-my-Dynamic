"""Preview MCP and A2A adapter payloads."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from protocol_adapters import A2ATaskStore, a2a_agent_card, mcp_tools, run_mcp_tool
from examples.mock_llm import mock_llm


def main() -> None:
    print("=== MCP tools ===")
    for tool in mcp_tools():
        print(f"- {tool['name']}: {tool['description']}")

    print("\n=== MCP tool run ===")
    response = run_mcp_tool(
        "oh_my_dynamic.run_workflow",
        {"query": "Evaluate a lightweight AI tutoring workflow.", "max_iterations": 1},
        mock_llm,
    )
    print(response["structuredContent"]["final_answer"])

    print("\n=== A2A Agent Card ===")
    card = a2a_agent_card("http://localhost:8765")
    print(card["name"], card["version"], card["skills"][0]["id"])

    print("\n=== A2A Task ===")
    store = A2ATaskStore(mock_llm)
    task = store.submit("Run a multi-agent workflow for a code review.")
    print(task["id"], task["status"]["state"], task["artifacts"][0]["name"])


if __name__ == "__main__":
    main()
