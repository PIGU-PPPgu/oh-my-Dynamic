"""Deterministic trigger policy for adaptive dynamic workflow replanning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from oh_my_dynamic.broker.broker_reducer import BrokerReductionResult


@dataclass
class ReplanTriggerDecision:
    """Structured evidence that should be shown to the replanner."""

    replan_triggers: List[Dict[str, Any]] = field(default_factory=list)
    missing_coverage: List[str] = field(default_factory=list)
    low_score_agents: List[str] = field(default_factory=list)
    failed_agents: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    followup_agent_budget: int = 0

    @property
    def should_replan(self) -> bool:
        return bool(self.replan_triggers)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReplanTriggerPolicy:
    """Find deterministic reasons to ask the replanner for follow-up agents."""

    def __init__(
        self,
        required_coverage: Optional[Iterable[str]] = None,
        force_missing_coverage: Optional[Iterable[str]] = None,
        min_followup_agents: int = 2,
        max_followup_agents: int = 5,
    ) -> None:
        if min_followup_agents < 1:
            raise ValueError("min_followup_agents must be at least 1")
        if max_followup_agents < min_followup_agents:
            raise ValueError("max_followup_agents must be >= min_followup_agents")
        self.required_coverage = _normalize_items(required_coverage or [])
        self.force_missing_coverage = _normalize_items(force_missing_coverage or [])
        self.min_followup_agents = min_followup_agents
        self.max_followup_agents = max_followup_agents

    def evaluate(
        self,
        reduction: BrokerReductionResult,
        planned_agents: Iterable[Dict[str, Any]],
        completed_agent_ids: Iterable[str],
        failed_agent_ids: Iterable[str],
        low_score_agents: Optional[Iterable[str]] = None,
    ) -> ReplanTriggerDecision:
        planned_records = list(planned_agents)
        completed = {str(agent_id) for agent_id in completed_agent_ids}
        failed = sorted({str(agent_id) for agent_id in failed_agent_ids if str(agent_id)})
        low_score = sorted({str(agent_id) for agent_id in (low_score_agents or []) if str(agent_id)})
        covered_text = _covered_text(planned_records, completed)
        missing = [
            lane for lane in self.required_coverage
            if lane not in covered_text
        ]
        for lane in self.force_missing_coverage:
            if lane not in missing:
                missing.append(lane)

        triggers: List[Dict[str, Any]] = []
        if missing:
            triggers.append({
                "kind": "missing_coverage",
                "lanes": missing,
                "reason": "Required coverage lanes were not represented by completed planner agents.",
            })
        if low_score:
            triggers.append({
                "kind": "low_score_agents",
                "agents": low_score,
                "reason": "Broker evidence includes low-completeness outputs.",
            })
        if failed:
            triggers.append({
                "kind": "failed_agents",
                "agents": failed,
                "reason": "One or more agents failed and need retry or triage.",
            })

        requested = 0
        if triggers:
            requested = min(
                self.max_followup_agents,
                max(self.min_followup_agents, len(missing) + len(low_score) + len(failed)),
            )

        return ReplanTriggerDecision(
            replan_triggers=triggers,
            missing_coverage=missing,
            low_score_agents=low_score,
            failed_agents=failed,
            open_questions=list(reduction.open_questions),
            followup_agent_budget=requested,
        )


def _normalize_items(items: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for item in items:
        value = str(item).strip().lower()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _covered_text(planned_agents: List[Dict[str, Any]], completed_agent_ids: Set[str]) -> str:
    parts: List[str] = []
    for agent in planned_agents:
        agent_id = str(agent.get("id", ""))
        if completed_agent_ids and agent_id not in completed_agent_ids:
            continue
        parts.extend([
            agent_id,
            str(agent.get("role", "")),
            str(agent.get("goal", "")),
            str(agent.get("context", "")),
        ])
    return " ".join(parts).lower()
