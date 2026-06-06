"""Small Codex CLI worker lifecycle helpers used by the swarm executor."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence
import os


def build_codex_exec_command(
    codex_bin: str,
    agent_cwd: Path,
    sandbox: str,
    output_path: Path,
    extra_args: Sequence[str],
) -> List[str]:
    """Build the argv for one `codex exec` worker."""
    return [
        codex_bin,
        "exec",
        "--cd",
        str(agent_cwd),
        "--sandbox",
        sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "--output-last-message",
        str(output_path),
        *extra_args,
        "-",
    ]


def build_worker_env(inherited_env: Dict[str, str]) -> Dict[str, str]:
    """Return the environment inherited by a Codex CLI worker."""
    env = os.environ.copy()
    env.update(inherited_env)
    return env


def clamp_worker_timeout(default_timeout_s: int, requested_timeout_s: Optional[int]) -> int:
    """Clamp per-worker timeout to a positive value no larger than the runtime default."""
    worker_timeout_s = requested_timeout_s if requested_timeout_s is not None else default_timeout_s
    return max(1, min(default_timeout_s, worker_timeout_s))
