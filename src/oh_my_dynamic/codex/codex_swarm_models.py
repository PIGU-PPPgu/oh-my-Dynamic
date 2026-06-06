"""Public data models for the Codex CLI swarm backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List
import uuid


def now_iso() -> str:
    return datetime.now().isoformat()


def new_run_id() -> str:
    return f"codex_cli_run_{uuid.uuid4().hex[:10]}"


@dataclass
class CodexCliAgentSpec:
    """One worker process launched through `codex exec`."""

    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: List[str] = field(default_factory=list)
    sandbox: str = "read-only"
    approval_policy: str = "never"
    extra_args: List[str] = field(default_factory=list)
    workspace_mode: str = "shared"
    write_intent: str = "none"
    base_ref: str = "HEAD"


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
    workspace_mode: str = "shared"
    agent_cwd: str = ""
    worktree_branch: str = ""
    worktree_path: str = ""
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
    manifest_path: str = ""
    trace_path: str = ""

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
            "manifest_path": self.manifest_path,
            "trace_path": self.trace_path,
        }
