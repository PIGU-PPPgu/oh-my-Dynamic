"""Checkpoint helpers for resumable dynamic workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import uuid


def checkpoint_path(checkpoint_dir: str, run_id: str) -> Path:
    if not run_id.strip():
        raise ValueError("run_id is required")
    return Path(checkpoint_dir).expanduser() / f"{run_id}.json"


def save_checkpoint(path: str, payload: Dict[str, Any]) -> str:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return str(target.resolve())


def load_checkpoint(path: str) -> Dict[str, Any]:
    target = Path(path).expanduser()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"checkpoint is not valid JSON: {target}") from exc
    except FileNotFoundError as exc:
        raise ValueError(f"checkpoint not found: {target}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"checkpoint root must be an object: {target}")
    return payload
