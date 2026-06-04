"""
Codex CLI swarm backend.

This module fans out many independent `codex exec` processes and ingests their
structured JSON envelopes into AgentBroker. It is not Codex App-native runtime
fan-out; it is a pragmatic process-swarm backend for cases where users want
dozens or hundreds of real Codex agents before the App exposes a native dynamic
workflow engine.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import os
import shutil
import subprocess
import time
import uuid

from agent_broker import AgentBroker, validate_agent_id
from codex_app_bridge import (
    CodexSubagentEnvelope,
    envelope_from_dict,
    ingest_subagent_envelope,
    parse_subagent_envelope,
)


def _now() -> str:
    return datetime.now().isoformat()


def _run_id() -> str:
    return f"codex_cli_run_{uuid.uuid4().hex[:10]}"


@dataclass
class CodexCliAgentSpec:
    """One worker process launched through `codex exec`."""

    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: List[str] = field(default_factory=list)
    sandbox: str = "workspace-write"
    approval_policy: str = "never"
    extra_args: List[str] = field(default_factory=list)


@dataclass
class CodexCliAgentResult:
    """Result from one `codex exec` worker process."""

    agent_id: str
    role: str
    status: str
    summary: str
    started_at: str
    completed_at: str
    duration_s: float
    returncode: int
    work_dir: str
    prompt_path: str
    output_path: str
    stdout_path: str
    stderr_path: str
    artifact_ids: Dict[str, str] = field(default_factory=dict)
    event_ids: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class CodexCliSwarmTrace:
    """Complete trace for a Codex CLI process swarm."""

    run_id: str
    goal: str
    max_parallel: int
    started_at: str
    completed_at: str
    duration_s: float
    results: List[CodexCliAgentResult]
    swarm_root: str
    codex_cwd: str
    topological_layers: List[List[str]]
    ready_batches: List[List[str]]
    broker_thread_id: str = ""
    broker_event_count: int = 0

    def summary(self) -> Dict[str, object]:
        completed = sum(1 for result in self.results if result.status == "completed")
        failed = sum(1 for result in self.results if result.status == "failed")
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "agents": len(self.results),
            "completed": completed,
            "failed": failed,
            "duration_s": self.duration_s,
            "max_parallel": self.max_parallel,
            "swarm_root": self.swarm_root,
            "broker_thread_id": self.broker_thread_id,
            "broker_event_count": self.broker_event_count,
        }

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "max_parallel": self.max_parallel,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_s": self.duration_s,
            "results": [asdict(result) for result in self.results],
            "swarm_root": self.swarm_root,
            "codex_cwd": self.codex_cwd,
            "topological_layers": self.topological_layers,
            "ready_batches": self.ready_batches,
            "broker_thread_id": self.broker_thread_id,
            "broker_event_count": self.broker_event_count,
        }


class CodexCliSwarmRuntime:
    """Run many independent Codex CLI workers and broker their envelopes."""

    def __init__(
        self,
        codex_bin: str = "codex",
        codex_cwd: str = ".",
        workspace_root: str = ".orchestry/codex_cli_swarm",
        max_parallel: int = 16,
        timeout_s: int = 1800,
        keep_workdirs: bool = True,
        broker: Optional[AgentBroker] = None,
        inherited_env: Optional[Dict[str, str]] = None,
    ) -> None:
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")
        if timeout_s < 1:
            raise ValueError("timeout_s must be at least 1")
        self.codex_bin = codex_bin
        self.codex_cwd = Path(codex_cwd).resolve()
        self.workspace_root = Path(workspace_root)
        self.max_parallel = max_parallel
        self.timeout_s = timeout_s
        self.keep_workdirs = keep_workdirs
        self.broker = broker
        self.inherited_env = inherited_env or {}

    def run(self, goal: str, agents: List[CodexCliAgentSpec]) -> CodexCliSwarmTrace:
        if not goal.strip():
            raise ValueError("goal is required")
        if not agents:
            raise ValueError("at least one CodexCliAgentSpec is required")
        layers = self._topological_layers(agents)
        layer_ids = [[spec.id for spec in layer] for layer in layers]
        ready_batches = self._ready_batches(layer_ids, self.max_parallel)

        run_id = _run_id()
        started_at = _now()
        start = time.time()
        swarm_root = self.workspace_root / run_id
        swarm_root.mkdir(parents=True, exist_ok=True)

        if self.broker:
            self.broker.register_agent("orchestrator", "orchestrator", ["plan", "reduce"])
            self.broker.trace(
                "orchestrator",
                "codex_cli_swarm_started",
                goal,
                thread_id=run_id,
                metadata={
                    "agents": len(agents),
                    "max_parallel": self.max_parallel,
                    "codex_cwd": str(self.codex_cwd),
                },
            )
            for spec in agents:
                self.broker.register_agent(
                    spec.id,
                    spec.role,
                    ["codex_cli_worker"],
                    metadata={"goal": spec.goal, "dependencies": spec.dependencies},
                )

        results_by_id: Dict[str, CodexCliAgentResult] = {}
        for layer in layers:
            runnable: List[CodexCliAgentSpec] = []
            for spec in layer:
                failed_deps = [
                    dep_id
                    for dep_id in spec.dependencies
                    if results_by_id[dep_id].status != "completed"
                ]
                if failed_deps:
                    results_by_id[spec.id] = self._dependency_failed_result(
                        spec,
                        swarm_root / spec.id,
                        failed_deps,
                        results_by_id,
                        run_id,
                    )
                else:
                    runnable.append(spec)

            for batch in self._agent_batches(runnable, self.max_parallel):
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {
                        pool.submit(
                            self._run_agent,
                            goal,
                            spec,
                            swarm_root / spec.id,
                            {dep_id: results_by_id[dep_id] for dep_id in spec.dependencies},
                            run_id,
                        ): spec
                        for spec in batch
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        results_by_id[result.agent_id] = result

        order = {spec.id: index for index, spec in enumerate(spec for layer in layers for spec in layer)}
        results = sorted(results_by_id.values(), key=lambda result: order[result.agent_id])
        if self.broker:
            self.broker.trace(
                "orchestrator",
                "codex_cli_swarm_completed",
                f"Codex CLI swarm completed with {len(results)} agents.",
                thread_id=run_id,
                metadata={
                    "completed": sum(1 for result in results if result.status == "completed"),
                    "failed": sum(1 for result in results if result.status == "failed"),
                },
            )

        completed_at = _now()
        broker_event_count = len(self.broker.list_events(thread_id=run_id)) if self.broker else 0
        trace = CodexCliSwarmTrace(
            run_id=run_id,
            goal=goal,
            max_parallel=self.max_parallel,
            started_at=started_at,
            completed_at=completed_at,
            duration_s=time.time() - start,
            results=results,
            swarm_root=str(swarm_root.resolve()),
            codex_cwd=str(self.codex_cwd),
            topological_layers=layer_ids,
            ready_batches=ready_batches,
            broker_thread_id=run_id if self.broker else "",
            broker_event_count=broker_event_count,
        )

        if not self.keep_workdirs:
            shutil.rmtree(swarm_root, ignore_errors=True)
        return trace

    def _run_agent(
        self,
        workflow_goal: str,
        spec: CodexCliAgentSpec,
        work_dir: Path,
        dependency_results: Dict[str, CodexCliAgentResult],
        run_id: str,
    ) -> CodexCliAgentResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = work_dir / "prompt.md"
        output_path = work_dir / "last_message.txt"
        stdout_path = work_dir / "stdout.txt"
        stderr_path = work_dir / "stderr.txt"
        prompt = self._build_prompt(workflow_goal, spec, dependency_results)
        prompt_path.write_text(prompt, encoding="utf-8")

        started_at = _now()
        start = time.time()
        if self.broker:
            self.broker.trace(
                spec.id,
                "codex_cli_agent_started",
                spec.goal,
                thread_id=run_id,
                metadata={"role": spec.role, "work_dir": str(work_dir.resolve())},
            )

        command = [
            self.codex_bin,
            "exec",
            "--cd",
            str(self.codex_cwd),
            "--sandbox",
            spec.sandbox,
            "--skip-git-repo-check",
            "--ephemeral",
            "--output-last-message",
            str(output_path),
            *spec.extra_args,
            prompt,
        ]
        env = os.environ.copy()
        env.update(self.inherited_env)

        try:
            completed = subprocess.run(
                command,
                cwd=str(self.codex_cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
            raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
            if completed.returncode != 0:
                error = completed.stderr.strip() or f"codex exec exited with {completed.returncode}"
                return self._failed_process_result(
                    spec,
                    work_dir,
                    prompt_path,
                    output_path,
                    stdout_path,
                    stderr_path,
                    started_at,
                    start,
                    completed.returncode,
                    error,
                    run_id,
                )

            envelope = parse_subagent_envelope(raw_output)
            if envelope.agent_id != spec.id:
                raise ValueError(f"envelope agent_id mismatch: expected {spec.id}, got {envelope.agent_id}")
            ingested = self._ingest_envelope(envelope, spec, run_id)
            return CodexCliAgentResult(
                agent_id=spec.id,
                role=spec.role,
                status=envelope.status,
                summary=envelope.summary,
                started_at=started_at,
                completed_at=_now(),
                duration_s=time.time() - start,
                returncode=completed.returncode,
                work_dir=str(work_dir.resolve()),
                prompt_path=str(prompt_path.resolve()),
                output_path=str(output_path.resolve()),
                stdout_path=str(stdout_path.resolve()),
                stderr_path=str(stderr_path.resolve()),
                artifact_ids=dict(ingested.get("artifact_ids", {})),
                event_ids=list(ingested.get("event_ids", [])),
                error=envelope.error,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            return self._failed_process_result(
                spec,
                work_dir,
                prompt_path,
                output_path,
                stdout_path,
                stderr_path,
                started_at,
                start,
                -1,
                f"codex exec timed out after {self.timeout_s}s",
                run_id,
            )
        except Exception as exc:
            return self._failed_process_result(
                spec,
                work_dir,
                prompt_path,
                output_path,
                stdout_path,
                stderr_path,
                started_at,
                start,
                -1,
                f"{type(exc).__name__}: {exc}",
                run_id,
            )

    def _build_prompt(
        self,
        workflow_goal: str,
        spec: CodexCliAgentSpec,
        dependency_results: Dict[str, CodexCliAgentResult],
    ) -> str:
        return (
            "You are an independent Codex CLI worker in an oh-my-Dynamic swarm.\n"
            "Return exactly one JSON object and no prose. The parent orchestrator "
            "will ingest it into AgentBroker.\n\n"
            f"Workflow goal:\n{workflow_goal}\n\n"
            f"Agent id: {spec.id}\n"
            f"Role: {spec.role}\n"
            f"Agent goal:\n{spec.goal}\n"
            f"Dependencies: {spec.dependencies}\n\n"
            f"Context:\n{spec.context or '(none)'}\n\n"
            f"Dependency outputs:\n{self._format_dependency_context(spec, dependency_results)}\n\n"
            "Required JSON schema:\n"
            "{\n"
            f'  "agent_id": "{spec.id}",\n'
            '  "status": "completed|failed",\n'
            '  "summary": "<concise result for reducer>",\n'
            '  "artifacts": [{"name":"result","kind":"analysis","content_type":"text/plain","content":"..."}],\n'
            '  "messages": [{"to_agent":"orchestrator","subject":"...","body":"...","artifact_names":["result"]}],\n'
            '  "handoffs": [],\n'
            '  "review_requests": [],\n'
            '  "review_responses": [],\n'
            '  "metadata": {"backend": "codex_cli_swarm"},\n'
            '  "error": ""\n'
            "}\n"
        )

    def _ingest_envelope(
        self,
        envelope: CodexSubagentEnvelope,
        spec: CodexCliAgentSpec,
        run_id: str,
    ) -> Dict[str, object]:
        if not self.broker:
            return {"artifact_ids": {}, "event_ids": []}
        return ingest_subagent_envelope(
            self.broker,
            run_id,
            envelope,
            role=spec.role,
            capabilities=["codex_cli_worker"],
        )

    def _failed_process_result(
        self,
        spec: CodexCliAgentSpec,
        work_dir: Path,
        prompt_path: Path,
        output_path: Path,
        stdout_path: Path,
        stderr_path: Path,
        started_at: str,
        start: float,
        returncode: int,
        error: str,
        run_id: str,
    ) -> CodexCliAgentResult:
        envelope = envelope_from_dict({
            "agent_id": spec.id,
            "status": "failed",
            "summary": error,
            "artifacts": [{
                "name": "error",
                "kind": "error",
                "content_type": "text/plain",
                "content": error,
            }],
            "messages": [{
                "to_agent": "orchestrator",
                "subject": f"Codex CLI worker failed: {spec.id}",
                "body": error,
                "artifact_names": ["error"],
            }],
            "metadata": {"backend": "codex_cli_swarm", "returncode": returncode},
            "error": error,
        })
        ingested = self._ingest_envelope(envelope, spec, run_id)
        return CodexCliAgentResult(
            agent_id=spec.id,
            role=spec.role,
            status="failed",
            summary=error,
            started_at=started_at,
            completed_at=_now(),
            duration_s=time.time() - start,
            returncode=returncode,
            work_dir=str(work_dir.resolve()),
            prompt_path=str(prompt_path.resolve()),
            output_path=str(output_path.resolve()),
            stdout_path=str(stdout_path.resolve()),
            stderr_path=str(stderr_path.resolve()),
            artifact_ids=dict(ingested.get("artifact_ids", {})),
            event_ids=list(ingested.get("event_ids", [])),
            error=error,
        )

    def _dependency_failed_result(
        self,
        spec: CodexCliAgentSpec,
        work_dir: Path,
        failed_deps: List[str],
        results_by_id: Dict[str, CodexCliAgentResult],
        run_id: str,
    ) -> CodexCliAgentResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now()
        details = []
        for dep_id in failed_deps:
            dep = results_by_id[dep_id]
            details.append(f"{dep_id} ({dep.status}: {dep.error or dep.summary})")
        error = f"Dependency failed for {spec.id}: " + "; ".join(details)
        return self._failed_process_result(
            spec,
            work_dir,
            work_dir / "prompt.md",
            work_dir / "last_message.txt",
            work_dir / "stdout.txt",
            work_dir / "stderr.txt",
            started_at,
            time.time(),
            -1,
            error,
            run_id,
        )

    def _format_dependency_context(
        self,
        spec: CodexCliAgentSpec,
        dependency_results: Dict[str, CodexCliAgentResult],
    ) -> str:
        if not spec.dependencies:
            return "(none)"
        parts = []
        for dep_id in spec.dependencies:
            result = dependency_results.get(dep_id)
            if result is None:
                parts.append(f"## {dep_id}\n(status unavailable)")
                continue
            body = result.summary or result.error or "(no summary)"
            parts.append(f"## {dep_id} ({result.role}, {result.status})\n{body[:4000]}")
        return "\n\n".join(parts)

    def _topological_layers(self, agents: List[CodexCliAgentSpec]) -> List[List[CodexCliAgentSpec]]:
        specs_by_id: Dict[str, CodexCliAgentSpec] = {}
        for spec in agents:
            spec.id = validate_agent_id(spec.id)
            if spec.id in specs_by_id:
                raise ValueError(f"duplicate agent id: {spec.id}")
            specs_by_id[spec.id] = spec

        order = {spec.id: index for index, spec in enumerate(agents)}
        dependents: Dict[str, List[str]] = {spec.id: [] for spec in agents}
        indegree: Dict[str, int] = {spec.id: 0 for spec in agents}
        for spec in agents:
            seen_deps = set()
            for dep_id in spec.dependencies:
                dep_id = validate_agent_id(dep_id, "dependency")
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
        layers: List[List[CodexCliAgentSpec]] = []
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
            raise ValueError("cycle detected in CodexCliAgentSpec.dependencies: " + ", ".join(cycle_ids))
        return layers

    def _ready_batches(self, layers: List[List[str]], max_parallel: int) -> List[List[str]]:
        batches: List[List[str]] = []
        for layer in layers:
            for index in range(0, len(layer), max_parallel):
                batches.append(layer[index:index + max_parallel])
        return batches

    def _agent_batches(
        self,
        agents: List[CodexCliAgentSpec],
        max_parallel: int,
    ) -> List[List[CodexCliAgentSpec]]:
        return [agents[index:index + max_parallel] for index in range(0, len(agents), max_parallel)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an oh-my-Dynamic Codex CLI process swarm.")
    parser.add_argument("goal", help="Workflow goal to distribute across Codex CLI workers.")
    parser.add_argument("--agents", type=int, default=8, help="Number of Codex CLI workers to launch.")
    parser.add_argument("--max-parallel", type=int, default=4, help="Maximum concurrent codex exec processes.")
    parser.add_argument("--codex-bin", default="codex", help="Path to the codex CLI binary.")
    parser.add_argument("--cd", default=".", help="Working directory passed to codex exec --cd.")
    parser.add_argument("--workspace-root", default=".orchestry/codex_cli_swarm")
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--keep-workdirs", action="store_true")
    args = parser.parse_args()

    if args.agents < 1:
        raise SystemExit("--agents must be at least 1")

    broker = AgentBroker(args.broker_dir)
    runtime = CodexCliSwarmRuntime(
        codex_bin=args.codex_bin,
        codex_cwd=args.cd,
        workspace_root=args.workspace_root,
        max_parallel=args.max_parallel,
        timeout_s=args.timeout_s,
        keep_workdirs=args.keep_workdirs,
        broker=broker,
    )
    specs = [
        CodexCliAgentSpec(
            id=f"agent_{index:03d}",
            role="codex_cli_worker",
            goal=f"Shard {index + 1}/{args.agents}: {args.goal}",
            context=(
                "Work independently. Return evidence-oriented findings for this shard. "
                "Do not edit files unless the prompt explicitly asks for implementation."
            ),
        )
        for index in range(args.agents)
    ]
    trace = runtime.run(args.goal, specs)
    print(trace.summary())
    print(f"broker_thread_id={trace.broker_thread_id}")
    print(f"swarm_root={trace.swarm_root}")


if __name__ == "__main__":
    main()
