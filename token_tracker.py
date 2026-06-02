"""Token budget tracker for managing LLM API usage across the oh-my-Dynamic project.

Provides thread-safe tracking of prompt/completion token consumption with
configurable budget limits and usage summaries.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class TokenUsage:
    """Record of a single LLM API call's token consumption.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Sum of prompt and completion tokens.
        model: Name of the model used.
        timestamp: Unix timestamp when the usage was recorded.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: float = field(default_factory=time.time)


class TokenTracker:
    """Thread-safe tracker for cumulative token usage against a budget.

    Accumulates token counts across multiple LLM calls and enforces an
    overall budget limit. All public methods are protected by a
    ``threading.Lock`` so the tracker can be shared safely across threads.

    Args:
        max_budget: Maximum number of tokens allowed. Defaults to 1 000 000.

    Example::

        tracker = TokenTracker(max_budget=500_000)
        usage = tracker.record(100, 50, "gpt-4o")
        assert not tracker.is_over_budget()
        assert tracker.remaining() == 499_850
    """

    def __init__(self, max_budget: int = 1_000_000) -> None:
        self._max_budget: int = max_budget
        self._history: List[TokenUsage] = []
        self._total_prompt: int = 0
        self._total_completion: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def record(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> TokenUsage:
        """Record a single LLM call's token usage.

        Args:
            prompt_tokens: Tokens consumed by the prompt.
            completion_tokens: Tokens consumed by the completion.
            model: Identifier of the model that was called.

        Returns:
            A :class:`TokenUsage` instance representing this call.

        Raises:
            ValueError: If *prompt_tokens* or *completion_tokens* is negative.
        """
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("Token counts must be non-negative")

        total = prompt_tokens + completion_tokens
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            model=model,
        )

        with self._lock:
            self._history.append(usage)
            self._total_prompt += prompt_tokens
            self._total_completion += completion_tokens

        return usage

    def remaining(self) -> int:
        """Return the number of tokens still available within the budget."""
        with self._lock:
            return max(0, self._max_budget - self._total_prompt - self._total_completion)

    def is_over_budget(self) -> bool:
        """Return ``True`` if cumulative usage has exceeded the budget."""
        with self._lock:
            return (self._total_prompt + self._total_completion) > self._max_budget

    def can_afford(self, estimated_tokens: int) -> bool:
        """Check whether *estimated_tokens* can be consumed without exceeding the budget.

        Args:
            estimated_tokens: Anticipated token cost of a planned call.

        Returns:
            ``True`` if the budget has enough remaining capacity.
        """
        if estimated_tokens < 0:
            return False
        with self._lock:
            return (self._total_prompt + self._total_completion + estimated_tokens) <= self._max_budget

    def summary(self) -> Dict[str, Any]:
        """Return a snapshot of cumulative usage statistics.

        The returned dictionary contains:

        - ``total_prompt`` – cumulative prompt tokens
        - ``total_completion`` – cumulative completion tokens
        - ``total`` – combined total
        - ``remaining`` – tokens left before hitting the budget
        - ``percent_used`` – budget consumption as a percentage (0–100)
        - ``call_count`` – number of recorded calls
        """
        with self._lock:
            total = self._total_prompt + self._total_completion
            return {
                "total_prompt": self._total_prompt,
                "total_completion": self._total_completion,
                "total": total,
                "remaining": max(0, self._max_budget - total),
                "percent_used": round(total / self._max_budget * 100, 2) if self._max_budget else 0.0,
                "call_count": len(self._history),
            }

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def max_budget(self) -> int:
        """The configured budget ceiling."""
        return self._max_budget

    @property
    def history(self) -> List[TokenUsage]:
        """Return a shallow copy of the recorded usage history."""
        with self._lock:
            return list(self._history)
