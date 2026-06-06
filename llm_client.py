"""Compatibility facade for ``oh_my_dynamic.core.llm_client``.

Prefer importing from ``oh_my_dynamic.core.llm_client`` in new code.
"""

from __future__ import annotations

from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from oh_my_dynamic.core.llm_client import *  # noqa: F401,F403
from oh_my_dynamic.core.llm_client import _detect_provider  # noqa: F401


def _run_module_main() -> int:
    try:
        from oh_my_dynamic.core.llm_client import main as _main
    except ImportError as exc:
        raise SystemExit(f"llm_client has no module entrypoint: {exc}") from exc
    result = _main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(_run_module_main())
