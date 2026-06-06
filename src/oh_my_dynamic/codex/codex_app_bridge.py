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

from oh_my_dynamic.broker.agent_broker import AgentBroker, validate_agent_id


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
    topological_layers: List[List[str]] = field(default_factory=list)
    ready_batches: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "broker_dir": self.broker_dir,
            "max_parallel": self.max_parallel,
            "topological_layers": self.topological_layers,
            "ready_batches": self.ready_batches,
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
    if max_parallel < 1:
        raise ValueError("max_parallel must be at least 1")
    layers = _topological_agent_layers(agents)
    ready_batches = _ready_batches(layers, max_parallel)
    return CodexAppDispatchPlan(
        run_id=run_id or _run_id(),
        goal=goal,
        agents=agents,
        broker_dir=broker_dir,
        max_parallel=max_parallel,
        topological_layers=layers,
        ready_batches=ready_batches,
    )


def _topological_agent_layers(agents: List[CodexSubagentSpec]) -> List[List[str]]:
    specs_by_id: Dict[str, CodexSubagentSpec] = {}
    for spec in agents:
        if not spec.id:
            raise ValueError("agent id is required")
        if spec.id in specs_by_id:
            raise ValueError(f"duplicate agent id: {spec.id}")
        specs_by_id[spec.id] = spec

    order = {spec.id: index for index, spec in enumerate(agents)}
    dependents: Dict[str, List[str]] = {spec.id: [] for spec in agents}
    indegree: Dict[str, int] = {spec.id: 0 for spec in agents}
    for spec in agents:
        seen_deps = set()
        for dep_id in spec.dependencies:
            if not dep_id:
                raise ValueError(f"agent {spec.id} has an empty dependency id")
            if dep_id in seen_deps:
                raise ValueError(f"agent {spec.id} has duplicate dependency: {dep_id}")
            if dep_id not in specs_by_id:
                raise ValueError(f"agent {spec.id} depends on unknown agent id: {dep_id}")
            if dep_id == spec.id:
                raise ValueError(f"agent {spec.id} cannot depend on itself")
            seen_deps.add(dep_id)
            dependents[dep_id].append(spec.id)
            indegree[spec.id] += 1

    ready = [spec.id for spec in agents if indegree[spec.id] == 0]
    layers: List[List[str]] = []
    processed: List[str] = []
    while ready:
        layer = ready
        layers.append(layer)
        next_ready: List[str] = []
        for agent_id in layer:
            processed.append(agent_id)
            for child_id in dependents[agent_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    next_ready.append(child_id)
        ready = sorted(next_ready, key=lambda agent_id: order[agent_id])

    if len(processed) != len(agents):
        cycle_ids = [agent_id for agent_id, degree in indegree.items() if degree > 0]
        raise ValueError("cycle detected in CodexSubagentSpec.dependencies: " + ", ".join(cycle_ids))
    return layers


def _ready_batches(layers: List[List[str]], max_parallel: int) -> List[List[str]]:
    batches: List[List[str]] = []
    for layer in layers:
        for index in range(0, len(layer), max_parallel):
            batches.append(layer[index:index + max_parallel])
    return batches


def build_subagent_prompt(
    plan: CodexAppDispatchPlan,
    spec: CodexSubagentSpec,
    dependency_outputs: Optional[Dict[str, CodexSubagentEnvelope]] = None,
) -> str:
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
        f"Dependency outputs:\n{_format_dependency_outputs(spec, dependency_outputs or {})}\n\n"
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
    _validate_envelope_for_ingest(broker, envelope)
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
            thread_id=thread_id,
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


def complete_dispatch_plan(
    broker: AgentBroker,
    plan: CodexAppDispatchPlan,
    final_answer: str = "",
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a Codex App dispatch plan as a terminal broker workflow."""
    events = broker.list_events(thread_id=plan.run_id)
    completed = sum(1 for event in events if event.kind == "trace" and event.subject == "codex_subagent_completed")
    failed = sum(1 for event in events if event.kind == "trace" and event.subject == "codex_subagent_failed")
    terminal = completed + failed
    if status is None:
        if terminal < len(plan.agents):
            raise ValueError("cannot infer workflow status before all planned agents return")
        status = "failed" if failed else "completed"
    if status not in ("completed", "failed"):
        raise ValueError("status must be completed or failed")

    artifact_ids: List[str] = []
    if final_answer:
        artifact = broker.publish_artifact(
            "orchestrator",
            "final_answer",
            final_answer,
            kind="final_answer",
            metadata={"run_id": plan.run_id},
            thread_id=plan.run_id,
        )
        artifact_ids.append(artifact.id)

    broker.trace(
        "orchestrator",
        "workflow_completed" if status == "completed" else "workflow_failed",
        final_answer or f"Codex App dispatch plan {status}.",
        thread_id=plan.run_id,
        artifact_ids=artifact_ids,
        metadata={
            "backend": "codex_app_bridge",
            "completed": completed,
            "failed": failed,
            "planned_agents": len(plan.agents),
        },
    )
    return broker.to_a2a_task(plan.run_id)


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


def _format_dependency_outputs(
    spec: CodexSubagentSpec,
    dependency_outputs: Dict[str, CodexSubagentEnvelope],
) -> str:
    if not spec.dependencies:
        return "(none)"
    parts: List[str] = []
    for dep_id in spec.dependencies:
        envelope = dependency_outputs.get(dep_id)
        if envelope is None:
            parts.append(f"## {dep_id}\n(status unavailable; parent has not provided this dependency output)")
            continue
        artifact_lines = []
        for artifact in envelope.artifacts[:5]:
            content = artifact.content[:1200]
            artifact_lines.append(f"- {artifact.name} ({artifact.kind}, {artifact.content_type}): {content}")
        parts.append(
            "\n".join([
                f"## {dep_id} ({envelope.status})",
                f"Summary: {envelope.summary or '(no summary)'}",
                f"Error: {envelope.error or '(none)'}",
                "Artifacts:",
                *(artifact_lines or ["- (none)"]),
            ])
        )
    return "\n\n".join(parts)


def _validate_envelope_for_ingest(broker: AgentBroker, envelope: CodexSubagentEnvelope) -> None:
    validate_agent_id(envelope.agent_id, "envelope.agent_id")
    artifact_names = [artifact.name for artifact in envelope.artifacts]
    duplicates = sorted({name for name in artifact_names if artifact_names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate envelope artifact names: {', '.join(duplicates)}")

    known_artifact_names = set(artifact_names)
    for artifact in envelope.artifacts:
        if len(artifact.content) > broker.policy.max_artifact_chars:
            raise ValueError("artifact content exceeds broker policy limit")
        if artifact.content_type not in broker.policy.allowed_content_types:
            raise ValueError(f"content_type not allowed by broker policy: {artifact.content_type}")

    known_agents = {agent.id for agent in broker.list_agents()} | set(broker.policy.system_agents)
    known_agents.add(envelope.agent_id)

    def require_agent(agent_id: Optional[str], field_name: str) -> None:
        if agent_id is None:
            return
        normalized = validate_agent_id(agent_id, field_name)
        if broker.policy.require_registered_agents and normalized not in known_agents:
            raise ValueError(f"{field_name} is not registered: {normalized}")

    def require_artifacts(names: List[str]) -> None:
        missing = [name for name in names if name not in known_artifact_names]
        if missing:
            raise ValueError(f"unknown envelope artifact names: {', '.join(missing)}")

    def require_event_size(subject: str, body: str) -> None:
        if len(subject) > broker.policy.max_subject_chars:
            raise ValueError("event subject exceeds broker policy limit")
        if len(body) > broker.policy.max_body_chars:
            raise ValueError("event body exceeds broker policy limit")

    for message in envelope.messages:
        require_agent(message.to_agent, "to_agent")
        require_artifacts(message.artifact_names)
        require_event_size(message.subject, message.body)
    for handoff in envelope.handoffs:
        require_agent(handoff.to_agent, "to_agent")
        require_artifacts(handoff.artifact_names)
        require_event_size(handoff.subject, handoff.body)
    for request in envelope.review_requests:
        require_agent(request.reviewer, "reviewer")
        require_artifacts(request.artifact_names)
        require_event_size(request.subject, request.body)
    for response in envelope.review_responses:
        require_agent(response.to_agent, "to_agent")
        require_artifacts(response.artifact_names)
        require_event_size(response.subject, response.body)


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
