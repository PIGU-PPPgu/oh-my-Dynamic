# Examples

Start with these three paths.

## 1. No-key shape check

```bash
python examples/real_repo_review.py --dry-run --run-id five-minute-demo
```

- Does not launch Codex CLI.
- Writes compact JSON/Markdown evidence shape.
- Safe for install checks and CI-style demos.

## 2. Real 5-agent repo review

```bash
python examples/real_repo_review.py --agents 5 --max-parallel 3 --dashboard
```

- Launches real `codex exec` workers using the local Codex CLI login/config.
- Writes raw traces under `.orchestry/`.
- Writes compact public evidence under `docs/evidence/`.

## 3. Adaptive replanner proof

```bash
python scripts/record_adaptive_workflow_evidence.py \
  --required-coverage security,tests,docs,replanner-proof \
  --force-missing-coverage replanner-proof \
  --max-rounds 2 \
  --max-agents 12 \
  --max-parallel 4 \
  --dashboard
```

- Launches planner/replanner workflow.
- May launch multiple real Codex CLI workers.
- Use `--dry-run` only when validating shape without real workers.

## Reference Demos

These use deterministic mock LLMs and do not require API keys:

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/protocol_preview.py
python examples/sandboxed_fanout.py
```

- `research_analysis.py`: research-style decomposition and synthesis.
- `code_review.py`: security/correctness/test review workflow.
- `data_processing.py`: validation, cleaning, aggregation, reporting workflow.
- `protocol_preview.py`: MCP-style tools and A2A-style payloads.
- `sandboxed_fanout.py`: local isolated worker fan-out with mock LLM.

Real Codex CLI swarm reference:

```bash
python examples/codex_cli_swarm_review.py --agents 8 --max-parallel 4
```

This launches real workers and writes manifests/traces under `.orchestry/`.
