"""
Codex App subagent bridge contract.

This module does not spawn Codex App subagents. Spawning is owned by the Codex
App runtime. The bridge provides the contract the parent Codex agent can use:

1. build a dispatch plan for real Codex subagents,
2. generate per-subagent prompts that require a structured result envelope,
3. parse returned envelopes, and
4. ingest them into AgentBroker as messages, artifacts, handoffs, review
   requests/responses, and audit trace events.

That keeps the default LLM path inside Codex App while letting App-native
subagents and local isolated workers share the same broker trace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import json
import re
import uuid

from agent_broker import AgentBroker


def _run_id() -> str:
    return f"codex_run_{uuid.uuid4().hex[:10]}"


@dataclass
class CodexSubagentSpec:
    """Dispatch specification for one Codex App subagent."""

    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    tool_policy: str = "least_privilege"


@dataclass
class CodexAppDispatchPlan:
    """Parent-agent dispatch plan for App-native subagents."""

    run_id: str
    goal: str
    agents: List[CodexSubagentSpec]
    broker_dir: str = ".orchestry/agent_broker"
    max_parallel: int = 8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "broker_dir": self.broker_dir,
            "max_parallel": self.max_parallel,
            "agents": [asdict(agent) for agent in self.agents],
        }


@dataclass
class EnvelopeArtifact:
    name: str
    content: str
    kind: str = "text"
    content_type: str = "text/plain"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvelopeMessage:
    to_agent: Optional[str]
    subject: str
    body: str
    artifact_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvelopeHandoff:
    to_agent: str
    task_id: str
    subject: str
    body: str
    artifact_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvelopeReviewRequest:
    reviewer: str
    task_id: str
    subject: str
    body: str
    artifact_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvelopeReviewResponse:
    to_agent: str
    task_id: str
    subject: str
    body: str
    verdict: str
    artifact_names: List[str] = field(default_factory=list)
    parent_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodexSubagentEnvelope:
    """Structured return envelope expected from a Codex App subagent."""

    agent_id: str
    status: str
    summary: str
    artifacts: List[EnvelopeArtifact] = field(default_factory=list)
    messages: List[EnvelopeMessage] = field(default_factory=list)
    handoffs: List[EnvelopeHandoff] = field(default_factory=list)
    review_requests: List[EnvelopeReviewRequest] = field(default_factory=list)
    review_responses: List[EnvelopeReviewResponse] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


def create_dispatch_plan(
    goal: str,
    agents: List[CodexSubagentSpec],
    broker_dir: str = ".orchestry/agent_broker",
    max_parallel: int = 8,
    run_id: Optional[str] = None,
) -> CodexAppDispatchPlan:
    """Create a dispatch plan for parent-orchestrated Codex App subagents."""
    if not goal.strip():
        raise ValueError("goal is required")
    if not agents:
        raise ValueError("at least one CodexSubagentSpec is required")
    seen = set()
    for agent in agents:
        if not agent.id:
            raise ValueError("agent id is required")
        if agent.id in seen:
            raise ValueError(f"duplicate agent id: {agent.id}")
        seen.add(agent.id)
    return CodexAppDispatchPlan(
        run_id=run_id or _run_id(),
        goal=goal,
        agents=agents,
        broker_dir=broker_dir,
        max_parallel=max_parallel,
    )


def build_subagent_prompt(plan: CodexAppDispatchPlan, spec: CodexSubagentSpec) -> str:
    """Build the prompt for a real Codex App subagent."""
    return (
        "You are a real Codex App subagent participating in an oh-my-Dynamic "
        "dynamic workflow.\n\n"
        "Runtime rules:\n"
        "- Use the current Codex App model/runtime inherited from the parent. Do not request external API keys.\n"
        "- Keep your context isolated to this assignment and the provided dependencies.\n"
        "- Return exactly one JSON object. Do not wrap it in prose.\n"
        "- The parent orchestrator will ingest your JSON into AgentBroker.\n"
        "- Reference artifacts inside events by artifact_names, using names you publish in this envelope.\n\n"
        f"Workflow run_id: {plan.run_id}\n"
        f"Workflow goal: {plan.goal}\n\n"
        f"Agent id: {spec.id}\n"
        f"Role: {spec.role}\n"
        f"Goal: {spec.goal}\n"
        f"Dependencies: {json.dumps(spec.dependencies, ensure_ascii=False)}\n"
        f"Tool policy: {spec.tool_policy}\n"
        f"Context:\n{spec.context or '(none)'}\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "agent_id": "<your agent id>",\n'
        '  "status": "completed|failed",\n'
        '  "summary": "<concise result for reducer>",\n'
        '  "artifacts": [{"name":"result","kind":"analysis","content_type":"text/plain","content":"..."}],\n'
        '  "messages": [{"to_agent":"orchestrator","subject":"...","body":"...","artifact_names":["result"]}],\n'
        '  "handoffs": [],\n'
        '  "review_requests": [],\n'
        '  "review_responses": [],\n'
        '  "metadata": {"confidence": 0.8},\n'
        '  "error": ""\n'
        "}\n"
    )


def parse_subagent_envelope(text: str) -> CodexSubagentEnvelope:
    """Parse a subagent JSON envelope from raw text or a fenced JSON block."""
    data = _extract_json_object(text)
    return envelope_from_dict(data)


def envelope_from_dict(data: Dict[str, Any]) -> CodexSubagentEnvelope:
    """Build an envelope dataclass from a dictionary."""
    agent_id = str(data.get("agent_id", "")).strip()
    if not agent_id:
        raise ValueError("envelope.agent_id is required")
    status = str(data.get("status", "")).strip() or "completed"
    if status not in ("completed", "failed"):
        raise ValueError("envelope.status must be completed or failed")
    return CodexSubagentEnvelope(
        agent_id=agent_id,
        status=status,
        summary=str(data.get("summary", "")),
        artifacts=[_artifact(item) for item in data.get("artifacts", [])],
        messages=[_message(item) for item in data.get("messages", [])],
        handoffs=[_handoff(item) for item in data.get("handoffs", [])],
        review_requests=[_review_request(item) for item in data.get("review_requests", [])],
        review_responses=[_review_response(item) for item in data.get("review_responses", [])],
        metadata=dict(data.get("metadata", {})),
        error=str(data.get("error", "")),
    )


def ingest_subagent_envelope(
    broker: AgentBroker,
    thread_id: str,
    envelope: CodexSubagentEnvelope,
    role: str = "subagent",
    capabilities: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Ingest one Codex App subagent envelope into AgentBroker."""
    broker.register_agent(envelope.agent_id, role, capabilities or ["codex_app_subagent"], envelope.metadata)
    artifact_ids_by_name: Dict[str, str] = {}

    for artifact in envelope.artifacts:
        published = broker.publish_artifact(
            envelope.agent_id,
            artifact.name,
            artifact.content,
            kind=artifact.kind,
            content_type=artifact.content_type,
            metadata={**artifact.metadata, "thread_id": thread_id},
        )
        artifact_ids_by_name[artifact.name] = published.id

    broker.trace(
        envelope.agent_id,
        "codex_subagent_completed" if envelope.status == "completed" else "codex_subagent_failed",
        envelope.summary or envelope.error,
        thread_id=thread_id,
        artifact_ids=list(artifact_ids_by_name.values()),
        metadata={"status": envelope.status, **envelope.metadata},
    )

    event_ids: List[str] = []
    for message in envelope.messages:
        event = broker.send_message(
            envelope.agent_id,
            message.to_agent,
            message.subject,
            message.body,
            thread_id=thread_id,
            artifact_ids=_resolve_names(message.artifact_names, artifact_ids_by_name),
            metadata=message.metadata,
        )
        event_ids.append(event.id)

    for handoff in envelope.handoffs:
        event = broker.create_handoff(
            envelope.agent_id,
            handoff.to_agent,
            handoff.task_id,
            handoff.subject,
            handoff.body,
            artifact_ids=_resolve_names(handoff.artifact_names, artifact_ids_by_name),
            thread_id=thread_id,
            metadata=handoff.metadata,
        )
        event_ids.append(event.id)

    for request in envelope.review_requests:
        event = broker.request_review(
            envelope.agent_id,
            request.reviewer,
            request.task_id,
            request.subject,
            request.body,
            artifact_ids=_resolve_names(request.artifact_names, artifact_ids_by_name),
            thread_id=thread_id,
            metadata=request.metadata,
        )
        event_ids.append(event.id)

    for response in envelope.review_responses:
        event = broker.respond_review(
            envelope.agent_id,
            response.to_agent,
            response.task_id,
            response.subject,
            response.body,
            response.verdict,
            artifact_ids=_resolve_names(response.artifact_names, artifact_ids_by_name),
            thread_id=thread_id,
            parent_id=response.parent_id,
            metadata=response.metadata,
        )
        event_ids.append(event.id)

    return {
        "agent_id": envelope.agent_id,
        "status": envelope.status,
        "artifact_ids": artifact_ids_by_name,
        "event_ids": event_ids,
    }


def register_dispatch_plan(broker: AgentBroker, plan: CodexAppDispatchPlan) -> None:
    """Register orchestrator and all planned Codex App subagents with the broker."""
    broker.register_agent("orchestrator", "orchestrator", ["coordinate", "reduce"])
    broker.trace(
        "orchestrator",
        "codex_app_dispatch_plan",
        plan.goal,
        thread_id=plan.run_id,
        metadata=plan.to_dict(),
    )
    for spec in plan.agents:
        broker.register_agent(
            spec.id,
            spec.role,
            spec.capabilities or ["codex_app_subagent"],
            metadata={
                "goal": spec.goal,
                "dependencies": spec.dependencies,
                "tool_policy": spec.tool_policy,
            },
        )


def _extract_json_object(text: str) -> Dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in subagent response")
        text = text[start:end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid subagent envelope JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("subagent envelope must be a JSON object")
    return data


def _artifact(data: Dict[str, Any]) -> EnvelopeArtifact:
    return EnvelopeArtifact(
        name=str(data.get("name", "result")),
        content=str(data.get("content", "")),
        kind=str(data.get("kind", "text")),
        content_type=str(data.get("content_type", "text/plain")),
        metadata=dict(data.get("metadata", {})),
    )


def _message(data: Dict[str, Any]) -> EnvelopeMessage:
    return EnvelopeMessage(
        to_agent=data.get("to_agent", data.get("to")),
        subject=str(data.get("subject", "message")),
        body=str(data.get("body", "")),
        artifact_names=list(data.get("artifact_names", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _handoff(data: Dict[str, Any]) -> EnvelopeHandoff:
    return EnvelopeHandoff(
        to_agent=str(data.get("to_agent", data.get("to", ""))),
        task_id=str(data.get("task_id", "")),
        subject=str(data.get("subject", "handoff")),
        body=str(data.get("body", "")),
        artifact_names=list(data.get("artifact_names", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _review_request(data: Dict[str, Any]) -> EnvelopeReviewRequest:
    return EnvelopeReviewRequest(
        reviewer=str(data.get("reviewer", data.get("to_agent", data.get("to", "")))),
        task_id=str(data.get("task_id", "")),
        subject=str(data.get("subject", "review_request")),
        body=str(data.get("body", "")),
        artifact_names=list(data.get("artifact_names", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _review_response(data: Dict[str, Any]) -> EnvelopeReviewResponse:
    return EnvelopeReviewResponse(
        to_agent=str(data.get("to_agent", data.get("to", "orchestrator"))),
        task_id=str(data.get("task_id", "")),
        subject=str(data.get("subject", "review_response")),
        body=str(data.get("body", "")),
        verdict=str(data.get("verdict", "commented")),
        artifact_names=list(data.get("artifact_names", [])),
        parent_id=str(data.get("parent_id", "")),
        metadata=dict(data.get("metadata", {})),
    )


def _resolve_names(names: List[str], artifact_ids_by_name: Dict[str, str]) -> List[str]:
    missing = [name for name in names if name not in artifact_ids_by_name]
    if missing:
        raise ValueError(f"unknown envelope artifact names: {', '.join(missing)}")
    return [artifact_ids_by_name[name] for name in names]
