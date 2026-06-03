"""
Protocol adapters for ecosystem-facing integrations.

This module intentionally stays transport-agnostic: it exposes MCP-style tool
descriptors and A2A-style Agent Card / Task payloads that can be served by an
HTTP, stdio, or hosted gateway layer later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import uuid

from pipeline import DynamicPipeline


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:12]}"


@dataclass
class MCPToolDescriptor:
    """Small MCP-compatible tool descriptor."""

    name: str
    description: str
    inputSchema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


def mcp_tools() -> List[Dict[str, Any]]:
    """Return the tools oh-my-Dynamic can expose through an MCP server."""
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Complex task or question to decompose and run.",
            },
            "max_iterations": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 3,
            },
            "max_parallel": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 3,
            },
            "max_tokens": {
                "type": "integer",
                "minimum": 1000,
                "default": 500000,
            },
        },
        "required": ["query"],
    }
    return [
        MCPToolDescriptor(
            name="oh_my_dynamic.run_workflow",
            description="Decompose a complex task into a DAG, run multi-agent workers, dynamically replan, and synthesize the final answer.",
            inputSchema=schema,
        ).to_dict()
    ]


def run_mcp_tool(name: str, arguments: Dict[str, Any], llm_fn: Callable[[str, str], str]) -> Dict[str, Any]:
    """Execute a known MCP-style tool call."""
    if name != "oh_my_dynamic.run_workflow":
        raise ValueError(f"Unknown MCP tool: {name}")

    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")

    pipeline = DynamicPipeline(
        llm_fn=llm_fn,
        max_iterations=int(arguments.get("max_iterations", 3)),
        max_parallel=int(arguments.get("max_parallel", 3)),
        max_tokens=int(arguments.get("max_tokens", 500000)),
        verbose=bool(arguments.get("verbose", False)),
    )
    result = pipeline.run(query)
    return {
        "content": [
            {
                "type": "text",
                "text": result.get("final_answer", ""),
            }
        ],
        "structuredContent": result,
    }


def a2a_agent_card(base_url: str = "http://localhost:8765") -> Dict[str, Any]:
    """Return an A2A-style Agent Card describing this orchestrator."""
    return {
        "name": "oh-my-Dynamic",
        "description": "Multi-agent dynamic workflow orchestrator with DAG execution, dynamic replan, and synthesis.",
        "url": base_url.rstrip("/"),
        "version": "1.4.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "dynamic-workflow",
                "name": "Run Dynamic Workflow",
                "description": "Break a complex goal into subtasks, run workers in parallel where possible, replan on gaps, and synthesize the result.",
                "tags": ["multi-agent", "dynamic-workflow", "dag", "replan"],
                "examples": [
                    "Analyze a market from product, competitor, and risk perspectives.",
                    "Review a code change for security, correctness, and test gaps.",
                ],
            }
        ],
    }


@dataclass
class A2ATaskStore:
    """In-memory A2A-style task store for demos and lightweight gateways."""

    llm_fn: Callable[[str, str], str]
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def submit(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        task_id = _new_task_id()
        task = {
            "id": task_id,
            "status": {"state": "working", "timestamp": _now_iso()},
            "history": [
                {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}],
                    "metadata": metadata or {},
                }
            ],
            "artifacts": [],
        }
        self.tasks[task_id] = task

        try:
            pipeline = DynamicPipeline(self.llm_fn, verbose=False)
            result = pipeline.run(message)
            task["status"] = {"state": "completed", "timestamp": _now_iso()}
            task["artifacts"].append({
                "artifactId": "final-answer",
                "name": "Final Answer",
                "parts": [
                    {"kind": "text", "text": result.get("final_answer", "")},
                    {"kind": "data", "data": result},
                ],
            })
        except Exception as exc:
            task["status"] = {
                "state": "failed",
                "timestamp": _now_iso(),
                "message": str(exc),
            }

        return task

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)
