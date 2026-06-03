"""
Agent broker for controlled multi-agent collaboration.

This module is the local contract oh-my-Dynamic can use for A2A-style
coordination: messages, artifacts, task handoffs, review requests, and audit
trace events are stored in a deterministic filesystem-backed broker.

It does not call any LLM by itself. Codex App subagents can use the contract
through the parent orchestrator, while local isolated workers can write the same
events during `native_runtime.py` fan-out.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import threading
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class BrokerAgent:
    """Agent registered with the broker."""

    id: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()


@dataclass
class BrokerArtifact:
    """Artifact produced by an agent and referenced by later events."""

    id: str
    producer: str
    name: str
    kind: str
    content: str
    content_type: str = "text/plain"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _id("artifact")
        if not self.created_at:
            self.created_at = _now_iso()


@dataclass
class BrokerEvent:
    """A2A-style event envelope stored in the broker trace."""

    id: str
    kind: str
    from_agent: str
    to_agent: Optional[str]
    subject: str
    body: str = ""
    thread_id: str = "default"
    task_id: str = ""
    artifact_ids: List[str] = field(default_factory=list)
    status: str = "pending"
    parent_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _id(self.kind)
        if not self.created_at:
            self.created_at = _now_iso()


class AgentBroker:
    """
    Filesystem-backed broker for controlled A2A-style agent collaboration.

    The broker writes append-only event and artifact logs plus per-agent inboxes.
    It is intentionally local and transport-agnostic so it can back a future
    HTTP/SSE A2A gateway without changing the workflow contract.
    """

    def __init__(self, base_dir: str = ".orchestry/agent_broker") -> None:
        self.base_dir = Path(base_dir)
        self.inbox_dir = self.base_dir / "inbox"
        self.artifact_dir = self.base_dir / "artifact_blobs"
        self.agents_path = self.base_dir / "agents.json"
        self.events_path = self.base_dir / "events.jsonl"
        self.artifacts_path = self.base_dir / "artifacts.jsonl"
        self._lock = threading.Lock()

        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.agents_path.exists():
            self.agents_path.write_text("{}", encoding="utf-8")
        self.events_path.touch(exist_ok=True)
        self.artifacts_path.touch(exist_ok=True)

    def register_agent(
        self,
        agent_id: str,
        role: str,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerAgent:
        """Register an agent and create its inbox."""
        agent = BrokerAgent(
            id=agent_id,
            role=role,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        with self._lock:
            agents = self._load_agents_unlocked()
            agents[agent.id] = asdict(agent)
            self.agents_path.write_text(
                json.dumps(agents, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._inbox_path(agent.id).touch(exist_ok=True)
        self.trace("broker", "agent_registered", f"Registered {agent.id}", metadata={"agent": asdict(agent)})
        return agent

    def list_agents(self) -> List[BrokerAgent]:
        with self._lock:
            agents = self._load_agents_unlocked()
        return [BrokerAgent(**data) for data in agents.values()]

    def publish_artifact(
        self,
        producer: str,
        name: str,
        content: str,
        kind: str = "text",
        content_type: str = "text/plain",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerArtifact:
        """Store an artifact and return its durable reference."""
        artifact = BrokerArtifact(
            id="",
            producer=producer,
            name=name,
            kind=kind,
            content=content,
            content_type=content_type,
            metadata=metadata or {},
        )
        blob_path = self.artifact_dir / f"{artifact.id}.txt"
        with self._lock:
            blob_path.write_text(content, encoding="utf-8")
            record = asdict(artifact)
            record["blob_path"] = str(blob_path)
            self._append_jsonl_unlocked(self.artifacts_path, record)
        self.trace(
            producer,
            "artifact_published",
            f"Artifact published: {name}",
            artifact_ids=[artifact.id],
            metadata={"kind": kind, "content_type": content_type},
        )
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[BrokerArtifact]:
        for record in self.list_artifacts():
            if record.id == artifact_id:
                return record
        return None

    def list_artifacts(self) -> List[BrokerArtifact]:
        records = self._read_jsonl(self.artifacts_path)
        artifacts = []
        for record in records:
            record = dict(record)
            record.pop("blob_path", None)
            artifacts.append(BrokerArtifact(**record))
        return artifacts

    def send_message(
        self,
        from_agent: str,
        to_agent: Optional[str],
        subject: str,
        body: str,
        thread_id: str = "default",
        task_id: str = "",
        artifact_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerEvent:
        """Send a direct or broadcast message."""
        return self._emit(
            BrokerEvent(
                id="",
                kind="message",
                from_agent=from_agent,
                to_agent=to_agent,
                subject=subject,
                body=body,
                thread_id=thread_id,
                task_id=task_id,
                artifact_ids=artifact_ids or [],
                metadata=metadata or {},
            )
        )

    def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_id: str,
        subject: str,
        body: str,
        artifact_ids: Optional[List[str]] = None,
        thread_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerEvent:
        """Create a task handoff event between agents."""
        return self._emit(
            BrokerEvent(
                id="",
                kind="handoff",
                from_agent=from_agent,
                to_agent=to_agent,
                subject=subject,
                body=body,
                thread_id=thread_id,
                task_id=task_id,
                artifact_ids=artifact_ids or [],
                metadata=metadata or {},
            )
        )

    def request_review(
        self,
        from_agent: str,
        reviewer: str,
        task_id: str,
        subject: str,
        body: str,
        artifact_ids: Optional[List[str]] = None,
        thread_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerEvent:
        """Ask a reviewer agent to inspect an artifact or result."""
        return self._emit(
            BrokerEvent(
                id="",
                kind="review_request",
                from_agent=from_agent,
                to_agent=reviewer,
                subject=subject,
                body=body,
                thread_id=thread_id,
                task_id=task_id,
                artifact_ids=artifact_ids or [],
                metadata=metadata or {},
            )
        )

    def trace(
        self,
        from_agent: str,
        subject: str,
        body: str,
        thread_id: str = "default",
        task_id: str = "",
        artifact_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrokerEvent:
        """Append an audit-only trace event."""
        return self._emit(
            BrokerEvent(
                id="",
                kind="trace",
                from_agent=from_agent,
                to_agent=None,
                subject=subject,
                body=body,
                thread_id=thread_id,
                task_id=task_id,
                artifact_ids=artifact_ids or [],
                status="recorded",
                metadata=metadata or {},
            ),
            deliver=False,
        )

    def read_inbox(self, agent_id: str, mark_delivered: bool = True) -> List[BrokerEvent]:
        """Read pending events for an agent."""
        inbox = self._inbox_path(agent_id)
        if not inbox.exists():
            return []

        with self._lock:
            records = self._read_jsonl_unlocked(inbox)
            pending = []
            rewritten = []
            for record in records:
                event = BrokerEvent(**record)
                if event.status == "pending":
                    pending.append(event)
                    if mark_delivered:
                        event.status = "delivered"
                rewritten.append(asdict(event))
            if mark_delivered and pending:
                self._write_jsonl_unlocked(inbox, rewritten)
        return pending

    def list_events(
        self,
        kind: Optional[str] = None,
        thread_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[BrokerEvent]:
        """Return audit events, optionally filtered."""
        events = [BrokerEvent(**record) for record in self._read_jsonl(self.events_path)]
        if kind is not None:
            events = [event for event in events if event.kind == kind]
        if thread_id is not None:
            events = [event for event in events if event.thread_id == thread_id]
        if agent_id is not None:
            events = [
                event for event in events
                if event.from_agent == agent_id or event.to_agent == agent_id
            ]
        return events

    def to_a2a_task(self, thread_id: str = "default") -> Dict[str, Any]:
        """Export a broker thread as an A2A-style task snapshot."""
        events = self.list_events(thread_id=thread_id)
        artifacts = {
            artifact.id: artifact
            for artifact in self.list_artifacts()
            if any(artifact.id in event.artifact_ids for event in events)
        }
        state = "working"
        if any(event.kind == "trace" and event.subject == "workflow_completed" for event in events):
            state = "completed"
        if any(event.kind == "trace" and event.subject == "workflow_failed" for event in events):
            state = "failed"
        return {
            "id": thread_id,
            "status": {"state": state, "timestamp": events[-1].created_at if events else _now_iso()},
            "history": [self._event_to_a2a_message(event) for event in events],
            "artifacts": [
                {
                    "artifactId": artifact.id,
                    "name": artifact.name,
                    "parts": [
                        {"kind": "text", "text": artifact.content}
                        if artifact.content_type.startswith("text/")
                        else {"kind": "data", "data": artifact.content}
                    ],
                    "metadata": {
                        "producer": artifact.producer,
                        "kind": artifact.kind,
                        **artifact.metadata,
                    },
                }
                for artifact in artifacts.values()
            ],
        }

    def _emit(self, event: BrokerEvent, deliver: bool = True) -> BrokerEvent:
        with self._lock:
            self._append_jsonl_unlocked(self.events_path, asdict(event))
            if deliver:
                targets = self._resolve_targets_unlocked(event)
                for target in targets:
                    self._append_jsonl_unlocked(self._inbox_path(target), asdict(event))
        return event

    def _resolve_targets_unlocked(self, event: BrokerEvent) -> List[str]:
        if event.to_agent:
            return [event.to_agent]
        agents = list(self._load_agents_unlocked().keys())
        return [agent for agent in agents if agent != event.from_agent]

    def _inbox_path(self, agent_id: str) -> Path:
        return self.inbox_dir / f"{agent_id}.jsonl"

    def _load_agents_unlocked(self) -> Dict[str, Dict[str, Any]]:
        try:
            return json.loads(self.agents_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        with self._lock:
            return self._read_jsonl_unlocked(path)

    def _read_jsonl_unlocked(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def _append_jsonl_unlocked(self, path: Path, record: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write_jsonl_unlocked(self, path: Path, records: List[Dict[str, Any]]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _event_to_a2a_message(self, event: BrokerEvent) -> Dict[str, Any]:
        role = "agent"
        if event.from_agent in ("user", "orchestrator"):
            role = event.from_agent
        return {
            "role": role,
            "parts": [
                {
                    "kind": "text",
                    "text": event.body or event.subject,
                }
            ],
            "metadata": {
                "eventId": event.id,
                "kind": event.kind,
                "from": event.from_agent,
                "to": event.to_agent,
                "subject": event.subject,
                "taskId": event.task_id,
                "artifactIds": event.artifact_ids,
                **event.metadata,
            },
        }
