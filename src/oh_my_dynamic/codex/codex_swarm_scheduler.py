"""Dependency scheduling helpers for the Codex CLI swarm backend."""

from __future__ import annotations

from typing import Dict, List

from oh_my_dynamic.broker.agent_broker import validate_agent_id
from oh_my_dynamic.codex.codex_swarm_models import CodexCliAgentResult, CodexCliAgentSpec


def topological_layers(agents: List[CodexCliAgentSpec]) -> List[List[CodexCliAgentSpec]]:
    specs_by_id: Dict[str, CodexCliAgentSpec] = {}
    for spec in agents:
        spec.id = validate_agent_id(spec.id)
        if spec.id in specs_by_id:
            raise ValueError(f"duplicate agent id: {spec.id}")
        specs_by_id[spec.id] = spec

    order = {spec.id: index for index, spec in enumerate(agents)}
    dependents: Dict[str, List[str]] = {spec.id: [] for spec in agents}
    indegree: Dict[str, int] = {spec.id: 0 for spec in agents}
    for spec in agents:
        seen_deps = set()
        normalized_deps = []
        for dep_id in spec.dependencies:
            dep_id = validate_agent_id(dep_id, "dependency")
            if dep_id in seen_deps:
                raise ValueError(f"agent {spec.id} has duplicate dependency: {dep_id}")
            if dep_id not in specs_by_id:
                raise ValueError(f"agent {spec.id} depends on unknown agent id: {dep_id}")
            if dep_id == spec.id:
                raise ValueError(f"agent {spec.id} cannot depend on itself")
            seen_deps.add(dep_id)
            normalized_deps.append(dep_id)
            dependents[dep_id].append(spec.id)
            indegree[spec.id] += 1
        spec.dependencies = normalized_deps

    ready = [spec.id for spec in agents if indegree[spec.id] == 0]
    layers: List[List[CodexCliAgentSpec]] = []
    processed: List[str] = []
    while ready:
        layer_ids = ready
        layers.append([specs_by_id[agent_id] for agent_id in layer_ids])
        next_ready: List[str] = []
        for agent_id in layer_ids:
            processed.append(agent_id)
            for child_id in dependents[agent_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    next_ready.append(child_id)
        ready = sorted(next_ready, key=lambda agent_id: order[agent_id])

    if len(processed) != len(agents):
        cycle_ids = [agent_id for agent_id, degree in indegree.items() if degree > 0]
        raise ValueError("cycle detected in CodexCliAgentSpec.dependencies: " + ", ".join(cycle_ids))
    return layers


def ready_batches(layers: List[List[str]], max_parallel: int) -> List[List[str]]:
    batches: List[List[str]] = []
    for layer in layers:
        for index in range(0, len(layer), max_parallel):
            batches.append(layer[index:index + max_parallel])
    return batches


def agent_batches(
    agents: List[CodexCliAgentSpec],
    max_parallel: int,
) -> List[List[CodexCliAgentSpec]]:
    return [agents[index:index + max_parallel] for index in range(0, len(agents), max_parallel)]


def dependency_failure_message(
    spec: CodexCliAgentSpec,
    failed_deps: List[str],
    results_by_id: Dict[str, CodexCliAgentResult],
) -> str:
    details = []
    for dep_id in failed_deps:
        dep = results_by_id[dep_id]
        details.append(f"{dep_id} ({dep.status}: {dep.error or dep.summary})")
    return f"Dependency failed for {spec.id}: " + "; ".join(details)
