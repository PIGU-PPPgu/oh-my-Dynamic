"""Small Codex CLI worker lifecycle helpers used by the swarm executor."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence
import os

DEFAULT_ENV_ALLOWLIST = {
    "ALL_PROXY",
    "CODEX_HOME",
    "HOME",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NO_PROXY",
    "PATH",
    "SHELL",
    "SSH_AUTH_SOCK",
    "TMPDIR",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
}

BLOCKED_EXTRA_ARGS_WITH_VALUE = {
    "--cd",
    "--output-last-message",
    "--sandbox",
}

BLOCKED_EXTRA_ARGS = {
    "--ephemeral",
    "--skip-git-repo-check",
    "-",
    *BLOCKED_EXTRA_ARGS_WITH_VALUE,
}


def validate_codex_extra_args(extra_args: Sequence[str]) -> List[str]:
    """Reject worker overrides that would break isolation or output capture."""
    cleaned = [str(arg) for arg in extra_args]
    index = 0
    while index < len(cleaned):
        arg = cleaned[index]
        if arg in BLOCKED_EXTRA_ARGS:
            raise ValueError(f"unsafe codex extra arg for worker: {arg}")
        for blocked in BLOCKED_EXTRA_ARGS_WITH_VALUE:
            if arg.startswith(f"{blocked}="):
                raise ValueError(f"unsafe codex extra arg for worker: {arg}")
        index += 1
    return cleaned


def build_codex_exec_command(
    codex_bin: str,
    agent_cwd: Path,
    sandbox: str,
    output_path: Path,
    extra_args: Sequence[str],
) -> List[str]:
    """Build the argv for one `codex exec` worker."""
    safe_extra_args = validate_codex_extra_args(extra_args)
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
        *safe_extra_args,
        "-",
    ]


def build_worker_env(
    inherited_env: Dict[str, str],
    allowlist: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    """Return a minimal environment inherited by a Codex CLI worker."""
    allowed = set(allowlist or DEFAULT_ENV_ALLOWLIST)
    env = {
        key: value
        for key, value in os.environ.items()
        if key in allowed or key.startswith("LC_")
    }
    for key, value in inherited_env.items():
        if key in allowed or key.startswith("OH_MY_DYNAMIC_") or key.startswith("LC_"):
            env[key] = value
    return env


def clamp_worker_timeout(default_timeout_s: int, requested_timeout_s: Optional[int]) -> int:
    """Clamp per-worker timeout to a positive value no larger than the runtime default."""
    worker_timeout_s = requested_timeout_s if requested_timeout_s is not None else default_timeout_s
    return max(1, min(default_timeout_s, worker_timeout_s))
