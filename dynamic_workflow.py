"""Dynamic planner/replanner runtime for Codex CLI swarms.

The runtime starts with a planner decision, fans out real Codex CLI workers,
then asks a replanner whether more workers are needed. It keeps one broker
thread across rounds so the reducer can read the full evidence trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set
import argparse
import json
import os
import re
import subprocess
import time
import uuid

from agent_broker import AgentBroker, validate_agent_id
from broker_reducer import BrokerReductionResult, reduce_broker_thread
from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime, CodexCliSwarmTrace


def _run_id() -> str:
    return f"dynamic_run_{uuid.uuid4().hex[:10]}"


@dataclass
class DynamicAgentPlan:
    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: List[str] = field(default_factory=list)
    workspace_mode: str = "shared"
    write_intent: str = "none"
    base_ref: str = "HEAD"

    def to_spec(self) -> CodexCliAgentSpec:
        return CodexCliAgentSpec(
            id=self.id,
            role=self.role,
            goal=self.goal,
            context=self.context,
            dependencies=list(self.dependencies),
            workspace_mode=self.workspace_mode,
            write_intent=self.write_intent,
            base_ref=self.base_ref,
        )


@dataclass
class PlannerDecision:
    agents: List[DynamicAgentPlan]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    max_parallel: int = 5
    stop_reason: str = ""
    confidence: float = 0.0


@dataclass
class ReplanDecision:
    agents: List[DynamicAgentPlan] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    stop_reason: str = ""
    confidence: float = 0.0


@dataclass
class DynamicWorkflowRound:
    round_index: int
    agent_ids: List[str]
    swarm_run_id: str
    trace_path: str
    completed: int
    failed: int
    duration_s: float


@dataclass
class DynamicWorkflowTrace:
    run_id: str
    goal: str
    max_rounds: int
    max_agents: int
    max_parallel: int
    rounds: List[DynamicWorkflowRound]
    reducer_result: BrokerReductionResult
    broker_thread_id: str
    stop_reason: str
    started_at: float
    completed_at: float

    def summary(self) -> Dict[str, Any]:
        completed = sum(round_trace.completed for round_trace in self.rounds)
        failed = sum(round_trace.failed for round_trace in self.rounds)
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "rounds": len(self.rounds),
            "agents": completed + failed,
            "completed": completed,
            "failed": failed,
            "stop_reason": self.stop_reason,
            "terminal_state": self.reducer_result.terminal_state,
            "broker_thread_id": self.broker_thread_id,
            "duration_s": self.completed_at - self.started_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["reducer_result"] = self.reducer_result.to_dict()
        return payload


PlannerFn = Callable[[str], Dict[str, Any]]
ReplannerFn = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class DynamicWorkflowRuntime:
    """Plan, fan out, replan, and reduce Codex CLI swarm work."""

    def __init__(
        self,
        codex_bin: str = "codex",
        codex_cwd: str = ".",
        workspace_root: str = ".orchestry/dynamic_workflow",
        broker_dir: str = ".orchestry/agent_broker_dynamic",
        max_rounds: int = 3,
        max_agents: int = 50,
        max_parallel: int = 5,
        timeout_s: int = 1800,
        total_timeout_s: Optional[int] = None,
        planner_timeout_s: Optional[int] = None,
        planner_fn: Optional[PlannerFn] = None,
        replanner_fn: Optional[ReplannerFn] = None,
        broker: Optional[AgentBroker] = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if max_agents < 1:
            raise ValueError("max_agents must be at least 1")
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")
        self.codex_bin = codex_bin
        self.codex_cwd = Path(codex_cwd).resolve()
        root = Path(workspace_root).expanduser()
        self.workspace_root = root.resolve() if root.is_absolute() else (self.codex_cwd / root).resolve()
        self.broker = broker or AgentBroker(str((self.codex_cwd / broker_dir).resolve()))
        self.max_rounds = max_rounds
        self.max_agents = max_agents
        self.max_parallel = max_parallel
        self.timeout_s = timeout_s
        self.total_timeout_s = total_timeout_s
        self.planner_timeout_s = planner_timeout_s if planner_timeout_s is not None else min(timeout_s, 120)
        self.planner_fn = planner_fn
        self.replanner_fn = replanner_fn

    def run(self, goal: str) -> DynamicWorkflowTrace:
        if not goal.strip():
            raise ValueError("goal is required")
        run_id = _run_id()
        started_at = time.time()
        self.broker.register_agent("orchestrator", "orchestrator", ["plan", "replan", "reduce"])
        self.broker.trace(
            "orchestrator",
            "dynamic_workflow_started",
            goal,
            thread_id=run_id,
            metadata={
                "max_rounds": self.max_rounds,
                "max_agents": self.max_agents,
                "max_parallel": self.max_parallel,
            },
        )

        planner = self._planner_decision(goal, run_id)
        planned: Dict[str, DynamicAgentPlan] = {agent.id: agent for agent in planner.agents}
        pending = list(planner.agents[: self.max_agents])
        completed_ids: Set[str] = set()
        failed_ids: Set[str] = set()
        rounds: List[DynamicWorkflowRound] = []
        stop_reason = planner.stop_reason or "planner_ready"

        for round_index in range(self.max_rounds):
            if not pending:
                stop_reason = "no_new_agents"
                break
            remaining = self.max_agents - (len(completed_ids) + len(failed_ids))
            if remaining <= 0:
                stop_reason = "max_agents"
                break

            round_agents = pending[:remaining]
            pending = pending[remaining:]
            specs = [
                self._round_spec(agent, completed_ids, failed_ids)
                for agent in round_agents
            ]
            round_parallel = max(1, min(self.max_parallel, planner.max_parallel or self.max_parallel))
            swarm = CodexCliSwarmRuntime(
                codex_bin=self.codex_bin,
                codex_cwd=str(self.codex_cwd),
                workspace_root=str(self.workspace_root / run_id / f"round_{round_index}"),
                max_parallel=round_parallel,
                timeout_s=self.timeout_s,
                total_timeout_s=self.total_timeout_s,
                broker=self.broker,
            )
            swarm_trace = swarm.run(goal, specs, run_id=run_id, terminal_trace=False)
            completed_ids.update(result.agent_id for result in swarm_trace.results if result.status == "completed")
            failed_ids.update(result.agent_id for result in swarm_trace.results if result.status == "failed")
            rounds.append(_round_from_swarm(round_index, swarm_trace))

            if round_index >= self.max_rounds - 1:
                stop_reason = "max_rounds"
                break
            if len(completed_ids) + len(failed_ids) >= self.max_agents:
                stop_reason = "max_agents"
                break

            reduction = reduce_broker_thread(self.broker, run_id, goal)
            replanner = self._replan_decision(goal, reduction, planned, run_id)
            if replanner.stop_reason == "ready_for_reducer":
                stop_reason = "ready_for_reducer"
                break
            new_agents = [agent for agent in replanner.agents if agent.id not in planned]
            if not new_agents:
                stop_reason = replanner.stop_reason or "no_new_agents"
                break
            for agent in new_agents:
                planned[agent.id] = agent
            pending.extend(new_agents)
            stop_reason = replanner.stop_reason or "replanned"

        reducer_result = reduce_broker_thread(self.broker, run_id, goal)
        final_artifact = self.broker.publish_artifact(
            "orchestrator",
            "final_answer",
            reducer_result.final_answer,
            kind="final_answer",
            content_type="text/markdown",
            thread_id=run_id,
            metadata={"terminal_state": reducer_result.terminal_state, "stop_reason": stop_reason},
        )
        subject = "workflow_failed" if reducer_result.terminal_state == "failed" else "workflow_completed"
        self.broker.trace(
            "orchestrator",
            subject,
            reducer_result.final_answer[:1000],
            thread_id=run_id,
            artifact_ids=[final_artifact.id],
            metadata={
                "backend": "dynamic_workflow",
                "terminal_state": reducer_result.terminal_state,
                "stop_reason": stop_reason,
            },
        )
        completed_at = time.time()
        trace = DynamicWorkflowTrace(
            run_id=run_id,
            goal=goal,
            max_rounds=self.max_rounds,
            max_agents=self.max_agents,
            max_parallel=self.max_parallel,
            rounds=rounds,
            reducer_result=reducer_result,
            broker_thread_id=run_id,
            stop_reason=stop_reason,
            started_at=started_at,
            completed_at=completed_at,
        )
        trace_path = self.workspace_root / run_id / "dynamic_trace.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace.to_dict(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return trace

    def _planner_decision(self, goal: str, run_id: str) -> PlannerDecision:
        payload = self.planner_fn(goal) if self.planner_fn else self._run_codex_json_worker("planner", _planner_prompt(goal), run_id)
        return parse_planner_decision(payload)

    def _replan_decision(
        self,
        goal: str,
        reduction: BrokerReductionResult,
        planned: Dict[str, DynamicAgentPlan],
        run_id: str,
    ) -> ReplanDecision:
        snapshot = {
            "reducer": reduction.to_dict(),
            "planned_agent_ids": sorted(planned),
        }
        payload = (
            self.replanner_fn(goal, snapshot)
            if self.replanner_fn
            else self._run_codex_json_worker("replanner", _replanner_prompt(goal, snapshot), run_id)
        )
        return parse_replan_decision(payload, existing_agent_ids=set(planned))

    def _run_codex_json_worker(self, role: str, prompt: str, run_id: str) -> Dict[str, Any]:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        worker_dir = self.workspace_root / run_id / f"{role}_{uuid.uuid4().hex[:8]}"
        worker_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = worker_dir / "prompt.md"
        output_path = worker_dir / "last_message.txt"
        stdout_path = worker_dir / "stdout.txt"
        stderr_path = worker_dir / "stderr.txt"
        command_path = worker_dir / "command.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        command = [
            self.codex_bin,
            "exec",
            "--cd",
            str(self.codex_cwd),
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--ephemeral",
            "--output-last-message",
            str(output_path),
            "-",
        ]
        command_path.write_text(json.dumps(command, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        self.broker.trace(
            "orchestrator",
            f"dynamic_{role}_started",
            f"Started {role} JSON worker.",
            thread_id=run_id,
            metadata={
                "worker_dir": str(worker_dir),
                "prompt_path": str(prompt_path),
                "output_path": str(output_path),
                "timeout_s": self.planner_timeout_s,
            },
        )
        try:
            with prompt_path.open("r", encoding="utf-8") as stdin:
                completed = subprocess.run(
                    command,
                    cwd=str(self.codex_cwd),
                    env=os.environ.copy(),
                    stdin=stdin,
                    capture_output=True,
                    text=True,
                    timeout=self.planner_timeout_s,
                )
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr_text = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
            stdout_path.write_text(stdout_text, encoding="utf-8")
            stderr_path.write_text(stderr_text, encoding="utf-8")
            error = f"codex {role} timed out after {self.planner_timeout_s}s"
            artifact = self.broker.publish_artifact(
                "orchestrator",
                f"{role}_failure",
                "\n".join([error, f"worker_dir={worker_dir}", f"stderr={stderr_text[:4000]}"]),
                kind="error",
                thread_id=run_id,
            )
            self.broker.trace(
                "orchestrator",
                f"dynamic_{role}_failed",
                error,
                thread_id=run_id,
                artifact_ids=[artifact.id],
                metadata={"worker_dir": str(worker_dir), "timeout_s": self.planner_timeout_s},
            )
            raise RuntimeError(error) from exc

        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        raw = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        if completed.returncode != 0:
            error = completed.stderr.strip() or f"codex {role} exited with {completed.returncode}"
            artifact = self.broker.publish_artifact(
                "orchestrator",
                f"{role}_failure",
                "\n".join([error, f"worker_dir={worker_dir}"]),
                kind="error",
                thread_id=run_id,
            )
            self.broker.trace(
                "orchestrator",
                f"dynamic_{role}_failed",
                error,
                thread_id=run_id,
                artifact_ids=[artifact.id],
                metadata={"worker_dir": str(worker_dir), "returncode": completed.returncode},
            )
            raise RuntimeError(error)
        self.broker.trace(
            "orchestrator",
            f"dynamic_{role}_completed",
            f"Completed {role} JSON worker.",
            thread_id=run_id,
            metadata={"worker_dir": str(worker_dir), "output_path": str(output_path)},
        )
        return _load_json_object(raw)

    def _round_spec(
        self,
        agent: DynamicAgentPlan,
        completed_ids: Set[str],
        failed_ids: Set[str],
    ) -> CodexCliAgentSpec:
        if any(dep_id in failed_ids for dep_id in agent.dependencies):
            context = agent.context + "\n\nOne or more dependencies failed in previous rounds; inspect broker evidence before proceeding."
        else:
            context = agent.context
        spec = agent.to_spec()
        spec.dependencies = [dep_id for dep_id in agent.dependencies if dep_id not in completed_ids and dep_id not in failed_ids]
        spec.context = context
        return spec


def parse_planner_decision(payload: Any) -> PlannerDecision:
    data = _ensure_object(payload)
    agents = _parse_agents(data.get("agents"), existing_agent_ids=set())
    deps = _dependencies_from(data, agents)
    max_parallel = _positive_int(data.get("max_parallel", 5), "max_parallel")
    return PlannerDecision(
        agents=agents,
        dependencies=deps,
        max_parallel=max_parallel,
        stop_reason=str(data.get("stop_reason", "")),
        confidence=float(data.get("confidence", 0.0) or 0.0),
    )


def parse_replan_decision(payload: Any, existing_agent_ids: Optional[Set[str]] = None) -> ReplanDecision:
    existing_agent_ids = existing_agent_ids or set()
    data = _ensure_object(payload)
    agents = _parse_agents(data.get("agents", []), existing_agent_ids=existing_agent_ids)
    deps = _dependencies_from(data, agents, existing_agent_ids=existing_agent_ids)
    return ReplanDecision(
        agents=agents,
        dependencies=deps,
        stop_reason=str(data.get("stop_reason", "")),
        confidence=float(data.get("confidence", 0.0) or 0.0),
    )


def _parse_agents(raw_agents: Any, existing_agent_ids: Set[str]) -> List[DynamicAgentPlan]:
    if not isinstance(raw_agents, list):
        raise ValueError("planner JSON must include agents[]")
    agents: List[DynamicAgentPlan] = []
    ids: Set[str] = set()
    for raw in raw_agents:
        if not isinstance(raw, dict):
            raise ValueError("each agent must be an object")
        missing = [key for key in ("id", "role", "goal") if not str(raw.get(key, "")).strip()]
        if missing:
            raise ValueError("agent is missing required fields: " + ", ".join(missing))
        agent_id = validate_agent_id(str(raw["id"]))
        if agent_id in ids or agent_id in existing_agent_ids:
            raise ValueError(f"duplicate agent id: {agent_id}")
        ids.add(agent_id)
        deps = [validate_agent_id(str(dep), "dependency") for dep in raw.get("dependencies", [])]
        agents.append(
            DynamicAgentPlan(
                id=agent_id,
                role=str(raw["role"]),
                goal=str(raw["goal"]),
                context=str(raw.get("context", "")),
                dependencies=deps,
                workspace_mode=str(raw.get("workspace_mode", "shared")),
                write_intent=str(raw.get("write_intent", "none")),
                base_ref=str(raw.get("base_ref", "HEAD")),
            )
        )
    known = ids | existing_agent_ids
    for agent in agents:
        for dep_id in agent.dependencies:
            if dep_id not in known:
                raise ValueError(f"agent {agent.id} depends on unknown agent id: {dep_id}")
            if dep_id == agent.id:
                raise ValueError(f"agent {agent.id} cannot depend on itself")
    return agents


def _dependencies_from(
    data: Dict[str, Any],
    agents: List[DynamicAgentPlan],
    existing_agent_ids: Optional[Set[str]] = None,
) -> Dict[str, List[str]]:
    dependencies = {agent.id: list(agent.dependencies) for agent in agents}
    raw = data.get("dependencies", {})
    if not isinstance(raw, dict):
        raise ValueError("dependencies must be an object when provided")
    known = {agent.id for agent in agents} | (existing_agent_ids or set())
    for agent_id, deps in raw.items():
        agent_id = validate_agent_id(str(agent_id))
        if agent_id not in known:
            raise ValueError(f"dependencies reference unknown agent id: {agent_id}")
        if not isinstance(deps, list):
            raise ValueError(f"dependencies for {agent_id} must be a list")
        parsed = [validate_agent_id(str(dep), "dependency") for dep in deps]
        for dep_id in parsed:
            if dep_id not in known:
                raise ValueError(f"agent {agent_id} depends on unknown agent id: {dep_id}")
        dependencies[agent_id] = parsed
    for agent in agents:
        agent.dependencies = list(dependencies.get(agent.id, agent.dependencies))
    return dependencies


def _positive_int(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except Exception as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if number < 1:
        raise ValueError(f"{field_name} must be at least 1")
    return number


def _ensure_object(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        payload = _load_json_object(payload)
    if not isinstance(payload, dict):
        raise ValueError("planner output must be a JSON object")
    return payload


def _load_json_object(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _round_from_swarm(round_index: int, trace: CodexCliSwarmTrace) -> DynamicWorkflowRound:
    summary = trace.summary()
    return DynamicWorkflowRound(
        round_index=round_index,
        agent_ids=[result.agent_id for result in trace.results],
        swarm_run_id=trace.run_id,
        trace_path=trace.trace_path,
        completed=int(summary["completed"]),
        failed=int(summary["failed"]),
        duration_s=float(summary["duration_s"]),
    )


def _planner_prompt(goal: str) -> str:
    return (
        "You are the oh-my-Dynamic planner. Return exactly one JSON object.\n"
        "Schema: {\"agents\":[{\"id\":\"agent_id\",\"role\":\"role\",\"goal\":\"goal\","
        "\"context\":\"optional\",\"dependencies\":[]}],\"dependencies\":{},"
        "\"max_parallel\":5,\"stop_reason\":\"\",\"confidence\":0.0}\n\n"
        f"Goal:\n{goal}\n"
    )


def _replanner_prompt(goal: str, snapshot: Dict[str, Any]) -> str:
    return (
        "You are the oh-my-Dynamic replanner. Return exactly one JSON object.\n"
        "Return new agents only, or stop_reason=\"ready_for_reducer\" when the broker evidence is enough.\n"
        "Schema: {\"agents\":[],\"dependencies\":{},\"stop_reason\":\"ready_for_reducer\",\"confidence\":0.0}\n\n"
        f"Goal:\n{goal}\n\n"
        f"Broker snapshot:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an oh-my-Dynamic planner/replanner dynamic workflow.")
    parser.add_argument("goal", nargs="?", help="Workflow goal to plan, fan out, replan, and reduce.")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--max-agents", type=int, default=50)
    parser.add_argument("--max-parallel", type=int, default=5)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--cd", default=".")
    parser.add_argument("--workspace-root", default=".orchestry/dynamic_workflow")
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker_dynamic")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--total-timeout-s", type=int, default=None)
    parser.add_argument("--planner-timeout-s", type=int, default=None, help="Timeout for planner/replanner codex exec JSON workers.")
    args = parser.parse_args()
    if not args.goal:
        parser.print_help()
        return
    runtime = DynamicWorkflowRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=args.cd,
        workspace_root=args.workspace_root,
        broker_dir=args.broker_dir,
        max_rounds=args.max_rounds,
        max_agents=args.max_agents,
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        total_timeout_s=args.total_timeout_s,
        planner_timeout_s=args.planner_timeout_s,
    )
    trace = runtime.run(args.goal)
    print(json.dumps(trace.summary(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
