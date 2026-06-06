#!/usr/bin/env python3
"""Run deterministic oh-my-Dynamic quality evals."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oh_my_dynamic.evals.eval_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
