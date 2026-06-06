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

from oh_my_dynamic.broker.agent_broker import AgentBroker


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
    topological_layers: List[List[str]] = field(default_factory=list)
    ready_batches: List[List[str]] = field(default_factory=list)
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
            "topological_layers": self.topological_layers,
            "ready_batches": self.ready_batches,
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
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        topological_layers = self._topological_layers(agents)
        topological_layer_ids = [[spec.id for spec in layer] for layer in topological_layers]
        ready_batches = self._ready_batches(topological_layer_ids, self.max_workers)

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

        results_by_id: Dict[str, AgentResult] = {}

        for layer in topological_layers:
            runnable: List[AgentSpec] = []
            for spec in layer:
                failed_deps = [
                    dep_id
                    for dep_id in spec.dependencies
                    if results_by_id[dep_id].status != "completed"
                ]
                if failed_deps:
                    result = self._dependency_failed_result(
                        spec,
                        sandbox_root / spec.id,
                        failed_deps,
                        results_by_id,
                    )
                    results_by_id[spec.id] = result
                else:
                    runnable.append(spec)

            if not runnable:
                continue

            for batch in self._agent_batches(runnable, self.max_workers):
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {
                        pool.submit(
                            self._run_agent,
                            goal,
                            spec,
                            sandbox_root / spec.id,
                            {dep_id: results_by_id[dep_id] for dep_id in spec.dependencies},
                        ): spec
                        for spec in batch
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        results_by_id[result.agent_id] = result

        result_order = {
            spec.id: index
            for index, spec in enumerate(spec for layer in topological_layers for spec in layer)
        }
        results = sorted(results_by_id.values(), key=lambda result: result_order[result.agent_id])
        final_answer = self._reduce(goal, results, reducer_prompt)
        final_artifact_ids: List[str] = []
        if self.broker:
            artifact = self.broker.publish_artifact(
                "orchestrator",
                "final_answer",
                final_answer,
                kind="final_answer",
                metadata={"run_id": run_id},
                thread_id=run_id,
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
            max_agents=len(agents),
            started_at=started_at,
            completed_at=completed_at,
            duration_s=time.time() - start,
            results=results,
            final_answer=final_answer,
            sandbox_root=str(sandbox_root.resolve()),
            topological_layers=topological_layer_ids,
            ready_batches=ready_batches,
            broker_thread_id=run_id if self.broker else "",
            broker_event_count=broker_event_count,
        )

        if not self.keep_sandboxes:
            shutil.rmtree(sandbox_root, ignore_errors=True)

        return trace

    def _run_agent(
        self,
        workflow_goal: str,
        spec: AgentSpec,
        sandbox_path: Path,
        dependency_results: Optional[Dict[str, AgentResult]] = None,
    ) -> AgentResult:
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
                metadata={
                    "role": spec.role,
                    "sandbox": sandbox.root,
                    "dependencies": spec.dependencies,
                },
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
            f"Dependency outputs:\n{self._format_dependency_context(spec, dependency_results or {})}\n\n"
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
                    thread_id=self._current_thread_id(sandbox_path),
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

    def _dependency_failed_result(
        self,
        spec: AgentSpec,
        sandbox_path: Path,
        failed_deps: List[str],
        results_by_id: Dict[str, AgentResult],
    ) -> AgentResult:
        sandbox_path.mkdir(parents=True, exist_ok=True)
        started_at = _now()
        sandbox = AgentSandbox(root=str(sandbox_path.resolve()))
        details = []
        for dep_id in failed_deps:
            dep = results_by_id[dep_id]
            details.append(f"{dep_id} ({dep.status}: {dep.error or dep.output[:200]})")
        error = f"Dependency failed for {spec.id}: " + "; ".join(details)
        broker_event_ids: List[str] = []
        if self.broker:
            event = self.broker.trace(
                spec.id,
                "agent_dependency_failed",
                error,
                thread_id=self._current_thread_id(sandbox_path),
                metadata={"role": spec.role, "dependencies": spec.dependencies, "failed_dependencies": failed_deps},
            )
            broker_event_ids.append(event.id)
        return AgentResult(
            agent_id=spec.id,
            role=spec.role,
            status="failed",
            output="",
            sandbox=sandbox,
            tool_grants=spec.tool_grants,
            started_at=started_at,
            completed_at=_now(),
            duration_s=0.0,
            error=error,
            thread_name=threading.current_thread().name,
            broker_event_ids=broker_event_ids,
        )

    def _current_thread_id(self, sandbox_path: Path) -> str:
        return sandbox_path.parent.name

    def _format_dependency_context(
        self,
        spec: AgentSpec,
        dependency_results: Dict[str, AgentResult],
    ) -> str:
        if not spec.dependencies:
            return "(none)"
        parts = []
        for dep_id in spec.dependencies:
            result = dependency_results.get(dep_id)
            if result is None:
                parts.append(f"## {dep_id}\n(status unavailable)")
                continue
            body = result.output or result.error or "(no output)"
            parts.append(
                f"## {dep_id} ({result.role}, {result.status})\n"
                f"{body[:4000]}"
            )
        return "\n\n".join(parts)

    def _topological_layers(self, agents: List[AgentSpec]) -> List[List[AgentSpec]]:
        specs_by_id: Dict[str, AgentSpec] = {}
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
        layers: List[List[AgentSpec]] = []
        processed: List[str] = []
        while ready:
            layer_ids = ready
            layers.append([specs_by_id[agent_id] for agent_id in layer_ids])
            next_ready: List[str] = []
            for agent_id in layer_ids:
                processed.append(agent_id)
                for child_id in dependents[agent_id]:
                    indegree[child_id] -= 1
                    if indegree[child_id] == 0:
                        next_ready.append(child_id)
            ready = sorted(next_ready, key=lambda agent_id: order[agent_id])

        if len(processed) != len(agents):
            cycle_ids = [agent_id for agent_id, degree in indegree.items() if degree > 0]
            raise ValueError("cycle detected in AgentSpec.dependencies: " + ", ".join(cycle_ids))
        return layers

    def _ready_batches(self, layers: List[List[str]], max_workers: int) -> List[List[str]]:
        batches: List[List[str]] = []
        for layer in layers:
            for index in range(0, len(layer), max_workers):
                batches.append(layer[index:index + max_workers])
        return batches

    def _agent_batches(self, agents: List[AgentSpec], max_workers: int) -> List[List[AgentSpec]]:
        return [agents[index:index + max_workers] for index in range(0, len(agents), max_workers)]

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
