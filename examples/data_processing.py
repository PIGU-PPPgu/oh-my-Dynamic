"""End-to-end demo: data processing workflow."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from oh_my_dynamic.runtime.pipeline import DynamicPipeline
from examples.mock_llm import mock_llm


def main() -> None:
    pipeline = DynamicPipeline(mock_llm, max_iterations=1, max_parallel=3, verbose=True)
    result = pipeline.run(
        "Design a data processing plan for attendance and grade CSV files. "
        "Include validation, cleaning, aggregation, anomaly checks, and report output."
    )
    print("\n=== Data Processing Demo ===")
    print(result["final_answer"])
    print(f"Tasks: {result['dag_stats']['completed']}/{result['dag_stats']['total']}")


if __name__ == "__main__":
    main()
