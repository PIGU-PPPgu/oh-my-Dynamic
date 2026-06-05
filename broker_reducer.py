"""Broker-aware reducer for dynamic workflows.

The reducer reads AgentBroker evidence rather than only worker summaries:
artifacts, failures, dependencies, review responses, and worktree diff artifacts.
It can run deterministically for CI, or delegate the final prose to an optional
LLM callable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agent_broker import AgentBroker, BrokerArtifact, BrokerEvent


@dataclass
class BrokerReductionResult:
    final_answer: str
    risk_summary: str
    open_questions: List[str] = field(default_factory=list)
    recommended_next_agents: List[Dict[str, Any]] = field(default_factory=list)
    artifact_ids: List[str] = field(default_factory=list)
    terminal_state: str = "completed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def reduce_broker_thread(
    broker: AgentBroker,
    thread_id: str,
    goal: str,
    llm_fn: Optional[Callable[..., str]] = None,
    model: str = "current",
) -> BrokerReductionResult:
    events = broker.list_events(thread_id=thread_id)
    artifacts = [
        artifact for artifact in broker.list_artifacts()
        if artifact.thread_id == thread_id
        or (artifact.thread_id == "default" and _artifact_referenced(artifact, events))
    ]
    evidence = _collect_evidence(events, artifacts)
    terminal_state = _terminal_state(evidence)
    final_answer = _deterministic_answer(goal, evidence, terminal_state)
    if llm_fn is not None:
        prompt = _llm_prompt(goal, evidence, terminal_state)
        try:
            final_answer = llm_fn(
                "You are a broker-aware reducer. Synthesize only from the provided evidence.",
                prompt,
                model,
            )
        except TypeError:
            final_answer = llm_fn(
                "You are a broker-aware reducer. Synthesize only from the provided evidence.",
                prompt,
            )

    return BrokerReductionResult(
        final_answer=final_answer,
        risk_summary=_risk_summary(evidence),
        open_questions=_open_questions(evidence),
        recommended_next_agents=_recommended_next_agents(evidence),
        artifact_ids=[artifact.id for artifact in artifacts],
        terminal_state=terminal_state,
    )


def _artifact_referenced(artifact: BrokerArtifact, events: List[BrokerEvent]) -> bool:
    return any(artifact.id in event.artifact_ids for event in events)


def _collect_evidence(events: List[BrokerEvent], artifacts: List[BrokerArtifact]) -> Dict[str, Any]:
    completed = [event for event in events if event.kind == "trace" and event.subject == "codex_subagent_completed"]
    failed = [event for event in events if event.kind == "trace" and event.subject == "codex_subagent_failed"]
    review_responses = [event for event in events if event.kind == "review_response"]
    review_requests = [event for event in events if event.kind == "review_request"]
    dependencies = {
        event.from_agent: event.metadata.get("agent", {}).get("metadata", {}).get("dependencies", [])
        for event in events
        if event.kind == "trace" and event.subject == "agent_registered"
    }
    worktree_diffs = [artifact for artifact in artifacts if artifact.kind == "worktree_diff"]
    low_score_events = [event for event in events if _event_score(event) < 0.6]
    return {
        "completed": completed,
        "failed": failed,
        "review_responses": review_responses,
        "review_requests": review_requests,
        "dependencies": dependencies,
        "artifacts": artifacts,
        "worktree_diffs": worktree_diffs,
        "low_score_events": low_score_events,
    }


def _terminal_state(evidence: Dict[str, Any]) -> str:
    if evidence["failed"] and evidence["completed"]:
        return "partial"
    if evidence["failed"]:
        return "failed"
    return "completed"


def _event_score(event: BrokerEvent) -> float:
    try:
        return float(event.metadata.get("completeness_score", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def _deterministic_answer(goal: str, evidence: Dict[str, Any], terminal_state: str) -> str:
    lines = [
        "# Broker Reduction",
        "",
        f"Goal: {goal}",
        f"State: {terminal_state}",
        f"Completed agents: {len(evidence['completed'])}",
        f"Failed agents: {len(evidence['failed'])}",
        f"Artifacts: {len(evidence['artifacts'])}",
        f"Review responses: {len(evidence['review_responses'])}",
        f"Worktree diff artifacts: {len(evidence['worktree_diffs'])}",
        f"Low-score events: {len(evidence['low_score_events'])}",
        "",
        "## Agent Findings",
    ]
    for event in evidence["completed"][:20]:
        lines.append(f"- {event.from_agent}: {event.body[:500]}")
    for event in evidence["failed"][:20]:
        lines.append(f"- FAILED {event.from_agent}: {event.body[:500]}")
    if evidence["review_responses"]:
        lines.append("")
        lines.append("## Reviews")
        for event in evidence["review_responses"][:20]:
            verdict = event.metadata.get("verdict", "commented")
            lines.append(f"- {event.from_agent} -> {event.to_agent}: {verdict}; {event.body[:300]}")
    return "\n".join(lines)


def _risk_summary(evidence: Dict[str, Any]) -> str:
    if evidence["failed"]:
        return f"{len(evidence['failed'])} agent(s) failed; inspect errors before treating output as complete."
    if evidence["review_responses"]:
        changes = [
            event for event in evidence["review_responses"]
            if event.metadata.get("verdict") in ("changes_requested", "rejected")
        ]
        if changes:
            return f"{len(changes)} review response(s) requested changes or rejected output."
    return "No reducer-detected blocking risks."


def _open_questions(evidence: Dict[str, Any]) -> List[str]:
    questions = []
    if evidence["failed"]:
        questions.append("Should failed agents be retried or replaced by a follow-up shard?")
    if not evidence["review_responses"]:
        questions.append("No review responses were recorded; consider adding a reviewer agent for high-risk changes.")
    return questions


def _recommended_next_agents(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    if evidence["low_score_events"]:
        return [
            {
                "id": "low_score_reviewer",
                "role": "quality_reviewer",
                "goal": "Inspect low-completeness outputs and propose targeted follow-up agents.",
                "dependencies": [event.from_agent for event in evidence["low_score_events"]],
            }
        ]
    if not evidence["failed"]:
        return []
    return [
        {
            "id": "failure_triage",
            "role": "failure_triage",
            "goal": "Inspect failed agent outputs and propose retry or recovery actions.",
            "dependencies": [event.from_agent for event in evidence["failed"]],
        }
    ]


def _llm_prompt(goal: str, evidence: Dict[str, Any], terminal_state: str) -> str:
    return "\n".join([
        f"Goal: {goal}",
        f"State: {terminal_state}",
        f"Completed: {len(evidence['completed'])}",
        f"Failed: {len(evidence['failed'])}",
        f"Artifacts: {len(evidence['artifacts'])}",
        _deterministic_answer(goal, evidence, terminal_state),
    ])
