"""Deterministic quality evals for oh-my-Dynamic agent outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import argparse
import json
import re
import time


DEFAULT_SUITE = [
    {
        "id": "security_review",
        "prompt": "Review security risks in this repository.",
        "expected_keywords": ["secret", "subprocess", "auth", "sandbox"],
        "required_evidence": ["file", "line"],
        "min_score": 0.65,
    },
    {
        "id": "install_docs_review",
        "prompt": "Review install experience and README clarity.",
        "expected_keywords": ["install", "README", "skill", "CLI"],
        "required_evidence": ["command", "expected"],
        "min_score": 0.65,
    },
    {
        "id": "dynamic_workflow_alignment",
        "prompt": "Review alignment with dynamic workflow behavior.",
        "expected_keywords": ["planner", "replanner", "broker", "artifact", "checkpoint"],
        "required_evidence": ["trace", "agent"],
        "min_score": 0.70,
    },
    {
        "id": "test_gap_review",
        "prompt": "Review tests, coverage, and evidence gaps.",
        "expected_keywords": ["coverage", "test", "CI", "eval"],
        "required_evidence": ["gap", "recommendation"],
        "min_score": 0.65,
    },
]


@dataclass
class EvalTask:
    id: str
    prompt: str
    expected_keywords: List[str]
    required_evidence: List[str]
    min_score: float = 0.65


@dataclass
class EvalResult:
    task_id: str
    score: float
    passed: bool
    keyword_hits: List[str]
    evidence_hits: List[str]
    missing_keywords: List[str]
    missing_evidence: List[str]
    response_preview: str


def load_eval_suite(path: str) -> List[EvalTask]:
    suite_path = Path(path)
    if suite_path.exists():
        tasks = json.loads(suite_path.read_text(encoding="utf-8")).get("tasks", [])
    elif path == "evals/task_suite.json":
        tasks = DEFAULT_SUITE
    else:
        raise FileNotFoundError(path)
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("eval suite must contain non-empty tasks[]")
    return [
        EvalTask(
            id=str(item["id"]),
            prompt=str(item.get("prompt", "")),
            expected_keywords=[str(value) for value in item.get("expected_keywords", [])],
            required_evidence=[str(value) for value in item.get("required_evidence", [])],
            min_score=float(item.get("min_score", 0.65)),
        )
        for item in tasks
    ]


def load_responses(path: str) -> Dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("responses file must be a JSON object keyed by task id")
    return {str(key): str(value) for key, value in payload.items()}


def sample_responses(tasks: Iterable[EvalTask]) -> Dict[str, str]:
    responses: Dict[str, str] = {}
    for task in tasks:
        keywords = ", ".join(task.expected_keywords)
        evidence = ", ".join(task.required_evidence)
        responses[task.id] = (
            f"Finding for {task.id}: review covers {keywords}. "
            f"Evidence includes {evidence}; file README.md line 1, command python test_suite.py, "
            "trace .orchestry/example/trace.json, agent reviewer_001, gap noted, recommendation recorded."
        )
    return responses


def score_response(task: EvalTask, response: str) -> EvalResult:
    lowered = response.lower()
    keyword_hits = [word for word in task.expected_keywords if word.lower() in lowered]
    evidence_hits = [word for word in task.required_evidence if word.lower() in lowered]
    missing_keywords = [word for word in task.expected_keywords if word not in keyword_hits]
    missing_evidence = [word for word in task.required_evidence if word not in evidence_hits]

    keyword_score = len(keyword_hits) / max(len(task.expected_keywords), 1)
    evidence_score = len(evidence_hits) / max(len(task.required_evidence), 1)
    structure_score = _structure_score(response)
    score = round((keyword_score * 0.50) + (evidence_score * 0.35) + (structure_score * 0.15), 3)
    return EvalResult(
        task_id=task.id,
        score=score,
        passed=score >= task.min_score,
        keyword_hits=keyword_hits,
        evidence_hits=evidence_hits,
        missing_keywords=missing_keywords,
        missing_evidence=missing_evidence,
        response_preview=response.replace("\n", " ")[:240],
    )


def evaluate_responses(tasks: Iterable[EvalTask], responses: Dict[str, str]) -> List[EvalResult]:
    results = []
    for task in tasks:
        response = responses.get(task.id, "")
        results.append(score_response(task, response))
    return results


def summarize_results(results: List[EvalResult]) -> Dict[str, object]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    avg_score = round(sum(result.score for result in results) / max(total, 1), 3)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "avg_score": avg_score,
        "terminal_state": "passed" if passed == total else "failed",
    }


def render_eval_report(results: List[EvalResult], output: str, suite_path: str) -> str:
    summary = summarize_results(results)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# oh-my-Dynamic Quality Eval",
        "",
        "```json",
        json.dumps({
            "suite_path": suite_path,
            "created_at": int(time.time()),
            **summary,
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Results",
        "",
    ]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.extend([
            f"### {result.task_id}: {status} ({result.score})",
            "",
            f"- keyword_hits: {', '.join(result.keyword_hits) or '(none)'}",
            f"- evidence_hits: {', '.join(result.evidence_hits) or '(none)'}",
            f"- missing_keywords: {', '.join(result.missing_keywords) or '(none)'}",
            f"- missing_evidence: {', '.join(result.missing_evidence) or '(none)'}",
            f"- preview: {result.response_preview}",
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path.resolve())


def _structure_score(response: str) -> float:
    if not response.strip():
        return 0.0
    signals = [
        bool(re.search(r"\b(file|line|command|trace|agent|artifact)\b", response, re.I)),
        bool(re.search(r"\b(finding|risk|gap|recommendation)\b", response, re.I)),
        len(response.strip()) >= 80,
    ]
    return sum(1 for signal in signals if signal) / len(signals)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic oh-my-Dynamic quality evals.")
    parser.add_argument("--suite", default="evals/task_suite.json")
    parser.add_argument("--responses", default="", help="JSON object mapping task id to response text.")
    parser.add_argument("--sample", action="store_true", help="Use deterministic sample responses.")
    parser.add_argument("--output", default="docs/evidence/quality_eval.md")
    parser.add_argument("--min-average", type=float, default=0.70)
    args = parser.parse_args(argv)

    tasks = load_eval_suite(args.suite)
    if args.sample:
        responses = sample_responses(tasks)
    elif args.responses:
        responses = load_responses(args.responses)
    else:
        raise SystemExit("pass --sample or --responses RESPONSES.json")

    results = evaluate_responses(tasks, responses)
    report_path = render_eval_report(results, args.output, args.suite)
    summary = summarize_results(results)
    print(json.dumps({"report_path": report_path, **summary}, ensure_ascii=False))
    if summary["avg_score"] < args.min_average or summary["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
