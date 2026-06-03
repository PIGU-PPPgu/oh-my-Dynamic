"""
Sandboxed fan-out runtime prototype.

This module implements the runtime mechanics oh-my-Dynamic wants Codex App to
support natively: many isolated worker agents, explicit tool grants, per-agent
context, concurrent scheduling, trace capture, and reducer synthesis.

It is not a Codex App internal subagent API. It is a local reference runtime
that makes the desired behavior executable today.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
import shutil
import threading
import time
import uuid

from agent_broker import AgentBroker


LLMFn = Callable[[str, str], str]


def _now() -> str:
    return datetime.now().isoformat()


def _run_id() -> str:
    return f"run_{uuid.uuid4().hex[:10]}"


@dataclass
class ToolGrant:
    """Least-privilege tool grant for a worker."""

    name: str
    scope: str = "read-only"
    reason: str = ""


@dataclass
class AgentSandbox:
    """Filesystem sandbox assigned to one worker."""

    root: str
    writable: bool = True
    network: bool = False


@dataclass
class AgentSpec:
    """Single isolated worker agent specification."""

    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: List[str] = field(default_factory=list)
    tool_grants: List[ToolGrant] = field(default_factory=list)

    @classmethod
    def create(cls, role: str, goal: str, **kwargs) -> "AgentSpec":
        return cls(id=f"agent_{uuid.uuid4().hex[:8]}", role=role, goal=goal, **kwargs)


@dataclass
class AgentResult:
    """Structured result from one worker."""

    agent_id: str
    role: str
    status: str
    output: str
    sandbox: AgentSandbox
    tool_grants: List[ToolGrant]
    started_at: str
    completed_at: str
    duration_s: float
    error: str = ""
    thread_name: str = ""
    artifact_ids: List[str] = field(default_factory=list)
    broker_event_ids: List[str] = field(default_factory=list)


@dataclass
class WorkflowTrace:
    """Complete fan-out/reduce trace."""

    run_id: str
    goal: str
    max_agents: int
    started_at: str
    completed_at: str
    duration_s: float
    results: List[AgentResult]
    final_answer: str
    sandbox_root: str
    broker_thread_id: str = ""
    broker_event_count: int = 0

    def summary(self) -> Dict:
        completed = sum(1 for r in self.results if r.status == "completed")
        failed = sum(1 for r in self.results if r.status == "failed")
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "agents": len(self.results),
            "completed": completed,
            "failed": failed,
            "duration_s": self.duration_s,
            "sandbox_root": self.sandbox_root,
            "broker_thread_id": self.broker_thread_id,
            "broker_event_count": self.broker_event_count,
        }

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "max_agents": self.max_agents,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_s": self.duration_s,
            "results": [asdict(r) for r in self.results],
            "final_answer": self.final_answer,
            "sandbox_root": self.sandbox_root,
            "broker_thread_id": self.broker_thread_id,
            "broker_event_count": self.broker_event_count,
        }


class SandboxedFanoutRuntime:
    """Local prototype for native dynamic workflow fan-out."""

    def __init__(
        self,
        llm_fn: LLMFn,
        workspace_root: str = ".orchestry/native_runtime",
        max_workers: int = 32,
        keep_sandboxes: bool = True,
        broker: Optional[AgentBroker] = None,
    ) -> None:
        self.llm_fn = llm_fn
        self.workspace_root = Path(workspace_root)
        self.max_workers = max_workers
        self.keep_sandboxes = keep_sandboxes
        self.broker = broker

    def run(
        self,
        goal: str,
        agents: List[AgentSpec],
        reducer_prompt: Optional[str] = None,
    ) -> WorkflowTrace:
        if not agents:
            raise ValueError("At least one AgentSpec is required")
        if len(agents) > self.max_workers:
            raise ValueError(f"Requested {len(agents)} agents, max_workers={self.max_workers}")

        run_id = _run_id()
        started_at = _now()
        start = time.time()
        sandbox_root = self.workspace_root / run_id
        sandbox_root.mkdir(parents=True, exist_ok=True)

        if self.broker:
            self.broker.register_agent("orchestrator", "orchestrator", ["plan", "reduce"])
            self.broker.trace(
                "orchestrator",
                "workflow_started",
                goal,
                thread_id=run_id,
                metadata={"max_agents": len(agents), "max_workers": self.max_workers},
            )
            for spec in agents:
                self.broker.register_agent(
                    spec.id,
                    spec.role,
                    [grant.name for grant in spec.tool_grants],
                    metadata={
                        "goal": spec.goal,
                        "dependencies": spec.dependencies,
                    },
                )

        results: List[AgentResult] = []
        result_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as pool:
            futures = [
                pool.submit(self._run_agent, goal, spec, sandbox_root / spec.id)
                for spec in agents
            ]
            for future in as_completed(futures):
                result = future.result()
                with result_lock:
                    results.append(result)

        results.sort(key=lambda r: r.agent_id)
        final_answer = self._reduce(goal, results, reducer_prompt)
        final_artifact_ids: List[str] = []
        if self.broker:
            artifact = self.broker.publish_artifact(
                "orchestrator",
                "final_answer",
                final_answer,
                kind="final_answer",
                metadata={"run_id": run_id},
            )
            final_artifact_ids.append(artifact.id)
            self.broker.trace(
                "orchestrator",
                "workflow_completed",
                f"Workflow completed with {len(results)} worker results.",
                thread_id=run_id,
                artifact_ids=final_artifact_ids,
                metadata={
                    "completed": sum(1 for r in results if r.status == "completed"),
                    "failed": sum(1 for r in results if r.status == "failed"),
                },
            )
        completed_at = _now()
        broker_event_count = len(self.broker.list_events(thread_id=run_id)) if self.broker else 0
        trace = WorkflowTrace(
            run_id=run_id,
            goal=goal,
            max_agents=self.max_workers,
            started_at=started_at,
            completed_at=completed_at,
            duration_s=time.time() - start,
            results=results,
            final_answer=final_answer,
            sandbox_root=str(sandbox_root.resolve()),
            broker_thread_id=run_id if self.broker else "",
            broker_event_count=broker_event_count,
        )

        if not self.keep_sandboxes:
            shutil.rmtree(sandbox_root, ignore_errors=True)

        return trace

    def _run_agent(self, workflow_goal: str, spec: AgentSpec, sandbox_path: Path) -> AgentResult:
        sandbox_path.mkdir(parents=True, exist_ok=True)
        started_at = _now()
        start = time.time()
        sandbox = AgentSandbox(root=str(sandbox_path.resolve()))
        thread_name = threading.current_thread().name
        broker_event_ids: List[str] = []
        artifact_ids: List[str] = []

        if self.broker:
            event = self.broker.trace(
                spec.id,
                "agent_started",
                spec.goal,
                thread_id=self._current_thread_id(sandbox_path),
                metadata={"role": spec.role, "sandbox": sandbox.root},
            )
            broker_event_ids.append(event.id)

        grants = "\n".join(
            f"- {grant.name} ({grant.scope}): {grant.reason or 'no reason provided'}"
            for grant in spec.tool_grants
        ) or "- none"

        system_prompt = (
            "You are an isolated worker agent in a dynamic workflow runtime. "
            "Use only the context and tool grants provided. Return a concise, "
            "evidence-oriented result for the reducer."
        )
        user_prompt = (
            f"Workflow goal:\n{workflow_goal}\n\n"
            f"Agent id: {spec.id}\n"
            f"Role: {spec.role}\n"
            f"Agent goal:\n{spec.goal}\n\n"
            f"Isolated context:\n{spec.context or '(none)'}\n\n"
            f"Sandbox path:\n{sandbox.root}\n\n"
            f"Tool grants:\n{grants}\n"
        )

        try:
            output = self.llm_fn(system_prompt, user_prompt)
            status = "completed"
            error = ""
            if self.broker:
                artifact = self.broker.publish_artifact(
                    spec.id,
                    f"{spec.id}_result",
                    output,
                    kind="worker_result",
                    metadata={"role": spec.role, "sandbox": sandbox.root},
                )
                artifact_ids.append(artifact.id)
                event = self.broker.send_message(
                    spec.id,
                    "orchestrator",
                    f"Worker completed: {spec.id}",
                    output[:2000],
                    thread_id=self._current_thread_id(sandbox_path),
                    artifact_ids=[artifact.id],
                    metadata={"status": status, "role": spec.role},
                )
                broker_event_ids.append(event.id)
        except Exception as exc:
            output = ""
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            if self.broker:
                event = self.broker.trace(
                    spec.id,
                    "agent_failed",
                    error,
                    thread_id=self._current_thread_id(sandbox_path),
                    metadata={"role": spec.role, "sandbox": sandbox.root},
                )
                broker_event_ids.append(event.id)

        return AgentResult(
            agent_id=spec.id,
            role=spec.role,
            status=status,
            output=output,
            sandbox=sandbox,
            tool_grants=spec.tool_grants,
            started_at=started_at,
            completed_at=_now(),
            duration_s=time.time() - start,
            error=error,
            thread_name=thread_name,
            artifact_ids=artifact_ids,
            broker_event_ids=broker_event_ids,
        )

    def _current_thread_id(self, sandbox_path: Path) -> str:
        return sandbox_path.parent.name

    def _reduce(
        self,
        goal: str,
        results: List[AgentResult],
        reducer_prompt: Optional[str],
    ) -> str:
        summaries = []
        for result in results:
            summaries.append(
                f"## {result.agent_id} ({result.role}, {result.status})\n"
                f"Sandbox: {result.sandbox.root}\n"
                f"Tools: {', '.join(g.name for g in result.tool_grants) or 'none'}\n"
                f"Output:\n{result.output or result.error}"
            )

        system_prompt = reducer_prompt or (
            "You are the reducer for a dynamic workflow. Synthesize worker "
            "outputs, call out failures or contradictions, and provide a final answer."
        )
        user_prompt = f"Workflow goal:\n{goal}\n\nWorker results:\n\n" + "\n\n".join(summaries)
        return self.llm_fn(system_prompt, user_prompt)
