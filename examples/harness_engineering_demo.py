#!/usr/bin/env python3
"""Run the deterministic harness-engineering demo validation scenario."""

from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    path = ROOT / "scripts" / "run_demo_validation.py"
    spec = importlib.util.spec_from_file_location("ohmy_demo_validation", path)
    if not spec or not spec.loader:
        raise RuntimeError("failed to load run_demo_validation.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate harness-engineering demo validation evidence.")
    default_output = str(Path(tempfile.gettempdir()) / "ohmy-demo-validation" / "harness_engineering.json")
    parser.add_argument("--output", default=default_output)
    parser.add_argument("--run-id", default="harness_engineering_demo")
    args = parser.parse_args()
    runner = _load_runner()
    return runner.main([
        "--scenarios",
        "harness_engineering",
        "--output",
        args.output,
        "--run-id",
        args.run_id,
    ])


if __name__ == "__main__":
    raise SystemExit(main())
