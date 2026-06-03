"""Deterministic mock LLM used by examples."""

from __future__ import annotations

import json


def mock_llm(system_prompt: str, user_prompt: str) -> str:
    """Return stable responses for decomposition, worker, replan, and synthesis prompts."""
    prompt = f"{system_prompt}\n{user_prompt}".lower()

    if "拆解" in prompt or "decompose" in prompt or "subtasks" in prompt:
        return json.dumps({
            "subtasks": [
                {
                    "id": "scope",
                    "question": "Clarify the goal, constraints, and success criteria.",
                    "agent_type": "explorer",
                    "priority": 9,
                    "dependencies": [],
                    "verification_criteria": "Covers scope and constraints.",
                },
                {
                    "id": "evidence",
                    "question": "Collect evidence, risks, and tradeoffs for the main decision.",
                    "agent_type": "builder",
                    "priority": 8,
                    "dependencies": ["scope"],
                    "verification_criteria": "Includes concrete risks and tradeoffs.",
                },
                {
                    "id": "recommendation",
                    "question": "Synthesize an actionable recommendation.",
                    "agent_type": "reviewer",
                    "priority": 7,
                    "dependencies": ["scope", "evidence"],
                    "verification_criteria": "Actionable and concise.",
                },
            ]
        }, ensure_ascii=False)

    if (
        "汇总" in prompt
        or "综合回答" in prompt
        or "synthesis" in prompt
        or "synthesizer" in prompt
        or "integrate" in prompt
        or "integrator" in prompt
    ):
        return (
            "Final synthesis:\n"
            "- The workflow separated scope, evidence, and recommendation.\n"
            "- Parallelizable work is explicit in the DAG and dependency chain.\n"
            "- Recommended next step: run the same template with a real provider key."
        )

    if "验证" in prompt or "review" in prompt:
        return "APPROVE: output is coherent, scoped, and actionable."

    return (
        "Mock agent result: identified core requirements, listed practical risks, "
        "and produced a compact recommendation for the requested scenario."
    )
