"""Artifact, manifest, prompt, and trace helpers for Codex CLI swarm runs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import subprocess
import time

from oh_my_dynamic.broker.agent_broker import AgentBroker
from oh_my_dynamic.codex.codex_app_bridge import CodexSubagentEnvelope, envelope_from_dict, ingest_subagent_envelope
from oh_my_dynamic.codex.codex_swarm_models import CodexCliAgentResult, CodexCliAgentSpec, now_iso
from oh_my_dynamic.runtime.workflow_events import WorkflowEvent


def build_manifest(
    run_id: str,
    goal: str,
    agents: List[CodexCliAgentSpec],
    started_at: str,
    swarm_root: Path,
    codex_bin: str,
    codex_cwd: Path,
    workspace_root: Path,
    max_parallel: int,
    timeout_s: int,
    total_timeout_s: Optional[int],
    keep_workdirs: bool,
    topological_layers: List[List[str]],
    ready_batches: List[List[str]],
) -> Dict[str, object]:
    return {
        "run_id": run_id,
        "goal": goal,
        "started_at": started_at,
        "codex_bin": codex_bin,
        "codex_cwd": str(codex_cwd),
        "workspace_root": str(workspace_root),
        "swarm_root": str(swarm_root.resolve()),
        "max_parallel": max_parallel,
        "timeout_s": timeout_s,
        "total_timeout_s": total_timeout_s,
        "keep_workdirs": keep_workdirs,
        "topological_layers": topological_layers,
        "ready_batches": ready_batches,
        "agents": [asdict(agent) for agent in agents],
    }


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def build_worker_prompt(
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
        f"Dependency outputs:\n{format_dependency_context(spec, dependency_results)}\n\n"
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


def ingest_envelope(
    broker: Optional[AgentBroker],
    envelope: CodexSubagentEnvelope,
    spec: CodexCliAgentSpec,
    run_id: str,
) -> Dict[str, object]:
    if not broker:
        return {"artifact_ids": {}, "event_ids": []}
    return ingest_subagent_envelope(
        broker,
        run_id,
        envelope,
        role=spec.role,
        capabilities=["codex_cli_worker"],
    )


def publish_worktree_diff_artifacts(
    broker: Optional[AgentBroker],
    spec: CodexCliAgentSpec,
    run_id: str,
    agent_cwd: Path,
) -> Dict[str, str]:
    if not broker or spec.workspace_mode != "worktree":
        return {}

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(agent_cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            return completed.stderr.strip()
        return completed.stdout

    artifacts = {
        "diff_stat": git("diff", "--stat", spec.base_ref),
        "patch": git("diff", spec.base_ref),
        "changed_files": git("diff", "--name-only", spec.base_ref),
    }
    published: Dict[str, str] = {}
    for name, content in artifacts.items():
        artifact = broker.publish_artifact(
            spec.id,
            name,
            content or "(no changes)",
            kind="worktree_diff",
            content_type="text/plain",
            metadata={
                "thread_id": run_id,
                "workspace_mode": spec.workspace_mode,
                "write_intent": spec.write_intent,
                "worktree_path": str(agent_cwd),
                "base_ref": spec.base_ref,
            },
            thread_id=run_id,
        )
        published[name] = artifact.id
    return published


def build_failed_process_result(
    broker: Optional[AgentBroker],
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
    default_cwd: Path,
    agent_cwd: Optional[Path] = None,
    worktree_branch: str = "",
    worktree_path: str = "",
) -> Tuple[CodexCliAgentResult, WorkflowEvent]:
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
    ingested = ingest_envelope(broker, envelope, spec, run_id)
    artifact_ids = dict(ingested.get("artifact_ids", {}))
    if agent_cwd is not None:
        artifact_ids.update(publish_worktree_diff_artifacts(broker, spec, run_id, agent_cwd))
    result = CodexCliAgentResult(
        agent_id=spec.id,
        role=spec.role,
        status="failed",
        summary=error,
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
        agent_cwd=str(agent_cwd.resolve()) if agent_cwd is not None else str(default_cwd),
        worktree_branch=worktree_branch,
        worktree_path=str(Path(worktree_path).resolve()) if worktree_path else "",
        error=error,
    )
    event = WorkflowEvent(
        run_id=run_id,
        kind="agent_failed",
        subject="agent_failed",
        body=error,
        agent_id=spec.id,
        status="failed",
        preview=error[:200],
        metadata={"returncode": returncode},
    )
    return result, event


def format_dependency_context(
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
        artifact_context = dependency_artifact_context(result)
        parts.append(
            "\n".join([
                f"## {dep_id} ({result.role}, {result.status})",
                f"Summary: {body[:2000]}",
                f"Error: {result.error or '(none)'}",
                f"Output file: {result.output_path}",
                f"Artifacts:\n{artifact_context}",
            ])
        )
    return "\n\n".join(parts)


def dependency_artifact_context(result: CodexCliAgentResult) -> str:
    output_path = Path(result.output_path)
    if not output_path.exists():
        return "(none; output file missing)"
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return "(none; output file is not JSON)"
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        return "(none)"
    lines = []
    for artifact in artifacts[:5]:
        if not isinstance(artifact, dict):
            continue
        name = str(artifact.get("name", "result"))
        kind = str(artifact.get("kind", "text"))
        content_type = str(artifact.get("content_type", "text/plain"))
        content = str(artifact.get("content", ""))[:1200]
        artifact_id = result.artifact_ids.get(name, "")
        id_part = f", broker_id={artifact_id}" if artifact_id else ""
        lines.append(f"- {name} ({kind}, {content_type}{id_part}): {content}")
    return "\n".join(lines) if lines else "(none)"
