# Examples

These examples use a deterministic mock LLM, so they run without API keys:

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/protocol_preview.py
python examples/sandboxed_fanout.py
```

They exercise the same `DynamicPipeline` used in production:

- `research_analysis.py` — research-style decomposition, evidence gathering, and synthesis
- `code_review.py` — security/correctness/test review workflow
- `data_processing.py` — validation, cleaning, aggregation, and reporting workflow
- `protocol_preview.py` — MCP-style tool descriptors and A2A-style Agent Card / Task payloads
- `sandboxed_fanout.py` — local isolated worker fan-out with mock LLM

This demo launches real Codex CLI workers and uses the existing local Codex CLI
login/config, not provider API keys:

```bash
python examples/codex_cli_swarm_review.py --agents 8 --max-parallel 4
```

- `codex_cli_swarm_review.py` — real `codex exec` process swarm with AgentBroker envelopes, manifest, and trace files
