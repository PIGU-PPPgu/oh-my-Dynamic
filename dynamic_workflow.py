"""Dynamic planner/replanner runtime for Codex CLI swarms.

The runtime starts with a planner decision, fans out real Codex CLI workers,
then asks a replanner whether more workers are needed. It keeps one broker
thread across rounds so the reducer can read the full evidence trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import argparse
import json
import os
import re
import subprocess
import time
import uuid

from agent_broker import AgentBroker, validate_agent_id
from broker_reducer import BrokerReductionResult, reduce_broker_thread
from checkpoint import checkpoint_path, load_checkpoint, save_checkpoint
from codex_cli_swarm import CodexCliAgentSpec, CodexCliSwarmRuntime, CodexCliSwarmTrace
from replan_trigger_policy import ReplanTriggerDecision, ReplanTriggerPolicy
from workflow_config import REPLAN_COMPLETENESS_THRESHOLD
from workflow_events import WorkflowEvent


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
    sandbox: str = "read-only"
    extra_args: List[str] = field(default_factory=list)

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
            sandbox=self.sandbox,
            extra_args=list(self.extra_args),
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
    replan_trigger_records: List[Dict[str, Any]] = field(default_factory=list)

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
            "replan_triggers": [record for record in self.replan_trigger_records if record.get("replan_triggers")],
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
        checkpoint_dir: str = ".orchestry/checkpoints",
        planner_fn: Optional[PlannerFn] = None,
        replanner_fn: Optional[ReplannerFn] = None,
        broker: Optional[AgentBroker] = None,
        event_callback: Optional[Callable[[WorkflowEvent], None]] = None,
        sandbox: str = "read-only",
        codex_extra_args: Optional[List[str]] = None,
        planner_sandbox: str = "read-only",
        replan_trigger_policy: Optional[ReplanTriggerPolicy] = None,
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
        self.checkpoint_dir = str((self.codex_cwd / checkpoint_dir).resolve()) if not Path(checkpoint_dir).is_absolute() else checkpoint_dir
        self.planner_fn = planner_fn
        self.replanner_fn = replanner_fn
        self.event_callback = event_callback
        self.sandbox = sandbox
        self.codex_extra_args = list(codex_extra_args or [])
        self.planner_sandbox = planner_sandbox
        self.replan_trigger_policy = replan_trigger_policy

    def run(
        self,
        goal: str = "",
        run_id: Optional[str] = None,
        resume_run_id: str = "",
        event_callback: Optional[Callable[[WorkflowEvent], None]] = None,
    ) -> DynamicWorkflowTrace:
        callback = event_callback or self.event_callback
        checkpoint_payload: Optional[Dict[str, Any]] = None
        if resume_run_id:
            checkpoint_payload = load_checkpoint(str(checkpoint_path(self.checkpoint_dir, resume_run_id)))
            run_id = str(checkpoint_payload.get("run_id", resume_run_id))
            goal = str(checkpoint_payload.get("goal", goal))
        if not goal.strip():
            raise ValueError("goal is required")
        run_id = run_id or _run_id()
        started_at = time.time()
        self.broker.register_agent("orchestrator", "orchestrator", ["plan", "replan", "reduce"])
        self._emit_event(callback, WorkflowEvent(
            run_id=run_id,
            kind="dynamic_workflow_started",
            subject="dynamic_workflow_started",
            body=goal,
            status="working",
            preview=goal[:200],
            metadata={"resume": bool(resume_run_id)},
        ))
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

        if checkpoint_payload is not None:
            planned = {
                agent.id: agent
                for agent in _plans_from_payload(checkpoint_payload.get("planned_agents", []))
            }
            pending = _plans_from_payload(checkpoint_payload.get("pending_agents", []))
            completed_ids = set(checkpoint_payload.get("completed_agent_ids", []))
            failed_ids = set()
            if not pending:
                pending = [planned[agent_id] for agent_id in checkpoint_payload.get("failed_agent_ids", []) if agent_id in planned]
            rounds = [DynamicWorkflowRound(**item) for item in checkpoint_payload.get("rounds", [])]
            replan_trigger_records = list(checkpoint_payload.get("replan_trigger_records", []))
            stop_reason = str(checkpoint_payload.get("stop_reason", "resumed"))
            planner = PlannerDecision(agents=list(planned.values()), max_parallel=self.max_parallel)
        else:
            planner = self._planner_decision(goal, run_id)
            planned = {agent.id: agent for agent in planner.agents}
            pending = list(planner.agents[: self.max_agents])
            completed_ids = set()
            failed_ids = set()
            rounds = []
            replan_trigger_records = []
            stop_reason = planner.stop_reason or "planner_ready"
            self._save_checkpoint(run_id, goal, planned, pending, completed_ids, failed_ids, rounds, stop_reason, replan_trigger_records)

        for round_index in range(len(rounds), self.max_rounds):
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
                event_callback=callback,
            )
            self._emit_event(callback, WorkflowEvent(
                run_id=run_id,
                kind="round_started",
                subject="round_started",
                body=f"Starting dynamic workflow round {round_index}.",
                status="running",
                metadata={"round_index": round_index, "agent_ids": [agent.id for agent in round_agents]},
            ))
            swarm_trace = swarm.run(goal, specs, run_id=run_id, terminal_trace=False)
            completed_ids.update(result.agent_id for result in swarm_trace.results if result.status == "completed")
            failed_ids.update(result.agent_id for result in swarm_trace.results if result.status == "failed")
            rounds.append(_round_from_swarm(round_index, swarm_trace))
            self._emit_event(callback, WorkflowEvent(
                run_id=run_id,
                kind="round_done",
                subject="round_done",
                body=f"Finished dynamic workflow round {round_index}.",
                status="completed",
                metadata={"round_index": round_index, "completed_agent_ids": sorted(completed_ids), "failed_agent_ids": sorted(failed_ids)},
            ))
            self._save_checkpoint(run_id, goal, planned, pending, completed_ids, failed_ids, rounds, stop_reason, replan_trigger_records)

            if round_index >= self.max_rounds - 1:
                stop_reason = "max_rounds"
                break
            if len(completed_ids) + len(failed_ids) >= self.max_agents:
                stop_reason = "max_agents"
                break

            reduction = reduce_broker_thread(self.broker, run_id, goal)
            trigger_decision = self._replan_trigger_decision(reduction, planned, completed_ids, failed_ids, run_id)
            trigger_record = {"round_index": round_index, **trigger_decision.to_dict()}
            replan_trigger_records.append(trigger_record)
            if trigger_decision.should_replan:
                self.broker.trace(
                    "orchestrator",
                    "replan_trigger_policy",
                    "Deterministic replan trigger policy requested follow-up agents.",
                    thread_id=run_id,
                    metadata=trigger_record,
                )
            replanner = self._replan_decision(goal, reduction, planned, run_id, trigger_decision)
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
            self._save_checkpoint(run_id, goal, planned, pending, completed_ids, failed_ids, rounds, stop_reason, replan_trigger_records)

        reducer_result = reduce_broker_thread(self.broker, run_id, goal)
        self._emit_event(callback, WorkflowEvent(
            run_id=run_id,
            kind="reducer_done",
            subject="reducer_done",
            body=reducer_result.final_answer,
            status=reducer_result.terminal_state,
            preview=reducer_result.final_answer[:200],
            metadata={"artifact_ids": reducer_result.artifact_ids, "stop_reason": stop_reason},
        ))
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
            replan_trigger_records=replan_trigger_records,
        )
        trace_path = self.workspace_root / run_id / "dynamic_trace.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace.to_dict(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        self._save_checkpoint(run_id, goal, planned, pending, completed_ids, failed_ids, rounds, stop_reason, replan_trigger_records)
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
        trigger_decision: Optional[ReplanTriggerDecision] = None,
    ) -> ReplanDecision:
        snapshot = {
            "reducer": reduction.to_dict(),
            "planned_agent_ids": sorted(planned),
            "replan_trigger_policy": trigger_decision.to_dict() if trigger_decision else {},
        }
        payload = (
            self.replanner_fn(goal, snapshot)
            if self.replanner_fn
            else self._run_codex_json_worker("replanner", _replanner_prompt(goal, snapshot), run_id)
        )
        return parse_replan_decision(payload, existing_agent_ids=set(planned))

    def _replan_trigger_decision(
        self,
        reduction: BrokerReductionResult,
        planned: Dict[str, DynamicAgentPlan],
        completed_ids: Set[str],
        failed_ids: Set[str],
        run_id: str,
    ) -> ReplanTriggerDecision:
        if self.replan_trigger_policy is None:
            return ReplanTriggerDecision()
        return self.replan_trigger_policy.evaluate(
            reduction,
            [asdict(agent) for agent in planned.values()],
            completed_ids,
            failed_ids,
            low_score_agents=self._low_score_agents(run_id),
        )

    def _low_score_agents(self, run_id: str) -> List[str]:
        agents: List[str] = []
        for event in self.broker.list_events(thread_id=run_id):
            try:
                score = float(event.metadata.get("completeness_score", 1.0) or 1.0)
            except (TypeError, ValueError):
                score = 1.0
            if score < REPLAN_COMPLETENESS_THRESHOLD and event.from_agent:
                agents.append(event.from_agent)
        return sorted(set(agents))

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
            self.planner_sandbox,
            "--skip-git-repo-check",
            "--ephemeral",
            "--output-last-message",
            str(output_path),
            *self.codex_extra_args,
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
                "sandbox": self.planner_sandbox,
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

    def _emit_event(
        self,
        callback: Optional[Callable[[WorkflowEvent], None]],
        event: WorkflowEvent,
    ) -> None:
        if callback is not None:
            callback(event)

    def _save_checkpoint(
        self,
        run_id: str,
        goal: str,
        planned: Dict[str, DynamicAgentPlan],
        pending: List[DynamicAgentPlan],
        completed_ids: Set[str],
        failed_ids: Set[str],
        rounds: List[DynamicWorkflowRound],
        stop_reason: str,
        replan_trigger_records: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        payload = {
            "goal": goal,
            "run_id": run_id,
            "rounds": [asdict(item) for item in rounds],
            "planned_agents": [asdict(agent) for agent in planned.values()],
            "pending_agents": [asdict(agent) for agent in pending],
            "completed_agent_ids": sorted(completed_ids),
            "failed_agent_ids": sorted(failed_ids),
            "broker_thread_id": run_id,
            "stop_reason": stop_reason,
            "replan_trigger_records": list(replan_trigger_records or []),
        }
        return save_checkpoint(str(checkpoint_path(self.checkpoint_dir, run_id)), payload)

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
        spec.sandbox = agent.sandbox or self.sandbox
        spec.extra_args = list(agent.extra_args or self.codex_extra_args)
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
    agents = _parse_agents(_repair_replanner_agents(data.get("agents", [])), existing_agent_ids=existing_agent_ids)
    deps = _dependencies_from(data, agents, existing_agent_ids=existing_agent_ids)
    return ReplanDecision(
        agents=agents,
        dependencies=deps,
        stop_reason=str(data.get("stop_reason", "")),
        confidence=float(data.get("confidence", 0.0) or 0.0),
    )


def _repair_replanner_agents(raw_agents: Any) -> Any:
    if not isinstance(raw_agents, list):
        return raw_agents
    repaired = []
    for raw in raw_agents:
        if not isinstance(raw, dict):
            repaired.append(raw)
            continue
        item = dict(raw)
        if not str(item.get("goal", "")).strip() and str(item.get("prompt", "")).strip():
            item["goal"] = str(item["prompt"])
        if not str(item.get("role", "")).strip() and str(item.get("lane", "")).strip():
            item["role"] = str(item["lane"])
        repaired.append(item)
    return repaired


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
                sandbox=str(raw.get("sandbox", "read-only")),
                extra_args=[str(item) for item in raw.get("extra_args", [])],
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


def _plans_from_payload(payload: Any) -> List[DynamicAgentPlan]:
    if not isinstance(payload, list):
        return []
    plans = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        plans.append(DynamicAgentPlan(
            id=str(item.get("id", "")),
            role=str(item.get("role", "worker")),
            goal=str(item.get("goal", "")),
            context=str(item.get("context", "")),
            dependencies=list(item.get("dependencies", [])),
            workspace_mode=str(item.get("workspace_mode", "shared")),
            write_intent=str(item.get("write_intent", "none")),
            base_ref=str(item.get("base_ref", "HEAD")),
            sandbox=str(item.get("sandbox", "read-only")),
            extra_args=[str(value) for value in item.get("extra_args", [])],
        ))
    return plans


def _planner_prompt(goal: str) -> str:
    return (
        "You are the oh-my-Dynamic planner. Return exactly one JSON object.\n"
        "Create only the initial planner round agents. Do not create replanner, follow-up, retry, or coverage-proof agents; those are added later by the replanner after broker evidence and trigger policy are available.\n"
        "Schema: {\"agents\":[{\"id\":\"agent_id\",\"role\":\"role\",\"goal\":\"goal\","
        "\"context\":\"optional\",\"dependencies\":[]}],\"dependencies\":{},"
        "\"max_parallel\":5,\"stop_reason\":\"\",\"confidence\":0.0}\n\n"
        f"Goal:\n{goal}\n"
    )


def _replanner_prompt(goal: str, snapshot: Dict[str, Any]) -> str:
    return (
        "You are the oh-my-Dynamic replanner. Return exactly one JSON object.\n"
        "Return new agents only, or stop_reason=\"ready_for_reducer\" when the broker evidence is enough.\n"
        "If replan_trigger_policy.replan_triggers is non-empty, do not return ready_for_reducer; add targeted follow-up agents for those triggers. Respect followup_agent_budget when present.\n"
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
    parser.add_argument("--checkpoint-dir", default=".orchestry/checkpoints")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--resume", default="", help="Resume from .orchestry/checkpoints/{RUN_ID}.json.")
    parser.add_argument("--stream-events", action="store_true", help="Print WorkflowEvent JSONL progress events.")
    parser.add_argument("--sandbox", default="read-only", help="Sandbox passed to dynamic workflow Codex CLI worker agents.")
    parser.add_argument("--planner-sandbox", default="read-only", help="Sandbox passed to planner/replanner JSON Codex CLI workers.")
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        default=[],
        help="Extra argument passed to planner/replanner and every worker. Repeat for multiple args.",
    )
    args = parser.parse_args()
    if not args.goal and not args.resume:
        parser.print_help()
        return

    def stream_event(event: WorkflowEvent) -> None:
        print(json.dumps(event.to_dict(), ensure_ascii=False), flush=True)

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
        checkpoint_dir=args.checkpoint_dir,
        event_callback=stream_event if args.stream_events else None,
        sandbox=args.sandbox,
        planner_sandbox=args.planner_sandbox,
        codex_extra_args=args.codex_extra_arg,
    )
    trace = runtime.run(args.goal or "", run_id=args.run_id or None, resume_run_id=args.resume)
    print(json.dumps(trace.summary(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
