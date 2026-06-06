"""End-to-end demo: research analysis workflow."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from oh_my_dynamic.runtime.pipeline import DynamicPipeline
from examples.mock_llm import mock_llm


def main() -> None:
    pipeline = DynamicPipeline(mock_llm, max_iterations=1, max_parallel=3, verbose=True)
    result = pipeline.run(
        "Research whether a school district should adopt an AI homework assistant. "
        "Compare benefits, risks, governance requirements, and rollout sequencing."
    )
    print("\n=== Research Analysis Demo ===")
    print(result["final_answer"])
    print(f"Tasks: {result['dag_stats']['completed']}/{result['dag_stats']['total']}")


if __name__ == "__main__":
    main()
