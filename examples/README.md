# Examples

These examples use a deterministic mock LLM, so they run without API keys:

```bash
python examples/research_analysis.py
python examples/code_review.py
python examples/data_processing.py
python examples/protocol_preview.py
```

They exercise the same `DynamicPipeline` used in production:

- `research_analysis.py` — research-style decomposition, evidence gathering, and synthesis
- `code_review.py` — security/correctness/test review workflow
- `data_processing.py` — validation, cleaning, aggregation, and reporting workflow
- `protocol_preview.py` — MCP-style tool descriptors and A2A-style Agent Card / Task payloads

