"""Hierarchical synthesis module for the oh-my-Dynamic project.

Implements the multi-level synthesis strategy inspired by the VMAO paper:
results are first grouped by agent type or category, condensed within each
group, and then integrated into a single coherent answer with source
attribution.

Uses only the Python standard library.  Token usage is optionally tracked
through a :class:`~token_tracker.TokenTracker` instance.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from token_tracker import TokenTracker

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

#: Signature expected for the LLM callable.
#: ``(system_prompt, user_prompt, model) -> str``
LLMFn = Callable[[str, str, str], str]

#: A single agent result is expected to contain at least an ``"output"`` key
#: and optionally ``"agent_type"`` / ``"category"`` keys.
Result = Dict[str, object]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHAR_THRESHOLD = 15_000  # characters
_RESULT_THRESHOLD = 10  # number of result dicts
_DEFAULT_MODEL = "glm-5.1"
_TARGET_CONDENSE_CHARS = 500  # approximate target length per group summary


class Synthesizer:
    """Hierarchical synthesizer that condenses and integrates agent results.

    The synthesis strategy follows two paths:

    * **Small payload** (≤ 15 000 chars **and** ≤ 10 results): a single
      LLM call produces the final answer directly.
    * **Large payload** (> 15 000 chars **or** > 10 results): results are
      first grouped by ``agent_type`` (falling back to ``category``), each
      group is condensed via an LLM call into ~500 chars, and the group
      summaries are integrated into a final coherent answer.

    Args:
        llm_fn: A callable with signature
            ``(system_prompt, user_prompt, model) -> str``.
        token_tracker: Optional :class:`TokenTracker` used to record token
            consumption.  When *None*, token tracking is skipped.

    Example::

        def my_llm(system: str, user: str, model: str) -> str:
            # ... call your LLM API here ...
            return "answer"

        synth = Synthesizer(llm_fn=my_llm)
        answer = synth.synthesize([
            {"agent_type": "researcher", "output": "..."},
            {"agent_type": "critic", "output": "..."},
        ])
    """

    def __init__(
        self,
        llm_fn: LLMFn,
        token_tracker: Optional[TokenTracker] = None,
    ) -> None:
        self._llm_fn = llm_fn
        self._tracker = token_tracker
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self,
        results: List[Result],
        max_group_size: int = 5,
        model: str = _DEFAULT_MODEL,
        original_query: str = "",
    ) -> str:
        """Synthesize a list of agent results into a single answer.

        Args:
            results: Each dict should contain ``"output"`` (str) and
                optionally ``"agent_type"`` or ``"category"`` for grouping.
            max_group_size: Maximum number of results per condensation
                group.  Groups larger than this are split.
            model: LLM model identifier forwarded to *llm_fn*.
            original_query: The original user query, used during the
                integration step for context.

        Returns:
            The final synthesized answer as a string.
        """
        if not results:
            return ""

        total_chars = sum(len(str(r.get("output", ""))) for r in results)

        # ---- Fast path: small enough for single-pass synthesis ----------
        if total_chars <= _CHAR_THRESHOLD and len(results) <= _RESULT_THRESHOLD:
            return self._single_pass(results, model, original_query)

        # ---- Hierarchical path ------------------------------------------
        groups = self._group_results(results, max_group_size)

        condensed: List[str] = []
        for group_key, group_items in groups.items():
            summary = self.condense_group(group_items, model=model)
            condensed.append(summary)

        return self.integrate(condensed, original_query, model=model)

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def condense_group(
        self,
        results: List[Result],
        model: str = _DEFAULT_MODEL,
    ) -> str:
        """Condense a group of related results into a short summary via LLM.

        Args:
            results: A list of result dicts belonging to the same group.
            model: LLM model identifier.

        Returns:
            A condensed summary string (target ~500 chars).
        """
        combined = "\n\n---\n\n".join(
            f"[Agent: {r.get('agent_type', r.get('category', 'unknown'))}]\n"
            f"{r.get('output', '')}"
            for r in results
        )

        system_prompt = (
            "You are a precise summarizer. Condense the following agent "
            "outputs into a single coherent summary of approximately "
            f"{_TARGET_CONDENSE_CHARS} characters. Preserve key facts, "
            "findings, and conclusions. Do not add information not present "
            "in the inputs."
        )

        user_prompt = (
            "Please condense the following agent outputs into a concise summary:\n\n"
            f"{combined}"
        )

        return self._call_llm(system_prompt, user_prompt, model)

    def integrate(
        self,
        summaries: List[str],
        original_query: str,
        model: str = _DEFAULT_MODEL,
    ) -> str:
        """Integrate group summaries into a final coherent answer.

        Args:
            summaries: Condensed summaries from each group.
            original_query: The original user query for context.
            model: LLM model identifier.

        Returns:
            The final integrated answer with source attribution.
        """
        combined_summaries = "\n\n".join(
            f"### Group {i + 1} Summary\n{s}"
            for i, s in enumerate(summaries)
        )

        system_prompt = (
            "You are an expert synthesis integrator. Your job is to combine "
            "multiple group summaries into a single, coherent, comprehensive "
            "answer. Include source attribution where applicable (referencing "
            "agent types or categories). Resolve contradictions by noting "
            "differing perspectives. Produce a well-structured response."
        )

        query_context = (
            f"\n\nOriginal query for context:\n{original_query}"
            if original_query
            else ""
        )

        user_prompt = (
            "Please integrate the following group summaries into a final "
            f"coherent answer:{query_context}\n\n{combined_summaries}"
        )

        return self._call_llm(system_prompt, user_prompt, model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> str:
        """Invoke the LLM function and optionally record token usage.

        Token usage is estimated from character counts (rough heuristic:
        ~4 chars per token) when a tracker is present.
        """
        # 兼容 2 参数和 3 参数的 llm_fn
        try:
            response = self._llm_fn(system_prompt, user_prompt, model)
        except TypeError:
            response = self._llm_fn(system_prompt, user_prompt)

        if self._tracker is not None:
            # Rough token estimate: ~4 chars per token for English text.
            est_prompt = (len(system_prompt) + len(user_prompt)) // 4
            est_completion = len(response) // 4
            self._tracker.record(est_prompt, est_completion, model)

        return response

    @staticmethod
    def _group_results(
        results: List[Result],
        max_group_size: int,
    ) -> Dict[str, List[Result]]:
        """Group results by agent_type (or category) and split oversized groups.

        Args:
            results: Flat list of result dicts.
            max_group_size: Maximum results per group before splitting.

        Returns:
            Mapping of group label to list of results.
        """
        raw_groups: Dict[str, List[Result]] = defaultdict(list)
        for r in results:
            key = str(r.get("agent_type") or r.get("category") or "uncategorized")
            raw_groups[key].append(r)

        # Split groups that exceed max_group_size
        final_groups: Dict[str, List[Result]] = {}
        for key, items in raw_groups.items():
            if len(items) <= max_group_size:
                final_groups[key] = items
            else:
                for idx, start in enumerate(range(0, len(items), max_group_size)):
                    final_groups[f"{key}_part{idx + 1}"] = items[start : start + max_group_size]

        return final_groups

    def _single_pass(
        self,
        results: List[Result],
        model: str,
        original_query: str,
    ) -> str:
        """Direct single-pass synthesis for small payloads."""
        combined = "\n\n---\n\n".join(
            f"[{r.get('agent_type', r.get('category', 'agent'))}]\n"
            f"{r.get('output', '')}"
            for r in results
        )

        query_context = (
            f"\n\nOriginal query:\n{original_query}" if original_query else ""
        )

        system_prompt = (
            "You are an expert synthesizer. Combine the following agent "
            "outputs into a single coherent answer with source attribution. "
            "Resolve any contradictions and highlight key insights."
        )

        user_prompt = (
            f"Synthesize these agent results into a final answer:"
            f"{query_context}\n\n{combined}"
        )

        return self._call_llm(system_prompt, user_prompt, model)
