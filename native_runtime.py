"""Compatibility facade for ``oh_my_dynamic.runtime.native_runtime``.

Prefer importing from ``oh_my_dynamic.runtime.native_runtime`` in new code.
"""

from __future__ import annotations

from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from oh_my_dynamic.runtime.native_runtime import *  # noqa: F401,F403


def _run_module_main() -> int:
    try:
        from oh_my_dynamic.runtime.native_runtime import main as _main
    except ImportError as exc:
        raise SystemExit(f"native_runtime has no module entrypoint: {exc}") from exc
    result = _main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(_run_module_main())
