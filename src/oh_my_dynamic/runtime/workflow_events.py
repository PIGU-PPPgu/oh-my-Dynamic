"""Unified workflow progress events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowEvent:
    id: str = ""
    run_id: str = ""
    kind: str = "event"
    subject: str = ""
    body: str = ""
    node_id: str = ""
    agent_id: str = ""
    status: str = ""
    preview: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"event_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
