"""Single-worker process lifecycle for Codex CLI swarm runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import subprocess
import time

from oh_my_dynamic.codex.codex_app_bridge import parse_subagent_envelope
from oh_my_dynamic.codex.codex_swarm_artifacts import (
    build_worker_prompt,
    ingest_envelope,
    publish_worktree_diff_artifacts,
)
from oh_my_dynamic.codex.codex_swarm_models import CodexCliAgentResult, CodexCliAgentSpec, now_iso
from oh_my_dynamic.codex.codex_worker import build_codex_exec_command, build_worker_env, clamp_worker_timeout
from oh_my_dynamic.runtime.workflow_events import WorkflowEvent


def run_agent_process(
    runtime: Any,
    workflow_goal: str,
    spec: CodexCliAgentSpec,
    work_dir: Path,
    dependency_results: Dict[str, CodexCliAgentResult],
    run_id: str,
    timeout_s: Optional[int],
) -> CodexCliAgentResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = work_dir / "prompt.md"
    output_path = work_dir / "last_message.txt"
    stdout_path = work_dir / "stdout.txt"
    stderr_path = work_dir / "stderr.txt"
    prompt = build_worker_prompt(workflow_goal, spec, dependency_results)
    prompt_path.write_text(prompt, encoding="utf-8")

    started_at = now_iso()
    start = time.time()

    try:
        agent_cwd, worktree_branch, worktree_path = runtime._prepare_agent_workspace(spec, run_id)
        if runtime.broker:
            runtime.broker.trace(
                spec.id,
                "codex_cli_agent_started",
                spec.goal,
                thread_id=run_id,
                metadata={
                    "role": spec.role,
                    "work_dir": str(work_dir.resolve()),
                    "workspace_mode": spec.workspace_mode,
                    "agent_cwd": str(agent_cwd),
                    "worktree_branch": worktree_branch,
                },
            )
        runtime._emit_event(WorkflowEvent(
            run_id=run_id,
            kind="agent_started",
            subject="agent_started",
            body=spec.goal,
            agent_id=spec.id,
            status="running",
            preview=spec.goal[:200],
            metadata={"role": spec.role, "workspace_mode": spec.workspace_mode},
        ))

        command = build_codex_exec_command(
            runtime.codex_bin,
            agent_cwd,
            spec.sandbox,
            output_path,
            spec.extra_args,
        )
        env = build_worker_env(runtime.inherited_env)
        worker_timeout_s = clamp_worker_timeout(runtime.timeout_s, timeout_s)

        with (
            prompt_path.open("r", encoding="utf-8") as prompt_file,
            stdout_path.open("w", encoding="utf-8") as stdout_file,
            stderr_path.open("w", encoding="utf-8") as stderr_file,
        ):
            process = subprocess.Popen(
                command,
                cwd=str(agent_cwd),
                env=env,
                stdin=prompt_file,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
            )
            try:
                returncode = process.wait(timeout=worker_timeout_s)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return runtime._failed_process_result(
                    spec,
                    work_dir,
                    prompt_path,
                    output_path,
                    stdout_path,
                    stderr_path,
                    started_at,
                    start,
                    -1,
                    f"codex exec timed out after {worker_timeout_s}s",
                    run_id,
                    agent_cwd=agent_cwd,
                    worktree_branch=worktree_branch,
                    worktree_path=worktree_path,
                )

        stdout_text = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
        stderr_text = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
        raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else stdout_text
        if returncode != 0:
            error = stderr_text.strip() or f"codex exec exited with {returncode}"
            return runtime._failed_process_result(
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
                agent_cwd=agent_cwd,
                worktree_branch=worktree_branch,
                worktree_path=worktree_path,
            )

        envelope = parse_subagent_envelope(raw_output)
        if envelope.agent_id != spec.id:
            raise ValueError(f"envelope agent_id mismatch: expected {spec.id}, got {envelope.agent_id}")
        ingested = ingest_envelope(runtime.broker, envelope, spec, run_id)
        artifact_ids = dict(ingested.get("artifact_ids", {}))
        artifact_ids.update(publish_worktree_diff_artifacts(runtime.broker, spec, run_id, agent_cwd))
        result = CodexCliAgentResult(
            agent_id=spec.id,
            role=spec.role,
            status=envelope.status,
            summary=envelope.summary,
            started_at=started_at,
            completed_at=now_iso(),
            duration_s=time.time() - start,
            returncode=returncode,
            work_dir=str(work_dir.resolve()),
            prompt_path=str(prompt_path.resolve()),
            output_path=str(output_path.resolve()),
            stdout_path=str(stdout_path.resolve()),
            stderr_path=str(stderr_path.resolve()),
            artifact_ids=artifact_ids,
            event_ids=list(ingested.get("event_ids", [])),
            workspace_mode=spec.workspace_mode,
            agent_cwd=str(agent_cwd.resolve()),
            worktree_branch=worktree_branch,
            worktree_path=str(Path(worktree_path).resolve()) if worktree_path else "",
            error=envelope.error,
        )
        runtime._emit_event(WorkflowEvent(
            run_id=run_id,
            kind="agent_done" if result.status == "completed" else "agent_failed",
            subject="agent_done" if result.status == "completed" else "agent_failed",
            body=result.summary,
            agent_id=spec.id,
            status=result.status,
            preview=result.summary[:200],
            metadata={"returncode": returncode, "role": spec.role},
        ))
        return result
    except Exception as exc:
        return runtime._failed_process_result(
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
            agent_cwd=agent_cwd if "agent_cwd" in locals() else None,
            worktree_branch=worktree_branch if "worktree_branch" in locals() else "",
            worktree_path=worktree_path if "worktree_path" in locals() else "",
        )
