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
from pathlib import Path
from typing import Callable, Dict, List, Optional
import shutil
import time

from oh_my_dynamic.broker.agent_broker import AgentBroker
from oh_my_dynamic.codex.codex_swarm_artifacts import (
    build_failed_process_result,
    build_manifest,
    write_json,
)
from oh_my_dynamic.codex.codex_swarm_models import (
    CodexCliAgentResult,
    CodexCliAgentSpec,
    CodexCliSwarmTrace,
    new_run_id,
    now_iso,
)
from oh_my_dynamic.codex.codex_swarm_scheduler import (
    agent_batches,
    dependency_failure_message,
    ready_batches,
    topological_layers,
)
from oh_my_dynamic.codex.codex_swarm_process import run_agent_process
from oh_my_dynamic.codex.worktree import WorktreeManager
from oh_my_dynamic.runtime.workflow_events import WorkflowEvent


def _now() -> str:
    return now_iso()


def _run_id() -> str:
    return new_run_id()


class CodexCliSwarmRuntime:
    """Run many independent Codex CLI workers and broker their envelopes."""

    def __init__(
        self,
        codex_bin: str = "codex",
        codex_cwd: str = ".",
        workspace_root: str = ".orchestry/codex_cli_swarm",
        max_parallel: int = 16,
        timeout_s: int = 1800,
        total_timeout_s: Optional[int] = None,
        keep_workdirs: bool = True,
        broker: Optional[AgentBroker] = None,
        inherited_env: Optional[Dict[str, str]] = None,
        worktree_root: str = ".orchestry/worktrees",
        event_callback: Optional[Callable[[WorkflowEvent], None]] = None,
    ) -> None:
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")
        if timeout_s < 1:
            raise ValueError("timeout_s must be at least 1")
        if total_timeout_s is not None and total_timeout_s < 1:
            raise ValueError("total_timeout_s must be at least 1 when provided")
        self.codex_bin = codex_bin
        self.codex_cwd = Path(codex_cwd).resolve()
        root = Path(workspace_root).expanduser()
        self.workspace_root = root.resolve() if root.is_absolute() else (Path.cwd() / root).resolve()
        self.max_parallel = max_parallel
        self.timeout_s = timeout_s
        self.total_timeout_s = total_timeout_s
        self.keep_workdirs = keep_workdirs
        self.broker = broker
        self.inherited_env = inherited_env or {}
        root = Path(worktree_root).expanduser()
        self.worktree_root = root.resolve() if root.is_absolute() else (self.codex_cwd / root).resolve()
        self.event_callback = event_callback

    def run(
        self,
        goal: str,
        agents: List[CodexCliAgentSpec],
        run_id: Optional[str] = None,
        terminal_trace: bool = True,
    ) -> CodexCliSwarmTrace:
        if not goal.strip():
            raise ValueError("goal is required")
        if not agents:
            raise ValueError("at least one CodexCliAgentSpec is required")
        layers = topological_layers(agents)
        layer_ids = [[spec.id for spec in layer] for layer in layers]
        batches = ready_batches(layer_ids, self.max_parallel)

        run_id = run_id or _run_id()
        started_at = _now()
        start = time.time()
        swarm_root = self.workspace_root / run_id
        swarm_root.mkdir(parents=True, exist_ok=True)
        manifest_path = swarm_root / "manifest.json"
        trace_path = swarm_root / "trace.json"
        write_json(
            manifest_path,
            build_manifest(
                run_id,
                goal,
                agents,
                started_at,
                swarm_root,
                self.codex_bin,
                self.codex_cwd,
                self.workspace_root,
                self.max_parallel,
                self.timeout_s,
                self.total_timeout_s,
                self.keep_workdirs,
                layer_ids,
                batches,
            ),
        )

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
                    metadata={
                        "goal": spec.goal,
                        "dependencies": spec.dependencies,
                        "workspace_mode": spec.workspace_mode,
                        "write_intent": spec.write_intent,
                    },
                )
        self._emit_event(WorkflowEvent(
            run_id=run_id,
            kind="codex_cli_swarm_started",
            subject="codex_cli_swarm_started",
            body=goal,
            status="running",
            metadata={"agents": len(agents), "max_parallel": self.max_parallel},
        ))

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

            for batch in agent_batches(runnable, self.max_parallel):
                remaining_timeout = self._remaining_timeout_s(start)
                if remaining_timeout is not None and remaining_timeout <= 0:
                    for spec in batch:
                        results_by_id[spec.id] = self._total_timeout_result(spec, swarm_root / spec.id, run_id)
                    continue
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {
                        pool.submit(
                            self._run_agent,
                            goal,
                            spec,
                            swarm_root / spec.id,
                            {dep_id: results_by_id[dep_id] for dep_id in spec.dependencies},
                            run_id,
                            remaining_timeout,
                        ): spec
                        for spec in batch
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        results_by_id[result.agent_id] = result
                self._emit_event(WorkflowEvent(
                    run_id=run_id,
                    kind="batch_done",
                    subject="batch_done",
                    body="Codex CLI swarm batch finished.",
                    status="completed",
                    metadata={"agent_ids": [spec.id for spec in batch]},
                ))

        order = {spec.id: index for index, spec in enumerate(spec for layer in layers for spec in layer)}
        results = sorted(results_by_id.values(), key=lambda result: order[result.agent_id])
        if self.broker and terminal_trace:
            completed_count = sum(1 for result in results if result.status == "completed")
            failed_count = sum(1 for result in results if result.status == "failed")
            terminal_subject = "workflow_completed" if failed_count == 0 else "workflow_failed"
            self.broker.trace(
                "orchestrator",
                terminal_subject,
                f"Codex CLI swarm finished with {completed_count} completed and {failed_count} failed agents.",
                thread_id=run_id,
                metadata={
                    "backend": "codex_cli_swarm",
                    "backend_event": "codex_cli_swarm_completed" if failed_count == 0 else "codex_cli_swarm_failed",
                    "completed": completed_count,
                    "failed": failed_count,
                },
            )
        self._emit_event(WorkflowEvent(
            run_id=run_id,
            kind="codex_cli_swarm_done",
            subject="codex_cli_swarm_done",
            body="Codex CLI swarm finished.",
            status="completed" if all(result.status == "completed" for result in results) else "failed",
            metadata={"completed": sum(1 for result in results if result.status == "completed"), "failed": sum(1 for result in results if result.status == "failed")},
        ))

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
            ready_batches=batches,
            broker_thread_id=run_id if self.broker else "",
            broker_event_count=broker_event_count,
            manifest_path=str(manifest_path.resolve()),
            trace_path=str(trace_path.resolve()),
        )

        write_json(trace_path, trace.to_dict())
        if not self.keep_workdirs:
            durable_manifest_path = self.workspace_root / f"{run_id}.manifest.json"
            durable_trace_path = self.workspace_root / f"{run_id}.trace.json"
            shutil.copy2(manifest_path, durable_manifest_path)
            shutil.copy2(trace_path, durable_trace_path)
            trace.manifest_path = str(durable_manifest_path.resolve())
            trace.trace_path = str(durable_trace_path.resolve())
            write_json(durable_trace_path, trace.to_dict())
            shutil.rmtree(swarm_root, ignore_errors=True)
        return trace

    def _run_agent(
        self,
        workflow_goal: str,
        spec: CodexCliAgentSpec,
        work_dir: Path,
        dependency_results: Dict[str, CodexCliAgentResult],
        run_id: str,
        timeout_s: Optional[int],
    ) -> CodexCliAgentResult:
        return run_agent_process(self, workflow_goal, spec, work_dir, dependency_results, run_id, timeout_s)

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
        agent_cwd: Optional[Path] = None,
        worktree_branch: str = "",
        worktree_path: str = "",
    ) -> CodexCliAgentResult:
        result, event = build_failed_process_result(
            self.broker,
            spec,
            work_dir,
            prompt_path,
            output_path,
            stdout_path,
            stderr_path,
            started_at,
            start,
            returncode,
            error,
            run_id,
            self.codex_cwd,
            agent_cwd=agent_cwd,
            worktree_branch=worktree_branch,
            worktree_path=worktree_path,
        )
        self._emit_event(event)
        return result

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
        error = dependency_failure_message(spec, failed_deps, results_by_id)
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

    def _prepare_agent_workspace(self, spec: CodexCliAgentSpec, run_id: str) -> tuple[Path, str, str]:
        if spec.workspace_mode not in ("shared", "worktree"):
            raise ValueError("workspace_mode must be shared or worktree")
        if spec.write_intent not in ("none", "patch"):
            raise ValueError("write_intent must be none or patch")
        if spec.write_intent == "patch" and spec.workspace_mode != "worktree":
            raise ValueError("write_intent=patch requires workspace_mode=worktree")
        if spec.workspace_mode == "shared":
            return self.codex_cwd, "", ""

        branch = f"ohmy/{run_id}/{spec.id}"
        path = self.worktree_root / run_id / spec.id
        manager = WorktreeManager(str(self.codex_cwd))
        manager.create(
            spec.id,
            base_branch=spec.base_ref,
            agent_id=spec.id,
            branch_name=branch,
            worktree_path=str(path),
        )
        return path.resolve(), branch, str(path.resolve())

    def _remaining_timeout_s(self, start: float) -> Optional[int]:
        if self.total_timeout_s is None:
            return None
        remaining = self.total_timeout_s - (time.time() - start)
        if remaining <= 0:
            return 0
        return max(1, int(remaining))

    def _total_timeout_result(self, spec: CodexCliAgentSpec, work_dir: Path, run_id: str) -> CodexCliAgentResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        started_at = _now()
        error = f"Codex CLI swarm total timeout reached before starting {spec.id}"
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

    def _emit_event(self, event: WorkflowEvent) -> None:
        if self.event_callback is not None:
            self.event_callback(event)


def main() -> None:
    from oh_my_dynamic.codex.codex_swarm_cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
