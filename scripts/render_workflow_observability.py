#!/usr/bin/env python3
"""Render a static workflow observability dashboard."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oh_my_dynamic.evals.workflow_observer import render_observability_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an oh-my-Dynamic static observability dashboard.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", default=".orchestry")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(render_observability_dashboard(args.run_id, source=args.source, output=args.output))


if __name__ == "__main__":
    main()
