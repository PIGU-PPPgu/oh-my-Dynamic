"""Lightweight capability routing for dynamic workflow agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from workflow_events import WorkflowEvent


DEFAULT_AGENT_CAPABILITIES: Dict[str, List[str]] = {
    "security_reviewer": ["security", "review", "code"],
    "architecture_reviewer": ["architecture", "review", "code"],
    "test_reviewer": ["tests", "coverage", "review"],
    "docs_reviewer": ["docs", "install", "readme"],
    "workflow_reviewer": ["dynamic-workflow", "broker", "orchestration"],
    "general_reviewer": ["review", "general"],
}


@dataclass
class CapabilityRouter:
    registry: Dict[str, List[str]] = field(default_factory=lambda: dict(DEFAULT_AGENT_CAPABILITIES))
    fallback_agent: str = "general_reviewer"

    def pick_agent(
        self,
        required_capabilities: Iterable[str],
        run_id: str = "",
        node_id: str = "",
        event_callback: Optional[Callable[[WorkflowEvent], None]] = None,
    ) -> str:
        required = [str(item).strip() for item in required_capabilities if str(item).strip()]
        if not required:
            return self.fallback_agent
        for agent_id, capabilities in self.registry.items():
            capability_set = set(capabilities)
            if all(capability in capability_set for capability in required):
                return agent_id
        if event_callback is not None:
            event_callback(WorkflowEvent(
                run_id=run_id,
                kind="capability_route_miss",
                subject="capability_route_miss",
                body="No exact capability match; using fallback agent.",
                node_id=node_id,
                agent_id=self.fallback_agent,
                status="fallback",
                preview=", ".join(required),
                metadata={"required_capabilities": required, "fallback_agent": self.fallback_agent},
            ))
        return self.fallback_agent
