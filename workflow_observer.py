"""Static observability report generation for workflow evidence."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, List
import json

from workflow_config import REPLAN_COMPLETENESS_THRESHOLD


def render_observability_dashboard(
    run_id: str,
    source: str = ".orchestry",
    output: str = "workflow-observability.html",
) -> str:
    """Render a static HTML dashboard for one workflow run."""
    if not run_id.strip():
        raise ValueError("run_id is required")
    source_path = Path(source)
    data = collect_observability_data(run_id, source_path)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_html(data), encoding="utf-8")
    return str(output_path.resolve())


def collect_observability_data(run_id: str, source: Path) -> Dict[str, Any]:
    events = _collect_jsonl(source, "events.jsonl", run_id)
    artifacts = _collect_jsonl(source, "artifacts.jsonl", run_id)
    traces = _collect_traces(source, run_id)
    checkpoint = _load_checkpoint(source, run_id)
    return {
        "run_id": run_id,
        "source": str(source),
        "events": events,
        "artifacts": artifacts,
        "traces": traces,
        "checkpoint": checkpoint,
        "summary": _summary(events, artifacts, traces, checkpoint),
    }


def _collect_jsonl(source: Path, filename: str, run_id: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(source.rglob(filename)):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            thread_id = str(record.get("thread_id", record.get("metadata", {}).get("thread_id", "")))
            if thread_id == run_id:
                record["_source_path"] = str(path)
                records.append(record)
    return records


def _collect_traces(source: Path, run_id: str) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    for path in sorted(source.rglob("*.json")):
        if path.name in {"agents.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("run_id", "")) == run_id:
            payload["_source_path"] = str(path)
            traces.append(payload)
    return traces


def _load_checkpoint(source: Path, run_id: str) -> Dict[str, Any]:
    path = source / "checkpoints" / f"{run_id}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"_source_path": str(path), "error": "checkpoint could not be parsed"}
    if isinstance(payload, dict):
        payload["_source_path"] = str(path)
        return payload
    return {"_source_path": str(path), "error": "checkpoint was not an object"}


def _summary(
    events: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    checkpoint: Dict[str, Any],
) -> Dict[str, Any]:
    failed_events = [event for event in events if _is_failed_event(event)]
    low_score_events = [
        event for event in events if _event_score(event) < REPLAN_COMPLETENESS_THRESHOLD
    ]
    review_responses = [event for event in events if event.get("kind") == "review_response"]
    agent_ids = sorted({
        str(event.get("from_agent", ""))
        for event in events
        if str(event.get("from_agent", ""))
    })
    return {
        "event_count": len(events),
        "artifact_count": len(artifacts),
        "trace_count": len(traces),
        "agent_count": len(agent_ids),
        "failed_count": len(failed_events),
        "low_score_count": len(low_score_events),
        "review_response_count": len(review_responses),
        "checkpoint": bool(checkpoint),
    }


def _is_failed_event(event: Dict[str, Any]) -> bool:
    text = " ".join([
        str(event.get("kind", "")),
        str(event.get("subject", "")),
        str(event.get("status", "")),
    ]).lower()
    return "failed" in text or event.get("metadata", {}).get("failed")


def _event_score(event: Dict[str, Any]) -> float:
    try:
        return float(event.get("metadata", {}).get("completeness_score", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def _render_html(data: Dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, indent=2).replace("</script", "<\\/script")
    summary = data["summary"]
    cards = [
        ("Events", summary["event_count"]),
        ("Artifacts", summary["artifact_count"]),
        ("Agents", summary["agent_count"]),
        ("Failures", summary["failed_count"]),
        ("Low Scores", summary["low_score_count"]),
        ("Reviews", summary["review_response_count"]),
    ]
    card_html = "\n".join(
        f'<section class="card"><div class="label">{escape(label)}</div><div class="value">{value}</div></section>'
        for label, value in cards
    )
    timeline = "\n".join(_event_row(event) for event in data["events"][:300])
    artifacts = "\n".join(_artifact_row(artifact) for artifact in data["artifacts"][:100])
    traces = "\n".join(_trace_row(trace) for trace in data["traces"])
    checkpoint = _checkpoint_block(data["checkpoint"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>oh-my-Dynamic Observability - {escape(data['run_id'])}</title>
<style>
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f7f8fb; color:#172033; }}
header {{ padding:24px 32px; background:#172033; color:white; }}
main {{ padding:24px 32px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:20px; }}
.card, .panel {{ background:white; border:1px solid #dfe4ee; border-radius:8px; padding:16px; }}
.label {{ color:#667085; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.value {{ font-size:28px; font-weight:700; margin-top:6px; }}
.grid {{ display:grid; grid-template-columns:minmax(0,2fr) minmax(320px,1fr); gap:16px; }}
.row {{ border-top:1px solid #edf0f5; padding:10px 0; }}
.row:first-child {{ border-top:0; }}
.kind {{ display:inline-block; min-width:120px; font-weight:700; color:#2f5f9f; }}
.failed {{ color:#b42318; }}
.low {{ color:#b54708; }}
pre {{ overflow:auto; background:#101828; color:#f2f4f7; padding:12px; border-radius:6px; font-size:12px; }}
h2 {{ font-size:16px; margin:0 0 12px; }}
small {{ color:#667085; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
<h1>oh-my-Dynamic Observability</h1>
<p>Run: <strong>{escape(data['run_id'])}</strong> · Source: {escape(data['source'])}</p>
</header>
<main>
<div class="cards">{card_html}</div>
<div class="grid">
<section class="panel"><h2>Timeline</h2>{timeline or '<p>No events found.</p>'}</section>
<aside class="panel"><h2>Checkpoint</h2>{checkpoint}<h2>Traces</h2>{traces or '<p>No traces found.</p>'}</aside>
</div>
<section class="panel" style="margin-top:16px"><h2>Artifacts</h2>{artifacts or '<p>No artifacts found.</p>'}</section>
<section class="panel" style="margin-top:16px"><h2>Raw Snapshot</h2><pre id="raw"></pre></section>
</main>
<script>
const DATA = {data_json};
document.getElementById("raw").textContent = JSON.stringify(DATA, null, 2);
</script>
</body>
</html>
"""


def _event_row(event: Dict[str, Any]) -> str:
    classes = ["row"]
    if _is_failed_event(event):
        classes.append("failed")
    if _event_score(event) < REPLAN_COMPLETENESS_THRESHOLD:
        classes.append("low")
    subject = str(event.get("subject", ""))
    body = str(event.get("body", ""))[:240]
    created = str(event.get("created_at", ""))
    return (
        f'<div class="{" ".join(classes)}"><span class="kind">{escape(str(event.get("kind", "")))}</span>'
        f'{escape(subject)}<br><small>{escape(created)} · from {escape(str(event.get("from_agent", "")))} '
        f'to {escape(str(event.get("to_agent", "")))}</small>'
        f'<div>{escape(body)}</div></div>'
    )


def _artifact_row(artifact: Dict[str, Any]) -> str:
    content = str(artifact.get("content", ""))[:300]
    return (
        f'<div class="row"><strong>{escape(str(artifact.get("name", "")))}</strong> '
        f'<small>{escape(str(artifact.get("kind", "")))} · {escape(str(artifact.get("producer", "")))}</small>'
        f'<div>{escape(content)}</div></div>'
    )


def _trace_row(trace: Dict[str, Any]) -> str:
    path = escape(str(trace.get("_source_path", "")))
    status = escape(str(trace.get("stop_reason", trace.get("reducer_state", ""))))
    return f'<div class="row"><strong>{path}</strong><br><small>{status}</small></div>'


def _checkpoint_block(checkpoint: Dict[str, Any]) -> str:
    if not checkpoint:
        return "<p>No checkpoint found.</p>"
    path = escape(str(checkpoint.get("_source_path", "")))
    stop = escape(str(checkpoint.get("stop_reason", "")))
    completed = len(checkpoint.get("completed_agent_ids", []) or [])
    failed = len(checkpoint.get("failed_agent_ids", []) or [])
    return f"<p><strong>{path}</strong><br><small>stop={stop} · completed={completed} · failed={failed}</small></p>"
